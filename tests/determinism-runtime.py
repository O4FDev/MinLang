#!/usr/bin/env python3
"""Every runtime function the compiler can emit is classified by the determinism audit.

The audit rejects unclassified runtime calls inside deterministic functions. This check
moves that failure to the change that adds a runtime function, with the place to fix it.
"""
import pathlib
import re
import sys

root = pathlib.Path(__file__).resolve().parents[1]
audit = (root / "compiler/determinism-audit.min").read_text(encoding="utf-8")


def section(start: str, end: str) -> str:
    return audit[audit.index(start):audit.index(end)]


pure = section("function determinismRuntimePure", "function determinismExternalEffect")
effect = section("function determinismRuntimeEffect", "function determinismRuntimePure")
families = re.findall(r'"([^"]+)"', re.search(r"let families = \[(.*?)\]", pure, re.S).group(1))
names = re.findall(r'"([^"]+)"', re.search(r"let names = \[(.*?)\]", pure, re.S).group(1))
denied_prefixes = re.findall(r'resultPrefix\(name, "([^"]+)"\)', effect)
denied_names = re.findall(r'name == "([^"]+)"', effect)
assert families and names and denied_prefixes and denied_names, "classification lists were not found"

missing = set()
for path in sorted((root / "compiler").rglob("*.min")):
    if path.name == "determinism-audit.min":
        continue
    text = path.read_text(encoding="utf-8")
    for match in re.finditer(r"@(minyar_[a-z0-9_]+)(\"\s*\+)?", text):
        symbol = match.group(1)
        if match.group(2):
            # A name completed at run time: its fixed part must sit inside one family.
            if symbol == "minyar_" or any(f.startswith(symbol) or symbol.startswith(f) for f in families + denied_prefixes):
                continue
        elif any(symbol.startswith(f) for f in families) or symbol in names:
            continue
        elif any(symbol.startswith(p) for p in denied_prefixes) or symbol in denied_names:
            continue
        missing.add((symbol, str(path.relative_to(root))))

for symbol, path in sorted(missing):
    print(f"runtime function {symbol} (emitted in {path}) is not classified for deterministic functions; "
          "add it to determinismRuntimePure if it only computes from its arguments, or to "
          "determinismRuntimeEffect if it touches the host, in compiler/determinism-audit.min", file=sys.stderr)
if missing:
    sys.exit(1)
print(f"Determinism runtime classification: {len(families)} pure families, {len(names)} pure functions, "
      f"{len(denied_prefixes) + len(denied_names)} host-effect classes cover every emitted runtime function")
