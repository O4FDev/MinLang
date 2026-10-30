/* checksum.crc32c: the hardware path (when this processor has it), the slicing-by-8 path and a bitwise oracle
 * agree on RFC 3720 vectors and on every alignment and length class, including the three-chain block sizes. */
#define MINYAR_SYSTEM_HEAP 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>

static uint32_t oracle(uint32_t crc, const unsigned char *p, size_t n) {
    crc = ~crc;
    while (n--) {
        crc ^= *p++;
        for (int bit = 0; bit < 8; bit++)
            crc = crc & 1 ? (crc >> 1) ^ 0x82F63B78u : crc >> 1;
    }
    return ~crc;
}

static uint32_t software(uint32_t crc, const unsigned char *p, size_t n) {
    return ~crc32c_software(~crc, p, n);
}

int main(void) {
    static unsigned char data[3 * CRC32C_LONG * 2 + 4096];
    uint64_t seed = 88172645463325252ull;
    for (size_t i = 0; i < sizeof(data); i++) {
        seed ^= seed << 13;
        seed ^= seed >> 7;
        seed ^= seed << 17;
        data[i] = (unsigned char)seed;
    }
    unsigned char vector[32];
    memset(vector, 0, 32);
    assert(crc32c_update(0, vector, 32) == 0x8A9136AAu && software(0, vector, 32) == 0x8A9136AAu);
    memset(vector, 0xFF, 32);
    assert(crc32c_update(0, vector, 32) == 0x62A8AB43u && software(0, vector, 32) == 0x62A8AB43u);
    for (int i = 0; i < 32; i++) vector[i] = (unsigned char)i;
    assert(crc32c_update(0, vector, 32) == 0x46DD794Eu && software(0, vector, 32) == 0x46DD794Eu);
    assert(crc32c_update(0, (const unsigned char *)"123456789", 9) == 0xE3069283u);
    int hardware = 0;
#if defined(MINYAR_CRC32C_X86) || defined(MINYAR_CRC32C_ARM)
    hardware = crc32c_detect() == 1;
#endif
    size_t lengths[] = {0, 1, 7, 8, 9, 63, 64, 255, 256, 767, 768, 769, 1100, 4096, 3 * CRC32C_LONG - 1,
                        3 * CRC32C_LONG, 3 * CRC32C_LONG + 769, 2 * 3 * CRC32C_LONG + 1000};
    for (size_t offset = 0; offset < 16; offset++) {
        for (size_t k = 0; k < sizeof(lengths) / sizeof(lengths[0]); k++) {
            size_t n = lengths[k];
            uint32_t expected = oracle(0x1234u, data + offset, n);
            assert(software(0x1234u, data + offset, n) == expected);
            assert(crc32c_update(0x1234u, data + offset, n) == expected);
#if defined(MINYAR_CRC32C_X86) || defined(MINYAR_CRC32C_ARM)
            if (hardware) assert(~crc32c_hardware(~0x1234u, data + offset, n) == expected);
#endif
        }
    }
    MinyarBytes bytes = {data, (long long)sizeof(data), (long long)sizeof(data), NULL, NULL};
    assert(minyar_runtime_crc32c(-4294967296LL, &bytes, 5, 100) == (long long)oracle(0, data + 5, 100));
    assert(minyar_runtime_crc32c(0, &bytes, (long long)sizeof(data), 0) == 0);
    printf("crc32c: %s path, slicing-by-8 and bitwise oracle agree\n", hardware ? "hardware" : "software");
    return 0;
}
