#!/usr/bin/env python3
"""Compile and exercise three complete gallery applications at O0 and O2."""
import argparse
import http.client
import json
import os
from pathlib import Path
import random
import re
import selectors
import signal
import subprocess
import time

if not __debug__:
    raise SystemExit("showcase checks require assertions; remove Python -O")

ROOT = Path(__file__).resolve().parent.parent
GALLERY = ROOT / "examples/gallery"
WORK = ROOT / "build/showcase"
SCALE = int(os.environ.get("MINYAR_TEST_TIMEOUT_SCALE", "1"))
if not 1 <= SCALE <= 20:
    raise SystemExit("MINYAR_TEST_TIMEOUT_SCALE must be between 1 and 20")
COUNT = 0
HTTP_COUNT = 0


def run(arguments, *, status=0, data=None, cwd=ROOT, timeout=20):
    global COUNT
    COUNT += 1
    command = [str(arg) for arg in arguments]
    started = time.monotonic()
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, cwd=cwd, start_new_session=True)
    timed_out = False
    try:
        output, error_output = process.communicate(data, timeout=timeout * SCALE)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        output, error_output = process.communicate()
    result = subprocess.CompletedProcess(command, process.returncode, output, error_output)
    stem = WORK / f"command-{COUNT:03d}"
    stem.with_suffix(".json").write_text(json.dumps({
        "argv": command, "cwd": str(cwd), "timed_out": timed_out,
        "seconds": time.monotonic() - started, "timeout_seconds": timeout * SCALE,
        "status": result.returncode, "expected_status": status,
    }, ensure_ascii=False) + "\n")
    stem.with_suffix(".stdout").write_bytes(result.stdout)
    stem.with_suffix(".stderr").write_bytes(result.stderr)
    assert not timed_out, ("command timed out; process group killed", command, stem)
    assert result.returncode == status, (arguments, result.returncode,
                                         result.stdout, result.stderr)
    return result


def build(name, mode, source, native=None, test=False):
    binary = WORK / f"{name}-{mode}"
    command = [ROOT / "minyar"]
    if mode == "O0":
        command.append("--debug")
    if test:
        command.append("--test-mode")
    if native:
        command.extend(["--native-source", f"trailinput={native}"])
    command.extend([source, "-o", binary])
    run(command, timeout=240)
    return binary


def write(name, contents):
    path = WORK / name
    if isinstance(contents, str):
        contents = contents.encode("utf-8")
    path.write_bytes(contents)
    return path


def daybook(mode):
    directory = GALLERY / "daybook"
    binary = build("daybook", mode, directory / "src/main.min")
    sample = directory / "week.tsv"
    expected = ("DAYBOOK\nproject\tminutes\nCafé\t20\nGarden\t60\nWriting\t30\n"
                "total\t110\n4 entries · 3 projects\n").encode()
    result = run([binary, sample])
    assert result.stdout == expected and result.stderr == b"", result
    result = run([binary, "--json", sample])
    assert result.stderr == b""
    assert json.loads(result.stdout) == {
        "entries": 4, "totalMinutes": 110,
        "projects": [{"name": "Café", "minutes": 20},
                     {"name": "Garden", "minutes": 60},
                     {"name": "Writing", "minutes": 30}],
    }
    empty = write("empty.tsv", b"")
    assert json.loads(run([binary, "--json", empty]).stdout) == {
        "entries": 0, "totalMinutes": 0, "projects": [],
    }
    other = write("other é.tsv", "  # morning\r\n\r\nGarden\t 2 \r\n星\t0")
    report = json.loads(run([binary, sample, "--json", other]).stdout)
    assert report["entries"] == 6 and report["totalMinutes"] == 112
    assert report["projects"][-1] == {"name": "星", "minutes": 0}
    assert report["projects"][1] == {"name": "Garden", "minutes": 62}
    maximum = write("maximum.tsv", "one\t9223372036854775807")
    assert json.loads(run([binary, "--json", maximum]).stdout)["totalMinutes"] == 2**63 - 1
    names = ['Café', 'Garden', '星', 'a"b', 'a\\b', 'zebra', 'é', 'e\u0301']
    rng = random.Random(1934)
    rows, totals = [], {name: 0 for name in names}
    for _ in range(1000):
        name, minutes = rng.choice(names), rng.randrange(901)
        rows.append(f"{name}\t{minutes}")
        totals[name] += minutes
    generated = write("generated.tsv", "\n".join(rows))
    result = run([binary, "--json", generated])
    assert result.stderr == b""
    assert json.loads(result.stdout) == {
        "entries": len(rows), "totalMinutes": sum(totals.values()),
        "projects": [{"name": name, "minutes": totals[name]} for name in sorted(names)],
    }
    for label, content, diagnostic in [
        ("no-tab", "Garden 20", b"expected project, a tab"),
        ("negative", "Garden\t-1", b"minutes cannot be negative"),
        ("not-number", "Garden\ttwenty", b"reading whole minutes"),
        ("extra-column", "Garden\t20\t3", b"reading whole minutes"),
        ("out-of-range", "Garden\t9223372036854775808", b"integer is outside the signed 64-bit range"),
        ("overflow", f"Garden\t{2**63 - 111}\nOther\t1", b"line 2"),
        ("control", "Gar\x00den\t20", b"control characters"),
        ("long-name", "x" * 81 + "\t20", b"80 characters"),
        ("utf8", b"bad\xff\t20", b"UTF-8"),
        ("too-large", b"#" * (4194304 + 1), b"opening"),
    ]:
        path = write(f"bad-{label}.tsv", content)
        result = run([binary, sample, path], status=1)
        assert result.stdout == b"" and diagnostic in result.stderr, (label, result)
        assert str(path).encode() in result.stderr, result
    for path in [WORK / "missing.tsv", WORK]:
        result = run([binary, path], status=1)
        assert result.stdout == b"" and b"opening" in result.stderr, result
    for arguments in [[], ["--json"], ["--unknown"], [sample] * 65]:
        result = run([binary, *arguments], status=2)
        assert result.stdout == b"" and result.stderr.startswith(b"daybook: "), result
    assert b"usage: daybook" in run([binary, "--help"]).stdout
    dash = write("-dash.tsv", "Garden\t42")
    assert json.loads(run([binary, "--json", "--", dash.name], cwd=WORK).stdout)["totalMinutes"] == 42
    tests = build("daybook-tests", mode, directory / "src/ledger.min", test=True)
    run([tests])


