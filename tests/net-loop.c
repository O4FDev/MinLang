/* Original peer-inspired readiness/timer contracts. See docs/network-event-loop.md.
 * Include the backend so exact bounded-storage assertions supplement behavior. */
#include "../runtime/native/net.c"
#include "../runtime/native/net_loop.h"
#include <assert.h>
#include <stdint.h>
#include <time.h>
#ifndef _WIN32
#include <signal.h>
#include <sys/resource.h>
#include <sys/time.h>
#endif

void minyar_rc_release(void *);

static uint32_t loop_word(const MinyarBytes *b, size_t at) {
    assert(at + 4 <= (size_t)b->byte_length);
    return (uint32_t)b->bytes[at] | (uint32_t)b->bytes[at + 1] << 8 |
           (uint32_t)b->bytes[at + 2] << 16 | (uint32_t)b->bytes[at + 3] << 24;
}
static uint64_t loop_wide(const MinyarBytes *b, size_t at) {
    return (uint64_t)loop_word(b, at) | (uint64_t)loop_word(b, at + 4) << 32;
}
static long long result_handle(MinyarBytes *b) {
    assert(b->byte_length == 16 && loop_word(b, 0) == NET_OK && !loop_word(b, 4));
    long long value = (long long)loop_wide(b, 8);
    minyar_rc_release(b);
    return value;
}
static void operation_ok(MinyarBytes *b) {
    assert(result_handle(b) == 1);
}
static void operation_failed(MinyarBytes *b) {
    assert(loop_word(b, 0) == NET_FAILURE && loop_word(b, 4));
    minyar_rc_release(b);
}
static size_t event_count(const MinyarBytes *b) {
    assert(b->byte_length >= 8 && (b->byte_length - 8) % 32 == 0);
    assert(loop_word(b, 0) == NET_OK && !loop_word(b, 4));
    return (size_t)(b->byte_length - 8) / 32;
}
static MinyarText loop_literal(const char *s) {
    MinyarText value = {(const unsigned char *)s, (long long)strlen(s), 0, NULL, NULL};
    return value;
}

static void timers_and_stale_handles(void) {
    long long loop = result_handle(minyar_net_loopCreate());
    long long late = result_handle(minyar_net_loopTimer(loop, 30, 0, 30));
    long long early = result_handle(minyar_net_loopTimer(loop, 2, 0, 2));
    long long cancelled = result_handle(minyar_net_loopTimer(loop, 1, 0, 99));
    operation_ok(minyar_net_loopRemove(loop, cancelled));
    operation_failed(minyar_net_loopRemove(loop, cancelled));
    MinyarBytes *b = minyar_net_loopWait(loop, 500, 1);
    assert(event_count(b) == 1 && loop_wide(b, 8) == (uint64_t)early);
    assert(loop_wide(b, 16) == 2 && loop_word(b, 24) == 16 && loop_word(b, 32) == 1);
    minyar_rc_release(b);
    b = minyar_net_loopWait(loop, 500, 1);
    assert(event_count(b) == 1 && loop_wide(b, 8) == (uint64_t)late && loop_wide(b, 16) == 30);
    minyar_rc_release(b);
    operation_failed(minyar_net_loopRemove(loop, early));
    long long repeating = result_handle(minyar_net_loopTimer(loop, 0, 5, -5));
    for (unsigned i = 0; i < 3; i++) {
        b = minyar_net_loopWait(loop, 500, 2);
        assert(event_count(b) == 1 && loop_wide(b, 8) == (uint64_t)repeating);
        assert((long long)loop_wide(b, 16) == -5);
        minyar_rc_release(b);
    }
    operation_ok(minyar_net_loopRemove(loop, repeating));
    b = minyar_net_loopWait(loop, 0, 2);
    assert(event_count(b) == 0);
    minyar_rc_release(b);
    /* Repeated long-delay cancellation must not retain tombstones/slot growth. */
    for (unsigned i = 0; i < 20000; i++) {
        long long timer = result_handle(minyar_net_loopTimer(loop, 1000000, 0, i));
        operation_ok(minyar_net_loopRemove(loop, timer));
    }
    NetLoop *state = net_loop_find(loop);
    assert(state && state->entry_count <= 4 && !state->timer_count);
    operation_failed(minyar_net_loopTimer(loop, -1, 0, 0));
    operation_failed(minyar_net_loopTimer(loop, 1, -1, 0));
    operation_failed(minyar_net_loopWait(loop, -2, 1));
    operation_failed(minyar_net_loopWait(loop, 0, 0));
    operation_failed(minyar_net_loopWait(loop, 0, LLONG_MAX));
    operation_ok(minyar_net_loopClose(loop));
    operation_failed(minyar_net_loopWait(loop, 0, 1));
    operation_failed(minyar_net_loopClose(loop));
    long long replacement = result_handle(minyar_net_loopCreate());
    assert(replacement != loop);
    operation_failed(minyar_net_loopTimer(loop, 0, 0, 0));
    long long fresh = result_handle(minyar_net_loopTimer(replacement, 100, 0, 0));
    operation_failed(minyar_net_loopRemove(replacement, early));
    operation_ok(minyar_net_loopRemove(replacement, fresh));
    long long other = result_handle(minyar_net_loopCreate());
    long long elsewhere = result_handle(minyar_net_loopTimer(other, 100, 0, 0));
    operation_failed(minyar_net_loopRemove(replacement, elsewhere));
    operation_ok(minyar_net_loopRemove(other, elsewhere));
    operation_ok(minyar_net_loopClose(other));
    operation_ok(minyar_net_loopClose(replacement));
}

