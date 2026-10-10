#!/usr/bin/env python3
"""Redis stream fragmentation, FIFO correlation and bounded backpressure."""
import unittest
from regressions import CompilerTestCase, ROOT


class RedisPipeline(CompilerTestCase):
    compiler_arguments = ('--library', str(ROOT / 'library'))

    def test_short_writes_and_coalesced_replies_preserve_fifo(self):
        self.executes('''use "redis" as redis
use "resp2" as resp
use "errors" as errors
let client = redis.create()
print(errors.booleanOk(redis.queue(client,[Bytes("PING")])))
print(redis.pending(client))
let first = redis.outgoing(client,65536)
print(first.length)
redis.sent(client,3)
print(redis.outgoing(client,65536).length == first.length - 3)
redis.sent(client,first.length - 3)
redis.queue(client,[Bytes("GET"),Bytes("key")])
redis.sent(client,redis.outgoing(client,65536).length)
redis.feed(client,Bytes("+PONG\\r\\n$-1\\r\\n"))
print(Text(resp.data(redis.value(redis.reply(client)))))
print(resp.kind(redis.value(redis.reply(client))) == resp.NULL_BULK)
print(redis.pending(client))
print(errors.isWouldBlock(redis.error(redis.reply(client))))
''', 'true\n1\n14\ntrue\nPONG\ntrue\n0\ntrue\n')

    def test_many_fragmented_binary_replies_and_error_values(self):
        self.executes('''use "redis" as redis
use "resp2" as resp
use "errors" as errors
let client = redis.create(); let count = 0
for index in 0..2000 { redis.queue(client,[Bytes("PING")]) }
redis.sent(client,redis.outgoing(client,65536).length)
for byte in Bytes("$2\\r\\n") { let piece = Bytes(1); piece[0] = byte; redis.feed(client,piece); if redis.ok(redis.reply(client)) { fail("partial reply accepted") } }
let binary = Bytes(); binary.add(0); binary.add(255); binary.addBytes(Bytes("\\r\\n"))
redis.feed(client,binary)
print(resp.data(redis.value(redis.reply(client)))[1])
let replies = Bytes()
for index in 0..1998 { replies.addBytes(Bytes(":" + Text(index) + "\\r\\n")) }
replies.addBytes(Bytes("-ERR ordinary rejection\\r\\n")); redis.feed(client,replies)
for index in 0..1998 {
    let response = redis.reply(client)
    if !redis.ok(response) || resp.integer(redis.value(response)) != index { fail("FIFO changed") }
    count += 1
}
print(count); print(resp.kind(redis.value(redis.reply(client))) == resp.ERROR)
print(redis.pending(client)); print(redis.closed(client))
''', '255\n1998\ntrue\n0\nfalse\n')

    def test_malformed_unsolicited_and_closed_inputs_fail_recoverably(self):
        self.executes('''use "redis" as redis
use "errors" as errors
let client = redis.create(); redis.queue(client,[Bytes("PING")])
redis.feed(client,Bytes("$2\\r\\na"))
print(errors.isWouldBlock(redis.error(redis.reply(client))))
redis.feed(client,Bytes("bXX"))
print(errors.code(redis.error(redis.reply(client))) == errors.invalidDataCode())
print(redis.closed(client)); print(redis.pending(client))
print(errors.booleanOk(redis.queue(client,[Bytes("PING")])))
let unsolicited = redis.create(); redis.feed(unsolicited,Bytes("+unexpected\\r\\n"))
print(errors.code(redis.error(redis.reply(unsolicited))) == errors.protocolCode())
print(redis.closed(unsolicited))
let ended = redis.create(); redis.queue(ended,[Bytes("PING")]); redis.feed(ended,Bytes("+part")); redis.endInput(ended)
print(errors.code(redis.error(redis.reply(ended))) == errors.truncatedCode())
print("alive")
''', 'true\ntrue\ntrue\n0\nfalse\ntrue\ntrue\ntrue\nalive\n')

    def test_backpressure_does_not_partially_queue_and_bounds_do_not_trap(self):
        self.executes('''use "redis" as redis
use "errors" as errors
let client = redis.create()
redis.queue(client,[Bytes(1000000)])
let before = redis.pending(client)
print(errors.isWouldBlock(errors.booleanError(redis.queue(client,[Bytes(100000)]))))
print(redis.pending(client) == before)
print(redis.outgoing(client,65536).length)
let other = redis.create()
for index in 0..4096 { if !errors.booleanOk(redis.queue(other,[Bytes("PING")])) { fail("early queue bound") } }
print(errors.isWouldBlock(errors.booleanError(redis.queue(other,[Bytes("PING")]))))
print(redis.pending(other))
print(errors.booleanOk(redis.feed(other,Bytes(2097153))))
print(redis.closed(other)); print(redis.pending(other))
''', 'true\ntrue\n65536\ntrue\n4096\nfalse\ntrue\n0\n')

    def test_reply_before_a_complete_request_is_not_correlated(self):
        self.executes('''use "redis" as redis
use "errors" as errors
let client = redis.create(); redis.queue(client,[Bytes("PING")]); redis.sent(client,1)
redis.feed(client,Bytes("+PONG\\r\\n"))
print(errors.code(redis.error(redis.reply(client))) == errors.protocolCode())
print(redis.closed(client))
''', 'true\ntrue\n')

    def test_complete_replies_drain_after_eof_then_report_unanswered_request(self):
        self.executes('''use "redis" as redis
use "resp2" as resp
use "errors" as errors
let client = redis.create()
for index in 0..3 { redis.queue(client,[Bytes("PING")]) }
redis.sent(client,redis.outgoing(client,65536).length)
redis.feed(client,Bytes("+first\\r\\n+second\\r\\n")); redis.endInput(client)
print(Text(resp.data(redis.value(redis.reply(client)))))
print(Text(resp.data(redis.value(redis.reply(client)))))
print(errors.code(redis.error(redis.reply(client))) == errors.closedCode())
print(redis.pending(client))
''', 'first\nsecond\ntrue\n0\n')

    def test_continuous_partial_writes_keep_request_boundaries_after_compaction(self):
        self.executes('''use "redis" as redis
use "resp2" as resp
use "errors" as errors
let client = redis.create(); redis.queue(client,[Bytes("PING")]); redis.queue(client,[Bytes("PING")])
redis.sent(client,1)
for index in 0..12000 {
    redis.sent(client,14)
    redis.feed(client,Bytes(":" + Text(index) + "\\r\\n"))
    let response = redis.reply(client)
    if !redis.ok(response) || resp.integer(redis.value(response)) != index { fail("write boundary changed") }
    if redis.pending(client) != 1 { fail("wrong pipeline count") }
    if !errors.booleanOk(redis.queue(client,[Bytes("PING")])) { fail("continuous queue blocked") }
}
redis.sent(client,redis.outgoing(client,65536).length)
redis.feed(client,Bytes("+last\\r\\n+tail\\r\\n"))
print(Text(resp.data(redis.value(redis.reply(client)))))
print(Text(resp.data(redis.value(redis.reply(client)))))
print(redis.pending(client)); print(redis.closed(client))
''', 'last\ntail\n0\nfalse\n')


if __name__ == '__main__':
    unittest.main()
