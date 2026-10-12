/* Win32 controls and message routing, not mocks. Run inside Windows VM/CI. */
#include "../runtime/minyar_native.h"
#include <windows.h>
#include <commctrl.h>
#include <math.h>
#include <assert.h>
extern void minyar_windows_initialize(const MinyarText *);
extern long long minyar_windows_window(const MinyarText *, long long, long long);
extern long long minyar_windows_column(long long, long long);
extern long long minyar_windows_row(long long, long long);
extern long long minyar_windows_label(long long, const MinyarText *);
extern long long minyar_windows_button(long long, const MinyarText *);
extern long long minyar_windows_textField(long long, const MinyarText *);
extern long long minyar_windows_checkbox(long long, const MinyarText *, bool);
extern long long minyar_windows_secureField(long long), minyar_windows_separator(long long);
extern long long minyar_windows_textEditor(long long, const MinyarText *),
    minyar_windows_textView(long long, const MinyarText *);
extern long long minyar_windows_slider(long long, double, double, double);
extern void minyar_windows_size(long long, long long, long long),
    minyar_windows_enabled(long long, bool),
    minyar_windows_appendText(long long, const MinyarText *),
    minyar_windows_setValue(long long, double);
extern double minyar_windows_value(long long);
extern long long minyar_windows_width(long long), minyar_windows_height(long long);
extern HACCEL minyar_windows_testAccelerators(long long);
extern void minyar_windows_padding(long long, long long);
extern void minyar_windows_setText(long long, const MinyarText *);
extern MinyarText *minyar_windows_text(long long);
extern void minyar_windows_font(long long, const MinyarText *, double, double);
extern bool minyar_windows_checked(long long);
extern void minyar_windows_setChecked(long long, bool);
extern bool minyar_windows_nextEvent(double);
extern long long minyar_windows_eventType(void), minyar_windows_eventSource(void);
extern MinyarText *minyar_windows_eventText(void);
extern void minyar_windows_close(long long), minyar_windows_destroy(long long),
    minyar_windows_quit(void);
extern HWND minyar_windows_testHandle(long long);
extern HMENU minyar_windows_testMenu(long long);
extern long long minyar_windows_menu(long long, const MinyarText *),
    minyar_windows_menuItem(long long, const MinyarText *, const MinyarText *);
