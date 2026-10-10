/* OS callbacks contain only Objective-C/C values. Managed allocations happen
 * on the caller's main thread, after copying a locked native snapshot. */
#import <AppKit/AppKit.h>
#import <UserNotifications/UserNotifications.h>
#import <ServiceManagement/ServiceManagement.h>
#import <Network/Network.h>
#import <IOKit/ps/IOPowerSources.h>
#import <IOKit/ps/IOPSKeys.h>
#include <os/lock.h>
#include <stdint.h>
#include <limits.h>
#include <math.h>
#include "../minyar_native.h"

#ifdef MINYAR_DESKTOP_TEST
static uint32_t desktop_word(const unsigned char *p) {
    return (uint32_t)p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24;
}
static uint64_t desktop_quad(const unsigned char *p) {
    return desktop_word(p) | (uint64_t)desktop_word(p+4)<<32;
}
#endif
static void desktop_put(MinyarBytes *b, size_t at, uint64_t value, size_t count) {
    for (size_t i=0; i<count; i++) ((unsigned char *)b->bytes)[at+i]=(unsigned char)(value>>(8*i));
}
static void desktop_owner(void) {
    if (![NSThread isMainThread]) minyar_native_stop("desktop APIs require the main thread.");
}
static MinyarBytes *desktop_envelope(uint32_t error, NSInteger native, size_t length) {
    MinyarBytes *b=minyar_bytes_new((long long)length);
    memset((void *)b->bytes,0,length); desktop_put(b,0,error,4); desktop_put(b,4,(uint32_t)native,4);
    return b;
}
static MinyarBytes *desktop_scalar(uint32_t error, NSInteger native, long long value) {
    MinyarBytes *b=desktop_envelope(error,native,16); desktop_put(b,8,(uint64_t)value,8); return b;
}
static NSString *desktop_string(const MinyarText *text, long long maximum) {
    if (text->byte_length<0 || text->byte_length>maximum) return nil;
    return [[NSString alloc] initWithBytes:text->bytes length:(NSUInteger)text->byte_length encoding:NSUTF8StringEncoding];
}
static void desktop_wake(void) {
    if (!NSApp) return;
    [NSApp postEvent:[NSEvent otherEventWithType:NSEventTypeApplicationDefined location:NSZeroPoint
        modifierFlags:0 timestamp:0 windowNumber:0 context:nil subtype:0x4D59 data1:0 data2:0] atStart:NO];
}

static MinyarBytes *desktop_power_snapshot(NSArray *descriptions, NSString *provider) {
    MinyarBytes *b=desktop_envelope(0,0,32);
    BOOL has=NO,ac=[provider isEqualToString:@kIOPSACPowerValue]; long long percent=-1;
    for (id value in descriptions) {
        if (![value isKindOfClass:NSDictionary.class]) continue;
        NSDictionary *d=value;
        if (![d[@kIOPSTypeKey] isEqual:@kIOPSInternalBatteryType] || ![d[@kIOPSIsPresentKey] isEqual:@YES]) continue;
        has=YES;
        id current=d[@kIOPSCurrentCapacityKey],maximum=d[@kIOPSMaxCapacityKey];
        if ([current isKindOfClass:NSNumber.class] && [maximum isKindOfClass:NSNumber.class] &&
            CFGetTypeID((__bridge CFTypeRef)current)!=CFBooleanGetTypeID() &&
            CFGetTypeID((__bridge CFTypeRef)maximum)!=CFBooleanGetTypeID()) {
            double n=[current doubleValue],m=[maximum doubleValue];
            if (isfinite(n) && isfinite(m) && n>=0 && m>0) percent=(long long)fmin(100,floor(n/m*100));
        }
        break;
    }
    desktop_put(b,8,has,8); desktop_put(b,16,ac,8); desktop_put(b,24,(uint64_t)percent,8); return b;
}
MinyarBytes *minyar_desktop_powerRaw(void) { @autoreleasepool {
    desktop_owner(); CFTypeRef info=IOPSCopyPowerSourcesInfo();
    if (!info) return desktop_envelope(9,0,32);
    CFArrayRef sources=IOPSCopyPowerSourcesList(info);
    if (!sources) { CFRelease(info); return desktop_envelope(9,0,32); }
    NSMutableArray *descriptions=[NSMutableArray new];
    for (CFIndex i=0;i<CFArrayGetCount(sources);i++) {
        CFDictionaryRef d=IOPSGetPowerSourceDescription(info,CFArrayGetValueAtIndex(sources,i));
        if (d) [descriptions addObject:(__bridge NSDictionary *)d];
    }
    MinyarBytes *b=desktop_power_snapshot(descriptions,(__bridge NSString *)IOPSGetProvidingPowerSourceType(info));
    CFRelease(sources); CFRelease(info); return b;
} }

