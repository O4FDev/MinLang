/* Only included in the numeric thread profile, after the common engine. */
static inline void rc_thread_domain_init(void) {
    /* A managed worker always begins on a fresh native thread. Never reset an
     * existing domain's live ownership/collector state to simulate isolation. */
    if (rc_frames || rc_free_frames || rc_pending_count)
        minyar_stop("a thread domain was already initialized.");
}

static inline void rc_thread_domain_drain(void) {
#ifdef MINYAR_BOUNDED_RC
    while (rc_pending_count) minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
#else
    minyar_rc_release(NULL);
#endif
}

static inline void rc_thread_domain_dispose(void) {
    if (rc_frames) minyar_stop("a thread returned with live ownership frames.");
    /* Retired frames, dead aggregate fields and view backings can still name
     * immortal integer cache headers. Finish that debt while caches are live. */
    rc_thread_domain_drain();
    integer_text_cached(0, 1);
    rc_thread_domain_drain();
    while (rc_free_frames) {
        RcFrame *frame = rc_free_frames;
        rc_free_frames = frame->previous;
#ifdef MINYAR_BOUNDED_RC
        rc_heap_deallocate(frame->locals);
        rc_heap_deallocate(frame);
#else
        free(frame->locals);
        free(frame->temporaries);
        free(frame);
#endif
    }
#ifdef MINYAR_BOUNDED_RC
    rc_bounded_cached_frame_bytes = 0;
#else
    free(rc_pending);
    rc_pending = NULL;
    rc_pending_capacity = 0;
#endif
#ifdef MINYAR_CYCLE_LOCAL_PROOFS
    if (rc_cycle_head || rc_cycle_known_head || rc_cycle_pending)
        minyar_stop("a thread returned with live collector roots.");
#endif
#ifdef MINYAR_RC_TESTING
    if (rc_object_count || rc_bytes || rc_immortal_object_count)
        minyar_stop("a thread leaked local managed allocations.");
#ifdef MINYAR_BOUNDED_RC
    if (rc_heap_allocation_count)
        minyar_stop("a thread leaked local frame allocations.");
#endif
#endif
}

MinyarText *minyar_thread_text_literal(const MinyarText *literal) {
    /* Read only the immutable prefix of a compiler literal. Never touch its
     * shared lazy character indexes or manufacture an owning static buffer. */
    return minyar_native_copy_text(literal->bytes, literal->byte_length);
}
