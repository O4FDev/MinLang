/* Complete gzip (including concatenation), zlib and raw DEFLATE operations. */
#include "compression.h"
#include <zlib.h>
static int window(long long format) { return format == 0 ? 31 : format == 1 ? 15 : -15; }
long long minyar_deflate_version(void) { return ZLIB_VERNUM; }
static long long zerror(int r) {
    return r == Z_MEM_ERROR ? MC_MEMORY : r == Z_NEED_DICT ? MC_DICTIONARY :
           r == Z_DATA_ERROR ? MC_CORRUPT : MC_INVALID;
}
long long minyar_deflate_rawCompress(long long src,long long n,long long dst,long long cap,long long format,long long level) {
    if (!mc_ranges(src,n,dst,cap) || format < 0 || format > 2 || level < -1 || level > 9) return MC_INVALID;
    z_stream z = {0};
    int r = deflateInit2(&z,(int)level,Z_DEFLATED,window(format),8,Z_DEFAULT_STRATEGY);
    if (r != Z_OK) return zerror(r);
    size_t at = 0, written = 0;
    long long result;
    unsigned char scratch;
    for (;;) {
        size_t in_size = mc_chunk((size_t)n-at), out_size = mc_chunk((size_t)cap-written);
        int probe = !out_size;
        z.next_in = in_size ? (Bytef *)(intptr_t)src + at : Z_NULL;
        z.avail_in = (uInt)in_size;
        z.next_out = probe ? &scratch : (Bytef *)(intptr_t)dst + written;
        z.avail_out = probe ? 1 : (uInt)out_size;
        r = deflate(&z, at + in_size == (size_t)n ? Z_FINISH : Z_NO_FLUSH);
        size_t consumed = in_size-z.avail_in, produced = (probe ? 1 : out_size)-z.avail_out;
        at += consumed;
        if (r != Z_OK && r != Z_STREAM_END && r != Z_BUF_ERROR) { result=zerror(r); break; }
        if (probe && produced) { result=MC_LIMIT; break; }
        written += produced;
        if (r == Z_STREAM_END) { result=(long long)written; break; }
        if (!consumed && !produced) { result=MC_LIMIT; break; }
    }
    deflateEnd(&z); return result;
}
long long minyar_deflate_rawDecompress(long long src,long long n,long long dst,long long cap,long long format) {
    if (!mc_ranges(src,n,dst,cap) || format < 0 || format > 2) return MC_INVALID;
    if (!n) return MC_TRUNCATED;
    z_stream z = {0};
    int r = inflateInit2(&z,window(format));
    if (r != Z_OK) return zerror(r);
    size_t at = 0, written = 0;
    long long result;
    unsigned char scratch;
    for (;;) {
        size_t in_size = mc_chunk((size_t)n-at), out_size = mc_chunk((size_t)cap-written);
        int probe = !out_size;
        z.next_in = in_size ? (Bytef *)(intptr_t)src + at : Z_NULL;
        z.avail_in = (uInt)in_size;
        z.next_out = probe ? &scratch : (Bytef *)(intptr_t)dst + written;
        z.avail_out = probe ? 1 : (uInt)out_size;
        r = inflate(&z,Z_NO_FLUSH);
        size_t consumed = in_size-z.avail_in, produced = (probe ? 1 : out_size)-z.avail_out;
        at += consumed;
        if (r != Z_OK && r != Z_STREAM_END && r != Z_BUF_ERROR) { result=zerror(r); break; }
        if (probe && produced) { result=MC_LIMIT; break; }
        written += produced;
        if (r == Z_STREAM_END) {
            if (at == (size_t)n) { result=(long long)written; break; }
            if (format != 0) { result=MC_TRAILING; break; }
            /* Empty remaining members still validate their header/CRC/ISIZE at exact cap. */
            r = inflateReset2(&z,31);
            if (r != Z_OK) { result=zerror(r); break; }
            continue;
        }
        if (!consumed && !produced) { result=at == (size_t)n ? MC_TRUNCATED : MC_CORRUPT; break; }
    }
    inflateEnd(&z); return result;
}
long long minyar_deflate_compressInto(const MinyarBytes *src,MinyarBytes *dst,long long format,long long level) {
    return minyar_deflate_rawCompress(mc_addr(src->bytes),src->byte_length,mc_addr(dst->bytes),dst->byte_length,format,level);
}
long long minyar_deflate_decompressInto(const MinyarBytes *src,MinyarBytes *dst,long long format) {
    return minyar_deflate_rawDecompress(mc_addr(src->bytes),src->byte_length,mc_addr(dst->bytes),dst->byte_length,format);
}
