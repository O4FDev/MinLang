/* Swift's AppKit calls lower to these same Objective-C classes/selectors.
 * Compile with ARC. Only scalar values and borrowed/owned Minyar Text cross
 * the C ABI; no Objective-C pointers or Swift ABI types escape this file. */
#import <AppKit/AppKit.h>
#import <CoreText/CoreText.h>
#include <math.h>
#include <limits.h>
#include "../minyar_native.h"

enum { MNNone, MNAction, MNChange, MNClosed, MNResized, MNQuit, MNSubmit };
enum { MNStart = 1, MNCenter = 2, MNEnd = 3 };
/* Other native packages (such as http) post an application-defined event with
 * this subtype when background work progresses, ending a nextEvent wait early. */
enum { MNWakeSubtype = 0x4D59 };
/* Background wake-ups end a nextEvent wait at most this often (60 Hz). */
static const NSTimeInterval MNWakeInterval = 1.0 / 60;
static NSTimeInterval lastWake;

@interface MNHandle : NSObject
@property(nonatomic, strong) id object;
@property(nonatomic) long long owner;
@property(nonatomic) BOOL isCheckbox;
@property(nonatomic, strong) NSLayoutConstraint *width;
@property(nonatomic, strong) NSLayoutConstraint *height;
// Text controls start with minimum sizes; minimumSize and plain replace them.
@property(nonatomic, strong) NSLayoutConstraint *minimumWidth, *minimumHeight, *maximumWidth, *maximumHeight;
@property(nonatomic, strong) NSArray<NSLayoutConstraint *> *fillConstraints;
@property(nonatomic) BOOL fills;
// Colors are dynamic NSColors, resolved for the appearance each time a view is styled.
@property(nonatomic, strong) NSColor *background, *borderColor, *foreground, *hoverBackground, *hoverForeground, *focusBorder;
@property(nonatomic) CGFloat borderWidth, radius, kerning, lineHeight;
@property(nonatomic, strong) NSFont *font;
@property(nonatomic) long long lines;
@property(nonatomic) BOOL styledText, hovering, focused, submitOnEnter;
@property(nonatomic) long long maxLength;
@property(nonatomic) CGFloat autoMinimum, autoMaximum, titlebarHeight;
@end
@implementation MNHandle
- (instancetype)init { if ((self = [super init])) _lines = -1; return self; }
@end
@interface MNEvent : NSObject
@property(nonatomic) long long kind, source, row;
@property(nonatomic) BOOL button;
@property(nonatomic, copy) NSString *text;
@end
@implementation MNEvent
@end
@interface MNDelegate : NSObject <NSApplicationDelegate, NSWindowDelegate, NSTextFieldDelegate, NSTextViewDelegate, NSStackViewDelegate>
- (void)action:(id)sender;
- (void)submit:(id)sender;
- (void)requestQuit:(id)sender;
- (void)showAbout:(id)sender;
@end
static NSMutableDictionary<NSNumber *, MNHandle *> *handles;
static NSMapTable<id, NSNumber *> *numbers;
static NSMutableArray<MNEvent *> *events;
static MNEvent *current;
static MNDelegate *delegate;
static long long nextHandle = 1;
static BOOL quitting, waiting;
static NSString *aboutCredits;

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
    [numbers setObject:@(result) forKey:value];
    return result;
}
static long long identifier(id value) {
    return value ? [numbers objectForKey:value].longLongValue : 0;
}
static MNHandle *handleFor(id value) {
    long long number = identifier(value);
    return number ? handles[@(number)] : nil;
}
/* Events can also arrive while nextEvent waits for input, from accessibility
 * actions, notifications and timers. A posted event ends that wait at once. */
static void wakeLoop(void) {
    if (!waiting) return;
    waiting = NO;
    [NSApp postEvent:[NSEvent otherEventWithType:NSEventTypeApplicationDefined location:NSZeroPoint modifierFlags:0
        timestamp:0 windowNumber:0 context:nil subtype:MNWakeSubtype data1:0 data2:0] atStart:NO];
}
static void enqueue(long long kind, long long source, NSString *text) {
    wakeLoop();
    // Repeated edits/resizes of the same source need only the latest snapshot.
    MNEvent *last = events.lastObject;
    if ((kind == MNChange || kind == MNResized) && last.kind == kind && last.source == source) {
        last.text = text ?: @""; return;
    }
    if (events.count >= 4096) minyar_native_stop("macos event queue is full; consume events with nextEvent.");
    MNEvent *e = [MNEvent new]; e.kind = kind; e.source = source; e.text = text ?: @""; e.row = -1;
    [events addObject:e];
}
/* A click on a list row, or on its button. */
static void enqueueRow(long long source, long long row, BOOL button) {
    enqueue(MNAction, source, @"");
    MNEvent *e = events.lastObject; e.row = row; e.button = button;
}
/* Drop queued events that match, such as those from objects that just ended. */
static void dropEvents(BOOL (^matches)(MNEvent *e)) {
    [events removeObjectsAtIndexes:[events indexesOfObjectsPassingTest:^BOOL(MNEvent *e, NSUInteger i, BOOL *stop) {
        (void)i; (void)stop; return matches(e);
    }]];
}
static void requestQuit(void) {
    if (!quitting) { quitting = YES; enqueue(MNQuit, 0, @""); }
}
static NSTextView *editor(id value) {
    return [value isKindOfClass:NSScrollView.class] && [[value documentView] isKindOfClass:NSTextView.class] ? [value documentView] : nil;
}
/* Read-only text that wraps to its width and is as tall as its text. Its
 * TextKit 1 layout manager keeps the layout of text that did not change, so
 * appendText lays out only the new end; a label measures and typesets all of
 * its text again after every change. */
@interface MNTextBlock : NSTextView
// A text view made from its own container does not own the text storage.
@property(nonatomic, strong) NSTextStorage *storage;
@end
/* The text view of an editor or a textView, or nil. */
static NSTextView *textView(id value) {
    return [value isKindOfClass:MNTextBlock.class] ? value : editor(value);
}
static NSString *getText(id value) {
    if (textView(value)) return textView(value).string;
    if ([value isKindOfClass:NSTextField.class]) return [value stringValue];
    if ([value isKindOfClass:NSWindow.class] || [value isKindOfClass:NSButton.class] || [value isKindOfClass:NSMenuItem.class]) return [value title];
    minyar_native_stop("macos.text requires a window, text control, button, or menu item.");
    return nil;
}

/* ----- Styling ----- */

static NSColor *textColorOf(MNHandle *h) {
    return h.hovering && h.hoverForeground ? h.hoverForeground : h.foreground;
}
static NSDictionary *textAttributes(MNHandle *h, NSFont *fallback, NSTextAlignment alignment) {
    NSMutableDictionary *a = [NSMutableDictionary new];
    NSFont *font = h.font ?: fallback ?: [NSFont systemFontOfSize:NSFont.systemFontSize];
    a[NSFontAttributeName] = font;
    a[NSForegroundColorAttributeName] = textColorOf(h) ?: NSColor.labelColor;
    if (h.kerning) a[NSKernAttributeName] = @(h.kerning);
    NSMutableParagraphStyle *p = [NSMutableParagraphStyle new];
    p.alignment = alignment;
    p.lineBreakMode = h.lines == 1 ? NSLineBreakByTruncatingTail : h.lines >= 0 ? NSLineBreakByWordWrapping : NSLineBreakByClipping;
    if (h.lineHeight > 0) {
        // CSS-style line height: a multiple of the font size, with the extra
        // space shared above and below the text rather than all above it.
        CGFloat line = font.pointSize * h.lineHeight, natural = font.ascender - font.descender + font.leading;
        p.minimumLineHeight = p.maximumLineHeight = line;
        a[NSBaselineOffsetAttributeName] = @((line - natural) / 2);
    }
    a[NSParagraphStyleAttributeName] = p;
    return a;
}
/* Text in a text view's style and alignment, for setText and appendText. */
static NSAttributedString *styledString(MNHandle *h, NSTextView *v, NSString *s) {
    return [[NSAttributedString alloc] initWithString:s attributes:textAttributes(h, v.font, v.alignment)];
}
/* lines(label, 1) truncates with "…"; 0 wraps to the width; n wraps up to n lines. */
static void wrapLabel(NSTextField *f, long long lines) {
    if (lines == 1) {
        f.maximumNumberOfLines = 1; f.cell.wraps = NO; f.cell.scrollable = NO; f.cell.truncatesLastVisibleLine = YES;
        f.lineBreakMode = NSLineBreakByTruncatingTail;
        [f setContentCompressionResistancePriority:1 forOrientation:NSLayoutConstraintOrientationHorizontal];
    } else {
        f.maximumNumberOfLines = (NSInteger)lines; f.cell.wraps = YES; f.cell.scrollable = NO;
        f.lineBreakMode = NSLineBreakByWordWrapping;
        [f setContentCompressionResistancePriority:NSLayoutPriorityDefaultLow forOrientation:NSLayoutConstraintOrientationHorizontal];
    }
}
static void applyText(MNHandle *h) {
    id o = h.object;
    NSColor *color = textColorOf(h);
    if ([o isKindOfClass:NSButton.class]) {
        NSButton *b = o;
        if (h.font) b.font = h.font;
        if (b.title.length) b.attributedTitle = [[NSAttributedString alloc] initWithString:b.title attributes:textAttributes(h, b.font, b.alignment)];
        if (color) b.contentTintColor = color;
    } else if ([o isKindOfClass:NSTextField.class]) {
        NSTextField *f = o;
        if (h.font) f.font = h.font;
        if (color) f.textColor = color;
        if (h.lines >= 0) wrapLabel(f, h.lines);
        // Editable fields keep plain values; their editor uses font and textColor.
        if (!f.isEditable) {
            f.allowsEditingTextAttributes = f.isSelectable;
            f.attributedStringValue = [[NSAttributedString alloc] initWithString:f.stringValue attributes:textAttributes(h, f.font, f.alignment)];
        }
    } else if (textView(o)) {
        NSTextView *v = textView(o);
        NSDictionary *a = textAttributes(h, v.font, v.alignment);
        if (h.font) v.font = h.font;
        if (color) { v.textColor = color; v.insertionPointColor = color; }
        v.defaultParagraphStyle = a[NSParagraphStyleAttributeName];
        v.typingAttributes = a;
        [v.textStorage setAttributes:a range:NSMakeRange(0, v.textStorage.length)];
        if (v == o) [v invalidateIntrinsicContentSize];
    }
}
static void restyle(MNHandle *h) {
    id o = h.object;
    if ([o isKindOfClass:NSWindow.class]) {
        if (h.background) [o setBackgroundColor:h.background];
        return;
    }
    if (![o isKindOfClass:NSView.class]) return;
    NSView *v = o;
    if (h.background || h.borderColor || h.radius > 0 || h.hoverBackground || h.focusBorder) {
        v.wantsLayer = YES;
        NSColor *fill = h.hovering && h.hoverBackground ? h.hoverBackground : h.background;
        NSColor *edge = h.focused && h.focusBorder ? h.focusBorder : h.borderColor;
        [v.effectiveAppearance performAsCurrentDrawingAppearance:^{
            v.layer.backgroundColor = fill ? fill.CGColor : NULL;
            v.layer.borderColor = edge ? edge.CGColor : NULL;
        }];
        v.layer.borderWidth = edge ? h.borderWidth : 0;
        v.layer.cornerRadius = h.radius;
    }
    if (h.styledText) applyText(h);
    if ([o isKindOfClass:NSClassFromString(@"MNShape")]) v.needsDisplay = YES;
}
static void applyFill(MNHandle *h);
static NSFont *resolveFont(NSString *name, double size, double weight);
@interface MNListRow : NSObject
@property(nonatomic, copy) NSString *top, *middle, *bottom;
@end
@interface MNListStyle : NSObject
@property(nonatomic, strong) NSFont *font;
@property(nonatomic, strong) NSColor *color;
@property(nonatomic) long long lines;
@end
@class MNListCell;
@interface MNList : NSScrollView <NSTableViewDataSource, NSTableViewDelegate>
@property(nonatomic, strong) NSTableView *table;
@property(nonatomic, strong) NSMutableArray<MNListCell *> *spareCells;
@property(nonatomic, strong) NSMutableArray<MNListRow *> *rows;
@property(nonatomic, copy) NSArray<MNListRow *> *shown;
@property(nonatomic, strong) NSArray<MNListStyle *> *styles;
@property(nonatomic, strong) NSImage *buttonImage;
@property(nonatomic, copy) NSString *buttonTip;
@property(nonatomic, strong) NSColor *buttonColor, *hoverBackground, *separator;
@property(nonatomic) NSEdgeInsets insets;
- (void)clearRows;
- (void)enableRows:(BOOL)enabled;
- (void)insetRows:(NSEdgeInsets)insets;
@end
static NSMutableSet<MNList *> *pendingLists;
static void reloadLists(void);
static void checkFont(double size, double weight);
static void checkLines(long long count);
static NSImage *symbolImage(NSString *name, double size);
/* Controls and rows drawn while disabled. */
static const CGFloat MNDisabledAlpha = 0.45;
/* Content hugging, including a stack's own hugging of its arranged views. */
static void hug(NSView *v, NSLayoutPriority priority, NSLayoutConstraintOrientation orientation) {
    if ([v contentHuggingPriorityForOrientation:orientation] > priority) [v setContentHuggingPriority:priority forOrientation:orientation];
    if ([v isKindOfClass:NSStackView.class] && [(NSStackView *)v huggingPriorityForOrientation:orientation] > priority)
        [(NSStackView *)v setHuggingPriority:priority forOrientation:orientation];
}
static void restyleAll(void) {
    for (NSNumber *key in handles) restyle(handles[key]);
}
static void styleView(NSView *v) {
    MNHandle *h = handleFor(v);
    if (h) restyle(h);
}

