#!/usr/bin/env python3
"""Generate the optional closure frontend from the one maintained core.

Every adapter anchor must match exactly once. This extends the existing
parser, ownership emitter, module resolver and graph fixups without forking
their implementations. Ordinary programs keep the ordinary frontend.
"""
from pathlib import Path
import argparse
import re
import runpy
import hashlib

ROOT = Path(__file__).resolve().parents[1]


def replace(source, old, new):
    if source.count(old) != 1:
        raise ValueError('core changed; review closure adapter: ' + old[:100])
    return source.replace(old, new, 1)


def body(source, name, replacement):
    match = re.search(r'^function ' + re.escape(name) + r'\([^\n]*\{\n', source, re.M)
    if not match:
        raise ValueError('missing function ' + name)
    end = source.find('\n}\n', match.end())
    if end < 0:
        raise ValueError('missing function end ' + name)
    return source[:match.end()] + replacement + source[end:]


def ordinary_control(source):
    type_start = source.index('    if name == "Callback" && tokenTexts[cursor[0] + 1] == "<" {', source.index('function takeType('))
    type_end = source.index('    let code = simpleTypeCode(name)', type_start)
    type_dispatch = source[type_start:type_end]
    source = source[:type_start] + source[type_end:]
    atom_start = source.index('    if token == "function" && tokenTexts[tokenIndex + 1] == "(" {', source.index('function parseAtom('))
    atom_end = source.index('\n    if kind == 1 {', atom_start)
    atom_dispatch = source[atom_start:atom_end]
    source = source[:atom_start] + source[atom_end:]
    atom_value = source.index('    let value = ""\n', source.index('function parseAtom(')) + len('    let value = ""\n')
    atom_kind = source.index('    if kind == 1 {', atom_value)
    source = source[:atom_value] + '\n' + source[atom_kind:]
    # Ordinary cyclic-edge checks request this frontend before storing an
    # unsafe edge. Restore those two anchors before applying the graph adapter.
    source = replace(source, '            if type == listType {\n                exit(86)\n',
        '            if type == listType {\n                fail("this List mutation could create a reference cycle; construct a new List instead")\n')
    source = replace(source, '                exit(86)\n            }\n            let record = type - 1000\n',
        '                fail(describeLocation(tokenLocation(locations, location)) + ": assigning this field could create a reference cycle; construct a new record instead")\n            }\n            let record = type - 1000\n')
    return source, type_dispatch, atom_dispatch


