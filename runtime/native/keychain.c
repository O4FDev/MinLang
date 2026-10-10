#include "../minyar_native.h"
#include "apple_identity.h"
MinyarBytes *minyar_keychain_identity(const MinyarText *label, const MinyarText *path) {
    MinyarBytes *result = minyar_bytes_new(16);
    OSStatus status = errSecParam;
    if (label->byte_length < 1 || label->byte_length > 4096 || path->byte_length < 0 ||
        path->byte_length > 4096)
        goto done;
    CFStringRef name = CFStringCreateWithBytes(NULL, label->bytes, label->byte_length,
                                               kCFStringEncodingUTF8, false);
    CFMutableDictionaryRef query = CFDictionaryCreateMutable(
        NULL, 0, &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
    if (!query || !name) {
        status = errSecAllocate;
        if (name)
            CFRelease(name);
        if (query)
            CFRelease(query);
        goto done;
    }
    CFDictionarySetValue(query, kSecClass, kSecClassIdentity);
    CFDictionarySetValue(query, kSecReturnRef, kCFBooleanTrue);
    CFDictionarySetValue(query, kSecMatchLimit, kSecMatchLimitAll);
    identity_no_ui(query);
    CFTypeRef item = NULL;
    status = identity_store(query, path->bytes, (size_t)path->byte_length);
    if (!status)
        status = SecItemCopyMatching(query, &item);
    if (!status && item && CFGetTypeID(item) == CFArrayGetTypeID() &&
        CFArrayGetCount(item) <= 256) {
        SecIdentityRef identity = NULL;
        /* SecItem's identity lookup does not reliably filter kSecAttrLabel.
         * Inspect public certificate summaries and reject ambiguity ourselves. */
        status = errSecItemNotFound;
        for (CFIndex i = 0; i < CFArrayGetCount(item); i++) {
            SecIdentityRef candidate = (SecIdentityRef)CFArrayGetValueAtIndex(item, i);
            SecCertificateRef certificate = NULL;
            if (CFGetTypeID(candidate) != SecIdentityGetTypeID() ||
                SecIdentityCopyCertificate(candidate, &certificate))
                continue;
            CFStringRef summary = SecCertificateCopySubjectSummary(certificate);
            bool matches = summary && CFStringCompare(summary, name, 0) == kCFCompareEqualTo;
            if (summary)
                CFRelease(summary);
            CFRelease(certificate);
            if (!matches)
                continue;
            if (identity) {
                status = errSecDuplicateItem;
                identity = NULL;
                break;
            }
            identity = candidate;
            status = errSecSuccess;
        }
        CFDataRef reference = NULL;
        if (!status) {
            CFMutableDictionaryRef selected = CFDictionaryCreateMutable(
                NULL, 0, &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
            if (!selected)
                status = errSecAllocate;
            else {
                CFDictionarySetValue(selected, kSecClass, kSecClassIdentity);
                CFArrayRef match =
                    CFArrayCreate(NULL, (const void **)&identity, 1, &kCFTypeArrayCallBacks);
                if (match)
                    CFDictionarySetValue(selected, kSecMatchItemList, match);
                CFDictionarySetValue(selected, kSecReturnPersistentRef, kCFBooleanTrue);
                status = identity_store(selected, path->bytes, (size_t)path->byte_length);
                if (!match)
                    status = errSecAllocate;
                if (!status)
                    status = SecItemCopyMatching(selected, (CFTypeRef *)&reference);
                if (match)
                    CFRelease(match);
                CFRelease(selected);
            }
        }
        SecCertificateRef certificate = NULL;
        if (!status && (!reference || CFGetTypeID(reference) != CFDataGetTypeID()))
            status = errSecInternalComponent;
        if (!status)
            status = SecIdentityCopyCertificate(identity, &certificate);
        CFDataRef der = !status ? SecCertificateCopyData(certificate) : NULL;
        if (!status &&
            (!der || CFDataGetLength(der) > 1024 * 1024 || CFDataGetLength(reference) > 4096))
            status = errSecParam;
        if (!status) {
            uint32_t cert_size = (uint32_t)CFDataGetLength(der),
                     ref_size = (uint32_t)CFDataGetLength(reference);
            identity_put((unsigned char *)result->bytes + 8, cert_size);
            identity_put((unsigned char *)result->bytes + 12,
                         12 + (uint32_t)path->byte_length + ref_size);
            memcpy(minyar_bytes_extend(result, cert_size), CFDataGetBytePtr(der), cert_size);
            unsigned char *encoded = minyar_bytes_extend(result, 12 + path->byte_length + ref_size);
            memcpy(encoded, "MNI1", 4);
            identity_put(encoded + 4, (uint32_t)path->byte_length);
            identity_put(encoded + 8, ref_size);
            memcpy(encoded + 12, path->bytes, (size_t)path->byte_length);
            memcpy(encoded + 12 + path->byte_length, CFDataGetBytePtr(reference), ref_size);
        }
        if (der)
            CFRelease(der);
        if (certificate)
            CFRelease(certificate);
        if (reference)
            CFRelease(reference);
    } else if (!status)
        status = errSecInternalComponent;
    if (item)
        CFRelease(item);
    CFRelease(query);
    CFRelease(name);
done:
    identity_put((unsigned char *)result->bytes, status ? 3 : 0);
    identity_put((unsigned char *)result->bytes + 4, (uint32_t)status);
    return result;
}
