#define WIN32_LEAN_AND_MEAN
#include "../minyar_native.h"
#include <windows.h>
#include <shellapi.h>
#include <math.h>
#include <stdint.h>

/* The UI owns only native memory. Generation checked IDs never expose pointers. */
enum { WINDOW = 1, COLUMN, ROW, LABEL, BUTTON, FIELD, CHECKBOX, MENU, MENUITEM, TRAY };
typedef struct Widget {
    uint32_t generation;
    int kind, padding, spacing, width, height, suppress;
    long long parent, first, last, next;
    HWND handle;
    HFONT font;
    HMENU menu, bar;
    UINT tray_id;
} Widget;
typedef struct Event {
    int type;
    long long source;
    wchar_t *text;
    struct Event *next;
} Event;
static Widget *widgets;
static size_t capacity;
static DWORD owner;
static Event *head, *tail, current;
static unsigned queued;
static bool quitting, delivered_quit;
static bool accessory;
static HWND tray_window;
static UINT next_tray = 1, taskbar_created;
static const wchar_t window_class[] = L"MinyarWindowV1";
#ifdef MINYAR_APP_EVENT_LOOP
extern bool minyar_net_appLoopWindowsValid(long long);
extern void *minyar_net_appLoopWindowsAttach(long long, int *);
extern void minyar_net_appLoopWindowsDetach(long long);
extern bool minyar_net_appLoopObserve(long long, void (*)(long long, unsigned));
extern uint64_t minyar_net_appLoopDeadline(long long);
static long long app_loop;
static HANDLE app_wake;
static bool app_armed;
static void unshare_loop(void) {
    if (app_loop)
        minyar_net_appLoopWindowsDetach(app_loop);
    minyar_net_appLoopObserve(0, NULL);
    app_loop = 0;
    app_wake = NULL;
    app_armed = false;
}
static void loop_changed(long long loop, unsigned reason) {
    if (loop != app_loop)
        return;
    if (reason == 2)
        unshare_loop();
    else
        app_armed = true;
}
#endif
static MinyarBytes *shared_result(unsigned error, int native, long long value) {
    MinyarBytes *result = minyar_bytes_new(16);
    memcpy((void *)result->bytes, &error, 4);
    memcpy((void *)(result->bytes + 4), &native, 4);
    memcpy((void *)(result->bytes + 8), &value, 8);
    return result;
}

