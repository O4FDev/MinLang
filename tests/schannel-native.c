/* Actual SChannel contracts, before any network interop. Never changes trust
 * stores, selects an implicit device certificate, or runs TLS on its own socket. */
#include "../runtime/native/schannel.c"
#include <assert.h>
void minyar_rc_release(void *);

static uint32_t code(const MinyarBytes *bytes) {
    assert(bytes->byte_length >= 8);
    uint32_t value;
    memcpy(&value, bytes->bytes, 4);
    return value;
}
static int64_t scalar(MinyarBytes *bytes) {
    if (code(bytes)) {
        SECURITY_STATUS native;
        memcpy(&native, bytes->bytes + 4, 4);
        fprintf(stderr, "unexpected SChannel error %u native 0x%08lx\n", code(bytes),
                (unsigned long)native);
    }
    assert(bytes->byte_length == 16 && code(bytes) == 0);
    int64_t value;
    memcpy(&value, bytes->bytes + 8, 8);
    minyar_rc_release(bytes);
    return value;
}
static void error(MinyarBytes *bytes, uint32_t expected) {
    assert(code(bytes) == expected);
    minyar_rc_release(bytes);
}
static MinyarBytes empty = {NULL, 0, 0, NULL, NULL};
static MinyarText host = {(const unsigned char *)"localhost", 9, 9, NULL, NULL};
static long long foreign_session;
static DWORD WINAPI wrong_thread(void *ignored) {
    (void)ignored;
    minyar_schannel_stateRaw(foreign_session);
    return 0;
}

int main(int argc, char **argv) {
    long long first = scalar(minyar_schannel_clientRaw(&host, &empty, &empty));
    if (argc == 2 && !strcmp(argv[1], "thread")) {
        foreign_session = first;
        HANDLE thread = CreateThread(NULL, 0, wrong_thread, NULL, 0, NULL);
        assert(thread && WaitForSingleObject(thread, 5000) == WAIT_OBJECT_0);
        CloseHandle(thread);
        return 0;
    }
    assert(first && scalar(minyar_schannel_stateRaw(first)) == 0);
    MinyarBytes *outgoing = minyar_schannel_takeOutgoingRaw(first);
    assert(code(outgoing) == 0 && outgoing->byte_length > 13 && outgoing->bytes[8] == 22);
    minyar_rc_release(outgoing);
    outgoing = minyar_schannel_takeOutgoingRaw(first);
    assert(code(outgoing) == 0 && outgoing->byte_length == 8);
    minyar_rc_release(outgoing);
    error(minyar_schannel_writeRaw(first, &empty), 1);
    error(minyar_schannel_endInputRaw(first), 12);
    error(minyar_schannel_takeIncomingRaw(first), 12);
    assert(scalar(minyar_schannel_closeRaw(first)) == 0);
    error(minyar_schannel_stateRaw(first), 4);
    error(minyar_schannel_closeRaw(first), 4);
    long long reused = scalar(minyar_schannel_clientRaw(&host, &empty, &empty));
    assert(reused != first);
    error(minyar_schannel_receiveRaw(first, &empty), 4);
    MinyarBytes *huge = minyar_bytes_new(1024 * 1024 + 1);
    error(minyar_schannel_receiveRaw(reused, huge), 10);
    minyar_rc_release(huge);
    error(minyar_schannel_takeIncomingRaw(reused), 10);
    assert(scalar(minyar_schannel_closeRaw(reused)) == 0);
    unsigned char wrong[] = {22, 3, 3, 0, 4, 255, 255, 255, 255};
    long long malformed = scalar(minyar_schannel_clientRaw(&host, &empty, &empty));
    for (size_t i = 0; i < sizeof(wrong); i++) {
        MinyarBytes fragment = {wrong + i, 1, 1, NULL, NULL};
        MinyarBytes *received = minyar_schannel_receiveRaw(malformed, &fragment);
        assert(code(received) == 0 || code(received) == 10);
        minyar_rc_release(received);
    }
    error(minyar_schannel_takeIncomingRaw(malformed), 10);
    assert(scalar(minyar_schannel_closeRaw(malformed)) == 0);
    const unsigned char nul[] = {'a', 0, 'b'};
    MinyarText invalid = {nul, 3, 3, NULL, NULL};
    error(minyar_schannel_clientRaw(&invalid, &empty, &empty), 6);
    MinyarBytes invalid_key = {(const unsigned char *)"MWI1", 4, 4, NULL, NULL};
    error(minyar_schannel_clientRaw(&host, &empty, &invalid_key), 11);
    puts(
        "Windows SChannel bounded fragments, early data, truncation and handle contracts verified");
    return 0;
}
