/* TEST ONLY: the enum fixture has no managed values. Count every generated
 * record constructor, including any that LLVM could otherwise fold away. */
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>

static unsigned long long choice_enum_record_allocations;

MinyarRecord *choice_enums_new(long long fields) {
    ++choice_enum_record_allocations;
    return minyar_record_new(fields);
}

MinyarRecord *choice_enums_new_scalar(long long fields) {
    ++choice_enum_record_allocations;
    return minyar_record_new_scalar(fields);
}

MinyarRecord *choice_enums_new_traced(long long fields) {
    ++choice_enum_record_allocations;
    return minyar_record_new_traced(fields);
}

__attribute__((destructor)) static void choice_enums_report(void) {
    assert(rc_frames == NULL);
#ifdef MINYAR_BOUNDED_RC
    while (rc_pending_count) assert(minyar_rc_poll(MINYAR_RC_POLL_BUDGET) > 0);
#else
    assert(rc_pending_count == 0);
#endif
    assert(choice_enum_record_allocations == 0);
    assert(rc_object_count == 0);
    assert(rc_bytes == 0);
    fprintf(stderr, "choice enums: %llu record allocations, %zu live objects, %zu live bytes\n",
            choice_enum_record_allocations, rc_object_count, rc_bytes);
}