typedef struct { BOOL known,usable,wifi,ethernet,expensive,constrained; } DesktopPath;
static DesktopPath desktop_path;
static os_unfair_lock desktop_path_lock=OS_UNFAIR_LOCK_INIT;
static nw_path_monitor_t desktop_monitor;
static uint64_t desktop_path_generation;
#ifdef MINYAR_DESKTOP_TEST
static BOOL desktop_test_network;
#endif
#ifdef MINYAR_DESKTOP_TEST
static void desktop_network_snapshot(BOOL usable, BOOL wifi, BOOL ethernet, BOOL expensive, BOOL constrained) {
    os_unfair_lock_lock(&desktop_path_lock);
    desktop_path=(DesktopPath){YES,usable,wifi,ethernet,expensive,constrained};
    os_unfair_lock_unlock(&desktop_path_lock);
}
#endif
static void desktop_start_monitor(void) {
    if (desktop_monitor) return;
#ifdef MINYAR_DESKTOP_TEST
    if (desktop_test_network) return;
#endif
    desktop_monitor=nw_path_monitor_create();
    if (!desktop_monitor) return;
    os_unfair_lock_lock(&desktop_path_lock); uint64_t generation=++desktop_path_generation;
    os_unfair_lock_unlock(&desktop_path_lock);
    nw_path_monitor_set_queue(desktop_monitor,dispatch_queue_create("minyar.desktop.network",DISPATCH_QUEUE_SERIAL));
    nw_path_monitor_set_update_handler(desktop_monitor,^(nw_path_t path) {
        DesktopPath value={YES,nw_path_get_status(path)==nw_path_status_satisfied,
            nw_path_uses_interface_type(path,nw_interface_type_wifi),nw_path_uses_interface_type(path,nw_interface_type_wired),
            nw_path_is_expensive(path),nw_path_is_constrained(path)};
        os_unfair_lock_lock(&desktop_path_lock);
        BOOL current=generation==desktop_path_generation;
        if (current) desktop_path=value;
        os_unfair_lock_unlock(&desktop_path_lock);
        if (current) desktop_wake();
    });
    nw_path_monitor_start(desktop_monitor);
}
MinyarBytes *minyar_desktop_networkRaw(void) { @autoreleasepool {
    desktop_owner(); desktop_start_monitor();
    os_unfair_lock_lock(&desktop_path_lock); DesktopPath p=desktop_path; os_unfair_lock_unlock(&desktop_path_lock);
    MinyarBytes *b=desktop_envelope(p.known?0:1,0,48);
    desktop_put(b,8,p.known,8); desktop_put(b,16,p.usable,8); desktop_put(b,24,p.wifi,8);
    desktop_put(b,32,p.ethernet,8); desktop_put(b,40,p.expensive|(p.constrained?2:0),8); return b;
} }
MinyarBytes *minyar_desktop_networkStopRaw(void) { @autoreleasepool {
    desktop_owner(); os_unfair_lock_lock(&desktop_path_lock);
    ++desktop_path_generation; memset(&desktop_path,0,sizeof(desktop_path)); os_unfair_lock_unlock(&desktop_path_lock);
    if (desktop_monitor) { nw_path_monitor_cancel(desktop_monitor); desktop_monitor=nil; }
    return desktop_scalar(0,0,1);
} }

MinyarBytes *minyar_desktop_launchAtLoginStatusRaw(void) { @autoreleasepool {
    desktop_owner();
    if (!NSBundle.mainBundle.bundleIdentifier.length) return desktop_scalar(9,0,0);
    if (@available(macOS 13,*)) return desktop_scalar(0,0,SMAppService.mainAppService.status);
    return desktop_scalar(9,0,0);
} }
MinyarBytes *minyar_desktop_setLaunchAtLoginRaw(bool enabled) { @autoreleasepool {
    desktop_owner();
    if (!NSBundle.mainBundle.bundleIdentifier.length) return desktop_scalar(9,0,0);
    if (@available(macOS 13,*)) {
        SMAppService *service=SMAppService.mainAppService; NSError *error=nil;
        if (service.status==SMAppServiceStatusNotFound) return desktop_scalar(9,0,service.status);
        if ((enabled && service.status!=SMAppServiceStatusNotRegistered) ||
            (!enabled && service.status==SMAppServiceStatusNotRegistered)) return desktop_scalar(0,0,service.status);
        BOOL ok=enabled?[service registerAndReturnError:&error]:[service unregisterAndReturnError:&error];
        return desktop_scalar(ok?0:8,error.code,service.status);
    }
    return desktop_scalar(9,0,0);
} }

