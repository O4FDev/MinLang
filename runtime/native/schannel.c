/* Socket-independent Windows TLS. OS trust is automatic by default; explicit
 * private roots are verified through tlsverify before any plaintext is exposed. */
#define SECURITY_WIN32
#define SCHANNEL_USE_BLACKLISTS
#define WIN32_LEAN_AND_MEAN
#include "../minyar_native.h"
#include <stdint.h>
#include <winsock2.h>
#include <windows.h>
#include <winternl.h>
#include <security.h>
#include <schannel.h>
#include "windows_identity.h"

#define CHANNEL_LIMIT (1024 * 1024)
extern MinyarText *minyar_tlsverify_chain(const MinyarText *, const MinyarBytes *,
                                          const MinyarBytes *);
extern void minyar_rc_release(void *);
typedef struct {
    unsigned char *data;
    size_t length, capacity;
} ChannelBuffer;
typedef struct {
    CredHandle credentials;
    CtxtHandle context;
    bool have_credentials, have_context, supplied, internal_handshake, close_sent;
    unsigned state, error;
    SECURITY_STATUS native;
    ULONG attributes;
    SecPkgContext_StreamSizes sizes;
    DWORD protocol;
    WinIdentityKey identity;
    char host[254];
    wchar_t target[254];
    ChannelBuffer roots, input, outgoing, incoming;
} Channel;
typedef struct {
    uint32_t generation;
    Channel *channel;
} ChannelSlot;
static ChannelSlot *slots;
static size_t slot_count;
static volatile LONG owner;

