#ifndef MINYAR_TRACES_H
#define MINYAR_TRACES_H
#include <stdint.h>
#include <stdio.h>
typedef struct { int32_t rows, count; } MinyarTraceModule;
#if defined(_WIN32)
#define MINYAR_TRACE_WEAK __attribute__((weak))
#else
#define MINYAR_TRACE_WEAK __attribute__((weak, visibility("hidden")))
#endif
/* A strong generated registry replaces this inert fallback. Integer address
 * arithmetic below permits independently sized module tables at link time. */
MINYAR_TRACE_WEAK const uint64_t minyar_trace_module_count = 0;
MINYAR_TRACE_WEAK const MinyarTraceModule minyar_trace_modules[1] = {{0, 0}};

typedef struct { int32_t symbol, name, file, source, entry; int64_t line, column; } MinyarTraceRow;
typedef struct { const MinyarTraceRow *rows[12]; uintptr_t bases[12]; unsigned count; } MinyarTrace;
_Static_assert(sizeof(MinyarTraceRow) == 40 && sizeof(MinyarTraceModule) == 8,
               "LLVM runtime trace metadata layout must match");

 #include "minyar_trace_symbols.h"

static const MinyarTraceRow *minyar_trace_find(uintptr_t region, uintptr_t *base_out, int entry_only) {
    char *owned = NULL;
    const char *symbol = entry_only ? NULL : minyar_trace_symbol(region, &owned);
    uintptr_t registry = (uintptr_t)minyar_trace_modules;
    for (uint64_t module = 0; module < minyar_trace_module_count; module++) {
        const MinyarTraceModule *entry = (const void *)(registry + module * sizeof(*entry));
        uintptr_t base = registry + (uintptr_t)entry->rows;
        uint64_t count = *(const uint64_t *)(registry + (uintptr_t)entry->count);
        const MinyarTraceRow *rows = (const void *)base;
        for (uint64_t index = 0; index < count; index++) {
            if ((entry_only && rows[index].entry) || (!entry_only && symbol && minyar_trace_name_equal((const char *)(base + (uintptr_t)rows[index].symbol), symbol))) {
                *base_out = base;
                free(owned);
                return &rows[index];
            }
        }
    }
    free(owned);
    return NULL;
}

#if defined(__APPLE__) && defined(__aarch64__) && (!defined(__STDC_HOSTED__) || __STDC_HOSTED__)
#include "minyar_traces_darwin.h"
#elif !defined(_WIN32) && !defined(__wasm__) && (!defined(__STDC_HOSTED__) || __STDC_HOSTED__)
#include <unwind.h>
static _Unwind_Reason_Code minyar_trace_frame(struct _Unwind_Context *context, void *data) {
    MinyarTrace *trace = data;
    uintptr_t base = 0;
    const MinyarTraceRow *row = minyar_trace_find((uintptr_t)_Unwind_GetRegionStart(context), &base, 0);
    if (row) {
        trace->rows[trace->count] = row;
        trace->bases[trace->count++] = base;
    }
    return trace->count == 12 ? _URC_END_OF_STACK : _URC_NO_REASON;
}
#endif

#if defined(__STDC_HOSTED__) && !__STDC_HOSTED__ && (defined(__x86_64__) || defined(__aarch64__))
/* A freestanding kernel has no unwinder and no loaded symbol table. Its
 * compiler keeps frame pointers, so follow that chain (saved frame, then return
 * address, on both x86-64 and Arm64) and print raw return addresses, innermost
 * first. tools/osdev.py maps them to Minyar functions using the kernel ELF.
 * Each step must move up the stack by less than 1 MiB; anything else ends it. */
#define MINYAR_TRACE_RETURN_ADDRESSES 1
static void minyar_trace_return_addresses(int (*print)(FILE *, const char *, ...)) {
    uintptr_t frame = (uintptr_t)__builtin_frame_address(0);
    for (unsigned depth = 0; depth < 16 && frame && !(frame & 7); depth++) {
        uintptr_t next = ((const uintptr_t *)frame)[0];
        uintptr_t address = ((const uintptr_t *)frame)[1];
        if (!address) break;
        print(stderr, "  at 0x%llx\n", (unsigned long long)address);
        if (next <= frame || next - frame >= ((uintptr_t)1 << 20)) break;
        frame = next;
    }
}
#endif

__attribute__((visibility("hidden"))) MINYAR_COLD void minyar_print_stack_trace(void) {
    if (!minyar_trace_module_count) return;
    MinyarTrace trace;
    trace.count = 0;
#if defined(__APPLE__) && defined(__aarch64__) && (!defined(__STDC_HOSTED__) || __STDC_HOSTED__)
    minyar_trace_darwin(&trace, __builtin_frame_address(0));
#elif !defined(_WIN32) && !defined(__wasm__) && (!defined(__STDC_HOSTED__) || __STDC_HOSTED__)
    _Unwind_Backtrace(minyar_trace_frame, &trace);
#endif
    if (!trace.count) {
        uintptr_t base = 0;
        const MinyarTraceRow *entry = minyar_trace_find(0, &base, 1);
        if (entry) { trace.rows[0] = entry; trace.bases[0] = base; trace.count = 1; }
    }
    if (!trace.count) return;
    /* Keep the reporter on the runtime's existing fprintf binding. A local
     * volatile target prevents libcall rewriting into new startup imports. */
    int (*volatile print)(FILE *, const char *, ...) = fprintf;
    print(stderr, "Minyar stack trace:\n");
#ifdef MINYAR_TRACE_RETURN_ADDRESSES
    minyar_trace_return_addresses(print);
#endif
    for (unsigned index = 0; index < trace.count; index++) {
        const MinyarTraceRow *row = trace.rows[index];
        uintptr_t base = trace.bases[index];
        print(stderr, "  at %s (%s:%lld:%lld)\n",
              (const char *)(base + (uintptr_t)row->name),
              (const char *)(base + (uintptr_t)row->file),
              (long long)row->line, (long long)row->column);
        const char *source = (const char *)(base + (uintptr_t)row->source);
        if (*source) print(stderr, "    | %s\n", source);
    }
}

#endif
