/* Independent nonexportable CNG identity for the actual OpenSSL mTLS peer.
 * Writes PUBLIC DER only, and removes its test certificate/key on stdin EOF. */
#include "../runtime/minyar_native.h"
#include <windows.h>
#include <wincrypt.h>
#include <bcrypt.h>
#include <ncrypt.h>
#include <stdio.h>
static NCRYPT_PROV_HANDLE provider;
static NCRYPT_KEY_HANDLE key;
static PCCERT_CONTEXT certificate, stored;
static HCERTSTORE store;
static void cleanup(void) {
    if (stored && !CertDeleteCertificateFromStore(stored))
        fputs("failed to remove owned test certificate\n", stderr);
    if (store)
        CertCloseStore(store, 0);
    if (certificate)
        CertFreeCertificateContext(certificate);
    if (key && NCryptDeleteKey(key, 0) != ERROR_SUCCESS)
        fputs("failed to remove owned test key\n", stderr);
    if (provider)
        NCryptFreeObject(provider);
}
#define CHECK(condition)                                                                           \
    do {                                                                                           \
        if (!(condition)) {                                                                        \
            fprintf(stderr, "identity fixture failed at line %d\n", __LINE__);                     \
            return 1;                                                                              \
        }                                                                                          \
    } while (0)
int main(int argc, char **argv) {
    if (argc != 2)
        return 2;
    atexit(cleanup);
    wchar_t key_name[96];
    swprintf(key_name, 96, L"Minyar Schannel test %lu %llu", GetCurrentProcessId(),
             GetTickCount64());
    CHECK(NCryptOpenStorageProvider(&provider, MS_KEY_STORAGE_PROVIDER, 0) == ERROR_SUCCESS);
    CHECK(NCryptCreatePersistedKey(provider, &key, BCRYPT_RSA_ALGORITHM, key_name, 0, 0) ==
          ERROR_SUCCESS);
    DWORD bits = 2048;
    CHECK(NCryptSetProperty(key, NCRYPT_LENGTH_PROPERTY, (PBYTE)&bits, sizeof(bits), 0) ==
          ERROR_SUCCESS);
    CHECK(NCryptFinalizeKey(key, 0) == ERROR_SUCCESS);
    DWORD exported = 0;
    CHECK(NCryptExportKey(key, 0, NCRYPT_PKCS8_PRIVATE_KEY_BLOB, NULL, NULL, 0, &exported, 0) !=
          ERROR_SUCCESS);
    BYTE name_bytes[256];
    DWORD name_size = sizeof(name_bytes);
    CHECK(CertStrToNameW(X509_ASN_ENCODING, L"CN=Minyar isolated Schannel device",
                         CERT_X500_NAME_STR, NULL, name_bytes, &name_size, NULL));
    CERT_NAME_BLOB name = {name_size, name_bytes};
    CRYPT_KEY_PROV_INFO info = {key_name, MS_KEY_STORAGE_PROVIDER, 0, 0, 0,
                                NULL,     CERT_NCRYPT_KEY_SPEC};
    CRYPT_ALGORITHM_IDENTIFIER algorithm = {szOID_RSA_SHA256RSA, {0, NULL}};
    certificate = CertCreateSelfSignCertificate((HCRYPTPROV_OR_NCRYPT_KEY_HANDLE)key, &name, 0,
                                                &info, &algorithm, NULL, NULL, NULL);
    CHECK(certificate);
    store = CertOpenStore(CERT_STORE_PROV_SYSTEM_W, 0, 0, CERT_SYSTEM_STORE_CURRENT_USER, L"My");
    CHECK(store);
    CHECK(CertAddCertificateContextToStore(store, certificate, CERT_STORE_ADD_NEW, &stored));
    FILE *public_file = fopen(argv[1], "wb");
    CHECK(public_file);
    bool wrote = fwrite(certificate->pbCertEncoded, 1, certificate->cbCertEncoded, public_file) ==
                 certificate->cbCertEncoded;
    CHECK(fclose(public_file) == 0 && wrote);
    BYTE digest[32];
    DWORD size = sizeof(digest);
    CHECK(CryptHashCertificate2(BCRYPT_SHA256_ALGORITHM, 0, NULL, certificate->pbCertEncoded,
                                certificate->cbCertEncoded, digest, &size));
    for (unsigned i = 0; i < 32; i++)
        printf("%02x", digest[i]);
    puts("");
    fflush(stdout);
    getchar();
    return 0;
}
