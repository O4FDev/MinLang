#define OPENSSL_SUPPRESS_DEPRECATED
#include <openssl/sha.h>
#include <openssl/crypto.h>
#include <string.h>
_Static_assert(sizeof(void *) == 8, "64-bit provider required");
int main(void) {
    SHA256_CTX state;
    unsigned char digest[32];
    static const unsigned char expected[32] = {
        0xba,0x78,0x16,0xbf,0x8f,0x01,0xcf,0xea,
        0x41,0x41,0x40,0xde,0x5d,0xae,0x22,0x23,
        0xb0,0x03,0x61,0xa3,0x96,0x17,0x7a,0x9c,
        0xb4,0x10,0xff,0x61,0xf2,0x00,0x15,0xad
    };
    if (OpenSSL_version_num() != OPENSSL_VERSION_NUMBER) return 1;
    if (!SHA256_Init(&state) || !SHA256_Update(&state, "abc", 3) || !SHA256_Final(digest, &state)) return 2;
    return memcmp(digest, expected, 32) != 0;
}
