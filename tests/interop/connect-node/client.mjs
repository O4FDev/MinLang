// check-connect-node: stock @connectrpc/connect-node calls the Minyar server
// (server.min) over HTTP/1.1 with the binary and JSON codecs, and checks
// results, metadata and the code of every kind of failure.
// Usage: node client.mjs PORT
import { createClient, ConnectError, Code } from "@connectrpc/connect";
import { createConnectTransport, compressionGzip, compressionBrotli } from "@connectrpc/connect-node";
import { create, fromBinary, createFileRegistry } from "@bufbuild/protobuf";
import { FileDescriptorSetSchema } from "@bufbuild/protobuf/wkt";

// protoc --descriptor_set_out=/dev/stdout interop.proto | base64
const DESCRIPTOR = "CsIECg1pbnRlcm9wLnByb3RvEhFtaW55YXIuaW50ZXJvcC52MSJJCgRQaW5nEhIKBHRleHQYASABKAlSBHRleHQSEgoEY29kZRgCIAEoBVIEY29kZRIZCghkZWxheV9tcxgDIAEoBVIHZGVsYXlNcyIaCgRQb25nEhIKBHRleHQYASABKAlSBHRleHQyrgMKB0ludGVyb3ASOAoERWNobxIXLm1pbnlhci5pbnRlcm9wLnYxLlBpbmcaFy5taW55YXIuaW50ZXJvcC52MS5Qb25nEjgKBEZhaWwSFy5taW55YXIuaW50ZXJvcC52MS5QaW5nGhcubWlueWFyLmludGVyb3AudjEuUG9uZxI4CgRTbG93EhcubWlueWFyLmludGVyb3AudjEuUGluZxoXLm1pbnlhci5pbnRlcm9wLnYxLlBvbmcSPwoGTG9va3VwEhcubWlueWFyLmludGVyb3AudjEuUGluZxoXLm1pbnlhci5pbnRlcm9wLnYxLlBvbmciA5ACARI5CgVDb3VudBIXLm1pbnlhci5pbnRlcm9wLnYxLlBpbmcaFy5taW55YXIuaW50ZXJvcC52MS5Qb25nEjsKB01pc3NpbmcSFy5taW55YXIuaW50ZXJvcC52MS5QaW5nGhcubWlueWFyLmludGVyb3AudjEuUG9uZxI8CgZTdHJlYW0SFy5taW55YXIuaW50ZXJvcC52MS5QaW5nGhcubWlueWFyLmludGVyb3AudjEuUG9uZzABYgZwcm90bzM=";
const registry = createFileRegistry(fromBinary(FileDescriptorSetSchema, Buffer.from(DESCRIPTOR, "base64")));
const service = registry.getService("minyar.interop.v1.Interop");
const PongSchema = registry.getMessage("minyar.interop.v1.Pong");
const baseUrl = "http://127.0.0.1:" + process.argv[2];
const NAMES = ["ok", "canceled", "unknown", "invalid_argument", "deadline_exceeded", "not_found", "already_exists",
  "permission_denied", "resource_exhausted", "failed_precondition", "aborted", "out_of_range", "unimplemented",
  "internal", "unavailable", "data_loss", "unauthenticated"];

let checks = 0;
function expect(condition, message) {
  if (!condition) throw new Error("check failed: " + message);
  checks += 1;
}
async function failure(promise) {
  try {
    await promise;
  } catch (error) {
    return ConnectError.from(error);
  }
  throw new Error("call succeeded unexpectedly");
}

