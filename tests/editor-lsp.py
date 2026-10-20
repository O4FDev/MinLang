#!/usr/bin/env python3
"""Real framed stdio tests; no editor SDK or network is required."""
import argparse
import atexit
import json
import os
from pathlib import Path
import selectors
import signal
import shutil
import subprocess
import sys
import tempfile
import time


class Client:
    def __init__(self, command):
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, start_new_session=True)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        self.buffer = bytearray()
        self.notifications = []
        self.serial = 0
        self.transcript = []
        atexit.register(self.abort)

    def abort(self):
        if self.process.poll() is None:
            os.killpg(self.process.pid, 9)
            self.process.wait()

    def send(self, method, params=None, ident=None):
        value = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            value["params"] = params
        if ident is not None:
            value["id"] = ident
        self.transcript.append({"send": value})
        raw = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
        wire = f"Content-Length: {len(raw)}\r\nContent-Type: application/vscode-jsonrpc; charset=utf-8\r\n\r\n".encode() + raw
        # Split both header and body at non-message boundaries, without delays.
        for chunk in (wire[:7], wire[7:43], wire[43:]):
            self.process.stdin.write(chunk)
            self.process.stdin.flush()

    def receive(self, timeout=40):
        deadline = time.monotonic() + timeout
        while True:
            end = self.buffer.find(b"\r\n\r\n")
            if end >= 0:
                headers = dict(line.split(b":", 1) for line in bytes(self.buffer[:end]).split(b"\r\n"))
                length = int(headers[b"Content-Length"].strip())
                assert length <= 16 * 1024 * 1024
                if len(self.buffer) >= end + 4 + length:
                    value = json.loads(self.buffer[end + 4:end + 4 + length])
                    del self.buffer[:end + 4 + length]
                    assert value["jsonrpc"] == "2.0", value
                    self.transcript.append({"receive": value})
                    return value
            remaining = deadline - time.monotonic()
            assert remaining > 0, "language server response timed out"
            ready = self.selector.select(remaining)
            assert ready, "language server response timed out"
            chunk = os.read(self.process.stdout.fileno(), 65536)
            if not chunk:
                self.abort()
                raise AssertionError(f"language server closed stdout: {self.process.stderr.read().decode(errors='replace')}")
            self.buffer.extend(chunk)

    def request(self, method, params=None, ident=None):
        self.serial += 1
        ident = self.serial if ident is None else ident
        self.send(method, params, ident)
        while True:
            message = self.receive()
            if "id" in message:
                assert message["id"] == ident, message
                return message
            self.notifications.append(message)

    def diagnostics(self, uri, version):
        while True:
            for position, message in enumerate(self.notifications):
                params = message.get("params", {})
                if message.get("method") == "textDocument/publishDiagnostics" and params.get("uri") == uri and params.get("version") == version:
                    self.notifications.pop(position)
                    return params["diagnostics"]
            self.notifications.append(self.receive())

    def close(self):
        try:
            assert self.request("shutdown")["result"] is None
            self.send("exit")
            self.process.stdin.close()
            assert self.process.wait(timeout=10) == 0
            errors = self.process.stderr.read()
            assert not errors, errors.decode(errors="replace")
        finally:
            self.selector.close()
            if self.process.poll() is None:
                os.killpg(self.process.pid, 9)
                self.process.wait()


def point(source, needle, occurrence=0, offset=0):
    position = -1
    for _ in range(occurrence + 1):
        position = source.index(needle, position + 1)
    position += offset
    line = source.count("\n", 0, position)
    start = source.rfind("\n", 0, position) + 1
    character = len(source[start:position].encode("utf-16-le")) // 2
    return {"line": line, "character": character}


