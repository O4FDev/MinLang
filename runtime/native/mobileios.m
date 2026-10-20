#import <UIKit/UIKit.h>
#include "../minyar_native.h"
#include "mobile-callback.h"

@interface MinyarMobileNode : NSObject
@property(nonatomic) NSInteger parent, kind, spacing, padding, depth;
@property(nonatomic, copy) NSString *key, *text;
@property(nonatomic) BOOL checked;
@property(nonatomic, strong) UIView *container, *content;
@end
@implementation MinyarMobileNode
@end

@interface MinyarMobileDelegate : UIResponder <UIApplicationDelegate, UITextFieldDelegate>
@property(nonatomic, strong) UIWindow *window;
- (void)action:(UIControl *)sender;
@end

static void *mobile_session;
static BOOL mobile_started, mobile_applying, mobile_dispatching;
static NSString *mobile_title, *mobile_event_key, *mobile_event_text;
static BOOL mobile_event_checked;
static NSMutableArray<MinyarMobileNode *> *mobile_pending;
static NSArray<MinyarMobileNode *> *mobile_nodes;
static UIScrollView *mobile_scroll;
static CFRunLoopObserverRef mobile_observer;
static NSTimer *mobile_cleanup;

static void mobile_main_thread(void) {
    if (![NSThread isMainThread]) minyar_native_stop("mobile UI calls belong to the main thread.");
}
static NSString *mobile_string(const MinyarText *text) {
    if (text->byte_length < 0) minyar_native_stop("invalid mobile text length.");
    NSString *value = [[NSString alloc] initWithBytes:text->bytes length:(NSUInteger)text->byte_length encoding:NSUTF8StringEncoding];
    if (!value) minyar_native_stop("mobile text must be valid UTF-8.");
    return value;
}
static MinyarText *mobile_text(NSString *text) {
    NSData *data = [(text ?: @"") dataUsingEncoding:NSUTF8StringEncoding];
    if (!data) minyar_native_stop("mobile event text could not be encoded as UTF-8.");
    return minyar_native_copy_text(data.bytes, (long long)data.length);
}

/* No repeating idle timer: a one-shot timer exists only while bounded or cycle
 * cleanup has outstanding work. Service runs on the creating UI domain. */
static void mobile_service(void) {
    long long wait = minyar_callbackruntime_serviceWait(-1);
    if (wait < 0) { [mobile_cleanup invalidate]; mobile_cleanup = nil; return; }
    if (!mobile_cleanup) {
        mobile_cleanup = [NSTimer timerWithTimeInterval:MAX(0.001, (double)wait / 1000.0) repeats:NO block:^(NSTimer *timer) {
            (void)timer;
            mobile_cleanup = nil;
            mobile_service();
        }];
        [[NSRunLoop mainRunLoop] addTimer:mobile_cleanup forMode:NSRunLoopCommonModes];
    }
}
static void mobile_before_wait(CFRunLoopObserverRef observer, CFRunLoopActivity activity, void *info) {
    (void)observer; (void)activity; (void)info;
    mobile_service();
}

static void mobile_emit(UIControl *sender, long long kind) {
    mobile_main_thread();
    if (mobile_applying || mobile_dispatching || sender.tag < 1 || (NSUInteger)sender.tag > mobile_nodes.count) return;
    MinyarMobileNode *node = mobile_nodes[(NSUInteger)sender.tag - 1];
    if (node.content != sender) return;
    mobile_event_key = node.key;
    mobile_event_text = [sender isKindOfClass:[UITextField class]] ? ((UITextField *)sender).text : @"";
    mobile_event_checked = [sender isKindOfClass:[UISwitch class]] && ((UISwitch *)sender).on;
    mobile_dispatching = YES;
    minyar_mobile_dispatch(mobile_session, kind);
    mobile_dispatching = NO;
    mobile_event_key = nil;
    mobile_event_text = nil;
    mobile_service();
}

