/* Independent complete-operation oracle: maintained codecs, no binding calls. */
#define ZSTD_STATIC_LINKING_ONLY
#include <zstd.h>
#include <zlib.h>
#include <stddef.h>
#include <string.h>
long long reference_zstd_compress(const void *src, size_t n, void *dst, size_t cap) {
    size_t r = ZSTD_compress(dst, cap, src, n, 3);
    return ZSTD_isError(r) ? -1 : (long long)r;
}
long long reference_zstd_decompress(const void *src, size_t n, void *dst, size_t cap) {
    size_t r = ZSTD_decompress(dst, cap, src, n);
    return ZSTD_isError(r) ? -1 : (long long)r;
}
long long reference_dict_compress(const void *src, size_t n, void *dst, size_t cap, const void *dict, size_t dn) {
    ZSTD_CDict *cd = ZSTD_createCDict_advanced(dict, dn, ZSTD_dlm_byCopy, ZSTD_dct_rawContent,
                                             ZSTD_getCParams(3, 0, dn), ZSTD_defaultCMem);
    ZSTD_CCtx *c = ZSTD_createCCtx();
    size_t r = ZSTD_compress_usingCDict(c, dst, cap, src, n, cd);
    ZSTD_freeCCtx(c); ZSTD_freeCDict(cd);
    return ZSTD_isError(r) ? -1 : (long long)r;
}
long long reference_dict_decompress(const void *src, size_t n, void *dst, size_t cap, const void *dict, size_t dn) {
    ZSTD_DDict *dd = ZSTD_createDDict_advanced(dict, dn, ZSTD_dlm_byCopy, ZSTD_dct_rawContent, ZSTD_defaultCMem);
    ZSTD_DCtx *d = ZSTD_createDCtx();
    size_t r = ZSTD_decompress_usingDDict(d, dst, cap, src, n, dd);
    ZSTD_freeDCtx(d); ZSTD_freeDDict(dd);
    return ZSTD_isError(r) ? -1 : (long long)r;
}
long long reference_zstd_checksum(const void *src, size_t n, void *dst, size_t cap) {
    ZSTD_CCtx *c=ZSTD_createCCtx();
    size_t r=ZSTD_CCtx_setParameter(c,ZSTD_c_compressionLevel,3);
    if (!ZSTD_isError(r)) r=ZSTD_CCtx_setParameter(c,ZSTD_c_checksumFlag,1);
    if (!ZSTD_isError(r)) r=ZSTD_compress2(c,dst,cap,src,n);
    ZSTD_freeCCtx(c); return ZSTD_isError(r) ? -1 : (long long)r;
}
