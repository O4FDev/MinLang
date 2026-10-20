/* Test user events through AppKit's real target/action and text-field delegate. */
#import <AppKit/AppKit.h>
#include "../runtime/minyar_native.h"

static NSString *text(MinyarText *value) {
    NSString *result = [[NSString alloc] initWithBytes:value->bytes length:(NSUInteger)value->byte_length encoding:NSUTF8StringEncoding];
#if __has_feature(objc_arc)
    return result;
#else
    return [result autorelease];
#endif
}
static NSView *find(NSView *view, Class kind, NSString *value) {
    if ([view isKindOfClass:kind]) {
        NSString *current = [view isKindOfClass:NSButton.class] ? [(NSButton *)view title] : [(NSTextField *)view stringValue];
        if ([current isEqualToString:value]) return view;
    }
    for (NSView *child in view.subviews) {
        NSView *match = find(child, kind, value);
        if (match) return match;
    }
    return nil;
}
static NSView *control(Class kind, NSString *value) {
    for (NSWindow *window in NSApp.windows) {
        NSView *match = find(window.contentView, kind, value);
        if (match) return match;
    }
    minyar_native_stop("declarative UI test could not find its control.");
    return nil;
}
void minyar_uitest_click(MinyarText *title) { @autoreleasepool {
    [(NSButton *)control(NSButton.class, text(title)) performClick:nil];
} }
void minyar_uitest_edit(MinyarText *previous, MinyarText *value) { @autoreleasepool {
    NSTextField *field = (NSTextField *)control(NSTextField.class, text(previous));
    field.stringValue = text(value);
    [field.delegate controlTextDidChange:[NSNotification notificationWithName:NSControlTextDidChangeNotification object:field]];
} }
void minyar_uitest_select(MinyarText *value) { @autoreleasepool {
    NSTextField *field = (NSTextField *)control(NSTextField.class, text(value));
    [field.window makeFirstResponder:field];
    [(NSTextView *)field.currentEditor setSelectedRange:NSMakeRange(1, 2)];
} }
_Bool minyar_uitest_selectionKept(MinyarText *value) { @autoreleasepool {
    NSTextField *field = (NSTextField *)control(NSTextField.class, text(value));
    NSTextView *editor = (NSTextView *)field.currentEditor;
    return editor && field.window.firstResponder == editor && NSEqualRanges(editor.selectedRange, NSMakeRange(1, 2));
} }
long long minyar_uitest_stackSpacing(MinyarText *value) { @autoreleasepool {
    NSView *parent = control(NSTextField.class, text(value)).superview;
    while (parent && ![parent isKindOfClass:NSStackView.class]) parent = parent.superview;
    if (!parent) minyar_native_stop("declarative UI test could not find the editor's stack.");
    return (long long)[(NSStackView *)parent spacing];
} }
