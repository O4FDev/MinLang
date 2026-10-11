#define WIN32_LEAN_AND_MEAN
#include "../minyar_native.h"
#include <windows.h>
#include <shellapi.h>
#include <commctrl.h>
#include <math.h>
#include <stdint.h>
#include <limits.h>

/* The UI owns only native memory. Generation checked IDs never expose pointers. */
enum {
    WINDOW = 1,
    COLUMN,
    ROW,
    VIEW,
    LABEL,
    BUTTON,
    FIELD,
    CHECKBOX,
    SECURE,
    EDITOR,
    TEXTVIEW,
    SLIDER,
    SEPARATOR,
    MENU,
    MENUITEM,
    TRAY
};
typedef struct Widget {
    uint32_t generation;
    int kind, spacing, width, height, suppress;
    int inset_top, inset_left, inset_bottom, inset_right, alignment, space_after;
    int min_width, min_height, max_width, max_height;
    unsigned grow_children;
    long long parent, first, last, next;
    HWND handle;
    HFONT font;
    HMENU menu, bar;
    UINT tray_id;
    double minimum, maximum;
    HACCEL accelerators;
    ACCEL accelerator;
    bool disabled, positioned, hidden, grows, fills, custom_spacing;
    int measured_dpi, measured_width, measured_height;
    int placed_x, placed_y, placed_width, placed_height;
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
static unsigned next_command = 1;
#ifdef MINYAR_WINDOWS_TEST
static unsigned long long measured_controls, positioned_controls;
#endif
static int layout_dpi;
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
    if (layout_dpi)
        return MulDiv(value, layout_dpi, 96);
    HDC dc = GetDC(root(w)->handle);
    int dpi = dc ? GetDeviceCaps(dc, LOGPIXELSY) : 96;
    if (dc)
        ReleaseDC(root(w)->handle, dc);
    return MulDiv(value, dpi, 96);
}
static bool editable(const Widget *w) {
    return w->kind == FIELD || w->kind == SECURE || w->kind == EDITOR;
}
static wchar_t *edit_text(Widget *w, const MinyarText *value) {
    wchar_t *text = wide(value);
    if (w->kind != EDITOR && w->kind != TEXTVIEW)
        return text;
    size_t length = wcslen(text), extra = 0;
    for (size_t i = 0; i < length; i++)
        if (text[i] == L'\n' && (!i || text[i - 1] != L'\r'))
            extra++;
    wchar_t *out = calloc(length + extra + 1, sizeof(*out));
    if (!out)
        fail("windows: allocation failed");
    size_t at = 0;
    for (size_t i = 0; i < length; i++) {
        if (text[i] == L'\n' && (!i || text[i - 1] != L'\r'))
            out[at++] = L'\r';
        out[at++] = text[i];
    }
    free(text);
    return out;
}
static int extent(int64_t value) {
    return value <= 0 ? 0 : value > INT_MAX ? INT_MAX : (int)value;
}
static bool stack(const Widget *w) {
    return w->kind == COLUMN || w->kind == ROW;
}
static bool hidden(const Widget *w) {
    for (;;) {
        if (w->hidden)
            return true;
        if (!w->parent)
            return false;
        w = get(w->parent);
    }
}
static int bounded(Widget *w, int value, bool horizontal) {
    int minimum_points = horizontal ? w->min_width : w->min_height;
    int maximum_points = horizontal ? w->max_width : w->max_height;
    if (!minimum_points && !maximum_points)
        return value < 0 ? 0 : value;
    int minimum = scaled(w, minimum_points);
    int maximum = scaled(w, maximum_points);
    if (value < minimum)
        value = minimum;
    if (maximum && value > maximum)
        value = maximum;
    return value < 0 ? 0 : value;
}
static int gap(Widget *parent, Widget *previous) {
    return previous ? scaled(parent, previous->custom_spacing ? previous->space_after : parent->spacing) : 0;
}
static void remember_measure(Widget *w, int width, int height) {
    if (w->measured_dpi != layout_dpi)
        w->positioned = false;
    w->measured_dpi = layout_dpi;
    w->measured_width = width;
    w->measured_height = height;
}
static void measure(Widget *w, int *width, int *height) {
    if (stack(w)) {
        int64_t x = 0, y = 0;
        Widget *previous = NULL;
        for (long long child = w->first; child; child = get(child)->next) {
            Widget *c = get(child);
            if (c->kind >= MENU || c->hidden)
                continue;
            int cw, ch;
            measure(c, &cw, &ch);
            if (w->kind == ROW) {
                x += (int64_t)gap(w, previous) + cw;
                if (ch > y)
                    y = ch;
            } else {
                if (cw > x)
                    x = cw;
                y += (int64_t)gap(w, previous) + ch;
            }
            previous = c;
        }
        *width = extent(x + scaled(w, w->inset_left) + scaled(w, w->inset_right));
        *height = extent(y + scaled(w, w->inset_top) + scaled(w, w->inset_bottom));
        if (w->width)
            *width = scaled(w, w->width);
        if (w->height)
            *height = scaled(w, w->height);
        *width = bounded(w, *width, true);
        *height = bounded(w, *height, false);
        return;
    }
    if (layout_dpi && w->measured_dpi == layout_dpi) {
        *width = w->measured_width;
        *height = w->measured_height;
        return;
    }
    if (w->kind == VIEW || w->kind == EDITOR || w->kind == TEXTVIEW ||
        w->kind == SLIDER || w->kind == SEPARATOR) {
        *width = scaled(w, w->width ? w->width : w->kind == VIEW ? 0 : 200);
        *height = scaled(w, w->height              ? w->height
                            : w->kind == VIEW      ? 0
                            : w->kind == SEPARATOR ? 2
                            : w->kind == SLIDER    ? 28
                                                   : 100);
        *width = bounded(w, *width, true);
        *height = bounded(w, *height, false);
        remember_measure(w, *width, *height);
        return;
    }
#ifdef MINYAR_WINDOWS_TEST
    measured_controls++;
#endif
    wchar_t *text = read_text(w->handle);
    HDC dc = GetDC(w->handle);
    HFONT old = SelectObject(dc, w->font ? w->font : GetStockObject(DEFAULT_GUI_FONT));
    SIZE size = {0};
    GetTextExtentPoint32W(dc, text, (int)wcslen(text), &size);
    SelectObject(dc, old);
    ReleaseDC(w->handle, dc);
    free(text);
    int extra = editable(w) ? 24 : (w->kind == LABEL ? 0 : 32);
    *width = extent((int64_t)size.cx + scaled(w, extra));
    *height = extent((int64_t)size.cy + scaled(w, w->kind == LABEL ? 4 : 14));
    int minimum = scaled(w, editable(w) ? 120 : 40);
    if (*width < minimum)
        *width = minimum;
    if (w->width)
        *width = scaled(w, w->width);
    if (w->height)
        *height = scaled(w, w->height);
    *width = bounded(w, *width, true);
    *height = bounded(w, *height, false);
    remember_measure(w, *width, *height);
}
static bool grows(const Widget *parent, const Widget *child) {
    return child->grows && !(parent->kind == ROW ? child->width : child->height);
}
static int growth_capacity(Widget *parent, Widget *child) {
    int width, height;
    measure(child, &width, &height);
    int maximum = parent->kind == ROW ? child->max_width : child->max_height;
    int base = parent->kind == ROW ? width : height;
    return maximum ? extent((int64_t)scaled(child, maximum) - base) : INT_MAX - base;
}
static uint64_t growth_cost(Widget *parent, int level) {
    uint64_t cost = 0;
    for (long long child = parent->first; child; child = get(child)->next) {
        Widget *c = get(child);
        if (c->kind >= MENU || c->hidden || !grows(parent, c))
            continue;
        int capacity = growth_capacity(parent, c);
        cost += (unsigned)(level < capacity ? level : capacity);
    }
    return cost;
}
static void arrange(Widget *w, int x, int y, int width, int height) {
    if (w->handle && w->kind != WINDOW) {
        if (w->positioned && w->placed_x == x && w->placed_y == y && w->placed_width == width &&
            w->placed_height == height)
            return;
        w->placed_x = x;
        w->placed_y = y;
        w->placed_width = width;
        w->placed_height = height;
        w->positioned = true;
#ifdef MINYAR_WINDOWS_TEST
        positioned_controls++;
#endif
        if (!SetWindowPos(w->handle, NULL, x, y, width, height, SWP_NOZORDER | SWP_NOACTIVATE))
            w->positioned = false;
        return;
    }
    int left = scaled(w, w->inset_left), top = scaled(w, w->inset_top);
    x = extent((int64_t)x + left);
    y = extent((int64_t)y + top);
    width = extent((int64_t)width - left - scaled(w, w->inset_right));
    height = extent((int64_t)height - top - scaled(w, w->inset_bottom));
    int64_t used = 0;
    unsigned flexible = 0;
    Widget *previous = NULL;
    if (w->grow_children)
        for (long long child = w->first; child; child = get(child)->next) {
            Widget *c = get(child);
            if (c->kind >= MENU || c->hidden)
                continue;
            int cw, ch;
            measure(c, &cw, &ch);
            used += (int64_t)gap(w, previous) + (w->kind == ROW ? cw : ch);
            if (grows(w, c))
                flexible++;
            previous = c;
        }
    int remaining = extent((int64_t)(w->kind == ROW ? width : height) - used);
    int level = 0, residual = 0;
    if (flexible && remaining) {
        // Find one fair expansion level, excluding capped children. No arrays
        // or quadratic retries are needed when many siblings have different caps.
        int low = 0, high = remaining;
        while (low < high) {
            int middle = low + (high - low) / 2 + (high - low) % 2;
            if (growth_cost(w, middle) <= (uint64_t)remaining)
                low = middle;
            else
                high = middle - 1;
        }
        level = low;
        residual = remaining - (int)growth_cost(w, level);
    }
    int64_t cursor = w->kind == ROW ? x : y;
    previous = NULL;
    for (long long child = w->first; child; child = get(child)->next) {
        Widget *c = get(child);
        if (c->kind >= MENU || c->hidden)
            continue;
        cursor += gap(w, previous);
        int cw, ch;
        measure(c, &cw, &ch);
        if (grows(w, c)) {
            int capacity = growth_capacity(w, c);
            int addition = level < capacity ? level : capacity;
            if (residual && addition < capacity) {
                addition++;
                residual--;
            }
            if (w->kind == ROW)
                cw = extent((int64_t)cw + addition);
            else
                ch = extent((int64_t)ch + addition);
        }
        bool horizontal = w->kind != ROW;
        int available = horizontal ? width : height;
        int across = horizontal ? cw : ch;
        bool explicit_size = horizontal ? c->width != 0 : c->height != 0;
        // A zero alignment retains the existing column-fill default. Explicit
        // alignment uses intrinsic cross-axis size unless fill was requested.
        if (!explicit_size && (c->fills || (horizontal && !w->alignment)))
            across = bounded(c, available, horizontal);
        int offset = available > across ? available - across : 0;
        offset = w->alignment == 3 ? offset : w->alignment == 2 ? offset / 2 : 0;
        if (horizontal) {
            cw = across;
            arrange(c, extent((int64_t)x + offset), extent(cursor), cw, ch);
            cursor += ch;
        } else {
            ch = across;
            arrange(c, extent(cursor), extent((int64_t)y + offset), cw, ch);
            cursor += cw;
        }
        previous = c;
    }
}
static void layout(Widget *w) {
    w = root(w);
    int previous_dpi = layout_dpi;
    HDC dc = GetDC(w->handle);
    layout_dpi = dc ? GetDeviceCaps(dc, LOGPIXELSY) : 96;
    if (dc)
        ReleaseDC(w->handle, dc);
    if (layout_dpi <= 0)
        layout_dpi = 96;
    RECT area;
    if (GetClientRect(w->handle, &area))
        arrange(w, 0, 0, area.right, area.bottom);
    layout_dpi = previous_dpi;
}
static void rebuild_accelerators(Widget *window) {
    unsigned count = 0;
    for (size_t i = 0; i < capacity; i++)
        if (widgets[i].kind == MENUITEM && widgets[i].accelerator.cmd &&
            root(widgets + i) == window)
            count++;
    ACCEL *bindings = count ? calloc(count, sizeof(*bindings)) : NULL;
    if (count && !bindings)
        fail("windows: allocation failed");
    unsigned at = 0;
    for (size_t i = 0; i < capacity; i++)
        if (widgets[i].kind == MENUITEM && widgets[i].accelerator.cmd &&
            root(widgets + i) == window)
            bindings[at++] = widgets[i].accelerator;
    HACCEL table = count ? CreateAcceleratorTableW(bindings, (int)count) : NULL;
    free(bindings);
    if (count && !table)
        fail("windows: unable to create accelerators");
    if (window->accelerators)
        DestroyAcceleratorTable(window->accelerators);
    window->accelerators = table;
}
static bool translate_accelerator(MSG *message) {
    if (message->message != WM_KEYDOWN && message->message != WM_SYSKEYDOWN)
        return false;
    for (size_t i = 0; i < capacity; i++)
        if (widgets[i].kind == WINDOW && widgets[i].accelerators &&
            (message->hwnd == widgets[i].handle || IsChild(widgets[i].handle, message->hwnd)) &&
            TranslateAcceleratorW(widgets[i].handle, widgets[i].accelerators, message))
            return true;
    return false;
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
            if (editable(c) && code == EN_CHANGE)
                c->measured_dpi = 0;
            if (!c->suppress && !c->disabled && editable(c) && code == EN_CHANGE)
                enqueue(2, child, read_text(c->handle));
            else if (!c->suppress && !c->disabled && (c->kind == BUTTON || c->kind == CHECKBOX) &&
                     code == BN_CLICKED)
                enqueue(1, child, NULL);
        }
        return 0;
    }
    if (message == WM_COMMAND && !lp && HIWORD(wp) == 1 && w) {
        for (size_t i = 0; i < capacity; i++)
            if (widgets[i].kind == MENUITEM && widgets[i].accelerator.cmd == LOWORD(wp) &&
                !widgets[i].disabled && root(widgets + i) == w)
                enqueue(1, id(widgets + i), NULL);
        return 0;
    }
    if ((message == WM_HSCROLL || message == WM_VSCROLL) && lp) {
        long long child = (long long)GetWindowLongPtrW((HWND)lp, GWLP_USERDATA);
        if (child && get(child)->kind == SLIDER && !get(child)->suppress && !get(child)->disabled)
            enqueue(2, child, NULL);
        return 0;
    }
    if (message == WM_MENUCOMMAND) {
        MENUITEMINFOW item = {0};
        item.cbSize = sizeof(item);
        item.fMask = MIIM_DATA | MIIM_STATE;
        if (GetMenuItemInfoW((HMENU)lp, (UINT)wp, TRUE, &item) && item.dwItemData &&
            !(item.fState & MFS_DISABLED))
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
    if (w && (message == WM_SETTINGCHANGE || message == WM_FONTCHANGE)) {
        for (size_t i = 0; i < capacity; i++)
            widgets[i].measured_dpi = 0;
        layout(w);
    }
    if (w && w->kind == WINDOW && message == WM_GETMINMAXINFO &&
        (w->min_width || w->min_height)) {
        MINMAXINFO *limits = (MINMAXINFO *)lp;
        RECT frame = {0, 0, scaled(w, w->min_width), scaled(w, w->min_height)};
        if (AdjustWindowRectEx(&frame, (DWORD)GetWindowLongPtrW(handle, GWL_STYLE),
                               GetMenu(handle) != NULL, (DWORD)GetWindowLongPtrW(handle, GWL_EXSTYLE))) {
            if (w->min_width)
                limits->ptMinTrackSize.x = frame.right - frame.left;
            if (w->min_height)
                limits->ptMinTrackSize.y = frame.bottom - frame.top;
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
    INITCOMMONCONTROLSEX common = {sizeof(common), ICC_BAR_CLASSES};
    if (!InitCommonControlsEx(&common))
        fail("windows: unable to initialize common controls");
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
    wchar_t *text = edit_text(w, title);
    bool edit = editable(w) || kind == TEXTVIEW;
    const wchar_t *class_name = kind == SLIDER                       ? TRACKBAR_CLASSW
                                : edit                               ? L"EDIT"
                                : kind == VIEW || kind == LABEL || kind == SEPARATOR ? L"STATIC"
                                                                     : L"BUTTON";
    DWORD style = WS_CHILD | (hidden(w) ? 0 : WS_VISIBLE);
    if (kind == SLIDER)
        style |= TBS_HORZ | TBS_NOTICKS | WS_TABSTOP;
    else if (kind == EDITOR || kind == TEXTVIEW)
        style |= ES_MULTILINE | ES_AUTOVSCROLL | WS_VSCROLL | WS_TABSTOP |
                 (kind == TEXTVIEW ? ES_READONLY : ES_WANTRETURN);
    else if (edit)
        style |= ES_AUTOHSCROLL | WS_TABSTOP | (kind == SECURE ? ES_PASSWORD : 0);
    else if (kind == VIEW || kind == LABEL || kind == SEPARATOR)
        style |= kind == SEPARATOR ? SS_ETCHEDHORZ : SS_LEFT;
    else
        style |= WS_TABSTOP | (kind == CHECKBOX ? BS_AUTOCHECKBOX : BS_PUSHBUTTON);
    w->handle =
        CreateWindowExW(edit && kind != TEXTVIEW ? WS_EX_CLIENTEDGE : 0, class_name, text, style, 0,
                        0, 1, 1, root(w)->handle, NULL, GetModuleHandleW(NULL), NULL);
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
static const MinyarText empty_text = {.bytes = (const unsigned char *)""};
static void dimension(long long value) {
    if (value < 0 || value > 100000)
        fail("windows: dimensions must be between 0 and 100000 points");
}
static Widget *view(long long value) {
    Widget *w = get(value);
    if (w->kind == WINDOW || w->kind >= MENU)
        fail("windows: layout requires a view");
    return w;
}
static Widget *stack_child(long long value) {
    Widget *w = view(value);
    if (!w->parent || !stack(get(w->parent)))
        fail("windows: layout requires a view inside a row or column");
    return w;
}
long long minyar_windows_view(long long parent) {
    return control(VIEW, parent, &empty_text, false);
}
long long minyar_windows_spacer(long long parent) {
    thread();
    if (!stack(get(parent)))
        fail("windows: spacer requires a row or column");
    long long value = minyar_windows_view(parent);
    Widget *w = get(value);
    w->grows = true;
    get(parent)->grow_children++;
    layout(w);
    return value;
}
void minyar_windows_grow(long long value) {
    thread();
    Widget *w = stack_child(value);
    if (!w->grows) {
        w->grows = true;
        get(w->parent)->grow_children++;
        layout(w);
    }
}
void minyar_windows_fill(long long value) {
    thread();
    Widget *w = stack_child(value);
    if (!w->fills) {
        w->fills = true;
        layout(w);
    }
}
static void bounds(long long value, long long width, long long height, bool minimum) {
    thread();
    dimension(width); dimension(height);
    Widget *w = minimum ? get(value) : view(value);
    if (w->kind >= MENU)
        fail("windows: minimumSize requires a window or view");
    int min_width = minimum ? (int)width : w->min_width;
    int min_height = minimum ? (int)height : w->min_height;
    int max_width = minimum ? w->max_width : (int)width;
    int max_height = minimum ? w->max_height : (int)height;
    if ((max_width && min_width > max_width) || (max_height && min_height > max_height))
        fail("windows: minimum size exceeds maximum size");
    if ((w->width && (w->width < min_width || (max_width && w->width > max_width))) ||
        (w->height && (w->height < min_height || (max_height && w->height > max_height))))
        fail("windows: explicit size conflicts with bounds");
    if (w->min_width == min_width && w->min_height == min_height &&
        w->max_width == max_width && w->max_height == max_height)
        return;
    w->min_width = min_width; w->min_height = min_height;
    w->max_width = max_width; w->max_height = max_height;
    w->measured_dpi = 0;
    layout(w);
}
void minyar_windows_minimumSize(long long value, long long width, long long height) {
    bounds(value, width, height, true);
}
void minyar_windows_maximumSize(long long value, long long width, long long height) {
    bounds(value, width, height, false);
}
void minyar_windows_insets(long long value, long long top, long long left, long long bottom, long long right) {
    thread();
    dimension(top); dimension(left); dimension(bottom); dimension(right);
    Widget *w = get(value);
    if (!stack(w))
        fail("windows: insets requires a row or column");
    w->inset_top = (int)top; w->inset_left = (int)left;
    w->inset_bottom = (int)bottom; w->inset_right = (int)right;
    w->measured_dpi = 0;
    layout(w);
}
void minyar_windows_align(long long value, long long alignment) {
    thread();
    Widget *w = get(value);
    if (!stack(w))
        fail("windows: align requires a row or column");
    if (alignment < 1 || alignment > 3)
        fail("windows: alignment must be START, CENTER, or END");
    if (w->alignment != alignment) {
        w->alignment = (int)alignment;
        layout(w);
    }
}
void minyar_windows_spaceAfter(long long value, long long points) {
    thread();
    dimension(points);
    Widget *w = stack_child(value);
    if (!w->custom_spacing || w->space_after != points) {
        w->custom_spacing = true;
        w->space_after = (int)points;
        layout(w);
    }
}
static void show_descendants(Widget *w, bool ancestor_hidden) {
    bool hide = ancestor_hidden || w->hidden;
    if (w->handle)
        ShowWindow(w->handle, hide ? SW_HIDE : SW_SHOWNOACTIVATE);
    for (long long child = w->first; child; child = get(child)->next)
        if (get(child)->kind < MENU)
            show_descendants(get(child), hide);
}
void minyar_windows_hidden(long long value, bool hide) {
    thread();
    Widget *w = view(value);
    if (w->hidden == hide)
        return;
    w->hidden = hide;
    show_descendants(w, w->parent && hidden(get(w->parent)));
    layout(w);
}
long long minyar_windows_secureField(long long parent) {
    return control(SECURE, parent, &empty_text, false);
}
long long minyar_windows_textEditor(long long parent, const MinyarText *text) {
    return control(EDITOR, parent, text, false);
}
long long minyar_windows_textView(long long parent, const MinyarText *text) {
    return control(TEXTVIEW, parent, text, false);
}
long long minyar_windows_separator(long long parent) {
    return control(SEPARATOR, parent, &empty_text, false);
}
long long minyar_windows_slider(long long parent, double minimum, double maximum, double value) {
    if (!isfinite(minimum) || !isfinite(maximum) || minimum >= maximum ||
        !isfinite(maximum - minimum) || !isfinite(value) || value < minimum || value > maximum)
        fail("windows: invalid slider range or value");
    long long handle = control(SLIDER, parent, &empty_text, false);
    Widget *w = get(handle);
    w->minimum = minimum;
    w->maximum = maximum;
    SendMessageW(w->handle, TBM_SETRANGEMIN, FALSE, 0);
    SendMessageW(w->handle, TBM_SETRANGEMAX, FALSE, 1000000);
    SendMessageW(w->handle, TBM_SETPOS, TRUE,
                 (LPARAM)llround((value - minimum) / (maximum - minimum) * 1000000));
    return handle;
}
void minyar_windows_size(long long handle, long long width, long long height) {
    thread();
    if (width < 0 || height < 0 || width > 32768 || height > 32768)
        fail("windows: invalid explicit size");
    Widget *w = get(handle);
    if (w->kind >= MENU || w->kind == WINDOW)
        fail("windows: size requires a view");
    if ((width && (width < w->min_width || (w->max_width && width > w->max_width))) ||
        (height && (height < w->min_height || (w->max_height && height > w->max_height))))
        fail("windows: explicit size conflicts with bounds");
    w->width = (int)width;
    w->height = (int)height;
    w->measured_dpi = 0;
    layout(w);
}
double minyar_windows_value(long long handle) {
    thread();
    Widget *w = get(handle);
    if (w->kind != SLIDER)
        fail("windows: handle is not a slider");
    long long position = SendMessageW(w->handle, TBM_GETPOS, 0, 0);
    return position == 0 ? w->minimum
           : position == 1000000
               ? w->maximum
               : w->minimum + (w->maximum - w->minimum) * (double)position / 1000000;
}
void minyar_windows_setValue(long long handle, double value) {
    thread();
    Widget *w = get(handle);
    if (w->kind != SLIDER)
        fail("windows: handle is not a slider");
    if (!isfinite(value) || value < w->minimum || value > w->maximum)
        fail("windows: slider value is outside its range");
    w->suppress++;
    SendMessageW(w->handle, TBM_SETPOS, TRUE,
                 (LPARAM)llround((value - w->minimum) / (w->maximum - w->minimum) * 1000000));
    w->suppress--;
}
void minyar_windows_appendText(long long handle, const MinyarText *text) {
    thread();
    Widget *w = get(handle);
    if (w->kind != EDITOR && w->kind != TEXTVIEW)
        fail("windows: appendText requires a multiline text control");
    wchar_t *value = edit_text(w, text);
    DWORD first = 0, last = 0;
    SendMessageW(w->handle, EM_GETSEL, (WPARAM)&first, (LPARAM)&last);
    w->suppress++;
    /* A negative start only clears selection at its existing caret. Select the
     * actual UTF-16 end so appending never inserts before the current text. */
    int end = GetWindowTextLengthW(w->handle);
    SendMessageW(w->handle, EM_SETSEL, (WPARAM)end, (LPARAM)end);
    SendMessageW(w->handle, EM_REPLACESEL, FALSE, (LPARAM)value);
    SendMessageW(w->handle, EM_SETSEL, first, last);
    w->suppress--;
    free(value);
}
void minyar_windows_enabled(long long handle, bool enabled) {
    thread();
    Widget *w = get(handle);
    w->disabled = !enabled;
    if (stack(w)) {
        for (long long child = w->first; child; child = get(child)->next)
            minyar_windows_enabled(child, enabled);
    } else if (w->kind > WINDOW && w->kind < MENU) {
        EnableWindow(w->handle, enabled);
    } else if (w->kind == MENUITEM) {
        HMENU menu = get(w->parent)->menu;
        for (int i = 0; i < GetMenuItemCount(menu); i++) {
            MENUITEMINFOW item = {0};
            item.cbSize = sizeof(item);
            item.fMask = MIIM_DATA;
            if (GetMenuItemInfoW(menu, (UINT)i, TRUE, &item) &&
                item.dwItemData == (ULONG_PTR)handle)
                EnableMenuItem(menu, (UINT)i, MF_BYPOSITION | (enabled ? MF_ENABLED : MF_DISABLED));
        }
    } else
        fail("windows: enabled requires a control or menu item");
}
static long long window_dimension(long long handle, bool horizontal) {
    thread();
    Widget *w = get(handle);
    if (w->kind != WINDOW)
        fail("windows: handle is not a window");
    RECT area;
    if (!GetClientRect(w->handle, &area))
        fail("windows: unable to read window size");
    return MulDiv(horizontal ? area.right : area.bottom, 96, scaled(w, 96));
}
long long minyar_windows_width(long long handle) {
    return window_dimension(handle, true);
}
long long minyar_windows_height(long long handle) {
    return window_dimension(handle, false);
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
    if (stack(w) || w->kind == WINDOW)
        w->inset_top = w->inset_left = w->inset_bottom = w->inset_right = (int)padding;
    layout(w);
}
void minyar_windows_setText(long long value, const MinyarText *text) {
    thread();
    Widget *w = get(value);
    if (!w->handle)
        fail("windows: container has no text");
    wchar_t *s = edit_text(w, text);
    w->suppress++;
    SetWindowTextW(w->handle, s);
    w->suppress--;
    free(s);
    w->measured_dpi = 0;
    layout(w);
}
MinyarText *minyar_windows_text(long long value) {
    thread();
    Widget *w = get(value);
    if (!w->handle)
        fail("windows: container has no text");
    wchar_t *s = read_text(w->handle);
    if (w->kind == EDITOR || w->kind == TEXTVIEW) {
        size_t write = 0;
        for (size_t read = 0; s[read]; read++)
            if (s[read] != L'\r' || s[read + 1] != L'\n')
                s[write++] = s[read];
        s[write] = 0;
    }
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
    w->measured_dpi = 0;
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
    while (w->first) {
        long long child = w->first;
        // Native disposal can synchronously reenter layout. Remove the child
        // before its handle becomes stale, while keeping its parent alive for
        // menu/control cleanup.
        w->first = get(child)->next;
        if (!w->first)
            w->last = 0;
        destroy(child);
        w = get(value);
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
    if (w->accelerators)
        DestroyAcceleratorTable(w->accelerators);
    // SetMenu can synchronously enqueue a resize after the first purge.
    // A disposed widget must not leave newly queued events with its handle.
    remove_events(value);
    w->kind = 0;
}
void minyar_windows_destroy(long long value) {
    thread();
    Widget *w = get(value);
    long long window = id(root(w));
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
        if (w->grows && p->grow_children)
            p->grow_children--;
    }
    destroy(value);
    if (window != value && get(window)->kind == WINDOW) {
        rebuild_accelerators(get(window));
        layout(get(window));
    }
}
void minyar_windows_clear(long long value) {
    thread();
    Widget *w = get(value);
    if (!stack(w))
        fail("windows: clear requires a row or column");
    long long child = w->first;
    w->first = w->last = 0;
    w->grow_children = 0;
    while (child) {
        long long next = get(child)->next;
        destroy(child);
        child = next;
    }
    layout(get(value));
}
void minyar_windows_remove(long long value) {
    thread();
    Widget *w = view(value);
    if (w->parent && get(w->parent)->kind == WINDOW)
        fail("windows: cannot remove a window's root view");
    stack_child(value);
    minyar_windows_destroy(value);
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
static ACCEL parse_accelerator(const MinyarText *raw) {
    ACCEL accelerator = {0};
    if (!raw->byte_length)
        return accelerator;
    if (raw->byte_length < 0 || raw->byte_length > 64)
        fail("windows: invalid menu shortcut");
    wchar_t *text = wide(raw);
    if (wcslen(text) > 64)
        fail("windows: invalid menu shortcut");
    wchar_t *key = text;
    wchar_t *plus;
    BYTE flags = FVIRTKEY;
    bool modifier = false;
    while ((plus = wcschr(key, L'+'))) {
        *plus = 0;
        BYTE flag = !_wcsicmp(key, L"Ctrl")    ? FCONTROL
                    : !_wcsicmp(key, L"Shift") ? FSHIFT
                    : !_wcsicmp(key, L"Alt")   ? FALT
                                               : 0;
        if (!flag || (flags & flag))
            fail("windows: invalid menu shortcut");
        flags |= flag;
        modifier = true;
        key = plus + 1;
    }
    WORD virtual_key = 0;
    if (key[0] && !key[1] &&
        ((key[0] >= L'a' && key[0] <= L'z') || (key[0] >= L'A' && key[0] <= L'Z') ||
         (key[0] >= L'0' && key[0] <= L'9'))) {
        virtual_key = key[0] >= L'a' && key[0] <= L'z' ? key[0] - L'a' + L'A' : key[0];
        if (!modifier)
            flags |= FCONTROL;
    } else if ((key[0] == L'F' || key[0] == L'f') && key[1]) {
        wchar_t *end;
        long number = wcstol(key + 1, &end, 10);
        if (*end || number < 1 || number > 24)
            fail("windows: invalid menu shortcut");
        virtual_key = (WORD)(VK_F1 + number - 1);
    } else {
        struct {
            const wchar_t *name;
            WORD key;
        } named[] = {{L"Enter", VK_RETURN}, {L"Escape", VK_ESCAPE}, {L"Space", VK_SPACE},
                     {L"Tab", VK_TAB},      {L"Delete", VK_DELETE}, {L"Backspace", VK_BACK},
                     {L"Home", VK_HOME},    {L"End", VK_END},       {L"Left", VK_LEFT},
                     {L"Right", VK_RIGHT},  {L"Up", VK_UP},         {L"Down", VK_DOWN}};
        for (size_t i = 0; i < sizeof(named) / sizeof(named[0]); i++)
            if (!_wcsicmp(key, named[i].name))
                virtual_key = named[i].key;
    }
    free(text);
    if (!virtual_key)
        fail("windows: invalid menu shortcut");
    accelerator.fVirt = flags;
    accelerator.key = virtual_key;
    return accelerator;
}
long long minyar_windows_menuItem(long long menu, const MinyarText *title, const MinyarText *key) {
    thread();
    if (get(menu)->kind != MENU)
        fail("windows: handle is not a menu");
    ACCEL accelerator = parse_accelerator(key);
    Widget *window = root(get(menu));
    if (accelerator.key && window->kind != WINDOW)
        fail("windows: menu shortcuts require a window");
    for (size_t i = 0; i < capacity; i++)
        if (accelerator.key && widgets[i].kind == MENUITEM && root(widgets + i) == window &&
            widgets[i].accelerator.key == accelerator.key &&
            widgets[i].accelerator.fVirt == accelerator.fVirt)
            fail("windows: duplicate menu shortcut");
    if (accelerator.key && next_command > 65535)
        fail("windows: accelerator command space exhausted");
    if (accelerator.key)
        accelerator.cmd = (WORD)next_command++;
    long long value = create(MENUITEM, menu);
    wchar_t *text = wide(title);
    MENUITEMINFOW item = {0};
    item.cbSize = sizeof(item);
    item.fMask = MIIM_STRING | MIIM_DATA | MIIM_ID;
    item.dwTypeData = text;
    item.dwItemData = (ULONG_PTR)value;
    item.wID = accelerator.cmd;
    if (!InsertMenuItemW(get(menu)->menu, (UINT)-1, TRUE, &item))
        fail("windows: unable to append menu item");
    free(text);
    get(value)->accelerator = accelerator;
    window = root(get(value));
    if (accelerator.key)
        rebuild_accelerators(window);
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
            // The COM activator stores only native data and wakes this owner.
            // The caller consumes the typed winnotify.nextAction() result.
            if (message.message == WM_APP + 0x249 && !message.hwnd)
                return true;
            if (message.message == WM_QUIT)
                minyar_windows_quit();
            else if (translate_accelerator(&message)) {
                // TranslateAccelerator synchronously queued its native action.
            } else if (message.message == WM_KEYDOWN && message.wParam == VK_RETURN) {
                long long value = (long long)GetWindowLongPtrW(GetFocus(), GWLP_USERDATA);
                if (value && !get(value)->disabled &&
                    (get(value)->kind == FIELD || get(value)->kind == SECURE))
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
unsigned long long minyar_windows_testMeasures(void) {
    thread();
    return measured_controls;
}
unsigned long long minyar_windows_testPositions(void) {
    thread();
    return positioned_controls;
}
HWND minyar_windows_testHandle(long long value) {
    thread();
    return get(value)->handle;
}
HMENU minyar_windows_testMenu(long long value) {
    thread();
    return get(value)->menu;
}
HACCEL minyar_windows_testAccelerators(long long value) {
    thread();
    return get(value)->accelerators;
}
#endif