for (const useBinaryFormat of [true, false]) {
  const format = useBinaryFormat ? "proto" : "json";
  const client = createClient(service, createConnectTransport({ baseUrl, httpVersion: "1.1", useBinaryFormat }));

  let headers, trailers;
  const pong = await client.echo({ text: "hello" }, { headers: { "x-call": "abc" }, onHeader: (h) => { headers = h; }, onTrailer: (t) => { trailers = t; } });
  expect(pong.text === "hello via " + format, format + " echo text " + pong.text);
  expect(headers.get("x-echo-header") === "abc", format + " response header");
  expect(/^[0-9]+$/.test(trailers.get("x-echo-trailer") ?? ""), format + " response trailer");

  for (let code = 1; code <= 16; code++) {
    const error = await failure(client.fail({ text: "failure " + code, code }));
    expect(error.code === code, format + " code " + code + " came back as " + error.code);
    expect(error.rawMessage === "failure " + code, format + " message " + error.rawMessage);
    expect(error.metadata.get("x-failed") === "yes", format + " error header for " + code);
    expect(error.metadata.get("x-failed-trailer") === "late", format + " error trailer for " + code);
    expect(error.details.length === 1, format + " one detail for " + code);
    const detail = error.details[0];
    expect(detail.desc === undefined && detail.type === "minyar.interop.v1.Pong", format + " detail type " + detail.type);
    expect(fromBinary(PongSchema, detail.value).text === "detail for " + NAMES[code], format + " detail value for " + code);
  }

  const missing = await failure(client.missing({ text: "x" }));
  expect(missing.code === Code.Unimplemented, format + " missing method " + missing.code);

  const late = await failure(client.slow({ delayMs: 400 }, { timeoutMs: 100 }));
  expect(late.code === Code.DeadlineExceeded, format + " deadline " + late.code);
  const quick = await client.slow({ delayMs: 1 }, { timeoutMs: 5000 });
  expect(quick.text === "slept 1", format + " within deadline");

  const large = await failure(client.echo({ text: "x".repeat(5000) }));
  expect(large.code === Code.ResourceExhausted, format + " oversized request " + large.code);

  const gzipClient = createClient(service, createConnectTransport({ baseUrl, httpVersion: "1.1", useBinaryFormat,
    sendCompression: compressionGzip, acceptCompression: [compressionGzip], compressMinBytes: 1 }));
  const gzipped = await gzipClient.echo({ text: "y".repeat(3000) });
  expect(gzipped.text === "y".repeat(3000) + " via " + format, format + " gzip round trip");
  const brotliClient = createClient(service, createConnectTransport({ baseUrl, httpVersion: "1.1", useBinaryFormat, sendCompression: compressionBrotli, compressMinBytes: 1 }));
  const brotli = await failure(brotliClient.echo({ text: "z".repeat(2000) }));
  expect(brotli.code === Code.Unimplemented, format + " unsupported compression " + brotli.code);

  const getClient = createClient(service, createConnectTransport({ baseUrl, httpVersion: "1.1", useBinaryFormat, useHttpGet: true }));
  const looked = await getClient.lookup({ text: "by get" });
  expect(looked.text === "by get via " + format, format + " GET " + looked.text);

  const streamed = [];
  let streamTrailers;
  for await (const item of client.stream({ text: "s", code: 3 }, { onTrailer: (t) => { streamTrailers = t; } })) streamed.push(item.text);
  expect(streamed.join(",") === "s 1/3,s 2/3,s 3/3", format + " stream " + streamed.join(","));
  expect(streamTrailers.get("x-sent") === "3", format + " stream trailer");
  const partial = [];
  const aborted = await failure((async () => { for await (const item of client.stream({ text: "fail", code: 2 })) partial.push(item.text); })());
  expect(aborted.code === Code.Aborted && partial.length === 2 && aborted.details.length === 1, format + " stream error " + aborted.code + " after " + partial.length);
  const started = Date.now();
  const times = [];
  for await (const item of client.stream({ text: "t", code: 3, delayMs: 60 })) times.push(Date.now() - started);
  expect(times.length === 3 && times[2] - times[0] >= 100, format + " messages arrive over time " + times.join(","));
  const cut = [];
  const expired = await failure((async () => { for await (const item of client.stream({ text: "d", code: 10, delayMs: 80 }, { timeoutMs: 200 })) cut.push(item.text); })());
  expect(expired.code === Code.DeadlineExceeded && cut.length >= 1 && cut.length < 10, format + " stream deadline " + expired.code + " after " + cut.length);

  const key = "retry-" + format;
  let replayed;
  const first = await client.count({}, { headers: { "idempotency-key": key } });
  const second = await client.count({}, { headers: { "idempotency-key": key }, onHeader: (h) => { replayed = h.get("idempotent-replayed"); } });
  expect(first.text === second.text && replayed === "true", format + " idempotent retry " + first.text + " " + second.text);
  const reused = await failure(client.count({ text: "other" }, { headers: { "idempotency-key": key } }));
  expect(reused.code === Code.InvalidArgument, format + " reused key " + reused.code);
}

const preflight = await fetch(baseUrl + "/minyar.interop.v1.Interop/Echo", { method: "OPTIONS",
  headers: { origin: "https://app.example", "access-control-request-method": "POST", "access-control-request-headers": "content-type,connect-protocol-version" } });
expect(preflight.status === 204, "preflight status " + preflight.status);
expect(preflight.headers.get("access-control-allow-origin") === "https://app.example", "preflight origin");
expect(preflight.headers.get("access-control-allow-headers").includes("connect-protocol-version"), "preflight headers");
const denied = await fetch(baseUrl + "/minyar.interop.v1.Interop/Echo", { method: "OPTIONS",
  headers: { origin: "https://evil.example", "access-control-request-method": "POST" } });
expect(denied.headers.get("access-control-allow-origin") === null, "foreign origin");

console.log("connect-node interop: " + checks + " checks passed");
