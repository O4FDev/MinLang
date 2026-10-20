/* Test-only executable input for examples/mobile-hello/main.min. Including the
 * adapter keeps every UIKit object, event target and reconciliation path real.
 * Build and launch only in the approved Simulator window through lx. */
#undef NDEBUG
#include <assert.h>
#include <dispatch/dispatch.h>
#include <math.h>
#include "../runtime/native/mobileios.m"

// NotificationCenter's opaque observer must survive this constructor's pool.
static id mobile_test_launch_observer;
static BOOL mobile_test_scheduled;

static MinyarMobileNode *mobile_test_control(NSString *key, NSInteger kind) {
    MinyarMobileNode *found = nil;
    for (MinyarMobileNode *node in mobile_nodes) {
        if (![node.key isEqualToString:key]) continue;
        assert(!found && node.kind == kind);
        assert([node.content.accessibilityIdentifier isEqualToString:key]);
        found = node;
    }
    assert(found);
    return found;
}

static void mobile_test_label(NSUInteger index, NSInteger kind, NSString *expected) {
    assert(index < mobile_nodes.count);
    MinyarMobileNode *node = mobile_nodes[index];
    assert(node.kind == kind && [node.content isKindOfClass:UILabel.class]);
    assert([node.text isEqualToString:expected]);
    assert([((UILabel *)node.content).text isEqualToString:expected]);
}

static void mobile_test_selection(UITextField *input, NSInteger start, NSInteger end) {
    UITextRange *selection = input.selectedTextRange;
    assert(selection);
    assert([input offsetFromPosition:input.beginningOfDocument toPosition:selection.start] == start);
    assert([input offsetFromPosition:input.beginningOfDocument toPosition:selection.end] == end);
}

static void mobile_test_select(UITextField *input, NSInteger start, NSInteger end) {
    assert(start >= 0 && end >= start && end <= (NSInteger)input.text.length);
    UITextPosition *from = [input positionFromPosition:input.beginningOfDocument offset:start];
    UITextPosition *to = [input positionFromPosition:input.beginningOfDocument offset:end];
    assert(from && to);
    input.selectedTextRange = [input textRangeFromPosition:from toPosition:to];
    mobile_test_selection(input, start, end);
}

static void mobile_test_layout(UIWindow *window) {
    [window setNeedsLayout];
    [window layoutIfNeeded];
    [window.rootViewController.view layoutIfNeeded];
    [mobile_scroll layoutIfNeeded];
    UIView *root = mobile_nodes.firstObject.container;
    [root layoutIfNeeded];
    assert(root.superview == mobile_scroll);
    assert(window.bounds.size.width > 0 && window.bounds.size.height > 0);
    assert(mobile_scroll.bounds.size.width > 0 && mobile_scroll.bounds.size.height > 0);
    assert(root.bounds.size.width > 0 && root.bounds.size.height > 0);
    assert(fabs(root.bounds.size.width - mobile_scroll.frameLayoutGuide.layoutFrame.size.width) < 1);
    NSUInteger pins = 0;
    BOOL width = NO;
    for (NSLayoutConstraint *constraint in mobile_scroll.constraints) {
        if (!constraint.active || constraint.firstItem != root) continue;
        if (constraint.secondItem == mobile_scroll.contentLayoutGuide) pins++;
        if (constraint.firstAttribute == NSLayoutAttributeWidth &&
                constraint.secondItem == mobile_scroll.frameLayoutGuide &&
                constraint.secondAttribute == NSLayoutAttributeWidth) width = YES;
    }
    assert(pins == 4 && width);
}

