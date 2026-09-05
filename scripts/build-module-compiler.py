#!/usr/bin/env python3
"""Assemble the optional module compiler from the compiler core.

The language has no conditional compilation. A guarded adapter adds stable
symbol/literal identities and body-work counters to this build. Every hunk must
match exactly once so core changes cannot silently produce a stale adapter."""
import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def adapt(source, patch):
    lines = patch.splitlines(keepends=True)
    index = 0
    while index < len(lines) and not lines[index].startswith('@@ '):
        index += 1
    while index < len(lines):
        header = lines[index].rstrip('\n')
        if not re.fullmatch(r'@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@.*', header):
            raise ValueError('invalid adapter hunk header: ' + header)
        index += 1
        before, after = [], []
        while index < len(lines) and not lines[index].startswith('@@ '):
            line = lines[index]
            if line[0] not in ' +-':
                raise ValueError('invalid adapter hunk line')
            if line[0] in ' -':
                before.append(line[1:])
            if line[0] in ' +':
                after.append(line[1:])
            index += 1
        old = ''.join(before)
        if not old or source.count(old) != 1:
            raise ValueError('compiler core changed; review module adapter at ' + header)
        source = source.replace(old, ''.join(after), 1)
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    core = adapt((ROOT / 'src/compiler.min').read_text(),
                 (ROOT / 'src/module-compiler-adapter.patch').read_text())
    matches = list(re.finditer(r'^function main\(', core, re.MULTILINE))
    if len(matches) != 1 or re.search(r'^function ', core[matches[0].end():], re.MULTILINE):
        raise SystemExit('compiler main must be its one final function')
    frontend = (ROOT / 'src/module-compiler.min').read_text()
    assembled = core[:matches[0].start()] + '\n' + frontend
    names = re.findall(r'^function (\w+)\(', assembled, re.MULTILINE)
    if len(names) != len(set(names)):
        raise SystemExit('duplicate compiler function in assembled source')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(args.output.name + '.tmp')
    temporary.write_text(assembled)
    temporary.replace(args.output)


if __name__ == '__main__':
    main()
