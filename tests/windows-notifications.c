#define _WIN32_WINNT 0x0a00
#define NTDDI_VERSION 0x0a000000
#define COBJMACROS
#include "../runtime/minyar_native.h"
#include <windows.h>
#include <notificationactivationcallback.h>
#include <assert.h>
#include <stdint.h>
#ifndef NOTICE_LIMIT
#define NOTICE_LIMIT 1024
#endif
#ifndef ACTION_QUEUE_LIMIT
#define ACTION_QUEUE_LIMIT 256
#endif
extern HRESULT minyar_winnotify_testActivate(const wchar_t *, const wchar_t *, ULONG);
extern MinyarBytes *minyar_winnotify_testPrepare(const MinyarBytes *),
    *minyar_winnotify_tokenRaw(long long);
extern const CLSID *minyar_winnotify_testClsid(void);
extern void minyar_winnotify_testCreated(long long, ULONGLONG),
    minyar_winnotify_testForeignOwner(bool);
extern MinyarBytes *minyar_winnotify_stopRaw(void);
extern MinyarBytes *minyar_winnotify_cancelTokenRaw(const MinyarText *);
extern bool minyar_windows_nextEvent(double);
typedef struct Invocation {
    CLSID clsid;
    wchar_t app[64], argument[100];
    HRESULT result;
} Invocation;
static DWORD WINAPI invoke_com(void *raw) {
    Invocation *call = raw;
    assert(SUCCEEDED(CoInitializeEx(NULL, COINIT_MULTITHREADED)));
    INotificationActivationCallback *callback = NULL;
    call->result = CoCreateInstance(&call->clsid, NULL, CLSCTX_LOCAL_SERVER,
                                    &IID_INotificationActivationCallback, (void **)&callback);
    if (SUCCEEDED(call->result)) {
        call->result =
            INotificationActivationCallback_Activate(callback, call->app, call->argument, NULL, 0);
        INotificationActivationCallback_Release(callback);
    }
    CoUninitialize();
    return 0;
}
extern MinyarBytes *minyar_winnotify_initializeRaw(const MinyarText *);
extern MinyarBytes *minyar_winnotify_registerRaw(const MinyarText *, const MinyarText *);
extern MinyarBytes *minyar_winnotify_unregisterRaw(void), *minyar_winnotify_nextActionRaw(void);
extern MinyarBytes *minyar_winnotify_showRaw(const MinyarText *, const MinyarText *,
                                             const MinyarBytes *);
