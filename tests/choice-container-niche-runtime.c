/* TEST ONLY: count generated choice wrappers before optimization and require
 * exact cleanup of a workload with one preallocated container payload. */
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>

static unsigned long long choice_container_records, choice_container_slots;

MinyarRecord *choice_container_new(long long fields) {
    ++choice_container_records;
    choice_container_slots += fields;
    return minyar_record_new(fields);
}
MinyarRecord *choice_container_new_scalar(long long fields) {
    ++choice_container_records;
    choice_container_slots += fields;
    return minyar_record_new_scalar(fields);
}
MinyarRecord *choice_container_new_traced(long long fields) {
    ++choice_container_records;
    choice_container_slots += fields;
    return minyar_record_new_traced(fields);
}

__attribute__((destructor)) static void choice_container_report(void) {
    assert(rc_frames == NULL);
#ifdef MINYAR_BOUNDED_RC
    while (rc_pending_count) assert(minyar_rc_poll(MINYAR_RC_POLL_BUDGET) > 0);
#else
    assert(rc_pending_count == 0);
#endif
    assert(rc_immortal_object_count == 0);
    assert(rc_object_count == 0);
    assert(rc_bytes == 0);
    fprintf(stderr, "choice container: %llu records, %llu slots, %zu live objects, %zu live bytes\n",
            choice_container_records, choice_container_slots, rc_object_count, rc_bytes);
}