def ready(process):
    """Wait for one actual stdout readiness event, with one absolute deadline."""
    deadline, output = time.monotonic() + 20 * SCALE, bytearray()
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        while b"\n" not in output:
            remaining = deadline - time.monotonic()
            assert remaining > 0, ("HTTP readiness timed out", output)
            assert selector.select(remaining), ("HTTP readiness timed out", output)
            chunk = os.read(process.stdout.fileno(), 4096)
            assert chunk, ("HTTP service exited before readiness", process.poll(), output)
            output.extend(chunk)
            assert len(output) <= 4096, output
    match = re.fullmatch(rb"TIDEBOARD_READY http://127\.0\.0\.1:([0-9]+)\n", output)
    assert match, output
    return int(match[1])


def tideboard(mode):
    binary = build("tideboard", mode, GALLERY / "tideboard/main.min")
    stderr_path = WORK / f"tideboard-{mode}.stderr"
    transcript = WORK / f"tideboard-{mode}.http.jsonl"
    transcript.write_text("")
    with stderr_path.open("wb") as stderr:
        process = subprocess.Popen([str(binary), "0"], stdout=subprocess.PIPE, stderr=stderr, cwd=ROOT)
        try:
            port = ready(process)

            def request(method, path, body=None, content_type=None, status=200):
                global HTTP_COUNT
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10 * SCALE)
                try:
                    headers = {} if content_type is None else {"Content-Type": content_type}
                    connection.request(method, path, body=body, headers=headers)
                    response = connection.getresponse()
                    payload = response.read()
                    HTTP_COUNT += 1
                    with transcript.open("a") as log:
                        log.write(json.dumps({"method": method, "path": path,
                                              "request_body_hex": (body or b"").hex(),
                                              "status": response.status, "expected_status": status,
                                              "headers": response.getheaders(),
                                              "response_body_hex": payload.hex()}) + "\n")
                    assert response.status == status, (method, path, response.status, payload)
                    fields = dict(response.getheaders())
                    mime = response.getheader("Content-Type", "")
                    if "json" in mime:
                        payload = json.loads(payload)
                    return payload, fields
                finally:
                    connection.close()

            page, _ = request("GET", "/")
            assert b"Tideboard" in page and b"/tasks" in page
            health, _ = request("GET", "/health")
            assert health == {"ok": True, "service": "tideboard"}, health
            board, _ = request("GET", "/tasks")
            assert board == {"tasks": [], "capacity": 128}, board
            title = 'Café "garden" \\ 星'
            task, _ = request("POST", "/tasks", ("  " + title + "\n").encode(), "text/plain; charset=utf-8", 201)
            assert task == {"id": 1, "title": title, "completed": False}, task
            completed, _ = request("POST", "/tasks/1/complete", b"")
            assert completed == {"id": 1, "title": title, "completed": True}, completed
            again, _ = request("POST", "/tasks/1/complete", b"")
            assert again == completed
            board, _ = request("GET", "/tasks")
            assert board["tasks"] == [completed]
            for method, path, code in [("GET", "/missing", 404), ("DELETE", "/tasks", 405),
                                       ("POST", "/tasks/99/complete", 404), ("GET", "/tasks/1/complete", 405),
                                       ("POST", "/tasks/01/complete", 404)]:
                request(method, path, status=code)
            for body, mime, code in [(b"", "text/plain", 400), (b" \t\r\n", "text/plain", 400),
                                     (b"bad\x00title", "text/plain", 400), (b"bad\xff", "text/plain", 400),
                                     (b"valid", "application/json", 415), (b"x" * 513, "text/plain", 413)]:
                request("POST", "/tasks", body, mime, code)
            for index in range(2, 129):
                task, _ = request("POST", "/tasks", f"task {index}".encode(), "text/plain", 201)
                assert task["id"] == index
            request("POST", "/tasks", b"one too many", "text/plain", 409)
            board, _ = request("GET", "/tasks")
            assert len(board["tasks"]) == 128 and board["tasks"][0] == completed
            request("GET", "/health")
            assert process.poll() is None, "Tideboard exited during its request loop"
        finally:
            process.terminate()
            try:
                process.wait(timeout=10 * SCALE)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10 * SCALE)
                raise AssertionError("Tideboard did not stop after SIGTERM")
            process.stdout.close()
    assert stderr_path.read_bytes() == b"", stderr_path.read_bytes()
    tests = build("tideboard-tests", mode, GALLERY / "tideboard/model.min", test=True)
    run([tests])
    for arguments in [["-1"], ["65536"], ["oops"], ["0", "1"]]:
        run([binary, *arguments], status=2)