def run(server, compiler):
    temporary = tempfile.mkdtemp(prefix="minyar lsp café ")
    print("LSP evidence:", temporary, flush=True)
    try:
        root = Path(temporary).resolve()
        extra = root / "extra-src"
        extra.mkdir()
        (extra / "weather.min").write_text('/// A west wind.\npublic function wind(): Integer { return 2 }\n')
        dependency = root / "packages" / "tide" / "src"
        dependency.mkdir(parents=True)
        (dependency / "tide.min").write_text('public function height(): Integer { return 3 }\n')
        (root / "Minyar.lock").write_text('version = 1\n[[package]]\nname = "tide"\npath = "./packages/tide"\n')
        module = root / "sky.min"
        module.write_text('''/// Twice the light.
public function twice(value: Integer): Integer { return value * 2 }
function hidden(): Integer { return 0 }
/// A lamp at sea.
public record Lamp { light: Integer; private secret: Integer }
public function make(): Lamp { return Lamp { light: 42; secret: 7 } }
''')
        path = root / "main #星.min"
        source = '''use "./sky.min" as sky
/// Keep a small light.
record Lantern { light: Integer }
function Lantern.brighten(amount: Integer) { self.light += amount }
function greet(name: Text): Text {
    let inside: Integer = 3
    return "hello, \\(name)"
}
let lamp = Lantern { light: 40 }
lamp.brighten(2)
let offshore = sky.make()
print(offshore.light)
let caption = "🌙"; print(lamp.light)
print(sky.twice(21))
use "weather" as weather
use "tide" as tide
print(weather.wind() + tide.height())
type Beacon = Lantern
let beacon: Beacon = Lantern { light: 1 }
print(beacon.light)
choice Glow { Dawn; Dusk }
let glow = Glow.Dawn
print(match glow { Dawn { "warm" } Dusk { "cool" } })
'''
        path.write_text(source)
        uri = path.as_uri()
        client = Client([server, "--compiler", compiler])
        assert client.request("textDocument/hover", {})["error"]["code"] == -32002
        initialized = client.request("initialize", {"rootUri": root.as_uri(), "capabilities": {}, "initializationOptions": {"libraryPaths": ["extra-src"]}}, ident="café")
        capabilities = initialized["result"]["capabilities"]
        assert capabilities["positionEncoding"] == "utf-16"
        assert capabilities["textDocumentSync"]["change"] == 2
        client.send("initialized", {})
        client.send("textDocument/didOpen", {"textDocument": {"uri": uri, "languageId": "minyar", "version": 1, "text": source}})
        initial_diagnostics = client.diagnostics(uri, 1)
        assert initial_diagnostics == [], initial_diagnostics

        def query(method, text, needle, occurrence=0, offset=0):
            return client.request("textDocument/" + method, {"textDocument": {"uri": uri}, "position": point(text, needle, occurrence, offset)})["result"]

        hover = query("hover", source, "Lantern", offset=2)
        assert "record Lantern" in hover["contents"]["value"] and "Keep a small light" in hover["contents"]["value"], hover
        hover = query("hover", source, "twice", occurrence=0, offset=2)
        assert "Integer" in hover["contents"]["value"] and "Twice the light" in hover["contents"]["value"], hover
        definition = query("definition", source, "twice", offset=2)
        assert definition["uri"] == module.as_uri() and definition["range"]["start"] == {"line": 1, "character": 16}, definition
        definition = query("definition", source, "lamp.light", offset=6)
        assert definition["range"]["start"] == {"line": 2, "character": 17}, definition
        hover = query("hover", source, "offshore.light", offset=10)
        assert "light: Integer" in hover["contents"]["value"], hover
        hover = query("hover", source, "offshore", offset=2)
        assert "let offshore: sky.Lamp" in hover["contents"]["value"], hover
        members = query("completion", source, "lamp.light", offset=5)
        assert {item["label"] for item in members} >= {"light", "brighten"}, members
        members = query("completion", source, "sky.twice", offset=4)
        labels = {item["label"] for item in members}
        assert {"twice", "Lamp", "make"} <= labels and "hidden" not in labels, members
        members = query("completion", source, "offshore.light", offset=9)
        assert "light" in {item["label"] for item in members} and "secret" not in {item["label"] for item in members}, members
        members = query("completion", source, "beacon.light", offset=7)
        assert {item["label"] for item in members} >= {"light", "brighten"}, members
        members = query("completion", source, "Glow.Dawn", offset=5)
        assert {item["label"] for item in members} >= {"Dawn", "Dusk"}, members
        definition = query("definition", source, "weather.wind", offset=10)
        assert definition["uri"] == (extra / "weather.min").as_uri(), definition
        definition = query("definition", source, "tide.height", offset=8)
        assert definition["uri"] == (dependency / "tide.min").as_uri(), definition
        names = query("completion", source, "print(sky", offset=0)
        assert "inside" not in {item["label"] for item in names}, names
        symbols = client.request("textDocument/documentSymbol", {"textDocument": {"uri": uri}})["result"]
        assert {item["name"] for item in symbols} >= {"Lantern", "Lantern.light", "Lantern.brighten", "greet", "lamp"}, symbols
        edits = client.request("textDocument/formatting", {"textDocument": {"uri": uri}, "options": {"tabSize": 4, "insertSpaces": True}})["result"]
        assert len(edits) == 1 and 'record Lantern {\n    light: Integer\n}' in edits[0]["newText"], edits
        assert path.read_text() == source
        assert query("hover", source, "lamp.light", offset=6)["range"]["start"] == point(source, "lamp.light", offset=5)

        # The character before this edit is non-BMP; positions are UTF-16 units.
        old = point(source, "🌙", offset=0)
        end = dict(old, character=old["character"] + 2)
        changed = source.replace("🌙", "✨")
        client.send("textDocument/didChange", {"textDocument": {"uri": uri, "version": 2}, "contentChanges": [{"range": {"start": old, "end": end}, "text": "✨"}]})
        assert client.diagnostics(uri, 2) == []
        assert query("hover", changed, "lamp.light", offset=6)["range"]["start"] == point(changed, "lamp.light", offset=5)

        broken = changed.replace('use "./sky.min" as sky', 'use "./sky.min" as sky; print("🌙"); print(missing)')
        client.send("textDocument/didChange", {"textDocument": {"uri": uri, "version": 3}, "contentChanges": [{"text": broken}]})
        errors = client.diagnostics(uri, 3)
        assert errors and errors[0]["severity"] == 1 and "missing" in errors[0]["message"], errors
        assert errors[0]["range"]["start"] == point(broken, "missing"), errors
        # A stale version cannot replace the current buffer or republish it.
        client.send("textDocument/didChange", {"textDocument": {"uri": uri, "version": 2}, "contentChanges": [{"text": "print(0)\n"}]})
        assert "lamp" in {item["name"] for item in client.request("textDocument/documentSymbol", {"textDocument": {"uri": uri}})["result"]}
        client.send("textDocument/didChange", {"textDocument": {"uri": uri, "version": 4}, "contentChanges": [{"text": changed}]})
        assert client.diagnostics(uri, 4) == []
        assert path.read_text() == source
        assert client.request("textDocument/unknown", {"textDocument": {"uri": uri}})["error"]["code"] == -32601
        assert client.request("minyar/unknown")["error"]["code"] == -32601
        module_source = module.read_text()
        client.send("textDocument/didOpen", {"textDocument": {"uri": module.as_uri(), "languageId": "minyar", "version": 1, "text": module_source}})
        assert client.diagnostics(module.as_uri(), 1) == []
        invalid_module = module_source.replace("return value * 2", "return missingValue")
        client.send("textDocument/didChange", {"textDocument": {"uri": module.as_uri(), "version": 2}, "contentChanges": [{"text": invalid_module}]})
        module_errors = client.diagnostics(module.as_uri(), 2)
        assert module_errors and module_errors[0]["range"]["start"]["line"] == 1, module_errors
        # Ask a feature after all change diagnostics have been processed, then
        # require the import-root compilation to see the unsaved module too.
        query("hover", changed, "twice", offset=2)
        assert any(message.get("method") == "textDocument/publishDiagnostics" and message["params"]["uri"] == module.as_uri() and message["params"]["diagnostics"] for message in client.notifications), client.notifications
        assert module.read_text() == module_source
        client.send("textDocument/didChange", {"textDocument": {"uri": module.as_uri(), "version": 3}, "contentChanges": [{"text": module_source}]})
        assert client.diagnostics(module.as_uri(), 3) == []
        client.send("textDocument/didClose", {"textDocument": {"uri": module.as_uri()}})
        # Invalid disk dependencies produce a diagnostic, not a server crash.
        module.write_bytes(b"\xff")
        client.send("textDocument/didSave", {"textDocument": {"uri": uri}})
        # A pending clear from didClose may precede the new source error.
        encoding_errors = []
        for _ in range(4):
            encoding_errors = client.diagnostics(module.as_uri(), 3)
            if encoding_errors:
                break
        assert encoding_errors and "UTF-8" in encoding_errors[0]["message"], encoding_errors
        module.write_text(module_source)
        client.send("textDocument/didClose", {"textDocument": {"uri": uri}})
        assert client.diagnostics(uri, 4) == []
        client.close()
    except BaseException:
        if "client" in locals():
            (Path(temporary) / "protocol.json").write_text(json.dumps(client.transcript, ensure_ascii=False, indent=2))
            client.abort()
        print("Retained LSP evidence:", temporary, flush=True)
        raise
    else:
        shutil.rmtree(temporary)
    print("LSP framed stdio, lifecycle, UTF-16 sync, live diagnostics and editor features passed")


