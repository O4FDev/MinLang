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
    try:
        source.write_text('let count: Integer = "not an integer"\n')
        for route in ("build", "check", "run", "test", "install"):
            options = ["--root", str(project / "target/diagnostic-install")] if route == "install" else []
            result = subprocess.run([str(command), route, "--error-format", "json", *options],
                                    cwd=project, env=environment, text=True, capture_output=True, timeout=120)
            assert result.returncode != 0, (route, result.stdout, result.stderr)
            diagnostics = [json.loads(line) for line in result.stderr.splitlines() if line]
            assert diagnostics, (route, result.stderr)
            for diagnostic in diagnostics:
                assert set(diagnostic) == fields and diagnostic["version"] == 1
                assert diagnostic["severity"] == "error" and diagnostic["message"]
                assert diagnostic["file"].endswith("src/main.min")
                assert diagnostic["line"] == 1 and diagnostic["column"] >= 1
                assert diagnostic["endLine"] >= diagnostic["line"] and isinstance(diagnostic["help"], list)
                assert "not an integer" in diagnostic["sourceLine"]
    finally:
        source.write_bytes(original)
