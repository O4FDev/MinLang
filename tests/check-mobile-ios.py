#!/usr/bin/env python3
"""Build a real UIKit interaction probe; run only on an already booted Simulator."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mobile", ROOT / "tools/mobile.py")
mobile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mobile)
IDENTIFIER = "org.minyar.mobile-smoke"
SUCCESS = "mobile UIKit smoke passed: launch, action, Unicode edit, toggle, reuse, selection"


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
    evidence.mkdir(parents=True, exist_ok=True)
    subprocess.run(["xcrun", "simctl", "install", device, str(app)], check=True, timeout=45)
    command = ["xcrun", "simctl", "launch", "--console", "--terminate-running-process", device, IDENTIFIER]
    (evidence / "command.json").write_text(json.dumps(command, indent=2) + "\n")
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        (evidence / "stdout").write_text(result.stdout)
        (evidence / "stderr").write_text(result.stderr)
        if result.returncode or SUCCESS not in result.stdout.splitlines():
            raise RuntimeError(f"UIKit interaction check failed with status {result.returncode}; evidence in {evidence}")
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
