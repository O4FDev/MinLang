#!/usr/bin/env python3
"""Generate full default casing overrides and context properties from pinned UCD data."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests/fixtures/unicode-18.0.0"
OUTPUT = ROOT / "runtime/native/unicode_case_data.h"


def rows(name):
    source = (DATA / name).read_text(encoding="utf-8")
    if not source.startswith("# " + name.removesuffix(".txt") + "-18.0.0.txt\n"):
        raise ValueError("Unicode data version changed: " + name)
    for raw in source.splitlines():
        line = raw.partition("#")[0].strip()
        if line:
            yield [field.strip() for field in line.split(";")]


def ranges(property_name):
    found = []
    for fields in rows("DerivedCoreProperties.txt"):
        if fields[1] != property_name:
            continue
        limits = [int(value, 16) for value in fields[0].split("..")]
        found.append((limits[0], limits[-1]))
    merged = []
    for first, last in sorted(found):
        if merged and first <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(last, merged[-1][1]))
        else:
            merged.append((first, last))
    return merged


def generate():
    special = []
    conditional = final_sigma = 0
    for fields in rows("SpecialCasing.txt"):
        if fields[4]:
            conditional += 1
            condition = fields[4].split()
            if fields[0] == "03A3" and condition == ["Final_Sigma"] and fields[1] == "03C2":
                final_sigma += 1
            elif condition[0] not in ("lt", "tr", "az"):
                raise ValueError("unsupported nonlocale casing context: " + fields[4])
            continue
        lower = [int(value, 16) for value in fields[1].split()]
        upper = [int(value, 16) for value in fields[3].split()]
        if not (1 <= len(lower) <= 3 and 1 <= len(upper) <= 3):
            raise ValueError("full case mapping exceeds the declared three-scalar limit")
        special.append((int(fields[0], 16), lower, upper))
    special.sort()
    cased, ignorable = ranges("Cased"), ranges("Case_Ignorable")
    if (len(special), len(cased), len(ignorable), conditional, final_sigma) != (104, 163, 468, 16, 1):
        raise ValueError("pinned Unicode 18 casing data changed")
    if len({row[0] for row in special}) != len(special):
        raise ValueError("duplicate full case mapping")
    lines = [
        "/* Generated from Unicode 18.0.0 SpecialCasing and DerivedCoreProperties.",
        " * Unicode data license: vendor/utf8proc/LICENSE.md.",
        " * Regenerate with python3 tools/generate-unicode-case.py. */",
        "typedef struct { uint32_t first, last; } UnicodeCaseRange;",
        "typedef struct {",
        "    uint32_t scalar, lower[3], upper[3];",
        "    unsigned char lower_count, upper_count;",
        "} UnicodeCaseMapping;",
        "static const UnicodeCaseMapping unicode_case_mappings[] = {",
    ]
    for scalar, lower, upper in special:
        encoded = []
        for mapping in (lower, upper):
            encoded.append("{" + ", ".join(f"0x{value:X}" for value in mapping) + "}")
        lines.append(f"    {{0x{scalar:X}, {encoded[0]}, {encoded[1]}, {len(lower)}, {len(upper)}}},")
    lines.append("};")
    for name, values in (("cased", cased), ("case_ignorable", ignorable)):
        lines.append(f"static const UnicodeCaseRange unicode_{name}_ranges[] = {{")
        for first, last in values:
            lines.append(f"    {{0x{first:X}, 0x{last:X}}},")
        lines.append("};")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="reject a stale generated header")
    options = parser.parse_args()
    source = generate()
    if options.check:
        if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != source:
            parser.exit(1, "Unicode casing header is stale; run python3 tools/generate-unicode-case.py\n")
    else:
        OUTPUT.write_text(source, encoding="utf-8")
    print("Unicode 18 casing tables: 104 full mappings, 163 cased ranges, 468 ignorable ranges")


if __name__ == "__main__":
    main()
