/* Native process/handle lifecycle contracts, independent of Minyar lowering. */
#include "../runtime/native/workers.c"
#include <aclapi.h>
#include <assert.h>
extern void minyar_rc_release(void *);

static uint32_t status(MinyarBytes *result) {
    assert(result->byte_length >= 8);
    return worker_get32(result->bytes);
}
static long long scalar(MinyarBytes *result) {
    assert(result->byte_length == 16 && status(result) == WORK_OK);
    long long value;
    memcpy(&value, result->bytes + 8, 8);
    minyar_rc_release(result);
    return value;
}
static void expect(MinyarBytes *result, uint32_t expected) {
    assert(status(result) == expected);
    minyar_rc_release(result);
}
static long long spawn(const wchar_t *mode) {
    wchar_t path[32768];
    DWORD length = GetModuleFileNameW(NULL, path, 32768);
    assert(length && length < 32768);
    return scalar(worker_spawn(path, mode));
}
static MinyarBytes *bytes(const void *value, size_t length) {
    MinyarBytes *result = minyar_bytes_new((long long)length);
    if (length)
        memcpy((void *)result->bytes, value, length);
    return result;
}
static void reply(const void *data, size_t length) {
    MinyarBytes *message = bytes(data, length);
    assert(scalar(minyar_workers_replyNative(message)) == (long long)length);
    minyar_rc_release(message);
}
static DWORD receive_pid(long long handle) {
    MinyarBytes *result = minyar_workers_receiveNative(handle, 5000);
    assert(status(result) == WORK_OK && result->byte_length == 12);
    DWORD pid = worker_get32(result->bytes + 8);
    minyar_rc_release(result);
    return pid;
}
static void pipe_has_private_dacl(HANDLE pipe) {
    PACL dacl = NULL;
    PSID owner = NULL;
    PSECURITY_DESCRIPTOR descriptor = NULL;
    assert(GetSecurityInfo(pipe, SE_KERNEL_OBJECT,
                           OWNER_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION, &owner, NULL,
                           &dacl, NULL, &descriptor) == ERROR_SUCCESS);
    assert(dacl && owner);
    DWORD length = SECURITY_MAX_SID_SIZE;
    unsigned char system[SECURITY_MAX_SID_SIZE];
    assert(CreateWellKnownSid(WinLocalSystemSid, NULL, system, &length));
    bool owner_allowed = false;
    for (DWORD index = 0; index < dacl->AceCount; index++) {
        void *raw = NULL;
        assert(GetAce(dacl, index, &raw));
        ACE_HEADER *header = raw;
        // No broad groups, anonymous reader, inherited grant, or null DACL.
        assert(header->AceType == ACCESS_ALLOWED_ACE_TYPE && !header->AceFlags);
        ACCESS_ALLOWED_ACE *ace = raw;
        PSID sid = &ace->SidStart;
        assert(EqualSid(sid, owner) || EqualSid(sid, system));
        owner_allowed |= EqualSid(sid, owner);
    }
    assert(owner_allowed);
    LocalFree(descriptor);
}

static int child(const wchar_t *mode) {
    if (!wcscmp(mode, L"idle")) {
        Sleep(INFINITE);
        return 0;
    }
    if (!wcsncmp(mode, L"handle:", 7)) {
        HANDLE suspect = (HANDLE)(uintptr_t)wcstoull(mode + 7, NULL, 10);
        // An unrelated inherited event would signal the parent's real handle.
        (void)SetEvent(suspect);
        reply("attempted", 9);
        return 0;
    }
    if (!wcscmp(mode, L"descendant")) {
        wchar_t path[32768], command[32768];
        DWORD length = GetModuleFileNameW(NULL, path, 32768);
        assert(length && length + 32 < 32768);
        swprintf(command, 32768, L"\"%ls\" --descendant", path);
        STARTUPINFOW startup = {0};
        startup.cb = sizeof(startup);
        PROCESS_INFORMATION process = {0};
        assert(CreateProcessW(path, command, NULL, NULL, FALSE, 0, NULL, NULL, &startup, &process));
        reply(&process.dwProcessId, sizeof(process.dwProcessId));
        CloseHandle(process.hThread);
        CloseHandle(process.hProcess);
        Sleep(INFINITE);
        return 0;
    }
    if (!wcscmp(mode, L"nested-exit")) {
        long long handle = spawn(L"idle");
        DWORD pid = GetProcessId(worker_lookup(handle)->process);
        reply(&pid, sizeof(pid));
        // Let the observer retain the descendant process before it exits.
        expect(minyar_workers_readMessageNative(), WORK_OK);
        // Bypass atexit: OS job-handle closure must still kill this child.
        ExitProcess(0);
    }
    if (!wcsncmp(mode, L"truncated:", 10)) {
        unsigned length = (unsigned)wcstoul(mode + 10, NULL, 10);
        unsigned char packet[] = {3, 0, 0, 0, 'a', 0, 255};
        assert(length < sizeof(packet));
        assert(!worker_write_exact(GetStdHandle(STD_OUTPUT_HANDLE), packet, length));
        return 0;
    }
    if (!wcscmp(mode, L"oversized")) {
        unsigned char header[4];
        worker_put32(header, WORK_MAX_MESSAGE + 1);
        assert(!worker_write_exact(GetStdHandle(STD_OUTPUT_HANDLE), header, 4));
        return 0;
    }
    assert(!wcscmp(mode, L"echo"));
    for (;;) {
        MinyarBytes *input = minyar_workers_readMessageNative();
        if (status(input) == WORK_EOF) {
            minyar_rc_release(input);
            return 0;
        }
        assert(status(input) == WORK_OK);
        reply(input->bytes + 8, (size_t)input->byte_length - 8);
        minyar_rc_release(input);
    }
}

