#include "../runtime/minyar_native.h"
#include <limits.h>
#include <stdint.h>
#include <dlfcn.h>
#include <zlib.h>

typedef long long (*Raw0)(void);
typedef long long (*Raw2)(long long, long long);
typedef long long (*Raw3)(long long, long long, long long);
typedef long long (*Raw4)(long long, long long, long long, long long);
typedef long long (*Raw5)(long long, long long, long long, long long, long long);
typedef long long (*Raw6)(long long, long long, long long, long long, long long, long long);
typedef void (*Close1)(long long);
typedef long long (*Reference4)(const void *, size_t, void *, size_t);
typedef long long (*Reference6)(const void *, size_t, void *, size_t, const void *, size_t);
static void *library;
static void *symbol(const char *name) {
    if (!library) abort();
    void *value = dlsym(library, name);
    if (!value) abort();
    return value;
}
long long minyar_codecoracle_open(const MinyarText *path) {
    if (library) { if (dlclose(library)) return -1; library = NULL; }
    char *name = malloc((size_t)path->byte_length + 1);
    if (!name) abort();
    memcpy(name, path->bytes, (size_t)path->byte_length);
    name[path->byte_length] = 0;
    library = dlopen(name, RTLD_NOW | RTLD_LOCAL);
    free(name);
    return library ? 0 : -1;
}
long long minyar_codecoracle_close(void) {
    if (!library) return -1;
    int result = dlclose(library);
    library = NULL;
    return result;
}
long long minyar_codecoracle_rawCompress(long long src, long long n, long long dst, long long cap, long long format, long long level) {
    return ((Raw6)symbol("minyar_deflate_rawCompress"))(src, n, dst, cap, format, level);
}
long long minyar_codecoracle_rawDecompress(long long src, long long n, long long dst, long long cap, long long format) {
    return ((Raw5)symbol("minyar_deflate_rawDecompress"))(src, n, dst, cap, format);
}
long long minyar_codecoracle_rawZCompress(long long src, long long n, long long dst, long long cap, long long level) {
    return ((Raw5)symbol("minyar_zstd_rawCompress"))(src, n, dst, cap, level);
}
long long minyar_codecoracle_rawZDecompress(long long src, long long n, long long dst, long long cap) {
    return ((Raw4)symbol("minyar_zstd_rawDecompress"))(src, n, dst, cap);
}
long long minyar_codecoracle_createCCtx(void) { return ((Raw0)symbol("minyar_zstd_rawCreateCCtx"))(); }
long long minyar_codecoracle_createDCtx(void) { return ((Raw0)symbol("minyar_zstd_rawCreateDCtx"))(); }
long long minyar_codecoracle_createCDict(long long src, long long n, long long level) { return ((Raw3)symbol("minyar_zstd_rawCreateCDict"))(src, n, level); }
long long minyar_codecoracle_createDDict(long long src, long long n) { return ((Raw2)symbol("minyar_zstd_rawCreateDDict"))(src, n); }
void minyar_codecoracle_closeCCtx(long long handle) { ((Close1)symbol("minyar_zstd_rawCloseCCtx"))(handle); }
void minyar_codecoracle_closeDCtx(long long handle) { ((Close1)symbol("minyar_zstd_rawCloseDCtx"))(handle); }
void minyar_codecoracle_closeCDict(long long handle) { ((Close1)symbol("minyar_zstd_rawCloseCDict"))(handle); }
void minyar_codecoracle_closeDDict(long long handle) { ((Close1)symbol("minyar_zstd_rawCloseDDict"))(handle); }
long long minyar_codecoracle_rawDictCompress(long long handle, long long dictionary, long long src, long long n, long long dst, long long cap) { return ((Raw6)symbol("minyar_zstd_rawCompressDict"))(handle, dictionary, src, n, dst, cap); }
long long minyar_codecoracle_rawDictDecompress(long long handle, long long dictionary, long long src, long long n, long long dst, long long cap) { return ((Raw6)symbol("minyar_zstd_rawDecompressDict"))(handle, dictionary, src, n, dst, cap); }

