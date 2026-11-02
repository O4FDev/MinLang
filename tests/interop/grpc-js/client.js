// A stock @grpc/grpc-js client against tests/grpc-interop.min.
// Usage: node client.js h2c|tls PORT [ROOT_PEM]. Messages are raw Buffers, so
// no Protobuf codec is involved on either side. Prints one line per check.
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const grpc = require("@grpc/grpc-js");

const [mode, port, root] = process.argv.slice(2);
const raw = (buffer) => buffer;
const method = (name, responseStream) => ({
    path: "/test.Probe/" + name, requestStream: false, responseStream,
    requestSerialize: raw, requestDeserialize: raw, responseSerialize: raw, responseDeserialize: raw,
});
const Probe = grpc.makeGenericClientConstructor({
    echo: method("Echo", false), count: method("Count", true), fail: method("Fail", false),
    failLater: method("FailLater", true), slow: method("Slow", false), hang: method("Hang", true),
    later: method("Later", false), stats: method("Stats", false), missing: method("Missing", false),
}, "Probe");
const credentials = mode === "tls"
    ? grpc.credentials.createSsl(fs.readFileSync(root))
    : grpc.credentials.createInsecure();
const client = new Probe((mode === "tls" ? "localhost" : "127.0.0.1") + ":" + port, credentials);

function unary(name, request, options = {}, metadata = new grpc.Metadata()) {
    return new Promise((resolve) => {
        const result = { metadata: null, trailers: null };
        const call = client[name](request, metadata, options, (error, response) => {
            result.error = error;
            result.response = response;
        });
        call.on("metadata", (value) => { result.metadata = value; });
        call.on("status", (status) => { result.status = status; setImmediate(() => resolve(result)); });
    });
}
function stream(name, request, options = {}, onData = () => {}) {
    return new Promise((resolve) => {
        const call = client[name](request, new grpc.Metadata(), options);
        const messages = [];
        let error = null;
        call.on("data", (message) => { messages.push(message.toString()); onData(call, messages); });
        call.on("error", (value) => { error = value; });
        call.on("status", (status) => setImmediate(() => resolve({ messages, status, error })));
    });
}
async function stats(name) {
    const result = await unary("stats", Buffer.from(name));
    assert.equal(result.status.code, grpc.status.OK);
    return result.response.toString();
}
function canceled(text) { return Number(text.split("canceled=")[1]); }
async function eventually(name, expected) {
    const deadline = Date.now() + 5000;
    let seen = "";
    while (Date.now() < deadline) {
        seen = await stats(name);
        if (seen === expected) return;
        await new Promise((resolve) => setTimeout(resolve, 20));
    }
    assert.fail(name + ": expected " + expected + ", saw " + seen);
}
function report(text) { console.log(mode + " " + text); }

async function main() {
    const metadata = new grpc.Metadata();
    metadata.set("x-probe", "abc");
    const echo = await unary("echo", Buffer.from("hello gRPC"), {}, metadata);
    assert.equal(echo.status.code, grpc.status.OK, JSON.stringify(echo.status));
    assert.equal(echo.response.toString(), "hello gRPC");
    assert.deepEqual(echo.metadata.get("x-probe-seen"), ["abc"]);
    assert.deepEqual(echo.status.metadata.get("x-served-by"), ["minyar"]);
    const large = Buffer.alloc(3 * 1024 * 1024, 7);
    const big = await unary("echo", large);
    assert.equal(big.status.code, grpc.status.OK);
    assert.ok(big.response.equals(large), "3 MiB echo");
    const empty = await unary("echo", Buffer.alloc(0));
    assert.equal(empty.status.code, grpc.status.OK);
    assert.equal(empty.response.length, 0);
    report("unary ok");

    const counted = await stream("count", Buffer.from("50"));
    assert.equal(counted.status.code, grpc.status.OK);
    assert.equal(counted.messages.length, 50);
    assert.equal(counted.messages[49], "item 49");
    report("server streaming ok");

    const failed = await unary("fail", Buffer.from("x"));
    assert.equal(failed.status.code, grpc.status.NOT_FOUND);
    assert.equal(failed.status.details, "no such thing: 100% gone é");
    assert.deepEqual(failed.status.metadata.get("x-reason"), ["fixture"]);
    const details = failed.status.metadata.get("grpc-status-details-bin")[0];
    const typeUrl = Buffer.from("type.googleapis.com/test.Missing");
    const message = Buffer.from("no such thing: 100% gone é");
    const any = Buffer.concat([Buffer.from([10, typeUrl.length]), typeUrl, Buffer.from([18, 12]), Buffer.from("detail-bytes")]);
    const expected = Buffer.concat([Buffer.from([8, 5, 18, message.length]), message, Buffer.from([26, any.length]), any]);
    assert.ok(details.equals(expected), "google.rpc.Status details " + details.toString("hex"));
    const later = await stream("failLater", Buffer.from("x"));
    assert.equal(later.status.code, grpc.status.PERMISSION_DENIED);
    assert.deepEqual(later.messages, ["before"]);
    const missing = await unary("missing", Buffer.from("x"));
    assert.equal(missing.status.code, grpc.status.UNIMPLEMENTED);
    report("handler errors ok");

    const deferred = await unary("later", Buffer.from("x"));
    assert.equal(deferred.status.code, grpc.status.OK);
    assert.equal(deferred.response.toString(), "answered later");
    const slowBefore = canceled(await stats("slow"));
    const started = Date.now();
    const slow = await unary("slow", Buffer.from("x"), { deadline: Date.now() + 300 });
    assert.equal(slow.status.code, grpc.status.DEADLINE_EXCEEDED);
    assert.ok(Date.now() - started < 3000);
    await eventually("slow", "slow open=0 canceled=" + (slowBefore + 1));
    report("deadline ok");

    const hangBefore = canceled(await stats("hang"));
    const hung = await stream("hang", Buffer.from("x"), {}, (call, messages) => { if (messages.length === 1) call.cancel(); });
    assert.equal(hung.status.code, grpc.status.CANCELLED);
    assert.deepEqual(hung.messages, ["first"]);
    await eventually("hang", "hang open=0 canceled=" + (hangBefore + 1));
    report("cancellation ok");
    client.close();
}
main().catch((error) => { console.error(mode + " " + (error.stack || error)); process.exit(1); });
