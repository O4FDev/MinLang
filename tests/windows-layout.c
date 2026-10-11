/* Real Win32 geometry, visibility, queue and lifetime contracts. */
#include "../runtime/minyar_native.h"
#include <windows.h>
#include <assert.h>
extern void minyar_windows_initialize(const MinyarText *);
extern long long minyar_windows_window(const MinyarText *, long long, long long);
extern long long minyar_windows_column(long long, long long), minyar_windows_row(long long, long long);
extern long long minyar_windows_view(long long), minyar_windows_spacer(long long);
extern long long minyar_windows_button(long long, const MinyarText *), minyar_windows_textField(long long, const MinyarText *);
extern void minyar_windows_grow(long long), minyar_windows_fill(long long);
extern void minyar_windows_size(long long, long long, long long);
extern void minyar_windows_minimumSize(long long, long long, long long), minyar_windows_maximumSize(long long, long long, long long);
extern void minyar_windows_insets(long long, long long, long long, long long, long long), minyar_windows_align(long long, long long);
extern void minyar_windows_spaceAfter(long long, long long), minyar_windows_hidden(long long, bool);
extern void minyar_windows_clear(long long), minyar_windows_remove(long long), minyar_windows_destroy(long long);
extern bool minyar_windows_nextEvent(double);
extern long long minyar_windows_eventType(void), minyar_windows_eventSource(void);
extern long long minyar_windows_width(long long);
extern HWND minyar_windows_testHandle(long long);
extern unsigned long long minyar_windows_testMeasures(void), minyar_windows_testPositions(void);
extern void minyar_rc_release(void *);
static RECT rect(long long window, long long child) {
    RECT r;
    HWND host = minyar_windows_testHandle(window);
    assert(GetWindowRect(minyar_windows_testHandle(child), &r));
    MapWindowPoints(NULL, host, (POINT *)&r, 2);
    HDC dc = GetDC(host);
    int dpi = GetDeviceCaps(dc, LOGPIXELSY);
    ReleaseDC(host, dc);
    r.left = MulDiv(r.left, 96, dpi); r.right = MulDiv(r.right, 96, dpi);
    r.top = MulDiv(r.top, 96, dpi); r.bottom = MulDiv(r.bottom, 96, dpi);
    return r;
}
static void near_point(long actual, long expected) { assert(labs(actual - expected) <= 2); }
static void drain(void) { while (minyar_windows_nextEvent(0) && minyar_windows_eventType()) {} }
int main(int argc, char **argv) {
    MinyarText *name = minyar_native_copy_text((const unsigned char *)"日本語 layout", 16);
    minyar_windows_initialize(name);
    long long window = minyar_windows_window(name, 500, 300);
    long client_width = (long)minyar_windows_width(window);
    long available_width = client_width - 32;
    assert(available_width > 130);
    long long column = minyar_windows_column(window, 5);
    minyar_windows_size(column, 0, 300);
    minyar_windows_insets(column, 11, 13, 17, 19);
    minyar_windows_align(column, 1);
    long long first = minyar_windows_view(column), second = minyar_windows_view(column);
    minyar_windows_size(first, 30, 20); minyar_windows_size(second, 40, 25);
    minyar_windows_spaceAfter(first, 9);
    if (argc > 1) {
        if (!strcmp(argv[1], "invalid-minimum")) minyar_windows_minimumSize(first, -1, 0);
        if (!strcmp(argv[1], "invalid-maximum")) minyar_windows_maximumSize(first, 100001, 0);
        if (!strcmp(argv[1], "invalid-insets")) minyar_windows_insets(column, 0, -1, 0, 0);
        if (!strcmp(argv[1], "invalid-alignment")) minyar_windows_align(column, 0);
        if (!strcmp(argv[1], "wrong-align")) minyar_windows_align(first, 1);
        if (!strcmp(argv[1], "wrong-clear")) minyar_windows_clear(first);
        if (!strcmp(argv[1], "remove-root")) minyar_windows_remove(column);
        if (!strcmp(argv[1], "invalid-gap")) minyar_windows_spaceAfter(first, -1);
        if (!strcmp(argv[1], "wrong-insets")) minyar_windows_insets(first, 0, 0, 0, 0);
        if (!strcmp(argv[1], "wrong-grow")) minyar_windows_grow(column);
        if (!strcmp(argv[1], "maximum-window")) minyar_windows_maximumSize(window, 20, 20);
        if (!strcmp(argv[1], "conflicting-size")) minyar_windows_maximumSize(first, 20, 0);
        if (!strcmp(argv[1], "conflicting-bounds")) {
            minyar_windows_size(first, 0, 20);
            minyar_windows_minimumSize(first, 50, 0);
            minyar_windows_maximumSize(first, 20, 0);
        }
    }
    RECT a = rect(window, first), b = rect(window, second);
    near_point(a.left, 13); near_point(a.top, 11);
    near_point(b.top, a.bottom + 9);
    minyar_windows_hidden(first, true);
    b = rect(window, second); near_point(b.top, 11);
    assert(!(GetWindowLongPtrW(minyar_windows_testHandle(first), GWL_STYLE) & WS_VISIBLE));
    minyar_windows_hidden(first, false);
    assert(GetWindowLongPtrW(minyar_windows_testHandle(first), GWL_STYLE) & WS_VISIBLE);
    b = rect(window, second); near_point(b.top, 40);
    minyar_windows_align(column, 3); b = rect(window, second); near_point(b.right, client_width - 19);
    minyar_windows_align(column, 2); b = rect(window, second); near_point(b.left, 13 + (available_width - 40) / 2);
    minyar_windows_size(second, 0, 25);
    minyar_windows_fill(second); minyar_windows_maximumSize(second, 70, 0);
    b = rect(window, second); near_point(b.right - b.left, 70);
    near_point(b.left, 13 + (available_width - 70) / 2);
    minyar_windows_maximumSize(second, 0, 0);
    b = rect(window, second); near_point(b.left, 13); near_point(b.right, client_width - 19);
    minyar_windows_align(column, 1);
    long long row = minyar_windows_row(column, 0);
    minyar_windows_fill(row); minyar_windows_size(row, 0, 60);
    long long left = minyar_windows_view(row), gap = minyar_windows_spacer(row);
    long long other_gap = minyar_windows_spacer(row), right = minyar_windows_view(row);
    minyar_windows_size(left, 40, 0); minyar_windows_fill(left);
    minyar_windows_size(right, 50, 30);
    minyar_windows_maximumSize(gap, 40, 0);
    a = rect(window, left); b = rect(window, right);
    near_point(a.bottom - a.top, 60); near_point(b.right, client_width - 19);
    RECT small_gap = rect(window, gap), large_gap = rect(window, other_gap);
    near_point(small_gap.right - small_gap.left, 40);
    near_point(large_gap.right - large_gap.left, available_width - 130);
    minyar_windows_remove(gap);
    large_gap = rect(window, other_gap);
    near_point(large_gap.right - large_gap.left, available_width - 90);
    minyar_windows_align(row, 3); b = rect(window, right);
    near_point(b.bottom, a.bottom);
    minyar_windows_size(right, 0, 0);
    minyar_windows_minimumSize(right, 80, 45); b = rect(window, right);
    near_point(b.right - b.left, 80); near_point(b.bottom - b.top, 45);
    minyar_windows_minimumSize(right, 0, 0);
    // A hidden ancestor must hide existing and newly appended native children,
    // and unhiding the ancestor must preserve a child's own hidden state.
    minyar_windows_hidden(row, true);
    long long hidden_child = minyar_windows_view(row);
    minyar_windows_hidden(right, true); minyar_windows_hidden(row, false);
    assert(GetWindowLongPtrW(minyar_windows_testHandle(hidden_child), GWL_STYLE) & WS_VISIBLE);
    assert(!(GetWindowLongPtrW(minyar_windows_testHandle(right), GWL_STYLE) & WS_VISIBLE));
    minyar_windows_hidden(right, false);
    // Zero minimum removes a bound; a window minimum becomes a native track limit.
    minyar_windows_minimumSize(window, 120, 90);
    MINMAXINFO track = {0};
    SendMessageW(minyar_windows_testHandle(window), WM_GETMINMAXINFO, 0, (LPARAM)&track);
    assert(track.ptMinTrackSize.x >= 120 && track.ptMinTrackSize.y >= 90);
    minyar_windows_minimumSize(window, 0, 0);
    // Removing a subtree purges queued descendants and keeps unrelated actions.
    long long branch = minyar_windows_column(column, 1);
    long long action = minyar_windows_button(branch, name);
    long long edit = minyar_windows_textField(branch, name);
    long long survivor = minyar_windows_button(column, name);
    HWND gone = minyar_windows_testHandle(action);
    drain();
    SendMessageW(gone, BM_CLICK, 0, 0);
    SendMessageW(minyar_windows_testHandle(survivor), BM_CLICK, 0, 0);
    SendMessageW(minyar_windows_testHandle(edit), WM_SETTEXT, 0, (LPARAM)L"queued change");
    minyar_windows_remove(branch);
    assert(!IsWindow(gone));
    assert(minyar_windows_nextEvent(0) && minyar_windows_eventType() == 1 && minyar_windows_eventSource() == survivor);
    assert(minyar_windows_nextEvent(0) && minyar_windows_eventType() == 0);
    if (argc > 1 && !strcmp(argv[1], "stale-remove")) minyar_windows_testHandle(edit);
    long long nested = minyar_windows_column(column, 0);
    long long nested_row = minyar_windows_row(nested, 0);
    long long nested_action = minyar_windows_button(nested_row, name);
    gone = minyar_windows_testHandle(nested_action);
    SendMessageW(gone, BM_CLICK, 0, 0);
    minyar_windows_clear(nested);
    assert(!IsWindow(gone));
    assert(minyar_windows_nextEvent(0) && minyar_windows_eventType() == 0);
    if (argc > 1 && !strcmp(argv[1], "stale-clear")) minyar_windows_testHandle(nested_action);
    assert(minyar_windows_view(nested) != nested_action);
    // Property changes and repeated identical layouts must retain intrinsic caches.
    unsigned long long measures = minyar_windows_testMeasures(), positions = minyar_windows_testPositions();
    for (unsigned i = 0; i < 16; i++)
        SendMessageW(minyar_windows_testHandle(window), WM_SIZE, 0, MAKELPARAM(500, 300));
    assert(minyar_windows_testMeasures() == measures);
    assert(minyar_windows_testPositions() == positions);
    // Repeat real native creation, queued input, clear and remove. The parent
    // survives, its growth ledger resets, and native USER resources stay flat.
    DWORD resources = GetGuiResources(GetCurrentProcess(), GR_USEROBJECTS);
    assert(resources);
    for (unsigned round = 0; round < 32; round++) {
        long long owned = minyar_windows_row(column, 0);
        minyar_windows_fill(owned);
        minyar_windows_size(owned, 0, 20);
        minyar_windows_spacer(owned);
        long long click = minyar_windows_button(owned, name);
        SendMessageW(minyar_windows_testHandle(click), BM_CLICK, 0, 0);
        minyar_windows_clear(owned);
        assert(minyar_windows_nextEvent(0) && minyar_windows_eventType() == 0);
        long long replacement = minyar_windows_spacer(owned);
        a = rect(window, replacement); near_point(a.right - a.left, available_width);
        minyar_windows_remove(owned);
        assert(GetGuiResources(GetCurrentProcess(), GR_USEROBJECTS) <= resources);
    }
    minyar_windows_clear(column);
    minyar_windows_clear(column);
    minyar_windows_destroy(window);
    minyar_rc_release(name);
    puts("Windows native constraints, hidden geometry and descendant lifetime verified");
    return 0;
}