long long minyar_codecoracle_zcompress(long long src, long long n, long long dst, long long cap) {
    return ((Reference4)symbol("reference_zstd_compress"))((void *)(intptr_t)src, (size_t)n, (void *)(intptr_t)dst, (size_t)cap);
}
long long minyar_codecoracle_zdecompress(long long src, long long n, long long dst, long long cap) {
    return ((Reference4)symbol("reference_zstd_decompress"))((void *)(intptr_t)src, (size_t)n, (void *)(intptr_t)dst, (size_t)cap);
}
long long minyar_codecoracle_dictCompress(long long src, long long n, long long dst, long long cap, long long dictionary, long long dn) {
    return ((Reference6)symbol("reference_dict_compress"))((void *)(intptr_t)src, (size_t)n, (void *)(intptr_t)dst, (size_t)cap, (void *)(intptr_t)dictionary, (size_t)dn);
}
long long minyar_codecoracle_dictDecompress(long long src, long long n, long long dst, long long cap, long long dictionary, long long dn) {
    return ((Reference6)symbol("reference_dict_decompress"))((void *)(intptr_t)src, (size_t)n, (void *)(intptr_t)dst, (size_t)cap, (void *)(intptr_t)dictionary, (size_t)dn);
}
long long minyar_codecoracle_checksum(long long src, long long n, long long dst, long long cap) {
    return ((Reference4)symbol("reference_zstd_checksum"))((void *)(intptr_t)src, (size_t)n, (void *)(intptr_t)dst, (size_t)cap);
}
MinyarBytes *minyar_codecoracle_compress(const MinyarBytes *input, long long format, long long level, const MinyarBytes *dictionary) {
    if (input->byte_length < 0 || (unsigned long long)input->byte_length > UINT_MAX || dictionary->byte_length < 0 || (unsigned long long)dictionary->byte_length > UINT_MAX) abort();
    z_stream stream = {0};
    int window = format == 0 ? 31 : format == 1 ? 15 : -15;
    if (deflateInit2(&stream, (int)level, Z_DEFLATED, window, 8, Z_DEFAULT_STRATEGY) != Z_OK) abort();
    if (dictionary->byte_length && deflateSetDictionary(&stream, dictionary->bytes, (uInt)dictionary->byte_length) != Z_OK) abort();
    uLong bound = deflateBound(&stream, (uLong)input->byte_length);
    if (bound > UINT_MAX) abort();
    MinyarBytes *result = minyar_bytes_new((long long)bound);
    stream.next_in = (Bytef *)input->bytes;
    stream.avail_in = (uInt)input->byte_length;
    stream.next_out = (Bytef *)result->bytes;
    stream.avail_out = (uInt)bound;
    if (deflate(&stream, Z_FINISH) != Z_STREAM_END) abort();
    result->byte_length = (long long)stream.total_out;
    if (deflateEnd(&stream) != Z_OK) abort();
    return result;
}
static long long inflate_status;
MinyarBytes *minyar_codecoracle_inflate(const MinyarBytes *input, long long format) {
    if (input->byte_length < 0 || (unsigned long long)input->byte_length > UINT_MAX) abort();
    z_stream stream = {0};
    int window = format == 0 ? 31 : format == 1 ? 15 : -15;
    inflate_status = -1;
    MinyarBytes *result = minyar_bytes_new(0);
    if (inflateInit2(&stream, window) != Z_OK) return result;
    stream.next_in = (Bytef *)input->bytes;
    stream.avail_in = (uInt)input->byte_length;
    for (;;) {
        unsigned char *next = minyar_bytes_extend(result, 8192);
        stream.next_out = next;
        stream.avail_out = 8192;
        int status = inflate(&stream, Z_NO_FLUSH);
        result->byte_length -= stream.avail_out;
        if (status == Z_STREAM_END) { inflate_status = (long long)stream.total_out; break; }
        if (status != Z_OK || stream.avail_out) { result->byte_length = 0; break; }
    }
    inflateEnd(&stream);
    return result;
}
long long minyar_codecoracle_inflateStatus(void) { return inflate_status; }
long long minyar_codecoracle_crc32(const MinyarBytes *input) {
    if (input->byte_length < 0 || (unsigned long long)input->byte_length > UINT_MAX) abort();
    return (long long)crc32(0, input->bytes, (uInt)input->byte_length);
}