extern MinyarBytes *minyar_winnotify_statusRaw(long long), *minyar_winnotify_closeRaw(long long);
extern void minyar_rc_release(void *);
static uint32_t error(MinyarBytes *b) {
    uint32_t v;
    memcpy(&v, b->bytes, 4);
    return v;
}
static int64_t integer(MinyarBytes *b) {
    int64_t v;
    assert(b->byte_length == 16 && !error(b));
    memcpy(&v, b->bytes + 8, 8);
    minyar_rc_release(b);
    return v;
}
static void failure(MinyarBytes *b, uint32_t expected) {
    assert(error(b) == expected);
    minyar_rc_release(b);
}
int main(void) {
    MinyarText *bad = minyar_native_copy_text((const unsigned char *)"foreign/app", 11);
    failure(minyar_winnotify_initializeRaw(bad), 6);
    failure(minyar_winnotify_cancelTokenRaw(bad), 6);
    minyar_rc_release(bad);
    failure(minyar_winnotify_nextActionRaw(), 9);
    MinyarText *title = minyar_native_copy_text((const unsigned char *)"<title> & \"日本語\"", 21);
    MinyarText *body = minyar_native_copy_text((const unsigned char *)"body", 4);
    MinyarBytes *actions = minyar_bytes_new(0);
    failure(minyar_winnotify_showRaw(title, body, actions), 9);
    wchar_t app[64];
    swprintf(app, 64, L"Minyar.NativeTest.%lu", GetCurrentProcessId());
    char ascii[64];
    WideCharToMultiByte(CP_UTF8, 0, app, -1, ascii, 64, NULL, NULL);
    MinyarText *id =
        minyar_native_copy_text((const unsigned char *)ascii, (long long)strlen(ascii));
    // Init alone cannot claim a foreign/unregistered app identity.
    failure(minyar_winnotify_initializeRaw(id), 9);
    assert(integer(minyar_winnotify_registerRaw(id, body)) == 1);
    assert(integer(minyar_winnotify_initializeRaw(id)) == 1);
    failure(minyar_winnotify_nextActionRaw(), 1);
    unsigned char malformed[] = {1, 1, 0, 'a', 0, 0};
    MinyarBytes *badActions = minyar_bytes_new(sizeof(malformed));
    memcpy((void *)badActions->bytes, malformed, sizeof(malformed));
    failure(minyar_winnotify_showRaw(title, body, badActions), 6);
    minyar_rc_release(badActions);
    failure(minyar_winnotify_statusRaw(0), 4);
    failure(minyar_winnotify_closeRaw(0), 4);
    // This independent token/action fixture uses the real WinRT XML parser and
    // persisted allowlist, even when CI's desktop policy disables visible banners.
    unsigned char packed[] = {1,   4,   0,   'o', 'p', 'e', 'n', 8,  0,
                              'O', 'p', 'e', 'n', ' ', '<', '&', '>'};
    MinyarBytes *valid = minyar_bytes_new(sizeof(packed));
    memcpy((void *)valid->bytes, packed, sizeof(packed));
    long long notice = integer(minyar_winnotify_testPrepare(valid));
    MinyarBytes *token = minyar_winnotify_tokenRaw(notice);
    assert(!error(token) && token->byte_length == 48);
    wchar_t argument[100];
    for (unsigned i = 0; i < 32; i++)
        argument[i] = token->bytes[16 + i];
    argument[32] = 0;
    wcscat(argument, L":foreign");
    assert(FAILED(minyar_winnotify_testActivate(app, argument, 0)));
    argument[32] = 0;
    wcscat(argument, L":open");
    assert(FAILED(minyar_winnotify_testActivate(L"Foreign.App", argument, 0)));
    assert(FAILED(minyar_winnotify_testActivate(app, argument, 1)));
    Invocation invocation = {0};
    invocation.clsid = *minyar_winnotify_testClsid();
    wcscpy(invocation.app, app);
    wcscpy(invocation.argument, argument);
    HANDLE worker = CreateThread(NULL, 0, invoke_com, &invocation, 0, NULL);
    assert(worker);
    assert(WaitForSingleObject(worker, 5000) == WAIT_OBJECT_0);
    CloseHandle(worker);
    assert(SUCCEEDED(invocation.result));
    assert(!minyar_windows_nextEvent(0)); // COM callback wakes the shared native GUI pump.
    assert(FAILED(minyar_winnotify_testActivate(app, argument, 0)));
    MinyarBytes *event = minyar_winnotify_nextActionRaw();
    assert(!error(event) && event->byte_length == 53);
    assert(!memcmp(event->bytes + 16, token->bytes + 16, 32));
    assert(!memcmp(event->bytes + 48, ":open", 5));
    minyar_rc_release(event);
    failure(minyar_winnotify_nextActionRaw(), 1);
    assert(integer(minyar_winnotify_closeRaw(notice)) == 0);
    assert(FAILED(minyar_winnotify_testActivate(app, argument, 0)));
    failure(minyar_winnotify_statusRaw(notice), 4);
    failure(minyar_winnotify_closeRaw(notice), 4);
    minyar_rc_release(token);
    // A persistent token can be cancelled after native ids have disappeared.
    notice = integer(minyar_winnotify_testPrepare(valid));
    token = minyar_winnotify_tokenRaw(notice);
    MinyarText *persisted = minyar_native_copy_text(token->bytes + 16, 32);
    for (unsigned i = 0; i < 32; i++)
        argument[i] = token->bytes[16 + i];
    argument[32] = 0;
    wcscat(argument, L":open");
    assert(integer(minyar_winnotify_stopRaw()) == 0);
    assert(integer(minyar_winnotify_initializeRaw(id)) == 1);
    assert(integer(minyar_winnotify_cancelTokenRaw(persisted)) == 0);
    assert(integer(minyar_winnotify_cancelTokenRaw(persisted)) == 0);
    assert(FAILED(minyar_winnotify_testActivate(app, argument, 0)));
    minyar_rc_release(persisted);
    minyar_rc_release(token);
    notice = integer(minyar_winnotify_testPrepare(valid));
    token = minyar_winnotify_tokenRaw(notice);
    for (unsigned i = 0; i < 32; i++)
        argument[i] = token->bytes[16 + i];
    argument[32] = 0;
    wcscat(argument, L":open");
    minyar_winnotify_testCreated(notice, 0);
    assert(FAILED(minyar_winnotify_testActivate(app, argument, 0)));
    minyar_winnotify_testCreated(notice, UINT64_MAX);
    assert(FAILED(minyar_winnotify_testActivate(app, argument, 0)));
    assert(integer(minyar_winnotify_closeRaw(notice)) == 0);
    minyar_rc_release(token);
    // Native state disappears on stop; persisted allowlist survives reinitialization.
    notice = integer(minyar_winnotify_testPrepare(valid));
    token = minyar_winnotify_tokenRaw(notice);
    for (unsigned i = 0; i < 32; i++)
        argument[i] = token->bytes[16 + i];
    argument[32] = 0;
    wcscat(argument, L":open");
    assert(integer(minyar_winnotify_stopRaw()) == 0);
    failure(minyar_winnotify_statusRaw(notice), 4);
    minyar_winnotify_testForeignOwner(true);
    failure(minyar_winnotify_registerRaw(id, body), 8);
    failure(minyar_winnotify_initializeRaw(id), 8);
    minyar_winnotify_testForeignOwner(false);
    assert(integer(minyar_winnotify_initializeRaw(id)) == 1);
    assert(SUCCEEDED(minyar_winnotify_testActivate(app, argument, 0)));
    event = minyar_winnotify_nextActionRaw();
    assert(!error(event) && event->byte_length == 53);
    minyar_rc_release(event);
    minyar_rc_release(token);
    notice = integer(minyar_winnotify_testPrepare(valid));
    token = minyar_winnotify_tokenRaw(notice);
    for (unsigned i = 0; i < 32; i++)
        argument[i] = token->bytes[16 + i];
    argument[32] = 0;
    wcscat(argument, L":open");
    assert(SUCCEEDED(minyar_winnotify_testActivate(app, argument, 0)));
    assert(integer(minyar_winnotify_closeRaw(notice)) == 0); // queued callbacks discarded on close
    failure(minyar_winnotify_nextActionRaw(), 1);
    minyar_rc_release(token);
    // Duplicate definitions, empty action labels, trailing bytes and over-five actions reject.
    unsigned char duplicate[] = {2, 1, 0, 'x', 1, 0, 'X', 1, 0, 'x', 1, 0, 'Y'};
    MinyarBytes *dup = minyar_bytes_new(sizeof(duplicate));
    memcpy((void *)dup->bytes, duplicate, sizeof(duplicate));
    failure(minyar_winnotify_testPrepare(dup), 6);
    minyar_rc_release(dup);
    unsigned char trailing[] = {0, 0}, invalidUtf8[] = {1, 1, 0, 'a', 1, 0, 0xff};
    dup = minyar_bytes_new(sizeof(trailing));
    memcpy((void *)dup->bytes, trailing, sizeof(trailing));
    failure(minyar_winnotify_testPrepare(dup), 6);
    minyar_rc_release(dup);
    dup = minyar_bytes_new(sizeof(invalidUtf8));
    memcpy((void *)dup->bytes, invalidUtf8, sizeof(invalidUtf8));
    failure(minyar_winnotify_testPrepare(dup), 6);
    minyar_rc_release(dup);
    // Queue backpressure leaves the persisted allowlist intact for a later retry.
    long long queued[ACTION_QUEUE_LIMIT + 1];
    for (unsigned i = 0; i <= ACTION_QUEUE_LIMIT; i++) {
        queued[i] = integer(minyar_winnotify_testPrepare(valid));
        token = minyar_winnotify_tokenRaw(queued[i]);
        for (unsigned j = 0; j < 32; j++)
            argument[j] = token->bytes[16 + j];
        minyar_rc_release(token);
        argument[32] = 0;
        wcscat(argument, L":open");
        HRESULT accepted = minyar_winnotify_testActivate(app, argument, 0);
        assert(i < ACTION_QUEUE_LIMIT ? SUCCEEDED(accepted) : accepted == E_OUTOFMEMORY);
    }
    for (unsigned i = 0; i < ACTION_QUEUE_LIMIT; i++) {
        event = minyar_winnotify_nextActionRaw();
        assert(!error(event));
        minyar_rc_release(event);
    }
    assert(SUCCEEDED(minyar_winnotify_testActivate(app, argument, 0)));
    for (unsigned i = 0; i <= ACTION_QUEUE_LIMIT; i++)
        assert(integer(minyar_winnotify_closeRaw(queued[i])) == 0);
    failure(minyar_winnotify_nextActionRaw(), 1);
    unsigned char tooMany[] = {6};
    dup = minyar_bytes_new(1);
    memcpy((void *)dup->bytes, tooMany, 1);
    failure(minyar_winnotify_testPrepare(dup), 6);
    minyar_rc_release(dup);
    // A restart cannot reset the persistent limit. Expired registrations are
    // pruned before counting, and cancellation releases capacity.
    assert(integer(minyar_winnotify_stopRaw()) == 0);
    assert(integer(minyar_winnotify_initializeRaw(id)) == 1);
    MinyarText *saved[NOTICE_LIMIT];
    for (unsigned i = 0; i < NOTICE_LIMIT; i++) {
        notice = integer(minyar_winnotify_testPrepare(valid));
        token = minyar_winnotify_tokenRaw(notice);
        saved[i] = minyar_native_copy_text(token->bytes + 16, 32);
        minyar_rc_release(token);
    }
    minyar_winnotify_testCreated(notice, 0);
    assert(integer(minyar_winnotify_stopRaw()) == 0);
    assert(integer(minyar_winnotify_initializeRaw(id)) == 1);
    notice = integer(minyar_winnotify_testPrepare(valid));
    failure(minyar_winnotify_testPrepare(valid), 7);
    assert(integer(minyar_winnotify_closeRaw(notice)) == 0);
    for (unsigned i = 0; i < NOTICE_LIMIT; i++) {
        assert(integer(minyar_winnotify_cancelTokenRaw(saved[i])) == 0);
        minyar_rc_release(saved[i]);
    }
    // Visible delivery goes through actual OS policy; disabled settings return denied.
    MinyarBytes *shown = minyar_winnotify_showRaw(title, body, valid);
    if (!error(shown)) {
        long long real = integer(shown);
        assert(real > 0);
        assert(integer(minyar_winnotify_statusRaw(real)) == 1);
        assert(integer(minyar_winnotify_closeRaw(real)) == 0);
    } else {
        assert(error(shown) == 8);
        minyar_rc_release(shown);
    }
    minyar_rc_release(valid);
    assert(integer(minyar_winnotify_unregisterRaw()) == 0);
    failure(minyar_winnotify_nextActionRaw(), 9);
    minyar_rc_release(id);
    minyar_rc_release(title);
    minyar_rc_release(body);
    minyar_rc_release(actions);
    puts("Windows persistent notification registration and action contracts verified");
    return 0;
}
