/* Compiler diagnostics use raw stderr and best-effort source reads. Neither
 * helper runs on a successful compiler path. Source files may be unavailable
 * when a tool checks an in-memory syntax tree; keep its location and message. */
void minyar_runtime_diagnosticWrite(const MinyarText *text) {
    (void)fwrite(text->bytes, 1, (size_t)text->byte_length, stderr);
    (void)fflush(stderr);
}

MinyarText *minyar_runtime_diagnosticSource(const MinyarText *path_text) {
    char *path = text_as_path(path_text);
    FILE *file = open_text_path(path, "rb");
#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_COMPILER_ARENA)
    rc_heap_deallocate(path);
#else
    free(path);
#endif
    if (!file) return copy_c_text("");
    long long length = text_file_length(file);
    unsigned char *bytes = new_bytes(length);
    size_t received = fread(bytes, 1, (size_t)length, file);
    int closed = fclose(file);
    if (received != (size_t)length || closed != 0) return copy_c_text("");
    bytes[length] = 0;
    validate_text_bytes(bytes, length);
    return new_text(bytes, length, -1);
}

/* Compiler options live in this process only. Normal programs never query
 * them; JSON selection adds no generated program instructions. */
static _Bool minyar_diagnostic_json;
void minyar_runtime_diagnosticSetJSON(_Bool enabled) { minyar_diagnostic_json = enabled; }
_Bool minyar_runtime_diagnosticJSON(void) { return minyar_diagnostic_json; }

/* This private boundary is used by the compiler, never emitted into a user
 * program. Only an explicit diagnostic can jump here; runtime faults remain
 * fatal. Unwind ownership while callback stack storage is still live. */
#include <setjmp.h>
typedef struct MinyarDiagnosticBoundary {
    jmp_buf *jump;
    struct MinyarDiagnosticBoundary *previous;
    void *job;
    size_t depth, limit;
#ifndef MINYAR_COMPILER_ARENA
    RcFrame *frames;
#endif
} MinyarDiagnosticBoundary;
static MinyarDiagnosticBoundary *minyar_diagnostic_boundary;
static long long minyar_diagnostic_errors;

_Bool minyar_compiler_try(void (*compile)(void *), void *job) {
    jmp_buf jump;
    MinyarDiagnosticBoundary boundary = {&jump, minyar_diagnostic_boundary, job,
                                        minyar_call_depth, minyar_depth_limit
#ifndef MINYAR_COMPILER_ARENA
                                        , rc_frames
#endif
    };
    minyar_diagnostic_boundary = &boundary;
    int rejected = setjmp(jump);
    if (!rejected) compile(job);
    minyar_diagnostic_boundary = boundary.previous;
    return !rejected;
}

static MINYAR_NORETURN void minyar_diagnostic_jump(int reason) {
    MinyarDiagnosticBoundary *boundary = minyar_diagnostic_boundary;
    if (!boundary) exit(1);
#ifndef MINYAR_COMPILER_ARENA
#ifdef MINYAR_BOUNDED_RC
    if (!minyar_stack_bounds_ready) minyar_find_stack_bounds();
#endif
    while (rc_frames != boundary->frames) {
#ifdef MINYAR_BOUNDED_RC
        uintptr_t address = (uintptr_t)rc_frames;
        if (address >= minyar_stack_low && address < minyar_stack_high) {
            /* Match leave_stack_v1 without requiring that optional ABI in
             * an ordinary runtime object. The header cannot enter a queue. */
            RcFrame *frame = rc_frames;
            size_t written = frame->written_count;
            rc_frames = frame->previous;
            rc_bounded_retire_temporaries(frame);
            while (frame->written_count)
                rc_drop(rc_bounded_pending_local_value(frame, --frame->written_count));
            size_t work = written + minyar_rc_poll(MINYAR_RC_POLL_BUDGET - written);
#ifdef MINYAR_RC_TESTING
            rc_bounded_last_work = work;
#else
            (void)work;
#endif
        } else
#endif
            minyar_rc_leave();
    }
#endif
    minyar_call_depth = boundary->depth;
    minyar_depth_limit = boundary->limit;
    longjmp(*boundary->jump, reason);
}

_Bool minyar_runtime_diagnosticHasJob(void) { return minyar_diagnostic_boundary != NULL; }
void *minyar_runtime_diagnosticCurrentJob(void) {
    void *job = minyar_diagnostic_boundary ? minyar_diagnostic_boundary->job : NULL;
    minyar_rc_retain(job);
    return job;
}
long long minyar_runtime_diagnosticErrorCount(void) { return minyar_diagnostic_errors; }
MINYAR_NORETURN void minyar_runtime_diagnosticRaise(void) {
    minyar_diagnostic_errors++;
    if (minyar_diagnostic_errors >= 20) exit(1);
    minyar_diagnostic_jump(1);
}
MINYAR_NORETURN void minyar_runtime_diagnosticDiscard(void) { minyar_diagnostic_jump(2); }
