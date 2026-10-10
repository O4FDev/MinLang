/* Real Windows CNG/CertStore fixture. Keys are nonexportable test keys in an
 * isolated VM/CI user store and removed before exit; no production credential. */
#include "../runtime/minyar_native.h"
#define SECURITY_WIN32
#include <windows.h>
#include <wincrypt.h>
#include <bcrypt.h>
#include <ncrypt.h>
#include <assert.h>

extern MinyarBytes *minyar_wincert_identity(const MinyarText *, const MinyarText *, bool);
extern MinyarBytes *minyar_tlsverify_sign(const MinyarBytes *, long long, const MinyarBytes *);
extern bool minyar_tlsverify_signature(const MinyarBytes *, long long, const MinyarBytes *,
                                       const MinyarBytes *);
extern void minyar_rc_release(void *);

static MinyarText *text(const char *value) {
    return minyar_native_copy_text((const unsigned char *)value, (long long)strlen(value));
}
static unsigned word(const unsigned char *p) {
    return p[0] | (unsigned)p[1] << 8 | (unsigned)p[2] << 16 | (unsigned)p[3] << 24;
}

int main(void) {
    NCRYPT_PROV_HANDLE provider = 0;
    NCRYPT_KEY_HANDLE key = 0;
    wchar_t key_name[96];
    swprintf(key_name, 96, L"Minyar test %lu %llu", GetCurrentProcessId(), GetTickCount64());
    assert(NCryptOpenStorageProvider(&provider, MS_KEY_STORAGE_PROVIDER, 0) == ERROR_SUCCESS);
    assert(NCryptCreatePersistedKey(provider, &key, BCRYPT_RSA_ALGORITHM, key_name, 0, 0) ==
           ERROR_SUCCESS);
    DWORD bits = 2048;
    assert(NCryptSetProperty(key, NCRYPT_LENGTH_PROPERTY, (PBYTE)&bits, sizeof(bits), 0) ==
           ERROR_SUCCESS);
    assert(NCryptFinalizeKey(key, 0) == ERROR_SUCCESS);
    DWORD exported = 0;
    assert(NCryptExportKey(key, 0, NCRYPT_PKCS8_PRIVATE_KEY_BLOB, NULL, NULL, 0, &exported, 0) !=
           ERROR_SUCCESS);
    BYTE name_bytes[256];
    DWORD name_size = sizeof(name_bytes);
    assert(CertStrToNameW(X509_ASN_ENCODING, L"CN=Minyar isolated identity test",
                          CERT_X500_NAME_STR, NULL, name_bytes, &name_size, NULL));
    CERT_NAME_BLOB name = {name_size, name_bytes};
    CRYPT_KEY_PROV_INFO info = {key_name, MS_KEY_STORAGE_PROVIDER, 0, 0, 0,
                                NULL,     CERT_NCRYPT_KEY_SPEC};
    CRYPT_ALGORITHM_IDENTIFIER algorithm = {szOID_RSA_SHA256RSA, {0, NULL}};
    PCCERT_CONTEXT certificate = CertCreateSelfSignCertificate(
        (HCRYPTPROV_OR_NCRYPT_KEY_HANDLE)key, &name, 0, &info, &algorithm, NULL, NULL, NULL);
    assert(certificate);
    HCERTSTORE store =
        CertOpenStore(CERT_STORE_PROV_SYSTEM_W, 0, 0, CERT_SYSTEM_STORE_CURRENT_USER, L"My");
    assert(store);
    PCCERT_CONTEXT stored = NULL;
    assert(CertAddCertificateContextToStore(store, certificate, CERT_STORE_ADD_NEW, &stored));
    BYTE digest[32];
    DWORD digest_size = 32;
    assert(CryptHashCertificate2(BCRYPT_SHA256_ALGORITHM, 0, NULL, certificate->pbCertEncoded,
                                 certificate->cbCertEncoded, digest, &digest_size));
    char fingerprint[65];
    for (unsigned i = 0; i < 32; i++)
        sprintf(fingerprint + i * 2, "%02x", digest[i]);
    MinyarText *expected = text(fingerprint), *my = text("My");
    MinyarBytes *envelope = minyar_wincert_identity(expected, my, false);
    assert(envelope->byte_length >= 16 && word(envelope->bytes) == 0);
    unsigned cert_size = word(envelope->bytes + 8), ref_size = word(envelope->bytes + 12);
    assert(cert_size == certificate->cbCertEncoded && ref_size > 44);
    assert(16ULL + cert_size + ref_size == (unsigned long long)envelope->byte_length);
    MinyarBytes *public_cert = minyar_native_copy_text(envelope->bytes + 16, cert_size);
    MinyarBytes *reference = minyar_native_copy_text(envelope->bytes + 16 + cert_size, ref_size);
    MinyarBytes *message = text("device certificate signing challenge");
    MinyarBytes *signature = minyar_tlsverify_sign(reference, 0x0804, message);
    assert(signature->byte_length == 256);
    assert(minyar_tlsverify_signature(public_cert, 0x0804, message, signature));
    ((unsigned char *)signature->bytes)[0] ^= 1;
    assert(!minyar_tlsverify_signature(public_cert, 0x0804, message, signature));
    MinyarBytes *wrong_scheme = minyar_tlsverify_sign(reference, 0x0403, message);
    assert(wrong_scheme->byte_length == 0);
    for (long long length = 0; length < reference->byte_length; length++) {
        MinyarBytes truncated = *reference;
        truncated.byte_length = length;
        MinyarBytes *bad = minyar_tlsverify_sign(&truncated, 0x0804, message);
        assert(!bad->byte_length);
        minyar_rc_release(bad);
    }
    MinyarBytes *extended = minyar_bytes_new(reference->byte_length + 1);
    memcpy((void *)extended->bytes, reference->bytes, (size_t)reference->byte_length);
    MinyarBytes *bad = minyar_tlsverify_sign(extended, 0x0804, message);
    assert(!bad->byte_length);
    minyar_rc_release(bad);
    minyar_rc_release(extended);
    ((unsigned char *)reference->bytes)[8] = 2;
    bad = minyar_tlsverify_sign(reference, 0x0804, message);
    assert(!bad->byte_length);
    minyar_rc_release(bad);
    ((unsigned char *)reference->bytes)[8] = 0;
    ((unsigned char *)reference->bytes)[reference->byte_length - 1] ^= 1;
    MinyarBytes *wrong_identity = minyar_tlsverify_sign(reference, 0x0804, message);
    assert(wrong_identity->byte_length == 0);
    MinyarText *missing = text("0000000000000000000000000000000000000000000000000000000000000000");
    MinyarBytes *absent = minyar_wincert_identity(missing, my, false);
    assert(absent->byte_length == 16 && word(absent->bytes) == 9);
    MinyarText *invalid = text("../My");
    bad = minyar_wincert_identity(expected, invalid, false);
    assert(bad->byte_length == 16 && word(bad->bytes) == 6);
    minyar_rc_release(bad);
    minyar_rc_release(invalid);
    invalid = text("not-a-sha256-fingerprint");
    bad = minyar_wincert_identity(invalid, my, false);
    assert(bad->byte_length == 16 && word(bad->bytes) == 6);
    minyar_rc_release(bad);
    minyar_rc_release(invalid);
    assert(CertDeleteCertificateFromStore(stored));
    CertCloseStore(store, 0);
    CertFreeCertificateContext(certificate);
    assert(NCryptDeleteKey(key, 0) == ERROR_SUCCESS);
    NCryptFreeObject(provider);
    minyar_rc_release(expected);
    minyar_rc_release(my);
    minyar_rc_release(envelope);
    minyar_rc_release(public_cert);
    minyar_rc_release(reference);
    minyar_rc_release(message);
    minyar_rc_release(signature);
    minyar_rc_release(wrong_scheme);
    minyar_rc_release(wrong_identity);
    minyar_rc_release(missing);
    minyar_rc_release(absent);
    puts("Windows nonexportable CNG certificate identity and TLS signing verified");
    return 0;
}
