/* CNG imports can label an ECDSA PKCS8 key ECDH (the .NET ECDsaCng
 * implementation accepts that case). TLS still requires the exact NIST curve,
 * digest and signature scheme; equal bit length never identifies a curve. */
#include "../runtime/native/tlsverify.c"
#include <assert.h>

void minyar_rc_release(void *);

static MinyarBytes *fixture(const char *path) {
    FILE *file = fopen(path, "rb");
    assert(file && !fseek(file, 0, SEEK_END));
    long length = ftell(file);
    assert(length > 0 && length < MAX_CERT_BYTES && !fseek(file, 0, SEEK_SET));
    MinyarBytes *bytes = minyar_bytes_new(length);
    assert(fread((void *)bytes->bytes, 1, (size_t)length, file) == (size_t)length);
    assert(!fclose(file));
    return bytes;
}

static void scheme_matrix(void) {
    const wchar_t *algorithms[] = {L"ECDSA_P256", L"ECDH_P256", L"ECDSA_P384",     L"ECDH_P384",
                                   L"ECDSA_P521", L"ECDH_P521", L"ECDSA",          L"ECDH",
                                   L"DSA",        L"RSA",       L"ECDSA_P256junk", L""};
    const wchar_t *curves[] = {NULL,        L"",          L"nistP256",        L"nistP384",
                               L"nistP521", L"secp256k1", L"brainpoolP256r1", L"nistP256junk"};
    DWORD lengths[] = {0, 255, 256, 384, 521, 2048};
    long long schemes[] = {0, 0x0403, 0x0503, 0x0603, 0x0804, 0x0805, 0x0806, 0x0401};
    for (size_t a = 0; a < sizeof(algorithms) / sizeof(*algorithms); a++)
        for (size_t c = 0; c < sizeof(curves) / sizeof(*curves); c++)
            for (size_t b = 0; b < sizeof(lengths) / sizeof(*lengths); b++)
                for (size_t s = 0; s < sizeof(schemes) / sizeof(*schemes); s++) {
                    bool rsa = a == 9 && lengths[b] >= 2048 && s >= 4 && s <= 6;
                    bool ec = s >= 1 && s <= 3 && lengths[b] == lengths[s + 1];
                    /* Specific algorithm IDs already establish the curve. Generic
                     * IDs require the independent provider curve-name property. */
                    bool named = a < 6 && a / 2 == s - 1;
                    bool generic = (a == 6 || a == 7) && c == s + 1;
                    assert(windows_scheme(algorithms[a], lengths[b], schemes[s], curves[c]) ==
                           (rsa || (ec && (named || generic))));
                }
}

static void describe(const MinyarBytes *private_key) {
    NCRYPT_PROV_HANDLE provider = 0;
    NCRYPT_KEY_HANDLE key = 0;
    SECURITY_STATUS status = NCryptOpenStorageProvider(&provider, MS_KEY_STORAGE_PROVIDER, 0);
    if (!status)
        status = NCryptImportKey(provider, 0, NCRYPT_PKCS8_PRIVATE_KEY_BLOB, NULL, &key,
                                 (PBYTE)private_key->bytes, (DWORD)private_key->byte_length,
                                 NCRYPT_SILENT_FLAG);
    wchar_t algorithm[64] = {0}, group[64] = {0}, curve[64] = {0};
    DWORD bits = 0, written = 0;
    if (!status) {
        NCryptGetProperty(key, NCRYPT_ALGORITHM_PROPERTY, (PBYTE)algorithm, sizeof(algorithm),
                          &written, 0);
        NCryptGetProperty(key, NCRYPT_ALGORITHM_GROUP_PROPERTY, (PBYTE)group, sizeof(group),
                          &written, 0);
        NCryptGetProperty(key, L"ECCCurveName", (PBYTE)curve, sizeof(curve), &written, 0);
        NCryptGetProperty(key, NCRYPT_LENGTH_PROPERTY, (PBYTE)&bits, sizeof(bits), &written, 0);
    }
    /* Public metadata only. Never print or export the key material. */
    printf("CNG import status=%08lx algorithm=%ls group=%ls curve=%ls bits=%lu\n",
           (unsigned long)status, algorithm, group, curve, (unsigned long)bits);
    if (key)
        NCryptFreeObject(key);
    if (provider)
        NCryptFreeObject(provider);
}

int main(int argc, char **argv) {
    assert(argc == 9);
    scheme_matrix();
    const unsigned char data[] = {0, 1, 2, 255, 'T', 'L', 'S'};
    MinyarBytes content = {data, sizeof(data), sizeof(data), NULL, NULL};
    const long long schemes[] = {0x0403, 0x0503, 0x0603};
    for (size_t i = 0; i < 4; i++) {
        MinyarBytes *key = fixture(argv[1 + 2 * i]);
        MinyarBytes *certificate = fixture(argv[2 + 2 * i]);
        describe(key);
        for (size_t s = 0; s < 3; s++) {
            MinyarBytes *signature = minyar_tlsverify_sign(key, schemes[s], &content);
            if (i < 3 && i == s) {
                assert(signature->byte_length > 0);
                assert(minyar_tlsverify_signature(certificate, schemes[s], &content, signature));
                MinyarBytes changed = content;
                changed.byte_length--;
                assert(!minyar_tlsverify_signature(certificate, schemes[s], &changed, signature));
                ((unsigned char *)signature->bytes)[signature->byte_length - 1] ^= 1;
                assert(!minyar_tlsverify_signature(certificate, schemes[s], &content, signature));
            } else {
                assert(!signature->byte_length);
            }
            minyar_rc_release(signature);
        }
        minyar_rc_release(key);
        minyar_rc_release(certificate);
    }
    puts("Windows CNG NIST signing and mismatched/non-NIST scheme rejection verified");
    return 0;
}
