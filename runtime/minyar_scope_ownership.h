/* Normal cleanup is emitted at lexical lifetime boundaries. This chain exists
 * only so a compiler diagnostic can release live cells before longjmp. */
#ifdef MINYAR_COMPILER_ARENA
void minyar_rc_scope_enter_v1(void *header, void *values, long long count) {
    (void)header; (void)values; (void)count;
}
void minyar_rc_scope_leave_v1(void *header) { (void)header; }
void minyar_rc_scope_move_v1(void *slot, void *value) { (void)slot; (void)value; }
void minyar_rc_scope_poll_v1(void) {}
void minyar_rc_scope_release_v1(void *value) { (void)value; }
#else
void minyar_rc_scope_enter_v1(void *header, void *values, long long count) {
    MinyarRcScope *scope = header;
    scope->previous = rc_scopes;
    scope->values = values;
    scope->count = (size_t)count;
    rc_scopes = scope;
}

void minyar_rc_scope_poll_v1(void) {
#ifdef MINYAR_BOUNDED_RC
    rc_service_pending(MINYAR_RC_POLL_BUDGET);
#elif defined(MINYAR_CYCLE_LOCAL_PROOFS)
    rc_cycle_eager_service(32);
#endif
}

void minyar_rc_scope_leave_v1(void *header) {
    MinyarRcScope *scope = header;
#ifdef MINYAR_RC_TESTING
    if (rc_scopes != scope) minyar_stop("ownership scopes were left out of order.");
    for (size_t index = 0; index < scope->count; index++)
        if (scope->values[index]) minyar_stop("an ownership scope has a live cell at return.");
#endif
    rc_scopes = scope->previous;
#if defined(MINYAR_CYCLE_LOCAL_PROOFS) && !defined(MINYAR_BOUNDED_RC)
    if (!rc_scopes && !rc_frames) rc_cycle_eager_service(SIZE_MAX);
#endif
}

/* A parameter can still borrow its caller's count when its binding is first
 * consumed. An empty local owner cell must give that consumer a fresh count. */
MINYAR_INLINE_ENTRY void minyar_rc_scope_move_v1(void *slot, void *value) {
    void **cell = slot;
    void *previous = *cell;
    *cell = NULL;
    if (!previous) minyar_rc_retain(value);
}

/* A null scope cell is not the native client's explicit drain request. */
MINYAR_INLINE_ENTRY void minyar_rc_scope_release_v1(void *value) {
    if (value) minyar_rc_release(value);
}

static void rc_scope_unwind(MinyarRcScope *boundary) {
    while (rc_scopes != boundary) {
        MinyarRcScope *scope = rc_scopes;
        for (size_t index = scope->count; index; index--) {
            void *value = scope->values[index - 1];
            scope->values[index - 1] = NULL;
            minyar_rc_scope_release_v1(value);
        }
        minyar_rc_scope_leave_v1(scope);
    }
}
#endif
