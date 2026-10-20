/* Native implementations for the io, process, random and math modules.
 * They share the core runtime compilation unit so every ownership profile
 * uses the same allocation ABI. Legacy C symbols also serve the bootstrap
 * and existing native clients; language APIs live exclusively in modules. */

static char *text_as_path(const MinyarText *text) {
    char *path;
    if (memchr(text->bytes, 0, (size_t)text->byte_length))
        minyar_stop("a file path cannot contain a zero byte.");
#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_COMPILER_ARENA)
    path = rc_heap_allocate((size_t)text->byte_length + 1);
#else
    path = malloc((size_t)text->byte_length + 1);
#endif
    if (!path)
        out_of_memory();
    memcpy(path, text->bytes, (size_t)text->byte_length);
    path[text->byte_length] = 0;
    return path;
}

long long minyar_argument_count(void) {
    return saved_argument_count > 0 ? saved_argument_count - 1 : 0;
}

MinyarText *minyar_argument(long long position) {
    if (position < 0 || position >= minyar_argument_count())
        minyar_stop("a program argument position was outside the argument list.");
#ifdef _WIN32
    const wchar_t *argument = saved_windows_argument_values[position + 1];
    int length =
        WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, argument, -1, NULL, 0, NULL, NULL);
    if (length <= 0)
        minyar_stop("a program argument contained invalid Unicode.");
    unsigned char *bytes = new_bytes((long long)length - 1);
    if (WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, argument, -1, (char *)bytes, length,
                            NULL, NULL) != length)
        minyar_stop("a program argument could not be converted to UTF-8.");
    return new_text(bytes, (long long)length - 1, -1);
#else
    return copy_c_text(saved_argument_values[position + 1]);
#endif
}

static long long text_file_length(FILE *file) {
    /* Some filesystems allow seeking directories and report a huge offset.
     * Check readability before treating that offset as an allocation size.
     * The seek below restores the first byte and clears EOF for empty files. */
    if (fgetc(file) == EOF && ferror(file))
        minyar_stop("a requested text file could not be read.");
#ifdef _WIN32
    __int64 length;
    if (_fseeki64(file, 0, SEEK_END) != 0 || (length = _ftelli64(file)) < 0 ||
        _fseeki64(file, 0, SEEK_SET) != 0)
#else
    long length;
    if (fseek(file, 0, SEEK_END) != 0 || (length = ftell(file)) < 0 ||
        fseek(file, 0, SEEK_SET) != 0)
#endif
        minyar_stop("a requested text file could not be read.");
    if ((unsigned long long)length > (unsigned long long)LLONG_MAX ||
        (unsigned long long)length >= (unsigned long long)SIZE_MAX)
        minyar_stop("a requested text file is too large.");
    return (long long)length;
}

/* Language paths are UTF-8 on every platform. All callers use binary modes. */
static FILE *open_text_path(const char *path, const char *mode) {
#ifdef _WIN32
    int length = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, path, -1, NULL, 0);
    if (length <= 0)
        minyar_stop("a file path contained invalid UTF-8.");
#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_COMPILER_ARENA)
    wchar_t *wide = rc_heap_allocate((size_t)length * sizeof(wchar_t));
#else
    wchar_t *wide = malloc((size_t)length * sizeof(wchar_t));
#endif
    if (!wide)
        out_of_memory();
    if (MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, path, -1, wide, length) != length)
        minyar_stop("a file path could not be converted to UTF-16.");
    FILE *file = _wfopen(wide, mode[0] == 'w' ? L"wb" : L"rb");
#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_COMPILER_ARENA)
    rc_heap_deallocate(wide);
#else
    free(wide);
#endif
    return file;
#else
    return fopen(path, mode);
#endif
}

MinyarText *minyar_read_text_file(const MinyarText *path_text) {
    char *path = text_as_path(path_text);
    FILE *file = open_text_path(path, "rb");
    long long length;
    unsigned char *bytes;
    if (!file) {
        fprintf(stderr, "Minyar stopped: the file '%s' could not be opened.\n", path);
#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_COMPILER_ARENA)
        rc_heap_deallocate(path);
#else
        free(path);
#endif
        minyar_print_stack_trace();
        exit(1);
    }
    length = text_file_length(file);
    bytes = new_bytes(length);
    if (fread(bytes, 1, (size_t)length, file) != (size_t)length)
        minyar_stop("a requested text file could not be read.");
    fclose(file);
#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_COMPILER_ARENA)
    rc_heap_deallocate(path);
#else
    free(path);
#endif
    bytes[length] = 0;
    validate_text_bytes(bytes, length);
    return new_text(bytes, length, -1);
}

