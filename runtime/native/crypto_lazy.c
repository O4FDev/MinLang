/* Load OpenSSL's libcrypto on first use instead of at program start (Linux x86-64 and ARM64).
 *
 * The aes and tlsverify natives call libcrypto. Linking -lcrypto puts libcrypto in DT_NEEDED, so every program
 * that imports tls maps and relocates it at start (about 450 KiB of private pages for libcrypto.so.3) even when
 * it never makes a TLS connection. Instead each libcrypto function those natives call is a small trampoline
 * here: it jumps through a slot that the first call fills with dlopen + dlsym, keeping the argument registers.
 * The driver links -lcrypto only --as-needed after this object, so a symbol missing from the list below (for
 * example under other OpenSSL headers) still resolves from libcrypto, eagerly, and the program keeps working.
 * List: llvm-nm -u of aes.o and tlsverify.o built against OpenSSL 3. Elsewhere this file is empty. */
#if defined(__linux__) && defined(__ELF__) && (defined(__x86_64__) || defined(__aarch64__))
#ifndef _GNU_SOURCE
#define _GNU_SOURCE 1
#endif
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <openssl/opensslv.h>

#if OPENSSL_VERSION_MAJOR >= 3
#define MINYAR_CRYPTO_STRING(value) #value
#define MINYAR_CRYPTO_SONAME(major) "libcrypto.so." MINYAR_CRYPTO_STRING(major)

#define MINYAR_CRYPTO_SYMBOLS(X)                                                                              \
    X(EVP_CIPHER_CTX_ctrl) X(EVP_CIPHER_CTX_free) X(EVP_CIPHER_CTX_new) X(EVP_CIPHER_CTX_set_padding)          \
    X(EVP_CipherFinal_ex) X(EVP_CipherInit_ex) X(EVP_CipherUpdate) X(EVP_DigestSign) X(EVP_DigestSignInit)      \
    X(EVP_DigestVerify) X(EVP_DigestVerifyInit) X(EVP_EncryptFinal_ex) X(EVP_EncryptInit_ex)                   \
    X(EVP_EncryptUpdate) X(EVP_MD_CTX_free) X(EVP_MD_CTX_new) X(EVP_MD_get_size) X(EVP_PKEY_CTX_free)          \
    X(EVP_PKEY_CTX_new) X(EVP_PKEY_CTX_new_id) X(EVP_PKEY_CTX_set_ec_paramgen_curve_nid)                      \
    X(EVP_PKEY_CTX_set_rsa_mgf1_md) X(EVP_PKEY_CTX_set_rsa_padding) X(EVP_PKEY_CTX_set_rsa_pss_saltlen)       \
    X(EVP_PKEY_derive) X(EVP_PKEY_derive_init) X(EVP_PKEY_derive_set_peer) X(EVP_PKEY_free)                   \
    X(EVP_PKEY_fromdata) X(EVP_PKEY_fromdata_init) X(EVP_PKEY_get_base_id) X(EVP_PKEY_get_bits)              \
    X(EVP_PKEY_get_group_name) X(EVP_PKEY_get_octet_string_param) X(EVP_PKEY_keygen) X(EVP_PKEY_keygen_init) \
    X(EVP_PKEY_private_check) X(EVP_PKEY_public_check) X(EVP_aes_128_ecb) X(EVP_aes_128_gcm) X(EVP_sha256)    \
    X(EVP_sha384) X(EVP_sha512) X(OPENSSL_cleanse) X(OPENSSL_sk_new_null) X(OPENSSL_sk_pop_free)              \
    X(OPENSSL_sk_push) X(OSSL_PARAM_construct_end) X(OSSL_PARAM_construct_octet_string)                       \
    X(OSSL_PARAM_construct_utf8_string) X(X509_STORE_CTX_free) X(X509_STORE_CTX_get0_param)                   \
    X(X509_STORE_CTX_init) X(X509_STORE_CTX_new) X(X509_STORE_add_cert) X(X509_STORE_free) X(X509_STORE_new)  \
    X(X509_STORE_set_default_paths) X(X509_VERIFY_PARAM_set1_host) X(X509_VERIFY_PARAM_set1_ip_asc)           \
    X(X509_VERIFY_PARAM_set_auth_level) X(X509_VERIFY_PARAM_set_depth) X(X509_VERIFY_PARAM_set_flags)         \
    X(X509_VERIFY_PARAM_set_hostflags) X(X509_VERIFY_PARAM_set_purpose) X(X509_free) X(X509_get_pubkey)       \
    X(X509_verify_cert) X(d2i_AutoPrivateKey) X(d2i_X509) X(i2d_PrivateKey)

static void *minyar_crypto_library;

/* Called by a trampoline on its first use, with that function's name and slot. Concurrent first calls may
 * both resolve; they store the same address. A missing library or symbol is a fatal configuration error. */
