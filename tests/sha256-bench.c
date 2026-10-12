#define _POSIX_C_SOURCE 200809L
#include <openssl/evp.h>
#include <openssl/sha.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#ifdef _WIN32
#include <windows.h>
#endif
#if defined(SHA256_PORTABLE_MBEDTLS)
#include "mbedtls/sha256.h"
#endif

static uint64_t nanos(void) {
#ifdef _WIN32
    LARGE_INTEGER now, frequency;
    if (!QueryPerformanceCounter(&now) || !QueryPerformanceFrequency(&frequency)) abort();
    return (uint64_t)(now.QuadPart / frequency.QuadPart) * 1000000000 +
        (uint64_t)(now.QuadPart % frequency.QuadPart) * 1000000000 / (uint64_t)frequency.QuadPart;
#else
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now)) abort();
    return (uint64_t)now.tv_sec * 1000000000 + (uint64_t)now.tv_nsec;
#endif
}
int main(int argc, char **argv) {
    if (argc != 5) return 2;
    size_t length = (size_t)strtoull(argv[1], NULL, 10);
    size_t iterations = (size_t)strtoull(argv[2], NULL, 10);
    int stream = !strcmp(argv[3], "lifecycle");
    int evp = !strcmp(argv[4], "evp");
    unsigned char *data = malloc(length ? length : 1), out[32], snapshot[32], fork[32];
    if (!data) abort();
    for (size_t i = 0; i < length; ++i) data[i] = (unsigned char)(i * 31 + 17);
    uint64_t sum = 0, start = nanos();
    for (size_t iteration = 0; iteration < iterations; ++iteration) {
        size_t prefix = length / 2;
#if defined(SHA256_PORTABLE_MBEDTLS)
        mbedtls_sha256_context state, branch, snap;
        mbedtls_sha256_init(&state);
        mbedtls_sha256_starts(&state, 0);
        mbedtls_sha256_update(&state, data, stream ? prefix : length);
        if (stream) {
            mbedtls_sha256_clone(&snap, &state);
            mbedtls_sha256_finish(&snap, snapshot);
            sum += snapshot[0];
            mbedtls_sha256_free(&snap);
            mbedtls_sha256_clone(&branch, &state);
            for (size_t at = prefix; at < length;) {
                size_t chunk = length - at < 65536 ? length - at : 65536;
                mbedtls_sha256_update(&state, data + at, chunk);
                mbedtls_sha256_update(&branch, data + at, chunk);
                at += chunk;
            }
            mbedtls_sha256_clone(&snap, &branch);
            mbedtls_sha256_finish(&snap, fork);
            mbedtls_sha256_free(&snap);
            sum += fork[0];
            mbedtls_sha256_free(&branch);
        }
        mbedtls_sha256_clone(&snap, &state);
        mbedtls_sha256_finish(&snap, out);
        mbedtls_sha256_free(&snap);
        mbedtls_sha256_free(&state);
#else
        if (evp) {
            EVP_MD_CTX *state = EVP_MD_CTX_new();
            if (!state || !EVP_DigestInit_ex(state, EVP_sha256(), NULL) ||
                !EVP_DigestUpdate(state, data, stream ? prefix : length)) abort();
            if (stream) {
                EVP_MD_CTX *branch = EVP_MD_CTX_new(), *snap = EVP_MD_CTX_new();
                if (!branch || !snap || !EVP_MD_CTX_copy_ex(snap, state) ||
                    !EVP_DigestFinal_ex(snap, snapshot, NULL) || !EVP_MD_CTX_copy_ex(branch, state)) abort();
                sum += snapshot[0];
                EVP_MD_CTX_free(snap);
                for (size_t at = prefix; at < length;) {
                    size_t chunk = length - at < 65536 ? length - at : 65536;
                    if (!EVP_DigestUpdate(state, data + at, chunk) || !EVP_DigestUpdate(branch, data + at, chunk)) abort();
                    at += chunk;
                }
                snap = EVP_MD_CTX_new();
                if (!snap || !EVP_MD_CTX_copy_ex(snap, branch) || !EVP_DigestFinal_ex(snap, fork, NULL)) abort();
                EVP_MD_CTX_free(snap);
                sum += fork[0];
                EVP_MD_CTX_free(branch);
            }
            EVP_MD_CTX *final = EVP_MD_CTX_new();
            if (!final || !EVP_MD_CTX_copy_ex(final, state) || !EVP_DigestFinal_ex(final, out, NULL)) abort();
            EVP_MD_CTX_free(final);
            EVP_MD_CTX_free(state);
        } else {
            SHA256_CTX state, branch, snap;
            if (!SHA256_Init(&state) || !SHA256_Update(&state, data, stream ? prefix : length)) abort();
            if (stream) {
                snap = state;
                if (!SHA256_Final(snapshot, &snap)) abort();
                sum += snapshot[0];
                branch = state;
                for (size_t at = prefix; at < length;) {
                    size_t chunk = length - at < 65536 ? length - at : 65536;
                    if (!SHA256_Update(&state, data + at, chunk) || !SHA256_Update(&branch, data + at, chunk)) abort();
                    at += chunk;
                }
                snap = branch;
                if (!SHA256_Final(fork, &snap)) abort();
                sum += fork[0];
            }
            snap = state;
            if (!SHA256_Final(out, &snap)) abort();
        }
#endif
        sum += out[0];
    }
    printf("%llu %llu\n", (unsigned long long)(nanos() - start), (unsigned long long)sum);
    free(data);
}
