/* TEST ONLY: count generated record constructors before LLVM optimization,
 * and require exact cleanup after the same preallocated Text/List workload. */
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>

static unsigned long long choice_text_records, choice_text_slots;

MinyarRecord *choice_text_new(long long fields) {
    ++choice_text_records;
    choice_text_slots += fields;
    return minyar_record_new(fields);
}
MinyarRecord *choice_text_new_scalar(long long fields) {
    ++choice_text_records;
    choice_text_slots += fields;
    return minyar_record_new_scalar(fields);
}
MinyarRecord *choice_text_new_traced(long long fields) {
    ++choice_text_records;
    choice_text_slots += fields;
    return minyar_record_new_traced(fields);
}

__attribute__((destructor)) static void choice_text_report(void) {
    assert(rc_frames == NULL);
#ifdef MINYAR_BOUNDED_RC
    while (rc_pending_count) assert(minyar_rc_poll(MINYAR_RC_POLL_BUDGET) > 0);
#else
    assert(rc_pending_count == 0);
#endif
    assert(rc_immortal_object_count == 0);
    assert(rc_object_count == 0);
    assert(rc_bytes == 0);
    fprintf(stderr, "choice Text: %llu records, %llu slots, %zu live objects, %zu live bytes\n",
            choice_text_records, choice_text_slots, rc_object_count, rc_bytes);
}
