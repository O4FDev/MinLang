/* Deterministic stdio failure injection for writeTextFile's two error paths. */
/* The included runtime uses GNU pthread stack queries on sanitized Linux. */
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE 1
#endif
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static FILE *peer_output;
static FILE *peer_fopen(const char *path, const char *mode) {
    FILE *file = fopen(path, mode);
    if (!strcmp(mode, "wb")) peer_output = file;
    return file;
}

static size_t peer_fwrite(const void *bytes, size_t size, size_t count, FILE *file) {
    const char *failure = getenv("MINYAR_PEER_WRITE_FAILURE");
    if (file == peer_output && failure && !strcmp(failure, "write-zero")) {
        return 0;
    }
    if (file == peer_output && failure && !strcmp(failure, "write")) {
        size_t written = fwrite(bytes, size, count / 2, file);
        if (fflush(file)) abort();
        return written;
    }
    return fwrite(bytes, size, count, file);
}

static int peer_fclose(FILE *file) {
    const char *failure = getenv("MINYAR_PEER_WRITE_FAILURE");
    int selected = file == peer_output;
    int result = fclose(file);
    if (selected) peer_output = NULL;
    if (selected && failure && !strcmp(failure, "close")) {
        if (result) abort();
        return EOF;
    }
    return result;
}

#define fopen peer_fopen
#define fwrite peer_fwrite
#define fclose peer_fclose
#include "../runtime/minyar_runtime.c"