int wmain(int argc, wchar_t **argv) {
    if (argc == 2 && !wcscmp(argv[1], L"--descendant")) {
        Sleep(INFINITE);
        return 0;
    }
    if (argc == 3 && !wcscmp(argv[1], L"--minyar-worker"))
        return child(argv[2]);
    assert(argc == 1);

    SECURITY_ATTRIBUTES inheritable = {sizeof(inheritable), NULL, TRUE};
    HANDLE unrelated = CreateEventW(&inheritable, TRUE, FALSE, NULL);
    assert(unrelated);
    wchar_t mode[80];
    swprintf(mode, 80, L"handle:%llu", (unsigned long long)(uintptr_t)unrelated);
    long long handle = spawn(mode);
    WorkerProcess *worker = worker_lookup(handle);
    pipe_has_private_dacl(worker->input);
    pipe_has_private_dacl(worker->output);
    MinyarBytes *result = minyar_workers_receiveNative(handle, 5000);
    assert(status(result) == WORK_OK && result->byte_length == 17 &&
           !memcmp(result->bytes + 8, "attempted", 9));
    minyar_rc_release(result);
    assert(WaitForSingleObject(unrelated, 0) == WAIT_TIMEOUT);
    assert(scalar(minyar_workers_closeNative(handle)) == 1);
    CloseHandle(unrelated);

    // Close must join pending reads and writes before releasing their storage.
    handle = spawn(L"idle");
    expect(minyar_workers_receiveNative(handle, 0), WORK_BLOCK);
    worker = worker_lookup(handle);
    assert(worker->read_pending);
    MinyarBytes *large = minyar_bytes_new(WORK_MAX_MESSAGE);
    memset((void *)large->bytes, 0xa5, WORK_MAX_MESSAGE);
    assert(scalar(minyar_workers_sendNative(handle, large)) == WORK_MAX_MESSAGE);
    assert(worker->write_pending);
    minyar_rc_release(large);
    assert(scalar(minyar_workers_closeNative(handle)) == 1);
    expect(minyar_workers_receiveNative(handle, 0), WORK_FAILURE);
    expect(minyar_workers_closeNative(handle), WORK_FAILURE);

    for (unsigned prefix = 0; prefix < 7; prefix++) {
        swprintf(mode, 80, L"truncated:%u", prefix);
        handle = spawn(mode);
        unsigned expected = prefix ? WORK_FAILURE : WORK_EOF;
        expect(minyar_workers_receiveNative(handle, 5000), expected);
        expect(minyar_workers_receiveNative(handle, 0), expected);
        assert(scalar(minyar_workers_closeNative(handle)) == 1);
    }
    handle = spawn(L"oversized");
    expect(minyar_workers_receiveNative(handle, 5000), WORK_FAILURE);
    assert(scalar(minyar_workers_closeNative(handle)) == 1);

    handle = spawn(L"echo");
    const unsigned sizes[] = {0, 1, 31, 4095, 4096, 65536, 131072};
    for (unsigned at = 0; at < sizeof(sizes) / sizeof(*sizes); at++) {
        unsigned length = sizes[at];
        MinyarBytes *message = minyar_bytes_new(length);
        for (unsigned index = 0; index < length; index++)
            ((unsigned char *)message->bytes)[index] = (unsigned char)(index * 131 + at);
        assert(scalar(minyar_workers_sendNative(handle, message)) == length);
        result = minyar_workers_receiveNative(handle, 5000);
        assert(status(result) == WORK_OK && result->byte_length == (long long)length + 8 &&
               !memcmp(result->bytes + 8, message->bytes, length));
        minyar_rc_release(result);
        minyar_rc_release(message);
    }
    assert(scalar(minyar_workers_closeNative(handle)) == 1);

    for (unsigned nested = 0; nested < 2; nested++) {
        handle = spawn(nested ? L"nested-exit" : L"descendant");
        DWORD pid = receive_pid(handle);
        HANDLE descendant = OpenProcess(SYNCHRONIZE, FALSE, pid);
        assert(descendant);
        if (nested) {
            MinyarBytes *ack = minyar_bytes_new(0);
            assert(scalar(minyar_workers_sendNative(handle, ack)) == 0);
            minyar_rc_release(ack);
            expect(minyar_workers_receiveNative(handle, 5000), WORK_EOF);
        } else
            assert(scalar(minyar_workers_closeNative(handle)) == 1);
        assert(WaitForSingleObject(descendant, 5000) == WAIT_OBJECT_0);
        CloseHandle(descendant);
        if (nested)
            assert(scalar(minyar_workers_closeNative(handle)) == 1);
    }

    DWORD before, after;
    assert(GetProcessHandleCount(GetCurrentProcess(), &before));
    for (unsigned at = 0; at < 8; at++) {
        handle = spawn(L"idle");
        expect(minyar_workers_receiveNative(handle, 0), WORK_BLOCK);
        assert(scalar(minyar_workers_closeNative(handle)) == 1);
    }
    assert(GetProcessHandleCount(GetCurrentProcess(), &after) && after == before);
    puts("Windows worker handle isolation and process lifecycle verified");
    return 0;
}