/* ----- Views with hover, click and drag behavior ----- */

static void track(NSView *v) {
    for (NSTrackingArea *area in v.trackingAreas) if (area.owner == v) [v removeTrackingArea:area];
    [v addTrackingArea:[[NSTrackingArea alloc] initWithRect:NSZeroRect
        options:NSTrackingMouseEnteredAndExited | NSTrackingActiveInActiveApp | NSTrackingInVisibleRect owner:v userInfo:nil]];
}
static void hover(NSView *v, BOOL inside) {
    MNHandle *h = handleFor(v);
    if (!h || h.hovering == inside || (!h.hoverBackground && !h.hoverForeground)) return;
    if (inside && [v isKindOfClass:NSControl.class] && ![(NSControl *)v isEnabled]) return;
    h.hovering = inside; restyle(h);
}
static void windowDrag(NSView *v, NSEvent *event) {
    if (event.clickCount == 2) {
        NSString *action = [NSUserDefaults.standardUserDefaults stringForKey:@"AppleActionOnDoubleClick"];
        if ([action isEqualToString:@"Minimize"]) [v.window performMiniaturize:nil];
        else if (![action isEqualToString:@"None"]) [v.window performZoom:nil];
        return;
    }
    [v.window performWindowDragWithEvent:event];
}
/* Labels, images and shapes inside a clickable or draggable container act as
 * part of it; buttons and text inputs keep their own mouse handling. */
static NSView *containerHit(NSView *container, NSView *hit, BOOL capture) {
    if (!capture || !hit || hit == container) return hit;
    for (NSView *v = hit; v && v != container; v = v.superview) {
        if ([v isKindOfClass:NSButton.class] || [v isKindOfClass:NSTextView.class] || [v isKindOfClass:NSScrollView.class] ||
            ([v isKindOfClass:NSTextField.class] && ([(NSTextField *)v isEditable] || [(NSTextField *)v isSelectable])))
            return hit;
    }
    return container;
}

@interface MNStack : NSStackView
@property(nonatomic) BOOL clickable, draggable, pressed, disabled;
@end
@implementation MNStack
- (BOOL)mouseDownCanMoveWindow { return NO; }
- (void)updateTrackingAreas { [super updateTrackingAreas]; track(self); }
- (void)mouseEntered:(NSEvent *)event { (void)event; if (!self.disabled) hover(self, YES); }
- (void)mouseExited:(NSEvent *)event { (void)event; hover(self, NO); }
- (NSView *)hitTest:(NSPoint)point { return containerHit(self, [super hitTest:point], self.clickable || self.draggable); }
- (void)mouseDown:(NSEvent *)event {
    if (self.clickable) { self.pressed = !self.disabled; return; }
    if (self.draggable) { windowDrag(self, event); return; }
    [super mouseDown:event];
}
- (void)mouseUp:(NSEvent *)event {
    if (!self.clickable) { [super mouseUp:event]; return; }
    BOOL inside = NSPointInRect([self convertPoint:event.locationInWindow fromView:nil], self.bounds);
    if (self.pressed && inside) enqueue(MNAction, identifier(self), @"");
    self.pressed = NO;
}
- (void)viewDidChangeEffectiveAppearance { [super viewDidChangeEffectiveAppearance]; styleView(self); }
// A clickable stack is one button to assistive technologies, named by its text.
- (BOOL)isAccessibilityElement { return self.clickable || super.isAccessibilityElement; }
- (NSAccessibilityRole)accessibilityRole { return self.clickable ? NSAccessibilityButtonRole : super.accessibilityRole; }
- (NSString *)accessibilityLabel {
    if (!self.clickable) return super.accessibilityLabel;
    NSMutableArray *parts = [NSMutableArray new];
    NSMutableArray<NSView *> *pending = [self.subviews mutableCopy];
    while (pending.count) {
        NSView *v = pending.firstObject; [pending removeObjectAtIndex:0];
        if (v.hidden) continue;
        if ([v isKindOfClass:NSTextField.class] && [(NSTextField *)v stringValue].length) [parts addObject:[(NSTextField *)v stringValue]];
        [pending addObjectsFromArray:v.subviews];
    }
    return [parts componentsJoinedByString:@", "];
}
- (NSArray *)accessibilityChildren { return self.clickable ? @[] : super.accessibilityChildren; }
- (BOOL)accessibilityPerformPress {
    if (!self.clickable || self.disabled) return NO;
    enqueue(MNAction, identifier(self), @"");
    return YES;
}
@end
/* A scroll container's document: flipped so content starts at the top. */
@interface MNDocument : MNStack
@end
@implementation MNDocument
- (BOOL)isFlipped { return YES; }
@end
@interface MNView : NSView
@end
@implementation MNView
- (BOOL)mouseDownCanMoveWindow { return NO; }
- (void)viewDidChangeEffectiveAppearance { [super viewDidChangeEffectiveAppearance]; styleView(self); }
@end
@interface MNButton : NSButton
@property(nonatomic) NSEdgeInsets insets;
@property(nonatomic, copy) NSURL *url;
@end
@interface MNButtonCell : NSButtonCell
@end
@implementation MNButtonCell
static const CGFloat symbolGap = 6;
static BOOL gapped(NSButtonCell *cell) {
    return cell.image && cell.title.length && cell.imagePosition == NSImageLeading;
}
- (NSSize)cellSize {
    NSSize size = super.cellSize;
    if (gapped(self)) size.width += symbolGap;
    return size;
}
// Draw the symbol and title inside the button's insets, not from its edges.
- (void)drawInteriorWithFrame:(NSRect)frame inView:(NSView *)view {
    if ([view isKindOfClass:MNButton.class]) {
        NSEdgeInsets i = [(MNButton *)view insets];
        frame.origin.x += i.left;
        frame.origin.y += view.isFlipped ? i.top : i.bottom;
        frame.size.width = fmax(0, frame.size.width - i.left - i.right);
        frame.size.height = fmax(0, frame.size.height - i.top - i.bottom);
    }
    [super drawInteriorWithFrame:frame inView:view];
}
- (NSRect)drawTitle:(NSAttributedString *)title withFrame:(NSRect)frame inView:(NSView *)view {
    if (gapped(self)) frame.origin.x += self.alignment == NSTextAlignmentCenter ? symbolGap / 2 : symbolGap;
    return [super drawTitle:title withFrame:frame inView:view];
}
- (void)drawImage:(NSImage *)image withFrame:(NSRect)frame inView:(NSView *)view {
    // Centered content keeps the symbol and title centered together.
    if (gapped(self) && self.alignment == NSTextAlignmentCenter) frame.origin.x -= symbolGap / 2;
    [super drawImage:image withFrame:frame inView:view];
}
@end
@implementation MNButton
+ (Class)cellClass { return MNButtonCell.class; }
- (NSSize)intrinsicContentSize {
    NSSize size = super.intrinsicContentSize;
    return NSMakeSize(size.width + self.insets.left + self.insets.right, size.height + self.insets.top + self.insets.bottom);
}
- (void)updateTrackingAreas { [super updateTrackingAreas]; track(self); }
- (void)mouseEntered:(NSEvent *)event { (void)event; hover(self, YES); }
- (void)mouseExited:(NSEvent *)event { (void)event; hover(self, NO); }
- (void)resetCursorRects { if (self.url) [self addCursorRect:self.bounds cursor:NSCursor.pointingHandCursor]; }
- (void)viewDidChangeEffectiveAppearance { [super viewDidChangeEffectiveAppearance]; styleView(self); }
// A button that moves, such as one below text that grows, is asked to draw
// the area it left, outside its bounds, where nothing it draws can show.
- (void)drawRect:(NSRect)dirty { if (NSIntersectsRect(dirty, self.bounds)) [super drawRect:dirty]; }
@end
@interface MNLabel : NSTextField
@end
@implementation MNLabel
- (void)layout {
    [super layout];
    // Wrapping labels measure their height for the width layout gives them.
    if (self.cell.wraps && fabs(self.preferredMaxLayoutWidth - NSWidth(self.bounds)) > 0.5) {
        self.preferredMaxLayoutWidth = NSWidth(self.bounds);
        [self invalidateIntrinsicContentSize];
    }
}
- (void)viewDidChangeEffectiveAppearance { [super viewDidChangeEffectiveAppearance]; styleView(self); }
@end
@interface MNTextView : NSTextView
@property(nonatomic, copy) NSString *placeholder;
@end
@implementation MNTextView
- (void)drawRect:(NSRect)rect {
    [super drawRect:rect];
    if (self.string.length || !self.placeholder.length) return;
    NSMutableDictionary *a = [self.typingAttributes mutableCopy];
    a[NSForegroundColorAttributeName] = NSColor.placeholderTextColor;
    NSPoint origin = self.textContainerOrigin;
    [self.placeholder drawAtPoint:NSMakePoint(origin.x + self.textContainer.lineFragmentPadding, origin.y) withAttributes:a];
}
@end
@implementation MNTextBlock
- (NSSize)intrinsicContentSize {
    NSLayoutManager *layout = self.layoutManager;
    [layout ensureLayoutForTextContainer:self.textContainer];
    CGFloat height = NSHeight([layout usedRectForTextContainer:self.textContainer]) + 2 * self.textContainerInset.height;
    return NSMakeSize(NSViewNoIntrinsicMetric, ceil(height));
}
- (void)setFrameSize:(NSSize)size {
    BOOL rewraps = fabs(size.width - NSWidth(self.frame)) > 0.5;
    [super setFrameSize:size];
    if (rewraps) [self invalidateIntrinsicContentSize];
}
- (void)viewDidChangeEffectiveAppearance { [super viewDidChangeEffectiveAppearance]; styleView(self); }
// Read-only text offers nothing to spell-check or correct. Otherwise, after
// every edit, AppKit's text checking copies the paragraph around the
// selection several times, which for a long one-paragraph answer is all of it.
- (NSAttributedString *)annotatedSubstringForProposedRange:(NSRange)range actualRange:(NSRangePointer)actual {
    (void)range;
    if (actual) *actual = NSMakeRange(NSNotFound, 0);
    return nil;
}
@end
/* Fills an SVG path, scaled from its view box to the view, in the text color. */
@interface MNShape : NSView
@property(nonatomic, strong) NSBezierPath *path;
@property(nonatomic) NSSize box;
@end
@implementation MNShape
- (BOOL)isFlipped { return YES; }
- (void)drawRect:(NSRect)rect {
    (void)rect;
    MNHandle *h = handleFor(self);
    NSAffineTransform *t = [NSAffineTransform transform];
    [t scaleXBy:NSWidth(self.bounds) / self.box.width yBy:NSHeight(self.bounds) / self.box.height];
    [(textColorOf(h) ?: NSColor.labelColor) setFill];
    [[t transformBezierPath:self.path] fill];
}
@end

