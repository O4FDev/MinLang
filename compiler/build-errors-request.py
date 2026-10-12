#!/usr/bin/env python3
"""Assemble a parser-owned Result request probe without changing ordinary IR."""
import argparse
from pathlib import Path
import re
import runpy

ROOT = Path(__file__).resolve().parents[1]


def replace(source, old, new):
    if source.count(old) != 1:
        raise ValueError('core changed; review Result request adapter: ' + old[:100])
    return source.replace(old, new, 1)


def assemble():
    closure = runpy.run_path(str(ROOT / 'scripts/build-closure-compiler.py'))
    source = closure['assemble'](runpy.run_path(str(ROOT / 'compiler/source.py'))['core_source']())
    # Parse the complete native marker before ordinary native ABI validation.
    # Recovery must be selected before generic Result requests, even when an
    # earlier imported module contains Result syntax.
    signature = re.search(r'^function compileTokens\([^\n]*\{\n', source, re.M).group(0)
    source = replace(source, signature, signature +
        '    let depthRequest = 0\n'
        '    while depthRequest + 1 < tokenTexts.length {\n'
        '        if tokenKinds[depthRequest] == 1 && tokenTexts[depthRequest] == "native" && tokenKinds[depthRequest + 1] == 3 && tokenTexts[depthRequest + 1] == "calldepth" { exit(88) }\n'
        '        depthRequest = depthRequest + 1\n    }\n')
    signature = re.search(r'^function takeType\([^\n]*\{\n', source, re.M).group(0)
    source = replace(source, signature + '    let name = tokenTexts[cursor[0]]\n',
                     signature + '    let name = tokenTexts[cursor[0]]\n'
                     '    requestResultType(tokenKinds, tokenTexts, tokenLines, cursor)\n')
    signature = re.search(r'^function takeCallbackType\([^\n]*\{\n', source, re.M).group(0)
    source = replace(source, signature, signature +
                     '    requestResultType(kinds, texts, lines, cursor)\n')
    start = source.index('function parseAtom(')
    anchor = '    let value = ""\n'
    end = source.index('\nfunction ', start + 1)
    tail = source[start:end]
    tail = replace(tail, anchor, anchor +
        '    if kind == 1 && (token == "Ok" || token == "Err") && tokenKinds[tokenIndex + 1] == 4 && tokenTexts[tokenIndex + 1] == "<" {\n'
        '        requestResultConstructor(tokenKinds, tokenTexts, tokenLines, state)\n    }\n')
    source = source[:start] + tail + source[end:]
    source = replace(source,
        'texts[position - 1] == "List" || texts[position - 1] == "Map" || texts[position - 1] == "Callback")',
        'texts[position - 1] == "List" || texts[position - 1] == "Map" || texts[position - 1] == "Callback" || texts[position - 1] == "Result")')
    source = replace(source,
        'token != "List" && token != "Map" && (token != "Callback" || tokenTexts[position + 1] != "<") && genericDepth == 0',
        'token != "List" && token != "Map" && token != "Result" && (token != "Callback" || tokenTexts[position + 1] != "<") && genericDepth == 0')
    source = replace(source,
        '                if kind == 4 && token == ":" && (declarationMode == 1 || functionHeader || letDeclaration) {',
        '                if kind == 1 && (token == "Ok" || token == "Err") && tokenTexts[position + 1] == "<" { typeMode = true; genericDepth = 0 }\n'
        '                if kind == 4 && token == ":" && (declarationMode == 1 || functionHeader || letDeclaration) {')
    source = replace(source,
        'token != "List" && token != "Map" && token != "Result" && (token != "Callback"',
        'token != "Ok" && token != "Err" && token != "List" && token != "Map" && token != "Result" && (token != "Callback"')
    source = replace(source,
        '        let pieces = compileEntryWithLibrary(argument(0), stackOwnerLimit, library)\n',
        '        let pieces = compileEntryWithLibrary(argument(0), stackOwnerLimit, library)\n'
        '        exit(0)\n')
    position = source.index('\nfunction main(')
    source = source[:position] + '\n' + (ROOT / 'compiler/errors-request.min').read_text() + source[position:]
    names = re.findall(r'^function (\w+)\(', source, re.M)
    if len(names) != len(set(names)):
        raise ValueError('duplicate Result request helper')
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    source = assemble()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(args.output.name + '.tmp')
    temporary.write_text(source)
    temporary.replace(args.output)


if __name__ == '__main__':
    main()
