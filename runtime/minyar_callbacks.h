/* Callback domain identities exist only in the opt-in managed graph engine.
 * Foreign calls are rejected before stack/RC/frame state is accessed. Domain
 * IDs are unique for the process lifetime, so recycled OS thread IDs cannot
 * authorize stale values. This does not make managed heaps shared. */
#include <stdatomic.h>
#include <stdint.h>
#include <stdbool.h>

static atomic_uint_fast64_t minyar_callback_next_domain = 1;
static _Thread_local uint64_t minyar_callback_current_domain;

long long minyar_callback_domain(void) {
    uint64_t domain = minyar_callback_current_domain;
    if (!domain) {
        domain = atomic_fetch_add_explicit(&minyar_callback_next_domain, 1, memory_order_relaxed);
        if (!domain || domain > INT64_MAX)
            minyar_stop("callback domain identity exhausted.");
        minyar_callback_current_domain = domain;
    }
    return (long long)domain;
}

void minyar_callback_check(const MinyarRecord *callback) {
    if (!callback || callback->length != 3 || callback->values[2] != minyar_callback_domain())
        minyar_stop("callback belongs to a different execution domain.");
}

void minyar_callback_check_environment(const MinyarRecord *environment) {
    if (!environment || environment->length < 1 ||
        environment->values[0] != minyar_callback_domain())
        minyar_stop("callback environment belongs to a different execution domain.");
}

/* An opt-in loop services bounded debt before sleeping. Returning true
 * requests an immediate empty readiness batch; no heap scan occurs here.
 * Once old work retires, the normal OS readiness wait can block again. */
bool minyar_callbackruntime_service(void) {
#ifdef MINYAR_COMPILER_ARENA
    return false;
#elif defined(MINYAR_BOUNDED_RC)
    rc_service_pending(MINYAR_RC_POLL_BUDGET);
    return rc_pending_count != 0;
#else
    rc_cycle_eager_service(32);
    return rc_cycle_pending != 0;
#endif
}

/* Borrowing an interior live node can request another epoch when that
 * transient owner drops. Draining every such new request before sleeping
 * lets an otherwise idle dispatcher perpetually restart collection.
 *
 * Finish old captured work, then yield for at most 10ms if the only debt
 * is newly requested cycle work. Keep that job queued, and cap infinite
 * waits too: a true last-owner drop still receives another cleanup batch.
 * Each call performs exactly the existing profile's service budget. */
long long minyar_callbackruntime_serviceWait(long long timeout_ms) {
    if (timeout_ms < -1 || timeout_ms > 2147483647LL)
        return timeout_ms;
#ifdef MINYAR_COMPILER_ARENA
    return timeout_ms;
#else
    static size_t completed_seen;
    bool pending = minyar_callbackruntime_service();
    unsigned completed = rc_cycle_completed != completed_seen;
    completed_seen = rc_cycle_completed;
    if (!pending)
        return timeout_ms;
    if (!rc_cycle_pending || !completed)
        return 0;
#ifdef MINYAR_BOUNDED_RC
    if (rc_pending_count != 1)
        return 0;
#endif
    return timeout_ms < 0 || timeout_ms > 10 ? 10 : timeout_ms;
#endif
}