static BOOL placingTrafficLights;
static void placeTrafficLights(NSWindow *w) {
    MNHandle *h = handleFor(w);
    if (!h || h.titlebarHeight <= 0 || (w.styleMask & NSWindowStyleMaskFullScreen) || placingTrafficLights) return;
    placingTrafficLights = YES;
    NSButton *close = [w standardWindowButton:NSWindowCloseButton];
    NSView *container = close.superview.superview;
    if (!container) return;
    NSRect frame = container.frame;
    frame.size.height = h.titlebarHeight;
    frame.origin.y = NSHeight(w.frame) - h.titlebarHeight;
    container.frame = frame;
    for (NSNumber *kind in @[@(NSWindowCloseButton), @(NSWindowMiniaturizeButton), @(NSWindowZoomButton)]) {
        NSButton *b = [w standardWindowButton:kind.unsignedIntegerValue];
        NSRect f = b.frame;
        f.origin.y = round((h.titlebarHeight - NSHeight(f)) / 2);
        if (!NSEqualRects(f, b.frame)) b.frame = f;
    }
    placingTrafficLights = NO;
}
/* A focused text input lights the border of the containers that ask for it. */
static void updateFocus(NSWindow *w) {
    id responder = w.firstResponder;
    if ([responder isKindOfClass:NSTextView.class] && [responder isFieldEditor] && [[responder delegate] isKindOfClass:NSView.class])
        responder = [responder delegate];
    NSView *target = [responder isKindOfClass:NSView.class] ? responder : nil;
    for (NSNumber *key in handles) {
        MNHandle *h = handles[key];
        if (!h.focusBorder || ![h.object isKindOfClass:NSView.class] || [h.object window] != w) continue;
        BOOL focused = target && [target isDescendantOf:h.object];
        if (focused != h.focused) { h.focused = focused; restyle(h); }
    }
}
static void fitHeight(MNHandle *h) {
    NSTextView *v = editor(h.object);
    if (!v || h.autoMaximum <= 0) return;
    [v.layoutManager ensureLayoutForTextContainer:v.textContainer];
    CGFloat used = NSHeight([v.layoutManager usedRectForTextContainer:v.textContainer]);
    CGFloat line = [v.layoutManager defaultLineHeightForFont:v.font ?: [NSFont systemFontOfSize:NSFont.systemFontSize]];
    CGFloat height = fmax(used, line) + 2 * v.textContainerInset.height;
    h.height.constant = fmin(fmax(ceil(height), h.autoMinimum), h.autoMaximum);
}

@implementation MNDelegate
- (void)action:(id)sender {
    if ([sender isKindOfClass:MNButton.class] && [sender url]) [NSWorkspace.sharedWorkspace openURL:[sender url]];
    enqueue([sender isKindOfClass:NSSlider.class] ? MNChange : MNAction, identifier(sender), @"");
}
- (void)submit:(id)sender { enqueue(MNSubmit, identifier(sender), [sender stringValue]); }
- (void)requestQuit:(id)sender { (void)sender; requestQuit(); }
- (void)showAbout:(id)sender {
    (void)sender;
    NSMutableDictionary *options = [NSMutableDictionary new];
    if (aboutCredits.length) {
        NSMutableParagraphStyle *p = [NSMutableParagraphStyle new]; p.alignment = NSTextAlignmentCenter;
        options[NSAboutPanelOptionCredits] = [[NSAttributedString alloc] initWithString:aboutCredits attributes:@{
            NSFontAttributeName: [NSFont systemFontOfSize:NSFont.smallSystemFontSize],
            NSForegroundColorAttributeName: NSColor.secondaryLabelColor, NSParagraphStyleAttributeName: p}];
    }
    [NSApp orderFrontStandardAboutPanelWithOptions:options];
}
- (NSApplicationTerminateReply)applicationShouldTerminate:(NSApplication *)app {
    (void)app; requestQuit(); return NSTerminateCancel;
}
- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication *)app { (void)app; return NO; }
- (void)windowWillClose:(NSNotification *)notification { enqueue(MNClosed, identifier(notification.object), @""); }
- (void)windowDidResize:(NSNotification *)notification {
    placeTrafficLights(notification.object);
    enqueue(MNResized, identifier(notification.object), @"");
}
- (void)windowDidBecomeKey:(NSNotification *)notification { placeTrafficLights(notification.object); }
- (void)windowDidExitFullScreen:(NSNotification *)notification { placeTrafficLights(notification.object); }
- (void)controlTextDidChange:(NSNotification *)notification {
    NSTextField *field = notification.object;
    MNHandle *h = handleFor(field);
    if (h.maxLength > 0 && (long long)field.stringValue.length > h.maxLength) {
        NSUInteger end = [field.stringValue rangeOfComposedCharacterSequenceAtIndex:(NSUInteger)h.maxLength].location;
        field.stringValue = [field.stringValue substringToIndex:end];
        NSBeep();
    }
    enqueue(MNChange, identifier(field), field.stringValue);
}
- (void)textDidChange:(NSNotification *)notification {
    NSTextView *view = notification.object;
    MNHandle *h = handleFor(view.enclosingScrollView);
    if (h) fitHeight(h);
    view.needsDisplay = YES;
    enqueue(MNChange, identifier(view.enclosingScrollView), view.string);
}
- (BOOL)textView:(NSTextView *)view shouldChangeTextInRange:(NSRange)range replacementString:(NSString *)text {
    MNHandle *h = handleFor(view.enclosingScrollView);
    if (!h || h.maxLength <= 0 || !text) return YES;
    long long room = h.maxLength - (long long)(view.string.length - range.length);
    if ((long long)text.length <= room) return YES;
    NSBeep();
    if (room <= 0) return NO;
    // Keep whole characters: cut before any sequence that straddles the limit.
    NSUInteger end = [text rangeOfComposedCharacterSequenceAtIndex:(NSUInteger)room].location;
    if (end) [view insertText:[text substringToIndex:end] replacementRange:range];
    return NO;
}
- (BOOL)textView:(NSTextView *)view doCommandBySelector:(SEL)command {
    MNHandle *h = handleFor(view.enclosingScrollView);
    if (!h.submitOnEnter || command != @selector(insertNewline:) || view.hasMarkedText) return NO;
    // Shift-Return and Option-Return add a line; Return alone submits.
    if (NSApp.currentEvent.modifierFlags & (NSEventModifierFlagShift | NSEventModifierFlagOption)) {
        [view insertNewlineIgnoringFieldEditor:nil];
        return YES;
    }
    enqueue(MNSubmit, identifier(view.enclosingScrollView), view.string);
    return YES;
}
- (void)stackView:(NSStackView *)stack didReattachViews:(NSArray<NSView *> *)views {
    (void)stack;
    for (NSView *v in views) { MNHandle *h = handleFor(v); if (h.fills) applyFill(h); }
}
// AppKit lays the title bar out again on some changes, such as appearance.
- (void)titlebarFrameDidChange:(NSNotification *)notification { placeTrafficLights([notification.object window]); }
- (void)viewFrameDidChange:(NSNotification *)notification {
    MNHandle *h = handleFor([notification.object enclosingScrollView]);
    if (h) fitHeight(h);
}
- (void)observeValueForKeyPath:(NSString *)path ofObject:(id)target change:(NSDictionary *)change context:(void *)context {
    (void)change; (void)context;
    if ([path isEqualToString:@"firstResponder"]) updateFocus(target);
    if ([path isEqualToString:@"effectiveAppearance"]) restyleAll();
}
@end

static void dimension(long long n) {
    if (n < 0 || n > 100000) minyar_native_stop("macos dimensions must be between 0 and 100000 points.");
}
static NSStackView *container(id value) {
    if ([value isKindOfClass:NSStackView.class]) return value;
    if ([value isKindOfClass:NSScrollView.class] && [[value documentView] isKindOfClass:MNDocument.class]) return [value documentView];
    return nil;
}
static long long append(long long parent, NSView *view) {
    MNHandle *p = entry(parent);
    view.translatesAutoresizingMaskIntoConstraints = NO;
    long long owner = p.owner;
    if ([p.object isKindOfClass:NSWindow.class]) {
        NSView *content = [p.object contentView];
        if (content.subviews.count) minyar_native_stop("a macos window accepts one root view; add controls to a row or column.");
        owner = parent;
        // Below NSLayoutPriorityWindowSizeStayPut: the window decides its size, not its content.
        hug(view, NSLayoutPriorityDefaultLow, NSLayoutConstraintOrientationHorizontal);
        hug(view, NSLayoutPriorityDefaultLow, NSLayoutConstraintOrientationVertical);
        [content addSubview:view];
        [NSLayoutConstraint activateConstraints:@[
            [view.leadingAnchor constraintEqualToAnchor:content.leadingAnchor],
            [view.trailingAnchor constraintEqualToAnchor:content.trailingAnchor],
            [view.topAnchor constraintEqualToAnchor:content.topAnchor],
            [view.bottomAnchor constraintEqualToAnchor:content.bottomAnchor]]];
    } else if (container(p.object)) {
        // New views join the START area even when an earlier view moved to CENTER.
        [container(p.object) addView:view inGravity:NSStackViewGravityLeading];
    } else minyar_native_stop("macos parent must be a window, row, column, or scroll view.");
    return registerObject(view, owner);
}
static NSView *view(long long handle) { return object(handle, NSView.class); }
static NSStackView *parentStack(long long handle) {
    NSView *v = view(handle);
    if (![v.superview isKindOfClass:NSStackView.class]) minyar_native_stop("macos layout requires a view inside a row, column, or scroll view.");
    return (NSStackView *)v.superview;
}
static NSColor *color(long long handle) {
    return handle ? object(handle, NSColor.class) : nil;
}
static void applyFill(MNHandle *h) {
    NSView *v = h.object;
    [NSLayoutConstraint deactivateConstraints:h.fillConstraints ?: @[]];
    h.fillConstraints = nil;
    if (!h.fills || ![v.superview isKindOfClass:NSStackView.class]) return;
    NSStackView *s = (NSStackView *)v.superview;
    NSEdgeInsets i = s.edgeInsets;
    // Stacks hug their content above the window's own size priority; a filled
    // view must not, or it would pull the window down to its fitting size.
    NSLayoutConstraintOrientation across = s.orientation == NSUserInterfaceLayoutOrientationVertical
        ? NSLayoutConstraintOrientationHorizontal : NSLayoutConstraintOrientationVertical;
    hug(v, NSLayoutPriorityDefaultLow, across);
    // Stay inside the stack's insets and match its size. A view with a maximum
    // size matches more weakly than the window keeps its size, so a capped
    // view never pulls its window (or its other ancestors) down to the cap.
    NSArray *c = s.orientation == NSUserInterfaceLayoutOrientationVertical
        ? @[[v.leadingAnchor constraintGreaterThanOrEqualToAnchor:s.leadingAnchor constant:i.left],
            [v.trailingAnchor constraintLessThanOrEqualToAnchor:s.trailingAnchor constant:-i.right],
            [v.widthAnchor constraintEqualToAnchor:s.widthAnchor constant:-(i.left + i.right)]]
        : @[[v.topAnchor constraintGreaterThanOrEqualToAnchor:s.topAnchor constant:i.top],
            [v.bottomAnchor constraintLessThanOrEqualToAnchor:s.bottomAnchor constant:-i.bottom],
            [v.heightAnchor constraintEqualToAnchor:s.heightAnchor constant:-(i.top + i.bottom)]];
    [c[0] setPriority:999]; [c[1] setPriority:999];
    BOOL capped = s.orientation == NSUserInterfaceLayoutOrientationVertical ? h.maximumWidth != nil : h.maximumHeight != nil;
    [c[2] setPriority:capped ? NSLayoutPriorityWindowSizeStayPut - 10 : 999];
    [NSLayoutConstraint activateConstraints:c];
    h.fillConstraints = c;
}
static void refill(NSStackView *s) {
    for (NSView *child in s.arrangedSubviews) {
        MNHandle *h = handleFor(child);
        if (h.fills) applyFill(h);
    }
}
static void forget(NSView *root, BOOL includeRoot) {
    NSMutableArray<NSNumber *> *gone = [NSMutableArray new];
    for (NSNumber *key in handles) {
        id o = handles[key].object;
        if ([o isKindOfClass:NSView.class] && [o isDescendantOf:root] && (includeRoot || o != root)) [gone addObject:key];
    }
    for (NSNumber *key in gone) [numbers removeObjectForKey:handles[key].object];
    [handles removeObjectsForKeys:gone];
    dropEvents(^BOOL(MNEvent *e) { return e.source != 0 && handles[@(e.source)] == nil; });
}
static void replaceMinimum(MNHandle *h, NSView *v, long long width, long long height) {
    h.minimumWidth.active = NO; h.minimumHeight.active = NO; h.minimumWidth = nil; h.minimumHeight = nil;
    if (width) { h.minimumWidth = [v.widthAnchor constraintGreaterThanOrEqualToConstant:width]; h.minimumWidth.active = YES; }
    if (height) { h.minimumHeight = [v.heightAnchor constraintGreaterThanOrEqualToConstant:height]; h.minimumHeight.active = YES; }
}
static NSFontWeight fontWeight(double weight) {
    static const double css[] = {100, 200, 300, 400, 500, 600, 700, 800, 900};
    const NSFontWeight native[] = {NSFontWeightUltraLight, NSFontWeightThin, NSFontWeightLight, NSFontWeightRegular,
        NSFontWeightMedium, NSFontWeightSemibold, NSFontWeightBold, NSFontWeightHeavy, NSFontWeightBlack};
    if (weight <= css[0]) return native[0];
    for (int i = 1; i < 9; ++i)
        if (weight <= css[i]) return native[i - 1] + (native[i] - native[i - 1]) * (weight - css[i - 1]) / (css[i] - css[i - 1]);
    return native[8];
}

