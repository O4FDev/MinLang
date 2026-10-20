/* Development-only persistent native code images. Managed roots and literals
 * may refer to any successful image, so images deliberately remain loaded. */
#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif
#include "../runtime/minyar_native.h"
#include <dlfcn.h>
#include <errno.h>
#include <unistd.h>

struct repl_image { void *handle; struct repl_image *previous; };
static struct repl_image *repl_images;

MinyarText *minyar_replhost_readLine(void) {
    char *line = NULL;
    size_t capacity = 0;
    ssize_t length;
    do {
        errno = 0;
        length = getline(&line, &capacity, stdin);
        if (length < 0 && errno == EINTR) clearerr(stdin);
        else break;
    } while (1);
    if (length < 0 && ferror(stdin)) {
        free(line);
        minyar_native_stop("the REPL could not read standard input");
    }
    if (length > 16 * 1024 * 1024) {
        free(line);
        minyar_native_stop("a REPL input line exceeds 16 MiB");
    }
    MinyarText *result = minyar_native_copy_text(
        (const unsigned char *)(length < 0 ? "" : line), length < 0 ? 0 : length);
    free(line);
    return result;
}

bool minyar_replhost_isTerminal(void) { return isatty(STDIN_FILENO) != 0; }

static char *repl_string(const MinyarText *value) {
    if (value->byte_length < 0 || value->byte_length > 1024 * 1024 ||
        memchr(value->bytes, 0, (size_t)value->byte_length)) return NULL;
    char *result = malloc((size_t)value->byte_length + 1);
    if (!result) return NULL;
    memcpy(result, value->bytes, (size_t)value->byte_length);
    result[value->byte_length] = 0;
    return result;
}

long long minyar_replhost_evaluate(const MinyarText *path_value, const MinyarText *entry_value) {
    char *path = repl_string(path_value), *entry = repl_string(entry_value);
    struct repl_image *image = malloc(sizeof *image);
    if (!path || !entry || !image) {
        fprintf(stderr, "[repl] cannot prepare a native code image\n");
        free(path); free(entry); free(image); return 1;
    }
    void *handle = dlopen(path, RTLD_NOW | RTLD_GLOBAL);
    if (!handle) {
        fprintf(stderr, "[repl] cannot load this submission: %s\n", dlerror());
        free(path); free(entry); free(image); return 1;
    }
    dlerror();
    void *address = dlsym(handle, entry);
    const char *error = dlerror();
    if (error || !address) {
        fprintf(stderr, "[repl] cannot find this submission's entry point: %s\n",
                error ? error : "missing entry point");
        dlclose(handle); free(path); free(entry); free(image); return 1;
    }
    image->handle = handle; image->previous = repl_images; repl_images = image;
    free(path); free(entry);
    int (*run)(int, char **) = NULL;
    _Static_assert(sizeof run == sizeof address, "native function pointer ABI");
    memcpy(&run, &address, sizeof run);
    char name[] = "minyar repl";
    char *arguments[] = {name, NULL};
    return run(1, arguments);
}

/* Every submission recompiles the current function declarations. Its calls
 * resolve to that image's own bodies; no previous top-level action is replayed. */
void *minyar_live_resolve(const char *key, void *fallback) {
    (void)key;
    return fallback;
}
