/* Exercise actual AppKit target/action and delegate delivery without UI scripting.
 * Importing the bridge gives this test access to native objects; Minyar callers
 * get only the checked API. Link against the real Minyar runtime. */
#include "../runtime/native/macos.m"
#include <assert.h>
extern void minyar_rc_release(void *value);
static MinyarText literal(const char *s) { return (MinyarText){(const unsigned char *)s, (long long)strlen(s), -1, NULL, NULL}; }
static void equals(MinyarText *value, const char *expected) {
    assert(value->byte_length == (long long)strlen(expected));
    assert(!memcmp(value->bytes,expected,strlen(expected)));
    minyar_rc_release(value);
}
static BOOL receive(long long kind, long long source) {
    for (int i = 0; i < 50; ++i) {
        if (!minyar_macos_nextEvent(0.001)) return NO;
        if (minyar_macos_eventType() == kind && minyar_macos_eventSource() == source) return YES;
    }
    return NO;
}
static void verifyRelease(void) {
    __weak NSView *weakView;
    __weak NSWindow *weakWindow;
    @autoreleasepool {
        MinyarText name = literal("Lifetime test");
        long long w = minyar_macos_window(&name,320,240);
        long long root = minyar_macos_column(w,4);
        long long field = minyar_macos_textField(root,&name);
        weakView = entry(field).object; weakWindow = entry(w).object;
        minyar_macos_destroy(w);
    }
    assert(!weakView && !weakWindow);
}
int main(int argc, char **argv) { @autoreleasepool {
    MinyarText title = literal("Native contract"), unicode = literal("é 🙂 漢字"), empty = literal("");
    if (argc > 1 && !strcmp(argv[1],"uninitialized")) { minyar_macos_window(&title,100,100); return 99; }
    minyar_macos_initialize(&title);
    if (argc > 1 && !strcmp(argv[1],"thread")) {
        [NSThread detachNewThreadWithBlock:^{ minyar_macos_window(&title,100,100); }];
        [NSThread sleepForTimeInterval:2]; return 99;
    }
    verifyRelease();
    long long w = minyar_macos_window(&title,640,480);
    long long root = minyar_macos_column(w,8); minyar_macos_padding(root,10);
    long long field = minyar_macos_textField(root,&unicode);
    long long edit = minyar_macos_textEditor(root,&unicode);
    long long row = minyar_macos_row(root,4);
    long long button = minyar_macos_button(row,&title);
    long long check = minyar_macos_checkbox(row,&title,false);
    long long slide = minyar_macos_slider(root,0,10,4.5);
    long long menu = minyar_macos_menu(&title);
    long long item = minyar_macos_menuItem(menu,&title,&empty);
    if (argc > 1) {
        if (!strcmp(argv[1],"stale")) { minyar_macos_destroy(w); minyar_macos_text(field); }
        if (!strcmp(argv[1],"wrong-type")) minyar_macos_checked(button);
        if (!strcmp(argv[1],"range")) minyar_macos_setValue(slide,NAN);
        if (!strcmp(argv[1],"timeout")) minyar_macos_nextEvent(-1);
        if (!strcmp(argv[1],"parent")) minyar_macos_button(button,&title);
        if (!strcmp(argv[1],"duplicate-init")) minyar_macos_initialize(&title);
        if (!strcmp(argv[1],"overflow")) for (int i = 0; i < 4097; ++i) enqueue(MNAction,button,@"");
        if (!strcmp(argv[1],"dimension")) minyar_macos_window(&title,-1,100);
        return 99;
    }
    equals(minyar_macos_text(field),"é 🙂 漢字");
    equals(minyar_macos_text(edit),"é 🙂 漢字");
    // Embedded NUL must survive both bridging directions.
    unsigned char bytes[] = {'a',0,'b'};
    MinyarText zero = {bytes,3,3,NULL,NULL}; minyar_macos_setText(field,&zero);
    MinyarText *roundtrip = minyar_macos_text(field);
    assert(roundtrip->byte_length == 3 && !memcmp(roundtrip->bytes,bytes,3)); minyar_rc_release(roundtrip);
    minyar_macos_setText(field,&unicode);
    minyar_macos_show(w);
    [object(button,NSButton.class) performClick:nil];
    assert(receive(MNAction,button));
    [object(check,NSButton.class) performClick:nil];
    assert(receive(MNAction,check)); assert(minyar_macos_checked(check));
    minyar_macos_setChecked(check,false); assert(!minyar_macos_checked(check));
    minyar_macos_setValue(slide,7.25); assert(minyar_macos_value(slide) == 7.25);
    NSSlider *slider = object(slide,NSSlider.class); [slider sendAction:slider.action to:slider.target];
    assert(receive(MNChange,slide));
    NSMenu *nativeMenu = object(menu,NSMenu.class); [nativeMenu performActionForItemAtIndex:0];
    assert(receive(MNAction,item));
    minyar_macos_enabled(item,false); assert(![(NSMenuItem *)entry(item).object isEnabled]);
    NSTextField *nativeField = object(field,NSTextField.class);
    [NSNotificationCenter.defaultCenter postNotificationName:NSControlTextDidChangeNotification object:nativeField];
    assert(receive(MNChange,field)); equals(minyar_macos_eventText(),"é 🙂 漢字");
    // An event snapshot must not change when the control subsequently changes.
    minyar_macos_setText(field,&title); equals(minyar_macos_eventText(),"é 🙂 漢字");
    NSTextView *nativeEditor = editor(entry(edit).object);
    [NSNotificationCenter.defaultCenter postNotificationName:NSTextDidChangeNotification object:nativeEditor];
    assert(receive(MNChange,edit)); equals(minyar_macos_eventText(),"é 🙂 漢字");
    NSWindow *window = object(w,NSWindow.class); [window setContentSize:NSMakeSize(700,520)];
    assert(receive(MNResized,w)); assert(minyar_macos_width(w) == 700); assert(minyar_macos_height(w) == 520);
    // A second independent window survives destruction of the first.
    long long second = minyar_macos_window(&title,320,240);
    window = nil; nativeField = nil; nativeEditor = nil; slider = nil;
    minyar_macos_close(w); assert(receive(MNClosed,w));
    minyar_macos_destroy(w); assert(handles[@(field)] == nil); assert(handles[@(edit)] == nil);
    assert(minyar_macos_width(second) == 320);
    // Drain AppKit's autoreleased notifications before checking release.
    minyar_macos_destroy(second);
    minyar_macos_quit(); assert(receive(MNQuit,0)); assert(!minyar_macos_nextEvent(0));
    assert(handles.count == 2); // Only the application-scoped menu and item remain.
    puts("native AppKit actions, delegates, Unicode, windows, menus and lifecycle verified");
    return 0;
} }
