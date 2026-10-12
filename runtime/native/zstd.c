/* Advanced raw/by-copy dictionary APIs require a matched STATIC provider. */
#define ZSTD_STATIC_LINKING_ONLY
#include <zstd.h>
#include <zstd_errors.h>
#include "compression.h"
static long long zerror(size_t r) {
    switch (ZSTD_getErrorCode(r)) {
    case ZSTD_error_memory_allocation: return MC_MEMORY;
    case ZSTD_error_dstSize_tooSmall:
    case ZSTD_error_frameParameter_windowTooLarge: return MC_LIMIT;
    case ZSTD_error_srcSize_wrong: return MC_TRUNCATED;
    case ZSTD_error_dictionary_corrupted:
    case ZSTD_error_dictionary_wrong: return MC_DICTIONARY;
    case ZSTD_error_parameter_outOfBound:
    case ZSTD_error_parameter_unsupported: return MC_INVALID;
    default: return MC_CORRUPT;
    }
}
long long minyar_zstd_version(void) { return ZSTD_versionNumber(); }
long long minyar_zstd_rawCreateCCtx(void) { return mc_addr(ZSTD_createCCtx()); }
long long minyar_zstd_rawCreateDCtx(void) { return mc_addr(ZSTD_createDCtx()); }
void minyar_zstd_rawCloseCCtx(long long h) { ZSTD_freeCCtx((ZSTD_CCtx *)(intptr_t)h); }
void minyar_zstd_rawCloseDCtx(long long h) { ZSTD_freeDCtx((ZSTD_DCtx *)(intptr_t)h); }
long long minyar_zstd_rawCreateCDict(long long src, long long n, long long level) {
    if (!mc_range(src, n) || n > MC_MAX_OUTPUT || level < ZSTD_minCLevel() || level > ZSTD_maxCLevel()) return 0;
    return mc_addr(ZSTD_createCDict_advanced((const void *)(intptr_t)src, (size_t)n,
        ZSTD_dlm_byCopy, ZSTD_dct_rawContent, ZSTD_getCParams((int)level, 0, (size_t)n), ZSTD_defaultCMem));
}
long long minyar_zstd_rawCreateDDict(long long src, long long n) {
    if (!mc_range(src, n) || n > MC_MAX_OUTPUT) return 0;
    return mc_addr(ZSTD_createDDict_advanced((const void *)(intptr_t)src, (size_t)n,
        ZSTD_dlm_byCopy, ZSTD_dct_rawContent, ZSTD_defaultCMem));
}
long long minyar_zstd_newCDict(const MinyarBytes *b, long long level) {
    return minyar_zstd_rawCreateCDict(mc_addr(b->bytes), b->byte_length, level);
}
long long minyar_zstd_newDDict(const MinyarBytes *b) {
    return minyar_zstd_rawCreateDDict(mc_addr(b->bytes), b->byte_length);
}
void minyar_zstd_rawCloseCDict(long long h) { ZSTD_freeCDict((ZSTD_CDict *)(intptr_t)h); }
void minyar_zstd_rawCloseDDict(long long h) { ZSTD_freeDDict((ZSTD_DDict *)(intptr_t)h); }
long long minyar_zstd_compressBound(long long n) {
    if (n < 0 || n > MC_MAX_OUTPUT) return MC_INVALID;
    size_t r = ZSTD_compressBound((size_t)n);
    return r <= MC_MAX_OUTPUT && !ZSTD_isError(r) ? (long long)r : MC_INVALID;
}
static long long compress_ctx(long long h, long long dict, long long src, long long n,
                              long long dst, long long cap, long long level) {
    if (!mc_ranges(src,n,dst,cap) || level < ZSTD_minCLevel() || level > ZSTD_maxCLevel()) return MC_INVALID;
    if (!h) return MC_CLOSED;
    ZSTD_CCtx *c = (ZSTD_CCtx *)(intptr_t)h;
    size_t r = ZSTD_CCtx_reset(c, ZSTD_reset_session_and_parameters);
    if (ZSTD_isError(r)) return zerror(r);
    unsigned char dummy = 0;
    const void *s = n ? (const void *)(intptr_t)src : &dummy;
    void *out = cap ? (void *)(intptr_t)dst : &dummy;
    r = dict ? ZSTD_compress_usingCDict(c,out,(size_t)cap,s,(size_t)n,(ZSTD_CDict *)(intptr_t)dict)
             : ZSTD_compressCCtx(c,out,(size_t)cap,s,(size_t)n,(int)level);
    long long result = ZSTD_isError(r) ? zerror(r) : (long long)r;
    ZSTD_CCtx_reset(c,ZSTD_reset_session_and_parameters);
    return result;
}
long long minyar_zstd_rawCompressCtx(long long h, long long s, long long n, long long out, long long cap, long long level) {
    return compress_ctx(h,0,s,n,out,cap,level);
}
long long minyar_zstd_rawCompressDict(long long h, long long dict, long long s, long long n, long long out, long long cap) {
    if (!mc_ranges(s,n,out,cap)) return MC_INVALID;
    if (!dict) return MC_CLOSED;
    return compress_ctx(h,dict,s,n,out,cap,3);
}
static long long decompress_ctx(long long h, long long dict, long long src, long long n, long long dst, long long cap) {
    if (!mc_ranges(src,n,dst,cap)) return MC_INVALID;
    if (!h) return MC_CLOSED;
    if (!n) return MC_TRUNCATED;
    ZSTD_DCtx *d = (ZSTD_DCtx *)(intptr_t)h;
    size_t r = ZSTD_DCtx_reset(d,ZSTD_reset_session_and_parameters);
    if (!ZSTD_isError(r)) r = ZSTD_DCtx_setParameter(d,ZSTD_d_windowLogMax,27);
    if (!ZSTD_isError(r)) r = ZSTD_DCtx_refDDict(d,(ZSTD_DDict *)(intptr_t)dict);
    if (ZSTD_isError(r)) return zerror(r);
    size_t at = 0, written = 0;
    unsigned char scratch;
    long long result;
    for (;;) {
        ZSTD_inBuffer in = { (const unsigned char *)(intptr_t)src + at, mc_chunk((size_t)n-at), 0 };
        int probe = written == (size_t)cap;
        ZSTD_outBuffer out = { probe ? &scratch : (unsigned char *)(intptr_t)dst + written,
                              probe ? 1 : mc_chunk((size_t)cap-written), 0 };
        r = ZSTD_decompressStream(d,&out,&in);
        at += in.pos;
        if (ZSTD_isError(r)) { result=zerror(r); break; } /* observed error precedes probe overflow */
        if (probe && out.pos) { result=MC_LIMIT; break; }
        written += out.pos;
        if (!r && at == (size_t)n) { result=(long long)written; break; }
        if (!in.pos && !out.pos) { result=at == (size_t)n ? MC_TRUNCATED : MC_CORRUPT; break; }
    }
    ZSTD_DCtx_reset(d,ZSTD_reset_session_and_parameters);
    return result;
}
long long minyar_zstd_rawDecompressCtx(long long h, long long s, long long n, long long out, long long cap) {
    return decompress_ctx(h,0,s,n,out,cap);
}
long long minyar_zstd_rawDecompressDict(long long h, long long dict, long long s, long long n, long long out, long long cap) {
    if (!mc_ranges(s,n,out,cap)) return MC_INVALID;
    if (!dict) return MC_CLOSED;
    return decompress_ctx(h,dict,s,n,out,cap);
}
long long minyar_zstd_rawCompress(long long s,long long n,long long out,long long cap,long long level) {
    if (!mc_ranges(s,n,out,cap) || level < ZSTD_minCLevel() || level > ZSTD_maxCLevel()) return MC_INVALID;
    long long h = minyar_zstd_rawCreateCCtx();
    if (!h) return MC_MEMORY;
    long long r = minyar_zstd_rawCompressCtx(h,s,n,out,cap,level);
    minyar_zstd_rawCloseCCtx(h); return r;
}
long long minyar_zstd_rawDecompress(long long s,long long n,long long out,long long cap) {
    if (!mc_ranges(s,n,out,cap)) return MC_INVALID;
    long long h = minyar_zstd_rawCreateDCtx();
    if (!h) return MC_MEMORY;
    long long r = minyar_zstd_rawDecompressCtx(h,s,n,out,cap);
    minyar_zstd_rawCloseDCtx(h); return r;
}
long long minyar_zstd_bufferCompress(long long h,const MinyarBytes *s,MinyarBytes *out,long long level) {
    return minyar_zstd_rawCompressCtx(h,mc_addr(s->bytes),s->byte_length,mc_addr(out->bytes),out->byte_length,level);
}
long long minyar_zstd_bufferDecompress(long long h,const MinyarBytes *s,MinyarBytes *out) {
    return minyar_zstd_rawDecompressCtx(h,mc_addr(s->bytes),s->byte_length,mc_addr(out->bytes),out->byte_length);
}
long long minyar_zstd_bufferCompressDict(long long h,long long dict,const MinyarBytes *s,MinyarBytes *out) {
    return minyar_zstd_rawCompressDict(h,dict,mc_addr(s->bytes),s->byte_length,mc_addr(out->bytes),out->byte_length);
}
long long minyar_zstd_bufferDecompressDict(long long h,long long dict,const MinyarBytes *s,MinyarBytes *out) {
    return minyar_zstd_rawDecompressDict(h,dict,mc_addr(s->bytes),s->byte_length,mc_addr(out->bytes),out->byte_length);
}

