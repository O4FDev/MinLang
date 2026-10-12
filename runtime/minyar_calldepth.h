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
/* Reporting has a finite emergency allowance, independent of logical caps.
 * Physical guards still apply. A failed report unwinds to an enclosing scope;
 * an escaped failure remains observable by the native entry owner. */
#define MINYAR_DEPTH_REPORT_FRAMES 32u
#define MINYAR_DEPTH_REPORT_RESERVE_BYTES (64u * 1024u)
static MINYAR_THREAD_LOCAL size_t minyar_depth_report_base;
static MINYAR_THREAD_LOCAL MinyarDepthScope *minyar_depth_report_parent;
static MINYAR_THREAD_LOCAL int minyar_depth_report_failed, minyar_depth_escaped;

static void minyar_depth_propagate(void) {
    if (minyar_depth_reporting) minyar_depth_report_failed = 1;
    else if (minyar_depth_scope) minyar_depth_scope->failed = 1;
    else minyar_depth_escaped = 1;
}

void minyar_calldepth_begin(void *storage, long long limit) {
    MinyarDepthScope *scope = storage;
    scope->previous = minyar_depth_scope;
    size_t allowance = limit > 0 ? (size_t)limit : 0;
    size_t available = minyar_call_depth < MINYAR_MAX_CALL_DEPTH ?
        MINYAR_MAX_CALL_DEPTH - minyar_call_depth : 0;
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
    if (minyar_depth_reporting)
        return minyar_depth_report_failed ||
            (minyar_depth_scope != minyar_depth_report_parent &&
             minyar_depth_scope && minyar_depth_scope->failed);
    return minyar_depth_escaped || (minyar_depth_scope && minyar_depth_scope->failed);
}

static int minyar_depth_physical_room(uintptr_t current, size_t reserve) {
    if (!minyar_stack_bounds_ready) minyar_find_stack_bounds();
    return !(current >= minyar_stack_low && current < minyar_stack_high &&
             current - minyar_stack_low <= reserve);
}

/* Preflight the complete factory allowance, rather than entering the first
 * factory and trapping at a later global/fallback/physical guard. */
MINYAR_NO_ADDRESS_SANITIZE int minyar_calldepth_reporting_begin(void) {
    unsigned char marker;
    if (minyar_depth_reporting >= MINYAR_DEPTH_REPORT_FRAMES ||
        minyar_depth_report_failed || minyar_depth_escaped ||
        !minyar_depth_physical_room((uintptr_t)&marker,
            MINYAR_STACK_RESERVE_BYTES + MINYAR_DEPTH_REPORT_RESERVE_BYTES)) {
        minyar_depth_propagate();
        return 0;
    }
    if (!minyar_depth_reporting) {
        minyar_depth_report_base = minyar_call_depth;
        minyar_depth_report_parent = minyar_depth_scope;
    }
    minyar_depth_reporting++;
    return 1;
}
int minyar_calldepth_reporting_end(void) {
    if (!minyar_depth_reporting)
        minyar_stop("the runtime detected unbalanced call-depth reporting.");
    if (minyar_depth_reporting == 1 && minyar_call_depth != minyar_depth_report_base)
        minyar_stop("the runtime detected an unbalanced reporting return.");
    minyar_depth_reporting--;
    int failed = minyar_depth_report_failed;
    if (!minyar_depth_reporting) {
        minyar_depth_report_base = 0;
        minyar_depth_report_parent = NULL;
        minyar_depth_report_failed = 0;
        if (failed) minyar_depth_propagate();
    }
    return failed;
}

static MINYAR_COLD int minyar_recovery_enter_slow(uintptr_t current) {
    if (!minyar_stack_bounds_ready) minyar_find_stack_bounds();
    return minyar_call_depth < MINYAR_MAX_CALL_DEPTH &&
        ((minyar_stack_low && minyar_stack_high) ||
         minyar_call_depth < MINYAR_FALLBACK_CALL_DEPTH) &&
        !(current >= minyar_stack_low && current < minyar_stack_high &&
          current - minyar_stack_low <= MINYAR_STACK_RESERVE_BYTES + MINYAR_DEPTH_REPORT_RESERVE_BYTES);
}

MINYAR_NO_ADDRESS_SANITIZE int minyar_recovery_enter(void) {
    if (minyar_depth_escaped) return 0;
    if (!minyar_depth_scope && !minyar_depth_reporting) {
        minyar_stack_enter();
        return 1;
    }
    unsigned char stack_marker;
    uintptr_t current = (uintptr_t)&stack_marker;
    if (minyar_depth_reporting) {
        if (minyar_depth_report_failed || minyar_call_depth == SIZE_MAX ||
            minyar_call_depth - minyar_depth_report_base >= MINYAR_DEPTH_REPORT_FRAMES ||
            !minyar_depth_physical_room(current, MINYAR_STACK_RESERVE_BYTES)) {
            minyar_depth_report_failed = 1;
            return 0;
        }
        /* The ambient exhausted scope is suspended only for its factories.
         * A new run started by a factory must still obey its own limit. */
        if (minyar_depth_scope && minyar_depth_scope != minyar_depth_report_parent &&
            (minyar_depth_scope->failed || minyar_call_depth >= minyar_depth_scope->ceiling)) {
            minyar_depth_scope->failed = 1;
            return 0;
        }
        minyar_call_depth++;
        return 1;
    }
    if (minyar_depth_scope->failed || minyar_call_depth >= minyar_depth_scope->ceiling ||
        ((minyar_call_depth >= minyar_depth_limit ||
          current - minyar_stack_low <= MINYAR_STACK_RESERVE_BYTES + MINYAR_DEPTH_REPORT_RESERVE_BYTES) &&
         !minyar_recovery_enter_slow(current))) {
        minyar_depth_scope->failed = 1;
        return 0;
    }
    minyar_call_depth++;
    return 1;
}
