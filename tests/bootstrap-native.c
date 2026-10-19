/* Distinct names ensure the stage0 test calls native wrappers rather than
 * one of its historical built-in io/process shortcuts. */
#include <stdbool.h>
typedef struct { const unsigned char *bytes; long long length; } TextPrefix;
extern void *minyar_native_copy_text(const unsigned char *, long long);
void *minyar_runtime_bootstrapNativeText(const TextPrefix *text) {
    return minyar_native_copy_text(text->bytes, text->length);
}
bool minyar_runtime_bootstrapNativeBoolean(bool value) { return !value; }
long long minyar_runtime_bootstrapNativeInteger(long long value) { return value; }
int minyar_runtime_bootstrapNativeCharacter(int value) { return value; }
static long long count;
void minyar_runtime_bootstrapNativeSet(long long value) { count = value; }
long long minyar_runtime_bootstrapNativeCount(void) { return count; }

/* Enter an owned native frame immediately before rejection. The explicit
 * stack probe verifies the optional stack ABI really used our live header. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
extern void minyar_rc_enter(long long);
extern void minyar_rc_local_take(long long, void *);
extern void *minyar_integer_text(long long);
extern _Noreturn void minyar_runtime_diagnosticRaise(void);
static long long recovery_calls;
long long minyar_runtime_diagnosticProbeCount(void) { return recovery_calls; }
_Noreturn void minyar_runtime_diagnosticRaiseOnStack(void) {
#ifdef MINYAR_DIAGNOSTICS_STACK_PROBE
    extern void minyar_rc_enter_stack_v1(void *, void *, long long);
    _Alignas(8) unsigned char header[64] = {0}, storage[16] = {0};
    minyar_rc_enter_stack_v1(header, storage, 1);
    void *used = NULL;
    memcpy(&used, header + sizeof(void *), sizeof used);
    if (used != storage) { fputs("stack probe did not enter its supplied header\n", stderr); exit(1); }
#else
    minyar_rc_enter(1);
#endif
    minyar_rc_local_take(0, minyar_integer_text(123));
    recovery_calls++;
    minyar_runtime_diagnosticRaise();
}