typedef struct {
    ZSTD_CCtx *compressor;
    ZSTD_DCtx *decoder;
    size_t remaining;
    long long consumed, written, error;
    int ending, ended;
} ZstdStream;
long long minyar_zstd_newStream(bool compress, long long level) {
    if (compress && (level < ZSTD_minCLevel() || level > ZSTD_maxCLevel())) return 0;
    ZstdStream *s = calloc(1, sizeof(*s));
    if (!s) return 0;
    s->remaining = 1;
    if (compress) {
        s->compressor = ZSTD_createCCtx();
        if (!s->compressor || ZSTD_isError(ZSTD_CCtx_setParameter(s->compressor, ZSTD_c_compressionLevel, (int)level))) {
            ZSTD_freeCCtx(s->compressor); free(s); return 0;
        }
    } else {
        s->decoder = ZSTD_createDCtx();
        if (!s->decoder) { free(s); return 0; }
    }
    return mc_addr(s);
}
void minyar_zstd_freeStream(long long handle) {
    ZstdStream *s = (ZstdStream *)(intptr_t)handle;
    if (!s) return;
    ZSTD_freeCCtx(s->compressor); ZSTD_freeDCtx(s->decoder); free(s);
}
long long minyar_zstd_streamConsumed(long long handle) { return ((ZstdStream *)(intptr_t)handle)->consumed; }
long long minyar_zstd_streamWritten(long long handle) { return ((ZstdStream *)(intptr_t)handle)->written; }
bool minyar_zstd_streamEnded(long long handle) { return ((ZstdStream *)(intptr_t)handle)->ended != 0; }
long long minyar_zstd_processStream(long long handle, const MinyarBytes *input, long long offset,
                                   long long length, MinyarBytes *output, bool finish) {
    if (!handle) return MC_CLOSED;
    ZstdStream *s = (ZstdStream *)(intptr_t)handle;
    s->consumed = s->written = 0;
    if (s->error) return s->error;
    if (!input || !output || offset < 0 || length < 0 || offset > input->byte_length ||
        length > input->byte_length - offset || output->byte_length < 1 ||
        !mc_range(mc_addr(input->bytes), input->byte_length) ||
        !mc_stream_ranges(mc_addr(input->bytes) + offset, length, mc_addr(output->bytes), output->byte_length) ||
        (s->ending && !finish)) return MC_INVALID;
    if (s->ended) return length ? MC_TRAILING : 0;
    s->ending = finish;
    ZSTD_inBuffer in = {input->bytes + offset, (size_t)length, 0};
    ZSTD_outBuffer out = {(void *)output->bytes, (size_t)output->byte_length, 0};
    if (s->compressor) {
        s->remaining = ZSTD_compressStream2(s->compressor, &out, &in, finish ? ZSTD_e_end : ZSTD_e_continue);
        if (!ZSTD_isError(s->remaining) && finish && !s->remaining) s->ended = 1;
    } else {
        if (!length && finish && !s->remaining) s->ended = 1;
        while (!s->ended) {
            size_t before_in = in.pos, before_out = out.pos;
            s->remaining = ZSTD_decompressStream(s->decoder, &out, &in);
            if (ZSTD_isError(s->remaining)) break;
            if (in.pos == in.size && !s->remaining && finish) { s->ended = 1; break; }
            if (out.pos == out.size) break;
            if (in.pos == in.size) {
                if (finish && s->remaining) s->error = MC_TRUNCATED;
                break;
            }
            if (in.pos == before_in && out.pos == before_out) { s->error = MC_CORRUPT; break; }
        }
    }
    s->consumed = (long long)in.pos; s->written = (long long)out.pos;
    if (ZSTD_isError(s->remaining)) s->error = zerror(s->remaining);
    return s->error;
}