__attribute__((used, visibility("hidden"))) void *minyar_crypto_resolve(const char *name, void **slot) {
    void *library = __atomic_load_n(&minyar_crypto_library, __ATOMIC_ACQUIRE);
    if (!library) {
        library = dlopen(MINYAR_CRYPTO_SONAME(OPENSSL_VERSION_MAJOR), RTLD_NOW | RTLD_LOCAL);
        if (!library) library = dlopen("libcrypto.so", RTLD_NOW | RTLD_LOCAL);
        if (!library) {
            fprintf(stderr, "Minyar stopped: cannot load libcrypto for TLS and AES: %s\n", dlerror());
            exit(1);
        }
        __atomic_store_n(&minyar_crypto_library, library, __ATOMIC_RELEASE);
    }
    void *function = dlsym(library, name);
    if (!function) {
        fprintf(stderr, "Minyar stopped: libcrypto has no %s\n", name);
        exit(1);
    }
    __atomic_store_n(slot, function, __ATOMIC_RELEASE);
    return function;
}

#if defined(__x86_64__)
/* The slow path keeps the six integer and eight vector argument registers across the resolver. */
#define MINYAR_CRYPTO_TRAMPOLINE(name)                                                                        \
    __attribute__((used, visibility("hidden"))) void *minyar_crypto_slot_##name;                              \
    __attribute__((used, visibility("hidden"))) const char minyar_crypto_name_##name[] = #name;               \
    __asm__(".text\n.p2align 4\n.globl " #name "\n.hidden " #name "\n.type " #name ",@function\n" #name ":\n  endbr64\n" \
            "  movq minyar_crypto_slot_" #name "(%rip), %rax\n  testq %rax, %rax\n  jz 1f\n  jmp *%rax\n"      \
            "1:\n  pushq %rdi\n  pushq %rsi\n  pushq %rdx\n  pushq %rcx\n  pushq %r8\n  pushq %r9\n"           \
            "  subq $136, %rsp\n  movdqu %xmm0, 0(%rsp)\n  movdqu %xmm1, 16(%rsp)\n  movdqu %xmm2, 32(%rsp)\n" \
            "  movdqu %xmm3, 48(%rsp)\n  movdqu %xmm4, 64(%rsp)\n  movdqu %xmm5, 80(%rsp)\n"                 \
            "  movdqu %xmm6, 96(%rsp)\n  movdqu %xmm7, 112(%rsp)\n"                                           \
            "  leaq minyar_crypto_name_" #name "(%rip), %rdi\n  leaq minyar_crypto_slot_" #name "(%rip), %rsi\n" \
            "  call minyar_crypto_resolve\n"                                                                   \
            "  movdqu 0(%rsp), %xmm0\n  movdqu 16(%rsp), %xmm1\n  movdqu 32(%rsp), %xmm2\n"                   \
            "  movdqu 48(%rsp), %xmm3\n  movdqu 64(%rsp), %xmm4\n  movdqu 80(%rsp), %xmm5\n"                 \
            "  movdqu 96(%rsp), %xmm6\n  movdqu 112(%rsp), %xmm7\n  addq $136, %rsp\n"                       \
            "  popq %r9\n  popq %r8\n  popq %rcx\n  popq %rdx\n  popq %rsi\n  popq %rdi\n  jmp *%rax\n"       \
            ".size " #name ", .-" #name "\n");
#else
/* x0-x7, x8 (indirect result) and q0-q7 survive the resolver; x16 is the intra-call scratch register. */
#define MINYAR_CRYPTO_TRAMPOLINE(name)                                                                        \
    __attribute__((used, visibility("hidden"))) void *minyar_crypto_slot_##name;                              \
    __attribute__((used, visibility("hidden"))) const char minyar_crypto_name_##name[] = #name;               \
    __asm__(".text\n.p2align 4\n.globl " #name "\n.hidden " #name "\n.type " #name ",%function\n" #name ":\n"  \
            "  adrp x16, minyar_crypto_slot_" #name "\n  add x16, x16, :lo12:minyar_crypto_slot_" #name "\n"   \
            "  ldar x16, [x16]\n  cbz x16, 1f\n  br x16\n"                                                     \
            "1:\n  stp x29, x30, [sp, #-224]!\n  mov x29, sp\n  stp x0, x1, [sp, #16]\n"                      \
            "  stp x2, x3, [sp, #32]\n  stp x4, x5, [sp, #48]\n  stp x6, x7, [sp, #64]\n  str x8, [sp, #80]\n" \
            "  stp q0, q1, [sp, #96]\n  stp q2, q3, [sp, #128]\n  stp q4, q5, [sp, #160]\n"                  \
            "  stp q6, q7, [sp, #192]\n"                                                                       \
            "  adrp x0, minyar_crypto_name_" #name "\n  add x0, x0, :lo12:minyar_crypto_name_" #name "\n"      \
            "  adrp x1, minyar_crypto_slot_" #name "\n  add x1, x1, :lo12:minyar_crypto_slot_" #name "\n"      \
            "  bl minyar_crypto_resolve\n  mov x16, x0\n"                                                      \
            "  ldp q6, q7, [sp, #192]\n  ldp q4, q5, [sp, #160]\n  ldp q2, q3, [sp, #128]\n"                 \
            "  ldp q0, q1, [sp, #96]\n  ldr x8, [sp, #80]\n  ldp x6, x7, [sp, #64]\n"                        \
            "  ldp x4, x5, [sp, #48]\n  ldp x2, x3, [sp, #32]\n  ldp x0, x1, [sp, #16]\n"                    \
            "  ldp x29, x30, [sp], #224\n  br x16\n"                                                           \
            ".size " #name ", .-" #name "\n");
#endif

MINYAR_CRYPTO_SYMBOLS(MINYAR_CRYPTO_TRAMPOLINE)
#endif
#endif