static void mobile_properties(MinyarMobileNode *node) {
    node.container.layoutMargins = UIEdgeInsetsMake(node.padding, node.padding, node.padding, node.padding);
    if (node.kind == 6 || node.kind == 7) {
        ((UIStackView *)node.content).spacing = node.spacing;
    } else if (node.kind == 1 || node.kind == 2) {
        ((UILabel *)node.content).text = node.text;
    } else if (node.kind == 3) {
        UIButton *button = (UIButton *)node.content;
        UIButtonConfiguration *configuration = [UIButtonConfiguration filledButtonConfiguration];
        configuration.title = node.text;
        configuration.baseBackgroundColor = [UIColor systemTealColor];
        configuration.cornerStyle = UIButtonConfigurationCornerStyleMedium;
        button.configuration = configuration;
    } else if (node.kind == 4) {
        UITextField *input = (UITextField *)node.content;
        // Keep an IME's marked text intact until composition ends. When the
        // model changes ordinary text, preserve the clamped UTF-16 selection.
        if (![input.text isEqualToString:node.text] && !input.markedTextRange) {
            UITextRange *selection = input.selectedTextRange;
            NSInteger start = selection ? [input offsetFromPosition:input.beginningOfDocument toPosition:selection.start] : 0;
            NSInteger end = selection ? [input offsetFromPosition:input.beginningOfDocument toPosition:selection.end] : 0;
            input.text = node.text;
            if (selection) {
                NSInteger length = (NSInteger)input.text.length;
                UITextPosition *from = [input positionFromPosition:input.beginningOfDocument offset:MAX(0, MIN(start, length))];
                UITextPosition *to = [input positionFromPosition:input.beginningOfDocument offset:MAX(0, MIN(end, length))];
                if (from && to) input.selectedTextRange = [input textRangeFromPosition:from toPosition:to];
            }
        }
    } else if (node.kind == 5) {
        UISwitch *toggle = (UISwitch *)node.content;
        toggle.on = node.checked;
        toggle.accessibilityLabel = node.text;
        UIStackView *stack = (UIStackView *)node.container.subviews.firstObject;
        ((UILabel *)stack.arrangedSubviews.firstObject).text = node.text;
    }
}

static void mobile_create(MinyarMobileNode *node, NSInteger index) {
    UIView *inner;
    if (node.kind == 6 || node.kind == 7) {
        UIStackView *stack = [[UIStackView alloc] init];
        stack.axis = node.kind == 6 ? UILayoutConstraintAxisHorizontal : UILayoutConstraintAxisVertical;
        stack.alignment = UIStackViewAlignmentFill;
        inner = stack;
    } else if (node.kind == 1 || node.kind == 2) {
        UILabel *label = [[UILabel alloc] init];
        label.numberOfLines = 0;
        label.font = [UIFont preferredFontForTextStyle:node.kind == 2 ? UIFontTextStyleLargeTitle : UIFontTextStyleBody];
        label.adjustsFontForContentSizeCategory = YES;
        if (node.kind == 2) label.accessibilityTraits |= UIAccessibilityTraitHeader;
        inner = label;
    } else if (node.kind == 3) {
        UIButton *button = [UIButton buttonWithType:UIButtonTypeSystem];
        [button addTarget:UIApplication.sharedApplication.delegate action:@selector(action:) forControlEvents:UIControlEventTouchUpInside];
        inner = button;
    } else if (node.kind == 4) {
        UITextField *input = [[UITextField alloc] init];
        input.borderStyle = UITextBorderStyleRoundedRect;
        input.font = [UIFont preferredFontForTextStyle:UIFontTextStyleBody];
        input.adjustsFontForContentSizeCategory = YES;
        input.delegate = (id<UITextFieldDelegate>)UIApplication.sharedApplication.delegate;
        [input addTarget:UIApplication.sharedApplication.delegate action:@selector(action:) forControlEvents:UIControlEventEditingChanged];
        inner = input;
    } else {
        UISwitch *toggle = [[UISwitch alloc] init];
        [toggle addTarget:UIApplication.sharedApplication.delegate action:@selector(action:) forControlEvents:UIControlEventValueChanged];
        inner = toggle;
    }
    node.content = inner;
    node.content.tag = index;
    if (node.key.length) node.content.accessibilityIdentifier = node.key;
    node.container = [[UIView alloc] init];
    node.container.translatesAutoresizingMaskIntoConstraints = NO;
    node.container.insetsLayoutMarginsFromSafeArea = NO;
    UIView *layout = inner;
    if (node.kind == 5) {
        UILabel *label = [[UILabel alloc] init];
        label.font = [UIFont preferredFontForTextStyle:UIFontTextStyleBody];
        label.adjustsFontForContentSizeCategory = YES;
        label.numberOfLines = 0;
        UIStackView *stack = [[UIStackView alloc] initWithArrangedSubviews:@[label, inner]];
        stack.axis = UILayoutConstraintAxisHorizontal;
        stack.alignment = UIStackViewAlignmentCenter;
        stack.spacing = 12;
        layout = stack;
    }
    layout.translatesAutoresizingMaskIntoConstraints = NO;
    [node.container addSubview:layout];
    UILayoutGuide *guide = node.container.layoutMarginsGuide;
    [NSLayoutConstraint activateConstraints:@[
        [layout.leadingAnchor constraintEqualToAnchor:guide.leadingAnchor],
        [layout.trailingAnchor constraintEqualToAnchor:guide.trailingAnchor],
        [layout.topAnchor constraintEqualToAnchor:guide.topAnchor],
        [layout.bottomAnchor constraintEqualToAnchor:guide.bottomAnchor]
    ]];
    if (node.kind == 3 || node.kind == 4) [[inner.heightAnchor constraintGreaterThanOrEqualToConstant:44] setActive:YES];
    mobile_properties(node);
}

