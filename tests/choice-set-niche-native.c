/* TEST ONLY: appended to the ownership runtime in the same translation unit.
 * These nominal Maybe<Set<Integer>> natives use an owned Set header or NULL,
 * never an interior bucket pointer or the former tagged choice wrapper. */
#if defined(MINYAR_COMPILER_ARENA) || !defined(MINYAR_MAP_CYCLE_RUNTIME) || !defined(MINYAR_RC_TESTING)
#error Set ownership contracts require the instrumented managed cycle runtime
#endif
#if MINYAR_INTEGER_TEXT_CACHE_LIMIT != 0 || !defined(MINYAR_MEMORY_CONTRACT_CUSTOM_CLEANUP)
#error Set ownership contracts require exact cleanup with Integer Text caching disabled
#endif

static void choice_set_header(const MinyarRecord *value) {
    if (!value) return;
    assert((((RcObject *)value - 1)->ownership & 7) == RC_RECORD);
    assert(value->length == MAP_FIELDS);
    assert(value->values[MAP_KEY_KIND] == 1);
    assert(value->values[MAP_VALUE_REFERENCES] == 0);
    for (unsigned field = MAP_HASHES; field <= MAP_VALUES; ++field)
        assert(map_array(value, field) != NULL);
}

MinyarRecord *minyar_choice_set_nativeOptional(long long mode) {
    assert(mode >= 0 && mode <= 2);
    if (!mode) return NULL;
    MinyarRecord *value = minyar_map_new(1, 0);
    if (mode == 2) minyar_map_set(value, 42, 1);
    choice_set_header(value);
    assert(value->values[MAP_LENGTH] == (mode == 2));
    return value; /* Transfer the constructor's one owned result. */
}

MinyarRecord *minyar_choice_set_nativeIdentity(MinyarRecord *value) {
    choice_set_header(value);
    minyar_rc_retain(value); /* The input is borrowed; return one owned alias. */
    return value;
}

_Bool minyar_choice_set_nativeSame(MinyarRecord *left, MinyarRecord *right) {
    choice_set_header(left);
    choice_set_header(right);
    return left == right;
}

__attribute__((destructor)) static void choice_set_exact_cleanup(void) {
    if (contract_explicit_exit) return;
    assert(rc_frames == NULL);
    size_t polls = 0;
#ifdef MINYAR_BOUNDED_RC
    while (rc_pending_count || rc_cycle_pending) {
        assert(++polls < 1000000);
        assert(minyar_rc_poll(MINYAR_RC_POLL_BUDGET) > 0);
    }
#else
    while (rc_cycle_pending) {
        assert(++polls < 1000000);
        rc_cycle_eager_service(1);
    }
#endif
    assert(rc_pending_count == 0 && rc_cycle_pending == 0);
    assert(rc_immortal_object_count == 0 && rc_object_count == 0 && rc_bytes == 0);
}
