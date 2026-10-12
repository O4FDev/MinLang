#ifndef MINYAR_COMPRESSION_H
#define MINYAR_COMPRESSION_H
#include "../minyar_native.h"
#include <limits.h>
#include <stdint.h>
/* Integer results: length >= 0, otherwise a stable diagnostic tag. */
enum { MC_INVALID=-1, MC_LIMIT=-2, MC_TRUNCATED=-3, MC_CORRUPT=-4,
       MC_DICTIONARY=-5, MC_MEMORY=-6, MC_CLOSED=-7, MC_TRAILING=-8 };
#define MC_MAX_OUTPUT (256LL * 1024 * 1024)
#ifndef MINYAR_COMPRESSION_CHUNK
#define MINYAR_COMPRESSION_CHUNK UINT_MAX
#endif
#if MINYAR_COMPRESSION_CHUNK < 1 || MINYAR_COMPRESSION_CHUNK > UINT_MAX
#error MINYAR_COMPRESSION_CHUNK must be in 1..UINT_MAX
#endif
static inline int mc_range(long long address, long long size) {
    return size >= 0 && address >= 0 && (size == 0 || address != 0) &&
           (uint64_t)size <= (uint64_t)INTPTR_MAX - (uint64_t)address;
}
static inline int mc_ranges(long long src, long long n, long long dst, long long cap) {
    if (!mc_range(src, n) || !mc_range(dst, cap) || cap > MC_MAX_OUTPUT) return 0;
    return !n || !cap || (uint64_t)src + (uint64_t)n <= (uint64_t)dst ||
           (uint64_t)dst + (uint64_t)cap <= (uint64_t)src;
}
static inline long long mc_addr(const void *p) { return (long long)(intptr_t)p; }
static inline size_t mc_chunk(size_t n) {
    return n < MINYAR_COMPRESSION_CHUNK ? n : MINYAR_COMPRESSION_CHUNK;
}
long long minyar_zstd_rawCreateCCtx(void);
long long minyar_zstd_rawCreateDCtx(void);
void minyar_zstd_rawCloseCCtx(long long);
void minyar_zstd_rawCloseDCtx(long long);
long long minyar_zstd_rawCompressCtx(long long, long long, long long, long long, long long, long long);
long long minyar_zstd_rawDecompressCtx(long long, long long, long long, long long, long long);
long long minyar_zstd_rawCreateCDict(long long, long long, long long);
long long minyar_zstd_rawCreateDDict(long long, long long);
void minyar_zstd_rawCloseCDict(long long);
void minyar_zstd_rawCloseDDict(long long);
long long minyar_zstd_rawCompressDict(long long, long long, long long, long long, long long, long long);
long long minyar_zstd_rawDecompressDict(long long, long long, long long, long long, long long, long long);
long long minyar_deflate_rawCompress(long long, long long, long long, long long, long long, long long);
long long minyar_deflate_rawDecompress(long long, long long, long long, long long, long long);
#endif
