#!/usr/bin/env python3
"""Generate/check the published reserved function names from compiler predicates."""
import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def names():
    source = (ROOT / 'compiler/compiler.min').read_text()
    found = set()
    for function in ('isBuiltinName', 'isNumericBuiltin', 'isFloatFunction'):
        body = re.search(r'^function ' + function + r'\([^\n]+\{\n(.*?)\n}', source, re.M | re.S)
        if body is None:
            raise ValueError('missing compiler predicate ' + function)
        found.update(re.findall(r'name == "([A-Za-z_][A-Za-z_0-9]*)"', body[1]))
    return sorted(found)


def render():
    return '''# Reserved function names

These names belong to the language's built-in functions and constructors.
A user function cannot declare one of them, including inside an imported
module. Choose a different function name, such as `joinTextLocal` or `joinWith`.
Record fields and methods use their receiver's namespace; this list reserves
function declarations, not field names or arbitrary prefixes.

Names are case-sensitive. Keywords and type syntax are described in
[the language reference](language.md). Standard-library functions belong to
their module alias and do not reserve every module's function namespace.

| Reserved function name |
| --- |
''' + ''.join(f'| `{name}` |\n' for name in names()) + '''
Generated from the compiler by `python3 tools/reserved-names.py`.
Run `python3 tools/reserved-names.py --check` after changing built-in names.
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    target = ROOT / 'docs/reserved-names.md'
    expected = render()
    if args.check:
        if not target.exists() or target.read_text() != expected:
            parser.exit(1, 'reserved-name list is stale; run python3 tools/reserved-names.py\n')
    else:
        target.write_text(expected)


if __name__ == '__main__': main()
