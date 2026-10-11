#!/usr/bin/env python3
"""Assemble the opt-in native Result frontend from the maintained core.

All adapters fail closed when an anchor drifts. The ordinary compiler and
runtime remain byte-identical; Result adds no runtime entry points.
"""
from pathlib import Path
import argparse
import re
import runpy

ROOT = Path(__file__).resolve().parents[1]

def replace(source, old, new):
    if source.count(old) != 1:
        raise ValueError('core changed; review Result adapter: ' + old[:100])
    return source.replace(old, new, 1)

def assemble():
    closure = runpy.run_path(str(ROOT / 'scripts/build-closure-compiler.py'))
    source = closure['assemble']((ROOT / 'compiler/compiler.min').read_text())
    signature = re.search(r'^function compileTokens\([^\n]*\{\n', source, re.M).group(0)
    source = replace(source, signature, signature +
        '    let resultTokens = normalizeResultTypes(tokenKinds, tokenTexts, tokenLines)\n'
        '    if true {\n'
        '        tokenKinds = resultTokens.kinds\n    tokenTexts = resultTokens.texts\n    tokenLines = resultTokens.lines\n'
        '        let emptyStarts: List<Integer> = []\n    let emptyEnds: List<Integer> = []\n'
        '        scannedStarts = emptyStarts\n    scannedEnds = emptyEnds\n    }\n')
    # Normalization changes token positions; rescan declarations through the
    # maintained scanner instead of retaining stale load-module spans.
    args = ('tokenKinds, tokenTexts, tokenLines, functionNames, symbolKinds, '
            'functionReturnTypes, functionParameterCounts, functionParameterNames, '
            'functionParameterTypes, localNames, localTypes, localIds, localLengths, '
            'state, textState, output, globals')
    anchor = '    if kind == 1 {\n'
    pos = source.index(anchor, source.index('function parseAtom('))
    source = source[:pos] + (
        '    if kind == 1 && token == "try" { fail("try is only supported as a binding initializer") }\n'
        '    if kind == 1 && (resultPrefix(token, "minyar_result_ok_") || resultPrefix(token, "minyar_result_err_")) {\n'
        '        return parseResultConstructor(' + args + ', resultType)\n    }\n') + source[pos:]
    signature = re.search(r'^function compileAtomicStatement\([^\n]*\{\n', source, re.M).group(0)
    source = replace(source, signature, signature +
        '    if tokenIs(tokenKinds, tokenTexts, state, "match") {\n'
        '        return compileResultMatch(' + args + ', returnType)\n    }\n')
    anchor = ('\n        let value = parseExpression(' + args + ', valueType)\n')
    start = source.index('function compileAtomicStatement(')
    tail = source[start:]
    tail = replace(tail, anchor,
        '\n        let value = ""\n'
        '        if tokenIs(tokenKinds, tokenTexts, state, "try") {\n'
        '            value = parseResultTry(' + args + ', valueType, returnType)\n'
        '        } else {\n            value = parseExpression(' + args + ', valueType)\n        }\n')
    source = source[:start] + tail
    anchor = '                            if ignoredType[0] == 6 {'
    source = replace(source, anchor,
        '                            if resultTypeName(ignoredType[0], functionNames) { fail("a Result expression must be handled or bound") }\n' + anchor)
    signature = re.search(r'^function parseRecord\([^\n]*\{\n', source, re.M).group(0)
    source = replace(source, signature, signature +
        '    if resultPrefix(tokenTexts[state[0]], "minyar_result_type_") {\n'
        '        fail("Result values require Ok or Err constructors")\n    }\n')
    signature = re.search(r'^function checkFieldAccess\([^\n]*\{\n', source, re.M).group(0)
    source = replace(source, signature, signature +
        '    if resultPrefix(recordName, "minyar_result_type_") {\n'
        '        fail("Result payloads are only accessible through match or try")\n    }\n')
    source = replace(source, 'token != "List" && (token != "Callback" || tokenTexts[position + 1] != "<") && genericDepth == 0',
        'token != "List" && token != "Result" && (token != "Callback" || tokenTexts[position + 1] != "<") && genericDepth == 0')
    # Body ownership alone cannot reject unused managed parameters. Keep the
    # scalar-only parallel ABI independent of liveness and body optimization.
    source = replace(source,
        '            finishParallelFunction(output, globals, entrySlot, bodySlot, name, state[6] == 1)',
        '            let parallelReferences = state[6] == 1 || isReferenceType(returnType)\n'
        '            let parallelParameter = 0\n'
        '            while parallelParameter < parameterNames.length {\n'
        '                if isReferenceType(parameterTypes[parallelParameter]) { parallelReferences = true }\n'
        '                parallelParameter = parallelParameter + 1\n'
        '            }\n'
        '            finishParallelFunction(output, globals, entrySlot, bodySlot, name, parallelReferences)')
    # Type arguments in explicit constructor headers need module qualification.
    source = replace(source, '                if kind == 4 && token == ":" && (declarationMode == 1 || functionHeader || letDeclaration) {',
        '                if kind == 1 && (token == "Ok" || token == "Err") && tokenTexts[position + 1] == "<" { typeMode = true; genericDepth = 0 }\n'
        '                if kind == 4 && token == ":" && (declarationMode == 1 || functionHeader || letDeclaration) {')
    source = replace(source, 'token != "List" && token != "Result" && (token != "Callback"',
        'token != "Ok" && token != "Err" && token != "List" && token != "Result" && (token != "Callback"')
    pos = source.index('\nfunction main(')
    source = source[:pos] + '\n' + (ROOT / 'compiler/errors-compiler.min').read_text() + source[pos:]
    names = re.findall(r'^function (\w+)\(', source, re.M)
    if len(names) != len(set(names)):
        raise ValueError('duplicate Result compiler function')
    return source

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    assembled = assemble()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(args.output.name + '.tmp')
    temporary.write_text(assembled)
    temporary.replace(args.output)

if __name__ == '__main__':
    main()