void minyar_mobileios_begin(void) {
    mobile_main_thread();
    if (!mobile_session || mobile_pending) minyar_native_stop("mobile.begin needs an active app and one complete snapshot at a time.");
    mobile_pending = [NSMutableArray array];
}
long long minyar_mobileios_node(long long parent, long long kind, MinyarText *key, MinyarText *text, bool checked, long long spacing, long long padding) {
    mobile_main_thread();
    if (!mobile_pending || mobile_pending.count >= 1024 || parent < 0 || (unsigned long long)parent > mobile_pending.count ||
        (parent == 0 && mobile_pending.count != 0) || kind < 1 || kind > 7 || spacing < 0 || spacing > 256 || padding < 0 || padding > 256)
        minyar_native_stop("invalid mobile view snapshot.");
    MinyarMobileNode *node = [[MinyarMobileNode alloc] init];
    node.parent = (NSInteger)parent; node.kind = (NSInteger)kind;
    node.spacing = (NSInteger)spacing; node.padding = (NSInteger)padding;
    node.key = mobile_string(key); node.text = mobile_string(text); node.checked = checked;
    node.depth = parent ? mobile_pending[(NSUInteger)parent - 1].depth + 1 : 1;
    if (node.depth > 64) minyar_native_stop("mobile views may be nested at most 64 levels deep.");
    if (parent && mobile_pending[(NSUInteger)parent - 1].kind < 6) minyar_native_stop("only a mobile row or column may contain children.");
    if (kind >= 3 && kind <= 5) {
        if (!node.key.length || key->byte_length > 256) minyar_native_stop("mobile controls need a key of 1 to 256 UTF-8 bytes.");
        for (MinyarMobileNode *prior in mobile_pending)
            if (prior.kind >= 3 && prior.kind <= 5 && [prior.key isEqualToString:node.key]) minyar_native_stop("mobile control keys must be unique.");
    }
    [mobile_pending addObject:node];
    return (long long)mobile_pending.count;
}
void minyar_mobileios_end(void) {
    mobile_main_thread();
    if (!mobile_pending.count || !mobile_scroll) minyar_native_stop("mobile.end needs a nonempty snapshot and an active UIKit host.");
    BOOL compatible = mobile_nodes.count == mobile_pending.count;
    if (compatible) {
        for (NSUInteger index = 0; index < mobile_nodes.count; index++) {
            MinyarMobileNode *before = mobile_nodes[index], *after = mobile_pending[index];
            if (before.kind != after.kind || before.parent != after.parent || ![before.key isEqualToString:after.key]) { compatible = NO; break; }
        }
    }
    mobile_applying = YES;
    if (!compatible) {
        if (mobile_nodes.count) [mobile_nodes.firstObject.container removeFromSuperview];
        for (NSUInteger index = 0; index < mobile_pending.count; index++) {
            MinyarMobileNode *node = mobile_pending[index];
            mobile_create(node, (NSInteger)index + 1);
            if (node.parent) {
                UIStackView *parent = (UIStackView *)mobile_pending[(NSUInteger)node.parent - 1].content;
                [parent addArrangedSubview:node.container];
            }
        }
        UIView *root = mobile_pending.firstObject.container;
        [mobile_scroll addSubview:root];
        [NSLayoutConstraint activateConstraints:@[
            [root.leadingAnchor constraintEqualToAnchor:mobile_scroll.contentLayoutGuide.leadingAnchor],
            [root.trailingAnchor constraintEqualToAnchor:mobile_scroll.contentLayoutGuide.trailingAnchor],
            [root.topAnchor constraintEqualToAnchor:mobile_scroll.contentLayoutGuide.topAnchor],
            [root.bottomAnchor constraintEqualToAnchor:mobile_scroll.contentLayoutGuide.bottomAnchor],
            [root.widthAnchor constraintEqualToAnchor:mobile_scroll.frameLayoutGuide.widthAnchor]
        ]];
    } else {
        for (NSUInteger index = 0; index < mobile_pending.count; index++) {
            MinyarMobileNode *before = mobile_nodes[index], *after = mobile_pending[index];
            after.container = before.container; after.content = before.content;
            mobile_properties(after);
        }
    }
    mobile_nodes = mobile_pending;
    mobile_pending = nil;
    mobile_applying = NO;
}