static void failed_poll_preserves_due_timers(void) {
#ifndef _WIN32
    long long loop = result_handle(minyar_net_loopCreate());
    long long timer = result_handle(minyar_net_loopTimer(loop, 0, 0, 321));
    NetLoop *state = net_loop_find(loop);
    int selector = state->selector;
    state->selector = -1; /* Controlled OS poll failure, repaired before retry. */
    operation_failed(minyar_net_loopWait(loop, 0, 2));
    state->selector = selector;
    MinyarBytes *b = minyar_net_loopWait(loop, 0, 2);
    assert(event_count(b) == 1 && loop_wide(b, 8) == (uint64_t)timer);
    minyar_rc_release(b);
    operation_ok(minyar_net_loopClose(loop));
#endif
}

static void socket_interest_and_ownership(void) {
    MinyarText host = loop_literal("127.0.0.1");
    long long socket = minyar_net_udp(&host, 0);
    long long sender = minyar_net_udp(&host, 0);
    assert(socket >= 0 && sender >= 0);
    assert(minyar_net_udpConnect(sender, &host, minyar_net_localPort(socket)));
    assert(minyar_net_nonBlocking(socket, false));
    long long loop = result_handle(minyar_net_loopCreate());
    long long watch = result_handle(minyar_net_loopWatch(loop, socket, 2, 12));
#ifndef _WIN32
    assert(fcntl((int)socket, F_GETFL) & O_NONBLOCK);
#else
    DWORD guard = 100;
    assert(
        !setsockopt((SOCKET)socket, SOL_SOCKET, SO_RCVTIMEO, (const char *)&guard, sizeof(guard)));
#endif
    MinyarBytes *empty = minyar_net_readResult(socket, 8, true);
    assert(loop_word(empty, 0) == NET_WOULD_BLOCK);
    minyar_rc_release(empty);
    operation_failed(minyar_net_loopWatch(loop, socket, 1, 99));
    MinyarBytes *b = minyar_net_loopWait(loop, 500, 4);
    assert(event_count(b) && loop_wide(b, 8) == (uint64_t)watch && loop_wide(b, 16) == 12);
    assert(loop_word(b, 24) & 2);
    minyar_rc_release(b);
    operation_ok(minyar_net_loopUpdate(loop, watch, 1, 41));
    b = minyar_net_loopWait(loop, 0, 4);
    assert(event_count(b) == 0);
    minyar_rc_release(b);
    MinyarBytes payload = loop_literal("x");
    operation_failed(minyar_net_loopWatch(loop, -1, 1, 0));
    operation_failed(minyar_net_loopUpdate(loop, watch, 4, 0));
    MinyarBytes *sent = minyar_net_writeResult(sender, &payload);
    assert(loop_word(sent, 0) == NET_OK);
    minyar_rc_release(sent);
    b = minyar_net_loopWait(loop, 500, 4);
    assert(event_count(b) && loop_wide(b, 16) == 41 && (loop_word(b, 24) & 1));
    minyar_rc_release(b);
    operation_ok(minyar_net_loopRemove(loop, watch));
    long long next = result_handle(minyar_net_loopWatch(loop, socket, 1, 42));
    assert(next != watch);
    operation_failed(minyar_net_loopUpdate(loop, watch, 1, 0));
    b = minyar_net_loopWait(loop, 0, 4);
    assert(event_count(b) && loop_wide(b, 16) == 42);
    minyar_rc_release(b);
    operation_ok(minyar_net_loopClose(loop));
    /* Closing a loop unregisters interest; its caller still owns the socket. */
    b = minyar_net_readResult(socket, 4, true);
    assert(loop_word(b, 0) == NET_OK && b->byte_length == 9 && b->bytes[8] == 'x');
    minyar_rc_release(b);
    minyar_net_close(sender);
    minyar_net_close(socket);
}

