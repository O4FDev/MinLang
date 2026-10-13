#ifdef __APPLE__
#define DEPTH_SYMBOL(name) "_" name
#else
#define DEPTH_SYMBOL(name) name
#endif
extern MinyarText *depth_test_language(void)
    __asm__(DEPTH_SYMBOL(".minyar.fn.minyar_module_0_deepNative")) __attribute__((weak));
MinyarText *minyar_depthtest_bounce(void) {
    assert(depth_test_language);
    MinyarText *value = depth_test_language();
    if (value) minyar_rc_release(value);
    return minyar_integer_text(42);
}
extern MinyarRecord *depth_test_run(long long, MinyarRecord *)
    __asm__(DEPTH_SYMBOL(".minyar.fn.minyar_module_1_run")) __attribute__((weak));
#ifdef __APPLE__
MinyarText *depth_test_language(void) { abort(); }
MinyarRecord *depth_test_run(long long depth, MinyarRecord *callback) {
    (void)depth; (void)callback; abort();
}
#endif
static MinyarDepthScope *depth_expected_scope;
static size_t depth_expected_count;
static void depth_domain_exit(void) {
    assert(minyar_depth_scope == depth_expected_scope);
    assert(minyar_call_depth == depth_expected_count);
    assert(minyar_depth_reporting == 0);
    puts("domain checked before depth state");
}
long long minyar_depthtest_foreign(void) {
    assert(depth_test_run);
    struct { long long length; long long fields[3]; } storage =
        { 3, { 0, 0, minyar_callback_domain() + 1 } };
    MinyarRecord *callback = (MinyarRecord *)&storage;
    depth_expected_scope = minyar_depth_scope;
    depth_expected_count = minyar_call_depth;
    assert(atexit(depth_domain_exit) == 0);
    (void)depth_test_run(0, callback);
    abort();
}
__attribute__((destructor)) static void depth_exit_contract(void) {
    if (contract_explicit_exit) return;
    assert(minyar_call_depth == 0);
    assert(minyar_depth_scope == NULL);
    assert(minyar_depth_reporting == 0);
}
