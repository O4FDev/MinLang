#!/usr/bin/env python3
"""Build a real UIKit interaction probe; run only on an already booted Simulator."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mobile", ROOT / "tools/mobile.py")
mobile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mobile)
IDENTIFIER = "org.minyar.mobile-smoke"
SUCCESS = "mobile UIKit smoke passed: launch, action, Unicode edit, toggle, reuse, selection"


def prepare_evidence(evidence):
    evidence.mkdir(parents=True, exist_ok=True)
    for name in ("command.json", "stdout", "stderr", "launch.result.json",
                 "install.command.json", "install.stdout", "install.stderr", "install.result.json"):
        (evidence / name).unlink(missing_ok=True)


def run_evidenced(command, evidence, phase, timeout):
    prefix = "" if phase == "launch" else phase + "."
    (evidence / (prefix + "command.json")).write_text(json.dumps(command, indent=2) + "\n")
    result = {"phase": phase, "command": command, "timeout_seconds": timeout,
              "returncode": None, "timed_out": False, "error": None}
    started = time.monotonic()
    process = None
    try:
        with (evidence / (prefix + "stdout")).open("wb") as output, \
                (evidence / (prefix + "stderr")).open("wb") as error:
            process = subprocess.Popen(command, stdout=output, stderr=error)
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                result["timed_out"] = True
                process.kill()
                process.wait()
                raise
    except (OSError, subprocess.SubprocessError) as error:
        result["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        if process is not None:
            result["returncode"] = process.returncode
        result["seconds"] = time.monotonic() - started
        (evidence / (phase + ".result.json")).write_text(json.dumps(result, indent=2) + "\n")
    return result["returncode"]


def simulator(requested):
    result = subprocess.run(["xcrun", "simctl", "list", "devices", "booted", "--json"], check=True,
                            capture_output=True, text=True, timeout=30)
    devices = [item for runtime, items in json.loads(result.stdout)["devices"].items()
               if ".iOS-" in runtime for item in items if item.get("state") == "Booted"]
    if requested != "booted":
        devices = [item for item in devices if item["udid"] == requested]
    if len(devices) != 1:
        raise RuntimeError("select one already booted iOS Simulator with --device UDID; this check never boots a device")
    return devices[0]["udid"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--device", default=os.environ.get("MINYAR_SIMULATOR_UDID", "booted"))
    requested = parser.parse_args()
    args = mobile.parser().parse_args([str(ROOT / "examples/mobile-hello/main.min"), "--target", "ios-simulator",
                                      "--identifier", IDENTIFIER, "--no-bootstrap", "-o",
                                      str(ROOT / "build/mobile/ios-smoke/MinyarSmoke.app")])
    app = mobile.build(args, ios_provider=ROOT / "tests/mobile-ios.m")
    if not requested.run:
        print(f"built UIKit smoke app {app}; no Simulator was started")
        return
    device = simulator(requested.device)
    evidence = ROOT / "build/mobile-tests/ios-smoke"
    prepare_evidence(evidence)
    install = ["xcrun", "simctl", "install", device, str(app)]
    status = run_evidenced(install, evidence, "install", 45)
    if status:
        raise RuntimeError(f"UIKit installation failed with status {status}; evidence in {evidence}")
    command = ["xcrun", "simctl", "launch", "--console", "--terminate-running-process", device, IDENTIFIER]
    try:
        status = run_evidenced(command, evidence, "launch", 60)
        output = (evidence / "stdout").read_text()
        if status or SUCCESS not in output.splitlines():
            raise RuntimeError(f"UIKit interaction check failed with status {status}; evidence in {evidence}")
        print(SUCCESS)
    finally:
        subprocess.run(["xcrun", "simctl", "terminate", device, IDENTIFIER],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError, mobile.MobileError) as error:
        print(f"mobile UIKit check failed: {error}", file=sys.stderr)
        sys.exit(1)
