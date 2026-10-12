/* Guarded raw ranges, exact cap trailers, by-copy raw magic and recovery. */
#include "../runtime/native/compression.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <zlib.h>
static long long address(void *p) { return (long long)(intptr_t)p; }
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
    puts("compression-native: ok");
}
