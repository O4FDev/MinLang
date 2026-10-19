"""Public command probes shared by native archive qualification."""
import json
import subprocess


def lsp_roundtrip(command, project, environment):
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"processId": None, "rootUri": project.as_uri(), "capabilities": {}}},
        {"jsonrpc": "2.0", "method": "initialized", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "shutdown", "params": None},
        {"jsonrpc": "2.0", "method": "exit", "params": None},
    ]
    frames = bytearray()
    for message in messages:
        body = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode()
        frames.extend(f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
    result = subprocess.run([str(command), "lsp"], cwd=project, env=environment, input=frames,
                            capture_output=True, timeout=60)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    remaining = result.stdout
    replies = {}
    while remaining:
        header, separator, body = remaining.partition(b"\r\n\r\n")
        assert separator, "language server stdout contains unframed output"
        fields = dict(line.split(b":", 1) for line in header.split(b"\r\n"))
        length = int(next(value for key, value in fields.items() if key.lower() == b"content-length"))
        assert 0 < length <= 16 * 1024 * 1024 and len(body) >= length
        message = json.loads(body[:length])
        assert message["jsonrpc"] == "2.0"
        if "id" in message:
            replies[message["id"]] = message
        remaining = body[length:]
    assert isinstance(replies[1]["result"]["capabilities"], dict)
    assert replies[2]["result"] is None


def project_diagnostics(command, project, environment):
    source = project / "src/main.min"
    original = source.read_bytes()
    fields = {"version", "severity", "message", "file", "line", "column", "endLine", "endColumn", "sourceLine", "label", "help"}

    def reject(route, expected_source, expected_text, profile):
        options = ["--root", str(project / "target/diagnostic-install")] if route == "install" else []
        result = subprocess.run([str(command), route, "--error-format", "json", *profile, *options],
                                cwd=project, env=environment, text=True, capture_output=True, timeout=120)
        assert result.returncode != 0, (route, profile, result.stdout, result.stderr)
        diagnostics = [json.loads(line) for line in result.stderr.splitlines() if line]
        assert diagnostics, (route, profile, result.stderr)
        for diagnostic in diagnostics:
            assert set(diagnostic) == fields and diagnostic["version"] == 1
            assert diagnostic["severity"] == "error" and diagnostic["message"]
            assert diagnostic["file"].endswith(expected_source)
            assert diagnostic["line"] >= 1 and diagnostic["column"] >= 1
            assert diagnostic["endLine"] >= diagnostic["line"] and isinstance(diagnostic["help"], list)
            assert expected_text in diagnostic["sourceLine"]

    embedded = project / "src/diagnostic-invariant.min"
    legacy = project / "tests/diagnostic-failure.min"
    assert not embedded.exists() and not legacy.exists()
    try:
        source.write_text('let count: Integer = "not an integer"\n')
        for profile in ([], ["--release"]):
            for route in ("build", "check", "run", "test", "install"):
                reject(route, "src/main.min", "not an integer", profile)
        source.write_bytes(original)
        for profile in ([], ["--release"]):
            embedded.write_text('test "unfinished\n')
            reject("test", "src/diagnostic-invariant.min", "unfinished", profile)
            embedded.write_text('test "invalid embedded" {\n    let count: Integer = "not an integer"\n    expect(count == 1)\n}\n')
            reject("test", "src/diagnostic-invariant.min", "not an integer", profile)
            embedded.unlink()
            legacy.write_text('let count: Integer = "not an integer"\n')
            reject("test", "tests/diagnostic-failure.min", "not an integer", profile)
            legacy.unlink()
    finally:
        source.write_bytes(original)
        embedded.unlink(missing_ok=True)
        legacy.unlink(missing_ok=True)
