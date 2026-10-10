/* An opaque persistent identity reference, not exported private key material.
 * MNI1 | little-endian path length | ref length | UTF-8 store path | CFData ref.
 * The empty path uses the OS search list. This internal format is local only. */
#ifndef MINYAR_APPLE_IDENTITY_H
#define MINYAR_APPLE_IDENTITY_H
#include <Security/Security.h>
#include <CoreFoundation/CoreFoundation.h>
#include <stdint.h>
static inline uint32_t identity_word(const unsigned char *p) {
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}
static inline void identity_put(unsigned char *p, uint32_t value) {
    for (unsigned i = 0; i < 4; i++)
        p[i] = (unsigned char)(value >> (8 * i));
}
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wdeprecated-declarations"
static inline OSStatus identity_store(CFMutableDictionaryRef query, const unsigned char *path,
                                      size_t size) {
    if (!size)
        return errSecSuccess;
    if (size > 4096 || memchr(path, 0, size))
        return errSecParam;
    char name[4097];
    memcpy(name, path, size);
    name[size] = 0;
    SecKeychainRef store = NULL;
    OSStatus status = SecKeychainOpen(name, &store);
    if (status != errSecSuccess)
        return status;
    const void *value = store;
    CFArrayRef list = CFArrayCreate(NULL, &value, 1, &kCFTypeArrayCallBacks);
    CFRelease(store);
    if (!list)
        return errSecAllocate;
    CFDictionarySetValue(query, kSecMatchSearchList, list);
    CFRelease(list);
    return errSecSuccess;
}
#pragma clang diagnostic pop
/* The legacy file-keychain API accepts this C-only setting. New data-protection
 * queries should use LAContext.interactionNotAllowed. Keep this compatibility
 * use local rather than suppressing deprecation diagnostics for the provider. */
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wdeprecated-declarations"
static inline void identity_no_ui(CFMutableDictionaryRef query) {
    CFDictionarySetValue(query, kSecUseAuthenticationUI, kSecUseAuthenticationUIFail);
}
#pragma clang diagnostic pop
static inline SecKeyRef identity_private_key(const MinyarBytes *encoded) {
    if (encoded->byte_length < 12 || encoded->byte_length > 8204 ||
        memcmp(encoded->bytes, "MNI1", 4))
        return NULL;
    uint32_t path_size = identity_word(encoded->bytes + 4),
             ref_size = identity_word(encoded->bytes + 8);
    if (path_size > 4096 || !ref_size || ref_size > 4096 ||
        12ULL + path_size + ref_size != (uint64_t)encoded->byte_length)
        return NULL;
    CFMutableDictionaryRef query = CFDictionaryCreateMutable(
        NULL, 0, &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
    if (!query)
        return NULL;
    CFDictionarySetValue(query, kSecClass, kSecClassIdentity);
    CFDictionarySetValue(query, kSecReturnRef, kCFBooleanTrue);
    CFDictionarySetValue(query, kSecMatchLimit, kSecMatchLimitOne);
    identity_no_ui(query);
    CFDataRef reference = CFDataCreate(NULL, encoded->bytes + 12 + path_size, ref_size);
    CFTypeRef item = NULL;
    OSStatus status =
        reference ? identity_store(query, encoded->bytes + 12, path_size) : errSecAllocate;
    CFArrayRef match =
        reference ? CFArrayCreate(NULL, (const void **)&reference, 1, &kCFTypeArrayCallBacks)
                  : NULL;
    if (match)
        CFDictionarySetValue(query, kSecMatchItemList, match);
    else
        status = errSecAllocate;
    if (!status)
        status = SecItemCopyMatching(query, &item);
    SecKeyRef key = NULL;
    if (!status && item && CFGetTypeID(item) == SecIdentityGetTypeID())
        SecIdentityCopyPrivateKey((SecIdentityRef)item, &key);
    if (item)
        CFRelease(item);
    if (reference)
        CFRelease(reference);
    if (match)
        CFRelease(match);
    CFRelease(query);
    return key;
}
#endif