static FILE *create_text_file(const MinyarText *path_text) {
    char *path = text_as_path(path_text);
    FILE *file = open_text_path(path, "wb");
#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_COMPILER_ARENA)
    rc_heap_deallocate(path);
#else
    free(path);
#endif
    if (!file)
        minyar_stop("a requested text file could not be created.");
    return file;
}

static void finish_text_file(FILE *file, int written) {
    if (!written || fclose(file) != 0)
        minyar_stop("a requested text file could not be written.");
}

void minyar_write_text_file(const MinyarText *path_text, const MinyarText *contents) {
    FILE *file = create_text_file(path_text);
    finish_text_file(file, fwrite(contents->bytes, 1, (size_t)contents->byte_length, file) ==
                               (size_t)contents->byte_length);
}

#ifndef MINYAR_WRITE_PARTS_BUFFER
#define MINYAR_WRITE_PARTS_BUFFER (256u * 1024u)
#endif

/* writeTextFile(path, pieces) writes what joinText(pieces) would contain
 * without building it, so a program that emits its output in many small
 * pieces (the compiler emits about 200,000) never holds the whole file twice.
 * Pieces are gathered in a buffer large enough that per-write file system
 * costs stay small; each write call costs tens of thousands of instructions. */
void minyar_write_text_parts(const MinyarText *path_text, const MinyarList *parts) {
    FILE *file = create_text_file(path_text);
    unsigned char *buffer = malloc(MINYAR_WRITE_PARTS_BUFFER);
    size_t used = 0;
    int written = 1;
    if (!buffer)
        out_of_memory();
    for (long long index = 0; written && index < parts->length; index++) {
        const MinyarText *part = (const MinyarText *)(intptr_t)parts->values[index];
        size_t length = (size_t)part->byte_length;
        if (length > MINYAR_WRITE_PARTS_BUFFER - used) {
            written = fwrite(buffer, 1, used, file) == used;
            used = 0;
            if (length > MINYAR_WRITE_PARTS_BUFFER) {
                written = written && fwrite(part->bytes, 1, length, file) == length;
                continue;
            }
        }
        copy_bytes(buffer + used, part->bytes, length);
        used += length;
    }
    written = written && fwrite(buffer, 1, used, file) == used;
    free(buffer);
    finish_text_file(file, written);
}

/* random.bytes(count): bytes from the platform's cryptographically secure
 * generator. Freestanding programs supply minyar_platform_random. */
#if defined(__APPLE__) || defined(__OpenBSD__) || defined(__FreeBSD__)
static void fill_random(unsigned char *out, size_t count) {
    arc4random_buf(out, count);
}
#elif defined(__wasi__)
#include <wasi/api.h>
static void fill_random(unsigned char *out, size_t count) {
    if (__wasi_random_get(out, count) != 0)
        minyar_stop("the system could not provide random bytes.");
}
#elif defined(__linux__)
#include <sys/random.h>
static void fill_random(unsigned char *out, size_t count) {
    while (count) {
        ssize_t got = getrandom(out, count, 0);
        if (got <= 0)
            minyar_stop("the system could not provide random bytes.");
        out += got;
        count -= (size_t)got;
    }
}
#elif defined(_WIN32)
#include <bcrypt.h>
typedef NTSTATUS(WINAPI *MinyarRandomGenerator)(BCRYPT_ALG_HANDLE, PUCHAR, ULONG, ULONG);
static INIT_ONCE random_once = INIT_ONCE_STATIC_INIT;
static MinyarRandomGenerator random_generator;

static BOOL CALLBACK initialize_random(PINIT_ONCE once, PVOID parameter, PVOID *context) {
    (void)once;
    (void)parameter;
    (void)context;
    /* Use the system DLL explicitly. Every runtime profile and direct C client
     * can use randomBytes without acquiring a new static linker dependency. */
    HMODULE module = LoadLibraryExW(L"bcrypt.dll", NULL, LOAD_LIBRARY_SEARCH_SYSTEM32);
    if (!module)
        return FALSE;
    random_generator = (MinyarRandomGenerator)GetProcAddress(module, "BCryptGenRandom");
    if (!random_generator) {
        FreeLibrary(module);
        return FALSE;
    }
    /* The process owns this one module reference for the lifetime of the cached
     * function. InitOnce publishes it safely to concurrent random requests. */
    return TRUE;
}

