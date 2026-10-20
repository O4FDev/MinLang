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
    for malformed in (b"Content-Length: -1\r\n\r\n", b"Content-Length: 16777217\r\n\r\n", b"Content-Length: 4\r\nContent-Length: 4\r\n\r\n{}", b"Content-Length: 8\r\n\r\n{}"):
        result = subprocess.run([server], input=malformed, capture_output=True, timeout=10)
        assert result.returncode == 1 and not result.stdout and b"invalid or truncated" in result.stderr, result
    result = subprocess.run([server], input=frame({"jsonrpc": "2.0", "method": "exit"}), capture_output=True, timeout=10)
    assert result.returncode == 1 and not result.stdout, result
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


def byte_offset(source, position):
    lines = source.splitlines(keepends=True)
    prefix = "".join(lines[:position["line"]])
    line = lines[position["line"]] if position["line"] < len(lines) else ""
    prefix += line.encode("utf-16-le")[:position["character"] * 2].decode("utf-16-le")
    return len(prefix.encode())


def apply_edits(source, edits):
    raw = source.encode()
    ranges = [(byte_offset(source, edit["range"]["start"]),
               byte_offset(source, edit["range"]["end"]), edit["newText"].encode()) for edit in edits]
    ranges.sort(reverse=True)
    previous = len(raw) + 1
    for first, after, replacement in ranges:
        assert first <= after <= previous, ranges
        raw = raw[:first] + replacement + raw[after:]
        previous = first
    return raw.decode()


