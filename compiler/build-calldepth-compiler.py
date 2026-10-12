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


def adapt(source, *, unwind_hook=None):
    """Apply recovery after the closure/Result and optional thread adapters.

    The caller supplies the complete assembled frontend. Anchors fail closed;
    this function does not reconstruct or replace another adapter's source.
    unwind_hook is optional Minyar emitter source, with output/globals/caller
    available, run only on accepted unwind before ownership/depth leaves.
    See docs/progress/ws2-calldepth-adapter.md for the shared emitter contract.
    """
    if unwind_hook is not None and (not isinstance(unwind_hook, str) or not unwind_hook.strip()):
        raise ValueError('unwind_hook must be nonempty Minyar emitter source')
    hook_parameters = ', caller: Text, globals: List<Text>' if unwind_hook is not None else ''
    hook_arguments = ', textState[1], globals' if unwind_hook is not None else ''
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
        '    setType(resultType, makeListType(elementType))\n',
        '    setType(resultType, makeListType(elementType))\n'
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
        'owners: Integer, references: Boolean, returnedType: Text' + hook_parameters + ') {\n    let entry: List<Text> = []')
    source = edit(source, 'finishFunctionEntry', lambda s: replace(replace(s,
        '    entry.add("  call void @minyar_stack_enter()\\n")\n',
        '    entry.add("  %recovery.accepted = call i32 @minyar_recovery_enter()\\n")\n'
        '    entry.add("  %recovery.allowed = icmp ne i32 %recovery.accepted, 0\\n")\n'
        '    entry.add("  br i1 %recovery.allowed, label %recovery.body, label %recovery.reject\\n")\n'
        '    entry.add("recovery.reject:\\n" + recoveryDummy(returnedType) + "recovery.body:\\n")\n'),
        '    output[slot] = joinText(entry)\n',
        '    output[slot] = joinText(entry)\n'
        '    output.add("\\nrecovery.unwind:\\n")\n'
        + (''.join('    ' + line + '\n' for line in unwind_hook.strip().splitlines()) if unwind_hook is not None else '') +
        '    if references { output.add("  call void @minyar_rc_leave()\\n") }\n'
        '    output.add("  call void @minyar_stack_leave()\\n")\n'
        '    output.add(recoveryDummy(returnedType))\n'))
    source = replace(source,
        'finishFunctionEntry(output, entrySlot, state[4], parameterNames.length, state[8], state[6] == 1)',
        'if !depthBoundary && !machineIntrinsic {\n'
        '            finishFunctionEntry(output, entrySlot, state[4], parameterNames.length, state[8], state[6] == 1, emittedReturn' + hook_arguments + ')\n'
        '        }')
    source = replace(source,
        '    finishFunctionEntry(output, entrySlot, state[4], 0, state[8], state[6] == 1)\n    output.add("}\\n\\n")\n}\n',
        '    finishFunctionEntry(output, entrySlot, state[4], 0, state[8], state[6] == 1, "i32"' + hook_arguments + ')\n    output.add("}\\n\\n")\n}\n')
    # Module constant loaders own a frame only on their initialization path.
    # A rejected or unwound initializer leaves its constant uninitialized, so a
    # later read retries instead of reporting recursive initialization. The
    # recovery declarations below already declare minyar_rc_release.
    source = edit(source, 'compileModuleConstants', lambda s: replace(replace(replace(replace(s,
        '    output.add("declare void @minyar_rc_release(ptr)\\n")\n', ''),
        '            output.add("  store i8 1, ptr " + flag + "\\n")\n'
        '            // Only the initialization path owns a frame. Cached reads are loads.\n'
        '            let entrySlot = output.length\n'
        '            output.add("")\n',
        '            // Only the initialization path owns a frame. Cached reads are loads.\n'
        '            let entrySlot = output.length\n'
        '            output.add("")\n'
        '            output.add("  store i8 1, ptr " + flag + "\\n")\n'),
        '            textState.add("initialize")\n', '            textState.add("recovery.body")\n'),
        '            finishFunctionEntry(output, entrySlot, state[4], 0, state[8], state[6] == 1)\n',
        '            finishFunctionEntry(output, entrySlot, state[4], 0, state[8], state[6] == 1, llvmType(type)' + hook_arguments + ')\n'
        '            recoveryResetConstant(output, entrySlot, flag)\n'))
    source = edit(source, 'parseAtom', lambda s: replace(s,
        '                            value = emitCall(output, textState, state, type, constantIRName(token, "load"), values, types)\n'
        '                            state[14] = state[14] + 1\n',
        '                            value = emitCall(output, textState, state, type, constantIRName(token, "load"), values, types)\n'
        '                            state[14] = state[14] + 1\n'
        '                            recoveryCheckpoint(output, textState, state)\n'))
    # Sort comparators reenter language code through the runtime.
    source = edit(source, 'parsePrimary', lambda s: replace(s,
        '                    output.add(")\\n")\n'
        '                    if copying {\n'
        '                        setType(resultType, receiverType)\n',
        '                    output.add(")\\n")\n'
        '                    if by {\n'
        '                        state[14] = state[14] + 1\n'
        '                        if copying { recoveryOwnedCheckpoint(output, textState, state, value) } else { recoveryCheckpoint(output, textState, state) }\n'
        '                    }\n'
        '                    if copying {\n'
        '                        setType(resultType, receiverType)\n'))
    source = replace(source,
        'finishFunctionEntry(output, entry, state[4], parameters.length, state[8], state[6] == 1)',
        'finishFunctionEntry(output, entry, state[4], parameters.length, state[8], state[6] == 1, llvmType(result)' + hook_arguments + ')\n'
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
    # Only the external native call can reenter language callbacks; the
    # integer_overflow intrinsic returns earlier without calling out.
    source = edit(source, 'compileNative', lambda s: replace(s,
        '    }\n    output.add("  call void @minyar_rc_leave()\\n")\n',
        '    }\n    recoveryNativeCheckpoint(output, textState, state, returnType)\n'
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
                    'i64 @minyar_calldepth_remaining()', 'i32 @minyar_calldepth_reporting_begin()',
                    'i32 @minyar_calldepth_reporting_end()']
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
