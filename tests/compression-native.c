/* Guarded raw ranges, exact cap trailers, by-copy raw magic and recovery. */
#include "../runtime/native/compression.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <zlib.h>
static long long address(void *p) { return (long long)(intptr_t)p; }

static long long stream_step(int codec, long long owner, MinyarBytes *in, long long offset,
                             long long length, MinyarBytes *out, bool end) {
    return codec ? minyar_zstd_processStream(owner, in, offset, length, out, end)
                 : minyar_deflate_processStream(owner, in, offset, length, out, end);
}
static long long stream_consumed(int codec, long long owner) {
    return codec ? minyar_zstd_streamConsumed(owner) : minyar_deflate_streamConsumed(owner);
}
static long long stream_written(int codec, long long owner) {
    return codec ? minyar_zstd_streamWritten(owner) : minyar_deflate_streamWritten(owner);
}
static bool stream_end(int codec, long long owner) {
    return codec ? minyar_zstd_streamEnded(owner) : minyar_deflate_streamEnded(owner);
}
static void streaming_large(int codec) {
    unsigned char input[65536], destination[65538];
    unsigned char *encoded = malloc(2097152); assert(encoded);
    memset(input, 42, sizeof(input));
    MinyarBytes in = {input, sizeof(input), 0, NULL, NULL};
    MinyarBytes out = {destination + 1, 65536, 0, NULL, NULL};
    long long owner = codec ? minyar_zstd_newStream(true, 3) : minyar_deflate_newStream(true, 0, 1);
    assert(owner);
#if MINYAR_COMPRESSION_CHUNK == UINT_MAX
    const int rounds = 4608;
#else
    const int rounds = 2;
#endif
    size_t packed = 0;
    for (int i = 0; i < rounds; i++) {
        long long at = 0;
        while (at < (long long)sizeof(input)) {
            destination[0] = destination[65537] = 0xa5;
            assert(!stream_step(codec, owner, &in, at, sizeof(input) - at, &out, false));
            long long used = stream_consumed(codec, owner), made = stream_written(codec, owner);
            assert(used >= 0 && used <= (long long)sizeof(input) - at && made >= 0 && made <= 65536);
            assert(used || made); assert(destination[0] == 0xa5 && destination[65537] == 0xa5);
            at += used; assert(packed + (size_t)made <= 2097152);
            memcpy(encoded + packed, destination + 1, (size_t)made); packed += (size_t)made;
        }
    }
    while (!stream_end(codec, owner)) {
        assert(!stream_step(codec, owner, &in, 0, 0, &out, true));
        long long made = stream_written(codec, owner);
        assert(made || stream_end(codec, owner)); assert(packed + (size_t)made <= 2097152);
        memcpy(encoded + packed, destination + 1, (size_t)made); packed += (size_t)made;
    }
    if (codec) minyar_zstd_freeStream(owner); else minyar_deflate_freeStream(owner);
    owner = codec ? minyar_zstd_newStream(false, 0) : minyar_deflate_newStream(false, 0, 0);
    assert(owner);
    in.bytes = encoded; in.byte_length = (long long)packed;
    size_t position = 0, decoded = 0;
    while (!stream_end(codec, owner)) {
        size_t count = packed - position; if (count > 8192) count = 8192;
        destination[0] = destination[65537] = 0xa5;
        assert(!stream_step(codec, owner, &in, (long long)position, (long long)count, &out, position + count == packed));
        long long used = stream_consumed(codec, owner), made = stream_written(codec, owner);
        assert(used >= 0 && used <= (long long)count && made >= 0 && made <= 65536);
        assert(used || made || stream_end(codec, owner));
        assert(destination[0] == 0xa5 && destination[65537] == 0xa5);
        assert(!memcmp(input, destination + 1, (size_t)made));
        position += (size_t)used; decoded += (size_t)made;
    }
    assert(position == packed && decoded == (size_t)rounds * sizeof(input));
    if (codec) minyar_zstd_freeStream(owner); else minyar_deflate_freeStream(owner);
    free(encoded);
}
int main(void) {
    unsigned char src[128], packed[512], guarded[130];
    memset(src, 'x', sizeof(src));
    for (int format = 0; format < 3; ++format) {
        long long n = minyar_deflate_rawCompress(address(src), 128, address(packed), 512, format, 6);
        assert(n > 0);
        memset(guarded, 0xa5, sizeof(guarded));
        assert(minyar_deflate_rawDecompress(address(packed), n, address(guarded + 1), 128, format) == 128);
        assert(guarded[0] == 0xa5 && guarded[129] == 0xa5);
        assert(memcmp(src, guarded + 1, 128) == 0);
        assert(minyar_deflate_rawDecompress(address(packed), n, address(guarded + 1), 127, format) == MC_LIMIT);
        assert(guarded[128] == 'x');
        assert(minyar_deflate_rawDecompress(address(packed), n - 1, address(guarded + 1), 128, format) == MC_TRUNCATED);
        if (format != 2) {
            packed[n - 1] ^= 0x80;
            assert(minyar_deflate_rawDecompress(address(packed), n, address(guarded + 1), 128, format) == MC_CORRUPT);
        }
    }
    long long c = minyar_zstd_rawCreateCCtx(), d = minyar_zstd_rawCreateDCtx();
    assert(c && d);
    long long n = minyar_zstd_rawCompressCtx(c, address(src), 128, address(packed), 512, 3);
    assert(n > 0);
    assert(minyar_zstd_rawDecompressCtx(d, address(packed), n - 1, address(guarded + 1), 128) == MC_TRUNCATED);
    assert(minyar_zstd_rawDecompressCtx(d, address(packed), n, address(guarded + 1), 127) == MC_LIMIT);
    assert(minyar_zstd_rawDecompressCtx(d, address(packed), n, address(guarded + 1), 128) == 128);
    assert(minyar_zstd_rawDecompressCtx(d, address(packed), n, address(packed), 512) == MC_INVALID);
    assert(minyar_zstd_rawDecompressCtx(d, -1, n, address(guarded), 128) == MC_INVALID);
    assert(minyar_zstd_rawDecompressCtx(d, address(packed), n, INT64_MAX, 128) == MC_INVALID);
    assert(minyar_zstd_rawDecompressCtx(0, address(packed), n, address(guarded), 128) == MC_CLOSED);
    // Close dictionary immediately after an incomplete operation, then recover
    // the same context using no dictionary. No retained pointer may be dereferenced.
    unsigned char dictionary[128]; memset(dictionary,'x',sizeof(dictionary));
    long long cd=minyar_zstd_rawCreateCDict(address(dictionary),128,3);
    long long dd=minyar_zstd_rawCreateDDict(address(dictionary),128);
    assert(cd && dd);
    n=minyar_zstd_rawCompressDict(c,cd,address(src),128,address(packed),512);
    assert(n > 0);
    assert(minyar_zstd_rawDecompressDict(d,dd,address(packed),n-1,address(guarded+1),128) < 0);
    minyar_zstd_rawCloseCDict(cd); minyar_zstd_rawCloseDDict(dd);
    n=minyar_zstd_rawCompressCtx(c,address(src),128,address(packed),512,3);
    assert(n > 0 && minyar_zstd_rawDecompressCtx(d,address(packed),n,address(guarded+1),128)==128);
    // Native sanitizer mutation cohort, guarded on both sides of output.
    unsigned state=5005;
    unsigned char valid[512], changed[512];
    for (int codec=0; codec<4; ++codec) {
        n = codec == 3 ? minyar_zstd_rawCompressCtx(c,address(src),128,address(valid),512,3)
                      : minyar_deflate_rawCompress(address(src),128,address(valid),512,codec,6);
        assert(n > 0);
        for (int sample=0; sample<1000; ++sample) {
            memcpy(changed,valid,(size_t)n);
            state=state*1664525u+1013904223u;
            size_t pos=state%(size_t)n;
            changed[pos]^=(unsigned char)(1u << ((state>>16)&7));
            size_t available=(size_t)n;
            if (sample%3==0) available=pos;
            memset(guarded,0xa5,sizeof(guarded));
            long long result=codec == 3 ? minyar_zstd_rawDecompressCtx(d,address(changed),(long long)available,address(guarded+1),128)
                                       : minyar_deflate_rawDecompress(address(changed),(long long)available,address(guarded+1),128,codec);
            assert(result <= 128);
            assert(guarded[0] == 0xa5 && guarded[129] == 0xa5);
        }
    }
    minyar_zstd_rawCloseCCtx(c); minyar_zstd_rawCloseDCtx(d);
    streaming_large(0); streaming_large(1);
    puts("compression-native: ok");
}
