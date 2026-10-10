/* Exercise actual AppKit target/action and delegate delivery without UI scripting.
 * Importing the bridge gives this test access to native objects; Minyar callers
 * get only the checked API. Link against the real Minyar runtime. */
#include "../runtime/native/macos.m"
#include <assert.h>
#include <objc/runtime.h>
#include <ApplicationServices/ApplicationServices.h>
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
/* Handle everything already queued. */
static void drain(void) {
    while (minyar_macos_nextEvent(0) && minyar_macos_eventType() != MNNone) {}
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
/* Layout, styling and input behavior added for full applications. */
static void verifyApplicationViews(void) {
    MinyarText title = literal("Views"), empty = literal(""), plus = literal("plus"), system = literal("");
    MinyarText mark = literal("M 50,8 Q 70,58 98,92 L 50,64 L 2,92 Q 30,58 50,8 Z"), long_text = literal("abcdefgh");
    long long w = minyar_macos_window(&title,600,400);
    minyar_macos_transparentTitlebar(w,52);
    long long root = minyar_macos_column(w,0);
    long long header = minyar_macos_row(root,0); minyar_macos_draggable(header); minyar_macos_fill(header); minyar_macos_size(header,0,52);
    minyar_macos_spacer(header);
    long long scroll = minyar_macos_scroll(root); minyar_macos_fill(scroll); minyar_macos_grow(scroll);
    minyar_macos_align(scroll,MNCenter);
    long long page = minyar_macos_column(scroll,4); minyar_macos_fill(page); minyar_macos_maximumSize(page,300,0);
    minyar_macos_gravity(page,MNCenter);
    long long label = minyar_macos_label(page,&title); minyar_macos_lines(label,0); minyar_macos_fill(label);
    long long color = minyar_macos_color(0x111111,0xeeeeee,1);
    minyar_macos_background(page,color); minyar_macos_border(page,1,color); minyar_macos_cornerRadius(page,4);
    minyar_macos_font(label,&system,14,500); minyar_macos_textColor(label,color);
    minyar_macos_lineHeight(label,1.5); minyar_macos_letterSpacing(label,0.5);
    long long button = minyar_macos_plainButton(page,&title); minyar_macos_symbol(button,&plus,12);
    minyar_macos_hover(button,color,color); minyar_macos_insets(button,4,8,4,8);
    long long shape = minyar_macos_shape(page,&mark,100,100); minyar_macos_size(shape,20,20);
    long long row = minyar_macos_row(page,0); minyar_macos_clickable(row); minyar_macos_label(row,&title);
    long long notes = minyar_macos_textEditor(root,&empty); minyar_macos_plain(notes); minyar_macos_fill(notes);
    minyar_macos_autoHeight(notes,40,120); minyar_macos_submitOnEnter(notes); minyar_macos_maxLength(notes,5);
    long long field = minyar_macos_textField(root,&empty); minyar_macos_placeholder(field,&title);
    minyar_macos_show(w);
    NSWindow *window = object(w,NSWindow.class); [window layoutIfNeeded];
    // Content never pulls the window to its own fitting size, and capped views stay capped.
    assert(minyar_macos_width(w) == 600);
    assert(NSWidth([object(page,NSView.class) frame]) == 300);
    assert(NSHeight([object(notes,NSView.class) frame]) == 40);
    NSTextView *text = editor(entry(notes).object);
    [text insertText:@"abcdefgh" replacementRange:NSMakeRange(0,0)];
    assert(text.string.length == 5);
    [text.delegate textView:text doCommandBySelector:@selector(insertNewline:)];
    assert(receive(MNSubmit,notes)); equals(minyar_macos_eventText(),"abcde");
    minyar_macos_setText(notes,&long_text); equals(minyar_macos_text(notes),"abcdefgh");
    NSTextField *input = object(field,NSTextField.class); [input sendAction:input.action to:input.target];
    assert(receive(MNSubmit,field));
    assert([object(row,NSView.class) accessibilityPerformPress]); assert(receive(MNAction,row));
    minyar_macos_enabled(row,false); assert(![object(row,NSView.class) accessibilityPerformPress]);
    minyar_macos_appearance(2); assert(!minyar_macos_isDark());
    minyar_macos_appearance(1); assert(minyar_macos_isDark());
    minyar_macos_appearance(0);
    // Clearing a container ends its descendants' handles but not its own.
    minyar_macos_clear(page);
    assert(handles[@(label)] == nil && handles[@(button)] == nil && handles[@(row)] == nil && handles[@(page)] != nil);
    minyar_macos_remove(page); assert(handles[@(page)] == nil);
    window = nil; text = nil; input = nil;
    minyar_macos_destroy(w);
    assert(handles[@(color)] != nil);
}
/* Lists keep rows as text and build views only for visible rows. */
static void verifyList(void) {
    MinyarText title = literal("List"), date = literal("10 Oct"), prompt = literal("Where is the Atacama?"), preview = literal("Chile"),
        empty = literal(""), trash = literal("trash"), remove = literal("Delete"), system = literal("");
    long long w = minyar_macos_window(&title,400,300);
    long long root = minyar_macos_column(w,0);
    long long l = minyar_macos_list(root); minyar_macos_fill(l); minyar_macos_grow(l);
    long long color = minyar_macos_color(0x222222,0xdddddd,1);
    minyar_macos_listLine(l,1,&system,14,450,color,0); minyar_macos_listColors(l,color,color);
    minyar_macos_rowButton(l,&trash,&remove,color); minyar_macos_insets(l,18,0,18,0);
    for (int i = 0; i < 5000; ++i) minyar_macos_addRow(l,&date,&prompt,i == 1 ? &empty : &preview);
    assert(minyar_macos_rowCount(l) == 5000 && minyar_macos_clickedRow(l) == -1);
    NSTableView *table = list(l).table;
    // The table sees rows only when nextEvent reloads it, never half-built ones.
    assert(table.numberOfRows == 0);
    minyar_macos_show(w);
    drain();
    assert(table.numberOfRows == 5000);
    // Only rows on screen have views.
    __block NSInteger realized = 0;
    [table enumerateAvailableRowViewsUsingBlock:^(NSTableRowView *view, NSInteger row) { (void)view; (void)row; ++realized; }];
    assert(realized > 0 && realized < 100);
    MNListCell *cell = [table viewAtColumn:0 row:1 makeIfNecessary:YES];
    MNListCell *other = [table viewAtColumn:0 row:3 makeIfNecessary:YES];
    assert([cell.top.stringValue isEqualToString:@"10 Oct"] && [cell.middle.stringValue isEqualToString:@"Where is the Atacama?"]);
    assert(cell.bottom.hidden && !cell.button.hidden && cell.buttonEdge.active && !cell.textEdge.active);
    assert(cell.topEdge.constant == 18 && cell.leadingEdge.constant == 0 && cell.buttonEdge.constant == 0);
    assert([cell.button.toolTip isEqualToString:@"Delete Where is the Atacama?"]);
    // Clicks queued before the program looks each keep their own row.
    [cell.button performClick:nil]; [other.button performClick:nil];
    assert(receive(MNAction,l)); assert(minyar_macos_clickedRow(l) == 1 && minyar_macos_clickedButton(l));
    assert(receive(MNAction,l)); assert(minyar_macos_clickedRow(l) == 3 && minyar_macos_clickedButton(l));
    // A disabled list delivers no clicks.
    minyar_macos_enabled(l,false); [cell.button performClick:nil];
    assert(!receive(MNAction,l)); minyar_macos_enabled(l,true);
    // clear ends the rows and any clicks on them that are still queued.
    [cell.button performClick:nil];
    minyar_macos_clear(l); assert(minyar_macos_rowCount(l) == 0);
    assert(!receive(MNAction,l)); assert(minyar_macos_clickedRow(l) == -1);
    assert(table.numberOfRows == 0);
    // Without a row button the text runs to the inset.
    minyar_macos_rowButton(l,&empty,&empty,0); minyar_macos_addRow(l,&date,&prompt,&preview);
    drain();
    cell = [table viewAtColumn:0 row:0 makeIfNecessary:YES];
    assert(cell.button.hidden && !cell.buttonEdge.active && cell.textEdge.active);
    table = nil; cell = nil; other = nil;
    minyar_macos_destroy(w);
}
/* A textView grows by appending: each append edits only the new characters,
 * keeps the layout of the text before it, and keeps the selection. */
static void verifyTextView(void) {
    MinyarText title = literal("Text view"), start = literal("é 🙂 "), word = literal("plateau "), empty = literal(""),
        system = literal(""), shorter = literal("short");
    long long w = minyar_macos_window(&title,500,400);
    long long root = minyar_macos_column(w,0);
    long long scroll = minyar_macos_scroll(root); minyar_macos_fill(scroll); minyar_macos_grow(scroll);
    long long page = minyar_macos_column(scroll,0); minyar_macos_fill(page);
    long long t = minyar_macos_textView(page,&start); minyar_macos_fill(t);
    minyar_macos_font(t,&system,16,400); minyar_macos_lineHeight(t,1.5);
    minyar_macos_textColor(t,minyar_macos_color(0x111111,0xeeeeee,1));
    minyar_macos_show(w);
    drain();
    MNTextBlock *view = entry(t).object;
    NSWindow *window = view.window; [window layoutIfNeeded];
    CGFloat oneLine = NSHeight(view.frame);
    assert(oneLine >= 24 && oneLine < 48 && view.isSelectable && !view.isEditable);
    // Record every edit the text storage processes.
    __block NSRange edited = NSMakeRange(NSNotFound, 0);
    __block NSInteger edits = 0, change = 0;
    id observer = [NSNotificationCenter.defaultCenter addObserverForName:NSTextStorageDidProcessEditingNotification
        object:view.textStorage queue:nil usingBlock:^(NSNotification *note) {
            NSTextStorage *storage = note.object; ++edits; edited = storage.editedRange; change = storage.changeInLength;
        }];
    NSMutableString *expected = [NSMutableString stringWithString:@"é 🙂 "];
    view.selectedRange = NSMakeRange(0,1);
    for (int i = 0; i < 2000; ++i) {
        NSUInteger before = view.textStorage.length;
        minyar_macos_appendText(t,&word); [expected appendString:@"plateau "];
        // Exactly one edit, of the appended characters only.
        assert(edits == i + 1 && edited.location == before && edited.length == 8 && change == 8);
        if (i % 500 == 499) {
            [window layoutIfNeeded];
            NSLayoutManager *layout = view.layoutManager;
            NSUInteger laid = layout.firstUnlaidCharacterIndex;
            minyar_macos_appendText(t,&word); [expected appendString:@"plateau "]; ++i;
            // Text laid out before the append keeps its layout (a replaced
            // string would start again from 0), except the last line.
            assert(laid == view.textStorage.length - 8 && layout.firstUnlaidCharacterIndex > laid / 2);
        }
    }
    [NSNotificationCenter.defaultCenter removeObserver:observer];
    MinyarText *content = minyar_macos_text(t);
    equals(content, expected.UTF8String);
    assert(NSEqualRanges(view.selectedRange, NSMakeRange(0,1)));
    // The text offers nothing to spell checking and correction, which would
    // otherwise copy the paragraph around the selection after every append.
    NSRange checked;
    assert(![(id<NSTextCheckingClient>)view annotatedSubstringForProposedRange:NSMakeRange(0,view.textStorage.length) actualRange:&checked]);
    // A selection copies as plain text (a private pasteboard leaves the clipboard alone).
    NSPasteboard *board = [NSPasteboard pasteboardWithUniqueName];
    view.selectedRange = NSMakeRange(0,4);
    assert([view writeSelectionToPasteboard:board types:view.writablePasteboardTypes]);
    assert([[board stringForType:NSPasteboardTypeString] isEqualToString:@"é 🙂"]);
    [board releaseGlobally];
    // The view grows to fit its text, inside the scroll view.
    [window layoutIfNeeded];
    CGFloat tall = NSHeight(view.frame);
    assert(tall > 100 * oneLine && fabs(tall - view.intrinsicContentSize.height) < 1);
    // Fonts and other attributes apply to appended text too.
    NSDictionary *a = [view.textStorage attributesAtIndex:view.textStorage.length - 1 effectiveRange:NULL];
    assert([a[NSFontAttributeName] pointSize] == 16 && [a[NSParagraphStyleAttributeName] minimumLineHeight] == 24);
    // A narrower window rewraps it taller.
    [window setContentSize:NSMakeSize(300,400)]; [window layoutIfNeeded];
    assert(NSHeight(view.frame) > tall * 1.3);
    // setText replaces everything; empty appends change nothing.
    minyar_macos_setText(t,&shorter); minyar_macos_appendText(t,&empty);
    equals(minyar_macos_text(t),"short");
    [window layoutIfNeeded]; assert(NSHeight(view.frame) == oneLine);
    minyar_macos_appendText(t,&start); equals(minyar_macos_text(t),"shorté 🙂 ");
    minyar_macos_selectable(t,false); assert(!view.isSelectable);
    // Alignment survives restyling and applies to appended text.
    minyar_macos_textAlign(t,MNCenter); minyar_macos_lineHeight(t,1.6); minyar_macos_appendText(t,&word);
    a = [view.textStorage attributesAtIndex:view.textStorage.length - 1 effectiveRange:NULL];
    assert([a[NSParagraphStyleAttributeName] alignment] == NSTextAlignmentCenter);
    // Editors append too.
    long long notes = minyar_macos_textEditor(root,&start);
    minyar_macos_appendText(notes,&word); equals(minyar_macos_text(notes),"é 🙂 plateau ");
    view = nil; window = nil;
    minyar_macos_destroy(w);
}
/* A button pushed down by growing text is not drawn again for the area it
 * left, but is still drawn when it changes. */
static int buttonDraws;
static IMP drawButton;
static void countButtonDraws(id self, SEL _cmd, NSRect frame, NSView *view) {
    ++buttonDraws; ((void (*)(id, SEL, NSRect, NSView *))drawButton)(self, _cmd, frame, view);
}
static void verifyMovingButton(void) {
    MinyarText title = literal("Moving button"), copy = literal("Copy"), copied = literal("Copied"), symbol = literal("doc.on.doc"),
        line = literal("plateau in south america covering ");
    Method draw = class_getInstanceMethod(NSButtonCell.class, @selector(drawWithFrame:inView:));
    drawButton = method_getImplementation(draw);
    class_replaceMethod(MNButtonCell.class, @selector(drawWithFrame:inView:), (IMP)countButtonDraws, method_getTypeEncoding(draw));
    long long w = minyar_macos_window(&title,500,400);
    long long root = minyar_macos_column(w,0);
    long long scroll = minyar_macos_scroll(root); minyar_macos_fill(scroll); minyar_macos_grow(scroll);
    long long page = minyar_macos_column(scroll,0); minyar_macos_fill(page);
    long long t = minyar_macos_textView(page,&line); minyar_macos_fill(t);
    long long b = minyar_macos_plainButton(page,&copy); minyar_macos_symbol(b,&symbol,12);
    minyar_macos_show(w);
    drain();
    NSView *button = entry(b).object;
    CGFloat top = NSMinY([button convertRect:button.bounds toView:nil]);
    buttonDraws = 0;
    for (int i = 0; i < 40; ++i) { minyar_macos_appendText(t,&line); for (int k = 0; k < 3; ++k) minyar_macos_nextEvent(0.005); }
    [button.window layoutIfNeeded];
    assert(fabs(NSMinY([button convertRect:button.bounds toView:nil]) - top) > 100);
    assert(buttonDraws == 0);
    minyar_macos_setText(b,&copied); drain(); [button.window displayIfNeeded];
    assert(buttonDraws > 0);
    button = nil;
    minyar_macos_destroy(w);
}
/* Background progress (as from http) wakes nextEvent at most once a frame. */
static void verifyWakeThrottle(void) {
    drain();
    dispatch_semaphore_t posted = dispatch_semaphore_create(0);
    __block double sending = 0;
    [NSThread detachNewThreadWithBlock:^{
        double start = CACurrentMediaTime();
        for (int i = 0; i < 200; ++i) {
            [NSApp postEvent:[NSEvent otherEventWithType:NSEventTypeApplicationDefined location:NSZeroPoint modifierFlags:0
                timestamp:0 windowNumber:0 context:nil subtype:MNWakeSubtype data1:0 data2:0] atStart:NO];
            [NSThread sleepForTimeInterval:0.001];
        }
        sending = CACurrentMediaTime() - start;
        dispatch_semaphore_signal(posted);
    }];
    int returns = 0;
    while (dispatch_semaphore_wait(posted, DISPATCH_TIME_NOW)) {
        assert(minyar_macos_nextEvent(0.05));
        ++returns;
    }
    drain();
    // At most one return a frame while the wake-ups arrive (plus 0.05 s
    // timeouts, and slack); unthrottled this would be near 200.
    assert(returns >= 1 && returns <= (int)(sending * 60) + 10);
    assert(returns < 150);
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
    if (argc > 1 && !strcmp(argv[1],"hover")) { long long v = minyar_macos_window(&title,100,100); minyar_macos_hover(minyar_macos_label(minyar_macos_column(v,0),&title),0,0); return 99; }
    if (argc > 1 && !strcmp(argv[1],"shape")) { MinyarText bad = literal("M 1 2 X"); long long v = minyar_macos_window(&title,100,100); minyar_macos_shape(minyar_macos_column(v,0),&bad,10,10); return 99; }
    if (argc > 1 && !strcmp(argv[1],"color")) { minyar_macos_color(0x1000000,0,1); return 99; }
    verifyApplicationViews();
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
        if (!strcmp(argv[1],"list-line")) minyar_macos_listLine(minyar_macos_list(root),3,&empty,12,400,0,1);
        if (!strcmp(argv[1],"list-type")) minyar_macos_addRow(button,&title,&title,&title);
        if (!strcmp(argv[1],"append-type")) minyar_macos_appendText(minyar_macos_label(root,&title),&title);
        return 99;
    }
    verifyList();
    verifyTextView();
    verifyMovingButton();
    verifyWakeThrottle();
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
    // An accessibility action (as from VoiceOver) arrives while nextEvent
    // waits for input; it must end the wait at once rather than at the timeout.
    // Needs the test to be trusted for accessibility, as automation tools are.
    if (AXIsProcessTrusted()) {
        drain();
        NSButton *pressed = object(button,NSButton.class);
        NSRect frame = [pressed.window convertRectToScreen:[pressed convertRect:pressed.bounds toView:nil]];
        CGPoint point = CGPointMake(NSMidX(frame), NSHeight(NSScreen.screens.firstObject.frame) - NSMidY(frame));
        pid_t self = getpid();
        [NSThread detachNewThreadWithBlock:^{
            [NSThread sleepForTimeInterval:0.2];
            AXUIElementRef application = AXUIElementCreateApplication(self), element = NULL;
            if (AXUIElementCopyElementAtPosition(application, point.x, point.y, &element) == kAXErrorSuccess) {
                AXUIElementPerformAction(element, kAXPressAction);
                CFRelease(element);
            }
            CFRelease(application);
        }];
        double waited = CACurrentMediaTime();
        assert(minyar_macos_nextEvent(10));
        assert(minyar_macos_eventType() == MNAction && minyar_macos_eventSource() == button);
        assert(CACurrentMediaTime() - waited < 3);
        pressed = nil;
    }
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
    assert(handles.count == 5); // Only the application-scoped menu, item and three colors remain.
    puts("native AppKit actions, delegates, Unicode, windows, menus and lifecycle verified");
    return 0;
} }
