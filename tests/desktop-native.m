/* The async provider seam exercises denial, cancellation and delayed replies
 * without modifying login settings or showing notifications on the CI host. */
#define MINYAR_DESKTOP_TEST 1
#include "../runtime/native/desktop.m"
#include <assert.h>
extern void minyar_rc_release(void *);
static MinyarText test_text(const char *s) {
    return (MinyarText){(const unsigned char *)s, (long long)strlen(s), -1, NULL, NULL};
}
static uint32_t code(MinyarBytes *b) { return desktop_word(b->bytes); }
static long long result(MinyarBytes *b) {
    assert(b->byte_length == 16 && !code(b));
    long long n = (long long)desktop_quad(b->bytes + 8); minyar_rc_release(b); return n;
}
@interface TestSettings : NSObject
@property(nonatomic) UNAuthorizationStatus authorizationStatus;
@end
@implementation TestSettings
@end
@interface TestCenter : NSObject <DesktopNotificationCenter>
@property(nonatomic) UNAuthorizationStatus status;
@property(nonatomic) BOOL deferred, granted, deferredDelivery;
@property(nonatomic) NSUInteger sent, removed;
@property(nonatomic,copy) void (^authorization)(BOOL,NSError *);
@property(nonatomic,copy) void (^delivery)(NSError *);
@end
@implementation TestCenter
- (void)getNotificationSettingsWithCompletionHandler:(void (^)(UNNotificationSettings *))block {
    TestSettings *s = [TestSettings new]; s.authorizationStatus = self.status;
    block((UNNotificationSettings *)s);
}
- (void)requestAuthorizationWithOptions:(UNAuthorizationOptions)options completionHandler:(void (^)(BOOL,NSError *))block {
    assert(options & UNAuthorizationOptionAlert);
    if (self.deferred) self.authorization = block; else block(self.granted,nil);
}
- (void)addNotificationRequest:(UNNotificationRequest *)request withCompletionHandler:(void (^)(NSError *))block {
    assert(request.content.title.length); self.sent++;
    if (self.deferredDelivery) self.delivery=block; else block(nil);
}
- (void)removePendingNotificationRequestsWithIdentifiers:(NSArray<NSString *> *)ids { assert(ids.count == 1); self.removed++; }
- (void)removeDeliveredNotificationsWithIdentifiers:(NSArray<NSString *> *)ids { assert(ids.count == 1); }
@end
int main(void) { @autoreleasepool {
    /* Missing/bogus power descriptions must not invent a battery level. */
    MinyarBytes *b = desktop_power_snapshot(@[], @"AC Power");
    assert(!code(b) && desktop_quad(b->bytes+8)==0 && desktop_quad(b->bytes+16)==1 && (long long)desktop_quad(b->bytes+24)==-1);
    minyar_rc_release(b);
    NSDictionary *battery = @{@kIOPSTypeKey:@kIOPSInternalBatteryType,@kIOPSIsPresentKey:@YES,
        @kIOPSCurrentCapacityKey:@25,@kIOPSMaxCapacityKey:@50};
    b=desktop_power_snapshot(@[battery],@"Battery Power");
    assert(!code(b) && desktop_quad(b->bytes+8)==1 && desktop_quad(b->bytes+16)==0 && desktop_quad(b->bytes+24)==50);
    minyar_rc_release(b);
    NSMutableDictionary *bad=[battery mutableCopy]; bad[@kIOPSMaxCapacityKey]=@NO;
    b=desktop_power_snapshot(@[bad],@"AC Power"); assert((long long)desktop_quad(b->bytes+24)==-1); minyar_rc_release(b);
    desktop_test_network=YES;
    for (unsigned flags=0; flags<32; flags++) {
        desktop_network_snapshot(flags&1,flags&2,flags&4,flags&8,flags&16);
        b=minyar_desktop_networkRaw(); assert(!code(b) && desktop_quad(b->bytes+8)==1);
        assert(desktop_quad(b->bytes+16)==!!(flags&1) && desktop_quad(b->bytes+24)==!!(flags&2) && desktop_quad(b->bytes+32)==!!(flags&4));
        assert(desktop_quad(b->bytes+40)==((flags&8?1:0)|(flags&16?2:0))); minyar_rc_release(b);
    }
    MinyarText title=test_text("Minyar test"), body=test_text("body");
    TestCenter *fake=[TestCenter new]; desktop_test_center=fake;
    desktop_test_bundle=@"com.minyar.test";
    fake.status=UNAuthorizationStatusDenied;
    long long id=result(minyar_desktop_notifyRaw(&title,&body));
    b=minyar_desktop_notificationStatusRaw(id); assert(code(b)==8); minyar_rc_release(b);
    assert(result(minyar_desktop_notificationCloseRaw(id))==1 && fake.sent==0);
    fake.status=UNAuthorizationStatusNotDetermined; fake.granted=YES;
    id=result(minyar_desktop_notifyRaw(&title,&body));
    assert(result(minyar_desktop_notificationStatusRaw(id))==1 && fake.sent==1);
    assert(result(minyar_desktop_notificationCloseRaw(id))==1);
    fake.deferred=YES;
    id=result(minyar_desktop_notifyRaw(&title,&body));
    assert(result(minyar_desktop_notificationStatusRaw(id))==0);
    __weak DesktopNotice *notice=desktop_notices[@(id)];
    assert(result(minyar_desktop_notificationCloseRaw(id))==1);
    @autoreleasepool { fake.authorization(YES,nil); fake.authorization=nil; }
    assert(!notice && fake.sent==1);
    b=minyar_desktop_notificationStatusRaw(id); assert(code(b)==4); minyar_rc_release(b);
    assert(!desktop_notices.count);
    /* Closing during native delivery must remove a late queued request too. */
    fake.status=UNAuthorizationStatusAuthorized; fake.deferredDelivery=YES;
    id=result(minyar_desktop_notifyRaw(&title,&body));
    assert(result(minyar_desktop_notificationStatusRaw(id))==0);
    NSUInteger removed=fake.removed;
    assert(result(minyar_desktop_notificationCloseRaw(id))==1);
    @autoreleasepool { fake.delivery(nil); fake.delivery=nil; }
    assert(fake.removed==removed+2 && !desktop_notices.count);
    /* Native failure must remain recoverable, and stale IDs never alias. */
    id=result(minyar_desktop_notifyRaw(&title,&body));
    fake.delivery([NSError errorWithDomain:@"fixture" code:42 userInfo:nil]); fake.delivery=nil;
    b=minyar_desktop_notificationStatusRaw(id); assert(code(b)==7); minyar_rc_release(b);
    assert(result(minyar_desktop_notificationCloseRaw(id))==1);
    for (long long stale=-2;stale<2;stale++) {
        b=minyar_desktop_notificationStatusRaw(stale); assert(code(b)==4); minyar_rc_release(b);
    }
    desktop_test_center=nil; desktop_test_bundle=nil;
    b=minyar_desktop_notifyRaw(&title,&body); assert(code(b)==9); minyar_rc_release(b);
    b=minyar_desktop_launchAtLoginStatusRaw(); assert(code(b)==9); minyar_rc_release(b);
    puts("desktop snapshots, notification denial/cancellation and unavailable services verified");
} return 0; }
