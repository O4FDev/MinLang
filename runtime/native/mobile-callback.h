#ifndef MINYAR_MOBILE_CALLBACK_H
#define MINYAR_MOBILE_CALLBACK_H
#include <stdint.h>

/* Private bridge for Session { callback: (Integer) -> Nothing }. Read records
 * through runtime accessors so the native bridge does not assume their layout.
 * The blocking run call borrows Session. Each dispatch additionally owns the
 * selected callback across reentrant calls and releases it before returning.
 * This must run on the callback's creating thread/domain. */
long long minyar_record_get(const void *record, long long field);
void minyar_callback_check(const void *callback);
void minyar_rc_retain_traced(void *value);
void minyar_rc_release(void *value);
long long minyar_callbackruntime_serviceWait(long long timeout_ms);

static inline void minyar_mobile_dispatch(void *session, long long event) {
    void *callback = (void *)(uintptr_t)minyar_record_get(session, 0);
    minyar_callback_check(callback);
    minyar_rc_retain_traced(callback);
    typedef void (*Handler)(void *, long long);
    Handler handler = (Handler)(uintptr_t)minyar_record_get(callback, 0);
    void *environment = (void *)(uintptr_t)minyar_record_get(callback, 1);
    handler(environment, event);
    minyar_rc_release(callback);
}
#endif
