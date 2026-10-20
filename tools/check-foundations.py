#!/usr/bin/env python3
"""Build the pinned ownership calculus and retain proof/trust-control evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


class Failed(RuntimeError):
    pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lake", default=os.environ.get("LAKE", "lake"))
    parser.add_argument("--output", type=Path, default=Path("build/foundations-proof-evidence"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    for prior in output.iterdir():
        if prior.is_file():
            prior.unlink()
    records = []
    started = time.monotonic()

    def run(name, command, *, data=None, cwd=None, timeout=180):
        before = time.monotonic()
        result = subprocess.run(command, cwd=cwd or root, input=data, text=True,
                                capture_output=True, timeout=timeout, check=False)
        (output / f"{name}.stdout").write_text(result.stdout)
        (output / f"{name}.stderr").write_text(result.stderr)
        records.append({"name": name, "command": [str(part) for part in command],
                        "cwd": str(cwd or root), "status": result.returncode,
                        "wall_seconds": time.monotonic() - before})
        return result

    def required(name, command, **kwargs):
        result = run(name, command, **kwargs)
        if result.returncode:
            raise Failed(f"{name} failed ({result.returncode}); see {output}")
        return result

    failure = None
    pin = None
    try:
        pin = (root / "proofs/lean-toolchain").read_text().strip()
        if pin != "leanprover/lean4:v4.19.0":
            raise Failed(f"unreviewed Lean toolchain: {pin}")
        proofs = root / "proofs"
        version = required("version", [args.lake, "env", "lean", "--version"], cwd=proofs)
        if "version 4.19.0," not in version.stdout:
            raise Failed("the selected Lean executable does not match lean-toolchain")
        # Build the semantics before elaborating the environment audit. Keeping
        # these phases sequential avoids accepting a stale Main.olean when a new
        # proof module is added to the Minyar root import.
        required("build", [args.lake, "build", "ownership-check"], cwd=proofs)
        audit = required("audit", [args.lake, "env", "lean", "Audit.lean"], cwd=proofs)
        if "foundations audit:" not in audit.stdout:
            raise Failed("the environment audit produced no audit result")

        # Use the same environment command on new unreferenced declarations.
        # An arbitrary parse/type error is never accepted as a rejected trust hole.
        audit_source = (proofs / "Audit.lean").read_text()
        injections = [
            ("custom-axiom", "axiom injectedTrustHole : False", "unapproved axiom"),
            ("admitted-proof", "theorem injectedTrustHole : False := by sorry", "unapproved axiom"),
            ("unsafe-definition", "unsafe def injectedTrustHole : Nat := 7", "unsafe declaration"),
            ("unsafe-backend-looking", "unsafe def fake_cstage1 : Nat := 7", "unsafe declaration"),
            ("partial-definition", "partial def injectedTrustHole (n : Nat) : Nat := injectedTrustHole n",
             "partial declaration"),
        ]
        for name, declaration, diagnostic in injections:
            source = output / f"audit-{name}.lean"
            source.write_text(audit_source + "\nnamespace Minyar\n" + declaration +
                              "\nend Minyar\n#audit_minyar\n")
            result = run("audit-" + name, [args.lake, "env", "lean", str(source)], cwd=proofs)
            if result.returncode == 0 or diagnostic not in result.stdout + result.stderr:
                raise Failed(f"audit did not reject {name} for the expected reason")

        checker = root / "build/foundations-lean/bin/ownership-check"
        cases = [
            ("owners-borrows-moves-reuse", True,
             "alloc 0 0 0\nborrow 0 0 1 1\nuse 0 1\nendborrow 0 1\n"
             "retain 0 0 2 0\nmove 0 2 3 1\nrelease 0 0\nreuse 0 3 4 1\nexit 0 1\n"),
            ("irq-scalar-mmio-signal", True,
             "irq_enter\neffect scalar\neffect mmio\neffect signal\nirq_exit\n"),
            ("scope-loan-cleanup", True, "alloc 0 0 0\nborrow 0 0 1 0\nexit 0 0\n"),
            ("use-after-free", False, "alloc 0 0 0\nrelease 0 0\nuse 0 0\n"),
            ("double-free", False, "alloc 0 0 0\nrelease 0 0\nrelease 0 0\n"),
            ("use-after-move", False, "alloc 0 0 0\nmove 0 0 1 0\nuse 0 0\n"),
            ("release-borrowed-slot", False, "alloc 0 0 0\nborrow 0 0 1 0\nrelease 0 1\n"),
            ("outliving-borrow", False, "alloc 0 0 0\nborrow 0 0 1 1\nexit 0 0\n"),
            ("reuse-shared", False, "alloc 0 0 0\nretain 0 0 1 0\nreuse 0 0 2 0\n"),
            ("reuse-borrowed", False, "alloc 0 0 0\nborrow 0 0 1 0\nreuse 0 0 2 0\n"),
            ("wrong-owner", False, "alloc 0 0 0\nmove 0 2 3 0\n"),
            ("dma-cpu-use", False, "alloc 0 0 0\nsubmit 0 0\nuse 0 0\n"),
            ("dma-pending-free", False, "alloc 0 0 0\nsubmit 0 0\nrelease 0 0\n"),
            ("dma-aliased-submit", False, "alloc 0 0 0\nretain 0 0 1 0\nsubmit 0 0\n"),
            ("dma-bare-complete-hidden", False, "alloc 0 0 0\ncomplete 0 0\n"),
            ("irq-allocation", False, "irq_enter\nalloc 0 0 0\n"),
            ("irq-nesting", False, "irq_enter\nirq_enter\n"),
            ("parse-unknown", False, "invented_operation\n"),
            ("parse-trailing-operand", False, "alloc 0 0 0 extra\n"),
            ("parse-negative-object", False, "alloc -1 0 0\n"),
        ]
        for effect in ("managed", "float", "blocking", "lock", "native", "indirect", "cyclic"):
            cases.append(("irq-" + effect, False, f"irq_enter\neffect {effect}\n"))
        for name, accepted, trace in cases:
            (output / f"{name}.trace").write_text(trace)
            result = run(name, [str(checker)], data=trace)
            if accepted:
                expected = f"ok {len(trace.splitlines())}\n"
                if result.returncode or result.stdout != expected or result.stderr:
                    raise Failed(f"valid trace {name} failed")
            elif result.returncode != 1 or "error line " not in result.stderr:
                raise Failed(f"invalid trace {name} was not rejected")
        print(f"foundations: proofs/audit, {len(injections)} trust controls, {len(cases)} traces passed")
    except (Failed, OSError, subprocess.TimeoutExpired) as error:
        failure = str(error)
    finally:
        proof_sources = list((root / "proofs").rglob("*.lean"))
        proof_sources.append(root / "proofs/lean-toolchain")
        source_hashes = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                         for path in sorted(proof_sources)
                         if ".lake" not in path.parts}
        (output / "results.json").write_text(json.dumps({
            "schema": 1, "ok": failure is None, "error": failure,
            "lean_toolchain": pin,
            "wall_seconds": time.monotonic() - started,
            "sources_sha256": source_hashes, "commands": records,
        }, indent=2) + "\n")
    if failure:
        raise SystemExit(f"foundations: {failure}")


if __name__ == "__main__":
    main()
