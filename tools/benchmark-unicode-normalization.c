/* Paired normalization CPU probe. Compile alongside the production Unicode
 * provider and pinned utf8proc.c, without normalization operation counters.
 * This intentionally uses a small shared owned-copy/free ABI rather than the
 * managed runtime; both variants pay exactly the same copy and checksum work. */
#if !defined(_WIN32) && !defined(_POSIX_C_SOURCE)
#define _POSIX_C_SOURCE 200809L
#endif
#ifdef MINYAR_UNICODE_NORMALIZATION_TESTING
#error "normalization benchmarks must use the production provider without operation counters"
#endif
#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "../runtime/minyar_native.h"
#define UTF8PROC_STATIC
#include "../vendor/utf8proc/utf8proc.h"

MinyarText *minyar_unicode_normalized(const MinyarText *source);
MinyarText *minyar_unicode_caseFold(const MinyarText *source);

#if defined(__GNUC__) || defined(__clang__)
#define BENCH_NOINLINE __attribute__((noinline))
#else
#define BENCH_NOINLINE
#endif

static size_t live_texts;

static void require(int condition, const char *message) {
    if (!condition) {
        fprintf(stderr, "normalization benchmark: %s\n", message);
        exit(1);
    }
}

MinyarBytes *minyar_bytes_new(long long length) {
    (void)length;
    fputs("normalization benchmark unexpectedly requested Bytes\n", stderr);
    abort();
}

/* Noinline keeps the baseline's same-translation-unit call from eliding a
 * copy that remains opaque to the separately compiled current provider. */
BENCH_NOINLINE MinyarText *minyar_native_copy_text(const unsigned char *bytes, long long length) {
    require(length >= 0 && (uint64_t)length < SIZE_MAX, "invalid copied Text length");
    require(bytes || length == 0, "invalid copied Text bytes");
    MinyarText *text = malloc(sizeof(*text));
    unsigned char *copy = malloc((size_t)length + 1);
    require(text && copy, "could not allocate copied Text");
    if (length) memcpy(copy, bytes, (size_t)length);
    copy[length] = 0;
    *text = (MinyarText){copy, length, -1, NULL, NULL};
    live_texts++;
    return text;
}

static BENCH_NOINLINE void release_text(MinyarText *text) {
    require(text && live_texts > 0, "invalid owned Text release");
    free((void *)text->bytes);
    free(text);
    live_texts--;
}

static MinyarText *baseline_nfc(const MinyarText *source) {
    unsigned char *output;
    utf8proc_ssize_t length = utf8proc_map(source->bytes, (utf8proc_ssize_t)source->byte_length,
        &output, UTF8PROC_COMPOSE | UTF8PROC_STABLE);
    require(length >= 0, "baseline NFC failed");
    MinyarText *result = minyar_native_copy_text(output, (long long)length);
    utf8proc_free(output);
    return result;
}

static MinyarText *baseline_fold(const MinyarText *source) {
    unsigned char *decomposed, *output;
    utf8proc_ssize_t length = utf8proc_map(source->bytes, (utf8proc_ssize_t)source->byte_length,
        &decomposed, UTF8PROC_DECOMPOSE | UTF8PROC_STABLE);
    require(length >= 0, "baseline NFD before folding failed");
    length = utf8proc_map(decomposed, length, &output,
        UTF8PROC_CASEFOLD | UTF8PROC_COMPOSE | UTF8PROC_STABLE);
    require(length >= 0, "baseline folding failed");
    utf8proc_free(decomposed);
    MinyarText *result = minyar_native_copy_text(output, (long long)length);
    utf8proc_free(output);
    return result;
}

enum { MAX_MARKS = 16384, INPUT_CAPACITY = (MAX_MARKS + 1) * 4 + 1 };
typedef struct { unsigned char *bytes; size_t length, scalars; } Input;

static void append_bytes(Input *input, const unsigned char *bytes, size_t length) {
    require(length < INPUT_CAPACITY - input->length, "benchmark input exceeds its bound");
    memcpy(input->bytes + input->length, bytes, length);
    input->length += length;
    input->bytes[input->length] = 0;
}