def lantern_trail(mode):
    directory = GALLERY / "lantern-trail"
    binary = build("lantern-trail", mode, directory / "main.min", directory / "input.c")
    for name in ["win", "lose", "controls"]:
        result = run([binary, "--replay", directory / f"{name}.replay"], status=1 if name == "lose" else 0)
        assert result.stdout == (directory / f"{name}.stdout").read_bytes(), (name, result.stdout)
        assert result.stderr == b"", result.stderr
    assert b"Usage: lantern-trail" in run([binary, "--help"]).stdout
    run([binary, "--unknown"], status=2)
    run([binary], data=b"quit\n")
    run([binary], data=b"")
    result = run([binary], data=b"x" * 512 + b"\nquit\n")
    assert b"Unknown command" in result.stdout and b"You leave" in result.stdout
    assert result.stdout.count(b"Energy 10 | Lanterns 0/2 | Steps 0") == 3
    result = run([binary], data=b"\xff\nquit\n")
    assert b"Unknown command" in result.stdout and b"You leave" in result.stdout
    assert result.stdout.count(b"Energy 10 | Lanterns 0/2 | Steps 0") == 3
    replay = (directory / "win.replay").read_bytes()
    crlf = write("win-crlf.replay", replay.rstrip(b"\n").replace(b"\n", b"\r\n"))
    result = run([binary, "--replay", crlf])
    assert result.stdout == (directory / "win.stdout").read_bytes()
    missing = WORK / "missing.replay"
    result = run([binary, "--replay", missing], status=2)
    assert result.stdout == b"" and b"cannot read replay" in result.stderr
    for name, contents in [("incomplete", b"look"), ("oversized", b"x" * 65537)]:
        result = run([binary, "--replay", write(name + ".replay", contents)], status=2)
        assert result.stderr.startswith(b"lantern-trail: ")
    tests = build("lantern-trail-tests", mode, directory / "engine.min", test=True)
    run([tests])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=["daybook", "tideboard", "lantern-trail"])
    parser.add_argument("--mode", choices=["O0", "O2"])
    arguments = parser.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    for mode in [arguments.mode] if arguments.mode else ["O0", "O2"]:
        for name, suite in [("daybook", daybook), ("tideboard", tideboard), ("lantern-trail", lantern_trail)]:
            if arguments.only is None or arguments.only == name:
                suite(mode)
                print(f"showcase: {name} {mode} passed", flush=True)
    print(f"showcase: {COUNT} commands and {HTTP_COUNT} HTTP requests passed in {time.monotonic() - started:.1f}s", flush=True)


if __name__ == "__main__":
    main()
