#!/usr/bin/env python3
"""Bridge the previous compiler's removed builtins for a shared-input comparison.

Only code identifiers change; literals containing the previous frontend's
language rules remain intact. Both compilers receive the resulting source and
link against the same runtime. LLVM aliases add no wrapper instructions.
"""

import hashlib
import json
from pathlib import Path
import re
import sys


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def prepare(source_path, output_path, runtime_path, evidence_path):
    source = source_path.read_text()
    runtime = runtime_path.read_text()
    bridges = {
        "readTextFile": ("budgetReadTextFile", "path: Text", ": Text", "minyar_read_text_file", "ptr (ptr)"),
        "fileExists": ("budgetFileExists", "path: Text", ": Boolean", "minyar_file_exists", "i1 (ptr)"),
        "argumentCount": ("budgetArgumentCount", "", ": Integer", "minyar_argument_count", "i64 ()"),
        "argument": ("budgetArgument", "index: Integer", ": Text", "minyar_argument", "ptr (i64)"),
        "writeTextFile": ("budgetWriteTextFile", "path: Text, value: Text", "", "minyar_write_text_file", "void (ptr, ptr)"),
    }
    tokens = re.compile(r'''//[^\n]*|/\*[\s\S]*?\*/|"(?:\\[\s\S]|[^"\\])*"|'(?:\\[\s\S]|[^'\\])*'|[A-Za-z_][A-Za-z_0-9]*''')
    counts = {}

    def replace(match):
        name = match[0]
        if name not in bridges:
            return name
        call = re.match(r"\s*\(", source[match.end():])
        qualified = source[:match.start()].rstrip().endswith(".")
        if call and not qualified:
            counts[name] = counts.get(name, 0) + 1
            return bridges[name][0]
        return name

    output = tokens.sub(replace, source)
    mode = "unchanged"
    if counts:
        mode = "legacy-builtin-bridge"
        # The legacy builtin accepted either Text or List<Text>. Its sole list
        # call streams the compiler output; keep that streaming behavior.
        call = "budgetWriteTextFile(budgetArgument(1), pieces)"
        if output.count(call) != 1:
            raise ValueError("unrecognized legacy compiler output; review the comparison bridge")
        output = output.replace(call, "budgetWriteTextParts(budgetArgument(1), pieces)")
        bridges.update({
            "openTextWriter": ("budgetOpenTextWriter", "path: Text", ": Integer", "minyar_runtime_openTextWriter", "i64 (ptr)"),
            "writeTextPart": ("budgetWriteTextPart", "writer: Integer, part: Text", "", "minyar_runtime_writeTextPart", "void (i64, ptr)"),
            "closeTextWriter": ("budgetCloseTextWriter", "writer: Integer", "", "minyar_runtime_closeTextWriter", "void (i64)"),
        })
        declarations = []
        aliases = []
        for name, parameters, result, target, signature in bridges.values():
            if not re.search(r"^define[^\n]*@" + re.escape(target) + r"\(", runtime, re.MULTILINE):
                raise ValueError("missing comparison runtime definition: " + target)
            declarations.append(f'function {name}({parameters}){result} {{ native "budget" }}')
            alias = f"@minyar_budget_{name} = alias {signature}, ptr @{target}"
            if f"@minyar_budget_{name} =" not in runtime:
                aliases.append(alias)
        declarations.append("""function budgetWriteTextParts(path: Text, parts: List<Text>) {
    let writer = budgetOpenTextWriter(path)
    for part in parts { budgetWriteTextPart(writer, part) }
    budgetCloseTextWriter(writer)
}""")
        output = "\n".join(declarations) + "\n" + output
        if aliases:
            runtime_path.write_text(runtime + "\n" + "\n".join(aliases) + "\n")
    output_path.write_text(output)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps({
        "mode": mode,
        "source_sha256": digest(source),
        "input_sha256": digest(output),
        "runtime_sha256": digest(runtime_path.read_text()),
        "identifier_replacements": counts,
        "streaming_output": True,
    }, indent=2) + "\n")
    print("Compiler comparison input: " + mode)


if __name__ == "__main__":
    if len(sys.argv) != 5:
        raise SystemExit("usage: prepare-compiler-budget.py SOURCE INPUT RUNTIME_LL EVIDENCE_JSON")
    prepare(*(Path(argument) for argument in sys.argv[1:]))
