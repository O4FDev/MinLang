/* Contained failure boundary (library "boundary"). boundary.run(body) runs
 * body; when a program error stops it (fail, unwrap, a position outside a
 * List/Text/Bytes, Integer overflow or division, invalid UTF-8 in
 * decodeOrStop, ...), the stop becomes an error value at the boundary instead
 * of ending the process.
 *
 * Generated code owns the jump: it calls _setjmp on the storage that
 * minyar_boundary_begin returns, then calls body. A contained stop releases
 * every ownership frame and scope cell above the boundary, as their normal
 * exits would, restores the thread's call-depth state and jumps back. Nothing
 * else is rolled back: completed side effects stay, and values that were only
 * in registers when the failure happened are leaked (never freed early).
 *
 * A stop is contained only when every structure it could leave half-changed
 * belongs to Minyar code: the failure site checks before it mutates, and no
 * runtime C code is running Minyar code it called (a Map's record key
 * callbacks, a sort comparator), no calldepth report is in progress and no
 * parallel worker or child thread started inside the boundary is running.
 * Anything else, and every runtime invariant failure, out-of-memory and
 * native-library stop, still ends the process. */
#if defined(__STDC_HOSTED__) && __STDC_HOSTED__ && !defined(MINYAR_COMPILER_ARENA) && \
    !defined(_WIN32) && !defined(__wasm__)
#define MINYAR_BOUNDARY_SUPPORTED 1
typedef struct MinyarBoundary {
    jmp_buf jump; /* first: generated code passes the storage itself to _setjmp */
    struct MinyarBoundary *previous;
    RcFrame *frames;
    MinyarRcScope *scopes;
    size_t depth, limit, callers, reporting;
    MinyarDepthScope *depth_scope;
    int depth_escaped;
    MinyarMapReadGuard *map_reads;
#if MINYAR_THREADED
    RcManagedThread *children;
#endif
    size_t message_length;
    char message[400];
} MinyarBoundary;
/* Generated code reserves 1024 bytes, 16-aligned. */
_Static_assert(sizeof(MinyarBoundary) <= 1024 && _Alignof(MinyarBoundary) <= 16,
               "boundary storage must fit the generated reservation");
static MINYAR_THREAD_LOCAL MinyarBoundary *minyar_boundary_top;

void *minyar_boundary_begin(void *storage) {
    MinyarBoundary *boundary = storage;
    boundary->previous = minyar_boundary_top;
    boundary->frames = rc_frames;
    boundary->scopes = rc_scopes;
    boundary->depth = minyar_call_depth;
    boundary->limit = minyar_depth_limit;
    boundary->callers = minyar_runtime_callers;
    boundary->reporting = minyar_depth_reporting;
    boundary->depth_scope = minyar_depth_scope;
    boundary->depth_escaped = minyar_depth_escaped;
    boundary->map_reads = map_active_reads;
#if MINYAR_THREADED
    boundary->children = rc_thread_children;
#endif
    boundary->message_length = 0;
    minyar_boundary_top = boundary;
    return boundary;
}

void minyar_boundary_end(void *storage) {
    if (minyar_boundary_top != storage)
        minyar_stop("the runtime detected an unbalanced failure boundary.");
    minyar_boundary_top = minyar_boundary_top->previous;
}

/* After a contained stop: leave the boundary and return its message. */
MinyarText *minyar_boundary_failure(void *storage) {
    MinyarBoundary *boundary = storage;
    minyar_boundary_end(storage);
    return minyar_native_copy_text((const unsigned char *)boundary->message,
                                   (long long)boundary->message_length);
}

static void minyar_stop_contained(const char *message, size_t length) {
    MinyarBoundary *boundary = minyar_boundary_top;
    if (!boundary || minyar_parallel_active || minyar_runtime_callers != boundary->callers ||
        minyar_depth_reporting != boundary->reporting || map_active_reads != boundary->map_reads)
        return;
#if MINYAR_THREADED
    if (rc_thread_children != boundary->children) return;
#endif
    /* Keep whole UTF-8 characters when the message is shortened. */
    if (length > sizeof(boundary->message)) {
        length = sizeof(boundary->message);
        while (length && ((unsigned char)message[length] & 0xc0) == 0x80) length--;
    }
    memcpy(boundary->message, message, length);
    boundary->message_length = length;
    minyar_unwind_ownership(boundary->frames, boundary->scopes);
    /* An omitted empty scope has no header for the unwind walk to leave. */
    minyar_rc_scope_leave_empty_v1();
    minyar_call_depth = boundary->depth;
    minyar_depth_limit = boundary->limit;
    minyar_depth_scope = boundary->depth_scope;
    minyar_depth_escaped = boundary->depth_escaped;
    longjmp(boundary->jump, 1);
}
#else
/* Freestanding, WebAssembly and Windows programs have no contained stops:
 * boundary.run calls its body directly and every stop ends the program. */
void *minyar_boundary_begin(void *storage) {
    (void)storage;
    return NULL;
}
void minyar_boundary_end(void *storage) { (void)storage; }
MinyarText *minyar_boundary_failure(void *storage) {
    (void)storage;
    minyar_stop("the runtime detected a failure boundary without support.");
}
static void minyar_stop_contained(const char *message, size_t length) {
    (void)message;
    (void)length;
    (void)minyar_runtime_callers;
}
#endif

/* boundary.run's success value. A Result is immutable, so one immortal value per
 * thread serves every run that does not stop and such a run allocates nothing.
 * Threaded programs build it each time (thread domains account for their
 * objects at exit). */
void *minyar_boundary_success(void *(*factory)(void)) {
#if !MINYAR_THREADED && !defined(MINYAR_COMPILER_ARENA)
    static MINYAR_THREAD_LOCAL void *success;
    if (!success) {
        success = factory();
        ((RcObject *)success - 1)->ownership &= 7;
        RC_ACCOUNT(rc_immortal_object_count++);
    }
    return success;
#else
    return factory();
#endif
}

/* Native libraries that call Minyar code bracket the call with these, so a
 * failure boundary never jumps across their C frames. */
void minyar_runtime_callers_enter(void) { minyar_runtime_callers++; }
void minyar_runtime_callers_leave(void) { minyar_runtime_callers--; }

/* A program error: contained by an enclosing boundary when it is safe,
 * otherwise the usual stop with its message and stack trace. */
static MINYAR_COLD MINYAR_NORETURN void minyar_stop_program(const char *message) {
    minyar_stop_contained(message, strlen(message));
    minyar_stop(message);
}