static void fill_random(unsigned char *out, size_t count) {
    if (!InitOnceExecuteOnce(&random_once, initialize_random, NULL, NULL))
        minyar_stop("the system could not provide random bytes.");
    while (count) {
        ULONG chunk = count > UINT32_MAX ? UINT32_MAX : (ULONG)count;
        if (random_generator(NULL, out, chunk, BCRYPT_USE_SYSTEM_PREFERRED_RNG) != 0)
            minyar_stop("the system could not provide random bytes.");
        out += chunk;
        count -= chunk;
    }
}
#else
void minyar_platform_random(unsigned char *out, size_t count);
static void fill_random(unsigned char *out, size_t count) {
    minyar_platform_random(out, count);
}
#endif

MinyarBytes *minyar_random_bytes(long long count) {
    MinyarBytes *bytes = minyar_bytes_new(count);
    if (count)
        fill_random((unsigned char *)bytes->bytes, (size_t)count);
    return bytes;
}

MinyarBytes *minyar_read_bytes_file(const MinyarText *path_text) {
    char *path = text_as_path(path_text);
    FILE *file = open_text_path(path, "rb");
    if (!file) {
        fprintf(stderr, "Minyar stopped: the file '%s' could not be opened.\n", path);
        minyar_print_stack_trace();
        exit(1);
    }
#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_COMPILER_ARENA)
    rc_heap_deallocate(path);
#else
    free(path);
#endif
    long long length = text_file_length(file);
    MinyarBytes *bytes = minyar_bytes_new(length);
    if (fread(bytes_data(bytes), 1, (size_t)length, file) != (size_t)length)
        minyar_stop("a requested file could not be read.");
    fclose(file);
    return bytes;
}

void minyar_write_bytes_file(const MinyarText *path_text, const MinyarBytes *contents) {
    char *path = text_as_path(path_text);
    FILE *file = open_text_path(path, "wb");
#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_COMPILER_ARENA)
    rc_heap_deallocate(path);
#else
    free(path);
#endif
    if (!file)
        minyar_stop("a requested file could not be created.");
    if (fwrite(contents->bytes, 1, (size_t)contents->byte_length, file) !=
            (size_t)contents->byte_length ||
        fclose(file) != 0)
        minyar_stop("a requested file could not be written.");
}

_Bool minyar_file_exists(const MinyarText *path_text) {
    char *path = text_as_path(path_text);
    FILE *file = open_text_path(path, "rb");
#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_COMPILER_ARENA)
    rc_heap_deallocate(path);
#else
    free(path);
#endif
    if (!file)
        return 0;
    fclose(file);
    return 1;
}

double minyar_tan(double value) {
    return tan(value);
}
double minyar_asin(double value) {
    return asin(value);
}
double minyar_acos(double value) {
    return acos(value);
}
double minyar_atan(double value) {
    return atan(value);
}
double minyar_atan2(double y, double x) {
    return atan2(y, x);
}

/* Recoverable whole-file I/O captures an errno in a private native snapshot.
 * Neither empty files nor truncated reads are mistaken for successful data.
 * Legacy entry points below retain their original diagnostics and behavior. */
#if defined(__STDC_HOSTED__) && __STDC_HOSTED__
#include <errno.h>
static void release_io_path(char *path) {
#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_COMPILER_ARENA)
    rc_heap_deallocate(path);
#else
    free(path);
#endif
}

MinyarRecord *minyar_runtime_readBytesOutcome(const MinyarText *path_text, long long maximum) {
    MinyarBytes *data = minyar_bytes_new(0);
    int code = 0;
    if (maximum < 0 || memchr(path_text->bytes, 0, (size_t)path_text->byte_length)) {
        code = EINVAL;
    } else {
        char *path = text_as_path(path_text);
        FILE *file = open_text_path(path, "rb");
        if (!file) code = errno ? errno : EIO;
        release_io_path(path);
        if (file) {
            unsigned char buffer[8192];
            for (;;) {
                size_t count = fread(buffer, 1, sizeof(buffer), file);
                if ((unsigned long long)count > (unsigned long long)(maximum - data->byte_length)) {
                    code = EFBIG;
                    break;
                }
                if (count) memcpy(minyar_bytes_extend(data, (long long)count), buffer, count);
                if (count != sizeof(buffer)) {
                    if (ferror(file)) code = errno ? errno : EIO;
                    break;
                }
            }
            if (fclose(file) != 0 && !code) code = errno ? errno : EIO;
        }
    }
    MinyarRecord *result = minyar_record_new(2);
    minyar_record_set_take(result, 0, (long long)(intptr_t)data);
    minyar_record_set(result, 1, code);
    return result;
}

