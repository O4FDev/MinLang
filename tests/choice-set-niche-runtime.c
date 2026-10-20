/* TEST ONLY: count generated wrapper calls, not the Set header/bucket Lists
 * allocated inside the runtime. The workload preallocates one Set payload. */
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>
#if defined(MINYAR_COMPILER_ARENA) || !defined(MINYAR_MAP_CYCLE_RUNTIME) || MINYAR_INTEGER_TEXT_CACHE_LIMIT != 0
#error Set wrapper counters require real cycle ownership with Integer Text caching disabled
#endif

static unsigned long long choice_set_records, choice_set_slots;
MinyarRecord *choice_set_new(long long fields) {
    ++choice_set_records;
    choice_set_slots += fields;
    return minyar_record_new(fields);
}
MinyarRecord *choice_set_new_scalar(long long fields) {
    ++choice_set_records;
    choice_set_slots += fields;
    return minyar_record_new_scalar(fields);
}
MinyarRecord *choice_set_new_traced(long long fields) {
    ++choice_set_records;
    choice_set_slots += fields;
    return minyar_record_new_traced(fields);
}

__attribute__((destructor)) static void choice_set_counter_report(void) {
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
    fprintf(stderr, "choice set: %llu records, %llu slots, 0 live objects, 0 live bytes\n",
            choice_set_records, choice_set_slots);
}
