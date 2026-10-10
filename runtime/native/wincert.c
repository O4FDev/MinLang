#include "../minyar_native.h"
#include <stdint.h>
#include "windows_identity.h"

MinyarBytes *minyar_wincert_identity(const MinyarText *fingerprint, const MinyarText *store,
                                     bool machine) {
    MinyarBytes *result = minyar_bytes_new(16);
    DWORD status = ERROR_INVALID_DATA;
    unsigned error = 6;
    PCCERT_CONTEXT certificate = NULL;
    wchar_t name[65];
    unsigned char digest[32];
    if (fingerprint->byte_length != 64 ||
        !win_identity_store_name(store->bytes, (size_t)store->byte_length, name))
        goto done;
    for (unsigned i = 0; i < 32; i++) {
        unsigned value = 0;
        for (unsigned j = 0; j < 2; j++) {
            unsigned char c = fingerprint->bytes[2 * i + j];
            if (c >= '0' && c <= '9')
                value = value * 16 + c - '0';
            else if (c >= 'a' && c <= 'f')
                value = value * 16 + c - 'a' + 10;
            else
                goto done;
        }
        digest[i] = (unsigned char)value;
    }
    certificate = win_identity_find(digest, name, machine);
    if (!certificate) {
        status = GetLastError();
        error = status == ERROR_ACCESS_DENIED ? 8 : 9;
        goto done;
    }
    if (certificate->cbCertEncoded > 1048576)
        goto done;
    MinyarBytes *reference = minyar_bytes_new(44 + store->byte_length);
    unsigned char *bytes = (unsigned char *)reference->bytes;
    memcpy(bytes, "MWI1", 4);
    win_identity_put(bytes + 4, (uint32_t)store->byte_length);
    win_identity_put(bytes + 8, machine ? 1 : 0);
    memcpy(bytes + 12, digest, 32);
    memcpy(bytes + 44, store->bytes, (size_t)store->byte_length);
    WinIdentityKey acquired;
    if (!win_identity_acquire(&acquired, reference)) {
        status = GetLastError();
        if (!status)
            status = ERROR_ACCESS_DENIED;
        error = status == ERROR_ACCESS_DENIED || status == (DWORD)NTE_PERM ||
                        status == (DWORD)NTE_SILENT_CONTEXT
                    ? 8
                    : 7;
    } else {
        win_identity_release(&acquired);
        unsigned char *tail =
            minyar_bytes_extend(result, certificate->cbCertEncoded + reference->byte_length);
        memcpy(tail, certificate->pbCertEncoded, certificate->cbCertEncoded);
        memcpy(tail + certificate->cbCertEncoded, reference->bytes, (size_t)reference->byte_length);
        win_identity_put((unsigned char *)result->bytes + 8, certificate->cbCertEncoded);
        win_identity_put((unsigned char *)result->bytes + 12, (uint32_t)reference->byte_length);
        status = ERROR_SUCCESS;
    }
    extern void minyar_rc_release(void *);
    minyar_rc_release(reference);
done:
    if (certificate)
        CertFreeCertificateContext(certificate);
    win_identity_put((unsigned char *)result->bytes, status ? error : 0);
    win_identity_put((unsigned char *)result->bytes + 4, status);
    return result;
}
