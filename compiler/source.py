import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
SOURCES = (
    'stages/source.min',
    'stages/emission.min',
    'stages/lexer.min',
    'stages/symbols.min',
    'stages/declarations.min',
    'stages/runtime-abi.min',
    'stages/types.min',
    'stages/ownership.min',
    'stages/operators.min',
    'stages/expressions.min',
    'stages/statements.min',
    'stages/literals.min',
    'stages/calls.min',
    'stages/assignment.min',
    'stages/native.min',
    'stages/effects.min',
    'stages/functions.min',
    'stages/pipeline.min',
    'stages/modules.min',
    'stages/incremental.min',
    'closure-compiler.min',
    'errors-compiler.min',
    'calldepth-compiler.min',
    'thread-compiler.min',
    'compiler.min',
)


def core_source(root=ROOT):
    source = ''.join((root / name).read_text() for name in SOURCES)
    names = re.findall(r'^function (\w+)\(', source, re.M)
    if len(names) != len(set(names)):
        raise ValueError('duplicate compiler function')
    return source


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    source = core_source()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(args.output.name + '.tmp')
    temporary.write_text(source)
    temporary.replace(args.output)


if __name__ == '__main__':
    main()
