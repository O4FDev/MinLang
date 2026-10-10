/* Win32 controls and message routing, not mocks. Run inside Windows VM/CI. */
#include "../runtime/minyar_native.h"
#include <windows.h>
#include <assert.h>
extern void minyar_windows_initialize(const MinyarText *);
extern long long minyar_windows_window(const MinyarText *, long long, long long);
extern long long minyar_windows_column(long long, long long);
extern long long minyar_windows_row(long long, long long);
extern long long minyar_windows_label(long long, const MinyarText *);
extern long long minyar_windows_button(long long, const MinyarText *);
extern long long minyar_windows_textField(long long, const MinyarText *);
extern long long minyar_windows_checkbox(long long, const MinyarText *, bool);
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
static void equal(MinyarText *value, const char *expected) {
    assert(value->byte_length == (long long)strlen(expected));
    assert(!memcmp(value->bytes, expected, strlen(expected)));
    minyar_rc_release(value);
}
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
    assert(minyar_windows_accessory(true));
    assert(GetWindowLongPtrW(minyar_windows_testHandle(window), GWL_EXSTYLE) & WS_EX_TOOLWINDOW);
    assert(minyar_windows_accessory(false));
    assert(!(GetWindowLongPtrW(minyar_windows_testHandle(window), GWL_EXSTYLE) & WS_EX_TOOLWINDOW));
    MinyarText *empty = text("");
    long long menu = minyar_windows_menu(window, name);
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
