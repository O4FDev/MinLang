/* Main-thread AppKit adapter. A native readiness hint wakes the owner; the
 * owner's loopWait dispatches managed callbacks and rearms the one-shot hint.
 * CF never receives a managed value or closes the reactor's descriptor. */
#ifndef MINYAR_APP_NET_LOOP_H
#define MINYAR_APP_NET_LOOP_H
#include <errno.h>
static MinyarBytes *mn_network_result(unsigned code, int native, long long value) {
    MinyarBytes *result = minyar_bytes_new(16);
    unsigned char *p = (unsigned char *)result->bytes;
    for (unsigned i = 0; i < 4; i++) {
        p[i] = (unsigned char)(code >> (8 * i));
        p[4 + i] = (unsigned char)((uint32_t)native >> (8 * i));
    }
    for (unsigned i = 0; i < 8; i++)
        p[8 + i] = (unsigned char)((uint64_t)value >> (8 * i));
    return result;
}
#ifdef MINYAR_APP_EVENT_LOOP
extern int minyar_net_appLoopDescriptor(long long);
extern uint64_t minyar_net_appLoopNow(void);
extern uint64_t minyar_net_appLoopDeadline(long long);
extern bool minyar_net_appLoopObserve(long long, void (*)(long long, unsigned));
static long long mn_network_loop;
static CFFileDescriptorRef mn_network_descriptor;
static CFRunLoopSourceRef mn_network_source;
static CFRunLoopTimerRef mn_network_timer;
static uint64_t mn_network_timer_deadline = UINT64_MAX;
static BOOL mn_network_wake_pending;
#ifdef MINYAR_MACOS_NETWORK_TEST
static unsigned mn_network_wake_count;
#endif
static void mn_network_wake(void) {
    if (mn_network_wake_pending)
        return;
    mn_network_wake_pending = YES;
#ifdef MINYAR_MACOS_NETWORK_TEST
    mn_network_wake_count++;
#endif
    CFFileDescriptorDisableCallBacks(mn_network_descriptor, kCFFileDescriptorReadCallBack);
    mn_network_timer_deadline = UINT64_MAX;
    CFRunLoopTimerSetNextFireDate(mn_network_timer, CFAbsoluteTimeGetCurrent() + 1.0e9);
    [NSApp postEvent:[NSEvent otherEventWithType:NSEventTypeApplicationDefined
                                        location:NSZeroPoint
                                   modifierFlags:0
                                       timestamp:0
                                    windowNumber:0
                                         context:nil
                                         subtype:MNWakeSubtype
                                           data1:0
                                           data2:0]
             atStart:NO];
}
static void mn_network_rearm(void) {
    if (!mn_network_loop || mn_network_wake_pending)
        return;
    CFFileDescriptorEnableCallBacks(mn_network_descriptor, kCFFileDescriptorReadCallBack);
    uint64_t deadline = minyar_net_appLoopDeadline(mn_network_loop);
    uint64_t now = minyar_net_appLoopNow();
    if (deadline != UINT64_MAX && deadline <= now) {
        mn_network_wake();
        return;
    }
    if (deadline != mn_network_timer_deadline) {
        mn_network_timer_deadline = deadline;
        double delay =
            deadline == UINT64_MAX ? 1.0e9 : fmin(1.0e9, (double)(deadline - now) / 1000);
        CFRunLoopTimerSetNextFireDate(mn_network_timer, CFAbsoluteTimeGetCurrent() + delay);
    }
}
static void mn_network_detach(void) {
    minyar_net_appLoopObserve(0, NULL);
    mn_network_loop = 0;
    mn_network_wake_pending = NO;
    mn_network_timer_deadline = UINT64_MAX;
    if (mn_network_source) {
        CFRunLoopRemoveSource(CFRunLoopGetMain(), mn_network_source, kCFRunLoopCommonModes);
        CFRunLoopSourceInvalidate(mn_network_source);
        CFRelease(mn_network_source);
        mn_network_source = NULL;
    }
    if (mn_network_descriptor) {
        CFFileDescriptorInvalidate(mn_network_descriptor);
        CFRelease(mn_network_descriptor);
        mn_network_descriptor = NULL;
    }
    if (mn_network_timer) {
        CFRunLoopTimerInvalidate(mn_network_timer);
        CFRelease(mn_network_timer);
        mn_network_timer = NULL;
    }
}
static void mn_network_observe(long long handle, unsigned reason) {
    if (handle != mn_network_loop)
        return;
    if (reason == 2)
        mn_network_detach();
    else {
        if (reason == 1)
            mn_network_wake_pending = NO;
        mn_network_rearm();
    }
}
static void mn_network_ready(CFFileDescriptorRef descriptor, CFOptionFlags flags, void *context) {
    (void)flags;
    if (descriptor == mn_network_descriptor && (long long)(uintptr_t)context == mn_network_loop)
        mn_network_wake();
}
static void mn_network_timer_ready(CFRunLoopTimerRef timer, void *context) {
    if (timer != mn_network_timer || (long long)(uintptr_t)context != mn_network_loop)
        return;
    /* CF's wall-clock scheduling is only a wake hint: readiness and actual
     * deadlines remain on the reactor's monotonic clock, even after a clock
     * change or an early system timer callback. */
    mn_network_timer_deadline = UINT64_MAX;
    mn_network_rearm();
}
#endif
MinyarBytes *minyar_macos_shareNetworkLoopRaw(long long handle) {
    @autoreleasepool {
        ready();
#ifdef MINYAR_APP_EVENT_LOOP
        int descriptor = minyar_net_appLoopDescriptor(handle);
        if (descriptor < 0)
            return mn_network_result(4, 0, 0);
        if (handle == mn_network_loop)
            return mn_network_result(0, 0, 1);
        mn_network_detach();
        CFFileDescriptorContext fd_context = {0, (void *)(uintptr_t)handle, NULL, NULL, NULL};
        mn_network_descriptor =
            CFFileDescriptorCreate(NULL, descriptor, false, mn_network_ready, &fd_context);
        if (mn_network_descriptor)
            mn_network_source = CFFileDescriptorCreateRunLoopSource(NULL, mn_network_descriptor, 0);
        CFRunLoopTimerContext timer_context = {0, (void *)(uintptr_t)handle, NULL, NULL, NULL};
        mn_network_timer = CFRunLoopTimerCreate(NULL, CFAbsoluteTimeGetCurrent() + 1.0e9, 1.0e9, 0,
                                                0, mn_network_timer_ready, &timer_context);
        if (!mn_network_source || !mn_network_timer) {
            mn_network_detach();
            return mn_network_result(7, ENOMEM, 0);
        }
        mn_network_loop = handle;
        minyar_net_appLoopObserve(handle, mn_network_observe);
        CFRunLoopAddSource(CFRunLoopGetMain(), mn_network_source, kCFRunLoopCommonModes);
        CFRunLoopAddTimer(CFRunLoopGetMain(), mn_network_timer, kCFRunLoopCommonModes);
        mn_network_rearm();
        return mn_network_result(0, 0, 1);
#else
        (void)handle;
        return mn_network_result(9, 0, 0);
#endif
    }
}
MinyarBytes *minyar_macos_unshareNetworkLoopRaw(void) {
    @autoreleasepool {
        ready();
#ifdef MINYAR_APP_EVENT_LOOP
        mn_network_detach();
#endif
        return mn_network_result(0, 0, 1);
    }
}
#endif
