/* Non-timing Linux link-wrapper probe adapted from completed review r1.
 * Counts owned output copies without changing allocations or return values.
 */
#include "../runtime/minyar_native.h"
#include <stdint.h>
extern MinyarBytes *__real_minyar_bytes_slice(const MinyarBytes *,long long,long long);
extern unsigned char *__real_minyar_bytes_extend(MinyarBytes *,long long);
static uint64_t slice_calls,slice_bytes,large_slices,large_slice_bytes;
static uint64_t extend_calls,extend_bytes,large_extends,large_extend_bytes;
MinyarBytes *__wrap_minyar_bytes_slice(const MinyarBytes *b,long long start,long long end) {
    slice_calls++; slice_bytes+=(uint64_t)(end-start);
    if (end-start>=1048576) { large_slices++; large_slice_bytes+=(uint64_t)(end-start); }
    return __real_minyar_bytes_slice(b,start,end);
}
unsigned char *__wrap_minyar_bytes_extend(MinyarBytes *b,long long n) {
    extend_calls++; extend_bytes+=(uint64_t)n;
    if (n>=1048576) { large_extends++; large_extend_bytes+=(uint64_t)n; }
    return __real_minyar_bytes_extend(b,n);
}
__attribute__((destructor)) static void report(void) {
    fprintf(stderr,"{\"slice_calls\":%llu,\"slice_bytes\":%llu,\"large_slices\":%llu,\"large_slice_bytes\":%llu,\"extend_calls\":%llu,\"extend_bytes\":%llu,\"large_extends\":%llu,\"large_extend_bytes\":%llu}\n",
            (unsigned long long)slice_calls,(unsigned long long)slice_bytes,(unsigned long long)large_slices,(unsigned long long)large_slice_bytes,
            (unsigned long long)extend_calls,(unsigned long long)extend_bytes,(unsigned long long)large_extends,(unsigned long long)large_extend_bytes);
}