void minyar_macos_initialize(const MinyarText *name) { @autoreleasepool {
    mainThread();
    if (handles) minyar_native_stop("macos.initialize may only be called once.");
    [NSApplication sharedApplication];
    handles = [NSMutableDictionary new]; events = [NSMutableArray new]; delegate = [MNDelegate new];
    numbers = [NSMapTable mapTableWithKeyOptions:NSPointerFunctionsWeakMemory | NSPointerFunctionsObjectPointerPersonality
                                    valueOptions:NSPointerFunctionsStrongMemory];
    NSApp.delegate = delegate;
    [NSApp setActivationPolicy:NSApplicationActivationPolicyRegular];
    NSString *title = string(name);
    NSMenu *main = [NSMenu new];
    NSMenuItem *appItem = [NSMenuItem new]; [main addItem:appItem];
    NSMenu *appMenu = [[NSMenu alloc] initWithTitle:title]; appItem.submenu = appMenu;
    NSMenuItem *about = [[NSMenuItem alloc] initWithTitle:[@"About " stringByAppendingString:title] action:@selector(showAbout:) keyEquivalent:@""];
    about.target = delegate; [appMenu addItem:about];
    [appMenu addItem:NSMenuItem.separatorItem];
    [appMenu addItem:[[NSMenuItem alloc] initWithTitle:[@"Hide " stringByAppendingString:title] action:@selector(hide:) keyEquivalent:@"h"]];
    NSMenuItem *others = [[NSMenuItem alloc] initWithTitle:@"Hide Others" action:@selector(hideOtherApplications:) keyEquivalent:@"h"];
    others.keyEquivalentModifierMask = NSEventModifierFlagCommand | NSEventModifierFlagOption; [appMenu addItem:others];
    [appMenu addItem:[[NSMenuItem alloc] initWithTitle:@"Show All" action:@selector(unhideAllApplications:) keyEquivalent:@""]];
    [appMenu addItem:NSMenuItem.separatorItem];
    NSMenuItem *quit = [[NSMenuItem alloc] initWithTitle:[@"Quit " stringByAppendingString:title] action:@selector(requestQuit:) keyEquivalent:@"q"];
    quit.target = delegate; [appMenu addItem:quit];
    NSMenuItem *editItem = [[NSMenuItem alloc] initWithTitle:@"Edit" action:NULL keyEquivalent:@""];
    [main addItem:editItem]; NSMenu *edit = [[NSMenu alloc] initWithTitle:@"Edit"]; editItem.submenu = edit;
    NSArray *titles = @[@"Undo", @"Redo", @"Cut", @"Copy", @"Paste", @"Select All"];
    NSArray *actions = @[@"undo:", @"redo:", @"cut:", @"copy:", @"paste:", @"selectAll:"];
    NSArray *keys = @[@"z", @"Z", @"x", @"c", @"v", @"a"];
    for (NSUInteger i = 0; i < titles.count; ++i)
        [edit addItem:[[NSMenuItem alloc] initWithTitle:titles[i] action:NSSelectorFromString(actions[i]) keyEquivalent:keys[i]]];
    NSMenuItem *windowItem = [[NSMenuItem alloc] initWithTitle:@"Window" action:NULL keyEquivalent:@""];
    [main addItem:windowItem]; NSMenu *windows = [[NSMenu alloc] initWithTitle:@"Window"]; windowItem.submenu = windows;
    [windows addItem:[[NSMenuItem alloc] initWithTitle:@"Minimize" action:@selector(performMiniaturize:) keyEquivalent:@"m"]];
    [windows addItem:[[NSMenuItem alloc] initWithTitle:@"Zoom" action:@selector(performZoom:) keyEquivalent:@""]];
    [windows addItem:NSMenuItem.separatorItem];
    [windows addItem:[[NSMenuItem alloc] initWithTitle:@"Bring All to Front" action:@selector(arrangeInFront:) keyEquivalent:@""]];
    NSApp.mainMenu = main; NSApp.windowsMenu = windows;
    [NSApp addObserver:delegate forKeyPath:@"effectiveAppearance" options:0 context:NULL];
    [NSApp finishLaunching];
} }
long long minyar_macos_window(const MinyarText *title, long long width, long long height) { @autoreleasepool {
    ready(); dimension(width); dimension(height);
    if (!width || !height) minyar_native_stop("macos windows require positive dimensions.");
    NSWindow *w = [[NSWindow alloc] initWithContentRect:NSMakeRect(0,0,width,height)
        styleMask:NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskMiniaturizable | NSWindowStyleMaskResizable
        backing:NSBackingStoreBuffered defer:NO];
    w.releasedWhenClosed = NO; w.title = string(title); w.delegate = delegate; [w center];
    [w addObserver:delegate forKeyPath:@"firstResponder" options:0 context:NULL];
    return registerObject(w, 0);
} }
void minyar_macos_show(long long handle) { @autoreleasepool {
    NSWindow *w = object(handle, NSWindow.class); [w makeKeyAndOrderFront:nil]; [NSApp activateIgnoringOtherApps:YES];
    placeTrafficLights(w);
} }
void minyar_macos_close(long long handle) { @autoreleasepool { [object(handle, NSWindow.class) close]; } }
void minyar_macos_destroy(long long handle) { @autoreleasepool {
    NSWindow *w = object(handle, NSWindow.class); w.delegate = nil; [w close];
    [w removeObserver:delegate forKeyPath:@"firstResponder"];
    for (NSNumber *key in handles.allKeys) if (handles[key].owner == handle) {
        [numbers removeObjectForKey:handles[key].object]; [handles removeObjectForKey:key];
    }
    [numbers removeObjectForKey:w];
    [handles removeObjectForKey:@(handle)];
    // No future events may refer to destroyed objects. The current event remains a snapshot.
    dropEvents(^BOOL(MNEvent *e) { return e.source != 0 && handles[@(e.source)] == nil; });
} }
static long long stack(long long parent, long long spacing, NSUserInterfaceLayoutOrientation orientation) {
    ready(); dimension(spacing); MNStack *s = [MNStack new]; s.orientation = orientation; s.spacing = spacing;
    s.alignment = orientation == NSUserInterfaceLayoutOrientationVertical ? NSLayoutAttributeLeading : NSLayoutAttributeCenterY;
    s.detachesHiddenViews = YES; s.delegate = delegate;
    return append(parent, s);
}
long long minyar_macos_column(long long parent, long long spacing) { @autoreleasepool { return stack(parent, spacing, NSUserInterfaceLayoutOrientationVertical); } }
long long minyar_macos_row(long long parent, long long spacing) { @autoreleasepool { return stack(parent, spacing, NSUserInterfaceLayoutOrientationHorizontal); } }
void minyar_macos_padding(long long handle, long long points) { @autoreleasepool {
    NSStackView *s = object(handle, NSStackView.class); dimension(points); s.edgeInsets = NSEdgeInsetsMake(points,points,points,points);
    refill(s);
} }
long long minyar_macos_label(long long parent, const MinyarText *text) { @autoreleasepool {
    ready(); NSTextField *v = [MNLabel labelWithString:string(text)]; v.selectable = YES; return append(parent,v);
} }
long long minyar_macos_button(long long parent, const MinyarText *title) { @autoreleasepool {
    ready(); return append(parent, [MNButton buttonWithTitle:string(title) target:delegate action:@selector(action:)]);
} }
long long minyar_macos_checkbox(long long parent, const MinyarText *title, bool checked) { @autoreleasepool {
    ready(); NSButton *b = [NSButton checkboxWithTitle:string(title) target:delegate action:@selector(action:)];
    b.state = checked ? NSControlStateValueOn : NSControlStateValueOff;
    long long h = append(parent,b); entry(h).isCheckbox = YES; return h;
} }
static long long field(long long parent, NSTextField *v) {
    v.delegate = delegate; v.target = delegate; v.action = @selector(submit:);
    v.cell.sendsActionOnEndEditing = NO;
    long long h = append(parent,v);
    replaceMinimum(entry(h), v, 160, 0);
    return h;
}
long long minyar_macos_textField(long long parent, const MinyarText *text) { @autoreleasepool {
    ready(); return field(parent, [NSTextField textFieldWithString:string(text)]);
} }
long long minyar_macos_secureField(long long parent) { @autoreleasepool {
    ready(); NSSecureTextField *v = [NSSecureTextField new]; v.bezeled = YES; v.editable = YES; v.selectable = YES;
    return field(parent, v);
} }
long long minyar_macos_textEditor(long long parent, const MinyarText *text) { @autoreleasepool {
    ready(); NSScrollView *scroll = [NSScrollView new]; scroll.hasVerticalScroller = YES; scroll.borderType = NSBezelBorder;
    MNTextView *v = [[MNTextView alloc] initWithFrame:NSMakeRect(0,0,320,180)];
    v.richText = NO; v.allowsUndo = YES; v.verticallyResizable = YES; v.horizontallyResizable = NO;
    v.autoresizingMask = NSViewWidthSizable; v.textContainer.widthTracksTextView = YES;
    v.minSize = NSMakeSize(0,0); v.maxSize = NSMakeSize(100000,100000);
    v.string = string(text); v.delegate = delegate; scroll.documentView = v;
    v.postsFrameChangedNotifications = YES;
    [NSNotificationCenter.defaultCenter addObserver:delegate selector:@selector(viewFrameDidChange:) name:NSViewFrameDidChangeNotification object:v];
    long long h = append(parent,scroll);
    replaceMinimum(entry(h), scroll, 200, 100);
    return h;
} }
long long minyar_macos_textView(long long parent, const MinyarText *text) { @autoreleasepool {
    ready();
    // TextKit 1, built by hand: appending to a long paragraph lays out only
    // the lines from the changed one on.
    NSTextStorage *storage = [NSTextStorage new];
    NSLayoutManager *layout = [NSLayoutManager new]; [storage addLayoutManager:layout];
    NSTextContainer *container = [[NSTextContainer alloc] initWithSize:NSMakeSize(0, CGFLOAT_MAX)];
    // Labels line up their text, not their cell's 2-point inset, with the
    // stack's edge, so the text starts at the view's edge.
    container.widthTracksTextView = YES; container.lineFragmentPadding = 0;
    [layout addTextContainer:container];
    MNTextBlock *v = [[MNTextBlock alloc] initWithFrame:NSZeroRect textContainer:container];
    v.storage = storage;
    v.richText = NO; v.importsGraphics = NO; v.editable = NO; v.selectable = YES; v.drawsBackground = NO;
    v.verticallyResizable = NO; v.horizontallyResizable = NO; v.textContainerInset = NSZeroSize;
    v.font = [NSFont systemFontOfSize:NSFont.systemFontSize];
    long long handle = append(parent, v);
    MNHandle *h = entry(handle);
    // Like a wrapping label: system font, label color, word wrapping.
    h.lines = 0; h.styledText = YES;
    [storage setAttributedString:styledString(h, v, string(text))];
    applyText(h);
    return handle;
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
    MNHandle *h = entry(handle); id v = h.object; NSString *s = string(text);
    if (editor(v)) { editor(v).string = s; if (h.styledText) applyText(h); fitHeight(h); editor(v).needsDisplay = YES; return; }
    if ([v isKindOfClass:MNTextBlock.class]) {
        MNTextBlock *t = v;
        [t.textStorage replaceCharactersInRange:NSMakeRange(0, t.textStorage.length) withAttributedString:styledString(h, t, s)];
        [t invalidateIntrinsicContentSize];
        return;
    }
    if ([v isKindOfClass:NSTextField.class]) { [v setStringValue:s]; if (h.styledText) applyText(h); return; }
    if ([v isKindOfClass:NSWindow.class] || [v isKindOfClass:NSMenuItem.class]) { [v setTitle:s]; return; }
    if ([v isKindOfClass:NSButton.class]) {
        NSButton *b = v; [b setTitle:s];
        if (b.image) b.imagePosition = s.length ? NSImageLeading : NSImageOnly;
        if (h.styledText) applyText(h);
        return;
    }
    minyar_native_stop("macos.setText requires a window, text control, button, or menu item.");
} }
void minyar_macos_appendText(long long handle, const MinyarText *text) { @autoreleasepool {
    MNHandle *h = entry(handle); NSTextView *v = textView(h.object);
    if (!v) minyar_native_stop("macos.appendText requires a textView or textEditor.");
    NSString *s = string(text);
    if (!s.length) return;
    // Only the new characters are edited, so the existing layout and any selection stay.
    [v.textStorage appendAttributedString:h.styledText ? styledString(h, v, s) : [[NSAttributedString alloc] initWithString:s attributes:v.typingAttributes]];
    if (v == h.object) [v invalidateIntrinsicContentSize]; else { fitHeight(h); v.needsDisplay = YES; }
} }
void minyar_macos_enabled(long long handle, bool value) { @autoreleasepool {
    MNHandle *h = entry(handle); id v = h.object;
    if ([v isKindOfClass:MNStack.class]) {
        MNStack *s = v; s.disabled = !value; s.alphaValue = value ? 1 : MNDisabledAlpha;
        if (!value && h.hovering) { h.hovering = NO; restyle(h); }
        return;
    }
    if ([v isKindOfClass:MNList.class]) { [(MNList *)v enableRows:value]; return; }
    if (editor(v)) {
        editor(v).editable = value; editor(v).textColor = value ? (textColorOf(h) ?: NSColor.textColor) : NSColor.disabledControlTextColor;
        return;
    }
    if (![v isKindOfClass:NSControl.class] && ![v isKindOfClass:NSMenuItem.class]) minyar_native_stop("macos.enabled requires a control, editor, or menu item.");
    [v setEnabled:value];
    if ([v isKindOfClass:MNButton.class] && ![v isBordered]) {
        [v setAlphaValue:value ? 1 : MNDisabledAlpha];
        if (!value && h.hovering) { h.hovering = NO; restyle(h); }
    }
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
    ready(); NSString *name = string(title);
    NSMenu *m = [[NSMenu alloc] initWithTitle:name]; m.autoenablesItems = NO;
    NSMenuItem *item = [[NSMenuItem alloc] initWithTitle:name action:NULL keyEquivalent:@""];
    item.submenu = m;
    // Keep the Mac order: application, File, Edit, application menus, Window, Help.
    NSMenu *bar = NSApp.mainMenu;
    BOOL help = [name isEqualToString:@"Help"];
    NSInteger index = [name isEqualToString:@"File"] ? 1 : help ? bar.numberOfItems : [bar indexOfItemWithSubmenu:NSApp.windowsMenu];
    if (index < 0 || index > bar.numberOfItems) index = bar.numberOfItems;
    [bar insertItem:item atIndex:index];
    if (help) NSApp.helpMenu = m;
    return registerObject(m,0);
} }
long long minyar_macos_menuItem(long long menu, const MinyarText *title, const MinyarText *key) { @autoreleasepool {
    NSMenu *m = object(menu,NSMenu.class);
    NSMenuItem *item = [[NSMenuItem alloc] initWithTitle:string(title) action:@selector(action:) keyEquivalent:string(key)];
    item.target = delegate; [m addItem:item]; return registerObject(item,entry(menu).owner);
} }
void minyar_macos_menuSeparator(long long menu) { @autoreleasepool {
    [object(menu,NSMenu.class) addItem:NSMenuItem.separatorItem];
} }
bool minyar_macos_accessory(bool enabled) { @autoreleasepool {
    ready();
    return [NSApp setActivationPolicy:enabled ? NSApplicationActivationPolicyAccessory : NSApplicationActivationPolicyRegular];
} }
long long minyar_macos_statusItem(const MinyarText *title, const MinyarText *symbol) { @autoreleasepool {
    ready();
    NSStatusItem *item = [NSStatusBar.systemStatusBar statusItemWithLength:NSVariableStatusItemLength];
    item.button.title = string(title);
    NSString *name = string(symbol);
    if (name.length) {
        NSImage *image = [NSImage imageWithSystemSymbolName:name accessibilityDescription:string(title)];
        image.template = YES;
        item.button.image = image;
        item.button.imagePosition = NSImageLeft;
    }
    item.button.toolTip = string(title);
    return registerObject(item,0);
} }
long long minyar_macos_statusMenu(long long handle) { @autoreleasepool {
    NSStatusItem *item = object(handle,NSStatusItem.class);
    if (item.menu) return identifier(item.menu);
    NSMenu *menu = [[NSMenu alloc] initWithTitle:item.button.title];
    item.menu = menu;
    return registerObject(menu,handle);
} }
void minyar_macos_statusRemove(long long handle) { @autoreleasepool {
    NSStatusItem *item = object(handle,NSStatusItem.class);
    [NSStatusBar.systemStatusBar removeStatusItem:item];
    item.menu = nil;
    for (NSNumber *key in handles.allKeys) if (handles[key].owner == handle) {
        [numbers removeObjectForKey:handles[key].object];
        [handles removeObjectForKey:key];
    }
    [numbers removeObjectForKey:item];
    [handles removeObjectForKey:@(handle)];
    dropEvents(^BOOL(MNEvent *event) { return event.source != 0 && !handles[@(event.source)]; });
} }
#include "app_net_loop.h"
#ifdef MINYAR_APP_MANAGED_CLEANUP
extern bool minyar_callbackruntime_service(void);
#endif
bool minyar_macos_nextEvent(double timeout) { @autoreleasepool {
    ready(); if (!isfinite(timeout) || timeout < 0 || timeout > 60) minyar_native_stop("macos event timeout must be between 0 and 60 seconds.");
    current = nil;
    reloadLists();
    NSDate *deadline = [NSDate dateWithTimeIntervalSinceNow:timeout];
#ifdef MINYAR_APP_MANAGED_CLEANUP
    // Collection stays on the owning main thread. Give abandoned captures one
    // bounded batch, then pump input without sleeping while old debt remains.
    // A drained application resumes its requested OS wait without idle ticks.
    if (minyar_callbackruntime_service()) deadline = NSDate.distantPast;
#endif
    BOOL woken = NO;
    // Always pump at least one native event, even while Minyar events are pending.
    // This keeps menus, window drawing and text input responsive under load.
    do {
        waiting = !events.count && !quitting;
        NSEvent *e = [NSApp nextEventMatchingMask:NSEventMaskAny untilDate:(events.count || quitting ? NSDate.distantPast : deadline) inMode:NSDefaultRunLoopMode dequeue:YES];
        waiting = NO;
        // Background work progressed: return so the program can look at it, but
        // at most once a display frame. A stream that arrives in many small
        // chunks is then drawn at the display rate, not once per chunk; input
        // events are still delivered at once.
        if (e.type == NSEventTypeApplicationDefined && e.subtype == MNWakeSubtype) {
            NSTimeInterval now = NSProcessInfo.processInfo.systemUptime, frame = lastWake + MNWakeInterval;
            woken = YES;
            if (now >= frame) break;
            if (deadline.timeIntervalSinceNow > frame - now) deadline = [NSDate dateWithTimeIntervalSinceNow:frame - now];
            continue;
        }
        if (e) [NSApp sendEvent:e];
        [NSApp updateWindows];
        if (!e) break;
    } while (!events.count && !quitting && deadline.timeIntervalSinceNow > 0);
    if (woken) lastWake = NSProcessInfo.processInfo.systemUptime;
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

/* ----- Layout ----- */

long long minyar_macos_view(long long parent) { @autoreleasepool { ready(); return append(parent, [MNView new]); } }
long long minyar_macos_spacer(long long parent) { @autoreleasepool {
    ready(); MNView *v = [MNView new];
    long long h = append(parent, v);
    NSStackView *s = parentStack(h);
    [v setContentHuggingPriority:1 forOrientation:(NSLayoutConstraintOrientation)s.orientation];
    s.distribution = NSStackViewDistributionFill;
    return h;
} }
long long minyar_macos_scroll(long long parent) { @autoreleasepool {
    ready();
    NSScrollView *scroll = [NSScrollView new];
    scroll.drawsBackground = NO; scroll.borderType = NSNoBorder;
    scroll.hasVerticalScroller = YES; scroll.autohidesScrollers = YES;
    scroll.contentView.drawsBackground = NO;
    MNDocument *document = [MNDocument new];
    document.orientation = NSUserInterfaceLayoutOrientationVertical; document.alignment = NSLayoutAttributeLeading;
    document.spacing = 0; document.detachesHiddenViews = YES; document.delegate = delegate;
    // Short content must never shrink the scroll view: the document hugs it
    // more weakly than any surrounding view hugs its own content.
    hug(document, 2, NSLayoutConstraintOrientationVertical);
    document.translatesAutoresizingMaskIntoConstraints = NO;
    scroll.documentView = document;
    NSClipView *clip = scroll.contentView;
    // The document is as wide as the view and at least as tall, so content can be centered.
    [NSLayoutConstraint activateConstraints:@[
        [document.leadingAnchor constraintEqualToAnchor:clip.leadingAnchor],
        [document.trailingAnchor constraintEqualToAnchor:clip.trailingAnchor],
        [document.topAnchor constraintEqualToAnchor:clip.topAnchor],
        [document.heightAnchor constraintGreaterThanOrEqualToAnchor:clip.heightAnchor]]];
    return append(parent, scroll);
} }
void minyar_macos_scrollToTop(long long handle) { @autoreleasepool {
    NSScrollView *s = object(handle, NSScrollView.class);
    [s.contentView scrollToPoint:NSZeroPoint]; [s reflectScrolledClipView:s.contentView];
} }
void minyar_macos_grow(long long handle) { @autoreleasepool {
    NSView *v = view(handle); NSStackView *s = parentStack(handle);
    hug(v, 1, (NSLayoutConstraintOrientation)s.orientation);
    s.distribution = NSStackViewDistributionFill;
} }
void minyar_macos_fill(long long handle) { @autoreleasepool {
    parentStack(handle); MNHandle *h = entry(handle); h.fills = YES; applyFill(h);
} }
void minyar_macos_minimumSize(long long handle, long long width, long long height) { @autoreleasepool {
    dimension(width); dimension(height); MNHandle *h = entry(handle);
    if ([h.object isKindOfClass:NSWindow.class]) {
        // A known full-screen minimum spares AppKit deriving one from every
        // constraint after each layout change.
        [h.object setContentMinSize:NSMakeSize(width, height)];
        [h.object setMinFullScreenContentSize:NSMakeSize(width, height)];
        return;
    }
    replaceMinimum(h, view(handle), width, height);
} }
void minyar_macos_maximumSize(long long handle, long long width, long long height) { @autoreleasepool {
    NSView *v = view(handle); dimension(width); dimension(height); MNHandle *h = entry(handle);
    h.maximumWidth.active = NO; h.maximumHeight.active = NO; h.maximumWidth = nil; h.maximumHeight = nil;
    if (width) { h.maximumWidth = [v.widthAnchor constraintLessThanOrEqualToConstant:width]; h.maximumWidth.active = YES; }
    if (height) { h.maximumHeight = [v.heightAnchor constraintLessThanOrEqualToConstant:height]; h.maximumHeight.active = YES; }
    if (h.fills) applyFill(h);
} }
void minyar_macos_insets(long long handle, long long top, long long left, long long bottom, long long right) { @autoreleasepool {
    dimension(top); dimension(left); dimension(bottom); dimension(right);
    id v = entry(handle).object;
    NSEdgeInsets insets = NSEdgeInsetsMake(top, left, bottom, right);
    if (container(v)) { container(v).edgeInsets = insets; refill(container(v)); return; }
    if ([v isKindOfClass:MNButton.class]) { [v setInsets:insets]; [v invalidateIntrinsicContentSize]; return; }
    if ([v isKindOfClass:MNList.class]) { [(MNList *)v insetRows:insets]; return; }
    minyar_native_stop("macos.insets requires a row, column, scroll view, list, or button.");
} }
void minyar_macos_align(long long handle, long long alignment) { @autoreleasepool {
    NSStackView *s = container(entry(handle).object);
    if (!s) minyar_native_stop("macos.align requires a row, column, or scroll view.");
    if (alignment < MNStart || alignment > MNEnd) minyar_native_stop("macos alignment must be START, CENTER, or END.");
    BOOL vertical = s.orientation == NSUserInterfaceLayoutOrientationVertical;
    s.alignment = alignment == MNStart ? (vertical ? NSLayoutAttributeLeading : NSLayoutAttributeTop)
        : alignment == MNCenter ? (vertical ? NSLayoutAttributeCenterX : NSLayoutAttributeCenterY)
        : (vertical ? NSLayoutAttributeTrailing : NSLayoutAttributeBottom);
} }
void minyar_macos_gravity(long long handle, long long gravity) { @autoreleasepool {
    NSView *v = view(handle); NSStackView *s = parentStack(handle);
    if (gravity < MNStart || gravity > MNEnd) minyar_native_stop("macos gravity must be START, CENTER, or END.");
    [s removeView:v];
    [s addView:v inGravity:gravity == MNStart ? NSStackViewGravityLeading : gravity == MNCenter ? NSStackViewGravityCenter : NSStackViewGravityTrailing];
    MNHandle *h = entry(handle);
    if (h.fills) applyFill(h);
} }
void minyar_macos_spaceAfter(long long handle, long long points) { @autoreleasepool {
    dimension(points); [parentStack(handle) setCustomSpacing:points afterView:view(handle)];
} }
void minyar_macos_hidden(long long handle, bool hidden) { @autoreleasepool {
    MNHandle *h = entry(handle); NSView *v = view(handle);
    if (v.hidden == hidden) return;
    v.hidden = hidden;
    // A hidden spinner stops, so an idle application does no animation work.
    if ([v isKindOfClass:NSProgressIndicator.class]) {
        if (hidden) [(NSProgressIndicator *)v stopAnimation:nil]; else [(NSProgressIndicator *)v startAnimation:nil];
    }
    if (hidden && h.hovering) { h.hovering = NO; restyle(h); }
} }
void minyar_macos_clear(long long handle) { @autoreleasepool {
    id o = entry(handle).object;
    if ([o isKindOfClass:MNList.class]) { [(MNList *)o clearRows]; return; }
    NSStackView *s = container(o);
    if (!s) minyar_native_stop("macos.clear requires a row, column, or scroll view.");
    forget(s, NO);
    for (NSView *child in [s.views copy]) [s removeView:child];
    for (NSView *child in [s.subviews copy]) [child removeFromSuperview];
} }
void minyar_macos_remove(long long handle) { @autoreleasepool {
    NSView *v = view(handle);
    if ([v.superview isKindOfClass:NSStackView.class]) [(NSStackView *)v.superview removeView:v];
    else if (v.window && v == v.window.contentView.subviews.firstObject) minyar_native_stop("macos.remove cannot remove a window's root view.");
    forget(v, YES);
    [v removeFromSuperview];
} }

/* ----- Lists -----
 * A list keeps its rows as text and lets NSTableView build views only for the
 * rows on screen, reusing them while scrolling. Rebuilding a list of any length
 * costs one string copy per line instead of a stack of laid-out views per row.
 * The table shows a snapshot of the rows taken when nextEvent reloads it, so
 * AppKit never sees rows that the program is still changing. */

@implementation MNListRow
@end
@implementation MNListStyle
@end
@interface MNListCell : NSTableCellView
@property(nonatomic, strong) NSTextField *top, *middle, *bottom;
@property(nonatomic, strong) NSButton *button;
@property(nonatomic, strong) NSLayoutConstraint *leadingEdge, *topEdge, *bottomEdge, *buttonEdge, *textEdge;
@end
@implementation MNListCell
@end
@interface MNListRowView : NSTableRowView
@property(nonatomic, strong) NSColor *hoverBackground, *separator;
@property(nonatomic) BOOL hovering;
@end
@implementation MNListRowView
- (void)mouseEntered:(NSEvent *)event { (void)event; self.hovering = YES; self.needsDisplay = YES; }
- (void)mouseExited:(NSEvent *)event { (void)event; self.hovering = NO; self.needsDisplay = YES; }
- (void)prepareForReuse { [super prepareForReuse]; self.hovering = NO; }
- (void)drawBackgroundInRect:(NSRect)dirtyRect {
    (void)dirtyRect;
    NSTableView *table = (NSTableView *)self.superview;
    BOOL enabled = ![table isKindOfClass:NSTableView.class] || table.isEnabled;
    if (self.hovering && self.hoverBackground && enabled) { [self.hoverBackground setFill]; NSRectFill(self.bounds); }
    if (self.separator) { [self.separator setFill]; NSRectFill(NSMakeRect(0, NSHeight(self.bounds) - 1, NSWidth(self.bounds), 1)); }
}
- (void)drawSelectionInRect:(NSRect)dirtyRect { (void)dirtyRect; }
@end

@implementation MNList
- (NSInteger)numberOfRowsInTableView:(NSTableView *)table { (void)table; return (NSInteger)self.shown.count; }
- (NSTableRowView *)tableView:(NSTableView *)table rowViewForRow:(NSInteger)row {
    (void)row;
    MNListRowView *view = [table makeViewWithIdentifier:@"MNListRowView" owner:self];
    if (!view) { view = [MNListRowView new]; view.identifier = @"MNListRowView"; track(view); }
    view.hoverBackground = self.hoverBackground; view.separator = self.separator;
    return view;
}
static NSTextField *listLabel(void) {
    NSTextField *label = [NSTextField labelWithString:@""];
    label.selectable = NO; label.translatesAutoresizingMaskIntoConstraints = NO;
    [label setContentCompressionResistancePriority:NSLayoutPriorityDefaultLow forOrientation:NSLayoutConstraintOrientationHorizontal];
    return label;
}
static void styleListLabel(NSTextField *label, MNListStyle *style, NSString *text) {
    label.hidden = text.length == 0;
    if (style.font) label.font = style.font;
    label.textColor = style.color ?: NSColor.labelColor;
    wrapLabel(label, style.lines);
    label.stringValue = text;
}
- (NSView *)tableView:(NSTableView *)table viewForTableColumn:(NSTableColumn *)column row:(NSInteger)row {
    (void)column;
    MNListCell *cell = [table makeViewWithIdentifier:@"MNListCell" owner:self];
    if (!cell && self.spareCells.count) { cell = self.spareCells.lastObject; [self.spareCells removeLastObject]; }
    if (!cell) {
        cell = [MNListCell new]; cell.identifier = @"MNListCell";
        cell.top = listLabel(); cell.middle = listLabel(); cell.bottom = listLabel();
        NSStackView *text = [NSStackView stackViewWithViews:@[cell.top, cell.middle, cell.bottom]];
        text.orientation = NSUserInterfaceLayoutOrientationVertical; text.alignment = NSLayoutAttributeLeading;
        text.spacing = 6; text.detachesHiddenViews = YES; text.translatesAutoresizingMaskIntoConstraints = NO;
        [cell addSubview:text];
        cell.button = [NSButton buttonWithTitle:@"" target:self action:@selector(rowButton:)];
        cell.button.bordered = NO; cell.button.imagePosition = NSImageOnly; cell.button.translatesAutoresizingMaskIntoConstraints = NO;
        [cell addSubview:cell.button];
        cell.leadingEdge = [text.leadingAnchor constraintEqualToAnchor:cell.leadingAnchor];
        cell.topEdge = [text.topAnchor constraintEqualToAnchor:cell.topAnchor];
        cell.bottomEdge = [text.bottomAnchor constraintEqualToAnchor:cell.bottomAnchor];
        // With a button the text ends 15 points before it; without, at the inset.
        cell.buttonEdge = [cell.button.trailingAnchor constraintEqualToAnchor:cell.trailingAnchor];
        cell.textEdge = [text.trailingAnchor constraintEqualToAnchor:cell.trailingAnchor];
        [NSLayoutConstraint activateConstraints:@[cell.leadingEdge, cell.topEdge, cell.bottomEdge,
            [cell.button.leadingAnchor constraintEqualToAnchor:text.trailingAnchor constant:15],
            [cell.button.centerYAnchor constraintEqualToAnchor:cell.centerYAnchor],
            [cell.button.widthAnchor constraintEqualToConstant:34], [cell.button.heightAnchor constraintEqualToConstant:34]]];
        for (NSTextField *label in @[cell.top, cell.middle, cell.bottom])
            [label.widthAnchor constraintEqualToAnchor:text.widthAnchor].active = YES;
    }
    NSEdgeInsets e = self.insets;
    cell.leadingEdge.constant = e.left; cell.topEdge.constant = e.top; cell.bottomEdge.constant = -e.bottom;
    cell.buttonEdge.constant = -e.right; cell.textEdge.constant = -e.right;
    BOOL button = self.buttonImage != nil;
    cell.button.hidden = !button;
    // Deactivate before activating, so the two trailing edges never conflict.
    if (button) { cell.textEdge.active = NO; cell.buttonEdge.active = YES; }
    else { cell.buttonEdge.active = NO; cell.textEdge.active = YES; }
    MNListRow *r = self.shown[(NSUInteger)row];
    styleListLabel(cell.top, self.styles[0], r.top);
    styleListLabel(cell.middle, self.styles[1], r.middle);
    styleListLabel(cell.bottom, self.styles[2], r.bottom);
    if (button) {
        cell.button.image = self.buttonImage;
        cell.button.toolTip = self.buttonTip.length ? [NSString stringWithFormat:@"%@ %@", self.buttonTip, r.middle.length ? r.middle : r.top] : nil;
        cell.button.accessibilityLabel = cell.button.toolTip;
        cell.button.contentTintColor = self.buttonColor;
        cell.button.enabled = table.isEnabled;
    }
    return cell;
}
/* Each click carries its own row, so queued clicks report the rows clicked. */
- (void)rowClicked:(id)sender {
    (void)sender;
    NSInteger row = self.table.clickedRow;
    if (row >= 0 && self.table.isEnabled) enqueueRow(identifier(self), row, NO);
}
- (void)rowButton:(NSButton *)sender {
    NSInteger row = [self.table rowForView:sender];
    if (row >= 0 && self.table.isEnabled) enqueueRow(identifier(self), row, YES);
}
// Adding rows only records text; nextEvent reloads each changed list once.
- (void)scheduleReload {
    if (!pendingLists) pendingLists = [NSMutableSet new];
    [pendingLists addObject:self];
}
/* reloadData drops the cells on screen instead of queueing them for reuse,
 * so a list refilled on every keystroke would build each visible row again.
 * Take those cells out of their rows and hand them back when the table asks
 * for new ones; every request configures a cell completely. */
- (void)reload {
    self.shown = [self.rows copy];
    NSMutableArray *cells = [NSMutableArray new];
    [self.table enumerateAvailableRowViewsUsingBlock:^(NSTableRowView *rowView, NSInteger row) {
        (void)row;
        NSView *cell = rowView.numberOfColumns ? [rowView viewAtColumn:0] : nil;
        if ([cell isKindOfClass:MNListCell.class]) { [cell removeFromSuperview]; [cells addObject:cell]; }
    }];
    self.spareCells = cells;
    [self.table reloadData];
}
/* clear ends the rows, and with them any clicks on them still queued. */
- (void)clearRows {
    [self.rows removeAllObjects]; [self scheduleReload];
    long long source = identifier(self);
    dropEvents(^BOOL(MNEvent *e) { return e.source == source; });
}
- (void)insetRows:(NSEdgeInsets)insets { self.insets = insets; [self scheduleReload]; }
- (void)enableRows:(BOOL)enabled {
    if (self.table.isEnabled == enabled) return;
    self.table.enabled = enabled; self.alphaValue = enabled ? 1 : MNDisabledAlpha; [self scheduleReload];
}
@end

static void reloadLists(void) {
    NSSet<MNList *> *lists = pendingLists; pendingLists = nil;
    for (MNList *l in lists) [l reload];
}
static MNList *list(long long handle) { return object(handle, MNList.class); }
long long minyar_macos_list(long long parent) { @autoreleasepool {
    ready();
    MNList *l = [MNList new];
    l.drawsBackground = NO; l.borderType = NSNoBorder; l.hasVerticalScroller = YES; l.autohidesScrollers = YES;
    l.rows = [NSMutableArray new]; l.shown = @[];
    NSMutableArray *styles = [NSMutableArray new];
    for (int i = 0; i < 3; ++i) { MNListStyle *style = [MNListStyle new]; style.lines = i == 1 ? 0 : 1; [styles addObject:style]; }
    l.styles = styles;
    l.insets = NSEdgeInsetsMake(15, 18, 15, 18);
    NSTableView *t = [NSTableView new];
    NSTableColumn *column = [[NSTableColumn alloc] initWithIdentifier:@"row"];
    column.resizingMask = NSTableColumnAutoresizingMask;
    [t addTableColumn:column];
    t.headerView = nil; t.backgroundColor = NSColor.clearColor; t.style = NSTableViewStylePlain;
    t.intercellSpacing = NSZeroSize; t.usesAutomaticRowHeights = YES; t.columnAutoresizingStyle = NSTableViewUniformColumnAutoresizingStyle;
    t.selectionHighlightStyle = NSTableViewSelectionHighlightStyleNone; t.gridStyleMask = NSTableViewGridNone;
    t.dataSource = l; t.delegate = l; t.target = l; t.action = @selector(rowClicked:);
    l.documentView = t; l.table = t;
    l.contentView.drawsBackground = NO;
    return append(parent, l);
} }
void minyar_macos_addRow(long long handle, const MinyarText *top, const MinyarText *middle, const MinyarText *bottom) { @autoreleasepool {
    MNList *l = list(handle);
    if (l.rows.count >= 10000000) minyar_native_stop("macos lists hold at most 10000000 rows.");
    MNListRow *r = [MNListRow new]; r.top = string(top); r.middle = string(middle); r.bottom = string(bottom);
    [l.rows addObject:r];
    [l scheduleReload];
} }
long long minyar_macos_rowCount(long long handle) { @autoreleasepool { return (long long)list(handle).rows.count; } }
void minyar_macos_listLine(long long handle, long long line, const MinyarText *family, double size, double weight, long long textColor, long long lines) { @autoreleasepool {
    MNList *l = list(handle);
    if (line < 0 || line > 2) minyar_native_stop("macos list lines are 0 (top), 1 (middle) and 2 (bottom).");
    checkFont(size, weight); checkLines(lines);
    MNListStyle *style = l.styles[(NSUInteger)line];
    style.font = resolveFont(string(family), size, weight); style.color = color(textColor); style.lines = lines;
    [l scheduleReload];
} }
void minyar_macos_listColors(long long handle, long long hoverBackground, long long separator) { @autoreleasepool {
    MNList *l = list(handle); l.hoverBackground = color(hoverBackground); l.separator = color(separator);
    [l scheduleReload];
} }
void minyar_macos_rowButton(long long handle, const MinyarText *symbol, const MinyarText *tooltip, long long tint) { @autoreleasepool {
    MNList *l = list(handle); NSString *name = string(symbol);
    l.buttonImage = name.length ? symbolImage(name, 15) : nil;
    l.buttonTip = string(tooltip); l.buttonColor = color(tint);
    [l scheduleReload];
} }
static BOOL fromList(long long handle) { list(handle); return current && current.source == handle && current.row >= 0; }
long long minyar_macos_clickedRow(long long handle) { @autoreleasepool { return fromList(handle) ? current.row : -1; } }
bool minyar_macos_clickedButton(long long handle) { @autoreleasepool { return fromList(handle) && current.button; } }

/* ----- Styling ----- */

long long minyar_macos_color(long long dark, long long light, double opacity) { @autoreleasepool {
    ready();
    if (dark < 0 || dark > 0xFFFFFF || light < 0 || light > 0xFFFFFF) minyar_native_stop("macos colors are 0xRRGGBB values.");
    if (!isfinite(opacity) || opacity < 0 || opacity > 1) minyar_native_stop("macos color opacity must be between 0 and 1.");
    NSColor *(^make)(long long) = ^NSColor *(long long rgb) {
        return [NSColor colorWithSRGBRed:((rgb >> 16) & 255) / 255.0 green:((rgb >> 8) & 255) / 255.0 blue:(rgb & 255) / 255.0 alpha:opacity];
    };
    NSColor *d = make(dark), *l = make(light);
    NSColor *c = [NSColor colorWithName:nil dynamicProvider:^NSColor *(NSAppearance *appearance) {
        return [appearance bestMatchFromAppearancesWithNames:@[NSAppearanceNameAqua, NSAppearanceNameDarkAqua]] == NSAppearanceNameDarkAqua ? d : l;
    }];
    return registerObject(c, 0);
} }
void minyar_macos_background(long long handle, long long fill) { @autoreleasepool {
    MNHandle *h = entry(handle); h.background = color(fill);
    if ([h.object isKindOfClass:NSWindow.class] && !fill) [h.object setBackgroundColor:NSColor.windowBackgroundColor];
    restyle(h);
} }
void minyar_macos_border(long long handle, long long width, long long edge) { @autoreleasepool {
    dimension(width); MNHandle *h = entry(handle); view(handle); h.borderWidth = width; h.borderColor = color(edge); restyle(h);
} }
void minyar_macos_cornerRadius(long long handle, long long radius) { @autoreleasepool {
    dimension(radius); MNHandle *h = entry(handle); view(handle); h.radius = radius; restyle(h);
} }
void minyar_macos_focusBorder(long long handle, long long edge) { @autoreleasepool {
    MNHandle *h = entry(handle); view(handle); h.focusBorder = color(edge);
    if ([h.object window]) updateFocus([h.object window]);
    restyle(h);
} }
void minyar_macos_textColor(long long handle, long long fill) { @autoreleasepool {
    MNHandle *h = entry(handle); h.foreground = color(fill); h.styledText = YES; restyle(h);
} }
void minyar_macos_hover(long long handle, long long foreground, long long fill) { @autoreleasepool {
    MNHandle *h = entry(handle);
    if (![h.object isKindOfClass:MNButton.class] && ![h.object isKindOfClass:MNStack.class])
        minyar_native_stop("macos.hover requires a button, row, or column.");
    h.hoverForeground = color(foreground); h.hoverBackground = color(fill);
    if (h.hoverForeground) h.styledText = YES;
    restyle(h);
} }
void minyar_macos_font(long long handle, const MinyarText *family, double size, double weight) { @autoreleasepool {
    MNHandle *h = entry(handle);
    checkFont(size, weight);
    h.font = resolveFont(string(family), size, weight);
    h.styledText = YES; restyle(h);
} }
static void checkFont(double size, double weight) {
    if (!isfinite(size) || size < 1 || size > 1000 || !isfinite(weight) || weight < 1 || weight > 1000)
        minyar_native_stop("macos fonts need a size from 1 to 1000 points and a weight from 1 to 1000.");
}
static void checkLines(long long count) {
    if (count < 0 || count > 100000) minyar_native_stop("macos label lines must be between 0 and 100000.");
}
static NSFont *resolveFont(NSString *name, double size, double weight) {
    NSFont *font = nil;
    if (name.length) {
        NSFontDescriptor *d = [NSFontDescriptor fontDescriptorWithFontAttributes:@{NSFontFamilyAttribute: name}];
        font = [NSFont fontWithDescriptor:d size:size];
        if (font && ![font.familyName isEqualToString:name]) font = nil;
        if (font) {
            NSArray *axes = CFBridgingRelease(CTFontCopyVariationAxes((__bridge CTFontRef)font));
            BOOL variable = NO;
            for (NSDictionary *axis in axes)
                if ([axis[(NSString *)kCTFontVariationAxisIdentifierKey] longLongValue] == 0x77676874) variable = YES;
            NSDictionary *style = variable
                ? @{(NSString *)kCTFontVariationAttribute: @{@0x77676874: @(weight)}}
                : @{NSFontTraitsAttribute: @{NSFontWeightTrait: @(fontWeight(weight))}};
            font = [NSFont fontWithDescriptor:[d fontDescriptorByAddingAttributes:style] size:size] ?: font;
        }
    }
    return font ?: [NSFont systemFontOfSize:size weight:fontWeight(weight)];
}
void minyar_macos_letterSpacing(long long handle, double points) { @autoreleasepool {
    if (!isfinite(points) || fabs(points) > 100) minyar_native_stop("macos letter spacing must be between -100 and 100 points.");
    MNHandle *h = entry(handle); h.kerning = points; h.styledText = YES; restyle(h);
} }
void minyar_macos_lineHeight(long long handle, double multiple) { @autoreleasepool {
    if (!isfinite(multiple) || multiple < 0 || multiple > 10) minyar_native_stop("macos line height must be a multiple from 0 to 10.");
    MNHandle *h = entry(handle); h.lineHeight = multiple; h.styledText = YES; restyle(h);
} }
void minyar_macos_lines(long long handle, long long count) { @autoreleasepool {
    MNHandle *h = entry(handle);
    if (![h.object isKindOfClass:NSTextField.class] || [h.object isEditable]) minyar_native_stop("macos.lines requires a label.");
    checkLines(count);
    h.lines = count; h.styledText = YES; restyle(h);
} }
void minyar_macos_selectable(long long handle, bool value) { @autoreleasepool {
    if ([entry(handle).object isKindOfClass:MNTextBlock.class]) { [entry(handle).object setSelectable:value]; return; }
    NSTextField *f = object(handle, NSTextField.class); f.selectable = value;
    MNHandle *h = entry(handle); if (h.styledText) applyText(h);
} }
void minyar_macos_accessibilityLabel(long long handle, const MinyarText *text) { @autoreleasepool {
    NSView *v = view(handle);
    (editor(v) ?: v).accessibilityLabel = string(text);
} }
void minyar_macos_textAlign(long long handle, long long alignment) { @autoreleasepool {
    MNHandle *h = entry(handle); id v = h.object;
    if (alignment < MNStart || alignment > MNEnd) minyar_native_stop("macos text alignment must be START, CENTER, or END.");
    NSTextAlignment a = alignment == MNStart ? NSTextAlignmentNatural : alignment == MNCenter ? NSTextAlignmentCenter : NSTextAlignmentRight;
    if ([v isKindOfClass:NSButton.class] || [v isKindOfClass:NSTextField.class]) [v setAlignment:a];
    else if (textView(v)) textView(v).alignment = a;
    else minyar_native_stop("macos.textAlign requires a button, label, text field, or editor.");
    if (h.styledText) applyText(h);
} }
void minyar_macos_tooltip(long long handle, const MinyarText *text) { @autoreleasepool {
    NSView *v = view(handle); v.toolTip = string(text);
    if ([v isKindOfClass:NSButton.class] && ![(NSButton *)v title].length) v.accessibilityLabel = v.toolTip;
} }

/* ----- Controls ----- */

long long minyar_macos_plainButton(long long parent, const MinyarText *title) { @autoreleasepool {
    ready(); MNButton *b = [MNButton buttonWithTitle:string(title) target:delegate action:@selector(action:)];
    b.bordered = NO; [b setButtonType:NSButtonTypeMomentaryChange];
    b.imageHugsTitle = YES;
    return append(parent, b);
} }
long long minyar_macos_link(long long parent, const MinyarText *title, const MinyarText *url) { @autoreleasepool {
    ready(); NSURL *u = [NSURL URLWithString:string(url)];
    if (!u || !([u.scheme isEqualToString:@"https"] || [u.scheme isEqualToString:@"http"]) || !u.host.length)
        minyar_native_stop("macos links must be http or https URLs.");
    long long h = minyar_macos_plainButton(parent, title);
    MNButton *b = entry(h).object; b.url = u; b.toolTip = u.absoluteString;
    return h;
} }
static NSImage *symbolImage(NSString *name, double size) {
    NSImage *image = [NSImage imageWithSystemSymbolName:name accessibilityDescription:nil];
    if (!image) minyar_native_stop("macos could not find that SF Symbol.");
    return [image imageWithSymbolConfiguration:[NSImageSymbolConfiguration configurationWithPointSize:size weight:NSFontWeightRegular]];
}
void minyar_macos_symbol(long long handle, const MinyarText *name, double size) { @autoreleasepool {
    NSButton *b = object(handle, NSButton.class);
    if (!isfinite(size) || size < 1 || size > 1000) minyar_native_stop("macos symbol sizes must be between 1 and 1000 points.");
    b.image = symbolImage(string(name), size);
    b.imagePosition = b.title.length ? NSImageLeading : NSImageOnly;
    MNHandle *h = entry(handle); if (h.foreground) b.contentTintColor = textColorOf(h);
} }
static double svgNumber(NSScanner *s, BOOL *ok) {
    double value = 0;
    [s scanCharactersFromSet:[NSCharacterSet characterSetWithCharactersInString:@" ,\n\t\r"] intoString:NULL];
    *ok = *ok && [s scanDouble:&value];
    return value;
}
long long minyar_macos_shape(long long parent, const MinyarText *path, double boxWidth, double boxHeight) { @autoreleasepool {
    ready();
    if (!isfinite(boxWidth) || !isfinite(boxHeight) || boxWidth <= 0 || boxHeight <= 0) minyar_native_stop("macos shapes need a positive view box.");
    // SVG path data with M, L, H, V, Q, C and Z commands, absolute or relative.
    NSScanner *s = [NSScanner scannerWithString:string(path)];
    s.charactersToBeSkipped = nil;
    NSCharacterSet *separators = [NSCharacterSet characterSetWithCharactersInString:@" ,\n\t\r"];
    NSCharacterSet *commands = [NSCharacterSet characterSetWithCharactersInString:@"MmLlHhVvQqCcZz"];
    NSBezierPath *p = [NSBezierPath bezierPath];
    NSPoint at = NSZeroPoint, start = NSZeroPoint;
    unichar command = 0; BOOL ok = YES;
    while (ok) {
        [s scanCharactersFromSet:separators intoString:NULL];
        if (s.isAtEnd) break;
        NSString *letter = nil;
        if ([s scanCharactersFromSet:commands intoString:&letter]) {
            if (letter.length != 1) { ok = NO; break; }
            command = [letter characterAtIndex:0];
            if (command == 'Z' || command == 'z') { [p closePath]; at = start; continue; }
        } else if (!command || command == 'Z' || command == 'z') { ok = NO; break; }
        BOOL relative = command >= 'a';
        NSPoint base = relative ? at : NSZeroPoint;
        switch (command | 0x20) {
        case 'm': {
            double x = svgNumber(s, &ok), y = svgNumber(s, &ok);
            at = start = NSMakePoint(base.x + x, base.y + y); [p moveToPoint:at];
            command = relative ? 'l' : 'L'; break;
        }
        case 'l': { double x = svgNumber(s, &ok), y = svgNumber(s, &ok); at = NSMakePoint(base.x + x, base.y + y); [p lineToPoint:at]; break; }
        case 'h': { double x = svgNumber(s, &ok); at.x = (relative ? at.x : 0) + x; [p lineToPoint:at]; break; }
        case 'v': { double y = svgNumber(s, &ok); at.y = (relative ? at.y : 0) + y; [p lineToPoint:at]; break; }
        case 'q': {
            double qx = svgNumber(s, &ok), qy = svgNumber(s, &ok), x = svgNumber(s, &ok), y = svgNumber(s, &ok);
            NSPoint q = NSMakePoint(base.x + qx, base.y + qy), end = NSMakePoint(base.x + x, base.y + y);
            [p curveToPoint:end controlPoint1:NSMakePoint(at.x + 2.0 / 3 * (q.x - at.x), at.y + 2.0 / 3 * (q.y - at.y))
                controlPoint2:NSMakePoint(end.x + 2.0 / 3 * (q.x - end.x), end.y + 2.0 / 3 * (q.y - end.y))];
            at = end; break;
        }
        case 'c': {
            double x1 = svgNumber(s, &ok), y1 = svgNumber(s, &ok), x2 = svgNumber(s, &ok), y2 = svgNumber(s, &ok), x = svgNumber(s, &ok), y = svgNumber(s, &ok);
            NSPoint end = NSMakePoint(base.x + x, base.y + y);
            [p curveToPoint:end controlPoint1:NSMakePoint(base.x + x1, base.y + y1) controlPoint2:NSMakePoint(base.x + x2, base.y + y2)];
            at = end; break;
        }
        default: ok = NO;
        }
    }
    if (!ok || p.isEmpty) minyar_native_stop("macos shape paths support SVG M, L, H, V, Q, C and Z commands.");
    MNShape *v = [MNShape new]; v.path = p; v.box = NSMakeSize(boxWidth, boxHeight);
    return append(parent, v);
} }
long long minyar_macos_spinner(long long parent) { @autoreleasepool {
    ready(); NSProgressIndicator *v = [NSProgressIndicator new];
    v.style = NSProgressIndicatorStyleSpinning; v.controlSize = NSControlSizeSmall; v.indeterminate = YES;
    [v startAnimation:nil];
    return append(parent, v);
} }
void minyar_macos_placeholder(long long handle, const MinyarText *text) { @autoreleasepool {
    id v = entry(handle).object;
    if (editor(v) && [editor(v) isKindOfClass:MNTextView.class]) { [(MNTextView *)editor(v) setPlaceholder:string(text)]; editor(v).needsDisplay = YES; return; }
    if ([v isKindOfClass:NSTextField.class] && [v isEditable]) { [v setPlaceholderString:string(text)]; return; }
    minyar_native_stop("macos.placeholder requires a text field or editor.");
} }
void minyar_macos_plain(long long handle) { @autoreleasepool {
    MNHandle *h = entry(handle); id v = h.object;
    if (editor(v)) {
        NSScrollView *s = v; NSTextView *t = editor(v);
        s.borderType = NSNoBorder; s.drawsBackground = NO; t.drawsBackground = NO;
        t.textContainerInset = NSZeroSize; t.textContainer.lineFragmentPadding = 0;
        t.focusRingType = NSFocusRingTypeNone; s.focusRingType = NSFocusRingTypeNone;
        replaceMinimum(h, s, 0, 0);
        return;
    }
    if ([v isKindOfClass:NSTextField.class] && [v isEditable]) {
        NSTextField *f = v; f.bezeled = NO; f.bordered = NO; f.drawsBackground = NO; f.focusRingType = NSFocusRingTypeNone;
        replaceMinimum(h, f, 0, 0);
        return;
    }
    minyar_native_stop("macos.plain requires a text field or editor.");
} }
void minyar_macos_autoHeight(long long handle, long long minimum, long long maximum) { @autoreleasepool {
    MNHandle *h = entry(handle);
    if (!editor(h.object)) minyar_native_stop("macos.autoHeight requires a text editor.");
    dimension(minimum); dimension(maximum);
    if (!maximum || minimum > maximum) minyar_native_stop("macos.autoHeight needs a minimum no larger than a positive maximum.");
    h.autoMinimum = minimum; h.autoMaximum = maximum;
    replaceMinimum(h, h.object, h.minimumWidth ? (long long)h.minimumWidth.constant : 0, 0);
    h.height.active = NO;
    h.height = [[h.object heightAnchor] constraintEqualToConstant:minimum]; h.height.active = YES;
    fitHeight(h);
} }
void minyar_macos_submitOnEnter(long long handle) { @autoreleasepool {
    MNHandle *h = entry(handle);
    if (!editor(h.object)) minyar_native_stop("macos.submitOnEnter requires a text editor; text fields always submit on Return.");
    h.submitOnEnter = YES;
} }
void minyar_macos_maxLength(long long handle, long long count) { @autoreleasepool {
    MNHandle *h = entry(handle);
    if (!editor(h.object) && !([h.object isKindOfClass:NSTextField.class] && [h.object isEditable]))
        minyar_native_stop("macos.maxLength requires a text field or editor.");
    if (count < 0) minyar_native_stop("macos.maxLength must not be negative.");
    h.maxLength = count;
} }
void minyar_macos_focus(long long handle) { @autoreleasepool {
    NSView *v = view(handle);
    if (!v.window) return;
    [v.window makeFirstResponder:editor(v) ?: v];
} }
void minyar_macos_clickable(long long handle) { @autoreleasepool {
    MNStack *s = object(handle, MNStack.class); s.clickable = YES; s.draggable = NO;
} }
void minyar_macos_draggable(long long handle) { @autoreleasepool {
    MNStack *s = object(handle, MNStack.class); s.draggable = YES; s.clickable = NO;
} }

/* ----- Windows ----- */

void minyar_macos_transparentTitlebar(long long handle, long long height) { @autoreleasepool {
    NSWindow *w = object(handle, NSWindow.class); dimension(height);
    w.styleMask |= NSWindowStyleMaskFullSizeContentView;
    w.titlebarAppearsTransparent = YES; w.titleVisibility = NSWindowTitleHidden;
    entry(handle).titlebarHeight = height;
    placeTrafficLights(w);
    NSButton *close = [w standardWindowButton:NSWindowCloseButton];
    NSMutableArray<NSView *> *watched = [NSMutableArray arrayWithObjects:close.superview.superview ?: close, nil];
    for (NSNumber *kind in @[@(NSWindowCloseButton), @(NSWindowMiniaturizeButton), @(NSWindowZoomButton)])
        [watched addObject:[w standardWindowButton:kind.unsignedIntegerValue]];
    for (NSView *v in watched) {
        v.postsFrameChangedNotifications = YES;
        [NSNotificationCenter.defaultCenter addObserver:delegate selector:@selector(titlebarFrameDidChange:) name:NSViewFrameDidChangeNotification object:v];
    }
} }
void minyar_macos_autosave(long long handle, const MinyarText *name) { @autoreleasepool {
    NSWindow *w = object(handle, NSWindow.class); [w setFrameAutosaveName:string(name)];
} }

/* ----- Application ----- */

void minyar_macos_appearance(long long mode) { @autoreleasepool {
    ready();
    if (mode < 0 || mode > 2) minyar_native_stop("macos appearance must be SYSTEM, DARK, or LIGHT.");
    NSApp.appearance = mode == 0 ? nil : [NSAppearance appearanceNamed:mode == 1 ? NSAppearanceNameDarkAqua : NSAppearanceNameAqua];
    restyleAll();
} }
bool minyar_macos_isDark(void) { @autoreleasepool {
    ready();
    return [NSApp.effectiveAppearance bestMatchFromAppearancesWithNames:@[NSAppearanceNameAqua, NSAppearanceNameDarkAqua]] == NSAppearanceNameDarkAqua;
} }
MinyarText *minyar_macos_setting(const MinyarText *key) { @autoreleasepool {
    ready(); return owned([NSUserDefaults.standardUserDefaults stringForKey:string(key)]);
} }
void minyar_macos_setSetting(const MinyarText *key, const MinyarText *value) { @autoreleasepool {
    ready(); [NSUserDefaults.standardUserDefaults setObject:string(value) forKey:string(key)];
} }
bool minyar_macos_openURL(const MinyarText *url) { @autoreleasepool {
    ready(); NSURL *u = [NSURL URLWithString:string(url)];
    if (!u || !([u.scheme isEqualToString:@"https"] || [u.scheme isEqualToString:@"http"] || [u.scheme isEqualToString:@"mailto"])) return false;
    return [NSWorkspace.sharedWorkspace openURL:u];
} }
double minyar_macos_seconds(void) { return NSProcessInfo.processInfo.systemUptime; }
MinyarText *minyar_macos_resource(const MinyarText *name) { @autoreleasepool {
    NSString *path = [NSBundle.mainBundle.resourcePath stringByAppendingPathComponent:string(name)];
    return owned([NSFileManager.defaultManager fileExistsAtPath:path] ? path : @"");
} }
bool minyar_macos_registerFont(const MinyarText *path) { @autoreleasepool {
    NSString *p = string(path);
    if (!p.length) return false;
    CFErrorRef error = NULL;
    bool ok = CTFontManagerRegisterFontsForURL((__bridge CFURLRef)[NSURL fileURLWithPath:p], kCTFontManagerScopeProcess, &error);
    if (error) {
        ok = CFErrorGetCode(error) == kCTFontManagerErrorAlreadyRegistered;
        CFRelease(error);
    }
    return ok;
} }
void minyar_macos_aboutText(const MinyarText *text) { @autoreleasepool { ready(); aboutCredits = string(text); } }
void minyar_macos_showAbout(void) { @autoreleasepool { ready(); [delegate showAbout:nil]; } }
bool minyar_macos_confirm(const MinyarText *title, const MinyarText *message, const MinyarText *action) { @autoreleasepool {
    ready(); NSAlert *a = [NSAlert new]; a.messageText = string(title); a.informativeText = string(message);
    a.alertStyle = NSAlertStyleWarning;
    NSButton *confirm = [a addButtonWithTitle:string(action)]; confirm.hasDestructiveAction = YES;
    [a addButtonWithTitle:@"Cancel"];
    return [a runModal] == NSAlertFirstButtonReturn;
} }
bool minyar_macos_capture(long long handle, const MinyarText *path) { @autoreleasepool {
    NSWindow *w = object(handle, NSWindow.class);
    NSView *frame = w.contentView.superview ?: w.contentView;
    [frame layoutSubtreeIfNeeded];
    NSBitmapImageRep *rep = [frame bitmapImageRepForCachingDisplayInRect:frame.bounds];
    if (!rep) return false;
    [frame cacheDisplayInRect:frame.bounds toBitmapImageRep:rep];
    return [[rep representationUsingType:NSBitmapImageFileTypePNG properties:@{}] writeToFile:string(path) atomically:YES];
} }
