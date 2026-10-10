/* Test-only RFC8032 seed: never a production update signing key. */
#include "../vendor/monocypher/monocypher-ed25519.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(int argc, char **argv) {
    assert(argc == 2);
    FILE *file = fopen(argv[1], "rb");
    assert(file);
    const unsigned char domain[] = "MINYAR-UPDATE-SIGNATURE-V1";
    unsigned char message[8192];
    memcpy(message, domain, sizeof(domain));
    size_t count = fread(message + sizeof(domain), 1, sizeof(message) - sizeof(domain), file);
    assert(!ferror(file) && feof(file));
    fclose(file);
    unsigned char seed[32] = {0x9d, 0x61, 0xb1, 0x9d, 0xef, 0xfd, 0x5a, 0x60, 0xba, 0x84, 0x4a,
                              0xf4, 0x92, 0xec, 0x2c, 0xc4, 0x44, 0x49, 0xc5, 0x69, 0x7b, 0x32,
                              0x69, 0x19, 0x70, 0x3b, 0xac, 0x03, 0x1c, 0xae, 0x7f, 0x60};
    unsigned char sk[64], pk[32], signature[64];
    crypto_ed25519_key_pair(sk, pk, seed);
    crypto_ed25519_sign(signature, sk, message, sizeof(domain) + count);
    assert(fwrite(signature, 1, sizeof(signature), stdout) == sizeof(signature));
    return 0;
}
