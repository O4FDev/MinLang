/* X.509 and asymmetric primitives for the Minyar TLS state machine.
 * No sockets, global error state, key registry, or implicit trust-on-first-use.
 * Apple/Windows use their OS roots; Unix uses OpenSSL's OS trust paths. */
#include "../minyar_native.h"
#include <limits.h>
#include <stdint.h>
#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <wincrypt.h>
#include <bcrypt.h>
#include <ncrypt.h>
#include "windows_identity.h"
#else
#include <arpa/inet.h>
#include <sys/time.h>
#endif

#define MAX_CHAIN 16
#define MAX_CERT_BYTES (1024 * 1024)
typedef struct {
    const unsigned char *data;
    size_t length;
} CertBytes;
typedef CertBytes Der;

static bool der_next(Der *source, unsigned char *tag, Der *value) {
    if (source->length < 2)
        return false;
    const unsigned char *p = source->data;
    size_t header = 2, length = p[1];
    if (length & 128) {
        size_t count = length & 127;
        if (!count || count > 4 || source->length < 2 + count || p[2] == 0)
            return false;
        length = 0;
        for (size_t i = 0; i < count; i++)
            length = (length << 8) | p[2 + i];
        if (length < 128)
            return false;
        header += count;
    }
    if (length > source->length - header)
        return false;
    *tag = p[0];
    *value = (Der){p + header, length};
    source->data += header + length;
    source->length -= header + length;
    return true;
}

static MinyarText *error_text(const char *message) {
    return minyar_native_copy_text((const unsigned char *)message, (long long)strlen(message));
}

/* Reject trailing bytes and indefinite/nonminimal DER lengths before the
 * platform parser. No parser gets a pointer outside the borrowed buffer. */
static bool exact_der(const unsigned char *p, size_t n) {
    if (n < 2 || p[0] != 0x30)
        return false;
    size_t header = 2, length = p[1];
    if (length & 128) {
        size_t count = length & 127;
        if (!count || count > 4 || n < 2 + count || p[2] == 0)
            return false;
        length = 0;
        for (size_t i = 0; i < count; i++)
            length = (length << 8) | p[2 + i];
        if (length < 128)
            return false;
        header += count;
    }
    return length == n - header;
}

static int unpack_chain(const MinyarBytes *bytes, CertBytes out[MAX_CHAIN]) {
    if (bytes->byte_length < 0 || bytes->byte_length > MAX_CERT_BYTES)
        return -1;
    size_t n = (size_t)bytes->byte_length, at = 0;
    int count = 0;
    while (at < n) {
        if (count == MAX_CHAIN || n - at < 3)
            return -1;
        size_t length = ((size_t)bytes->bytes[at] << 16) | ((size_t)bytes->bytes[at + 1] << 8) |
                        bytes->bytes[at + 2];
        at += 3;
        if (!length || length > n - at || !exact_der(bytes->bytes + at, length))
            return -1;
        out[count++] = (CertBytes){bytes->bytes + at, length};
        at += length;
        if (n - at < 2)
            return -1;
        size_t extensions = ((size_t)bytes->bytes[at] << 8) | bytes->bytes[at + 1];
        at += 2;
        if (extensions > n - at)
            return -1;
        at += extensions;
    }
    return count;
}

static bool hostname(const MinyarText *host, char out[254]) {
    if (host->byte_length < 1 || host->byte_length > 253)
        return false;
    for (long long i = 0; i < host->byte_length; i++) {
        unsigned char c = host->bytes[i];
        if (c < 33 || c > 126 || c == '*' || c == '/' || c == '\\')
            return false;
    }
    memcpy(out, host->bytes, (size_t)host->byte_length);
    out[host->byte_length] = 0;
    return true;
}

static unsigned char lower_ascii(unsigned char c) {
    return c >= 'A' && c <= 'Z' ? (unsigned char)(c + 'a' - 'A') : c;
}

static bool dns_matches(Der pattern, const char *host) {
    size_t length = strlen(host);
    if (!pattern.length)
        return false;
    for (size_t i = 0; i < pattern.length; i++)
        if (pattern.data[i] < 33 || pattern.data[i] > 126)
            return false;
    size_t start = 0;
    if (pattern.length > 2 && pattern.data[0] == '*' && pattern.data[1] == '.') {
        const char *dot = strchr(host, '.');
        if (!dot || dot == host)
            return false;
        start = (size_t)(dot - host);
        pattern.data++;
        pattern.length--;
    }
    if (pattern.length != length - start)
        return false;
    for (size_t i = 0; i < pattern.length; i++)
        if (pattern.data[i] == '*' ||
            lower_ascii(pattern.data[i]) != lower_ascii((unsigned char)host[start + i]))
            return false;
    return true;
}

/* Require SAN, never a CN fallback. Match the raw IA5String/IP bytes so NULs,
 * partial wildcards and suffix/multiple-label matches cannot be accepted by
 * platform-specific string conversion. Chain validation remains OS-owned. */
static bool certificate_hostname(CertBytes certificate, const char *host) {
    Der input = certificate, outer, tbs, field;
    unsigned char tag;
    if (!der_next(&input, &tag, &outer) || tag != 0x30 || input.length ||
        !der_next(&outer, &tag, &tbs) || tag != 0x30)
        return false;
    if (tbs.length && tbs.data[0] == 0xa0 && !der_next(&tbs, &tag, &field))
        return false;
    for (int i = 0; i < 6; i++)
        if (!der_next(&tbs, &tag, &field))
            return false;
    unsigned char address[16];
    size_t ip_length = 0;
    if (inet_pton(AF_INET, host, address) == 1)
        ip_length = 4;
    else if (inet_pton(AF_INET6, host, address) == 1)
        ip_length = 16;
    bool matched = false, found_san = false;
    while (tbs.length) {
        if (!der_next(&tbs, &tag, &field))
            return false;
        if (tag != 0xa3)
            continue;
        Der extensions;
        if (!der_next(&field, &tag, &extensions) || tag != 0x30 || field.length)
            return false;
        while (extensions.length) {
            Der extension, oid, value;
            if (!der_next(&extensions, &tag, &extension) || tag != 0x30 ||
                !der_next(&extension, &tag, &oid) || tag != 6)
                return false;
            if (extension.length && extension.data[0] == 1 && !der_next(&extension, &tag, &value))
                return false;
            if (!der_next(&extension, &tag, &value) || tag != 4 || extension.length)
                return false;
            if (oid.length != 3 || memcmp(oid.data, "\x55\x1d\x11", 3))
                continue;
            if (found_san)
                return false;
            found_san = true;
            Der names;
            if (!der_next(&value, &tag, &names) || tag != 0x30 || value.length)
                return false;
            while (names.length) {
                Der name;
                if (!der_next(&names, &tag, &name))
                    return false;
                if (tag == 0x82 && !ip_length && dns_matches(name, host))
                    matched = true;
                if (tag == 0x87 && ip_length == name.length && ip_length &&
                    !memcmp(name.data, address, ip_length))
                    matched = true;
            }
        }
    }
    return found_san && matched;
}

#ifdef __APPLE__
#include <CoreFoundation/CoreFoundation.h>
#include <Security/Security.h>
#include "apple_identity.h"

static SecCertificateRef apple_certificate(CertBytes bytes) {
    CFDataRef data = CFDataCreate(NULL, bytes.data, (CFIndex)bytes.length);
    SecCertificateRef certificate = data ? SecCertificateCreateWithData(NULL, data) : NULL;
    if (data)
        CFRelease(data);
    return certificate;
}

