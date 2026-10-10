/* Swift's AppKit calls lower to these same Objective-C classes/selectors.
 * Compile with ARC. Only scalar values and borrowed/owned Minyar Text cross
 * the C ABI; no Objective-C pointers or Swift ABI types escape this file. */
#import <AppKit/AppKit.h>
#include <math.h>
#include <limits.h>
#include "../minyar_native.h"

enum { MNNone, MNAction, MNChange, MNClosed, MNResized, MNQuit };
@interface MNHandle : NSObject
@property(nonatomic, strong) id object;
@property(nonatomic) long long owner;
@property(nonatomic) BOOL isCheckbox;
@property(nonatomic, strong) NSLayoutConstraint *width;
@property(nonatomic, strong) NSLayoutConstraint *height;
@end
@implementation MNHandle
@end
@interface MNEvent : NSObject
@property(nonatomic) long long kind, source;
@property(nonatomic, copy) NSString *text;
@end
@implementation MNEvent
@end
@interface MNDelegate : NSObject <NSApplicationDelegate, NSWindowDelegate, NSTextFieldDelegate, NSTextViewDelegate>
- (void)action:(id)sender;
- (void)requestQuit:(id)sender;
@end
static NSMutableDictionary<NSNumber *, MNHandle *> *handles;
static NSMutableArray<MNEvent *> *events;
static MNEvent *current;
static MNDelegate *delegate;
static long long nextHandle = 1;
static BOOL quitting;

static void mainThread(void) {
    if (![NSThread isMainThread]) minyar_native_stop("macos APIs require the main thread.");
}
static void ready(void) {
    mainThread();
    if (!handles) minyar_native_stop("call macos.initialize before using desktop APIs.");
}
static NSString *string(const MinyarText *text) {
    NSString *s = [[NSString alloc] initWithBytes:text->bytes length:(NSUInteger)text->byte_length encoding:NSUTF8StringEncoding];
    if (!s) minyar_native_stop("macos requires valid UTF-8 Text.");
    return s;
}
static MinyarText *owned(NSString *s) {
    NSData *data = [(s ?: @"") dataUsingEncoding:NSUTF8StringEncoding];
    if (!data) minyar_native_stop("macos could not encode Unicode Text.");
    return minyar_native_copy_text(data.bytes, (long long)data.length);
}
static MNHandle *entry(long long handle) {
    ready();
    MNHandle *h = handles[@(handle)];
    if (!h) minyar_native_stop("macos received an invalid or destroyed handle.");
    return h;
}
static id object(long long handle, Class type) {
    id value = entry(handle).object;
    if (![value isKindOfClass:type]) minyar_native_stop("macos handle has the wrong object type.");
    return value;
}
static long long registerObject(id value, long long owner) {
    if (!value || nextHandle == LLONG_MAX) minyar_native_stop("macos could not allocate a native object.");
    MNHandle *h = [MNHandle new];
    h.object = value; h.owner = owner;
    long long result = nextHandle++;
    handles[@(result)] = h;
    return result;
}
static long long identifier(id value) {
    for (NSNumber *key in handles) if (handles[key].object == value) return key.longLongValue;
    return 0;
}
static void enqueue(long long kind, long long source, NSString *text) {
    // Repeated edits/resizes of the same source need only the latest snapshot.
    MNEvent *last = events.lastObject;
    if ((kind == MNChange || kind == MNResized) && last.kind == kind && last.source == source) {
        last.text = text ?: @""; return;
    }
    if (events.count >= 4096) minyar_native_stop("macos event queue is full; consume events with nextEvent.");
    MNEvent *e = [MNEvent new]; e.kind = kind; e.source = source; e.text = text ?: @"";
    [events addObject:e];
}
static void requestQuit(void) {
    if (!quitting) { quitting = YES; enqueue(MNQuit, 0, @""); }
}
static NSTextView *editor(id value) {
    return [value isKindOfClass:NSScrollView.class] && [[value documentView] isKindOfClass:NSTextView.class] ? [value documentView] : nil;
}
static NSString *getText(id value) {
    if (editor(value)) return editor(value).string;
    if ([value isKindOfClass:NSTextField.class]) return [value stringValue];
    if ([value isKindOfClass:NSWindow.class] || [value isKindOfClass:NSButton.class] || [value isKindOfClass:NSMenuItem.class]) return [value title];
    minyar_native_stop("macos.text requires a window, text control, button, or menu item.");
    return nil;
}
@implementation MNDelegate
- (void)action:(id)sender {
    enqueue([sender isKindOfClass:NSSlider.class] ? MNChange : MNAction, identifier(sender), @"");
}
- (void)requestQuit:(id)sender { (void)sender; requestQuit(); }
- (NSApplicationTerminateReply)applicationShouldTerminate:(NSApplication *)app {
    (void)app; requestQuit(); return NSTerminateCancel;
}
- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication *)app { (void)app; return NO; }
- (void)windowWillClose:(NSNotification *)notification { enqueue(MNClosed, identifier(notification.object), @""); }
- (void)windowDidResize:(NSNotification *)notification { enqueue(MNResized, identifier(notification.object), @""); }
- (void)controlTextDidChange:(NSNotification *)notification {
    enqueue(MNChange, identifier(notification.object), [notification.object stringValue]);
}
- (void)textDidChange:(NSNotification *)notification {
    NSTextView *view = notification.object;
    enqueue(MNChange, identifier(view.enclosingScrollView), view.string);
}
@end