static void fail(const char *message) {
    minyar_native_stop(message);
}
static void thread(void) {
    if (!owner || owner != GetCurrentThreadId())
        fail("windows: use the initialized UI thread");
}
static long long id(Widget *w) {
    return (long long)(((uint64_t)w->generation << 32) | (uint32_t)(w - widgets + 1));
}
static Widget *get(long long value) {
    uint32_t index = (uint32_t)value, generation = (uint32_t)((uint64_t)value >> 32);
    if (!index || index > capacity || !widgets[index - 1].kind ||
        widgets[index - 1].generation != generation)
        fail("windows: invalid or destroyed handle");
    return widgets + index - 1;
}
static wchar_t *wide(const MinyarText *value) {
    if (value->byte_length < 0 || value->byte_length > INT_MAX ||
        memchr(value->bytes, 0, (size_t)value->byte_length))
        fail("windows: text contains NUL or is too long");
    int n = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, (const char *)value->bytes,
                                (int)value->byte_length, NULL, 0);
    if (!n && value->byte_length)
        fail("windows: invalid UTF-8");
    wchar_t *out = calloc((size_t)n + 1, sizeof(*out));
    if (!out)
        fail("windows: allocation failed");
    if (n)
        MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, (const char *)value->bytes,
                            (int)value->byte_length, out, n);
    return out;
}
static MinyarText *narrow(const wchar_t *value) {
    int n = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, value, -1, NULL, 0, NULL, NULL);
    if (!n)
        fail("windows: invalid UTF-16");
    char *out = malloc((size_t)n);
    if (!out)
        fail("windows: allocation failed");
    WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, value, -1, out, n, NULL, NULL);
    MinyarText *text = minyar_native_copy_text((const unsigned char *)out, n - 1);
    free(out);
    return text;
}
static wchar_t *read_text(HWND handle) {
    int n = GetWindowTextLengthW(handle);
    wchar_t *out = calloc((size_t)n + 1, sizeof(*out));
    if (!out)
        fail("windows: allocation failed");
    GetWindowTextW(handle, out, n + 1);
    return out;
}
static void enqueue(int type, long long source, wchar_t *text) {
    if (type == 2)
        for (Event *event = head; event; event = event->next)
            if (event->type == type && event->source == source) {
                free(event->text);
                event->text = text;
                return;
            }
    if (queued >= 65536)
        fail("windows: event queue capacity exceeded");
    Event *event = calloc(1, sizeof(*event));
    if (!event)
        fail("windows: allocation failed");
    event->type = type;
    event->source = source;
    event->text = text;
    if (tail)
        tail->next = event;
    else
        head = event;
    tail = event;
    queued++;
}
static Widget *root(Widget *w) {
    while (w->parent)
        w = get(w->parent);
    return w;
}
static int scaled(Widget *w, int value) {
    HDC dc = GetDC(root(w)->handle);
    int dpi = dc ? GetDeviceCaps(dc, LOGPIXELSY) : 96;
    if (dc)
        ReleaseDC(root(w)->handle, dc);
    return MulDiv(value, dpi, 96);
}
static void measure(Widget *w, int *width, int *height) {
    if (w->kind == COLUMN || w->kind == ROW) {
        int x = 0, y = 0, count = 0;
        for (long long child = w->first; child; child = get(child)->next) {
            if (get(child)->kind >= MENU)
                continue;
            int cw, ch;
            measure(get(child), &cw, &ch);
            count++;
            if (w->kind == ROW) {
                x += cw;
                if (ch > y)
                    y = ch;
            } else {
                if (cw > x)
                    x = cw;
                y += ch;
            }
        }
        if (count > 1) {
            if (w->kind == ROW)
                x += (count - 1) * scaled(w, w->spacing);
            else
                y += (count - 1) * scaled(w, w->spacing);
        }
        *width = x + 2 * scaled(w, w->padding);
        *height = y + 2 * scaled(w, w->padding);
        return;
    }
    wchar_t *text = read_text(w->handle);
    HDC dc = GetDC(w->handle);
    HFONT old = SelectObject(dc, w->font ? w->font : GetStockObject(DEFAULT_GUI_FONT));
    SIZE size = {0};
    GetTextExtentPoint32W(dc, text, (int)wcslen(text), &size);
    SelectObject(dc, old);
    ReleaseDC(w->handle, dc);
    free(text);
    int extra = w->kind == FIELD ? 24 : (w->kind == LABEL ? 0 : 32);
    *width = size.cx + scaled(w, extra);
    *height = size.cy + scaled(w, w->kind == LABEL ? 4 : 14);
    int minimum = scaled(w, w->kind == FIELD ? 120 : 40);
    if (*width < minimum)
        *width = minimum;
}
static void arrange(Widget *w, int x, int y, int width, int height) {
    if (w->handle && w->kind != WINDOW) {
        SetWindowPos(w->handle, NULL, x, y, width, height, SWP_NOZORDER | SWP_NOACTIVATE);
        return;
    }
    int padding = scaled(w, w->padding), spacing = scaled(w, w->spacing);
    x += padding;
    y += padding;
    width -= 2 * padding;
    height -= 2 * padding;
    for (long long child = w->first; child; child = get(child)->next) {
        Widget *c = get(child);
        if (c->kind >= MENU)
            continue;
        int cw, ch;
        measure(c, &cw, &ch);
        if (w->kind == ROW) {
            arrange(c, x, y, cw, ch);
            x += cw + spacing;
        } else {
            arrange(c, x, y, width > 0 ? width : 0, ch);
            y += ch + spacing;
        }
    }
}
static void layout(Widget *w) {
    w = root(w);
    RECT area;
    if (GetClientRect(w->handle, &area))
        arrange(w, 0, 0, area.right, area.bottom);
}
static LRESULT CALLBACK procedure(HWND handle, UINT message, WPARAM wp, LPARAM lp) {
    long long value = (long long)GetWindowLongPtrW(handle, GWLP_USERDATA);
    if (message == WM_NCCREATE) {
        value = (long long)((CREATESTRUCTW *)lp)->lpCreateParams;
        SetWindowLongPtrW(handle, GWLP_USERDATA, (LONG_PTR)value);
    }
    Widget *w = value ? get(value) : NULL;
    if (message == WM_COMMAND && lp) {
        long long child = (long long)GetWindowLongPtrW((HWND)lp, GWLP_USERDATA);
        if (child) {
            Widget *c = get(child);
            int code = HIWORD(wp);
            if (!c->suppress && c->kind == FIELD && code == EN_CHANGE)
                enqueue(2, child, read_text(c->handle));
            else if (!c->suppress && (c->kind == BUTTON || c->kind == CHECKBOX) &&
                     code == BN_CLICKED)
                enqueue(1, child, NULL);
        }
        return 0;
    }
    if (message == WM_MENUCOMMAND) {
        MENUITEMINFOW item = {0};
        item.cbSize = sizeof(item);
        item.fMask = MIIM_DATA;
        if (GetMenuItemInfoW((HMENU)lp, (UINT)wp, TRUE, &item) && item.dwItemData)
            enqueue(1, (long long)item.dwItemData, NULL);
        return 0;
    }
    if (message == WM_APP + 1 && (lp == WM_RBUTTONUP || lp == WM_CONTEXTMENU ||
                                  lp == WM_LBUTTONUP || lp == NIN_SELECT || lp == NIN_KEYSELECT)) {
        for (size_t i = 0; i < capacity; i++)
            if (widgets[i].kind == TRAY && widgets[i].tray_id == (UINT)wp) {
                Widget *tray = widgets + i;
                if (tray->first) {
                    POINT point;
                    GetCursorPos(&point);
                    SetForegroundWindow(handle);
                    TrackPopupMenuEx(get(tray->first)->menu, TPM_RIGHTBUTTON, point.x, point.y,
                                     handle, NULL);
                    PostMessageW(handle, WM_NULL, 0, 0);
                } else
                    enqueue(1, id(tray), NULL);
                break;
            }
        return 0;
    }
    if (taskbar_created && message == taskbar_created) {
        for (size_t i = 0; i < capacity; i++)
            if (widgets[i].kind == TRAY) {
                NOTIFYICONDATAW data = {0};
                data.cbSize = sizeof(data);
                data.hWnd = handle;
                data.uID = widgets[i].tray_id;
                data.uFlags = NIF_ICON | NIF_MESSAGE | NIF_TIP;
                data.hIcon = LoadIconW(NULL, MAKEINTRESOURCEW(32512));
                data.uCallbackMessage = WM_APP + 1;
                GetWindowTextW(widgets[i].handle, data.szTip, 128);
                if (Shell_NotifyIconW(NIM_ADD, &data)) {
                    data.uVersion = NOTIFYICON_VERSION;
                    Shell_NotifyIconW(NIM_SETVERSION, &data);
                }
            }
        return 0;
    }
    if (w && message == WM_CLOSE) {
        ShowWindow(handle, SW_HIDE);
        enqueue(3, value, NULL);
        return 0;
    }
    if (w && message == WM_SIZE) {
        layout(w);
        if (IsWindowVisible(handle))
            enqueue(4, value, NULL);
        return 0;
    }
    return DefWindowProcW(handle, message, wp, lp);
}
static long long create(int kind, long long parent) {
    thread();
    size_t i = 0;
    for (; i < capacity; i++)
        if (!widgets[i].kind)
            break;
    if (i == capacity) {
        if (capacity >= 65536)
            fail("windows: widget capacity exceeded");
        size_t next = capacity ? capacity * 2 : 128;
        Widget *fresh = realloc(widgets, next * sizeof(*fresh));
        if (!fresh)
            fail("windows: allocation failed");
        widgets = fresh;
        memset(widgets + capacity, 0, (next - capacity) * sizeof(*widgets));
        capacity = next;
    }
    Widget *w = widgets + i;
    uint32_t generation = w->generation + 1;
    if (!generation)
        fail("windows: handle generation exhausted");
    memset(w, 0, sizeof(*w));
    w->generation = generation;
    w->kind = kind;
    w->parent = parent;
    long long value = id(w);
    if (parent) {
        Widget *p = get(parent);
        if (p->kind != WINDOW && p->kind != COLUMN && p->kind != ROW &&
            !(kind == MENU && p->kind == TRAY) && !(kind == MENUITEM && p->kind == MENU))
            fail("windows: parent is not a container");
        if (p->last)
            get(p->last)->next = value;
        else
            p->first = value;
        p->last = value;
    }
    return value;
}
void minyar_windows_initialize(const MinyarText *name) {
    (void)name;
    if (owner && owner != GetCurrentThreadId())
        fail("windows: UI initialized on another thread");
    if (owner)
        return;
    owner = GetCurrentThreadId();
    WNDCLASSEXW wc = {0};
    wc.cbSize = sizeof(wc);
    wc.lpfnWndProc = procedure;
    wc.hInstance = GetModuleHandleW(NULL);
    wc.lpszClassName = window_class;
    wc.hCursor = LoadCursorW(NULL, MAKEINTRESOURCEW(32512));
    wc.hbrBackground = (HBRUSH)(COLOR_WINDOW + 1);
    if (!RegisterClassExW(&wc) && GetLastError() != ERROR_CLASS_ALREADY_EXISTS)
        fail("windows: unable to register window class");
}
long long minyar_windows_window(const MinyarText *title, long long width, long long height) {
    if (width < 1 || height < 1 || width > 32768 || height > 32768)
        fail("windows: invalid window size");
    long long value = create(WINDOW, 0);
    Widget *w = get(value);
    wchar_t *text = wide(title);
    RECT rectangle = {0, 0, (LONG)width, (LONG)height};
    AdjustWindowRectEx(&rectangle, WS_OVERLAPPEDWINDOW, FALSE, 0);
    w->handle = CreateWindowExW(accessory ? WS_EX_TOOLWINDOW : 0, window_class, text,
                                WS_OVERLAPPEDWINDOW, CW_USEDEFAULT, CW_USEDEFAULT,
                                rectangle.right - rectangle.left, rectangle.bottom - rectangle.top,
                                NULL, NULL, GetModuleHandleW(NULL), (LPVOID)(intptr_t)value);
    free(text);
    if (!w->handle)
        fail("windows: unable to create window");
    return value;
}
static long long container(int kind, long long parent, long long spacing) {
    if (spacing < 0 || spacing > 32768)
        fail("windows: invalid spacing");
    long long value = create(kind, parent);
    Widget *w = get(value);
    w->spacing = (int)spacing;
    layout(w);
    return value;
}
long long minyar_windows_column(long long parent, long long spacing) {
    return container(COLUMN, parent, spacing);
}
long long minyar_windows_row(long long parent, long long spacing) {
    return container(ROW, parent, spacing);
}
static long long control(int kind, long long parent, const MinyarText *title, bool checked) {
    long long value = create(kind, parent);
    Widget *w = get(value);
    wchar_t *text = wide(title);
    const wchar_t *class_name = kind == FIELD ? L"EDIT" : kind == LABEL ? L"STATIC" : L"BUTTON";
    DWORD style =
        WS_CHILD | WS_VISIBLE |
        (kind == FIELD   ? ES_AUTOHSCROLL | WS_TABSTOP
         : kind == LABEL ? SS_LEFT
                         : WS_TABSTOP | (kind == CHECKBOX ? BS_AUTOCHECKBOX : BS_PUSHBUTTON));
    w->handle = CreateWindowExW(kind == FIELD ? WS_EX_CLIENTEDGE : 0, class_name, text, style, 0, 0,
                                1, 1, root(w)->handle, NULL, GetModuleHandleW(NULL), NULL);
    free(text);
    if (!w->handle)
        fail("windows: unable to create control");
    SetWindowLongPtrW(w->handle, GWLP_USERDATA, (LONG_PTR)value);
    SendMessageW(w->handle, WM_SETFONT, (WPARAM)GetStockObject(DEFAULT_GUI_FONT), TRUE);
    if (kind == CHECKBOX)
        SendMessageW(w->handle, BM_SETCHECK, checked ? BST_CHECKED : BST_UNCHECKED, 0);
    layout(w);
    return value;
}
long long minyar_windows_label(long long parent, const MinyarText *text) {
    return control(LABEL, parent, text, false);
}
long long minyar_windows_button(long long parent, const MinyarText *text) {
    return control(BUTTON, parent, text, false);
}
long long minyar_windows_textField(long long parent, const MinyarText *text) {
    return control(FIELD, parent, text, false);
}
long long minyar_windows_checkbox(long long parent, const MinyarText *text, bool checked) {
    return control(CHECKBOX, parent, text, checked);
}
void minyar_windows_padding(long long value, long long padding) {
    thread();
    if (padding < 0 || padding > 32768)
        fail("windows: invalid padding");
    Widget *w = get(value);
    w->padding = (int)padding;
    layout(w);
}
void minyar_windows_setText(long long value, const MinyarText *text) {
    thread();
    Widget *w = get(value);
    if (!w->handle)
        fail("windows: container has no text");
    wchar_t *s = wide(text);
    w->suppress++;
    SetWindowTextW(w->handle, s);
    w->suppress--;
    free(s);
    layout(w);
}
MinyarText *minyar_windows_text(long long value) {
    thread();
    Widget *w = get(value);
    if (!w->handle)
        fail("windows: container has no text");
    wchar_t *s = read_text(w->handle);
    MinyarText *out = narrow(s);
    free(s);
    return out;
}
void minyar_windows_font(long long value, const MinyarText *family, double size, double weight) {
    thread();
    Widget *w = get(value);
    if (!w->handle || !isfinite(size) || size < 1 || size > 1000 || !isfinite(weight) ||
        weight < 1 || weight > 1000)
        fail("windows: invalid font");
    wchar_t *name = wide(family);
    HFONT font = CreateFontW(-scaled(w, (int)llround(size)), 0, 0, 0, (int)llround(weight), FALSE,
                             FALSE, FALSE, DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                             CLEARTYPE_QUALITY, DEFAULT_PITCH, name);
    free(name);
    if (!font)
        fail("windows: unable to create font");
    SendMessageW(w->handle, WM_SETFONT, (WPARAM)font, TRUE);
    if (w->font)
        DeleteObject(w->font);
    w->font = font;
    layout(w);
}
bool minyar_windows_checked(long long value) {
    thread();
    Widget *w = get(value);
    if (w->kind != CHECKBOX)
        fail("windows: handle is not a checkbox");
    return SendMessageW(w->handle, BM_GETCHECK, 0, 0) == BST_CHECKED;
}
void minyar_windows_setChecked(long long value, bool checked) {
    thread();
    Widget *w = get(value);
    if (w->kind != CHECKBOX)
        fail("windows: handle is not a checkbox");
    SendMessageW(w->handle, BM_SETCHECK, checked ? BST_CHECKED : BST_UNCHECKED, 0);
}
void minyar_windows_show(long long value) {
    thread();
    Widget *w = get(value);
    if (w->kind != WINDOW)
        fail("windows: handle is not a window");
    ShowWindow(w->handle, SW_SHOW);
    layout(w);
}
void minyar_windows_hide(long long value) {
    thread();
    Widget *w = get(value);
    if (w->kind != WINDOW)
        fail("windows: handle is not a window");
    ShowWindow(w->handle, SW_HIDE);
}
void minyar_windows_close(long long value) {
    thread();
    Widget *w = get(value);
    if (w->kind != WINDOW)
        fail("windows: handle is not a window");
    SendMessageW(w->handle, WM_CLOSE, 0, 0);
}
static void remove_events(long long value) {
    Event **link = &head;
    tail = NULL;
    while (*link) {
        Event *event = *link;
        if (event->source == value) {
            *link = event->next;
            free(event->text);
            free(event);
            queued--;
        } else {
            tail = event;
            link = &event->next;
        }
    }
}
static void destroy(long long value) {
    Widget *w = get(value);
    for (long long child = w->first; child;) {
        long long next = get(child)->next;
        destroy(child);
        child = next;
    }
    w = get(value);
    remove_events(value);
    if (w->kind == MENUITEM && w->parent) {
        HMENU menu = get(w->parent)->menu;
        for (int i = GetMenuItemCount(menu) - 1; i >= 0; i--) {
            MENUITEMINFOW item = {0};
            item.cbSize = sizeof(item);
            item.fMask = MIIM_DATA;
            if (GetMenuItemInfoW(menu, (UINT)i, TRUE, &item) && item.dwItemData == (ULONG_PTR)value)
                RemoveMenu(menu, (UINT)i, MF_BYPOSITION);
        }
    }
    if (w->kind == MENU && w->parent && get(w->parent)->kind == WINDOW) {
        HMENU bar = get(w->parent)->bar;
        for (int i = GetMenuItemCount(bar) - 1; i >= 0; i--)
            if (GetSubMenu(bar, i) == w->menu)
                RemoveMenu(bar, (UINT)i, MF_BYPOSITION);
    }
    if (w->menu)
        DestroyMenu(w->menu);
    if (w->bar) {
        SetMenu(w->handle, NULL);
        DestroyMenu(w->bar);
    }
    if (w->kind == TRAY) {
        NOTIFYICONDATAW data = {0};
        data.cbSize = sizeof(data);
        data.hWnd = tray_window;
        data.uID = w->tray_id;
        Shell_NotifyIconW(NIM_DELETE, &data);
    }
    if (w->handle) {
        SetWindowLongPtrW(w->handle, GWLP_USERDATA, 0);
        DestroyWindow(w->handle);
    }
    if (w->font)
        DeleteObject(w->font);
    w->kind = 0;
}
void minyar_windows_destroy(long long value) {
    thread();
    Widget *w = get(value);
    if (w->parent) {
        Widget *p = get(w->parent);
        long long previous = 0;
        for (long long child = p->first; child && child != value; child = get(child)->next)
            previous = child;
        if (previous)
            get(previous)->next = w->next;
        else
            p->first = w->next;
        if (p->last == value)
            p->last = previous;
    }
    destroy(value);
}
void minyar_windows_quit(void) {
    thread();
    if (!quitting) {
        quitting = true;
        enqueue(5, 0, NULL);
    }
}
long long minyar_windows_menu(long long window, const MinyarText *title) {
    thread();
    Widget *parent = get(window);
    if (parent->kind != WINDOW)
        fail("windows: menu requires a window");
    long long value = create(MENU, window);
    Widget *w = get(value);
    w->menu = CreatePopupMenu();
    if (!w->menu)
        fail("windows: unable to create menu");
    MENUINFO info = {0};
    info.cbSize = sizeof(info);
    info.fMask = MIM_STYLE;
    info.dwStyle = MNS_NOTIFYBYPOS;
    SetMenuInfo(w->menu, &info);
    parent = get(window);
    if (!parent->bar)
        parent->bar = CreateMenu();
    if (!parent->bar)
        fail("windows: unable to create menu bar");
    wchar_t *text = wide(title);
    AppendMenuW(parent->bar, MF_POPUP, (UINT_PTR)w->menu, text);
    free(text);
    SetMenu(parent->handle, parent->bar);
    DrawMenuBar(parent->handle);
    return value;
}
long long minyar_windows_menuItem(long long menu, const MinyarText *title, const MinyarText *key) {
    thread();
    if (get(menu)->kind != MENU)
        fail("windows: handle is not a menu");
    if (key->byte_length)
        fail("windows: menu shortcuts require an explicit accelerator binding");
    long long value = create(MENUITEM, menu);
    wchar_t *text = wide(title);
    MENUITEMINFOW item = {0};
    item.cbSize = sizeof(item);
    item.fMask = MIIM_STRING | MIIM_DATA;
    item.dwTypeData = text;
    item.dwItemData = (ULONG_PTR)value;
    if (!InsertMenuItemW(get(menu)->menu, (UINT)-1, TRUE, &item))
        fail("windows: unable to append menu item");
    free(text);
    return value;
}
void minyar_windows_menuSeparator(long long menu) {
    thread();
    Widget *w = get(menu);
    if (w->kind != MENU)
        fail("windows: handle is not a menu");
    if (!AppendMenuW(w->menu, MF_SEPARATOR, 0, NULL))
        fail("windows: unable to append separator");
}
bool minyar_windows_accessory(bool enabled) {
    thread();
    accessory = enabled;
    for (size_t i = 0; i < capacity; i++)
        if (widgets[i].kind == WINDOW) {
            HWND handle = widgets[i].handle;
            bool visible = IsWindowVisible(handle);
            if (visible)
                ShowWindow(handle, SW_HIDE);
            LONG_PTR style = GetWindowLongPtrW(handle, GWL_EXSTYLE);
            style =
                enabled ? (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW : style & ~WS_EX_TOOLWINDOW;
            SetWindowLongPtrW(handle, GWL_EXSTYLE, style);
            SetWindowPos(handle, NULL, 0, 0, 0, 0,
                         SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE |
                             SWP_FRAMECHANGED);
            if (visible)
                ShowWindow(handle, SW_SHOW);
        }
    return true;
}
long long minyar_windows_statusItem(const MinyarText *title, const MinyarText *symbol) {
    thread();
    (void)symbol;
    if (!tray_window) {
        tray_window = CreateWindowExW(0, window_class, L"Minyar tray", WS_POPUP, 0, 0, 0, 0, NULL,
                                      NULL, GetModuleHandleW(NULL), NULL);
        if (!tray_window)
            fail("windows: unable to create tray event window");
        taskbar_created = RegisterWindowMessageW(L"TaskbarCreated");
    }
    if (!next_tray)
        fail("windows: tray ID space exhausted");
    long long value = create(TRAY, 0);
    Widget *w = get(value);
    w->tray_id = next_tray++;
    wchar_t *text = wide(title);
    if (wcslen(text) >= 128) {
        free(text);
        fail("windows: tray title exceeds 127 UTF-16 units");
    }
    w->handle = CreateWindowExW(0, L"STATIC", text, 0, 0, 0, 0, 0, tray_window, NULL,
                                GetModuleHandleW(NULL), NULL);
    NOTIFYICONDATAW data = {0};
    data.cbSize = sizeof(data);
    data.hWnd = tray_window;
    data.uID = w->tray_id;
    data.uFlags = NIF_ICON | NIF_MESSAGE | NIF_TIP;
    data.uCallbackMessage = WM_APP + 1;
    data.hIcon = LoadIconW(NULL, MAKEINTRESOURCEW(32512));
    wcscpy(data.szTip, text);
    free(text);
    if (!Shell_NotifyIconW(NIM_ADD, &data))
        fail("windows: taskbar is unavailable");
    /* Version 3 keeps full 32-bit icon IDs while enabling keyboard activation. */
    data.uVersion = NOTIFYICON_VERSION;
    if (!Shell_NotifyIconW(NIM_SETVERSION, &data)) {
        Shell_NotifyIconW(NIM_DELETE, &data);
        fail("windows: taskbar version is unavailable");
    }
    return value;
}
long long minyar_windows_statusMenu(long long tray) {
    thread();
    Widget *parent = get(tray);
    if (parent->kind != TRAY)
        fail("windows: handle is not a tray icon");
    if (parent->first)
        return parent->first;
    long long value = create(MENU, tray);
    Widget *w = get(value);
    w->menu = CreatePopupMenu();
    if (!w->menu)
        fail("windows: unable to create tray menu");
    MENUINFO info = {0};
    info.cbSize = sizeof(info);
    info.fMask = MIM_STYLE;
    info.dwStyle = MNS_NOTIFYBYPOS;
    SetMenuInfo(w->menu, &info);
    return value;
}
void minyar_windows_statusRemove(long long tray) {
    thread();
    if (get(tray)->kind != TRAY)
        fail("windows: handle is not a tray icon");
    minyar_windows_destroy(tray);
}
MinyarBytes *minyar_windows_shareNetworkLoopRaw(long long loop) {
    thread();
#ifdef MINYAR_APP_EVENT_LOOP
    if (!minyar_net_appLoopWindowsValid(loop))
        return shared_result(6, ERROR_INVALID_HANDLE, 0);
    if (loop == app_loop)
        return shared_result(0, 0, loop);
    unshare_loop();
    int code = 0;
    HANDLE event = minyar_net_appLoopWindowsAttach(loop, &code);
    if (!event)
        return shared_result(7, code, 0);
    app_loop = loop;
    app_wake = event;
    app_armed = true;
    if (!minyar_net_appLoopObserve(loop, loop_changed)) {
        unshare_loop();
        return shared_result(6, ERROR_INVALID_HANDLE, 0);
    }
    return shared_result(0, 0, loop);
#else
    (void)loop;
    return shared_result(9, ERROR_NOT_SUPPORTED, 0);
#endif
}
MinyarBytes *minyar_windows_unshareNetworkLoopRaw(void) {
    thread();
#ifdef MINYAR_APP_EVENT_LOOP
    bool attached = app_loop != 0;
    unshare_loop();
    return shared_result(0, 0, attached);
#else
    return shared_result(9, ERROR_NOT_SUPPORTED, 0);
#endif
}
bool minyar_windows_nextEvent(double seconds) {
    thread();
    if (!isfinite(seconds) || seconds < 0 || seconds > 86400)
        fail("windows: invalid event timeout");
    free(current.text);
    memset(&current, 0, sizeof(current));
    if (delivered_quit)
        return false;
    ULONGLONG start = GetTickCount64();
    DWORD duration = (DWORD)ceil(seconds * 1000);
    for (;;) {
        MSG message;
        unsigned dispatched = 0;
        while (dispatched++ < 256 && PeekMessageW(&message, NULL, 0, 0, PM_REMOVE)) {
            if (message.message == WM_QUIT)
                minyar_windows_quit();
            else if (message.message == WM_KEYDOWN && message.wParam == VK_RETURN) {
                long long value = (long long)GetWindowLongPtrW(GetFocus(), GWLP_USERDATA);
                if (value && get(value)->kind == FIELD)
                    enqueue(6, value, read_text(get(value)->handle));
                else {
                    TranslateMessage(&message);
                    DispatchMessageW(&message);
                }
            } else {
                bool handled = false;
                for (size_t i = 0; i < capacity; i++)
                    if (widgets[i].kind == WINDOW &&
                        (message.hwnd == widgets[i].handle ||
                         IsChild(widgets[i].handle, message.hwnd)) &&
                        IsDialogMessageW(widgets[i].handle, &message)) {
                        handled = true;
                        break;
                    }
                if (!handled) {
                    TranslateMessage(&message);
                    DispatchMessageW(&message);
                }
            }
        }
        if (head) {
            Event *event = head;
            head = event->next;
            if (!head)
                tail = NULL;
            current = *event;
            current.next = NULL;
            free(event);
            queued--;
            if (current.type == 5)
                delivered_quit = true;
            return true;
        }
        ULONGLONG elapsed = GetTickCount64() - start;
#ifdef MINYAR_APP_EVENT_LOOP
        HANDLE wake = app_armed ? app_wake : NULL;
        uint64_t timer = app_loop && app_armed ? minyar_net_appLoopDeadline(app_loop) : UINT64_MAX;
        uint64_t now = GetTickCount64();
        if (wake && (WaitForSingleObject(wake, 0) == WAIT_OBJECT_0 || timer <= now)) {
            app_armed = false;
            return true;
        }
#endif
        if (elapsed >= duration)
            return true;
        DWORD delay = duration - (DWORD)elapsed;
#ifdef MINYAR_APP_EVENT_LOOP
        if (timer != UINT64_MAX && timer - now < delay)
            delay = (DWORD)(timer - now);
        DWORD status = MsgWaitForMultipleObjectsEx(wake ? 1 : 0, wake ? &wake : NULL, delay,
                                                   QS_ALLINPUT, MWMO_INPUTAVAILABLE);
#else
        DWORD status =
            MsgWaitForMultipleObjectsEx(0, NULL, delay, QS_ALLINPUT, MWMO_INPUTAVAILABLE);
#endif
        if (status == WAIT_FAILED)
            fail("windows: event wait failed");
    }
}
long long minyar_windows_eventType(void) {
    thread();
    return current.type;
}
long long minyar_windows_eventSource(void) {
    thread();
    return current.source;
}
MinyarText *minyar_windows_eventText(void) {
    thread();
    return narrow(current.text ? current.text : L"");
}
#ifdef MINYAR_WINDOWS_TEST
HWND minyar_windows_testHandle(long long value) {
    thread();
    return get(value)->handle;
}
HMENU minyar_windows_testMenu(long long value) {
    thread();
    return get(value)->menu;
}
#endif