static void append_scalar(Input *input, uint32_t scalar) {
    unsigned char bytes[4];
    utf8proc_ssize_t length = utf8proc_encode_char((utf8proc_int32_t)scalar, bytes);
    require(length > 0 && length <= 4, "invalid fixture scalar");
    append_bytes(input, bytes, (size_t)length);
}

static Input make_input(const char *name) {
    Input input = {malloc(INPUT_CAPACITY), 0, 0};
    require(input.bytes != NULL, "could not allocate input fixture");
    input.bytes[0] = 0;
    static const unsigned char ascii[] =
        "MINYAR carries 42 small boats past the harbour, safely and plainly.\n";
    static const unsigned char composed[] =
        "Caf\u00E9; Stra\u00DFe; \u00C5ngstr\u00F6m; na\u00EFve; r\u00E9sum\u00E9; 42 boats. \U0001F30A\n";
    static const unsigned char decomposed[] =
        "Cafe\u0301; Stra\u00DFe; A\u030Angstro\u0308m; nai\u0308ve; re\u0301sume\u0301; 42 boats. \U0001F30A\n";
    if (!strcmp(name, "ascii") || !strcmp(name, "prose-composed") || !strcmp(name, "prose-decomposed")) {
        const unsigned char *bytes = ascii;
        size_t length = sizeof(ascii) - 1;
        if (!strcmp(name, "prose-composed")) { bytes = composed; length = sizeof(composed) - 1; }
        if (!strcmp(name, "prose-decomposed")) { bytes = decomposed; length = sizeof(decomposed) - 1; }
        for (unsigned repeat = 0; repeat < 4; repeat++) append_bytes(&input, bytes, length);
    } else if (!strcmp(name, "short-runs")) {
        for (unsigned repeat = 0; repeat < 32; repeat++) {
            append_scalar(&input, 0x71);
            append_scalar(&input, 0x315);
            append_scalar(&input, 0x301);
            append_scalar(&input, 0x323);
            append_scalar(&input, 0x300);
        }
    } else {
        int leading = !strncmp(name, "leading-", 8);
        int starter = !strncmp(name, "starter-", 8);
        require(leading || starter, "unknown input case");
        const char *size = name + 8;
        size_t marks = !strcmp(size, "1024") ? 1024 : !strcmp(size, "4096") ? 4096 :
                       !strcmp(size, "16384") ? 16384 : 0;
        require(marks != 0, "adversarial size must be 1024, 4096 or 16384 marks");
        if (starter) append_scalar(&input, 0x71);
        /* Equal-class alternation makes stability visible in the checksum.
         * Leading and starter cases both contain marks/2 high-class scalars
         * followed by marks/2 low-class scalars: marks^2/4 inversions. */
        for (size_t index = 0; index < marks / 2; index++) append_scalar(&input, index % 2 ? 0x31A : 0x315);
        for (size_t index = 0; index < marks / 2; index++) append_scalar(&input, index % 2 ? 0x324 : 0x323);
    }
    for (size_t position = 0; position < input.length;) {
        utf8proc_int32_t scalar;
        utf8proc_ssize_t width = utf8proc_iterate(input.bytes + position,
            (utf8proc_ssize_t)(input.length - position), &scalar);
        require(width > 0, "fixture contains invalid UTF-8");
        position += (size_t)width;
        input.scalars++;
    }
    return input;
}

static int process_clock;
static const char *clock_name = "clock";
static double clock_resolution;

static void initialize_clock(void) {
#ifdef CLOCK_PROCESS_CPUTIME_ID
    struct timespec now, resolution;
    if (clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &now) == 0) {
        process_clock = 1;
        clock_name = "CLOCK_PROCESS_CPUTIME_ID";
        if (clock_getres(CLOCK_PROCESS_CPUTIME_ID, &resolution) == 0)
            clock_resolution = (double)resolution.tv_sec + (double)resolution.tv_nsec / 1e9;
        return;
    }
#endif
    clock_resolution = 1.0 / CLOCKS_PER_SEC;
}

