/* Experimental compiler-private ABI, not a source-language feature.
 * Supplied storage is live and aligned through the paired leave. The compiler
 * must separately prove placement/lifetime (including after optimization).
 * Never pass a stack header or owner table to a deferred queue or cache. */
#ifndef MINYAR_STACK_FRAMES_V1
#define MINYAR_STACK_FRAMES_V1 1

#ifdef MINYAR_COMPILER_ARENA
void minyar_rc_enter_stack_v1(void *header, void *storage, long long locals) {
    (void)header; (void)storage; (void)locals;
}
void minyar_rc_leave_stack_v1(void *header) { (void)header; }
#else

#ifdef MINYAR_BOUNDED_RC
_Static_assert(sizeof(RcFrame) == 64 && _Alignof(RcFrame) <= 8,
               "stack ownership ABI v1 requires an aligned 64-byte header");
_Static_assert(sizeof(void *) == 8 && sizeof(size_t) == 8,
               "stack ownership ABI v1 requires 16 bytes per owner slot");
#endif

void minyar_rc_enter_stack_v1(void *header, void *storage, long long locals) {
#ifdef MINYAR_BOUNDED_RC
    /* N<K reserves at least one queued-work unit at leave. Runtime budget
     * selection is independent of the compiler. Rejected cases get exactly
     * the original enter, including its one entry poll. */
    if (locals > 0 && locals <= 8 &&
        (unsigned long long)locals < MINYAR_RC_POLL_BUDGET) {
        minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
        RcFrame *frame = header;
        frame->previous = rc_frames;
        frame->locals = storage;
        frame->local_count = frame->local_capacity = (size_t)locals;
        frame->temporary_head = frame->temporary_tail = NULL;
        frame->temporary_count = frame->written_count = 0;
        memset(frame->locals, 0, (size_t)locals * sizeof(*frame->locals));
        rc_frames = frame;
        return;
    }
#else
    (void)header; (void)storage;
#endif
    minyar_rc_enter(locals);
}

void minyar_rc_leave_stack_v1(void *header) {
#ifdef MINYAR_BOUNDED_RC
    RcFrame *frame = rc_frames;
    if (frame == header) {
        size_t written = frame->written_count;
        rc_frames = frame->previous;
        /* Heap chunks have no parent-frame pointer and detach in O(1). */
        rc_bounded_retire_temporaries(frame);
        while (frame->written_count)
            rc_drop(rc_bounded_pending_local_value(frame, --frame->written_count));
        /* Count visits, even null/immortal/shared ones. rc_drop's result is
         * not a visit count. Public release here would poll repeatedly. */
        size_t work = written + minyar_rc_poll(MINYAR_RC_POLL_BUDGET - written);
#ifdef MINYAR_RC_TESTING
        rc_bounded_last_work = work;
#else
        (void)work;
#endif
        return;
    }
#else
    (void)header;
#endif
    /* The matching enter chose the ordinary heap-backed representation. */
    minyar_rc_leave();
}
#endif
#endif
