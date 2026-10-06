// Test-only wrappers count save-module requests and call the frozen runtime.
#include "../runtime/minyar_native.h"

MinyarBytes *minyar_read_bytes_file(const MinyarText *path);
void minyar_write_bytes_file(const MinyarText *path, const MinyarBytes *bytes);

static long long read_calls;
static long long write_calls;
static long long read_bytes;
static long long write_bytes;

static void report_counts(void) {
    printf("{\"save_read_calls\":%lld,\"save_write_calls\":%lld,"
           "\"save_read_bytes\":%lld,\"save_write_bytes\":%lld}\n",
           read_calls, write_calls, read_bytes, write_bytes);
}

void minyar_round5_begin(void) {
    if (atexit(report_counts) != 0) {
        exit(92);
    }
}

MinyarBytes *minyar_round5_save_read(const MinyarText *path) {
    read_calls++;
    MinyarBytes *result = minyar_read_bytes_file(path);
    read_bytes += result->byte_length;
    return result;
}

void minyar_round5_save_write(const MinyarText *path, const MinyarBytes *bytes) {
    write_calls++;
    write_bytes += bytes->byte_length;
    minyar_write_bytes_file(path, bytes);
}
