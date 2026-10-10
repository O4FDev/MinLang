/* Real status-bar lifecycle and target/action; all temporary UI is removed. */
#include "../runtime/native/macos.m"
#include <assert.h>
extern void minyar_rc_release(void *);
static MinyarText service_literal(const char *s) {
    return (MinyarText){(const unsigned char *)s, (long long)strlen(s), -1, NULL, NULL};
}
int main(void) { @autoreleasepool {
    MinyarText name = service_literal("Minyar service test"), symbol = service_literal("network"), empty = service_literal("");
    minyar_macos_initialize(&name);
    assert(minyar_macos_accessory(true));
    assert(NSApp.activationPolicy == NSApplicationActivationPolicyAccessory);
    NSUInteger baseline = handles.count;
    for (int i = 0; i < 128; i++) {
        long long tray = minyar_macos_statusItem(&name, &symbol);
        NSStatusItem *status = object(tray, NSStatusItem.class);
        assert(status.button.image != nil);
        long long menu = minyar_macos_statusMenu(tray);
        assert(minyar_macos_statusMenu(tray) == menu);
        long long action = minyar_macos_menuItem(menu, &name, &empty);
        assert(entry(action).owner == tray);
        [status.menu performActionForItemAtIndex:0];
        assert(events.lastObject.kind == MNAction && events.lastObject.source == action);
        minyar_macos_statusRemove(tray);
        assert(!handles[@(tray)] && !handles[@(menu)] && !handles[@(action)]);
        assert(!events.count && handles.count == baseline);
    }
    assert(minyar_macos_accessory(false));
    assert(NSApp.activationPolicy == NSApplicationActivationPolicyRegular);
    puts("status icon, accessory mode, menu actions and lifecycle verified");
} return 0; }