extern void minyar_windows_menuSeparator(long long);
extern bool minyar_windows_accessory(bool);
extern long long minyar_windows_statusItem(const MinyarText *, const MinyarText *);
extern long long minyar_windows_statusMenu(long long);
extern void minyar_windows_statusRemove(long long);
extern void minyar_rc_release(void *);
static MinyarText *text(const char *s) {
    return minyar_native_copy_text((const unsigned char *)s, (long long)strlen(s));
}
static void equal_at(MinyarText *value, const char *expected, unsigned line) {
    if (value->byte_length != (long long)strlen(expected) ||
        memcmp(value->bytes, expected, strlen(expected))) {
        fprintf(stderr, "text mismatch at fixture line %u; expected:", line);
        for (size_t i = 0; i < strlen(expected); i++)
            fprintf(stderr, " %02x", (unsigned char)expected[i]);
        fprintf(stderr, "; actual:");
        for (long long i = 0; i < value->byte_length; i++)
            fprintf(stderr, " %02x", value->bytes[i]);
        fputc('\n', stderr);
    }
    assert(value->byte_length == (long long)strlen(expected));
    assert(!memcmp(value->bytes, expected, strlen(expected)));
    minyar_rc_release(value);
}
#define equal(value, expected) equal_at(value, expected, __LINE__)
int main(int argc, char **argv) {
    MinyarText *name = text("Minyar Windows test"), *unicode = text("日本語 é 😀"),
               *family = text("Segoe UI");
    minyar_windows_initialize(name);
    long long window = minyar_windows_window(unicode, 500, 300);
    long long column = minyar_windows_column(window, 6);
    minyar_windows_padding(column, 10);
    long long label = minyar_windows_label(column, unicode);
    minyar_windows_font(label, family, 14, 400);
    long long row = minyar_windows_row(column, 8);
    long long button = minyar_windows_button(row, name),
              field = minyar_windows_textField(row, unicode);
    long long check = minyar_windows_checkbox(column, name, true);
    if (argc > 1 && !strcmp(argv[1], "nan"))
        minyar_windows_slider(column, 0, 1, NAN);
    if (argc > 1 && !strcmp(argv[1], "wrong-slider"))
        minyar_windows_value(field);
    if (argc > 1 && !strcmp(argv[1], "invalid-size"))
        minyar_windows_size(label, -1, 20);
    assert(minyar_windows_checked(check));
    minyar_windows_setChecked(check, false);
    assert(!minyar_windows_checked(check));
    equal(minyar_windows_text(field), "日本語 é 😀");
    while (minyar_windows_nextEvent(0) && minyar_windows_eventType() != 0) {
    }
    minyar_windows_setText(field, name);
    assert(minyar_windows_nextEvent(0) && minyar_windows_eventType() == 0);
    SendMessageW(minyar_windows_testHandle(field), WM_SETTEXT, 0, (LPARAM)L"changed 日本語");
    assert(minyar_windows_nextEvent(0) && minyar_windows_eventType() == 2 &&
           minyar_windows_eventSource() == field);
    equal(minyar_windows_eventText(), "changed 日本語");
    SendMessageW(minyar_windows_testHandle(button), BM_CLICK, 0, 0);
    assert(minyar_windows_nextEvent(0) && minyar_windows_eventType() == 1 &&
           minyar_windows_eventSource() == button);
    RECT left, right;
    GetWindowRect(minyar_windows_testHandle(button), &left);
    GetWindowRect(minyar_windows_testHandle(field), &right);
    assert(right.left >= left.right && right.top == left.top);
    long long secure = minyar_windows_secureField(column);
    assert(GetWindowLongPtrW(minyar_windows_testHandle(secure), GWL_STYLE) & ES_PASSWORD);
    minyar_windows_setText(secure, unicode);
    equal(minyar_windows_text(secure), "日本語 é 😀");
    MinyarText *multiline = text("line one\n日本語"), *suffix = text("\n😀");
    long long editor = minyar_windows_textEditor(column, multiline),
              view = minyar_windows_textView(column, multiline);
    assert(GetWindowLongPtrW(minyar_windows_testHandle(editor), GWL_STYLE) & ES_MULTILINE);
    assert(GetWindowLongPtrW(minyar_windows_testHandle(view), GWL_STYLE) & ES_READONLY);
    // Append must ignore the current caret/selection and restore it afterward.
    SendMessageW(minyar_windows_testHandle(editor), EM_SETSEL, 2, 5);
    minyar_windows_appendText(editor, suffix);
    minyar_windows_appendText(view, suffix);
    equal(minyar_windows_text(editor), "line one\n日本語\n😀");
    equal(minyar_windows_text(view), "line one\n日本語\n😀");
    DWORD selection_start = 0, selection_end = 0;
    SendMessageW(minyar_windows_testHandle(editor), EM_GETSEL, (WPARAM)&selection_start,
                 (LPARAM)&selection_end);
    assert(selection_start == 2 && selection_end == 5);
    minyar_windows_enabled(editor, false);
    assert(!IsWindowEnabled(minyar_windows_testHandle(editor)));
    minyar_windows_enabled(editor, true);
    assert(IsWindowEnabled(minyar_windows_testHandle(editor)));
    minyar_windows_size(editor, 120, 80);
    GetWindowRect(minyar_windows_testHandle(editor), &left);
    assert(left.right > left.left && left.bottom > left.top);
    minyar_windows_enabled(button, false);
    SendMessageW(minyar_windows_testHandle(button), BM_CLICK, 0, 0);
    assert(minyar_windows_nextEvent(0) && minyar_windows_eventType() == 0);
    minyar_windows_enabled(button, true);
    long long slider = minyar_windows_slider(column, -0.25, 0.75, 0.25);
    assert(fabs(minyar_windows_value(slider) - 0.25) < 0.000002);
    if (argc > 1 && !strcmp(argv[1], "value-range"))
        minyar_windows_setValue(slider, 100);
    minyar_windows_setValue(slider, 0.75);
    assert(minyar_windows_value(slider) == 0.75);
    minyar_windows_setValue(slider, -0.25);
    assert(minyar_windows_value(slider) == -0.25);
    SendMessageW(minyar_windows_testHandle(slider), TBM_SETPOS, TRUE, 500000);
    SendMessageW(minyar_windows_testHandle(window), WM_HSCROLL, TB_THUMBTRACK,
                 (LPARAM)minyar_windows_testHandle(slider));
    assert(minyar_windows_nextEvent(0) && minyar_windows_eventType() == 2 &&
           minyar_windows_eventSource() == slider);
    assert(fabs(minyar_windows_value(slider) - 0.25) < 0.000002);
    long long separator = minyar_windows_separator(column);
    assert(minyar_windows_testHandle(separator));
    assert(minyar_windows_width(window) > 0 && minyar_windows_height(window) > 0);
    minyar_rc_release(multiline);
    minyar_rc_release(suffix);
    assert(minyar_windows_accessory(true));
    assert(GetWindowLongPtrW(minyar_windows_testHandle(window), GWL_EXSTYLE) & WS_EX_TOOLWINDOW);
    assert(minyar_windows_accessory(false));
    assert(!(GetWindowLongPtrW(minyar_windows_testHandle(window), GWL_EXSTYLE) & WS_EX_TOOLWINDOW));
    MinyarText *empty = text("");
    long long menu = minyar_windows_menu(window, name);
    MinyarText *shortcut = text("Ctrl+Shift+Q");
    if (argc > 1 && !strcmp(argv[1], "invalid-shortcut")) {
        MinyarText *invalid = text("Ctrl+Ctrl+Q");
        minyar_windows_menuItem(menu, name, invalid);
    }
    long long accelerated = minyar_windows_menuItem(menu, name, shortcut);
    if (argc > 1 && !strcmp(argv[1], "duplicate-shortcut"))
        minyar_windows_menuItem(menu, name, shortcut);
    ACCEL binding;
    assert(CopyAcceleratorTableW(minyar_windows_testAccelerators(window), &binding, 1) == 1);
    assert(binding.key == 'Q' && binding.fVirt == (FVIRTKEY | FCONTROL | FSHIFT));
    SendMessageW(minyar_windows_testHandle(window), WM_COMMAND, MAKEWPARAM(binding.cmd, 1), 0);
    assert(minyar_windows_nextEvent(0) && minyar_windows_eventType() == 1 &&
           minyar_windows_eventSource() == accelerated);
    minyar_windows_enabled(accelerated, false);
    SendMessageW(minyar_windows_testHandle(window), WM_COMMAND, MAKEWPARAM(binding.cmd, 1), 0);
    assert(minyar_windows_nextEvent(0) && minyar_windows_eventType() == 0);
    minyar_windows_enabled(accelerated, true);
    // Native translation itself is exercised through the real message pump;
    // bare F6 avoids mutating global modifier-key state in the test session.
    MinyarText *function_key = text("F6");
    long long translated = minyar_windows_menuItem(menu, name, function_key);
    PostMessageW(minyar_windows_testHandle(field), WM_KEYDOWN, VK_F6, 0);
    assert(minyar_windows_nextEvent(0) && minyar_windows_eventType() == 1 &&
           minyar_windows_eventSource() == translated);
    minyar_windows_destroy(translated);
    minyar_rc_release(function_key);
    minyar_windows_destroy(accelerated);
    assert(!minyar_windows_testAccelerators(window));
    SendMessageW(minyar_windows_testHandle(window), WM_COMMAND, MAKEWPARAM(binding.cmd, 1), 0);
    assert(minyar_windows_nextEvent(0) && minyar_windows_eventType() == 0);
    minyar_rc_release(shortcut);
    long long action = minyar_windows_menuItem(menu, unicode, empty);
    minyar_windows_menuSeparator(menu);
    SendMessageW(minyar_windows_testHandle(window), WM_MENUCOMMAND, 0,
                 (LPARAM)minyar_windows_testMenu(menu));
    assert(minyar_windows_nextEvent(0) && minyar_windows_eventType() == 1 &&
           minyar_windows_eventSource() == action);
    minyar_windows_destroy(action);
    assert(GetMenuItemCount(minyar_windows_testMenu(menu)) == 1);
    if (FindWindowW(L"Shell_TrayWnd", NULL)) {
        long long tray = minyar_windows_statusItem(unicode, empty);
        long long tray_menu = minyar_windows_statusMenu(tray);
        assert(tray_menu == minyar_windows_statusMenu(tray));
        minyar_windows_menuItem(tray_menu, name, empty);
        minyar_windows_statusRemove(tray);
        puts("Windows Explorer tray icon and owned menu lifetime verified");
    } else
        puts("Windows session has no Explorer taskbar; real tray check requires desktop VM");
    minyar_windows_close(window);
    assert(minyar_windows_nextEvent(0) && minyar_windows_eventType() == 3);
    minyar_windows_destroy(window);
    if (argc > 1 && !strcmp(argv[1], "stale")) {
        minyar_windows_text(field);
        assert(!"stale child handle accepted");
    }
    minyar_windows_quit();
    assert(minyar_windows_nextEvent(0) && minyar_windows_eventType() == 5);
    assert(!minyar_windows_nextEvent(0));
    minyar_rc_release(name);
    minyar_rc_release(unicode);
    minyar_rc_release(family);
    minyar_rc_release(empty);
    puts("Windows Unicode controls, layout, fonts, events and handle lifetime verified");
    return 0;
}