def protocol_controls(server, compiler):
    def frame(value):
        body = value if isinstance(value, bytes) else json.dumps(value).encode()
        return f"Content-Length: {len(body)}\r\n\r\n".encode() + body

    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        b"{", b"\xff", [], {"jsonrpc": "2.0", "id": 1.5, "method": "shutdown"},
        {"jsonrpc": "2.0", "id": 2, "method": "shutdown"},
        {"jsonrpc": "2.0", "method": "exit"},
    ]
    result = subprocess.run([server, "--compiler", compiler], input=b"".join(map(frame, messages)), capture_output=True, timeout=20)
    assert result.returncode == 0 and not result.stderr, result
    responses = []
    rest = result.stdout
    while rest:
        header, body = rest.split(b"\r\n\r\n", 1)
        size = int(header.split(b":", 1)[1])
        responses.append(json.loads(body[:size]))
        rest = body[size:]
    assert [message["error"]["code"] for message in responses if "error" in message] == [-32700, -32700, -32600, -32600], responses
    for malformed in (
        b"Content-Length: -1\r\n\r\n", b"Content-Length: 16777217\r\n\r\n",
        b"Content-Length: 4\r\nContent-Length: 4\r\n\r\n{}", b"Content-Length: 8\r\n\r\n{}",
        b"Content-Length: 2\r\n\x00\r\n\r\n{}", b"Content-Length: 2\r\nX-Other: a\nb\r\n\r\n{}",
    ):
        result = subprocess.run([server], input=malformed, capture_output=True, timeout=10)
        assert result.returncode == 1 and not result.stdout and b"invalid or truncated" in result.stderr, result
    result = subprocess.run([server], input=frame({"jsonrpc": "2.0", "method": "exit"}), capture_output=True, timeout=10)
    assert result.returncode == 1 and not result.stdout, result
    with tempfile.TemporaryDirectory(prefix="minyar-lsp-index-growth-") as temporary:
        root = Path(temporary)
        source = "".join(f"record R{index} {{ field: Integer }}\n" for index in range(40000)) + "}\n"
        uri = (root / "growth.min").as_uri()
        oversized = root / "oversized.min"
        with oversized.open("wb") as file:
            file.truncate(16 * 1024 * 1024 + 1)
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"rootUri": root.as_uri()}},
            {"jsonrpc": "2.0", "id": 2, "method": "textDocument/documentSymbol", "params": {"textDocument": {"uri": Path("/dev/zero").as_uri()}}},
            {"jsonrpc": "2.0", "id": 3, "method": "textDocument/documentSymbol", "params": {"textDocument": {"uri": oversized.as_uri()}}},
            {"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {"textDocument": {"uri": uri, "version": 1, "text": source}}},
            {"jsonrpc": "2.0", "id": 4, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        ]
        result = subprocess.run([server, "--compiler", compiler], input=b"".join(map(frame, messages)), capture_output=True, timeout=10)
        assert result.returncode == 0 and not result.stderr and b'"id":2,"error"' in result.stdout and b'"id":3,"error"' in result.stdout and b"opening bracket" in result.stdout, result
    print("LSP malformed JSON/UTF-8, frame limits, truncation and lifecycle controls passed")


def json_diagnostic_controls(server):
    with tempfile.TemporaryDirectory(prefix="minyar-json-lsp-") as temporary:
        root = Path(temporary).resolve()
        compiler = root / "compiler with spaces"
        compiler.write_text('''#!/usr/bin/env python3
import json, pathlib, sys
assert "--error-format" in sys.argv and "json" in sys.argv
source = pathlib.Path(sys.argv[1]).read_text()
found = False
for name in ("missing", "otherMissing"):
    if name not in source:
        continue
    found = True
    position = source.index(name)
    line = source.count("\\n", 0, position) + 1
    column = position - source.rfind("\\n", 0, position)
    print(json.dumps({"version": 1, "severity": "error", "message": "unknown " + name, "file": sys.argv[1], "line": line, "column": column, "endLine": line, "endColumn": column + len(name), "sourceLine": source.splitlines()[line - 1], "label": "not in scope", "help": ["choose a visible name"]}), file=sys.stderr)
pathlib.Path(sys.argv[2]).write_text("")
sys.exit(1 if found else 0)
''')
        compiler.chmod(0o755)
        path = root / "moon.min"
        source = 'let moon = "🌙"; print(missing)\nprint(otherMissing)\n'
        path.write_text(source)
        client = Client([server, "--compiler", str(compiler)])
        client.request("initialize", {"rootUri": root.as_uri(), "capabilities": {}})
        client.send("textDocument/didOpen", {"textDocument": {"uri": path.as_uri(), "version": 7, "text": source}})
        errors = client.diagnostics(path.as_uri(), 7)
        assert len(errors) == 2, errors
        assert errors[0]["range"] == {"start": point(source, "missing"), "end": point(source, "missing", offset=len("missing"))}, errors
        assert errors[1]["range"]["start"] == point(source, "otherMissing"), errors
        assert "not in scope" in errors[0]["message"] and "help: choose a visible name" in errors[0]["message"], errors
        client.send("textDocument/didChange", {"textDocument": {"uri": path.as_uri(), "version": 8}, "contentChanges": [{"text": "print(42)\n"}]})
        assert client.diagnostics(path.as_uri(), 8) == []
        client.close()
        client = Client([server, "--compiler", str(root / "absent compiler")])
        client.request("initialize", {"rootUri": root.as_uri(), "capabilities": {}})
        client.send("textDocument/didOpen", {"textDocument": {"uri": path.as_uri(), "version": 1, "text": "print(42)\n"}})
        errors = client.diagnostics(path.as_uri(), 1)
        assert errors and "could not check" in errors[0]["message"], errors
        client.close()
        compiler.write_text('#!/usr/bin/env python3\nimport sys\nsys.stderr.buffer.write(bytes([255]))\nsys.exit(1)\n')
        client = Client([server, "--compiler", str(compiler)])
        client.request("initialize", {"rootUri": root.as_uri(), "capabilities": {}})
        client.send("textDocument/didOpen", {"textDocument": {"uri": path.as_uri(), "version": 1, "text": "print(42)\n"}})
        errors = client.diagnostics(path.as_uri(), 1)
        assert errors and "not valid UTF-8" in errors[0]["message"], errors
        client.close()
        for stream, descriptor in (("output", 1), ("error", 2)):
            compiler.write_text(f'''#!/usr/bin/env python3
import os
chunk = b"x" * 1048576
for _ in range(17):
    os.write({descriptor}, chunk)
''')
            client = Client([server, "--compiler", str(compiler)])
            client.request("initialize", {"rootUri": root.as_uri(), "capabilities": {}})
            client.send("textDocument/didOpen", {"textDocument": {"uri": path.as_uri(), "version": 1, "text": "print(42)\n"}})
            errors = client.diagnostics(path.as_uri(), 1)
            assert errors and errors[0]["message"] == f"The compiler wrote more than 16 MiB to standard {stream} while checking this document.", errors
            client.close()
        compiler.write_text('''#!/usr/bin/env python3
import pathlib, sys
if "--error-format" in sys.argv:
    print("error: usage: compiler SOURCE OUTPUT", file=sys.stderr)
    sys.exit(1)
source = pathlib.Path(sys.argv[1]).read_text()
if "missing" in source:
    position = source.index("missing")
    line = source.count("\\n", 0, position) + 1
    column = position - source.rfind("\\n", 0, position)
    print("error: unknown value missing", file=sys.stderr)
    print(f"  --> {sys.argv[1]}:{line}:{column}", file=sys.stderr)
    sys.exit(1)
pathlib.Path(sys.argv[2]).write_text("")
''')
        client = Client([server, "--compiler", str(compiler)])
        client.request("initialize", {"rootUri": root.as_uri(), "capabilities": {}})
        client.send("textDocument/didOpen", {"textDocument": {"uri": path.as_uri(), "version": 1, "text": source}})
        errors = client.diagnostics(path.as_uri(), 1)
        assert errors and errors[0]["range"]["start"] == point(source, "missing"), errors
        client.send("textDocument/didChange", {"textDocument": {"uri": path.as_uri(), "version": 2}, "contentChanges": [{"text": "print(42)\n"}]})
        assert client.diagnostics(path.as_uri(), 2) == []
        client.close()
    print("LSP NDJSON/legacy handoff, multiple errors, scalar/UTF-16 spans and failed compiler controls passed")


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda _signal, _frame: sys.exit(143))
    parser = argparse.ArgumentParser()
    parser.add_argument("server")
    parser.add_argument("compiler")
    options = parser.parse_args()
    run(str(Path(options.server).resolve()), str(Path(options.compiler).resolve()))
    protocol_controls(str(Path(options.server).resolve()), str(Path(options.compiler).resolve()))
    json_diagnostic_controls(str(Path(options.server).resolve()))
