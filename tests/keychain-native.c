/* Uses a disposable keychain; private key bytes never enter a Minyar value. */
#include "../runtime/minyar_native.h"
#include <Security/Security.h>
#include <CoreFoundation/CoreFoundation.h>
#include <assert.h>
#include <stdint.h>
/* This fixture deliberately creates a disposable legacy file keychain. */
#pragma clang diagnostic ignored "-Wdeprecated-declarations"
extern MinyarBytes *minyar_keychain_identity(const MinyarText *, const MinyarText *);
extern MinyarBytes *minyar_tlsverify_sign(const MinyarBytes *, long long, const MinyarBytes *);
extern bool minyar_tlsverify_signature(const MinyarBytes *, long long, const MinyarBytes *,
                                       const MinyarBytes *);
extern void minyar_rc_release(void *);
static MinyarText literal(const char *s) {
    return (MinyarText){(const unsigned char *)s, (long long)strlen(s), -1, NULL, NULL};
}
static uint32_t word(const unsigned char *p) {
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}
int main(int argc, char **argv) {
    assert(argc == 3);
    SecKeychainRef store = NULL;
    assert(SecKeychainCreate(argv[2], 11, "minyar-test", false, NULL, &store) == errSecSuccess);
    FILE *file = fopen(argv[1], "rb");
    assert(file);
    assert(!fseek(file, 0, SEEK_END));
    long size = ftell(file);
    rewind(file);
    assert(size > 0);
    unsigned char *buffer = malloc((size_t)size);
    assert(fread(buffer, 1, (size_t)size, file) == (size_t)size);
    fclose(file);
    CFDataRef data = CFDataCreate(NULL, buffer, size);
    free(buffer);
    const void *keys[] = {kSecImportExportPassphrase, kSecImportExportKeychain};
    const void *values[] = {CFSTR("minyar-test"), store};
    CFDictionaryRef options = CFDictionaryCreate(
        NULL, keys, values, 2, &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
    CFArrayRef imported = NULL;
    assert(SecPKCS12Import(data, options, &imported) == errSecSuccess);
    CFRelease(data);
    CFRelease(options);
    CFRelease(imported);
    MinyarText label = literal("Minyar key test"), path = literal(argv[2]);
    MinyarBytes *found = minyar_keychain_identity(&label, &path);
    if (word(found->bytes))
        fprintf(stderr, "Keychain lookup failed: status=%u code=%d\n", word(found->bytes),
                (int32_t)word(found->bytes + 4));
    assert(found->byte_length >= 16 && word(found->bytes) == 0);
    uint32_t cert_size = word(found->bytes + 8), ref_size = word(found->bytes + 12);
    assert((long long)cert_size + ref_size + 16 == found->byte_length);
    MinyarBytes cert = {found->bytes + 16, cert_size, 0, NULL, NULL};
    MinyarBytes key = {found->bytes + 16 + cert_size, ref_size, 0, NULL, NULL};
    assert(ref_size > 12 && !memcmp(key.bytes, "MNI1", 4));
    MinyarBytes message = {(const unsigned char *)"transcript\0binary", 17, 0, NULL, NULL};
    MinyarBytes *signature = minyar_tlsverify_sign(&key, 0x0804, &message);
    assert(signature->byte_length > 0 &&
           minyar_tlsverify_signature(&cert, 0x0804, &message, signature));
    /* Every truncated opaque reference must fail closed without an import. */
    for (long long length = 0; length < key.byte_length; length++) {
        MinyarBytes bad = key;
        bad.byte_length = length;
        MinyarBytes *rejected = minyar_tlsverify_sign(&bad, 0x0804, &message);
        assert(rejected->byte_length == 0);
        minyar_rc_release(rejected);
    }
    unsigned char changed[] = "different-content";
    MinyarBytes other = {changed, 17, 0, NULL, NULL};
    assert(!minyar_tlsverify_signature(&cert, 0x0804, &other, signature));
    minyar_rc_release(signature);
    minyar_rc_release(found);
    MinyarText absent = literal("missing identity");
    found = minyar_keychain_identity(&absent, &path);
    assert(found->byte_length == 16 && word(found->bytes) == 3 && word(found->bytes + 4));
    minyar_rc_release(found);
    assert(SecKeychainDelete(store) == errSecSuccess);
    CFRelease(store);
    puts("opaque Keychain identity, signature binding and truncation rejection verified");
    return 0;
}