MinyarText *minyar_mobileios_eventKeyRaw(void) { mobile_main_thread(); return mobile_text(mobile_event_key); }
MinyarText *minyar_mobileios_eventTextRaw(void) { mobile_main_thread(); return mobile_text(mobile_event_text); }
bool minyar_mobileios_eventCheckedRaw(void) { mobile_main_thread(); return mobile_event_checked; }

@implementation MinyarMobileDelegate
- (BOOL)application:(UIApplication *)application didFinishLaunchingWithOptions:(NSDictionary *)options {
    (void)application; (void)options;
    self.window = [[UIWindow alloc] initWithFrame:UIScreen.mainScreen.bounds];
    UIViewController *controller = [[UIViewController alloc] init];
    controller.title = mobile_title;
    controller.view.backgroundColor = UIColor.systemBackgroundColor;
    mobile_scroll = [[UIScrollView alloc] init];
    mobile_scroll.translatesAutoresizingMaskIntoConstraints = NO;
    mobile_scroll.keyboardDismissMode = UIScrollViewKeyboardDismissModeInteractive;
    [controller.view addSubview:mobile_scroll];
    UILayoutGuide *safe = controller.view.safeAreaLayoutGuide;
    [NSLayoutConstraint activateConstraints:@[
        [mobile_scroll.leadingAnchor constraintEqualToAnchor:safe.leadingAnchor],
        [mobile_scroll.trailingAnchor constraintEqualToAnchor:safe.trailingAnchor],
        [mobile_scroll.topAnchor constraintEqualToAnchor:safe.topAnchor],
        [mobile_scroll.bottomAnchor constraintEqualToAnchor:controller.view.keyboardLayoutGuide.topAnchor]
    ]];
    self.window.rootViewController = controller;
    [self.window makeKeyAndVisible];
    minyar_mobile_dispatch(mobile_session, 0);
    mobile_observer = CFRunLoopObserverCreate(NULL, kCFRunLoopBeforeWaiting, true, 0, mobile_before_wait, NULL);
    CFRunLoopAddObserver(CFRunLoopGetMain(), mobile_observer, kCFRunLoopCommonModes);
    mobile_service();
    return YES;
}
- (void)action:(UIControl *)sender { mobile_emit(sender, [sender isKindOfClass:UIButton.class] ? 1 : 2); }
- (BOOL)textFieldShouldReturn:(UITextField *)textField {
    mobile_emit(textField, 6);
    [textField resignFirstResponder];
    return YES;
}
@end

void minyar_mobileios_runRaw(MinyarText *title, void *session) {
    mobile_main_thread();
    if (mobile_started) minyar_native_stop("mobile.run may start only one UIKit application.");
    mobile_started = YES;
    mobile_session = session;
    @autoreleasepool {
        mobile_title = mobile_string(title);
        static char name[] = "Minyar";
        static char *arguments[] = {name, NULL};
        (void)UIApplicationMain(1, arguments, nil, NSStringFromClass(MinyarMobileDelegate.class));
    }
    if (mobile_observer) {
        CFRunLoopRemoveObserver(CFRunLoopGetMain(), mobile_observer, kCFRunLoopCommonModes);
        CFRelease(mobile_observer); mobile_observer = NULL;
    }
    [mobile_cleanup invalidate]; mobile_cleanup = nil;
    mobile_pending = nil; mobile_nodes = nil; mobile_scroll = nil;
    mobile_title = nil; mobile_session = NULL;
}