static long long checked_file_write(const MinyarText *path_text, const MinyarBytes *contents,
                                    const MinyarList *parts) {
    if (memchr(path_text->bytes, 0, (size_t)path_text->byte_length)) return -EINVAL;
    char *path = text_as_path(path_text);
    FILE *file = open_text_path(path, "wb");
    int code = file ? 0 : (errno ? errno : EIO);
    release_io_path(path);
    if (!file) return -code;
    if (parts) {
        for (long long index = 0; index < parts->length; index++) {
            const MinyarText *part = (const MinyarText *)(intptr_t)parts->values[index];
            if (fwrite(part->bytes, 1, (size_t)part->byte_length, file) != (size_t)part->byte_length) {
                code = errno ? errno : EIO;
                break;
            }
        }
    } else if (fwrite(contents->bytes, 1, (size_t)contents->byte_length, file) != (size_t)contents->byte_length) {
        code = errno ? errno : EIO;
    }
    if (fclose(file) != 0 && !code) code = errno ? errno : EIO;
    return -code;
}

#else
/* There is no hosted filesystem or errno in the freestanding shim. Keep
 * typed I/O recoverable without importing host headers or fabricating data.
 * Codes match the existing freestanding process/sync contract: EINVAL=22,
 * ENOSYS=38. The kernel's own disk driver is independent of these APIs. */
MinyarRecord *minyar_runtime_readBytesOutcome(const MinyarText *path, long long maximum) {
    int invalid = maximum < 0 || memchr(path->bytes, 0, (size_t)path->byte_length);
    MinyarRecord *result = minyar_record_new(2);
    minyar_record_set_take(result, 0, (long long)(intptr_t)minyar_bytes_new(0));
    minyar_record_set(result, 1, invalid ? 22 : 38);
    return result;
}
static long long checked_file_write(const MinyarText *path, const MinyarBytes *contents,
                                    const MinyarList *parts) {
    (void)contents;
    (void)parts;
    return memchr(path->bytes, 0, (size_t)path->byte_length) ? -22 : -38;
}
#endif

long long minyar_runtime_writeBytesStatus(const MinyarText *path, const MinyarBytes *contents) {
    return checked_file_write(path, contents, NULL);
}
long long minyar_runtime_writePartsStatus(const MinyarText *path, const MinyarRecord *contents) {
    const MinyarList *parts = (const MinyarList *)(intptr_t)minyar_record_get(contents, 0);
    return checked_file_write(path, NULL, parts);
}

/* Module-native entry points. */
MinyarText *minyar_runtime_readTextFile(const MinyarText *path) { return minyar_read_text_file(path); }
void minyar_runtime_writeTextFile(const MinyarText *path, const MinyarText *text) { minyar_write_text_file(path, text); }
long long minyar_runtime_openTextWriter(const MinyarText *path) {
    FILE *file = create_text_file(path);
#if defined(__STDC_HOSTED__) && __STDC_HOSTED__
    if (setvbuf(file, NULL, _IOFBF, MINYAR_WRITE_PARTS_BUFFER) != 0)
        minyar_stop("a requested text file could not be buffered.");
#endif
    return (long long)(uintptr_t)file;
}
void minyar_runtime_writeTextPart(long long writer, const MinyarText *part) {
    FILE *file = (FILE *)(uintptr_t)writer;
    if (fwrite(part->bytes, 1, (size_t)part->byte_length, file) != (size_t)part->byte_length)
        minyar_stop("a requested text file could not be written.");
}
void minyar_runtime_closeTextWriter(long long writer) {
    finish_text_file((FILE *)(uintptr_t)writer, 1);
}
MinyarBytes *minyar_runtime_readBytesFile(const MinyarText *path) { return minyar_read_bytes_file(path); }
void minyar_runtime_writeBytesFile(const MinyarText *path, const MinyarBytes *bytes) { minyar_write_bytes_file(path, bytes); }
_Bool minyar_runtime_fileExists(const MinyarText *path) { return minyar_file_exists(path); }
long long minyar_runtime_argumentCount(void) { return minyar_argument_count(); }
MinyarText *minyar_runtime_argument(long long index) { return minyar_argument(index); }
MinyarBytes *minyar_runtime_bytes(long long count) { return minyar_random_bytes(count); }
double minyar_runtime_sqrt(double value) { return sqrt(value); }
double minyar_runtime_sin(double value) { return sin(value); }
double minyar_runtime_cos(double value) { return cos(value); }
double minyar_runtime_tan(double value) { return tan(value); }
double minyar_runtime_asin(double value) { return asin(value); }
double minyar_runtime_acos(double value) { return acos(value); }
double minyar_runtime_atan(double value) { return atan(value); }
double minyar_runtime_exp(double value) { return exp(value); }
double minyar_runtime_log(double value) { return log(value); }
double minyar_runtime_floor(double value) { return floor(value); }
double minyar_runtime_ceil(double value) { return ceil(value); }
double minyar_runtime_round(double value) { return round(value); }
double minyar_runtime_atan2(double first, double second) { return atan2(first, second); }
double minyar_runtime_pow(double first, double second) { return pow(first, second); }