static void thousands_of_sockets_and_timer_fairness(void) {
    enum { N = 2048, BATCH = 31 };
#ifndef _WIN32
    struct rlimit previous, capacity;
    assert(getrlimit(RLIMIT_NOFILE, &previous) == 0);
    capacity = previous;
    if (capacity.rlim_cur < N + 128) {
        capacity.rlim_cur = N + 128;
        assert(capacity.rlim_cur <= capacity.rlim_max && setrlimit(RLIMIT_NOFILE, &capacity) == 0);
    }
#endif
    MinyarText host = loop_literal("127.0.0.1");
    long long sockets[N], watches[N];
    unsigned char seen[N] = {0};
    long long loop = result_handle(minyar_net_loopCreate());
    long long sender = minyar_net_udp(&host, 0);
    assert(sender >= 0);
    MinyarBytes packet = loop_literal("fair");
    for (unsigned i = 0; i < N; i++) {
        sockets[i] = minyar_net_udp(&host, 0);
        assert(sockets[i] >= 0);
        watches[i] = result_handle(minyar_net_loopWatch(loop, sockets[i], 1, i + 100));
        assert(minyar_net_udpConnect(sender, &host, minyar_net_localPort(sockets[i])));
        MinyarBytes *sent = minyar_net_writeResult(sender, &packet);
        assert(loop_word(sent, 0) == NET_OK);
        minyar_rc_release(sent);
    }
    for (unsigned i = 0; i < 100; i++)
        result_handle(minyar_net_loopTimer(loop, 0, 0, -(long long)i - 1));
    unsigned received = 0, timers = 0;
    for (unsigned batch = 0; batch < 500 && (received < N || timers < 100); batch++) {
        MinyarBytes *b = minyar_net_loopWait(loop, 1000, BATCH);
        size_t count = event_count(b);
        assert(count > 0 && count <= BATCH);
        for (size_t i = 0; i < count; i++) {
            size_t at = 8 + i * 32;
            long long token = (long long)loop_wide(b, at + 8);
            if (loop_word(b, at + 24) == 1) {
                assert(token < 0);
                timers++;
            } else {
                assert(token >= 100 && token < N + 100);
                unsigned slot = (unsigned)(token - 100);
                assert(!seen[slot] && loop_wide(b, at) == (uint64_t)watches[slot]);
                seen[slot] = 1;
                received++;
                MinyarBytes *read = minyar_net_readResult(sockets[slot], 16, true);
                assert(loop_word(read, 0) == NET_OK && read->byte_length == 12);
                minyar_rc_release(read);
            }
        }
        minyar_rc_release(b);
        if (batch == 8)
            assert(received > 0 && timers > 0);
    }
    assert(received == N && timers == 100);
    operation_ok(minyar_net_loopClose(loop));
    for (unsigned i = 0; i < N; i++)
        minyar_net_close(sockets[i]);
    minyar_net_close(sender);
#ifndef _WIN32
    assert(setrlimit(RLIMIT_NOFILE, &previous) == 0);
#endif
}

#ifndef _WIN32
static volatile sig_atomic_t signal_count;
static void loop_signal(int number) {
    (void)number;
    signal_count++;
}
#endif
static void idle_blocking_and_interrupted_deadline(void) {
    long long loop = result_handle(minyar_net_loopCreate());
#ifndef _WIN32
    struct sigaction action = {0}, previous;
    action.sa_handler = loop_signal;
    sigemptyset(&action.sa_mask);
    assert(sigaction(SIGALRM, &action, &previous) == 0);
    struct itimerval alarm = {{0, 5000}, {0, 5000}}, zero = {{0, 0}, {0, 0}};
    assert(setitimer(ITIMER_REAL, &alarm, NULL) == 0);
#endif
    uint64_t before = net_loop_now();
    clock_t cpu = clock();
    MinyarBytes *b = minyar_net_loopWait(loop, 100, 8);
    uint64_t elapsed = net_loop_now() - before;
    double cpu_seconds = (double)(clock() - cpu) / CLOCKS_PER_SEC;
#ifndef _WIN32
    assert(setitimer(ITIMER_REAL, &zero, NULL) == 0);
    assert(sigaction(SIGALRM, &previous, NULL) == 0);
    assert(signal_count > 3);
#endif
    assert(event_count(b) == 0 && elapsed >= 75 && elapsed < 1000);
    assert(cpu_seconds < 0.05);
    minyar_rc_release(b);
    operation_ok(minyar_net_loopClose(loop));
    printf("idle wait: %llu ms, %.4f CPU seconds\n", (unsigned long long)elapsed, cpu_seconds);
}

int main(void) {
    timers_and_stale_handles();
    failed_poll_preserves_due_timers();
    socket_interest_and_ownership();
    thousands_of_sockets_and_timer_fairness();
    idle_blocking_and_interrupted_deadline();
    puts("event loop: timers, generation safety, 2048 sockets, fairness, idle deadlines verified");
    return 0;
}
