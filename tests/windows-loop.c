/* Real GUI + reactor dispatch without a background WSAPoll loop. More than
 * MAXIMUM_WAIT_OBJECTS sockets share one wake hint; callbacks hold native data. */
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <windows.h>
static unsigned socket_polls;
static int counted_poll(LPWSAPOLLFD sockets, ULONG count, INT timeout) {
    socket_polls++;
    return WSAPoll(sockets, count, timeout);
}
#define WSAPoll counted_poll
#include "../runtime/native/net.c"
#include <assert.h>
extern void minyar_rc_release(void *);
extern void minyar_windows_initialize(const MinyarText *);
extern long long minyar_windows_window(const MinyarText *, long long, long long);
extern long long minyar_windows_textField(long long, const MinyarText *);
extern bool minyar_windows_nextEvent(double);
extern long long minyar_windows_eventType(void);
extern long long minyar_windows_eventSource(void);
extern HWND minyar_windows_testHandle(long long);
extern void minyar_windows_destroy(long long);
extern MinyarBytes *minyar_windows_shareNetworkLoopRaw(long long);
extern MinyarBytes *minyar_windows_unshareNetworkLoopRaw(void);

static MinyarText *text(const char *s) {
    return minyar_native_copy_text((const unsigned char *)s, strlen(s));
}
static uint32_t word(const MinyarBytes *b, size_t p) {
    assert(p + 4 <= (size_t)b->byte_length);
    return b->bytes[p] | (uint32_t)b->bytes[p + 1] << 8 | (uint32_t)b->bytes[p + 2] << 16 |
           (uint32_t)b->bytes[p + 3] << 24;
}
static long long wide(const MinyarBytes *b, size_t p) {
    return (long long)((uint64_t)word(b, p) | ((uint64_t)word(b, p + 4) << 32));
}
static long long result(MinyarBytes *b) {
    assert(b->byte_length == 16 && !word(b, 0));
    long long n = wide(b, 8);
    minyar_rc_release(b);
    return n;
}
static void drain_gui(void) {
    do {
        assert(minyar_windows_nextEvent(0));
    } while (minyar_windows_eventType());
}
static void drain_shared(long long loop) {
    for (unsigned tries = 0; tries < 32; tries++) {
        assert(minyar_windows_nextEvent(0));
        long long kind = minyar_windows_eventType();
        MinyarBytes *batch = minyar_net_loopWait(loop, 0, 256);
        assert(!word(batch, 0) && batch->byte_length == 8);
        minyar_rc_release(batch);
        if (!kind)
            return;
    }
    assert(false);
}
static SOCKET sender;
static struct sockaddr_in destination;
static HWND field;
static DWORD WINAPI arrival(void *ignored) {
    (void)ignored;
    Sleep(40);
    SendMessageW(field, WM_SETTEXT, 0, (LPARAM)L"native message during socket wait");
    Sleep(40);
    assert(sendto(sender, "packet", 6, 0, (struct sockaddr *)&destination, sizeof(destination)) ==
           6);
    return 0;
}
int main(void) {
    MinyarText *name = text("Windows shared reactor"), *host = text("127.0.0.1"),
               *title = text("field");
    minyar_windows_initialize(name);
    long long window = minyar_windows_window(name, 240, 80),
              field_id = minyar_windows_textField(window, title);
    field = minyar_windows_testHandle(field_id);
    drain_gui();
    MinyarBytes *invalid = minyar_windows_shareNetworkLoopRaw(0);
    assert(word(invalid, 0) == 6);
    minyar_rc_release(invalid);
    long long loop = result(minyar_net_loopCreate());
    enum { COUNT = 128 };
    long long sockets[COUNT], registrations[COUNT];
    for (unsigned i = 0; i < COUNT; i++) {
        sockets[i] = minyar_net_udp(host, 0);
        assert(sockets[i] >= 0);
        registrations[i] = result(minyar_net_loopWatch(loop, sockets[i], 1, (long long)i + 1000));
    }
    assert(result(minyar_windows_shareNetworkLoopRaw(loop)) == loop);
    MinyarBytes *batch = minyar_net_loopWait(loop, 0, 256);
    assert(!word(batch, 0) && batch->byte_length == 8);
    minyar_rc_release(batch);
    drain_shared(loop);
    sender = socket(AF_INET, SOCK_DGRAM, 0);
    assert(sender != INVALID_SOCKET);
    memset(&destination, 0, sizeof(destination));
    destination.sin_family = AF_INET;
    destination.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    destination.sin_port = htons((u_short)minyar_net_localPort(sockets[COUNT - 1]));
    HANDLE worker = CreateThread(NULL, 0, arrival, NULL, 0, NULL);
    assert(worker);
    unsigned before = socket_polls;
    assert(minyar_windows_nextEvent(1));
    assert(minyar_windows_eventType() == 2 && minyar_windows_eventSource() == field_id);
    assert(socket_polls == before); /* GUI dispatch must not run periodic WSAPoll. */
    assert(minyar_windows_nextEvent(1));
    assert(minyar_windows_eventType() == 0 && socket_polls == before);
    batch = minyar_net_loopWait(loop, 0, 256);
    assert(!word(batch, 0) && batch->byte_length == 40 &&
           wide(batch, 8) == registrations[COUNT - 1] && wide(batch, 16) == COUNT - 1 + 1000);
    minyar_rc_release(batch);
    MinyarBytes *packet = minyar_net_readResult(sockets[COUNT - 1], 32, true);
    assert(word(packet, 0) == NET_OK && packet->byte_length == 14 &&
           !memcmp(packet->bytes + 8, "packet", 6));
    minyar_rc_release(packet);
    assert(WaitForSingleObject(worker, 5000) == WAIT_OBJECT_0);
    CloseHandle(worker);
    closesocket(sender);
    /* Poll/read re-enables notifications; a later datagram cannot disappear. */
    sender = socket(AF_INET, SOCK_DGRAM, 0);
    assert(sender != INVALID_SOCKET);
    assert(sendto(sender, "again", 5, 0, (struct sockaddr *)&destination, sizeof(destination)) ==
           5);
    assert(minyar_windows_nextEvent(1) && !minyar_windows_eventType());
    batch = minyar_net_loopWait(loop, 0, 256);
    assert(!word(batch, 0) && batch->byte_length == 40);
    minyar_rc_release(batch);
    packet = minyar_net_readResult(sockets[COUNT - 1], 32, true);
    assert(word(packet, 0) == NET_OK && packet->byte_length == 13);
    minyar_rc_release(packet);
    /* One-event batches must not consume the wake for other ready sockets. */
    for (unsigned i = COUNT - 3; i < COUNT; i++) {
        destination.sin_port = htons((u_short)minyar_net_localPort(sockets[i]));
        assert(sendto(sender, "batch", 5, 0, (struct sockaddr *)&destination,
                      sizeof(destination)) == 5);
    }
    bool seen[3] = {false, false, false};
    for (unsigned n = 0; n < 3; n++) {
        assert(minyar_windows_nextEvent(1));
        batch = minyar_net_loopWait(loop, 0, 1);
        assert(!word(batch, 0) && batch->byte_length == 40);
        long long index = wide(batch, 16) - 1000;
        assert(index >= COUNT - 3 && index < COUNT && !seen[index - (COUNT - 3)]);
        seen[index - (COUNT - 3)] = true;
        minyar_rc_release(batch);
        packet = minyar_net_readResult(sockets[index], 32, true);
        assert(word(packet, 0) == NET_OK && packet->byte_length == 13);
        minyar_rc_release(packet);
    }
    bool slept = false;
    for (unsigned attempt = 0; attempt < 16; attempt++) {
        ULONGLONG started = GetTickCount64();
        assert(minyar_windows_nextEvent(0.04) && !minyar_windows_eventType());
        ULONGLONG elapsed = GetTickCount64() - started;
        batch = minyar_net_loopWait(loop, 0, 256);
        assert(!word(batch, 0) && batch->byte_length == 8);
        minyar_rc_release(batch);
        if (elapsed >= 25) {
            slept = true;
            break;
        }
    }
    assert(slept); /* A consumed FD_READ record must not keep idle UI awake. */
    closesocket(sender);
    for (unsigned i = 0; i < COUNT; i++) {
        assert(result(minyar_net_loopRemove(loop, registrations[i])) == 1);
        minyar_net_close(sockets[i]);
    }
    long long listener = minyar_net_listen(host, 0, 8);
    assert(listener >= 0);
    long long listening = result(minyar_net_loopWatch(loop, listener, 1, 4321));
    long long peer = minyar_net_connect(host, minyar_net_localPort(listener));
    assert(peer >= 0);
    assert(minyar_windows_nextEvent(1));
    batch = minyar_net_loopWait(loop, 0, 8);
    assert(!word(batch, 0) && batch->byte_length == 40 && wide(batch, 16) == 4321);
    minyar_rc_release(batch);
    long long accepted = minyar_net_accept(listener);
    assert(accepted >= 0);
    assert(result(minyar_net_loopRemove(loop, listening)) == 1);
    minyar_net_close(listener);
    MinyarBytes *payload = minyar_native_copy_text((const unsigned char *)"child", 5);
    assert(minyar_net_send(peer, payload) == 5);
    minyar_rc_release(payload);
    assert(minyar_net_ready(accepted, 1000));
    WSANETWORKEVENTS inherited = {0};
    assert(!WSAEnumNetworkEvents((SOCKET)accepted, NULL, &inherited));
    assert(!inherited.lNetworkEvents); /* Child no longer owns the listener event. */
    long long child = result(minyar_net_loopWatch(loop, accepted, 1, 6789));
    assert(minyar_windows_nextEvent(1));
    batch = minyar_net_loopWait(loop, 0, 8);
    assert(!word(batch, 0) && batch->byte_length == 40 && wide(batch, 16) == 6789);
    minyar_rc_release(batch);
    packet = minyar_net_readResult(accepted, 32, false);
    assert(word(packet, 0) == NET_OK && packet->byte_length == 13);
    minyar_rc_release(packet);
    assert(result(minyar_net_loopRemove(loop, child)) == 1);
    minyar_net_close(accepted);
    minyar_net_close(peer);
    drain_shared(loop);
    long long timer = result(minyar_net_loopTimer(loop, 25, 0, 9876));
    ULONGLONG started = GetTickCount64();
    do {
        assert(minyar_windows_nextEvent(3) && !minyar_windows_eventType());
        batch = minyar_net_loopWait(loop, 0, 256);
        assert(!word(batch, 0));
        if (batch->byte_length == 8) {
            minyar_rc_release(batch);
            batch = NULL;
        }
        assert(GetTickCount64() - started < 2500);
    } while (!batch);
    assert(batch->byte_length == 40 && wide(batch, 8) == timer && wide(batch, 16) == 9876 &&
           word(batch, 32) == 1);
    minyar_rc_release(batch);
    before = socket_polls;
    assert(minyar_windows_nextEvent(0.025) && !minyar_windows_eventType() &&
           socket_polls == before);
    assert(result(minyar_windows_unshareNetworkLoopRaw()) == 1);
    assert(result(minyar_windows_unshareNetworkLoopRaw()) == 0);
    assert(result(minyar_windows_shareNetworkLoopRaw(loop)) == loop);
    assert(result(minyar_net_loopClose(loop)) ==
           1); /* Must detach before freeing its wake handle. */
    long long replacement = result(minyar_net_loopCreate());
    assert(replacement != loop);
    invalid = minyar_windows_shareNetworkLoopRaw(loop);
    assert(word(invalid, 0) == 6);
    minyar_rc_release(invalid);
    assert(result(minyar_windows_unshareNetworkLoopRaw()) == 0);
    assert(result(minyar_net_loopClose(replacement)) == 1);
    minyar_windows_destroy(window);
    minyar_rc_release(name);
    minyar_rc_release(host);
    minyar_rc_release(title);
    puts("Windows GUI, sockets, timers, wake rearming and detachment verified");
    return 0;
}