static void dimension(long long n) {
    if (n < 0 || n > 100000) minyar_native_stop("macos dimensions must be between 0 and 100000 points.");
}
static long long append(long long parent, NSView *view) {
    MNHandle *p = entry(parent);
    view.translatesAutoresizingMaskIntoConstraints = NO;
    long long owner = p.owner;
    if ([p.object isKindOfClass:NSWindow.class]) {
        NSView *content = [p.object contentView];
        if (content.subviews.count) minyar_native_stop("a macos window accepts one root view; add controls to a row or column.");
        owner = parent;
        [content addSubview:view];
        [NSLayoutConstraint activateConstraints:@[
            [view.leadingAnchor constraintEqualToAnchor:content.leadingAnchor],
            [view.trailingAnchor constraintEqualToAnchor:content.trailingAnchor],
            [view.topAnchor constraintEqualToAnchor:content.topAnchor],
            [view.bottomAnchor constraintEqualToAnchor:content.bottomAnchor]]];
    } else if ([p.object isKindOfClass:NSStackView.class]) {
        [(NSStackView *)p.object addArrangedSubview:view];
    } else minyar_native_stop("macos parent must be a window, row, or column.");
    return registerObject(view, owner);
}
void minyar_macos_initialize(const MinyarText *name) { @autoreleasepool {
    mainThread();
    if (handles) minyar_native_stop("macos.initialize may only be called once.");
    [NSApplication sharedApplication];
    handles = [NSMutableDictionary new]; events = [NSMutableArray new]; delegate = [MNDelegate new];
    NSApp.delegate = delegate;
    [NSApp setActivationPolicy:NSApplicationActivationPolicyRegular];
    NSMenu *main = [NSMenu new];
    NSMenuItem *appItem = [NSMenuItem new]; [main addItem:appItem];
    NSMenu *appMenu = [[NSMenu alloc] initWithTitle:string(name)]; appItem.submenu = appMenu;
    NSMenuItem *quit = [[NSMenuItem alloc] initWithTitle:[@"Quit " stringByAppendingString:string(name)] action:@selector(requestQuit:) keyEquivalent:@"q"];
    quit.target = delegate; [appMenu addItem:quit];
    NSMenuItem *editItem = [[NSMenuItem alloc] initWithTitle:@"Edit" action:NULL keyEquivalent:@""];
    [main addItem:editItem]; NSMenu *edit = [[NSMenu alloc] initWithTitle:@"Edit"]; editItem.submenu = edit;
    NSArray *titles = @[@"Undo", @"Redo", @"Cut", @"Copy", @"Paste", @"Select All"];
    NSArray *actions = @[@"undo:", @"redo:", @"cut:", @"copy:", @"paste:", @"selectAll:"];
    NSArray *keys = @[@"z", @"Z", @"x", @"c", @"v", @"a"];
    for (NSUInteger i = 0; i < titles.count; ++i)
        [edit addItem:[[NSMenuItem alloc] initWithTitle:titles[i] action:NSSelectorFromString(actions[i]) keyEquivalent:keys[i]]];
    NSApp.mainMenu = main;
    [NSApp finishLaunching];
} }
long long minyar_macos_window(const MinyarText *title, long long width, long long height) { @autoreleasepool {
    ready(); dimension(width); dimension(height);
    if (!width || !height) minyar_native_stop("macos windows require positive dimensions.");
    NSWindow *w = [[NSWindow alloc] initWithContentRect:NSMakeRect(0,0,width,height)
        styleMask:NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskMiniaturizable | NSWindowStyleMaskResizable
        backing:NSBackingStoreBuffered defer:NO];
    w.releasedWhenClosed = NO; w.title = string(title); w.delegate = delegate; [w center];
    return registerObject(w, 0);
} }
void minyar_macos_show(long long handle) { @autoreleasepool {
    NSWindow *w = object(handle, NSWindow.class); [w makeKeyAndOrderFront:nil]; [NSApp activateIgnoringOtherApps:YES];
} }
void minyar_macos_close(long long handle) { @autoreleasepool { [object(handle, NSWindow.class) close]; } }
void minyar_macos_destroy(long long handle) { @autoreleasepool {
    NSWindow *w = object(handle, NSWindow.class); w.delegate = nil; [w close];
    for (NSNumber *key in handles.allKeys) if (handles[key].owner == handle) [handles removeObjectForKey:key];
    [handles removeObjectForKey:@(handle)];
    // No future events may refer to destroyed objects. The current event remains a snapshot.
    NSIndexSet *stale = [events indexesOfObjectsPassingTest:^BOOL(MNEvent *e, NSUInteger i, BOOL *stop) {
        (void)i; (void)stop; return e.source != 0 && handles[@(e.source)] == nil;
    }];
    [events removeObjectsAtIndexes:stale];
} }
static long long stack(long long parent, long long spacing, NSUserInterfaceLayoutOrientation orientation) {
    ready(); dimension(spacing); NSStackView *s = [NSStackView new]; s.orientation = orientation; s.spacing = spacing;
    s.alignment = orientation == NSUserInterfaceLayoutOrientationVertical ? NSLayoutAttributeLeading : NSLayoutAttributeCenterY;
    s.detachesHiddenViews = YES;
    return append(parent, s);
}
long long minyar_macos_column(long long parent, long long spacing) { @autoreleasepool { return stack(parent, spacing, NSUserInterfaceLayoutOrientationVertical); } }
long long minyar_macos_row(long long parent, long long spacing) { @autoreleasepool { return stack(parent, spacing, NSUserInterfaceLayoutOrientationHorizontal); } }
void minyar_macos_padding(long long handle, long long points) { @autoreleasepool {
    NSStackView *s = object(handle, NSStackView.class); dimension(points); s.edgeInsets = NSEdgeInsetsMake(points,points,points,points);
} }
long long minyar_macos_label(long long parent, const MinyarText *text) { @autoreleasepool {
    ready(); NSTextField *v = [NSTextField labelWithString:string(text)]; v.selectable = YES; return append(parent,v);
} }
long long minyar_macos_button(long long parent, const MinyarText *title) { @autoreleasepool {
    ready(); return append(parent, [NSButton buttonWithTitle:string(title) target:delegate action:@selector(action:)]);
} }
long long minyar_macos_checkbox(long long parent, const MinyarText *title, bool checked) { @autoreleasepool {
    ready(); NSButton *b = [NSButton checkboxWithTitle:string(title) target:delegate action:@selector(action:)];
    b.state = checked ? NSControlStateValueOn : NSControlStateValueOff;
    long long h = append(parent,b); entry(h).isCheckbox = YES; return h;
} }
long long minyar_macos_textField(long long parent, const MinyarText *text) { @autoreleasepool {
    ready(); NSTextField *v = [NSTextField textFieldWithString:string(text)]; v.delegate = delegate;
    [v.widthAnchor constraintGreaterThanOrEqualToConstant:160].active = YES; return append(parent,v);
} }
long long minyar_macos_textEditor(long long parent, const MinyarText *text) { @autoreleasepool {
    ready(); NSScrollView *scroll = [NSScrollView new]; scroll.hasVerticalScroller = YES; scroll.borderType = NSBezelBorder;
    NSTextView *v = [[NSTextView alloc] initWithFrame:NSMakeRect(0,0,320,180)];
    v.richText = NO; v.allowsUndo = YES; v.verticallyResizable = YES; v.horizontallyResizable = NO;
    v.autoresizingMask = NSViewWidthSizable; v.textContainer.widthTracksTextView = YES;
    v.minSize = NSMakeSize(0,0); v.maxSize = NSMakeSize(100000,100000);
    v.string = string(text); v.delegate = delegate; scroll.documentView = v;
    [scroll.widthAnchor constraintGreaterThanOrEqualToConstant:200].active = YES;
    [scroll.heightAnchor constraintGreaterThanOrEqualToConstant:100].active = YES;
    return append(parent,scroll);
} }
long long minyar_macos_slider(long long parent, double minimum, double maximum, double value) { @autoreleasepool {
    ready();
    if (!isfinite(minimum) || !isfinite(maximum) || !isfinite(value) || minimum >= maximum || value < minimum || value > maximum)
        minyar_native_stop("macos slider requires a finite increasing range and a value within it.");
    NSSlider *s = [NSSlider sliderWithValue:value minValue:minimum maxValue:maximum target:delegate action:@selector(action:)];
    s.continuous = YES; return append(parent,s);
} }
long long minyar_macos_separator(long long parent) { @autoreleasepool {
    ready(); NSBox *b = [NSBox new]; b.boxType = NSBoxSeparator; return append(parent,b);
} }
void minyar_macos_size(long long handle, long long width, long long height) { @autoreleasepool {
    NSView *v = object(handle, NSView.class); dimension(width); dimension(height); MNHandle *h = entry(handle);
    h.width.active = NO; h.height.active = NO; h.width = nil; h.height = nil;
    if (width) { h.width = [v.widthAnchor constraintEqualToConstant:width]; h.width.active = YES; }
    if (height) { h.height = [v.heightAnchor constraintEqualToConstant:height]; h.height.active = YES; }
} }
MinyarText *minyar_macos_text(long long handle) { @autoreleasepool { return owned(getText(entry(handle).object)); } }
void minyar_macos_setText(long long handle, const MinyarText *text) { @autoreleasepool {
    id v = entry(handle).object; NSString *s = string(text);
    if (editor(v)) { editor(v).string = s; return; }
    if ([v isKindOfClass:NSTextField.class]) { [v setStringValue:s]; return; }
    if ([v isKindOfClass:NSWindow.class] || [v isKindOfClass:NSButton.class] || [v isKindOfClass:NSMenuItem.class]) { [v setTitle:s]; return; }
    minyar_native_stop("macos.setText requires a window, text control, button, or menu item.");
} }
void minyar_macos_enabled(long long handle, bool value) { @autoreleasepool {
    id v = entry(handle).object;
    if (![v isKindOfClass:NSControl.class] && ![v isKindOfClass:NSMenuItem.class]) minyar_native_stop("macos.enabled requires a control or menu item.");
    [v setEnabled:value];
} }
static NSButton *checkbox(long long handle) {
    NSButton *b = object(handle,NSButton.class);
    if (!entry(handle).isCheckbox) minyar_native_stop("macos checkbox operation requires a checkbox.");
    return b;
}
bool minyar_macos_checked(long long handle) { @autoreleasepool { return checkbox(handle).state == NSControlStateValueOn; } }
void minyar_macos_setChecked(long long handle, bool value) { @autoreleasepool { checkbox(handle).state = value ? NSControlStateValueOn : NSControlStateValueOff; } }
double minyar_macos_value(long long handle) { @autoreleasepool { return [object(handle,NSSlider.class) doubleValue]; } }
void minyar_macos_setValue(long long handle, double value) { @autoreleasepool {
    NSSlider *s = object(handle,NSSlider.class);
    if (!isfinite(value) || value < s.minValue || value > s.maxValue) minyar_native_stop("macos slider value is outside its range.");
    s.doubleValue = value;
} }
long long minyar_macos_width(long long handle) { @autoreleasepool { NSWindow *w = object(handle,NSWindow.class); return (long long)w.contentView.bounds.size.width; } }
long long minyar_macos_height(long long handle) { @autoreleasepool { NSWindow *w = object(handle,NSWindow.class); return (long long)w.contentView.bounds.size.height; } }
long long minyar_macos_menu(const MinyarText *title) { @autoreleasepool {
    ready(); NSMenu *m = [[NSMenu alloc] initWithTitle:string(title)]; m.autoenablesItems = NO;
    NSMenuItem *item = [[NSMenuItem alloc] initWithTitle:string(title) action:NULL keyEquivalent:@""];
    item.submenu = m; [NSApp.mainMenu addItem:item]; return registerObject(m,0);
} }
long long minyar_macos_menuItem(long long menu, const MinyarText *title, const MinyarText *key) { @autoreleasepool {
    NSMenu *m = object(menu,NSMenu.class);
    NSMenuItem *item = [[NSMenuItem alloc] initWithTitle:string(title) action:@selector(action:) keyEquivalent:string(key)];
    item.target = delegate; [m addItem:item]; return registerObject(item,0);
} }
bool minyar_macos_nextEvent(double timeout) { @autoreleasepool {
    ready(); if (!isfinite(timeout) || timeout < 0 || timeout > 60) minyar_native_stop("macos event timeout must be between 0 and 60 seconds.");
    current = nil;
    NSDate *deadline = [NSDate dateWithTimeIntervalSinceNow:timeout];
    // Always pump at least one native event, even while Minyar events are pending.
    // This keeps menus, window drawing and text input responsive under load.
    do {
        NSEvent *e = [NSApp nextEventMatchingMask:NSEventMaskAny untilDate:(events.count || quitting ? NSDate.distantPast : deadline) inMode:NSDefaultRunLoopMode dequeue:YES];
        if (e) [NSApp sendEvent:e];
        [NSApp updateWindows];
        if (!e) break;
    } while (!events.count && !quitting && deadline.timeIntervalSinceNow > 0);
    if (events.count) { current = events.firstObject; [events removeObjectAtIndex:0]; return true; }
    return !quitting;
} }
long long minyar_macos_eventType(void) { @autoreleasepool { ready(); return current ? current.kind : MNNone; } }
long long minyar_macos_eventSource(void) { @autoreleasepool { ready(); return current ? current.source : 0; } }
MinyarText *minyar_macos_eventText(void) { @autoreleasepool { ready(); return owned(current.text); } }
void minyar_macos_quit(void) { @autoreleasepool { ready(); requestQuit(); } }
MinyarText *minyar_macos_clipboardText(void) { @autoreleasepool { ready(); return owned([NSPasteboard.generalPasteboard stringForType:NSPasteboardTypeString]); } }
void minyar_macos_setClipboardText(const MinyarText *text) { @autoreleasepool {
    ready(); [NSPasteboard.generalPasteboard clearContents];
    if (![NSPasteboard.generalPasteboard setString:string(text) forType:NSPasteboardTypeString]) minyar_native_stop("macos could not write the clipboard.");
} }
MinyarText *minyar_macos_openFile(const MinyarText *title) { @autoreleasepool {
    ready(); NSOpenPanel *panel = [NSOpenPanel openPanel]; panel.title = string(title);
    panel.canChooseFiles = YES; panel.canChooseDirectories = NO; panel.allowsMultipleSelection = NO;
    return owned([panel runModal] == NSModalResponseOK ? panel.URL.path : @"");
} }
MinyarText *minyar_macos_saveFile(const MinyarText *title, const MinyarText *name) { @autoreleasepool {
    ready(); NSSavePanel *panel = [NSSavePanel savePanel]; panel.title = string(title); panel.nameFieldStringValue = string(name);
    return owned([panel runModal] == NSModalResponseOK ? panel.URL.path : @"");
} }
bool minyar_macos_alert(const MinyarText *title, const MinyarText *message) { @autoreleasepool {
    ready(); NSAlert *a = [NSAlert new]; a.messageText = string(title); a.informativeText = string(message);
    [a addButtonWithTitle:@"OK"]; [a addButtonWithTitle:@"Cancel"]; return [a runModal] == NSAlertFirstButtonReturn;
} }
