/* Actual kqueue readiness and timers in the AppKit main run loop. */
#define MINYAR_MACOS_NETWORK_TEST 1
#include "../runtime/native/macos.m"
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <unistd.h>
extern void minyar_rc_release(void *);
extern MinyarBytes *minyar_net_loopCreate(void);
extern MinyarBytes *minyar_net_loopWatch(long long,long long,long long,long long);
extern MinyarBytes *minyar_net_loopTimer(long long,long long,long long,long long);
extern MinyarBytes *minyar_net_loopRemove(long long,long long);
extern MinyarBytes *minyar_net_loopWait(long long,long long,long long);
extern MinyarBytes *minyar_net_loopClose(long long);
static uint64_t network_word(const unsigned char *p) {
    uint64_t value=0; for (unsigned i=0;i<8;i++) value|=(uint64_t)p[i]<<(i*8); return value;
}
static long long network_value(MinyarBytes *result) {
    assert(result->byte_length==16 && !result->bytes[0]);
    long long value=(long long)network_word(result->bytes+8); minyar_rc_release(result); return value;
}
static void network_status(MinyarBytes *result,unsigned code) {
    assert(result->byte_length==16 && result->bytes[0]==code); minyar_rc_release(result);
}
static void network_drain_events(void) {
    while ([NSApp nextEventMatchingMask:NSEventMaskAny untilDate:NSDate.distantPast
            inMode:NSDefaultRunLoopMode dequeue:YES]) {}
}
int main(void) { @autoreleasepool {
    MinyarText name={(const unsigned char *)"Minyar network test",19,-1,NULL,NULL};
    minyar_macos_initialize(&name); assert(minyar_macos_accessory(true));
    network_status(minyar_macos_shareNetworkLoopRaw(-1),4);
    for (unsigned round=0;round<64;round++) {
        long long loop=network_value(minyar_net_loopCreate());
        network_status(minyar_macos_shareNetworkLoopRaw(loop),0);
        network_status(minyar_macos_shareNetworkLoopRaw(loop),0);
        int sockets[2]; assert(!socketpair(AF_UNIX,SOCK_STREAM,0,sockets));
        long long registration=network_value(minyar_net_loopWatch(loop,sockets[0],1,111));
        network_drain_events();
        assert(write(sockets[1],"x",1)==1);
        assert(minyar_macos_nextEvent(.5));
        assert(mn_network_wake_pending);
        unsigned wakes=mn_network_wake_count;
        CFRunLoopRunInMode(kCFRunLoopDefaultMode,.03,false);
        assert(mn_network_wake_count==wakes);
        MinyarBytes *ready=minyar_net_loopWait(loop,0,16);
        assert(ready->byte_length==40 && network_word(ready->bytes+16)==111);
        minyar_rc_release(ready);
        char data; assert(read(sockets[0],&data,1)==1 && data=='x');
        network_status(minyar_net_loopRemove(loop,registration),0);
        /* A readiness hint is one shot until the owner drains/polls: a slow
         * application must not produce an unbounded wake queue or spin. */
        network_drain_events();
        assert(write(sockets[1],"y",1)==1);
        CFRunLoopRunInMode(kCFRunLoopDefaultMode,.01,false);
        assert(!mn_network_wake_pending);
        long long timer=network_value(minyar_net_loopTimer(loop,15,0,222));
        (void)timer;
        assert(minyar_macos_nextEvent(.5));
        assert(mn_network_wake_pending);
        ready=minyar_net_loopWait(loop,0,16);
        assert(ready->byte_length==40 && network_word(ready->bytes+16)==222);
        minyar_rc_release(ready); assert(!mn_network_wake_pending);
        network_drain_events();
        assert(minyar_macos_nextEvent(.025)); assert(!mn_network_wake_pending);
        /* Cancelling an attached timer must remove its CF wake deadline. */
        timer=network_value(minyar_net_loopTimer(loop,1000,0,333));
        network_status(minyar_net_loopRemove(loop,timer),0);
        assert(minyar_macos_nextEvent(.025)); assert(!mn_network_wake_pending);
        /* Closing detaches before kqueue FD reuse; an old ID cannot attach
         * to a different loop allocated in the same registry slot. */
        network_status(minyar_net_loopClose(loop),0);
        assert(!mn_network_loop && !mn_network_descriptor && !mn_network_timer);
        long long replacement=network_value(minyar_net_loopCreate());
        assert(replacement!=loop);
        network_status(minyar_macos_shareNetworkLoopRaw(loop),4);
        network_status(minyar_macos_shareNetworkLoopRaw(replacement),0);
        network_status(minyar_macos_unshareNetworkLoopRaw(),0);
        assert(fcntl(minyar_net_appLoopDescriptor(replacement),F_GETFD)>=0);
        network_status(minyar_net_loopClose(replacement),0);
        close(sockets[0]); close(sockets[1]);
    }
    puts("AppKit shares socket readiness, timers and generation-safe close with kqueue");
} return 0; }
