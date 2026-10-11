#!/usr/bin/env python3
"""Actual AppKit/kqueue integration, in native and ASan/UBSan builds."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if sys.platform != 'darwin':
    raise SystemExit('this mandatory macOS gate requires AppKit and kqueue')
(ROOT/'build').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='macos-network-', dir=ROOT/'build') as directory:
    temp = Path(directory)
    clang = os.environ.get('MINYAR_TEST_CLANG', 'clang')
    for sanitized in (False, True):
        mode = 'sanitize' if sanitized else 'native'
        flags = ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if sanitized else ['-O2']
        runtime, net, executable = temp/(mode+'-runtime.o'), temp/(mode+'-net.o'), temp/mode
        subprocess.run([clang, *flags, '-DMINYAR_SYSTEM_HEAP=1', '-c',
                        ROOT/'runtime/minyar_runtime.c', '-o', runtime], check=True)
        subprocess.run([clang, '-std=c11', '-Wall', '-Wextra', '-Werror', *flags,
                        '-DMINYAR_APP_EVENT_LOOP=1', '-c', ROOT/'runtime/native/net.c', '-o', net], check=True)
        subprocess.run([clang, '-fobjc-arc', '-fmodules', '-Wall', '-Wextra', '-Werror', *flags,
                        '-DMINYAR_APP_EVENT_LOOP=1', ROOT/'tests/macos-network.m', runtime, net,
                        '-framework', 'AppKit', '-o', executable], check=True)
        subprocess.run([executable], check=True, timeout=30,
                       env=dict(os.environ, ASAN_OPTIONS='detect_leaks=0', UBSAN_OPTIONS='halt_on_error=1'))
    # The public launcher must select matching desktop/reactor cache variants;
    # direct native tests alone cannot detect a missing compile-time adapter.
    source = temp/'contract.min'
    source.write_text('''use "macos" as macos
use "eventloop" as loop
use "errors" as errors
macos.initialize("shared loop contract")
macos.accessory(true)
let reactor = errors.integerValue(loop.create())
let shared = macos.shareNetworkLoop(reactor)
print(errors.integerOk(shared))
let timer = errors.integerValue(loop.timer(reactor, 10, 0, 77))
macos.nextEvent(0.5)
let batch = loop.wait(reactor, 0, 16)
print(!errors.isError(loop.batchError(batch)))
print(loop.events(batch).length == 1)
print(loop.events(batch)[0].token == 77)
print(errors.booleanOk(loop.close(reactor)))
''')
    for mode in ['--debug', '--release']:
        executable = temp/('contract-'+mode[2:])
        subprocess.run([ROOT/'minyar', mode, source, '-o', executable], check=True, timeout=120)
        result = subprocess.run([executable], check=True, capture_output=True, text=True, timeout=15)
        assert result.stdout == 'true\ntrue\ntrue\ntrue\ntrue\n', result

    # No socket/timer/managed callback may be required to retire an abandoned
    # capture graph. These C loops never insert compiler RC service points, so
    # progress comes only from the actual AppKit wait being tested.
    sys.path.insert(0, str(ROOT/'tools'))
    from cycle_runtime import engine_source
    engine = engine_source(ROOT)
    helpers = r'''
long long minyar_idle_pending(void) {
    return (long long)(rc_pending_count + rc_cycle_pending);
}
long long minyar_idle_objects(void) {
    return (long long)(rc_object_count - rc_immortal_object_count);
}
long long minyar_idle_units(void) { return (long long)rc_cycle_units; }
void minyar_idle_capture_graph(void) {
    enum { COUNT = 1024 };
    MinyarRecord *nodes[COUNT];
    for (unsigned i = 0; i < COUNT; i++)
        nodes[i] = minyar_record_new_traced(1);
    for (unsigned i = 0; i + 1 < COUNT; i++)
        minyar_record_set_reference_traced(nodes[i], 0, (long long)(uintptr_t)nodes[i+1]);
    /* The closure owns its captured environment; the environment retains the
     * first node. This is the runtime's actual three-word callback layout. */
    MinyarRecord *environment = minyar_record_new_traced(2);
    minyar_record_set_scalar(environment, 0, minyar_callback_domain());
    minyar_record_set_reference_traced(environment, 1, (long long)(uintptr_t)nodes[0]);
    MinyarRecord *callback = minyar_record_new_traced(3);
    minyar_record_set_scalar(callback, 0, 0); /* Never invoked. */
    minyar_record_set_reference_traced(callback, 1, (long long)(uintptr_t)environment);
    minyar_record_set_scalar(callback, 2, minyar_callback_domain());
    minyar_record_set_reference_traced(nodes[COUNT-1], 0, (long long)(uintptr_t)callback);
    minyar_rc_release(environment);
    minyar_rc_release(callback);
    for (unsigned i = 0; i < COUNT; i++)
        minyar_rc_release(nodes[i]);
}
'''
    fixture = temp/'idle.m'
    fixture.write_text('#include "' + str(ROOT/'runtime/native/macos.m') + '"\n' + r'''
#include <assert.h>
#include <time.h>
extern long long minyar_idle_pending(void);
extern long long minyar_idle_objects(void);
extern long long minyar_idle_units(void);
extern void minyar_idle_capture_graph(void);
static double idle_now(void) {
    struct timespec now;
    assert(!clock_gettime(CLOCK_MONOTONIC, &now));
    return now.tv_sec + now.tv_nsec / 1.0e9;
}
static void idle_native_drain(void) {
    while ([NSApp nextEventMatchingMask:NSEventMaskAny untilDate:NSDate.distantPast
            inMode:NSDefaultRunLoopMode dequeue:YES]) {}
}
int main(void) { @autoreleasepool {
    MinyarText name={(const unsigned char *)"Minyar idle captures",20,-1,NULL,NULL};
    minyar_macos_initialize(&name);
    assert(minyar_macos_accessory(true));
    idle_native_drain();
    long long baseline = minyar_idle_objects();
    minyar_idle_capture_graph();
    assert(minyar_idle_pending() && minyar_idle_objects() > baseline);
    long long before = minyar_idle_units();
    double start = idle_now();
    assert(minyar_macos_nextEvent(.4));
    assert(idle_now() - start < .2);
    assert(minyar_idle_units() > before);
    assert(minyar_idle_units() - before <= IDLE_BUDGET);
    unsigned batches = 0;
    while (minyar_idle_pending()) {
        before = minyar_idle_units();
        start = idle_now();
        assert(minyar_macos_nextEvent(.4));
        if (minyar_idle_pending()) assert(idle_now() - start < .2);
        assert(minyar_idle_units() - before <= IDLE_BUDGET);
        assert(++batches < 20000);
    }
    assert(minyar_idle_objects() == baseline);
    idle_native_drain();
    start = idle_now();
    assert(minyar_macos_nextEvent(.1));
    assert(idle_now() - start >= .05);
    puts("AppKit reclaims idle captured cycles in bounded batches, then sleeps");
} return 0; }
''')
    for sanitized in (False, True):
        for budget in (1, 32):
            label = ('sanitize' if sanitized else 'native')+'-idle-'+str(budget)
            flags = ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if sanitized else ['-O2']
            runtime_source = temp/(label+'-runtime.c')
            runtime_source.write_text('#define MINYAR_RC_TESTING 1\n#define MINYAR_INTEGER_TEXT_CACHE_LIMIT 0\n'+engine+helpers)
            runtime = temp/(label+'-runtime.o')
            executable = temp/label
            subprocess.run([clang, *flags, '-DMINYAR_SYSTEM_HEAP=1',
                            '-DMINYAR_RC_POLL_BUDGET='+str(budget), '-iquote', ROOT/'runtime',
                            '-c', runtime_source, '-o', runtime], check=True)
            subprocess.run([clang, '-fobjc-arc', '-fmodules', '-Wall', '-Wextra', '-Werror',
                            *flags, '-DMINYAR_APP_MANAGED_CLEANUP=1', '-DIDLE_BUDGET='+str(budget),
                            fixture, runtime, '-framework', 'AppKit', '-o', executable], check=True)
            subprocess.run([executable], check=True, timeout=30,
                           env=dict(os.environ, ASAN_OPTIONS='detect_leaks=0', UBSAN_OPTIONS='halt_on_error=1'))