static MinyarText *verify_chain(const MinyarText *host, const MinyarBytes *chain,
                                const MinyarBytes *anchors, bool server_peer) {
    CertBytes peers[MAX_CHAIN], roots[MAX_CHAIN];
    int peer_count = unpack_chain(chain, peers), root_count = unpack_chain(anchors, roots);
    char name[254] = {0};
    if (peer_count <= 0 || root_count < 0 ||
        (server_peer && (!hostname(host, name) || !certificate_hostname(peers[0], name))))
        return error_text("invalid certificate chain or hostname");
    CFMutableArrayRef certificates = CFArrayCreateMutable(NULL, 0, &kCFTypeArrayCallBacks);
    CFMutableArrayRef trusted = CFArrayCreateMutable(NULL, 0, &kCFTypeArrayCallBacks);
    bool valid = certificates && trusted;
    for (int i = 0; valid && i < peer_count; i++) {
        SecCertificateRef certificate = apple_certificate(peers[i]);
        if (!certificate) {
            valid = false;
            break;
        }
        CFArrayAppendValue(certificates, certificate);
        CFRelease(certificate);
    }
    for (int i = 0; valid && i < root_count; i++) {
        SecCertificateRef certificate = apple_certificate(roots[i]);
        if (!certificate) {
            valid = false;
            break;
        }
        CFArrayAppendValue(trusted, certificate);
        CFRelease(certificate);
    }
    CFStringRef server =
        server_peer ? CFStringCreateWithCString(NULL, name, kCFStringEncodingASCII) : NULL;
    SecPolicyRef policy = server_peer ? (server ? SecPolicyCreateSSL(true, server) : NULL)
                                      : SecPolicyCreateSSL(false, NULL);
    SecTrustRef trust = NULL;
    if (!policy || !valid ||
        SecTrustCreateWithCertificates(certificates, policy, &trust) != errSecSuccess)
        valid = false;
    if (valid && SecTrustSetNetworkFetchAllowed(trust, false) != errSecSuccess)
        valid = false;
    if (valid && root_count) {
        if (SecTrustSetAnchorCertificates(trust, trusted) != errSecSuccess ||
            SecTrustSetAnchorCertificatesOnly(trust, true) != errSecSuccess)
            valid = false;
    }
    CFErrorRef detail = NULL;
    if (valid)
        valid = SecTrustEvaluateWithError(trust, &detail);
    if (detail)
        CFRelease(detail);
    if (trust)
        CFRelease(trust);
    if (policy)
        CFRelease(policy);
    if (server)
        CFRelease(server);
    if (trusted)
        CFRelease(trusted);
    if (certificates)
        CFRelease(certificates);
    return error_text(
        valid ? "" : "certificate chain, hostname, validity, or server usage did not verify");
}

static SecKeyAlgorithm apple_algorithm(SecKeyRef key, long long scheme) {
    CFDictionaryRef attributes = SecKeyCopyAttributes(key);
    if (!attributes)
        return NULL;
    CFTypeRef type = CFDictionaryGetValue(attributes, kSecAttrKeyType);
    CFNumberRef size = CFDictionaryGetValue(attributes, kSecAttrKeySizeInBits);
    int bits = 0;
    if (size)
        CFNumberGetValue(size, kCFNumberIntType, &bits);
    bool rsa = type && CFEqual(type, kSecAttrKeyTypeRSA) && bits >= 2048;
    bool ec = type && CFEqual(type, kSecAttrKeyTypeECSECPrimeRandom);
    CFRelease(attributes);
    if (rsa && scheme == 0x0804)
        return kSecKeyAlgorithmRSASignatureMessagePSSSHA256;
    if (rsa && scheme == 0x0805)
        return kSecKeyAlgorithmRSASignatureMessagePSSSHA384;
    if (rsa && scheme == 0x0806)
        return kSecKeyAlgorithmRSASignatureMessagePSSSHA512;
    if (ec && bits == 256 && scheme == 0x0403)
        return kSecKeyAlgorithmECDSASignatureMessageX962SHA256;
    if (ec && bits == 384 && scheme == 0x0503)
        return kSecKeyAlgorithmECDSASignatureMessageX962SHA384;
    if (ec && bits == 521 && scheme == 0x0603)
        return kSecKeyAlgorithmECDSASignatureMessageX962SHA512;
    return NULL;
}

/* SecItemImport does not consistently accept unencrypted EC PKCS#8. Convert
 * its SEC1 public point and private scalar to Security's X9.63 key format.
 * Imported keys remain ephemeral and are never added to a Keychain. */
