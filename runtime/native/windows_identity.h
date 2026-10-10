/* Local certificate identity reference. MWI1 | u32 store byte length | u32
 * machine-store flag | SHA256(certificate DER)[32] | ASCII store name.
 * Contains public identity metadata only, never pointers or private key bytes. */
#ifndef MINYAR_WINDOWS_IDENTITY_H
#define MINYAR_WINDOWS_IDENTITY_H
#include <stdint.h>
#include <windows.h>
#include <wincrypt.h>
#include <bcrypt.h>
#include <ncrypt.h>

static inline uint32_t win_identity_word(const unsigned char *p) {
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}
static inline void win_identity_put(unsigned char *p, uint32_t value) {
    for (unsigned i = 0; i < 4; i++)
        p[i] = (unsigned char)(value >> (8 * i));
}
static inline bool win_identity_store_name(const unsigned char *source, size_t length,
                                           wchar_t name[65]) {
    if (!length || length > 64)
        return false;
    for (size_t i = 0; i < length; i++) {
        unsigned char c = source[i];
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') ||
              c == '_' || c == '-'))
            return false;
        name[i] = c;
    }
    name[length] = 0;
    return true;
}
static inline PCCERT_CONTEXT win_identity_find(const unsigned char digest[32], const wchar_t *name,
                                               bool machine) {
    HCERTSTORE store = CertOpenStore(
        CERT_STORE_PROV_SYSTEM_W, 0, 0,
        CERT_STORE_READONLY_FLAG | CERT_STORE_OPEN_EXISTING_FLAG |
            (machine ? CERT_SYSTEM_STORE_LOCAL_MACHINE : CERT_SYSTEM_STORE_CURRENT_USER),
        name);
    if (!store)
        return NULL;
    PCCERT_CONTEXT candidate = NULL, found = NULL;
    bool ambiguous = false;
    while ((candidate = CertEnumCertificatesInStore(store, candidate))) {
        unsigned char hash[32];
        DWORD size = sizeof(hash);
        if (!CryptHashCertificate2(BCRYPT_SHA256_ALGORITHM, 0, NULL, candidate->pbCertEncoded,
                                   candidate->cbCertEncoded, hash, &size) ||
            size != 32 || memcmp(hash, digest, 32))
            continue;
        if (found) {
            ambiguous = true;
            CertFreeCertificateContext(candidate);
            break;
        }
        found = CertDuplicateCertificateContext(candidate);
    }
    CertCloseStore(store, 0);
    if (ambiguous && found) {
        CertFreeCertificateContext(found);
        found = NULL;
    }
    SetLastError(ambiguous ? ERROR_DUP_NAME : found ? ERROR_SUCCESS : CRYPT_E_NOT_FOUND);
    return found;
}
static inline PCCERT_CONTEXT win_identity_certificate(const MinyarBytes *encoded) {
    if (encoded->byte_length < 45 || encoded->byte_length > 108 ||
        memcmp(encoded->bytes, "MWI1", 4)) {
        SetLastError(ERROR_INVALID_DATA);
        return NULL;
    }
    uint32_t length = win_identity_word(encoded->bytes + 4),
             machine = win_identity_word(encoded->bytes + 8);
    wchar_t name[65];
    if (machine > 1 || 44ULL + length != (uint64_t)encoded->byte_length ||
        !win_identity_store_name(encoded->bytes + 44, length, name)) {
        SetLastError(ERROR_INVALID_DATA);
        return NULL;
    }
    return win_identity_find(encoded->bytes + 12, name, machine != 0);
}
typedef struct {
    NCRYPT_KEY_HANDLE key;
    BOOL owned;
    PCCERT_CONTEXT certificate;
} WinIdentityKey;
static inline bool win_identity_acquire(WinIdentityKey *out, const MinyarBytes *encoded) {
    memset(out, 0, sizeof(*out));
    out->certificate = win_identity_certificate(encoded);
    DWORD spec = 0;
    if (!out->certificate)
        return false;
    HCRYPTPROV_OR_NCRYPT_KEY_HANDLE acquired = 0;
    BOOL acquired_ok = CryptAcquireCertificatePrivateKey(out->certificate,
                                                         CRYPT_ACQUIRE_ONLY_NCRYPT_KEY_FLAG |
                                                             CRYPT_ACQUIRE_SILENT_FLAG |
                                                             CRYPT_ACQUIRE_COMPARE_KEY_FLAG,
                                                         NULL, &acquired, &spec, &out->owned);
    bool valid = acquired_ok && spec == CERT_NCRYPT_KEY_SPEC;
    if (valid)
        out->key = (NCRYPT_KEY_HANDLE)acquired;
    else {
        DWORD status = acquired_ok ? ERROR_NOT_SUPPORTED : GetLastError();
        if (acquired_ok && out->owned)
            CryptReleaseContext((HCRYPTPROV)acquired, 0);
        CertFreeCertificateContext(out->certificate);
        out->certificate = NULL;
        SetLastError(status ? status : ERROR_ACCESS_DENIED);
    }
    return valid;
}
static inline void win_identity_release(WinIdentityKey *value) {
    if (value->key && value->owned)
        NCryptFreeObject(value->key);
    if (value->certificate)
        CertFreeCertificateContext(value->certificate);
    memset(value, 0, sizeof(*value));
}
#endif
