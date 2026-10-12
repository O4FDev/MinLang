/* TEST ONLY: exact low-cap result inspection and a cooperating native bridge. */
static long long reporting_field(MinyarRecord *record, size_t field) {
    assert(record && field < (size_t)record->length);
    return record->values[field];
}
long long minyar_reporttest_code(MinyarRecord *result) {
    return reporting_field((MinyarRecord *)(uintptr_t)reporting_field(result, 1), 0);
}
long long minyar_reporttest_value(MinyarRecord *result) {
    assert(minyar_reporttest_code(result) == 0);
    return reporting_field(result, 0);
}
long long minyar_reporttest_unknown(void) {
    minyar_stack_low = minyar_stack_high = 0;
    minyar_stack_bounds_ready = 1;
    minyar_depth_limit = MINYAR_FALLBACK_CALL_DEPTH;
    return 0;
}
long long minyar_reporttest_restore(void) {
    minyar_stack_bounds_ready = 0;
    minyar_depth_limit = 0;
    return 0;
}
static long long reporting_physical_callback(void *unused) {
    (void)unused;
    if (!minyar_recovery_enter()) return 0;
    minyar_stack_leave();
    return 99;
}
static MINYAR_NO_ADDRESS_SANITIZE __attribute__((noinline)) long long reporting_near_reserve(void) {
    volatile unsigned char storage[4096];
    storage[0] = 1;
    uintptr_t current = (uintptr_t)&storage[0];
    assert(minyar_stack_low && minyar_stack_high);
    if (current - minyar_stack_low > MINYAR_STACK_RESERVE_BYTES - 4096) {
        long long result = reporting_near_reserve();
        return result + storage[0] - 1; /* Retain the real native frames at O2. */
    }
    struct { long long length; long long fields[3]; } callback =
        {3, {(long long)(uintptr_t)reporting_physical_callback, 0, minyar_callback_domain()}};
    MinyarRecord *result = depth_test_run(100, (MinyarRecord *)&callback);
    if (result) minyar_rc_release(result);
    /* No dummy/result projection after a cooperating failed native entry. */
    return 0;
}
long long minyar_reporttest_physical(void) {
    assert(depth_test_run && minyar_depth_scope);
    return reporting_near_reserve();
}