static double cpu_seconds(void) {
#ifdef CLOCK_PROCESS_CPUTIME_ID
    if (process_clock) {
        struct timespec now;
        require(clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &now) == 0, "could not read process CPU clock");
        return (double)now.tv_sec + (double)now.tv_nsec / 1e9;
    }
#endif
    clock_t now = clock();
    require(now != (clock_t)-1, "could not read CPU clock");
    return (double)now / CLOCKS_PER_SEC;
}

static uint64_t checksum_bytes(uint64_t checksum, const unsigned char *bytes, size_t length) {
    for (size_t index = 0; index < length; index++) {
        checksum ^= bytes[index];
        checksum *= UINT64_C(1099511628211);
    }
    checksum ^= (uint64_t)length;
    return checksum * UINT64_C(1099511628211);
}

int main(int argc, char **argv) {
    const char *variant = NULL, *operation = NULL, *name = NULL, *iteration_text = NULL;
    for (int index = 1; index < argc; index += 2) {
        require(index + 1 < argc, "each option requires one value");
        if (!strcmp(argv[index], "--variant")) variant = argv[index + 1];
        else if (!strcmp(argv[index], "--operation")) operation = argv[index + 1];
        else if (!strcmp(argv[index], "--case")) name = argv[index + 1];
        else if (!strcmp(argv[index], "--iterations")) iteration_text = argv[index + 1];
        else require(0, "unknown option");
    }
    require(variant && operation && name && iteration_text, "expected --variant, --operation, --case and --iterations");
    require(!strcmp(variant, "baseline") || !strcmp(variant, "current"), "unknown variant");
    require(!strcmp(operation, "nfc") || !strcmp(operation, "fold"), "unknown operation");
    char *after;
    errno = 0;
    unsigned long long iterations = strtoull(iteration_text, &after, 10);
    require(!errno && iteration_text[0] >= '0' && iteration_text[0] <= '9' && !*after &&
            iterations > 0 && iterations <= 10000000, "iterations must be 1..10000000");
    Input input = make_input(name);
    MinyarText source = {input.bytes, (long long)input.length, -1, NULL, NULL};
    MinyarText *(*transform)(const MinyarText *);
    if (!strcmp(variant, "baseline")) transform = !strcmp(operation, "nfc") ? baseline_nfc : baseline_fold;
    else transform = !strcmp(operation, "nfc") ? minyar_unicode_normalized : minyar_unicode_caseFold;
    initialize_clock();
    uint64_t checksum = UINT64_C(14695981039346656037), output_bytes = 0;
    long long bytes_per_operation = -1;
    double start = cpu_seconds();
    for (unsigned long long index = 0; index < iterations; index++) {
        MinyarText *result = transform(&source);
        require(result && result->byte_length >= 0, "invalid transformation result");
        if (bytes_per_operation < 0) bytes_per_operation = result->byte_length;
        require(result->byte_length == bytes_per_operation, "output length changed between iterations");
        require((uint64_t)result->byte_length <= UINT64_MAX - output_bytes, "output byte counter overflow");
        output_bytes += (uint64_t)result->byte_length;
        checksum = checksum_bytes(checksum, result->bytes, (size_t)result->byte_length);
        release_text(result);
    }
    double elapsed = cpu_seconds() - start;
    require(live_texts == 0 && elapsed > 0, "owned Text leak or insufficient CPU clock resolution");
    printf("{\"schema_version\":1,\"variant\":\"%s\",\"operation\":\"%s\",\"case\":\"%s\","
           "\"iterations\":%llu,\"input_bytes\":%zu,\"input_scalars\":%zu,"
           "\"output_bytes_per_operation\":%lld,\"output_bytes\":%" PRIu64 ","
           "\"checksum\":\"%016" PRIx64 "\",\"cpu_seconds\":%.12f,"
           "\"cpu_clock\":\"%s\",\"clock_resolution_seconds\":%.12f,"
           "\"utf8proc_version\":\"%s\",\"unicode_version\":\"%s\"}\n",
           variant, operation, name, iterations, input.length, input.scalars,
           bytes_per_operation, output_bytes, checksum, elapsed, clock_name,
           clock_resolution, utf8proc_version(), utf8proc_unicode_version());
    free(input.bytes);
    return 0;
}
