#!/usr/bin/env python3
"""Hearth live-state policy, then the exact emitted commands against Redis."""
import unittest
from regressions import CompilerTestCase, ROOT


class PeerLive(CompilerTestCase):
    compiler_arguments = ('--library', str(ROOT / 'library'))

    def test_weight_pause_quarantine_and_trusted_connection_epoch(self):
        self.executes('''use "peerlive" as live
use "errors" as errors
use "json" as json
let input = Bytes("{\\"in_flight\\":2,\\"max_concurrent\\":8,\\"paused\\":false,\\"policy_hash\\":\\"" + "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" + "\\",\\"public_ip\\":\\"203.0.113.2\\",\\"asn\\":64500,\\"country\\":\\"GB\\"}")
let health = live.heartbeat(input)
print(live.ok(health))
let epoch = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
let payload = live.payload(health,"exit-a","edge-a",epoch,1000,3,false,false,1.0)
print(errors.bytesOk(payload))
let state = json.parseBytes(errors.bytesValue(payload),16384)
print(json.member(state,"capacity_weight").number > 0.62499 && json.member(state,"capacity_weight").number < 0.62501)
print(json.member(state,"in_flight").number == 3.0)
print(json.string(state,"_epoch") == epoch)
print(json.member(json.parseBytes(errors.bytesValue(live.payload(health,"exit-a","edge-a",epoch,1000,3,true,false,1.0)),16384),"capacity_weight").number == 0.0)
print(json.member(json.parseBytes(errors.bytesValue(live.payload(health,"exit-a","edge-a",epoch,1000,8,false,false,1.0)),16384),"capacity_weight").number == 0.0)
print(json.member(json.parseBytes(errors.bytesValue(live.payload(health,"exit-a","edge-a",epoch,1000,3,false,true,1.0)),16384),"capacity_weight").number == 0.0)
''', 'true\ntrue\ntrue\ntrue\ntrue\ntrue\ntrue\ntrue\n')

    def test_malformed_heartbeat_and_untrusted_payload_fields_fail_without_trap(self):
        self.executes('''use "peerlive" as live
use "errors" as errors
let base = "{\\"in_flight\\":0,\\"max_concurrent\\":1,\\"paused\\":false,\\"policy_hash\\":\\"" + "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" + "\\",\\"public_ip\\":\\"203.0.113.2\\",\\"asn\\":1,\\"country\\":\\"GB\\"}"
let good = live.heartbeat(Bytes(base))
print(live.ok(good))
for input in ["{}", "{\\"in_flight\\":-1}", base.slice(0,base.length-1) + ",\\"_epoch\\":\\"owned\\"}", base.slice(0,base.length-1) + ",\\"paused\\":false}"] {
    if live.ok(live.heartbeat(Bytes(input))) { fail("malformed heartbeat accepted") }
}
print(errors.bytesOk(live.payload(good,"exit\\nforeign","edge","bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",1,0,false,false,1.0)))
print(errors.bytesOk(live.payload(good,"exit","edge","short",1,0,false,false,1.0)))
print("alive")
''', 'true\nfalse\nfalse\nalive\n')



if __name__ == '__main__':
    unittest.main()