def assemble(source):
    source, type_dispatch, atom_dispatch = ordinary_control(source)
    adapt = runpy.run_path(str(ROOT / 'scripts/build-module-compiler.py'))['adapt']
    source = adapt(source, (ROOT / 'compiler/managed-graphs-adapter.patch').read_text())
    type_position = source.index('    let code = simpleTypeCode(name)', source.index('function takeType('))
    source = source[:type_position] + type_dispatch + source[type_position:]
    atom_position = source.index('    if kind == 1 {', source.index('function parseAtom('))
    source = source[:atom_position] + atom_dispatch + '\n' + source[atom_position:]
    source = replace(source, '    let firstToken = tokenKinds.length\n',
        '    let firstToken = tokenKinds.length\n'
        '    let delimiterFrames: List<Integer> = []\n    let delimiterDepth = 0\n')
    source = replace(source, '                                    let punctuationKind = 4\n',
        '                                    let punctuationKind = 4\n'
        '                                    if punctuation == "{" {\n'
        '                                        while delimiterFrames.length < delimiterDepth * 2 + 2 { delimiterFrames.add(0) }\n'
        '                                        delimiterFrames[delimiterDepth * 2] = roundDepth\n'
        '                                        delimiterFrames[delimiterDepth * 2 + 1] = squareDepth\n'
        '                                        delimiterDepth = delimiterDepth + 1\n'
        '                                        roundDepth = 0\n                                        squareDepth = 0\n'
        '                                    }\n'
        '                                    if punctuation == "}" && delimiterDepth > 0 {\n'
        '                                        delimiterDepth = delimiterDepth - 1\n'
        '                                        roundDepth = delimiterFrames[delimiterDepth * 2]\n'
        '                                        squareDepth = delimiterFrames[delimiterDepth * 2 + 1]\n'
        '                                    }\n')
    start = source.index('    if name == "Callback" && tokenTexts[cursor[0] + 1] == "<" {', source.index('function takeType('))
    end = source.index('    let code = simpleTypeCode(name)', start)
    source = source[:start] + ('    if name == "Callback" && tokenTexts[cursor[0] + 1] == "<" {\n'
        '        return takeCallbackType(tokenKinds, tokenTexts, tokenLines, cursor, symbolNames, symbolKinds, false)\n'
        '    }\n') + source[end:]
    start = source.index('    if token == "function" && tokenTexts[tokenIndex + 1] == "(" {', source.index('function parseAtom('))
    end = source.index('\n    if kind == 1 {', start)
    call = 'tokenKinds, tokenTexts, tokenLines, functionNames, symbolKinds, functionReturnTypes, functionParameterCounts, functionParameterNames, functionParameterTypes, localNames, localTypes, localIds, localLengths, state, textState, output, globals, resultType'
    source = source[:start] + ('    if token == "function" && tokenTexts[tokenIndex + 1] == "(" {\n'
        '        return parseClosure(' + call + ')\n    }\n') + source[end:]
    source = replace(source, '    let callLocation = state[0]\n    state[0] = state[0] + 1',
        '    let callbackLocal = findLocal(localNames, localLengths, state, name)\n'
        '    if callbackLocal >= 0 && isCallbackType(localTypes[callbackLocal], functionNames) {\n'
        '        let callback = loadLocal(output, textState, state, localIds[callbackLocal], localTypes[callbackLocal])\n'
        '        return parseCallbackCall(' + call + ', callback, localTypes[callbackLocal])\n'
        '    }\n    let callLocation = state[0]\n    state[0] = state[0] + 1')
    source = replace(source, '    let symbolLookup = buildSymbolLookup(functionNames, symbolKinds)\n',
        '    prepareCallbackSymbols(tokenKinds, tokenTexts, tokenLines, functionNames, symbolKinds, symbolLocations, functionReturnTypes, functionParameterCounts)\n'
        '    let symbolLookup = buildSymbolLookup(functionNames, symbolKinds)\n')
    signature = re.search(r'^function compileTokens\([^\n]*\{\n', source, re.M).group(0)
    source = replace(source, signature, signature +
        '    let expanded = normalizeCallbackTokens(tokenKinds, tokenTexts, tokenLines, scannedStarts, scannedEnds)\n'
        '    tokenKinds = expanded.kinds\n    tokenTexts = expanded.texts\n    tokenLines = expanded.lines\n')
    source = replace(source, '    checkParallelCalls(globals)\n    finishCycleFixups(',
        '    compileClosureBodies(tokenKinds, tokenTexts, tokenLines, functionNames, symbolKinds, functionReturnTypes, functionParameterCounts, functionParameterNames, functionParameterTypes, output, globals)\n'
        '    checkParallelCalls(globals)\n    finishCallbackGraph(functionReturnTypes, functionParameterCounts, functionParameterTypes)\n'
        '    finishCycleFixups(')
    source = body(source, 'noteCycleFixup', '''    let baseA = typeA
    let baseB = typeB
    while isListType(baseA) { baseA = listElementType(baseA) }
    while isListType(baseB) { baseB = listElementType(baseB) }
    if !isRecordType(baseA) && !isRecordType(baseB) { return }
    returnTypes.add(-2)
    returnTypes.add(-1 - piece)
    returnTypes.add(-1 - typeA)
    returnTypes.add(-1 - typeB)''')
    source = body(source, 'checkListMutation', '''    if isReferenceType(listElementType(listType)) {
        activateCycleType(returnTypes, listType, counts.length)
    }''')
    source = body(source, 'checkFieldMutation', '''    if isReferenceType(fieldType) {
        activateCycleType(returnTypes, recordType, counts.length)
    }''')
    # A capture is an object escape, even when its body reads only scalar
    # fields. The ordinary field-only suffix proof predates callable values.
    source = body(source, 'prepareScalarRecord', '    return')
    source = replace(source, '                        state[0] = state[0] + 2\n                        let valueType: List<Integer> = []\n',
        '                        if localIds[local] < 0 { fail("captured bindings cannot be reassigned; capture a mutable record field") }\n'
        '                        state[0] = state[0] + 2\n                        let valueType: List<Integer> = []\n')
    # Optional frontend includes hidden graph edges only after all literals
    # have been type checked. Markers are filtered against that final graph.
    source = replace(source, '    if (tokenKinds[atom] == 1 && tokenTexts[atom + 1] == "(") || (tokenKinds[atom] == 4 && tokenTexts[atom] == "[") {',
        '    if tokenTexts[atom] != "function" && ((tokenKinds[atom] == 1 && tokenTexts[atom + 1] == "(") || (tokenKinds[atom] == 4 && tokenTexts[atom] == "[")) {')
    source = replace(source, 'token != "List" && genericDepth == 0',
        'token != "List" && (token != "Callback" || tokenTexts[position + 1] != "<") && genericDepth == 0')
    # Normalize anonymous header state in the shared module name rewriter.
    source = replace(source, '(token == "record" || token == "function") {',
        '(token == "record" || (token == "function" && tokenTexts[position + 1] != "(")) {')
    source = replace(source, '                let token = tokenTexts[position]\n                let kind = tokenKinds[position]\n',
        '                let token = tokenTexts[position]\n                let kind = tokenKinds[position]\n'
        '                if token == "function" && tokenTexts[position + 1] == "(" { functionHeader = true }\n'
        '                if token == "{" && functionHeader { functionHeader = false }\n')
    main = source.index('\nfunction main(')
    helpers = (ROOT / 'compiler/closure-compiler.min').read_text()
    source = source[:main] + '\n' + helpers + source[main:]
    names = re.findall(r'^function (\w+)\(', source, re.M)
    if len(names) != len(set(names)):
        raise ValueError('duplicate generated compiler function')
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--baseline', action='store_true', help='reconstruct the exact foundation compiler control')
    args = parser.parse_args()
    core = (ROOT / 'compiler/compiler.min').read_text()
    if args.baseline:
        assembled = ordinary_control(core)[0]
        expected = 'a5f30a7954381231fbe04a712b72bd9663d1bd7082c667fef851b739ec63c3cf'
        if hashlib.sha256(assembled.encode()).hexdigest() != expected:
            raise ValueError('foundation baseline reconstruction drifted; do not update the control silently')
    else:
        assembled = assemble(core)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(args.output.name + '.tmp')
    temporary.write_text(assembled)
    temporary.replace(args.output)


if __name__ == '__main__':
    main()
