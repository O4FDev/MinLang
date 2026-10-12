#!/usr/bin/env python3
"""Feature-selected cooperative emitter; every adapter anchor fails closed."""
from pathlib import Path
import argparse
import re
import runpy

ROOT = Path(__file__).resolve().parents[1]
closure = runpy.run_path(str(ROOT / 'scripts/build-closure-compiler.py'))
replace = closure['replace']
body = closure['body']


def edit(source, name, transform):
    start = source.index('function ' + name + '(')
    end = source.index('\n}\n', start) + 3
    return source[:start] + transform(source[start:end]) + source[end:]


def adapt(source):
    """Apply recovery after the closure/Result and optional thread adapters.

    The caller supplies the complete assembled frontend. Anchors fail closed;
    this function does not reconstruct or replace another adapter's source.
    See docs/progress/ws2-calldepth-adapter.md for the shared emitter contract.
    """
    source = body(source, 'takeOwner', '    return false')
    source = edit(source, 'parseAtom', lambda s: replace(s,
        '                    if id >= 0 && resultType.length > 3 && resultType[2] == id && resultType[3] == tokenIndex {\n'
        '                        let owner = output.length\n'
        '                        output.add("  ; minyar-owned-local-transfer\\n")\n'
        '                        output.add(Text(ownershipSlot(state, id)))\n'
        '                        markOwner(resultType, owner)\n'
        '                    }\n',
        '                    // Recovery retains the local owner throughout fallible evaluation.\n'))
    source = edit(source, 'ownResult', lambda s: replace(s,
        '    if isReferenceType(resultType[0]) {',
        '    if resultType.length > 1 && resultType[1] >= 0 { return }\n'
        '    if isReferenceType(resultType[0]) {'))
    source = edit(source, 'parseListLiteral', lambda s: replace(replace(s,
        '    let references = false\n',
        '    let constructionOwner = keepReference(output, state, value, 100001)\n'
        '    let references = false\n'),
        '    setType(resultType, 100000 + elementType)\n',
        '    setType(resultType, 100000 + elementType)\n'
        '    markOwner(resultType, constructionOwner)\n'))
    source = edit(source, 'parseCall', lambda s: replace(s,
        '                                    setType(resultType, returnType)\n',
        '                                    recoveryCheckpoint(output, textState, state)\n'
        '                                    setType(resultType, returnType)\n'))
    source = edit(source, 'parseCallbackCall', lambda s: replace(s,
        '    state[14] = state[14] + 1\n',
        '    state[14] = state[14] + 1\n'
        '    recoveryCheckpoint(output, textState, state)\n'))
    # The current block, rather than %entry, is the predecessor of later PHIs.
    source = edit(source, 'compileFunctions', lambda s: replace(s,
        '        textState[0] = "entry"\n', '        textState[0] = "recovery.body"\n'))
    source = edit(source, 'compileTopLevel', lambda s: replace(s,
        '    textState.add("entry")\n', '    textState.add("recovery.body")\n'))
    source = edit(source, 'compileClosureBodies', lambda s: replace(s,
        '            let textState: List<Text> = ["entry", "callback"]\n',
        '            let textState: List<Text> = ["recovery.body", "callback"]\n'))
    # Structured return metadata covers named, native, callback and main exits.
    source = replace(source,
        'owners: Integer, references: Boolean) {\n    let entry: List<Text> = []',
        'owners: Integer, references: Boolean, returnedType: Text) {\n    let entry: List<Text> = []')
    source = edit(source, 'finishFunctionEntry', lambda s: replace(replace(s,
        '    entry.add("  call void @minyar_stack_enter()\\n")\n',
        '    entry.add("  %recovery.accepted = call i32 @minyar_recovery_enter()\\n")\n'
        '    entry.add("  %recovery.allowed = icmp ne i32 %recovery.accepted, 0\\n")\n'
        '    entry.add("  br i1 %recovery.allowed, label %recovery.body, label %recovery.reject\\n")\n'
        '    entry.add("recovery.reject:\\n" + recoveryDummy(returnedType) + "recovery.body:\\n")\n'),
        '    output[slot] = joinText(entry)\n',
        '    output[slot] = joinText(entry)\n'
        '    output.add("\\nrecovery.unwind:\\n")\n'
        '    if references { output.add("  call void @minyar_rc_leave()\\n") }\n'
        '    output.add("  call void @minyar_stack_leave()\\n")\n'
        '    output.add(recoveryDummy(returnedType))\n'))
    source = replace(source,
        'finishFunctionEntry(output, entrySlot, state[4], parameterNames.length, state[8], state[6] == 1)',
        'if !depthBoundary && !machineIntrinsic {\n'
        '            finishFunctionEntry(output, entrySlot, state[4], parameterNames.length, state[8], state[6] == 1, emittedReturn)\n'
        '        }')
    source = replace(source,
        'finishFunctionEntry(output, entrySlot, state[4], 0, state[8], state[6] == 1)',
        'finishFunctionEntry(output, entrySlot, state[4], 0, state[8], state[6] == 1, "i32")')
    source = replace(source,
        'finishFunctionEntry(output, entry, state[4], parameters.length, state[8], state[6] == 1)',
        'finishFunctionEntry(output, entry, state[4], parameters.length, state[8], state[6] == 1, llvmType(result))\n'
        '            if stackOwnerLimit > 0 && state[14] == 0 && state[6] == 1 && state[8] >= 1 && state[8] <= stackOwnerLimit {\n'
        '                finishStackOwnership(output, entry, state[8])\n            }')
    source = replace(source,
        'output: List<Text>, globals: List<Text>) {\n    let marker = 0\n',
        'output: List<Text>, globals: List<Text>, stackOwnerLimit: Integer) {\n    let marker = 0\n')
    source = replace(source,
        'functionParameterTypes, output, globals)\n    checkParallelCalls(globals)',
        'functionParameterTypes, output, globals, stackOwnerLimit)\n    checkParallelCalls(globals)')
    source = body(source, 'finishStackOwnership', '''    let prefix = "  call void @minyar_rc_enter(i64 " + Text(owners) + ")\\n"
    let entry = output[slot]
    let start = recoveryTextPosition(entry, prefix)
    if start < 0 { fail("recovery stack frame entry metadata drifted") }
    let storage = "  %rc.stack.header = alloca [64 x i8], align 8\\n"
    storage = storage + "  %rc.stack.owners = alloca [" + Text(owners * 2) + " x i64], align 8\\n"
    storage = storage + "  call void @minyar_rc_enter_stack_v1(ptr %rc.stack.header, ptr %rc.stack.owners, i64 " + Text(owners) + ")\\n"
    output[slot] = entry.slice(0, start) + storage + entry.slice(start + prefix.length, entry.length)
    let piece = slot + 1
    while piece < output.length {
        if output[piece] == "  call void @minyar_rc_leave()\\n" {
            output[piece] = "  call void @minyar_rc_leave_stack_v1(ptr %rc.stack.header)\\n"
        }
        piece = piece + 1
    }''')
    # Logical guards cover all normal language edges, including parallel ones.
    for name in ('dropCallDepthFrame', 'dropCallDepthFrameBetween', 'dropTreeGuards'):
        source = body(source, name, '    return')
    source = edit(source, 'compileFunctions', lambda s: replace(replace(replace(s,
        '        let machineIntrinsic = false\n', '        let machineIntrinsic = false\n        let depthBoundary = false\n'),
        '            hasNative = true\n',
        '            hasNative = true\n            depthBoundary = tokenTexts[state[12] + 1] == "calldepth"\n'),
        'stackOwnerLimit > 0 && name != "main" && state[5] == -1',
        'stackOwnerLimit > 0 && !depthBoundary && !machineIntrinsic && name != "main" && state[14] == 0'))
    source = edit(source, 'compileFunctions', lambda s: replace(s,
        '                lowerIntegerDispatch(tokenKinds, tokenTexts, tokenLines, bodyStart, state[0], parameterNames[0], output, globals, bodySlot, dispatchTable)\n',
        '                // Recovery keeps the structured body and its real predecessors.\n'))
    source = edit(source, 'parallelRuntimeAllowed', lambda s: replace(s,
        '    return callee == "minyar_tan"',
        '    if callee == "minyar_recovery_pending" || callee == "minyar_stack_leave" { return true }\n'
        '    return callee == "minyar_tan"'))
    source = edit(source, 'compileNative', lambda s: replace(s,
        '    if library == "machine" || library == "machine_arm64" {\n',
        '    if library == "calldepth" {\n'
        '        compileDepthBoundary(output, functionNames, symbolKinds, functionReturnTypes, functionParameterCounts, functionParameterTypes, name, returnType)\n'
        '        return\n    }\n'
        '    if (library == "machine" || library == "machine_arm64") && readableDeclarationName(name) == "callEntry" {\n'
        '        fail("machine.callEntry is unavailable in recoverable call-depth programs; use a typed language callback")\n    }\n'
        '    if library == "machine" || library == "machine_arm64" {\n'))
    source = edit(source, 'compileNative', lambda s: replace(s,
        '    output.add("  call void @minyar_rc_leave()\\n")\n',
        '    recoveryNativeCheckpoint(output, textState, state, returnType)\n'
        '    output.add("  call void @minyar_rc_leave()\\n")\n'))
    source = edit(source, 'compileClosureBodies', lambda s: replace(replace(replace(s,
        '        output.add("declare i64 @minyar_callback_domain()\\n")\n', ''),
        '        output.add("declare void @minyar_callback_check(ptr)\\n")\n', ''),
        '        output.add("declare void @minyar_callback_check_environment(ptr)\\n")\n', ''))
    declarations = ['void @minyar_rc_release(ptr)',
                    'i64 @minyar_callback_domain()', 'void @minyar_callback_check(ptr)',
                    'void @minyar_callback_check_environment(ptr)',
                    'i32 @minyar_recovery_enter()', 'i32 @minyar_recovery_pending()',
                    'void @minyar_calldepth_begin(ptr, i64)', 'i32 @minyar_calldepth_end(ptr)',
                    'i64 @minyar_calldepth_remaining()', 'void @minyar_calldepth_reporting_begin()',
                    'void @minyar_calldepth_reporting_end()']
    source = replace(source, '    output.add("declare void @minyar_stack_enter()\\n")\n',
        '    output.add("; minyar-calldepth-policy: cooperative-v1-full-program\\n")\n' +
        '    output.add("; minyar-callback-runtime: 1\\n")\n' +
        ''.join('    output.add("declare ' + d + '\\n")\n' for d in declarations) +
        '    output.add("declare void @minyar_stack_enter()\\n")\n')
    position = source.index('\nfunction main(')
    return source[:position] + '\n' + (ROOT / 'compiler/calldepth-compiler.min').read_text() + source[position:]


def assemble():
    return adapt(runpy.run_path(str(ROOT / 'compiler/build-errors-compiler.py'))['assemble']())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    source = assemble()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(source)


if __name__ == '__main__':
    main()