@protocol DesktopNotificationCenter <NSObject>
- (void)getNotificationSettingsWithCompletionHandler:(void (^)(UNNotificationSettings *))block;
- (void)requestAuthorizationWithOptions:(UNAuthorizationOptions)options completionHandler:(void (^)(BOOL,NSError *))block;
- (void)addNotificationRequest:(UNNotificationRequest *)request withCompletionHandler:(void (^)(NSError *))block;
- (void)removePendingNotificationRequestsWithIdentifiers:(NSArray<NSString *> *)ids;
- (void)removeDeliveredNotificationsWithIdentifiers:(NSArray<NSString *> *)ids;
@end
@interface DesktopNotice : NSObject
@property(nonatomic) BOOL done,closed;
@property(nonatomic) uint32_t error;
@property(nonatomic) NSInteger nativeCode;
@property(nonatomic,copy) NSString *identifier;
@property(nonatomic,copy) NSString *title,body;
@end
@implementation DesktopNotice
@end
static NSMutableDictionary<NSNumber *,DesktopNotice *> *desktop_notices;
static long long desktop_notice_id=1;
#ifdef MINYAR_DESKTOP_TEST
static id<DesktopNotificationCenter> desktop_test_center;
static NSString *desktop_test_bundle;
#endif
static id<DesktopNotificationCenter> desktop_center(void) {
#ifdef MINYAR_DESKTOP_TEST
    if (desktop_test_center) return desktop_test_center;
#endif
    return (id<DesktopNotificationCenter>)UNUserNotificationCenter.currentNotificationCenter;
}
static void desktop_notice_finish(DesktopNotice *notice, uint32_t error, NSInteger native) {
    @synchronized(notice) { if (!notice.closed) { notice.done=YES; notice.error=error; notice.nativeCode=native; } }
    desktop_wake();
}
MinyarBytes *minyar_desktop_notifyRaw(const MinyarText *title, const MinyarText *body) { @autoreleasepool {
    desktop_owner(); NSString *t=desktop_string(title,256),*b=desktop_string(body,4096);
    if (!t.length || !b) return desktop_scalar(6,0,0);
    NSString *bundle=NSBundle.mainBundle.bundleIdentifier;
#ifdef MINYAR_DESKTOP_TEST
    if (desktop_test_bundle) bundle=desktop_test_bundle;
#endif
    if (!bundle.length) return desktop_scalar(9,0,0);
    if (!desktop_notices) desktop_notices=[NSMutableDictionary new];
    if (desktop_notices.count>=256 || desktop_notice_id==LLONG_MAX) return desktop_scalar(9,0,0);
    DesktopNotice *notice=[DesktopNotice new]; long long handle=desktop_notice_id++;
    notice.title=t; notice.body=b;
    notice.identifier=[NSString stringWithFormat:@"%@.minyar.%lld",bundle,handle]; desktop_notices[@(handle)]=notice;
    id<DesktopNotificationCenter> center=desktop_center();
    __weak id<DesktopNotificationCenter> weakCenter=center;
    __weak DesktopNotice *weakNotice=notice;
    void (^submit)(BOOL,NSError *)=^(BOOL granted,NSError *error) {
        DesktopNotice *active=weakNotice;
        id<DesktopNotificationCenter> provider=weakCenter;
        if (!active || !provider) return;
        @synchronized(active) {
            if (active.closed) return;
            if (!granted || error) { desktop_notice_finish(active,8,error.code); return; }
            UNMutableNotificationContent *content=[UNMutableNotificationContent new]; content.title=active.title; content.body=active.body;
            NSString *identifier=active.identifier;
            UNNotificationRequest *request=[UNNotificationRequest requestWithIdentifier:identifier content:content trigger:nil];
            [provider addNotificationRequest:request withCompletionHandler:^(NSError *failure) {
                DesktopNotice *completed=weakNotice;
                BOOL closed;
                @synchronized(completed) { closed=!completed || completed.closed; }
                if (closed) {
                    id<DesktopNotificationCenter> completionProvider=weakCenter;
                    [completionProvider removePendingNotificationRequestsWithIdentifiers:@[identifier]];
                    [completionProvider removeDeliveredNotificationsWithIdentifiers:@[identifier]];
                } else desktop_notice_finish(completed,failure?7:0,failure.code);
            }];
        }
    };
    [center getNotificationSettingsWithCompletionHandler:^(UNNotificationSettings *settings) {
        DesktopNotice *active=weakNotice;
        if (!active) return;
        @synchronized(active) { if (active.closed) return; }
        if (settings.authorizationStatus==UNAuthorizationStatusNotDetermined)
            [weakCenter requestAuthorizationWithOptions:UNAuthorizationOptionAlert|UNAuthorizationOptionSound completionHandler:submit];
        else submit(settings.authorizationStatus!=UNAuthorizationStatusDenied,nil);
    }];
    return desktop_scalar(0,0,handle);
} }
MinyarBytes *minyar_desktop_notificationStatusRaw(long long handle) { @autoreleasepool {
    desktop_owner(); DesktopNotice *notice=desktop_notices[@(handle)];
    if (!notice) return desktop_scalar(4,0,0);
    @synchronized(notice) { return desktop_scalar(notice.error,notice.nativeCode,notice.done?1:0); }
} }
MinyarBytes *minyar_desktop_notificationCloseRaw(long long handle) { @autoreleasepool {
    desktop_owner(); DesktopNotice *notice=desktop_notices[@(handle)];
    if (!notice) return desktop_scalar(4,0,0);
    @synchronized(notice) { notice.closed=YES; }
    [desktop_notices removeObjectForKey:@(handle)];
    [desktop_center() removePendingNotificationRequestsWithIdentifiers:@[notice.identifier]];
    [desktop_center() removeDeliveredNotificationsWithIdentifiers:@[notice.identifier]];
    return desktop_scalar(0,0,1);
} }
