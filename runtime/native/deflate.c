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

typedef struct {
    z_stream codec;
    long long consumed, written, error;
    int compress, format, boundary, ending, ended;
} DeflateStream;
long long minyar_deflate_newStream(bool compress, long long format, long long level) {
    if (format < 0 || format > 2 || (compress && (level < -1 || level > 9))) return 0;
    DeflateStream *s = calloc(1, sizeof(*s));
    if (!s) return 0;
    s->compress = compress; s->format = (int)format;
    int r = compress ? deflateInit2(&s->codec, (int)level, Z_DEFLATED, window(format), 8, Z_DEFAULT_STRATEGY)
                     : inflateInit2(&s->codec, window(format));
    if (r != Z_OK) { free(s); return 0; }
    return mc_addr(s);
}
void minyar_deflate_freeStream(long long handle) {
    DeflateStream *s = (DeflateStream *)(intptr_t)handle;
    if (!s) return;
    if (s->compress) deflateEnd(&s->codec); else inflateEnd(&s->codec);
    free(s);
}
long long minyar_deflate_streamConsumed(long long handle) { return ((DeflateStream *)(intptr_t)handle)->consumed; }
long long minyar_deflate_streamWritten(long long handle) { return ((DeflateStream *)(intptr_t)handle)->written; }
bool minyar_deflate_streamEnded(long long handle) { return ((DeflateStream *)(intptr_t)handle)->ended != 0; }
long long minyar_deflate_processStream(long long handle, const MinyarBytes *input, long long offset,
                                      long long length, MinyarBytes *output, bool finish) {
    if (!handle) return MC_CLOSED;
    DeflateStream *s = (DeflateStream *)(intptr_t)handle;
    s->consumed = s->written = 0;
    if (s->error) return s->error;
    if (!input || !output || offset < 0 || length < 0 || offset > input->byte_length ||
        length > input->byte_length - offset || output->byte_length < 1 ||
        !mc_range(mc_addr(input->bytes), input->byte_length) ||
        !mc_stream_ranges(mc_addr(input->bytes) + offset, length, mc_addr(output->bytes), output->byte_length) ||
        (s->ending && !finish)) return MC_INVALID;
    if (s->ended) return length ? MC_TRAILING : 0;
    s->ending = finish;
    z_stream *z = &s->codec;
    size_t at = 0, written = 0;
    for (;;) {
        if (s->boundary) {
            if (at == (size_t)length) { if (finish) s->ended = 1; break; }
            if (s->format != 0) { s->error = MC_TRAILING; break; }
            int r = inflateReset2(z, 31);
            if (r != Z_OK) { s->error = zerror(r); break; }
            s->boundary = 0;
        }
        size_t ni = mc_chunk((size_t)length - at), no = mc_chunk((size_t)output->byte_length - written);
        z->next_in = (Bytef *)input->bytes + offset + at; z->avail_in = (uInt)ni;
        z->next_out = (Bytef *)output->bytes + written; z->avail_out = (uInt)no;
        int r = s->compress ? deflate(z, finish && at + ni == (size_t)length ? Z_FINISH : Z_NO_FLUSH)
                            : inflate(z, Z_NO_FLUSH);
        size_t used = ni - z->avail_in, made = no - z->avail_out;
        at += used; written += made;
        if (r != Z_OK && r != Z_STREAM_END && r != Z_BUF_ERROR) { s->error = zerror(r); break; }
        if (r == Z_STREAM_END) {
            if (s->compress) { s->ended = 1; break; }
            s->boundary = 1;
            if (at == (size_t)length) { if (finish) s->ended = 1; break; }
            if (s->format != 0) { s->error = MC_TRAILING; break; }
        }
        if (written == (size_t)output->byte_length) break;
        if (!used && !made) {
            if (finish) s->error = s->compress ? MC_INVALID : MC_TRUNCATED;
            break;
        }
        if (!finish && at == (size_t)length && !s->boundary) break;
    }
    s->consumed = (long long)at; s->written = (long long)written;
    z->next_in = Z_NULL; z->avail_in = 0; z->next_out = Z_NULL; z->avail_out = 0;
    return s->error;
}
