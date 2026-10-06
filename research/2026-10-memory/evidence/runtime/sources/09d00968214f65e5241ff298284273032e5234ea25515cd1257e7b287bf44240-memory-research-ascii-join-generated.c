/* Only link with the research runner's instrumented runtime snapshot. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#include <stddef.h>
#ifndef MINYAR_RESEARCH_INSTRUMENTED
#error Use the research runner's instrumented runtime snapshot.
#endif
static size_t research_index_builds, research_index_input_bytes;
static size_t research_service_calls, research_service_work;
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include "../runtime/minyar_stack_frames.h"

__attribute__((destructor)) static void report_metrics(void) {
    fprintf(stderr,
            "{\"index_builds\":%zu,\"index_input_bytes\":%zu,\"service_hooks\":%zu,"
            "\"service_units\":%zu}\n",
            research_index_builds, research_index_input_bytes, research_service_calls,
            research_service_work);
}
