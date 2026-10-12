/* Native files fixtures honor the runner's owned temporary root. No process-global directory changes. */
#ifndef MINYAR_FILES_TEST_PATH_H
#define MINYAR_FILES_TEST_PATH_H
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
static void files_test_path(char *out, size_t capacity, const char *name) {
    const char *root = getenv("TMPDIR");
    if (!root || !root[0]) root = ".";
    int n = snprintf(out, capacity, "%s/%s", root, name);
    assert(n > 0 && (size_t)n < capacity);
}
#endif