static SecKeyRef apple_ec_pkcs8(const MinyarBytes *encoded) {
    Der input = {encoded->bytes, (size_t)encoded->byte_length}, outer, version, algorithm,
        private_key;
    unsigned char tag;
    static const unsigned char ec_oid[] = {0x2a, 0x86, 0x48, 0xce, 0x3d, 0x02, 0x01};
    if (!der_next(&input, &tag, &outer) || tag != 0x30 || input.length ||
        !der_next(&outer, &tag, &version) || tag != 2 || version.length != 1 ||
        version.data[0] != 0 || !der_next(&outer, &tag, &algorithm) || tag != 0x30 ||
        !der_next(&outer, &tag, &private_key) || tag != 4 || outer.length)
        return NULL;
    Der oid, curve;
    if (!der_next(&algorithm, &tag, &oid) || tag != 6 || oid.length != sizeof(ec_oid) ||
        memcmp(oid.data, ec_oid, sizeof(ec_oid)) || !der_next(&algorithm, &tag, &curve) ||
        tag != 6 || algorithm.length)
        return NULL;
    int bits = 0;
    static const unsigned char p256[] = {0x2a, 0x86, 0x48, 0xce, 0x3d, 0x03, 0x01, 0x07};
    static const unsigned char p384[] = {0x2b, 0x81, 0x04, 0x00, 0x22};
    static const unsigned char p521[] = {0x2b, 0x81, 0x04, 0x00, 0x23};
    if (curve.length == sizeof(p256) && !memcmp(curve.data, p256, sizeof(p256)))
        bits = 256;
    if (curve.length == sizeof(p384) && !memcmp(curve.data, p384, sizeof(p384)))
        bits = 384;
    if (curve.length == sizeof(p521) && !memcmp(curve.data, p521, sizeof(p521)))
        bits = 521;
    if (!bits)
        return NULL;
    Der sec1, scalar, point = {0};
    if (!der_next(&private_key, &tag, &sec1) || tag != 0x30 || private_key.length ||
        !der_next(&sec1, &tag, &version) || tag != 2 || version.length != 1 ||
        version.data[0] != 1 || !der_next(&sec1, &tag, &scalar) || tag != 4 ||
        scalar.length != (size_t)(bits + 7) / 8)
        return NULL;
    while (sec1.length) {
        Der option;
        if (!der_next(&sec1, &tag, &option))
            return NULL;
        if (tag == 0xa1) {
            if (point.data || !der_next(&option, &tag, &point) || tag != 3 || option.length)
                return NULL;
        } else if (tag != 0xa0)
            return NULL;
    }
    if (point.length != 2 + 2 * scalar.length || point.data[0] != 0 || point.data[1] != 4)
        return NULL;
    unsigned char raw[199];
    memcpy(raw, point.data + 1, point.length - 1);
    memcpy(raw + point.length - 1, scalar.data, scalar.length);
    CFDataRef data = CFDataCreate(NULL, raw, (CFIndex)(point.length - 1 + scalar.length));
    CFNumberRef size = CFNumberCreate(NULL, kCFNumberIntType, &bits);
    const void *keys[] = {kSecAttrKeyType, kSecAttrKeyClass, kSecAttrKeySizeInBits};
    const void *values[] = {kSecAttrKeyTypeECSECPrimeRandom, kSecAttrKeyClassPrivate, size};
    CFDictionaryRef attributes = CFDictionaryCreate(
        NULL, keys, values, 3, &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
    SecKeyRef key =
        data && size && attributes ? SecKeyCreateWithData(data, attributes, NULL) : NULL;
    if (attributes)
        CFRelease(attributes);
    if (size)
        CFRelease(size);
    if (data)
        CFRelease(data);
    /* Volatile writes keep this temporary private scalar from being retained. */
    for (size_t i = 0; i < sizeof(raw); i++)
        ((volatile unsigned char *)raw)[i] = 0;
    return key;
}

bool minyar_tlsverify_signature(const MinyarBytes *certificate, long long scheme,
                                const MinyarBytes *content, const MinyarBytes *signature) {
    if (certificate->byte_length <= 0 || certificate->byte_length > MAX_CERT_BYTES ||
        !exact_der(certificate->bytes, (size_t)certificate->byte_length))
        return false;
    SecCertificateRef cert =
        apple_certificate((CertBytes){certificate->bytes, (size_t)certificate->byte_length});
    SecKeyRef key = cert ? SecCertificateCopyKey(cert) : NULL;
    SecKeyAlgorithm algorithm = key ? apple_algorithm(key, scheme) : NULL;
    CFDataRef data = CFDataCreate(NULL, content->bytes, content->byte_length);
    CFDataRef signed_data = CFDataCreate(NULL, signature->bytes, signature->byte_length);
    bool valid = algorithm && data && signed_data &&
                 SecKeyVerifySignature(key, algorithm, data, signed_data, NULL);
    if (signed_data)
        CFRelease(signed_data);
    if (data)
        CFRelease(data);
    if (key)
        CFRelease(key);
    if (cert)
        CFRelease(cert);
    return valid;
}

MinyarBytes *minyar_tlsverify_sign(const MinyarBytes *private_key, long long scheme,
                                   const MinyarBytes *content) {
    MinyarBytes *result = minyar_bytes_new(0);
    bool reference = private_key->byte_length >= 4 && !memcmp(private_key->bytes, "MNI1", 4);
    if (private_key->byte_length <= 0 || private_key->byte_length > MAX_CERT_BYTES ||
        (!reference && !exact_der(private_key->bytes, (size_t)private_key->byte_length)))
        return result;
    CFDataRef encoded =
        reference ? NULL : CFDataCreate(NULL, private_key->bytes, private_key->byte_length);
    SecExternalFormat format = kSecFormatUnknown;
    SecExternalItemType type = kSecItemTypePrivateKey;
    CFArrayRef items = NULL;
    OSStatus status =
        encoded ? SecItemImport(encoded, NULL, &format, &type, 0, NULL, NULL, &items) : errSecParam;
    SecKeyRef key = reference ? identity_private_key(private_key)
                    : status == errSecSuccess && items && CFArrayGetCount(items) == 1 &&
                            CFGetTypeID(CFArrayGetValueAtIndex(items, 0)) == SecKeyGetTypeID()
                        ? (SecKeyRef)CFArrayGetValueAtIndex(items, 0)
                        : NULL;
    SecKeyRef fallback = key ? NULL : apple_ec_pkcs8(private_key);
    if (fallback)
        key = fallback;
    SecKeyAlgorithm algorithm = key ? apple_algorithm(key, scheme) : NULL;
    CFDataRef data = CFDataCreate(NULL, content->bytes, content->byte_length);
    CFDataRef signature =
        algorithm && data ? SecKeyCreateSignature(key, algorithm, data, NULL) : NULL;
    if (signature)
        memcpy(minyar_bytes_extend(result, CFDataGetLength(signature)), CFDataGetBytePtr(signature),
               (size_t)CFDataGetLength(signature));
    if (signature)
        CFRelease(signature);
    if (data)
        CFRelease(data);
    if (items)
        CFRelease(items);
    if (fallback)
        CFRelease(fallback);
    if (encoded)
        CFRelease(encoded);
    if (reference && key)
        CFRelease(key);
    return result;
}

#elif defined(_WIN32)

static MinyarText *verify_chain(const MinyarText *host, const MinyarBytes *chain,
                                const MinyarBytes *anchors, bool server_peer) {
    CertBytes peers[MAX_CHAIN], roots[MAX_CHAIN];
    int peer_count = unpack_chain(chain, peers), root_count = unpack_chain(anchors, roots);
    char name[254] = {0};
    if (peer_count <= 0 || root_count < 0 ||
        (server_peer && (!hostname(host, name) || !certificate_hostname(peers[0], name))))
        return error_text("invalid certificate chain or hostname");
    HCERTSTORE peer_store =
        CertOpenStore(CERT_STORE_PROV_MEMORY, 0, 0, CERT_STORE_CREATE_NEW_FLAG, NULL);
    HCERTSTORE root_store =
        CertOpenStore(CERT_STORE_PROV_MEMORY, 0, 0, CERT_STORE_CREATE_NEW_FLAG, NULL);
    PCCERT_CONTEXT leaf = NULL;
    bool valid = peer_store && root_store;
    for (int i = 0; valid && i < peer_count; i++) {
        PCCERT_CONTEXT certificate =
            CertCreateCertificateContext(X509_ASN_ENCODING, peers[i].data, (DWORD)peers[i].length);
        valid = certificate && CertAddCertificateContextToStore(peer_store, certificate,
                                                                CERT_STORE_ADD_ALWAYS, NULL);
        if (i == 0)
            leaf = certificate;
        else if (certificate)
            CertFreeCertificateContext(certificate);
    }
    for (int i = 0; valid && i < root_count; i++)
        valid =
            CertAddEncodedCertificateToStore(root_store, X509_ASN_ENCODING, roots[i].data,
                                             (DWORD)roots[i].length, CERT_STORE_ADD_ALWAYS, NULL);
    HCERTCHAINENGINE engine = NULL;
    if (valid && root_count) {
        CERT_CHAIN_ENGINE_CONFIG configuration = {0};
        configuration.cbSize = sizeof(configuration);
        configuration.hExclusiveRoot = root_store;
        valid = CertCreateCertificateChainEngine(&configuration, &engine);
    }
    CERT_CHAIN_PARA parameters = {0};
    parameters.cbSize = sizeof(parameters);
    LPSTR usage[] = {server_peer ? szOID_PKIX_KP_SERVER_AUTH : szOID_PKIX_KP_CLIENT_AUTH};
    parameters.RequestedUsage.dwType = USAGE_MATCH_TYPE_AND;
    parameters.RequestedUsage.Usage.cUsageIdentifier = 1;
    parameters.RequestedUsage.Usage.rgpszUsageIdentifier = usage;
    PCCERT_CHAIN_CONTEXT context = NULL;
    if (valid)
        valid = CertGetCertificateChain(engine, leaf, NULL, peer_store, &parameters,
                                        CERT_CHAIN_CACHE_ONLY_URL_RETRIEVAL |
                                            CERT_CHAIN_DISABLE_AUTH_ROOT_AUTO_UPDATE,
                                        NULL, &context);
    if (valid)
        valid = context->TrustStatus.dwErrorStatus == CERT_TRUST_NO_ERROR;
    wchar_t server[254];
    for (size_t i = 0; i <= strlen(name); i++)
        server[i] = (wchar_t)(unsigned char)name[i];
    SSL_EXTRA_CERT_CHAIN_POLICY_PARA ssl_policy = {0};
    ssl_policy.cbSize = sizeof(ssl_policy);
    ssl_policy.dwAuthType = server_peer ? AUTHTYPE_SERVER : AUTHTYPE_CLIENT;
    ssl_policy.pwszServerName = server_peer ? server : NULL;
    CERT_CHAIN_POLICY_PARA policy = {0};
    policy.cbSize = sizeof(policy);
    policy.pvExtraPolicyPara = &ssl_policy;
    CERT_CHAIN_POLICY_STATUS status = {0};
    status.cbSize = sizeof(status);
    if (valid)
        valid =
            CertVerifyCertificateChainPolicy(CERT_CHAIN_POLICY_SSL, context, &policy, &status) &&
            !status.dwError;
    if (context)
        CertFreeCertificateChain(context);
    if (engine)
        CertFreeCertificateChainEngine(engine);
    if (leaf)
        CertFreeCertificateContext(leaf);
    if (root_store)
        CertCloseStore(root_store, 0);
    if (peer_store)
        CertCloseStore(peer_store, 0);
    return error_text(
        valid ? "" : "certificate chain, hostname, validity, or server usage did not verify");
}

static LPCWSTR windows_hash(long long scheme, DWORD *size) {
    if (scheme == 0x0403 || scheme == 0x0804) {
        *size = 32;
        return BCRYPT_SHA256_ALGORITHM;
    }
    if (scheme == 0x0503 || scheme == 0x0805) {
        *size = 48;
        return BCRYPT_SHA384_ALGORITHM;
    }
    if (scheme == 0x0603 || scheme == 0x0806) {
        *size = 64;
        return BCRYPT_SHA512_ALGORITHM;
    }
    return NULL;
}

static bool windows_digest(const MinyarBytes *content, LPCWSTR algorithm, DWORD size,
                           unsigned char out[64]) {
    if (content->byte_length < 0 || content->byte_length > UINT32_MAX)
        return false;
    BCRYPT_ALG_HANDLE handle = NULL;
    BCRYPT_HASH_HANDLE hash = NULL;
    bool valid =
        BCryptOpenAlgorithmProvider(&handle, algorithm, NULL, 0) == 0 &&
        BCryptCreateHash(handle, &hash, NULL, 0, NULL, 0, 0) == 0 &&
        BCryptHashData(hash, (PUCHAR)content->bytes, (ULONG)content->byte_length, 0) == 0 &&
        BCryptFinishHash(hash, out, size, 0) == 0;
    if (hash)
        BCryptDestroyHash(hash);
    if (handle)
        BCryptCloseAlgorithmProvider(handle, 0);
    return valid;
}

static bool windows_scheme(LPCWSTR algorithm, DWORD bits, long long scheme, LPCWSTR curve) {
    if (!wcscmp(algorithm, BCRYPT_RSA_ALGORITHM) && bits >= 2048)
        return scheme == 0x0804 || scheme == 0x0805 || scheme == 0x0806;
    LPCWSTR signing = NULL, agreement = NULL, named = NULL;
    if (bits == 256 && scheme == 0x0403) {
        signing = BCRYPT_ECDSA_P256_ALGORITHM;
        agreement = BCRYPT_ECDH_P256_ALGORITHM;
        named = L"nistP256";
    } else if (bits == 384 && scheme == 0x0503) {
        signing = BCRYPT_ECDSA_P384_ALGORITHM;
        agreement = BCRYPT_ECDH_P384_ALGORITHM;
        named = L"nistP384";
    } else if (bits == 521 && scheme == 0x0603) {
        signing = BCRYPT_ECDSA_P521_ALGORITHM;
        agreement = BCRYPT_ECDH_P521_ALGORITHM;
        named = L"nistP521";
    }
    if (!named)
        return false;
    /* CNG can import an EC signing key under its ECDH algorithm identifier,
     * as also supported by .NET ECDsaCng. A generic EC identifier and bit
     * length alone cannot distinguish NIST curves from e.g. secp256k1. */
    if (!wcscmp(algorithm, signing) || !wcscmp(algorithm, agreement))
        return true;
    /* Generic Windows 10 identifiers are absent from older MinGW headers. */
    return (!wcscmp(algorithm, L"ECDSA") || !wcscmp(algorithm, L"ECDH")) && curve &&
           !wcscmp(curve, named);
}

static bool windows_property_string(LPCWSTR text, DWORD written, size_t capacity) {
    return written >= sizeof(wchar_t) && written <= capacity && written % sizeof(wchar_t) == 0 &&
           text[written / sizeof(wchar_t) - 1] == 0;
}

static bool windows_ec_signature(const MinyarBytes *encoded, size_t width, unsigned char raw[132]) {
    if (encoded->byte_length <= 0 || encoded->byte_length > 144)
        return false;
    Der input = {encoded->bytes, (size_t)encoded->byte_length}, integers;
    unsigned char tag;
    if (!der_next(&input, &tag, &integers) || tag != 0x30 || input.length)
        return false;
    memset(raw, 0, 2 * width);
    for (size_t i = 0; i < 2; i++) {
        Der integer;
        if (!der_next(&integers, &tag, &integer) || tag != 2 || !integer.length ||
            (integer.data[0] & 128))
            return false;
        if (integer.length > 1 && integer.data[0] == 0) {
            if (!(integer.data[1] & 128))
                return false;
            integer.data++;
            integer.length--;
        }
        if (integer.length > width)
            return false;
        memcpy(raw + (i + 1) * width - integer.length, integer.data, integer.length);
    }
    return integers.length == 0;
}

bool minyar_tlsverify_signature(const MinyarBytes *certificate, long long scheme,
                                const MinyarBytes *content, const MinyarBytes *signature) {
    if (certificate->byte_length <= 0 || certificate->byte_length > MAX_CERT_BYTES ||
        signature->byte_length <= 0 || signature->byte_length > MAX_CERT_BYTES ||
        !exact_der(certificate->bytes, (size_t)certificate->byte_length))
        return false;
    PCCERT_CONTEXT cert = CertCreateCertificateContext(X509_ASN_ENCODING, certificate->bytes,
                                                       (DWORD)certificate->byte_length);
    BCRYPT_KEY_HANDLE key = NULL;
    bool valid =
        cert && CryptImportPublicKeyInfoEx2(X509_ASN_ENCODING,
                                            &cert->pCertInfo->SubjectPublicKeyInfo, 0, NULL, &key);
    wchar_t algorithm[64] = {0}, curve[64] = {0};
    DWORD bits = 0, written = 0, hash_size = 0;
    LPCWSTR hash_algorithm = windows_hash(scheme, &hash_size);
    if (valid)
        valid = BCryptGetProperty(key, BCRYPT_ALGORITHM_NAME, (PUCHAR)algorithm, sizeof(algorithm),
                                  &written, 0) == 0 &&
                windows_property_string(algorithm, written, sizeof(algorithm)) &&
                BCryptGetProperty(key, BCRYPT_KEY_LENGTH, (PUCHAR)&bits, sizeof(bits), &written,
                                  0) == 0 &&
                written == sizeof(bits);
    if (valid) {
        /* This Windows 10 property is missing from some MinGW SDK headers. */
        if (BCryptGetProperty(key, L"ECCCurveName", (PUCHAR)curve, sizeof(curve), &written, 0) !=
                0 ||
            !windows_property_string(curve, written, sizeof(curve)))
            curve[0] = 0;
        valid = windows_scheme(algorithm, bits, scheme, curve) && hash_algorithm;
    }
    unsigned char digest[64], raw[132];
    if (valid)
        valid = windows_digest(content, hash_algorithm, hash_size, digest);
    bool rsa = scheme >= 0x0804 && scheme <= 0x0806;
    BCRYPT_PSS_PADDING_INFO padding = {hash_algorithm, hash_size};
    const unsigned char *data = signature->bytes;
    DWORD size = (DWORD)signature->byte_length;
    if (valid && !rsa) {
        size_t width = (bits + 7) / 8;
        valid = width <= 66 && windows_ec_signature(signature, width, raw);
        data = raw;
        size = (DWORD)(2 * width);
    }
    if (valid)
        valid = BCryptVerifySignature(key, rsa ? &padding : NULL, digest, hash_size, (PUCHAR)data,
                                      size, rsa ? BCRYPT_PAD_PSS : 0) == 0;
    if (key)
        BCryptDestroyKey(key);
    if (cert)
        CertFreeCertificateContext(cert);
    return valid;
}

static void append_ec_der(MinyarBytes *out, const unsigned char *raw, size_t length) {
    unsigned char integers[140];
    size_t at = 0, width = length / 2;
    for (size_t i = 0; i < 2; i++) {
        const unsigned char *number = raw + i * width;
        size_t size = width;
        while (size > 1 && *number == 0) {
            number++;
            size--;
        }
        bool prefix = (*number & 128) != 0;
        integers[at++] = 2;
        integers[at++] = (unsigned char)(size + prefix);
        if (prefix)
            integers[at++] = 0;
        memcpy(integers + at, number, size);
        at += size;
    }
    unsigned char *data = minyar_bytes_extend(out, (long long)(at + (at < 128 ? 2 : 3)));
    *data++ = 0x30;
    if (at >= 128)
        *data++ = 0x81;
    *data++ = (unsigned char)at;
    memcpy(data, integers, at);
}

MinyarBytes *minyar_tlsverify_sign(const MinyarBytes *private_key, long long scheme,
                                   const MinyarBytes *content) {
    MinyarBytes *result = minyar_bytes_new(0);
    bool opaque = private_key->byte_length >= 4 && !memcmp(private_key->bytes, "MWI1", 4);
    if (private_key->byte_length <= 0 || private_key->byte_length > MAX_CERT_BYTES ||
        (!opaque && !exact_der(private_key->bytes, (size_t)private_key->byte_length)))
        return result;
    NCRYPT_PROV_HANDLE provider = 0;
    NCRYPT_KEY_HANDLE key = 0;
    WinIdentityKey identity = {0};
    bool valid;
    if (opaque) {
        valid = win_identity_acquire(&identity, private_key);
        key = identity.key;
    } else {
        valid = NCryptOpenStorageProvider(&provider, MS_KEY_STORAGE_PROVIDER, 0) == ERROR_SUCCESS &&
                NCryptImportKey(provider, 0, NCRYPT_PKCS8_PRIVATE_KEY_BLOB, NULL, &key,
                                (PBYTE)private_key->bytes, (DWORD)private_key->byte_length,
                                NCRYPT_SILENT_FLAG) == ERROR_SUCCESS;
    }
    wchar_t algorithm[64] = {0}, curve[64] = {0};
    DWORD bits = 0, written = 0, hash_size = 0;
    LPCWSTR hash_algorithm = windows_hash(scheme, &hash_size);
    if (valid)
        valid = NCryptGetProperty(key, NCRYPT_ALGORITHM_PROPERTY, (PBYTE)algorithm,
                                  sizeof(algorithm), &written, 0) == ERROR_SUCCESS &&
                windows_property_string(algorithm, written, sizeof(algorithm)) &&
                NCryptGetProperty(key, NCRYPT_LENGTH_PROPERTY, (PBYTE)&bits, sizeof(bits), &written,
                                  0) == ERROR_SUCCESS &&
                written == sizeof(bits);
    if (valid) {
        if (NCryptGetProperty(key, L"ECCCurveName", (PBYTE)curve, sizeof(curve), &written, 0) !=
                ERROR_SUCCESS ||
            !windows_property_string(curve, written, sizeof(curve)))
            curve[0] = 0;
        valid = windows_scheme(algorithm, bits, scheme, curve) && hash_algorithm;
    }
    unsigned char digest[64];
    if (valid)
        valid = windows_digest(content, hash_algorithm, hash_size, digest);
    bool rsa = scheme >= 0x0804 && scheme <= 0x0806;
    BCRYPT_PSS_PADDING_INFO padding = {hash_algorithm, hash_size};
    DWORD flags = NCRYPT_SILENT_FLAG | (rsa ? NCRYPT_PAD_PSS_FLAG : 0), size = 0;
    if (valid)
        valid = NCryptSignHash(key, rsa ? &padding : NULL, digest, hash_size, NULL, 0, &size,
                               flags) == ERROR_SUCCESS;
    unsigned char *signature = valid && size <= 16384 ? malloc(size) : NULL;
    if (signature && NCryptSignHash(key, rsa ? &padding : NULL, digest, hash_size, signature, size,
                                    &written, flags) == ERROR_SUCCESS) {
        if (rsa)
            memcpy(minyar_bytes_extend(result, written), signature, written);
        else if (written == 2 * ((bits + 7) / 8) && written <= 132)
            append_ec_der(result, signature, written);
    }
    free(signature);
    if (opaque)
        win_identity_release(&identity);
    else if (key)
        NCryptFreeObject(key);
    if (provider)
        NCryptFreeObject(provider);
    return result;
}

#else
#include <openssl/evp.h>
#include <openssl/ec.h>
#include <openssl/rsa.h>
#include <openssl/x509.h>
#include <openssl/x509_vfy.h>
#include <openssl/x509v3.h>

static X509 *unix_certificate(CertBytes bytes) {
    const unsigned char *cursor = bytes.data;
    X509 *certificate = d2i_X509(NULL, &cursor, (long)bytes.length);
    if (certificate && cursor != bytes.data + bytes.length) {
        X509_free(certificate);
        return NULL;
    }
    return certificate;
}

static MinyarText *verify_chain(const MinyarText *host, const MinyarBytes *chain,
                                const MinyarBytes *anchors, bool server_peer) {
    CertBytes peers[MAX_CHAIN], roots[MAX_CHAIN];
    int peer_count = unpack_chain(chain, peers), root_count = unpack_chain(anchors, roots);
    char name[254] = {0};
    if (peer_count <= 0 || root_count < 0 ||
        (server_peer && (!hostname(host, name) || !certificate_hostname(peers[0], name))))
        return error_text("invalid certificate chain or hostname");
    X509_STORE *store = X509_STORE_new();
    X509_STORE_CTX *context = X509_STORE_CTX_new();
    STACK_OF(X509) *intermediates = sk_X509_new_null();
    X509 *leaf = unix_certificate(peers[0]);
    bool valid = store && context && intermediates && leaf;
    if (valid && !root_count)
        valid = X509_STORE_set_default_paths(store) == 1;
    for (int i = 0; valid && i < root_count; i++) {
        X509 *root = unix_certificate(roots[i]);
        valid = root && X509_STORE_add_cert(store, root) == 1;
        X509_free(root);
    }
    for (int i = 1; valid && i < peer_count; i++) {
        X509 *certificate = unix_certificate(peers[i]);
        if (!certificate || !sk_X509_push(intermediates, certificate)) {
            X509_free(certificate);
            valid = false;
        }
    }
    if (valid)
        valid = X509_STORE_CTX_init(context, store, leaf, intermediates) == 1;
    if (valid) {
        X509_VERIFY_PARAM *parameter = X509_STORE_CTX_get0_param(context);
        X509_VERIFY_PARAM_set_depth(parameter, MAX_CHAIN);
        X509_VERIFY_PARAM_set_auth_level(parameter, 2);
        X509_VERIFY_PARAM_set_hostflags(parameter, X509_CHECK_FLAG_NO_PARTIAL_WILDCARDS |
                                                       X509_CHECK_FLAG_NEVER_CHECK_SUBJECT);
        X509_VERIFY_PARAM_set_flags(parameter, X509_V_FLAG_X509_STRICT | X509_V_FLAG_TRUSTED_FIRST);
        unsigned char ip[16];
        valid =
            X509_VERIFY_PARAM_set_purpose(parameter, server_peer ? X509_PURPOSE_SSL_SERVER
                                                                 : X509_PURPOSE_SSL_CLIENT) == 1;
        if (valid && server_peer &&
            (inet_pton(AF_INET, name, ip) == 1 || inet_pton(AF_INET6, name, ip) == 1))
            valid = X509_VERIFY_PARAM_set1_ip_asc(parameter, name) == 1;
        else if (valid && server_peer)
            valid = X509_VERIFY_PARAM_set1_host(parameter, name, 0) == 1;
    }
    if (valid)
        valid = X509_verify_cert(context) == 1;
    X509_free(leaf);
    sk_X509_pop_free(intermediates, X509_free);
    X509_STORE_CTX_free(context);
    X509_STORE_free(store);
    return error_text(
        valid ? "" : "certificate chain, hostname, validity, or server usage did not verify");
}

static bool unix_signature_init(EVP_MD_CTX *context, EVP_PKEY *key, long long scheme, bool sign) {
    const EVP_MD *digest = NULL;
    int type = EVP_PKEY_base_id(key), bits = EVP_PKEY_bits(key);
    bool rsa = type == EVP_PKEY_RSA && bits >= 2048;
    bool ec = type == EVP_PKEY_EC;
    int curve = NID_undef;
    if (ec) {
#if OPENSSL_VERSION_NUMBER >= 0x30000000L
        char name[80];
        size_t length = 0;
        if (EVP_PKEY_get_group_name(key, name, sizeof(name), &length) == 1) {
            if (!strcmp(name, "prime256v1"))
                curve = NID_X9_62_prime256v1;
            if (!strcmp(name, "secp384r1"))
                curve = NID_secp384r1;
            if (!strcmp(name, "secp521r1"))
                curve = NID_secp521r1;
        }
#else
        EC_KEY *ec_key = EVP_PKEY_get1_EC_KEY(key);
        const EC_GROUP *group = ec_key ? EC_KEY_get0_group(ec_key) : NULL;
        if (group)
            curve = EC_GROUP_get_curve_name(group);
        EC_KEY_free(ec_key);
#endif
    }
    if ((rsa && scheme == 0x0804) ||
        (curve == NID_X9_62_prime256v1 && bits == 256 && scheme == 0x0403))
        digest = EVP_sha256();
    if ((rsa && scheme == 0x0805) || (curve == NID_secp384r1 && bits == 384 && scheme == 0x0503))
        digest = EVP_sha384();
    if ((rsa && scheme == 0x0806) || (curve == NID_secp521r1 && bits == 521 && scheme == 0x0603))
        digest = EVP_sha512();
    if (!digest)
        return false;
    EVP_PKEY_CTX *pkey_context = NULL;
    int status = sign ? EVP_DigestSignInit(context, &pkey_context, digest, NULL, key)
                      : EVP_DigestVerifyInit(context, &pkey_context, digest, NULL, key);
    if (status != 1)
        return false;
    return !rsa || (EVP_PKEY_CTX_set_rsa_padding(pkey_context, RSA_PKCS1_PSS_PADDING) == 1 &&
                    EVP_PKEY_CTX_set_rsa_pss_saltlen(pkey_context, EVP_MD_size(digest)) == 1 &&
                    EVP_PKEY_CTX_set_rsa_mgf1_md(pkey_context, digest) == 1);
}

bool minyar_tlsverify_signature(const MinyarBytes *certificate, long long scheme,
                                const MinyarBytes *content, const MinyarBytes *signature) {
    if (certificate->byte_length <= 0 || certificate->byte_length > MAX_CERT_BYTES ||
        !exact_der(certificate->bytes, (size_t)certificate->byte_length))
        return false;
    X509 *cert =
        unix_certificate((CertBytes){certificate->bytes, (size_t)certificate->byte_length});
    EVP_PKEY *key = cert ? X509_get_pubkey(cert) : NULL;
    EVP_MD_CTX *context = EVP_MD_CTX_new();
    bool valid = key && context && unix_signature_init(context, key, scheme, false) &&
                 EVP_DigestVerify(context, signature->bytes, (size_t)signature->byte_length,
                                  content->bytes, (size_t)content->byte_length) == 1;
    EVP_MD_CTX_free(context);
    EVP_PKEY_free(key);
    X509_free(cert);
    return valid;
}

MinyarBytes *minyar_tlsverify_sign(const MinyarBytes *private_key, long long scheme,
                                   const MinyarBytes *content) {
    MinyarBytes *result = minyar_bytes_new(0);
    if (private_key->byte_length <= 0 || private_key->byte_length > MAX_CERT_BYTES ||
        !exact_der(private_key->bytes, (size_t)private_key->byte_length))
        return result;
    const unsigned char *cursor = private_key->bytes;
    EVP_PKEY *key = d2i_AutoPrivateKey(NULL, &cursor, (long)private_key->byte_length);
    EVP_MD_CTX *context = EVP_MD_CTX_new();
    size_t length = 0;
    if (key && context && cursor == private_key->bytes + private_key->byte_length &&
        unix_signature_init(context, key, scheme, true) &&
        EVP_DigestSign(context, NULL, &length, content->bytes, (size_t)content->byte_length) == 1) {
        unsigned char *signature = malloc(length);
        if (signature && EVP_DigestSign(context, signature, &length, content->bytes,
                                        (size_t)content->byte_length) == 1)
            memcpy(minyar_bytes_extend(result, (long long)length), signature, length);
        free(signature);
    }
    EVP_MD_CTX_free(context);
    EVP_PKEY_free(key);
    return result;
}
#endif

MinyarText *minyar_tlsverify_chain(const MinyarText *host, const MinyarBytes *chain,
                                   const MinyarBytes *anchors) {
    return verify_chain(host, chain, anchors, true);
}
MinyarText *minyar_tlsverify_clientChain(const MinyarBytes *chain, const MinyarBytes *anchors) {
    return verify_chain(NULL, chain, anchors, false);
}

/* Tickets need wall time across connections; transport timers remain monotonic. */
long long minyar_tlsverify_currentTimeMilliseconds(void) {
#ifdef _WIN32
    FILETIME filetime;
    GetSystemTimeAsFileTime(&filetime);
    ULARGE_INTEGER ticks;
    ticks.LowPart = filetime.dwLowDateTime;
    ticks.HighPart = filetime.dwHighDateTime;
    if (ticks.QuadPart < UINT64_C(116444736000000000))
        return 0;
    return (long long)((ticks.QuadPart - UINT64_C(116444736000000000)) / 10000);
#else
    struct timeval time;
    if (gettimeofday(&time, NULL) != 0 || time.tv_sec < 0 ||
        (uint64_t)time.tv_sec > INT64_MAX / 1000)
        return 0;
    return (long long)time.tv_sec * 1000 + time.tv_usec / 1000;
#endif
}

/* RFC5280 section4.1.2.5: strict calendar bounds and seconds in UTC/Zulu.
 * This extracts time policy only. It never replaces platform trust or signature
 * validation. Gregorian arithmetic is bounded to ASN.1's four-digit years. */
static bool certificate_time(unsigned char tag, Der date, long long *milliseconds) {
    size_t year_digits = tag == 0x17 ? 2 : tag == 0x18 ? 4 : 0;
    if (!year_digits || date.length != year_digits + 11 || date.data[date.length - 1] != 'Z')
        return false;
    int fields[6] = {0};
    size_t at = 0;
    for (size_t field = 0; field < 6; field++) {
        size_t width = field ? 2 : year_digits;
        for (size_t digit = 0; digit < width; digit++, at++) {
            if (date.data[at] < '0' || date.data[at] > '9')
                return false;
            fields[field] = fields[field] * 10 + date.data[at] - '0';
        }
    }
    int year = fields[0];
    if (year_digits == 2)
        year += year >= 50 ? 1900 : 2000;
    int month = fields[1], day = fields[2];
    bool leap = year % 4 == 0 && (year % 100 != 0 || year % 400 == 0);
    static const int lengths[] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    static const int elapsed[] = {0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334};
    if (year < 1 || month < 1 || month > 12 || day < 1 ||
        day > lengths[month - 1] + (month == 2 && leap) || fields[3] > 23 || fields[4] > 59 ||
        fields[5] > 59)
        return false;
    int prior = year - 1;
    long long days = (long long)(year - 1970) * 365 + prior / 4 - prior / 100 + prior / 400 - 477;
    days += elapsed[month - 1] + day - 1 + (month > 2 && leap);
    *milliseconds = ((days * 24 + fields[3]) * 3600 + fields[4] * 60 + fields[5]) * 1000;
    return true;
}

static long long certificate_expiry(CertBytes bytes, long long now) {
    Der input = bytes, outer, tbs, field, validity;
    unsigned char tag;
    if (!der_next(&input, &tag, &outer) || tag != 0x30 || input.length ||
        !der_next(&outer, &tag, &tbs) || tag != 0x30)
        return 0;
    if (tbs.length && tbs.data[0] == 0xa0 && !der_next(&tbs, &tag, &field))
        return 0;
    static const unsigned char expected[] = {2, 0x30, 0x30, 0x30};
    for (size_t i = 0; i < sizeof(expected); i++) {
        if (!der_next(&tbs, &tag, &field) || tag != expected[i])
            return 0;
    }
    validity = field;
    long long before, after;
    if (!der_next(&validity, &tag, &field) || !certificate_time(tag, field, &before) ||
        !der_next(&validity, &tag, &field) || !certificate_time(tag, field, &after) ||
        validity.length || before > now || after <= now || before >= after)
        return 0;
    return after;
}

long long minyar_tlsverify_currentCertificateExpiry(const MinyarBytes *chain) {
    CertBytes certificates[MAX_CHAIN];
    int count = unpack_chain(chain, certificates);
    long long now = minyar_tlsverify_currentTimeMilliseconds(), expires = INT64_MAX;
    if (count < 1 || now < 1)
        return 0;
    for (int i = 0; i < count; i++) {
        long long bound = certificate_expiry(certificates[i], now);
        if (!bound)
            return 0;
        if (bound < expires)
            expires = bound;
    }
    return expires;
}

/* Native ephemeral P-256 key agreement for TLS 1.3 secp256r1 key shares.
 * Private encodings are provider-owned bytes, never a global key registry.
 * The peer must be exactly the RFC 8446 uncompressed SEC1 point. */
#ifdef __APPLE__
static SecKeyRef p256_apple_key(const MinyarBytes *data, bool private_key) {
    if (data->byte_length != (private_key ? 97 : 65) || data->bytes[0] != 4)
        return NULL;
    int bits = 256;
    CFNumberRef size = CFNumberCreate(NULL, kCFNumberIntType, &bits);
    const void *keys[] = {kSecAttrKeyType, kSecAttrKeyClass, kSecAttrKeySizeInBits};
    const void *values[] = {kSecAttrKeyTypeECSECPrimeRandom,
                            private_key ? kSecAttrKeyClassPrivate : kSecAttrKeyClassPublic, size};
    CFDictionaryRef attributes =
        size ? CFDictionaryCreate(NULL, keys, values, 3, &kCFTypeDictionaryKeyCallBacks,
                                  &kCFTypeDictionaryValueCallBacks)
             : NULL;
    CFDataRef bytes = attributes ? CFDataCreate(NULL, data->bytes, data->byte_length) : NULL;
    SecKeyRef key = bytes ? SecKeyCreateWithData(bytes, attributes, NULL) : NULL;
    if (bytes)
        CFRelease(bytes);
    if (attributes)
        CFRelease(attributes);
    if (size)
        CFRelease(size);
    return key;
}
static void p256_apple_export(MinyarBytes *output, SecKeyRef key, size_t expected) {
    CFDataRef data = key ? SecKeyCopyExternalRepresentation(key, NULL) : NULL;
    if (data && CFDataGetLength(data) == (CFIndex)expected && CFDataGetBytePtr(data)[0] == 4)
        memcpy(minyar_bytes_extend(output, expected), CFDataGetBytePtr(data), expected);
    if (data)
        CFRelease(data);
}
MinyarBytes *minyar_tlsverify_p256Key(void) {
    MinyarBytes *output = minyar_bytes_new(0);
    int bits = 256;
    CFNumberRef size = CFNumberCreate(NULL, kCFNumberIntType, &bits);
    const void *keys[] = {kSecAttrKeyType, kSecAttrKeySizeInBits};
    const void *values[] = {kSecAttrKeyTypeECSECPrimeRandom, size};
    CFDictionaryRef attributes =
        size ? CFDictionaryCreate(NULL, keys, values, 2, &kCFTypeDictionaryKeyCallBacks,
                                  &kCFTypeDictionaryValueCallBacks)
             : NULL;
    SecKeyRef key = attributes ? SecKeyCreateRandomKey(attributes, NULL) : NULL;
    p256_apple_export(output, key, 97);
    if (key)
        CFRelease(key);
    if (attributes)
        CFRelease(attributes);
    if (size)
        CFRelease(size);
    return output;
}
MinyarBytes *minyar_tlsverify_p256Public(const MinyarBytes *private_key) {
    MinyarBytes *output = minyar_bytes_new(0);
    SecKeyRef key = p256_apple_key(private_key, true);
    SecKeyRef public_key = key ? SecKeyCopyPublicKey(key) : NULL;
    p256_apple_export(output, public_key, 65);
    if (public_key)
        CFRelease(public_key);
    if (key)
        CFRelease(key);
    return output;
}
MinyarBytes *minyar_tlsverify_p256(const MinyarBytes *private_key, const MinyarBytes *public_key) {
    MinyarBytes *output = minyar_bytes_new(0);
    SecKeyRef local = p256_apple_key(private_key, true);
    SecKeyRef peer = p256_apple_key(public_key, false);
    CFDictionaryRef parameters = CFDictionaryCreate(
        NULL, NULL, NULL, 0, &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
    CFDataRef shared =
        local && peer && parameters &&
                SecKeyIsAlgorithmSupported(local, kSecKeyOperationTypeKeyExchange,
                                           kSecKeyAlgorithmECDHKeyExchangeStandard)
            ? SecKeyCopyKeyExchangeResult(local, kSecKeyAlgorithmECDHKeyExchangeStandard, peer,
                                          parameters, NULL)
            : NULL;
    if (shared && CFDataGetLength(shared) == 32)
        memcpy(minyar_bytes_extend(output, 32), CFDataGetBytePtr(shared), 32);
    if (shared)
        CFRelease(shared);
    if (parameters)
        CFRelease(parameters);
    if (peer)
        CFRelease(peer);
    if (local)
        CFRelease(local);
    return output;
}
#elif defined(_WIN32)
static BCRYPT_KEY_HANDLE p256_windows_private(BCRYPT_ALG_HANDLE provider,
                                              const MinyarBytes *bytes) {
    if (bytes->byte_length != sizeof(BCRYPT_ECCKEY_BLOB) + 96)
        return NULL;
    BCRYPT_ECCKEY_BLOB header;
    memcpy(&header, bytes->bytes, sizeof(header));
    if (header.dwMagic != BCRYPT_ECDH_PRIVATE_P256_MAGIC || header.cbKey != 32)
        return NULL;
    BCRYPT_KEY_HANDLE key = NULL;
    if (BCryptImportKeyPair(provider, NULL, BCRYPT_ECCPRIVATE_BLOB, &key, (PUCHAR)bytes->bytes,
                            (ULONG)bytes->byte_length, 0) < 0)
        return NULL;
    return key;
}
MinyarBytes *minyar_tlsverify_p256Key(void) {
    MinyarBytes *output = minyar_bytes_new(0);
    BCRYPT_ALG_HANDLE provider = NULL;
    BCRYPT_KEY_HANDLE key = NULL;
    unsigned char encoded[sizeof(BCRYPT_ECCKEY_BLOB) + 96];
    ULONG size = 0;
    if (BCryptOpenAlgorithmProvider(&provider, BCRYPT_ECDH_P256_ALGORITHM, NULL, 0) >= 0 &&
        BCryptGenerateKeyPair(provider, &key, 256, 0) >= 0 && BCryptFinalizeKeyPair(key, 0) >= 0 &&
        BCryptExportKey(key, NULL, BCRYPT_ECCPRIVATE_BLOB, encoded, sizeof(encoded), &size, 0) >=
            0 &&
        size == sizeof(encoded))
        memcpy(minyar_bytes_extend(output, size), encoded, size);
    SecureZeroMemory(encoded, sizeof(encoded));
    if (key)
        BCryptDestroyKey(key);
    if (provider)
        BCryptCloseAlgorithmProvider(provider, 0);
    return output;
}
MinyarBytes *minyar_tlsverify_p256Public(const MinyarBytes *private_key) {
    MinyarBytes *output = minyar_bytes_new(0);
    BCRYPT_ALG_HANDLE provider = NULL;
    BCRYPT_KEY_HANDLE key = NULL;
    unsigned char encoded[sizeof(BCRYPT_ECCKEY_BLOB) + 64];
    ULONG size = 0;
    if (BCryptOpenAlgorithmProvider(&provider, BCRYPT_ECDH_P256_ALGORITHM, NULL, 0) >= 0 &&
        (key = p256_windows_private(provider, private_key)) &&
        BCryptExportKey(key, NULL, BCRYPT_ECCPUBLIC_BLOB, encoded, sizeof(encoded), &size, 0) >=
            0 &&
        size == sizeof(encoded)) {
        unsigned char *point = minyar_bytes_extend(output, 65);
        point[0] = 4;
        memcpy(point + 1, encoded + sizeof(BCRYPT_ECCKEY_BLOB), 64);
    }
    if (key)
        BCryptDestroyKey(key);
    if (provider)
        BCryptCloseAlgorithmProvider(provider, 0);
    return output;
}
MinyarBytes *minyar_tlsverify_p256(const MinyarBytes *private_key, const MinyarBytes *public_key) {
    MinyarBytes *output = minyar_bytes_new(0);
    if (public_key->byte_length != 65 || public_key->bytes[0] != 4)
        return output;
    BCRYPT_ALG_HANDLE provider = NULL;
    BCRYPT_KEY_HANDLE local = NULL, peer = NULL;
    BCRYPT_SECRET_HANDLE agreement = NULL;
    unsigned char encoded[sizeof(BCRYPT_ECCKEY_BLOB) + 64], shared[32];
    BCRYPT_ECCKEY_BLOB header = {BCRYPT_ECDH_PUBLIC_P256_MAGIC, 32};
    memcpy(encoded, &header, sizeof(header));
    memcpy(encoded + sizeof(header), public_key->bytes + 1, 64);
    ULONG size = 0;
    if (BCryptOpenAlgorithmProvider(&provider, BCRYPT_ECDH_P256_ALGORITHM, NULL, 0) >= 0 &&
        (local = p256_windows_private(provider, private_key)) &&
        BCryptImportKeyPair(provider, NULL, BCRYPT_ECCPUBLIC_BLOB, &peer, encoded, sizeof(encoded),
                            0) >= 0 &&
        BCryptSecretAgreement(local, peer, &agreement, 0) >= 0 &&
        BCryptDeriveKey(agreement, BCRYPT_KDF_RAW_SECRET, NULL, shared, sizeof(shared), &size, 0) >=
            0 &&
        size == 32) {
        unsigned char *big_endian = minyar_bytes_extend(output, 32);
        for (size_t i = 0; i < 32; i++)
            big_endian[i] = shared[31 - i];
    }
    SecureZeroMemory(shared, sizeof(shared));
    if (agreement)
        BCryptDestroySecret(agreement);
    if (peer)
        BCryptDestroyKey(peer);
    if (local)
        BCryptDestroyKey(local);
    if (provider)
        BCryptCloseAlgorithmProvider(provider, 0);
    return output;
}
#else
#if OPENSSL_VERSION_NUMBER >= 0x30000000L
#include <openssl/core_names.h>
#include <openssl/params.h>
#endif
static EVP_PKEY *p256_unix_private(const MinyarBytes *bytes) {
    if (bytes->byte_length <= 0 || bytes->byte_length > 1024 ||
        !exact_der(bytes->bytes, (size_t)bytes->byte_length))
        return NULL;
    const unsigned char *cursor = bytes->bytes;
    EVP_PKEY *key = d2i_AutoPrivateKey(NULL, &cursor, (long)bytes->byte_length);
    bool valid =
        key && cursor == bytes->bytes + bytes->byte_length && EVP_PKEY_base_id(key) == EVP_PKEY_EC;
#if OPENSSL_VERSION_NUMBER >= 0x30000000L
    char group[80];
    size_t length = 0;
    valid = valid && EVP_PKEY_get_group_name(key, group, sizeof(group), &length) == 1 &&
            !strcmp(group, "prime256v1");
#else
    EC_KEY *ec = valid ? EVP_PKEY_get1_EC_KEY(key) : NULL;
    valid = ec && EC_GROUP_get_curve_name(EC_KEY_get0_group(ec)) == NID_X9_62_prime256v1 &&
            EC_KEY_check_key(ec) == 1;
    EC_KEY_free(ec);
#endif
    EVP_PKEY_CTX *check = valid ? EVP_PKEY_CTX_new(key, NULL) : NULL;
    valid = check && EVP_PKEY_private_check(check) == 1;
    EVP_PKEY_CTX_free(check);
    if (!valid) {
        EVP_PKEY_free(key);
        key = NULL;
    }
    return key;
}
MinyarBytes *minyar_tlsverify_p256Key(void) {
    MinyarBytes *output = minyar_bytes_new(0);
    EVP_PKEY_CTX *context = EVP_PKEY_CTX_new_id(EVP_PKEY_EC, NULL);
    EVP_PKEY *key = NULL;
    if (context && EVP_PKEY_keygen_init(context) == 1 &&
        EVP_PKEY_CTX_set_ec_paramgen_curve_nid(context, NID_X9_62_prime256v1) == 1 &&
        EVP_PKEY_keygen(context, &key) == 1) {
        int size = i2d_PrivateKey(key, NULL);
        if (size > 0 && size <= 1024) {
            unsigned char encoded[1024], *cursor = encoded;
            if (i2d_PrivateKey(key, &cursor) == size)
                memcpy(minyar_bytes_extend(output, size), encoded, size);
            OPENSSL_cleanse(encoded, sizeof(encoded));
        }
    }
    EVP_PKEY_free(key);
    EVP_PKEY_CTX_free(context);
    return output;
}
MinyarBytes *minyar_tlsverify_p256Public(const MinyarBytes *private_key) {
    MinyarBytes *output = minyar_bytes_new(0);
    EVP_PKEY *key = p256_unix_private(private_key);
    unsigned char point[65];
    size_t size = 0;
#if OPENSSL_VERSION_NUMBER >= 0x30000000L
    bool valid = key && EVP_PKEY_get_octet_string_param(key, OSSL_PKEY_PARAM_PUB_KEY, point,
                                                        sizeof(point), &size) == 1;
#else
    EC_KEY *ec = key ? EVP_PKEY_get1_EC_KEY(key) : NULL;
    size = ec ? EC_POINT_point2oct(EC_KEY_get0_group(ec), EC_KEY_get0_public_key(ec),
                                   POINT_CONVERSION_UNCOMPRESSED, point, sizeof(point), NULL)
              : 0;
    bool valid = ec && size == 65;
    EC_KEY_free(ec);
#endif
    if (valid && size == 65 && point[0] == 4)
        memcpy(minyar_bytes_extend(output, 65), point, 65);
    EVP_PKEY_free(key);
    return output;
}
MinyarBytes *minyar_tlsverify_p256(const MinyarBytes *private_key, const MinyarBytes *public_key) {
    MinyarBytes *output = minyar_bytes_new(0);
    if (public_key->byte_length != 65 || public_key->bytes[0] != 4)
        return output;
    EVP_PKEY *local = p256_unix_private(private_key), *peer = NULL;
#if OPENSSL_VERSION_NUMBER >= 0x30000000L
    EVP_PKEY_CTX *decoder = EVP_PKEY_CTX_new_id(EVP_PKEY_EC, NULL);
    char group[] = "prime256v1";
    OSSL_PARAM parameters[] = {
        OSSL_PARAM_construct_utf8_string(OSSL_PKEY_PARAM_GROUP_NAME, group, 0),
        OSSL_PARAM_construct_octet_string(OSSL_PKEY_PARAM_PUB_KEY, (void *)public_key->bytes, 65),
        OSSL_PARAM_construct_end()};
    if (!decoder || EVP_PKEY_fromdata_init(decoder) != 1 ||
        EVP_PKEY_fromdata(decoder, &peer, EVP_PKEY_PUBLIC_KEY, parameters) != 1) {
        EVP_PKEY_free(peer);
        peer = NULL;
    }
    EVP_PKEY_CTX_free(decoder);
#else
    EC_KEY *ec = EC_KEY_new_by_curve_name(NID_X9_62_prime256v1);
    const unsigned char *cursor = public_key->bytes;
    if (ec && o2i_ECPublicKey(&ec, &cursor, 65) && cursor == public_key->bytes + 65 &&
        EC_KEY_check_key(ec) == 1) {
        peer = EVP_PKEY_new();
        if (!peer || EVP_PKEY_assign_EC_KEY(peer, ec) != 1) {
            EVP_PKEY_free(peer);
            peer = NULL;
        } else
            ec = NULL;
    }
    EC_KEY_free(ec);
#endif
    EVP_PKEY_CTX *check = peer ? EVP_PKEY_CTX_new(peer, NULL) : NULL;
    bool valid = check && EVP_PKEY_public_check(check) == 1;
    EVP_PKEY_CTX_free(check);
    EVP_PKEY_CTX *agreement = local && valid ? EVP_PKEY_CTX_new(local, NULL) : NULL;
    unsigned char shared[32];
    size_t size = sizeof(shared);
    if (agreement && EVP_PKEY_derive_init(agreement) == 1 &&
        EVP_PKEY_derive_set_peer(agreement, peer) == 1 &&
        EVP_PKEY_derive(agreement, shared, &size) == 1 && size == 32)
        memcpy(minyar_bytes_extend(output, 32), shared, 32);
    OPENSSL_cleanse(shared, sizeof(shared));
    EVP_PKEY_CTX_free(agreement);
    EVP_PKEY_free(peer);
    EVP_PKEY_free(local);
    return output;
}
#endif