#if defined(__STDC_HOSTED__) && __STDC_HOSTED__
#include <errno.h>
#ifndef _WIN32
#include <unistd.h>
#include <time.h>
#endif
#endif
#if defined(__STDC_HOSTED__) && __STDC_HOSTED__
long long minyar_runtime_processId(void) {
    int saved_errno = errno;
#ifdef _WIN32
    long long result = (long long)GetCurrentProcessId();
#elif defined(__wasi__)
    long long result = -38; /* WASI Preview 1 has no process identifier. */
#elif defined(__STDC_HOSTED__) && __STDC_HOSTED__
    long long result = (long long)getpid();
#else
    long long result = -38;
#endif
    errno = saved_errno;
    return result;
}
long long minyar_runtime_sleepNanoseconds(long long nanoseconds) {
    int saved_errno = errno;
    long long result = 0;
    if (nanoseconds < 0) result = -EINVAL;
    else if (nanoseconds) {
#if MINYAR_THREADED
        rc_thread_domain_drain();
#endif
#ifdef _WIN32
        HANDLE timer = CreateWaitableTimerW(NULL, TRUE, NULL);
        if (!timer) result = -EIO;
        else {
            LARGE_INTEGER due;
            /* Ceiling division without overflowing signed Integer. */
            due.QuadPart = -(nanoseconds / 100 + (nanoseconds % 100 != 0));
            if (!SetWaitableTimer(timer, &due, 0, NULL, NULL, FALSE) ||
                WaitForSingleObject(timer, INFINITE) != WAIT_OBJECT_0) result = -EIO;
            CloseHandle(timer);
        }
#elif defined(__STDC_HOSTED__) && __STDC_HOSTED__
        long long seconds = nanoseconds / 1000000000;
        if ((long long)(time_t)seconds != seconds) result = -EINVAL;
        else {
            struct timespec request = {(time_t)seconds, (long)(nanoseconds % 1000000000)};
            struct timespec remaining;
            while (nanosleep(&request, &remaining)) {
                int error = errno;
                if (error != EINTR) { result = -(long long)error; break; }
                request = remaining;
            }
        }
#else
        result = -38;
#endif
    }
    errno = saved_errno;
    return result;
}
long long minyar_runtime_sync(long long descriptor) {
    int saved_errno = errno;
    long long result;
    if (descriptor < 0 || descriptor > INT_MAX) result = -EINVAL;
    else {
#if MINYAR_THREADED
        rc_thread_domain_drain();
#endif
#ifdef _WIN32
        result = _commit((int)descriptor) ? -(long long)errno : 0;
#elif defined(__STDC_HOSTED__) && __STDC_HOSTED__
        result = fsync((int)descriptor) ? -(long long)errno : 0;
#else
        result = -38;
#endif
    }
    errno = saved_errno;
    return result;
}
#else
long long minyar_runtime_processId(void) { return -38; }
long long minyar_runtime_sleepNanoseconds(long long value) { return value < 0 ? -22 : (value == 0 ? 0 : -38); }
long long minyar_runtime_sync(long long descriptor) { return descriptor < 0 || descriptor > INT_MAX ? -22 : -38; }
#endif
