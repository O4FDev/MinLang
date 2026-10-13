#include "../runtime/minyar_native.h"
#include <limits.h>
#include <openssl/sha.h>
#include <zlib.h>
#include <zstd.h>

MinyarBytes *minyar_formatstest_digest(const MinyarBytes *input) {
    MinyarBytes *result = minyar_bytes_new(32);
    SHA256(input->bytes, (size_t)input->byte_length, (unsigned char *)result->bytes);
    return result;
}

long long minyar_formatstest_gunzip(const MinyarBytes *input, MinyarBytes *output) {
    if (input->byte_length < 0 || output->byte_length < 0 ||
        (unsigned long long)input->byte_length > UINT_MAX ||
        (unsigned long long)output->byte_length > UINT_MAX) return -1;
    z_stream stream;
    memset(&stream, 0, sizeof(stream));
    stream.next_in = (Bytef *)input->bytes;
    stream.avail_in = (uInt)input->byte_length;
    stream.next_out = (Bytef *)output->bytes;
    stream.avail_out = (uInt)output->byte_length;
    if (inflateInit2(&stream, 31) != Z_OK) return -1;
    int status = inflate(&stream, Z_FINISH);
    long long produced = (long long)stream.total_out;
    int complete = status == Z_STREAM_END && stream.total_in == (uLong)input->byte_length;
    inflateEnd(&stream);
    return complete ? produced : -1;
}

long long minyar_formatstest_unzstd(const MinyarBytes *input, MinyarBytes *output) {
    if (input->byte_length < 0 || output->byte_length < 0) return -1;
    size_t decoded = ZSTD_decompress((void *)output->bytes, (size_t)output->byte_length, input->bytes, (size_t)input->byte_length);
    return ZSTD_isError(decoded) ? -1 : (long long)decoded;
}