static void channel_thread(void) {
    LONG current = (LONG)GetCurrentThreadId();
    LONG established = InterlockedCompareExchange(&owner, current, 0);
    if (established && established != current)
        minyar_native_stop("SChannel sessions require their owning thread.");
}
static MinyarBytes *channel_result(unsigned error, SECURITY_STATUS native, int64_t value) {
    MinyarBytes *b = minyar_bytes_new(16);
    memcpy((void *)b->bytes, &error, 4);
    memcpy((void *)(b->bytes + 4), &native, 4);
    memcpy((void *)(b->bytes + 8), &value, 8);
    return b;
}
static Channel *channel_get(long long id) {
    uint32_t index = (uint32_t)id, generation = (uint32_t)((uint64_t)id >> 32);
    return index && index <= slot_count && slots[index - 1].generation == generation
               ? slots[index - 1].channel
               : NULL;
}
static MinyarBytes *channel_status(Channel *c, int64_t value) {
    return channel_result(c ? c->error : 4, c ? c->native : SEC_E_INVALID_HANDLE, value);
}
static bool channel_append(ChannelBuffer *b, const void *data, size_t length) {
    if (length > CHANNEL_LIMIT - b->length)
        return false;
    size_t needed = b->length + length;
    if (needed > b->capacity) {
        size_t capacity = b->capacity ? b->capacity : 4096;
        while (capacity < needed)
            capacity *= 2;
        unsigned char *fresh = realloc(b->data, capacity);
        if (!fresh)
            return false;
        b->data = fresh;
        b->capacity = capacity;
    }
    if (length)
        memcpy(b->data + b->length, data, length);
    b->length = needed;
    return true;
}
static void channel_clear(ChannelBuffer *b, bool secret) {
    if (secret && b->data)
        SecureZeroMemory(b->data, b->capacity);
    free(b->data);
    memset(b, 0, sizeof(*b));
}
static void channel_release_security(Channel *c) {
    if (c->have_context) {
        DeleteSecurityContext(&c->context);
        c->have_context = false;
    }
    if (c->have_credentials) {
        FreeCredentialsHandle(&c->credentials);
        c->have_credentials = false;
    }
    win_identity_release(&c->identity);
}
static void channel_fail(Channel *c, unsigned error, SECURITY_STATUS native) {
    c->state = 3;
    c->error = error;
    c->native = native;
    channel_release_security(c);
    channel_clear(&c->input, false);
    channel_clear(&c->outgoing, false);
    channel_clear(&c->incoming, true);
}
static unsigned channel_security_error(SECURITY_STATUS status) {
    if (status == SEC_E_INSUFFICIENT_MEMORY)
        return 7;
    if (status == SEC_E_WRONG_PRINCIPAL || status == SEC_E_CERT_EXPIRED ||
        status == SEC_E_UNTRUSTED_ROOT || status == SEC_E_CERT_UNKNOWN ||
        status == SEC_E_NO_CREDENTIALS || status == SEC_E_UNKNOWN_CREDENTIALS)
        return 11;
    return 10;
}
static void channel_dispose(Channel *c) {
    channel_release_security(c);
    channel_clear(&c->roots, false);
    channel_clear(&c->input, false);
    channel_clear(&c->outgoing, false);
    channel_clear(&c->incoming, true);
    free(c);
}
static bool channel_roots(const MinyarBytes *bytes) {
    if (bytes->byte_length < 0 || bytes->byte_length > CHANNEL_LIMIT)
        return false;
    size_t at = 0, length = (size_t)bytes->byte_length;
    unsigned count = 0;
    while (at < length) {
        if (++count > 16 || length - at < 5)
            return false;
        size_t n = (size_t)bytes->bytes[at] << 16 | (size_t)bytes->bytes[at + 1] << 8 |
                   bytes->bytes[at + 2];
        at += 3;
        if (!n || n > length - at - 2)
            return false;
        PCCERT_CONTEXT cert =
            CertCreateCertificateContext(X509_ASN_ENCODING, bytes->bytes + at, (DWORD)n);
        if (!cert)
            return false;
        CertFreeCertificateContext(cert);
        at += n;
        size_t extensions = (size_t)bytes->bytes[at] << 8 | bytes->bytes[at + 1];
        at += 2;
        if (extensions > length - at)
            return false;
        at += extensions;
    }
    return true;
}
static bool channel_pack_certificate(MinyarBytes *out, PCCERT_CONTEXT certificate) {
    DWORD n = certificate->cbCertEncoded;
    if (!n || n > CHANNEL_LIMIT || out->byte_length > CHANNEL_LIMIT - (long long)n - 5)
        return false;
    unsigned char *p = minyar_bytes_extend(out, n + 5);
    p[0] = (unsigned char)(n >> 16);
    p[1] = (unsigned char)(n >> 8);
    p[2] = (unsigned char)n;
    memcpy(p + 3, certificate->pbCertEncoded, n);
    p[n + 3] = p[n + 4] = 0;
    return true;
}
static bool channel_authenticate(Channel *c) {
    PCCERT_CONTEXT leaf = NULL;
    SECURITY_STATUS status =
        QueryContextAttributesW(&c->context, SECPKG_ATTR_REMOTE_CERT_CONTEXT, &leaf);
    if (status || !leaf) {
        channel_fail(c, 11, status ? status : SEC_E_CERT_UNKNOWN);
        return false;
    }
    MinyarBytes *chain = minyar_bytes_new(0);
    unsigned count = 1;
    bool valid = channel_pack_certificate(chain, leaf);
    PCCERT_CONTEXT intermediate = NULL;
    if (valid && leaf->hCertStore)
        while ((intermediate = CertEnumCertificatesInStore(leaf->hCertStore, intermediate))) {
            if (intermediate->cbCertEncoded == leaf->cbCertEncoded &&
                !memcmp(intermediate->pbCertEncoded, leaf->pbCertEncoded, leaf->cbCertEncoded))
                continue;
            if (++count > 16 || !channel_pack_certificate(chain, intermediate)) {
                valid = false;
                CertFreeCertificateContext(intermediate);
                break;
            }
        }
    MinyarText host = {(const unsigned char *)c->host, (long long)strlen(c->host), 0, NULL, NULL};
    MinyarBytes roots = {c->roots.data, (long long)c->roots.length, 0, NULL, NULL};
    MinyarText *error = valid ? minyar_tlsverify_chain(&host, chain, &roots) : NULL;
    valid = valid && error && !error->byte_length;
    if (error)
        minyar_rc_release(error);
    minyar_rc_release(chain);
    CertFreeCertificateContext(leaf);
    if (!valid) {
        channel_fail(c, 11, SEC_E_CERT_UNKNOWN);
        return false;
    }
    SecPkgContext_ConnectionInfo connection = {0};
    status = QueryContextAttributesW(&c->context, SECPKG_ATTR_CONNECTION_INFO, &connection);
    if (status || !(connection.dwProtocol & (SP_PROT_TLS1_2_CLIENT | SP_PROT_TLS1_3_CLIENT)) ||
        !(c->attributes & ISC_RET_CONFIDENTIALITY) || !(c->attributes & ISC_RET_STREAM)) {
        channel_fail(c, 10, status ? status : SEC_E_ALGORITHM_MISMATCH);
        return false;
    }
    c->protocol = connection.dwProtocol;
    status = QueryContextAttributesW(&c->context, SECPKG_ATTR_STREAM_SIZES, &c->sizes);
    if (status || !c->sizes.cbMaximumMessage || c->sizes.cbMaximumMessage > CHANNEL_LIMIT ||
        c->sizes.cbHeader > CHANNEL_LIMIT || c->sizes.cbTrailer > CHANNEL_LIMIT) {
        channel_fail(c, 10, status ? status : SEC_E_INVALID_TOKEN);
        return false;
    }
    c->state = 1;
    c->internal_handshake = false;
    return true;
}
static ULONG channel_flags(Channel *c) {
    return ISC_REQ_SEQUENCE_DETECT | ISC_REQ_REPLAY_DETECT | ISC_REQ_CONFIDENTIALITY |
           ISC_REQ_EXTENDED_ERROR | ISC_REQ_ALLOCATE_MEMORY | ISC_REQ_STREAM |
           (c->supplied ? ISC_REQ_USE_SUPPLIED_CREDS : 0);
}
static bool channel_handshake(Channel *c) {
    SecBuffer incoming[2] = {{(ULONG)c->input.length, SECBUFFER_TOKEN, NULL},
                             {0, SECBUFFER_EMPTY, NULL}};
    unsigned char *copy = c->input.length ? malloc(c->input.length) : NULL;
    if (c->input.length && !copy) {
        channel_fail(c, 7, SEC_E_INSUFFICIENT_MEMORY);
        return false;
    }
    if (copy)
        memcpy(copy, c->input.data, c->input.length);
    incoming[0].pvBuffer = copy;
    SecBufferDesc input = {SECBUFFER_VERSION, 2, incoming};
    SecBuffer outgoing = {0, SECBUFFER_TOKEN, NULL};
    SecBufferDesc output = {SECBUFFER_VERSION, 1, &outgoing};
    SECURITY_STATUS status = InitializeSecurityContextW(
        &c->credentials, c->have_context ? &c->context : NULL, c->target, channel_flags(c), 0,
        SECURITY_NATIVE_DREP, c->have_context ? &input : NULL, 0, &c->context, &output,
        &c->attributes, NULL);
    if (status == SEC_E_OK || status == SEC_I_CONTINUE_NEEDED ||
        status == SEC_I_INCOMPLETE_CREDENTIALS)
        c->have_context = true;
    bool appended = true;
    if (outgoing.pvBuffer) {
        if (status == SEC_E_OK || status == SEC_I_CONTINUE_NEEDED)
            appended = channel_append(&c->outgoing, outgoing.pvBuffer, outgoing.cbBuffer);
        FreeContextBuffer(outgoing.pvBuffer);
    }
    free(copy);
    if (!appended) {
        channel_fail(c, 10, SEC_E_BUFFER_TOO_SMALL);
        return false;
    }
    if (status == SEC_E_INCOMPLETE_MESSAGE)
        return false;
    if (status == SEC_I_INCOMPLETE_CREDENTIALS && !c->supplied) {
        c->supplied = true;
        c->internal_handshake = true;
        return true;
    }
    if (status != SEC_E_OK && status != SEC_I_CONTINUE_NEEDED) {
        channel_fail(c, channel_security_error(status), status);
        return false;
    }
    size_t extra = incoming[1].BufferType == SECBUFFER_EXTRA ? incoming[1].cbBuffer : 0;
    if (extra > c->input.length) {
        channel_fail(c, 10, SEC_E_INVALID_TOKEN);
        return false;
    }
    if (extra && extra < c->input.length)
        memmove(c->input.data, c->input.data + c->input.length - extra, extra);
    c->input.length = extra;
    c->internal_handshake = false;
    if (status == SEC_E_OK)
        return channel_authenticate(c);
    return extra > 0;
}
static bool channel_inside(ChannelBuffer *b, const SecBuffer *part) {
    uintptr_t start = (uintptr_t)b->data, address = (uintptr_t)part->pvBuffer;
    return part->cbBuffer <= b->length && address >= start &&
           address - start <= b->length - part->cbBuffer;
}
static bool channel_decrypt(Channel *c) {
    SecBuffer parts[4] = {{(ULONG)c->input.length, SECBUFFER_DATA, c->input.data},
                          {0, SECBUFFER_EMPTY, NULL},
                          {0, SECBUFFER_EMPTY, NULL},
                          {0, SECBUFFER_EMPTY, NULL}};
    SecBufferDesc input = {SECBUFFER_VERSION, 4, parts};
    SECURITY_STATUS status = DecryptMessage(&c->context, &input, 0, NULL);
    if (status == SEC_E_INCOMPLETE_MESSAGE)
        return false;
    if (status != SEC_E_OK && status != SEC_I_CONTEXT_EXPIRED && status != SEC_I_RENEGOTIATE) {
        channel_fail(c, channel_security_error(status), status);
        return false;
    }
    size_t extra = 0;
    for (unsigned i = 0; i < 4; i++) {
        /* Handshake/control records are never application plaintext. */
        if (status == SEC_E_OK && parts[i].BufferType == SECBUFFER_DATA && parts[i].cbBuffer &&
            (!channel_inside(&c->input, parts + i) ||
             !channel_append(&c->incoming, parts[i].pvBuffer, parts[i].cbBuffer))) {
            channel_fail(c, 10, SEC_E_BUFFER_TOO_SMALL);
            return false;
        }
        if (parts[i].BufferType == SECBUFFER_EXTRA)
            extra = parts[i].cbBuffer;
    }
    if (extra > c->input.length) {
        channel_fail(c, 10, SEC_E_INVALID_TOKEN);
        return false;
    }
    if (extra && extra < c->input.length)
        memmove(c->input.data, c->input.data + c->input.length - extra, extra);
    c->input.length = extra;
    if (status == SEC_I_CONTEXT_EXPIRED) {
        if (extra) {
            channel_fail(c, 10, SEC_E_INVALID_TOKEN);
            return false;
        }
        c->state = 2;
        return false;
    }
    if (status == SEC_I_RENEGOTIATE) {
        if (!(c->protocol & SP_PROT_TLS1_3_CLIENT)) {
            channel_fail(c, 10, SEC_I_RENEGOTIATE);
            return false;
        }
        c->state = 0;
        c->internal_handshake = true;
        return true;
    }
    return extra > 0;
}
static void channel_process(Channel *c) {
    for (unsigned turns = 0; turns < 64 && !c->error; turns++) {
        if (c->state == 0) {
            if (!c->input.length && !c->internal_handshake)
                return;
            if (!channel_handshake(c))
                return;
        } else if (c->state == 1) {
            if (!c->input.length || !channel_decrypt(c))
                return;
        } else
            return;
    }
}
MinyarBytes *minyar_schannel_clientRaw(const MinyarText *host, const MinyarBytes *roots,
                                       const MinyarBytes *identity) {
    channel_thread();
    if (host->byte_length < 1 || host->byte_length > 253 || !channel_roots(roots))
        return channel_result(6, SEC_E_INVALID_TOKEN, 0);
    for (long long i = 0; i < host->byte_length; i++)
        if (host->bytes[i] <= 32 || host->bytes[i] >= 127 || host->bytes[i] == '/' ||
            host->bytes[i] == '\\')
            return channel_result(6, SEC_E_INVALID_TOKEN, 0);
    Channel *c = calloc(1, sizeof(*c));
    if (!c)
        return channel_result(7, SEC_E_INSUFFICIENT_MEMORY, 0);
    memcpy(c->host, host->bytes, (size_t)host->byte_length);
    for (long long i = 0; i < host->byte_length; i++)
        c->target[i] = host->bytes[i];
    if (!channel_append(&c->roots, roots->bytes, (size_t)roots->byte_length)) {
        channel_dispose(c);
        return channel_result(7, SEC_E_INSUFFICIENT_MEMORY, 0);
    }
    if (identity->byte_length && !win_identity_acquire(&c->identity, identity)) {
        DWORD status = GetLastError();
        channel_dispose(c);
        return channel_result(status == ERROR_ACCESS_DENIED ? 8 : 11, (SECURITY_STATUS)status, 0);
    }
    TLS_PARAMETERS parameters = {0};
    parameters.grbitDisabledProtocols = SP_PROT_PCT1 | SP_PROT_SSL2 | SP_PROT_SSL3 |
                                        SP_PROT_TLS1_0 | SP_PROT_TLS1_1 | SP_PROT_DTLS1_0 |
                                        SP_PROT_DTLS1_2;
    SCH_CREDENTIALS credentials = {0};
    credentials.dwVersion = SCH_CREDENTIALS_VERSION;
    credentials.dwFlags =
        SCH_CRED_NO_DEFAULT_CREDS | SCH_USE_STRONG_CRYPTO |
        SCH_CRED_CACHE_ONLY_URL_RETRIEVAL_ON_CREATE |
        (roots->byte_length ? SCH_CRED_MANUAL_CRED_VALIDATION : SCH_CRED_AUTO_CRED_VALIDATION);
    if (c->identity.certificate) {
        credentials.cCreds = 1;
        credentials.paCred = &c->identity.certificate;
    }
    credentials.cTlsParameters = 1;
    credentials.pTlsParameters = &parameters;
    SECURITY_STATUS status =
        AcquireCredentialsHandleW(NULL, (LPWSTR)UNISP_NAME_W, SECPKG_CRED_OUTBOUND, NULL,
                                  &credentials, NULL, NULL, &c->credentials, NULL);
    if (status) {
        channel_dispose(c);
        return channel_result(channel_security_error(status), status, 0);
    }
    c->have_credentials = true;
    c->internal_handshake = true;
    channel_process(c);
    if (c->error) {
        unsigned error = c->error;
        status = c->native;
        channel_dispose(c);
        return channel_result(error, status, 0);
    }
    size_t index = 0;
    for (; index < slot_count; index++)
        if (!slots[index].channel)
            break;
    if (index == slot_count) {
        if (slot_count >= 65536) {
            channel_dispose(c);
            return channel_result(9, SEC_E_INSUFFICIENT_MEMORY, 0);
        }
        size_t next = slot_count ? slot_count * 2 : 64;
        ChannelSlot *fresh = realloc(slots, next * sizeof(*fresh));
        if (!fresh) {
            channel_dispose(c);
            return channel_result(7, SEC_E_INSUFFICIENT_MEMORY, 0);
        }
        slots = fresh;
        memset(slots + slot_count, 0, (next - slot_count) * sizeof(*slots));
        slot_count = next;
    }
    if (slots[index].generation == UINT32_MAX) {
        channel_dispose(c);
        return channel_result(9, SEC_E_INSUFFICIENT_MEMORY, 0);
    }
    slots[index].generation++;
    slots[index].channel = c;
    return channel_result(
        0, 0, (int64_t)((uint64_t)slots[index].generation << 32 | (uint32_t)(index + 1)));
}
MinyarBytes *minyar_schannel_stateRaw(long long id) {
    channel_thread();
    Channel *c = channel_get(id);
    return channel_status(c, c ? c->state : 0);
}
MinyarBytes *minyar_schannel_receiveRaw(long long id, const MinyarBytes *data) {
    channel_thread();
    Channel *c = channel_get(id);
    if (!c || c->error)
        return channel_status(c, 0);
    if (c->state == 2)
        return channel_result(4, SEC_I_CONTEXT_EXPIRED, 0);
    if (data->byte_length < 0 || data->byte_length > CHANNEL_LIMIT ||
        !channel_append(&c->input, data->bytes, (size_t)data->byte_length))
        channel_fail(c, 10, SEC_E_BUFFER_TOO_SMALL);
    else
        channel_process(c);
    return channel_status(c, data->byte_length);
}
MinyarBytes *minyar_schannel_writeRaw(long long id, const MinyarBytes *data) {
    channel_thread();
    Channel *c = channel_get(id);
    if (!c || c->error)
        return channel_status(c, 0);
    if (c->close_sent || c->state == 2)
        return channel_result(4, SEC_I_CONTEXT_EXPIRED, 0);
    if (c->state != 1)
        return channel_result(1, SEC_E_INCOMPLETE_MESSAGE, 0);
    if (data->byte_length < 0 || data->byte_length > CHANNEL_LIMIT)
        return channel_result(6, SEC_E_INVALID_TOKEN, 0);
    size_t at = 0, length = (size_t)data->byte_length;
    size_t chunks = (length + c->sizes.cbMaximumMessage - 1) / c->sizes.cbMaximumMessage;
    size_t overhead = (size_t)c->sizes.cbHeader + c->sizes.cbTrailer;
    if (chunks > CHANNEL_LIMIT / (overhead ? overhead : 1) ||
        length > CHANNEL_LIMIT - chunks * overhead ||
        c->outgoing.length > CHANNEL_LIMIT - length - chunks * overhead)
        return channel_result(1, SEC_E_BUFFER_TOO_SMALL, 0);
    while (at < length) {
        size_t n = length - at;
        if (n > c->sizes.cbMaximumMessage)
            n = c->sizes.cbMaximumMessage;
        size_t size = n + overhead;
        unsigned char *record = calloc(size, 1);
        if (!record) {
            channel_fail(c, 7, SEC_E_INSUFFICIENT_MEMORY);
            break;
        }
        memcpy(record + c->sizes.cbHeader, data->bytes + at, n);
        SecBuffer parts[4] = {
            {c->sizes.cbHeader, SECBUFFER_STREAM_HEADER, record},
            {(ULONG)n, SECBUFFER_DATA, record + c->sizes.cbHeader},
            {c->sizes.cbTrailer, SECBUFFER_STREAM_TRAILER, record + c->sizes.cbHeader + n},
            {0, SECBUFFER_EMPTY, NULL}};
        SecBufferDesc message = {SECBUFFER_VERSION, 4, parts};
        SECURITY_STATUS status = EncryptMessage(&c->context, 0, &message, 0);
        bool valid = !status;
        if (valid)
            for (unsigned i = 0; i < 3; i++)
                if (!channel_append(&c->outgoing, parts[i].pvBuffer, parts[i].cbBuffer))
                    valid = false;
        SecureZeroMemory(record, size);
        free(record);
        if (!valid) {
            channel_fail(c, channel_security_error(status),
                         status ? status : SEC_E_BUFFER_TOO_SMALL);
            break;
        }
        at += n;
    }
    return channel_status(c, (int64_t)at);
}
static MinyarBytes *channel_take(long long id, bool plaintext) {
    channel_thread();
    Channel *c = channel_get(id);
    ChannelBuffer *buffer = c ? (plaintext ? &c->incoming : &c->outgoing) : NULL;
    unsigned error = c ? c->error : 4;
    SECURITY_STATUS status = c ? c->native : SEC_E_INVALID_HANDLE;
    MinyarBytes *result = minyar_bytes_new(8 + (!error ? (long long)buffer->length : 0));
    memcpy((void *)result->bytes, &error, 4);
    memcpy((void *)(result->bytes + 4), &status, 4);
    if (!error && buffer->length)
        memcpy((void *)(result->bytes + 8), buffer->data, buffer->length);
    if (buffer)
        channel_clear(buffer, plaintext);
    return result;
}
MinyarBytes *minyar_schannel_takeOutgoingRaw(long long id) {
    return channel_take(id, false);
}
MinyarBytes *minyar_schannel_takeIncomingRaw(long long id) {
    return channel_take(id, true);
}
MinyarBytes *minyar_schannel_endInputRaw(long long id) {
    channel_thread();
    Channel *c = channel_get(id);
    if (!c || c->error)
        return channel_status(c, 0);
    if (c->state != 2 || c->input.length)
        channel_fail(c, 12, SEC_E_MESSAGE_ALTERED);
    return channel_status(c, 0);
}
MinyarBytes *minyar_schannel_shutdownRaw(long long id) {
    channel_thread();
    Channel *c = channel_get(id);
    if (!c || c->error)
        return channel_status(c, 0);
    if (c->close_sent)
        return channel_status(c, 0);
    if (c->state == 0)
        return channel_result(1, SEC_E_INCOMPLETE_MESSAGE, 0);
    DWORD token = SCHANNEL_SHUTDOWN;
    SecBuffer part = {sizeof(token), SECBUFFER_TOKEN, &token};
    SecBufferDesc input = {SECBUFFER_VERSION, 1, &part};
    SECURITY_STATUS status = ApplyControlToken(&c->context, &input);
    SecBuffer outgoing = {0, SECBUFFER_TOKEN, NULL};
    SecBufferDesc output = {SECBUFFER_VERSION, 1, &outgoing};
    if (!status)
        status = InitializeSecurityContextW(&c->credentials, &c->context, c->target,
                                            channel_flags(c), 0, SECURITY_NATIVE_DREP, NULL, 0,
                                            &c->context, &output, &c->attributes, NULL);
    bool valid = status == SEC_E_OK || status == SEC_I_CONTEXT_EXPIRED;
    if (valid)
        valid = channel_append(&c->outgoing, outgoing.pvBuffer, outgoing.cbBuffer);
    if (outgoing.pvBuffer)
        FreeContextBuffer(outgoing.pvBuffer);
    if (!valid)
        channel_fail(c, 10, status ? status : SEC_E_BUFFER_TOO_SMALL);
    else
        c->close_sent = true;
    return channel_status(c, 0);
}
MinyarBytes *minyar_schannel_closeRaw(long long id) {
    channel_thread();
    Channel *c = channel_get(id);
    if (!c)
        return channel_status(NULL, 0);
    slots[(uint32_t)id - 1].channel = NULL;
    channel_dispose(c);
    return channel_result(0, 0, 0);
}