static void mobile_test_smoke(void) {
    assert(NSThread.isMainThread && mobile_test_launch_observer);
    assert(mobile_started && mobile_session && !mobile_pending);
    assert(!mobile_applying && !mobile_dispatching && mobile_nodes.count == 8);
    MinyarMobileDelegate *delegate = (MinyarMobileDelegate *)UIApplication.sharedApplication.delegate;
    assert([delegate isKindOfClass:MinyarMobileDelegate.class] && delegate.window);
    assert(mobile_nodes.firstObject.kind == 7);
    mobile_test_layout(delegate.window);
    mobile_test_label(1, 2, @"Hello from Minyar");
    mobile_test_label(2, 1, @"A native app. A few ordinary words.");
    mobile_test_label(5, 1, @"Hello, Ada!");
    mobile_test_label(6, 1, @"You have sent 0 little lights.");

    UIButton *button = (UIButton *)mobile_test_control(@"light", 3).content;
    UITextField *input = (UITextField *)mobile_test_control(@"name", 4).content;
    UISwitch *toggle = (UISwitch *)mobile_test_control(@"welcome", 5).content;
    assert([button isKindOfClass:UIButton.class] && [input isKindOfClass:UITextField.class]);
    assert([toggle isKindOfClass:UISwitch.class] && toggle.on);
    assert([input.text isEqualToString:@"Ada"]);
    assert([button.configuration.title isEqualToString:@"Send a little light"]);
    [button sendActionsForControlEvents:UIControlEventTouchUpInside];
    mobile_test_label(6, 1, @"You have sent 1 little lights.");
    assert(mobile_test_control(@"light", 3).content == button);

    assert([input becomeFirstResponder]);
    input.text = @"Zoë 🌕";
    // Offset 2 precedes ë and does not split the moon's surrogate pair.
    mobile_test_select(input, 2, 2);
    [input sendActionsForControlEvents:UIControlEventEditingChanged];
    assert(mobile_test_control(@"name", 4).content == input);
    assert(input.isFirstResponder && [input.text isEqualToString:@"Zoë 🌕"]);
    mobile_test_selection(input, 2, 2);
    mobile_test_label(5, 1, @"Hello, Zoë 🌕!");
    mobile_test_label(6, 1, @"You have sent 1 little lights.");

    [toggle setOn:NO animated:NO];
    [toggle sendActionsForControlEvents:UIControlEventValueChanged];
    mobile_test_label(5, 1, @"A little quiet, a little light.");
    assert(mobile_test_control(@"welcome", 5).content == toggle && !toggle.on);
    assert(mobile_test_control(@"name", 4).content == input);
    mobile_test_selection(input, 2, 2);
    [toggle setOn:YES animated:NO];
    [toggle sendActionsForControlEvents:UIControlEventValueChanged];
    mobile_test_label(5, 1, @"Hello, Zoë 🌕!");
    assert(mobile_test_control(@"welcome", 5).content == toggle && toggle.on);
    mobile_test_selection(input, 2, 2);

    // Exercise the changed-model-text branch directly on the reused control.
    // Both offsets are scalar boundaries in the original UTF-16 string.
    MinyarMobileNode *node = mobile_test_control(@"name", 4);
    mobile_test_select(input, 2, 4);
    node.text = @"Zoë 🌕, a little longer";
    mobile_properties(node);
    assert(node.content == input && [input.text isEqualToString:node.text]);
    mobile_test_selection(input, 2, 4);
    node.text = @"Z";
    mobile_properties(node);
    assert(node.content == input && [input.text isEqualToString:@"Z"]);
    mobile_test_selection(input, 1, 1);

    // A normal redraw restores the Minyar model after the direct property test.
    minyar_mobile_dispatch(mobile_session, 0);
    assert(mobile_test_control(@"name", 4).content == input);
    assert([input.text isEqualToString:@"Zoë 🌕"] && input.isFirstResponder);
    mobile_test_selection(input, 1, 1);
    mobile_test_label(1, 2, @"Hello from Minyar");
    mobile_test_label(5, 1, @"Hello, Zoë 🌕!");
    mobile_test_label(6, 1, @"You have sent 1 little lights.");
    mobile_test_layout(delegate.window);
    puts("mobile UIKit smoke passed: launch, action, Unicode edit, toggle, reuse, selection");
    fflush(stdout);
    exit(0);
}

__attribute__((constructor)) static void mobile_test_observe_launch(void) {
    @autoreleasepool {
        mobile_test_launch_observer = [NSNotificationCenter.defaultCenter
            addObserverForName:UIApplicationDidFinishLaunchingNotification
            object:nil queue:NSOperationQueue.mainQueue
            usingBlock:^(NSNotification *notification) {
                (void)notification;
                if (mobile_test_scheduled) return;
                mobile_test_scheduled = YES;
                dispatch_async(dispatch_get_main_queue(), ^{
                    @autoreleasepool { mobile_test_smoke(); }
                });
            }];
        assert(mobile_test_launch_observer);
    }
}