def refactoring(server, compiler):
    temporary = tempfile.mkdtemp(prefix="minyar-refactoring-星-")
    root = Path(temporary).resolve()
    try:
        module = root / "sky.min"
        module_source = '/// Twice the light.\npublic function twice(value: Integer): Integer { return value * 2 }\n'
        module.write_text(module_source)
        sibling = root / "unopened.min"
        sibling_source = 'use "./sky.min" as sky\nprint(sky.twice(4))\n'
        sibling.write_text(sibling_source)
        path = root / "harbor #moon.min"
        source = '''use "./sky.min" as sky
record Lantern { light: Integer }
function Lantern.raise(amount: Integer) { self.light += amount }
function local(value: Integer): Integer {
    let copy = value
    if true { let value = 9; print(value) }
    return copy + value
}
function shadow(localLamp: Lantern): Integer { return localLamp.light }
let lamp = Lantern { light: 40 }
lamp.raise(2)
print(lamp.light)
print(sky.twice(21))
let caption = "🌙"; let count = 2
let typed: Integer = 3
let compared = 1 == 1
let words = "light"
print(words)
print(count + typed)
// light and value are words here, not references.
'''
        path.write_text(source)
        uri = path.as_uri()
        client = Client([server, "--compiler", compiler])
        initialized = client.request("initialize", {"rootUri": root.as_uri(), "capabilities": {"workspace": {"workspaceEdit": {"documentChanges": True}}, "textDocument": {"rename": {"prepareSupport": True}, "codeAction": {"codeActionLiteralSupport": {"codeActionKind": {"valueSet": ["quickfix"]}}}}}})
        capabilities = initialized["result"]["capabilities"]
        assert capabilities["referencesProvider"] is True
        assert capabilities["renameProvider"]["prepareProvider"] is True
        assert capabilities["inlayHintProvider"] is True
        assert "quickfix" in capabilities["codeActionProvider"]["codeActionKinds"]
        client.send("textDocument/didOpen", {"textDocument": {"uri": uri, "version": 7, "text": source}})
        initial = client.diagnostics(uri, 7)
        assert initial == [], initial

        def query(method, needle, *, text=source, document=uri, extra=None, offset=0):
            params = {"textDocument": {"uri": document}, "position": point(text, needle, offset=offset)}
            params.update(extra or {})
            return client.request("textDocument/" + method, params)

        def references(needle, include=True, **kwargs):
            return query("references", needle, extra={"context": {"includeDeclaration": include}}, **kwargs)["result"]

        # Identity and scope, rather than text matching, exclude the inner value.
        refs = references("local(value", offset=6)
        expected = [point(source, "local(value", offset=6), point(source, "copy = value", offset=7), point(source, "copy + value", offset=7)]
        assert [item["range"]["start"] for item in refs] == expected, refs
        assert len(references("local(value", include=False, offset=6)) == 2
        prepared = query("prepareRename", "local(value", offset=11)["result"]
        assert prepared["placeholder"] == "value" and prepared["range"]["start"] == expected[0], prepared
        renamed = query("rename", "local(value", offset=6, extra={"newName": "input"})["result"]
        changes = renamed["documentChanges"]
        assert len(changes) == 1 and changes[0]["textDocument"] == {"uri": uri, "version": 7}, changes
        updated = apply_edits(source, changes[0]["edits"])
        assert "local(input: Integer)" in updated and "copy = input" in updated and "copy + input" in updated
        assert "let value = 9; print(value)" in updated and "// light and value" in updated
        for name in ("copy", "return", "print", "two words", "2light", ""):
            rejected = query("rename", "local(value", offset=6, extra={"newName": name})
            assert rejected["error"]["code"] == -32602, (name, rejected)
        assert query("prepareRename", "print(words)")["result"] is None
        assert query("references", "print(words)", extra={"context": {"includeDeclaration": True}})["result"] == []

        definition = query("definition", "localLamp.light", offset=11)["result"]
        assert definition["uri"] == uri and definition["range"]["start"] == point(source, "light: Integer"), definition
        members = query("completion", "localLamp.light", offset=10)["result"]
        assert "light" in {item["label"] for item in members} and "twice" not in {item["label"] for item in members}, members
        alias = query("rename", 'as sky', offset=3, extra={"newName": "heavens"})["result"]
        alias_text = apply_edits(source, alias["documentChanges"][0]["edits"])
        assert 'as heavens' in alias_text and "heavens.twice(21)" in alias_text and "return localLamp.light" in alias_text, alias_text
        fields = references("light: Integer")
        assert len(fields) == 5, fields
        field_edit = query("rename", "light: Integer", extra={"newName": "brightness"})["result"]
        field_text = apply_edits(source, field_edit["documentChanges"][0]["edits"])
        assert 'Lantern { brightness: 40 }' in field_text and 'self.brightness' in field_text and '"light"' in field_text, field_text
        method = query("rename", "raise(amount", extra={"newName": "brighten"})["result"]
        assert len(method["documentChanges"][0]["edits"]) == 2, method

        # Find callers in unopened files and use current unsaved dependencies.
        refs = references("sky.twice", offset=4)
        assert {item["uri"] for item in refs} == {uri, module.as_uri(), sibling.as_uri()}, refs
        assert len(refs) == 3, refs
        imported = query("rename", "sky.twice", offset=4, extra={"newName": "doubled"})["result"]
        imported_changes = {item["textDocument"]["uri"]: item for item in imported["documentChanges"]}
        assert imported_changes[module.as_uri()]["textDocument"]["version"] is None
        assert imported_changes[sibling.as_uri()]["textDocument"]["version"] is None
        assert len(imported_changes) == 3, imported
        for owner, original in ((path, source), (module, module_source), (sibling, sibling_source)):
            edits = imported_changes[owner.as_uri()]["edits"]
            owner.write_text(apply_edits(original, edits))
        checked = subprocess.run([compiler, str(path), str(root / "renamed.ll")], capture_output=True, timeout=30)
        assert checked.returncode == 0, checked.stderr.decode()
        path.write_text(source)
        module.write_text(module_source)
        sibling.write_text(sibling_source)
        unsaved = sibling_source + "print(sky.twice(5))\n"
        client.send("textDocument/didOpen", {"textDocument": {"uri": sibling.as_uri(), "version": 2, "text": unsaved}})
        assert client.diagnostics(sibling.as_uri(), 2) == []
        assert len(references("sky.twice", offset=4)) == 4
        client.send("textDocument/didClose", {"textDocument": {"uri": sibling.as_uri()}})
        assert len(references("sky.twice", offset=4)) == 3

        # Closed callers outside root must be refreshed too: cached offsets
        # are unsafe after another program edits those files on disk.
        external_root = Path(tempfile.mkdtemp(prefix="minyar-external-caller-"))
        try:
            external = external_root / "caller.min"
            external_source = f'use "{module}" as sky\nprint(sky.twice(6))\n'
            external.write_text(external_source)
            client.send("textDocument/didOpen", {"textDocument": {"uri": external.as_uri(), "version": 1, "text": external_source}})
            assert client.diagnostics(external.as_uri(), 1) == []
            client.send("textDocument/didClose", {"textDocument": {"uri": external.as_uri()}})
            shifted = "// A new line moves the call.\n" + external_source
            external.write_text(shifted)
            external_edit = query("rename", "sky.twice", offset=4, extra={"newName": "doubled"})["result"]
            external_change = next(item for item in external_edit["documentChanges"] if item["textDocument"]["uri"] == external.as_uri())
            assert external_change["edits"][0]["range"]["start"] == point(shifted, "twice"), external_change
            assert "sky.doubled(6)" in apply_edits(shifted, external_change["edits"])
        finally:
            shutil.rmtree(external_root)

        # Navigation remains lexical in an incomplete/invalid buffer even when
        # a parameter shadows an import alias. The compiler currently rejects
        # this source; the tooling must still avoid selecting the wrong symbol.
        shadow_path = root / "shadow.min"
        shadow_source = 'use "./sky.min" as sky\nrecord Lantern { light: Integer }\nfunction shadow(sky: Lantern): Integer { return sky.light }\n'
        shadow_path.write_text(shadow_source)
        shadow_uri = shadow_path.as_uri()
        client.send("textDocument/didOpen", {"textDocument": {"uri": shadow_uri, "version": 1, "text": shadow_source}})
        client.diagnostics(shadow_uri, 1)
        definition = query("definition", "sky.light", text=shadow_source, document=shadow_uri, offset=5)["result"]
        assert definition["uri"] == shadow_uri and definition["range"]["start"] == point(shadow_source, "light: Integer"), definition
        shadow_alias = query("rename", "as sky", text=shadow_source, document=shadow_uri, offset=3, extra={"newName": "heavens"})
        assert shadow_alias["error"]["code"] == -32602, shadow_alias
        client.send("textDocument/didClose", {"textDocument": {"uri": shadow_uri}})

        # Hints are certain scalar literals only, with UTF-16 insertion points.
        whole = {"start": {"line": 0, "character": 0}, "end": {"line": source.count("\n"), "character": 0}}
        hints = client.request("textDocument/inlayHint", {"textDocument": {"uri": uri}, "range": whole})["result"]
        positions = {(hint["position"]["line"], hint["position"]["character"]): hint for hint in hints}
        count_position = point(source, "count =", offset=5)
        assert positions[(count_position["line"], count_position["character"])]["label"] == ": Integer", hints
        assert all(hint["kind"] == 1 for hint in hints)
        for needle in ("typed:", "compared =", "lamp =", "copy ="):
            pos = point(source, needle, offset=len(needle.split(":")[0].split(" ")[0]))
            assert (pos["line"], pos["character"]) not in positions, (needle, hints)
        line_range = {"start": point(source, "count ="), "end": point(source, "count =", offset=9)}
        selected = client.request("textDocument/inlayHint", {"textDocument": {"uri": uri}, "range": line_range})["result"]
        assert len(selected) == 1 and selected[0]["position"] == count_position, selected
        assert path.read_text() == source and sibling.read_text() == sibling_source

        # A compiler's exact suggestion becomes a versioned quick fix; applying
        # it repairs the document. Client-injected diagnostic data is ignored.
        broken = 'let moon = "🌙"; let light = 42; print(ligth)\n'
        client.send("textDocument/didChange", {"textDocument": {"uri": uri, "version": 8}, "contentChanges": [{"text": broken}]})
        errors = client.diagnostics(uri, 8)
        assert errors and "did you mean `light`?" in errors[0]["message"], errors
        action_params = {"textDocument": {"uri": uri}, "range": errors[0]["range"], "context": {"diagnostics": errors, "only": ["quickfix"]}}
        actions = client.request("textDocument/codeAction", action_params)["result"]
        assert len(actions) == 1 and actions[0]["kind"] == "quickfix" and actions[0]["isPreferred"], actions
        forged = json.loads(json.dumps(errors))
        forged[0]["data"] = {"original": "ligth", "replacement": "inventedByClient"}
        action_params["context"]["diagnostics"] = forged
        assert client.request("textDocument/codeAction", action_params)["result"] == actions
        fix = actions[0]["edit"]["documentChanges"][0]
        assert fix["textDocument"] == {"uri": uri, "version": 8}, fix
        fixed = apply_edits(broken, fix["edits"])
        assert fixed == broken.replace("ligth", "light"), fixed
        action_params["context"]["only"] = ["refactor"]
        assert client.request("textDocument/codeAction", action_params)["result"] == []
        client.send("textDocument/didChange", {"textDocument": {"uri": uri, "version": 9}, "contentChanges": [{"text": fixed}]})
        assert client.diagnostics(uri, 9) == []
        action_params["context"]["only"] = ["quickfix"]
        assert client.request("textDocument/codeAction", action_params)["result"] == []
        for method in ("references", "rename", "prepareRename"):
            invalid = client.request("textDocument/" + method, {"textDocument": {"uri": uri}, "position": {"line": 999, "character": 0}, "newName": "valid"})
            assert invalid["error"]["code"] == -32602, invalid
        for version, (unsafe, needle, new_name) in enumerate((
            ('let name = "moon"\nprint("\\(name)")\n', "name =", "title"),
            ('let value = 1\nfor value in 0..2 { print(value) }\nprint(value)\n', "value =", "amount"),
            ('function identity<Item>(value: Item): Item { return value }\n', "value:", "Item"),
            ('function step(value: Integer): Integer { let value = value + 1; return value }\n', "value:", "input"),
            ('record Lamp { light: Integer }\nfunction make(): Lamp { return Lamp { light: 1 } }\nprint(make().light)\n', "light:", "power"),
            ('record Lamp { light: Integer }\nfunction read(Lamp: Integer): Integer { let lamp: Lamp = Lamp { light: 40 }; return lamp.light + Lamp }\nprint(read(2))\n', "read(Lamp", "amount"),
        ), start=10):
            client.send("textDocument/didChange", {"textDocument": {"uri": uri, "version": version}, "contentChanges": [{"text": unsafe}]})
            client.diagnostics(uri, version)
            offset = 5 if needle == "read(Lamp" else 0
            rejected = query("rename", needle, text=unsafe, offset=offset, extra={"newName": new_name})
            assert rejected["error"]["code"] == -32602, (unsafe, rejected)
            if needle == "read(Lamp":
                assert query("prepareRename", "record Lamp", text=unsafe, offset=7)["result"] is None
                rejected_type = query("rename", "record Lamp", text=unsafe, offset=7, extra={"newName": "Lantern"})
                assert rejected_type["error"]["code"] == -32602, rejected_type

        # These programs are valid. Type/value namespaces, generic parameters
        # and shadowed callback factories must not become incorrect edits.
        for version, (ambiguous, needle, name) in enumerate((
            ('record Lamp { light: Integer }\nlet Lamp = 2\nlet lamp: Lamp = Lamp { light: 40 }\nprint(lamp.light + Lamp)\n', "Lamp =", "amount"),
            ('function count<Item>(value: Item): Integer { let Item = 2; let again: Item = value; return Item }\nprint(count(40))\n', "Item =", "amount"),
            ('record A { light: Integer }\nrecord B { light: Integer }\nfunction source(): A { return A { light: 1 } }\nfunction read(source: () -> B): Integer { let value = source(); return value.light }\nprint(0)\n', "light:", "power"),
            ('record Lamp { light: Integer }\nfunction Lamp(): Integer { return 2 }\nlet lamp = Lamp { light: 1 }\nprint(lamp.light + Lamp())\n', "Lamp()", "make"),
            ('record A { light: Integer }\nrecord B { light: Integer }\nfunction A.other(): B { return B { light: 2 } }\nlet value = A { light: 1 }.other()\nprint(value.light)\n', "light:", "power"),
        ), start=20):
            client.send("textDocument/didChange", {"textDocument": {"uri": uri, "version": version}, "contentChanges": [{"text": ambiguous}]})
            diagnostics = client.diagnostics(uri, version)
            assert diagnostics == [], (ambiguous, diagnostics)
            rejected = query("rename", needle, text=ambiguous, extra={"newName": name})
            assert rejected["error"]["code"] == -32602, (ambiguous, rejected)

        sequential = "let value = 1\nprint(value)\nlet value = 2\nprint(value)\n"
        client.send("textDocument/didChange", {"textDocument": {"uri": uri, "version": 30}, "contentChanges": [{"text": sequential}]})
        assert client.diagnostics(uri, 30) == []
        for occurrence, name in enumerate(("first", "second")):
            position = point(sequential, "let value", occurrence=occurrence, offset=4)
            params = {"textDocument": {"uri": uri}, "position": position, "context": {"includeDeclaration": True}, "newName": name}
            refs = client.request("textDocument/references", params)["result"]
            assert [ref["range"]["start"]["line"] for ref in refs] == [occurrence * 2, occurrence * 2 + 1], refs
            edits = client.request("textDocument/rename", params)["result"]["documentChanges"][0]["edits"]
            assert len(edits) == 2, edits
            renamed_source = apply_edits(sequential, edits)
            path.write_text(renamed_source)
            checked = subprocess.run([compiler, str(path), str(root / "sequential.ll")], capture_output=True, timeout=30)
            assert checked.returncode == 0, checked.stderr.decode()
            path.write_text(source)
        client.close()

        # Clients without documentChanges support receive the baseline changes
        # form. No source file is rewritten by the server.
        client = Client([server, "--compiler", compiler])
        minimal = client.request("initialize", {"rootUri": root.as_uri(), "capabilities": {}})["result"]["capabilities"]
        assert minimal["renameProvider"] is True and minimal["codeActionProvider"] is False, minimal
        result = query("rename", "local(value", offset=6, extra={"newName": "input"})["result"]
        assert uri in result["changes"] and "documentChanges" not in result, result
        client.close()
        print("LSP references, safe rename, alias shadowing, inlay hints and compiler quick fixes passed")
    except BaseException:
        if "client" in locals():
            (root / "protocol.json").write_text(json.dumps(client.transcript, ensure_ascii=False, indent=2))
            client.abort()
        print("Retained refactoring evidence:", temporary, flush=True)
        raise
    else:
        shutil.rmtree(temporary)


