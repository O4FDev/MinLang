/* Cooperative recovery is selected by generated language code. Ordinary
 * minyar_stack_enter remains unchanged. No jump crosses an ownership frame. */
typedef struct MinyarDepthScope {
    struct MinyarDepthScope *previous;
    size_t ceiling;
    int failed;
} MinyarDepthScope;
_Static_assert(sizeof(MinyarDepthScope) <= 32, "generated depth scope storage");
static MINYAR_THREAD_LOCAL MinyarDepthScope *minyar_depth_scope;
static MINYAR_THREAD_LOCAL size_t minyar_depth_reporting;

void minyar_calldepth_begin(void *storage, long long limit) {
    MinyarDepthScope *scope = storage;
    scope->previous = minyar_depth_scope;
    size_t allowance = limit > 0 ? (size_t)limit : 0;
    size_t available = MINYAR_MAX_CALL_DEPTH - minyar_call_depth;
    if (allowance > available) allowance = available;
    scope->ceiling = minyar_call_depth + allowance;
    if (scope->previous && scope->previous->ceiling < scope->ceiling)
        scope->ceiling = scope->previous->ceiling;
    scope->failed = 0;
    minyar_depth_scope = scope;
}

int minyar_calldepth_end(void *storage) {
    MinyarDepthScope *scope = storage;
    if (scope != minyar_depth_scope)
        minyar_stop("the runtime detected an unbalanced call-depth scope.");
    int failed = scope->failed;
    minyar_depth_scope = scope->previous;
    return failed;
}

long long minyar_calldepth_remaining(void) {
    if (!minyar_depth_scope) return -1;
    if (minyar_depth_scope->failed || minyar_call_depth >= minyar_depth_scope->ceiling)
        return 0;
    return (long long)(minyar_depth_scope->ceiling - minyar_call_depth);
}

int minyar_recovery_pending(void) {
    return !minyar_depth_reporting && minyar_depth_scope && minyar_depth_scope->failed;
}

/* Result factories run with logical counting suspended, after scope restore.
 * Their native guards remain active and their ownership cleanup is ordinary. */
void minyar_calldepth_reporting_begin(void) { minyar_depth_reporting++; }
void minyar_calldepth_reporting_end(void) {
    if (!minyar_depth_reporting)
        minyar_stop("the runtime detected unbalanced call-depth reporting.");
    minyar_depth_reporting--;
}

static MINYAR_COLD int minyar_recovery_enter_slow(uintptr_t current) {
    if (!minyar_stack_bounds_ready) minyar_find_stack_bounds();
    return minyar_call_depth < MINYAR_MAX_CALL_DEPTH &&
        ((minyar_stack_low && minyar_stack_high) ||
         minyar_call_depth < MINYAR_FALLBACK_CALL_DEPTH) &&
        !(current >= minyar_stack_low && current < minyar_stack_high &&
          current - minyar_stack_low <= MINYAR_STACK_RESERVE_BYTES);
}

MINYAR_NO_ADDRESS_SANITIZE int minyar_recovery_enter(void) {
    if (!minyar_depth_scope || minyar_depth_reporting) {
        minyar_stack_enter();
        return 1;
    }
    unsigned char stack_marker;
    uintptr_t current = (uintptr_t)&stack_marker;
    if (minyar_depth_scope->failed || minyar_call_depth >= minyar_depth_scope->ceiling ||
        ((minyar_call_depth >= minyar_depth_limit ||
          current - minyar_stack_low <= MINYAR_STACK_RESERVE_BYTES) &&
         !minyar_recovery_enter_slow(current))) {
        minyar_depth_scope->failed = 1;
        return 0;
    }
    minyar_call_depth++;
    return 1;
}