def gallery(compiler):
    with tempfile.TemporaryDirectory(prefix="minyar-editor-gallery-") as temporary:
        root = Path(temporary)
        llvm = root / "lighthouse.ll"
        checked = subprocess.run([compiler, "examples/gallery/lighthouse-editor.min", str(llvm)], capture_output=True, timeout=30)
        assert checked.returncode == 0, checked.stderr.decode()
        for optimization in ("-O0", "-O2"):
            binary = root / "lighthouse"
            built = subprocess.run([os.environ.get("MINYAR_TEST_CLANG", "clang"), optimization, "-Wno-override-module", str(llvm), "build/minyar-runtime.o", "-pthread", "-lm", "-o", str(binary)], capture_output=True, timeout=30)
            assert built.returncode == 0, built.stderr.decode()
            ran = subprocess.run([str(binary)], capture_output=True, timeout=10)
            assert ran.returncode == 0 and ran.stdout == b"Harbor: 42\n" and not ran.stderr, ran
    print("LSP lighthouse gallery passed exact output at O0/O2")


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda _signal, _frame: sys.exit(143))
    parser = argparse.ArgumentParser()
    parser.add_argument("server")
    parser.add_argument("compiler")
    options = parser.parse_args()
    run(str(Path(options.server).resolve()), str(Path(options.compiler).resolve()))
    refactoring(str(Path(options.server).resolve()), str(Path(options.compiler).resolve()))
    protocol_controls(str(Path(options.server).resolve()), str(Path(options.compiler).resolve()))
    json_diagnostic_controls(str(Path(options.server).resolve()))
    gallery(str(Path(options.compiler).resolve()))
