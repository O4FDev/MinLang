#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0a00
#endif
#ifndef NTDDI_VERSION
#define NTDDI_VERSION 0x0a000000
#endif
#define WIDL_using_Windows_UI_Notifications
#define WIDL_using_Windows_Data_Xml_Dom
#define WIN32_LEAN_AND_MEAN
#define COBJMACROS
#include "../minyar_native.h"
#include <stdint.h>
#ifdef MINYAR_NOTIFY_TEST
#include <assert.h>
#endif
#include <windows.h>
#include <shlobj.h>
#include <propsys.h>
#include <propkey.h>
#include <bcrypt.h>
#include <roapi.h>
#include <winstring.h>
#include <initguid.h>
#include <notificationactivationcallback.h>
#include <windows.data.xml.dom.h>
#include <windows.ui.notifications.h>

// All OS callback data is native, protected by this lock; no managed references.
#ifndef NOTICE_LIMIT
#define NOTICE_LIMIT 1024
#endif
#define ACTION_LIMIT 5
#ifndef ACTION_QUEUE_LIMIT
#define ACTION_QUEUE_LIMIT 256
#endif
#define NOTICE_MAX_AGE (7ULL * 24 * 60 * 60 * 10000000)
static DWORD notify_owner;
static SRWLOCK notify_lock = SRWLOCK_INIT;
static wchar_t app_id[129], executable[32768], registry_path[256], shortcut_path[32768];
static wchar_t clsid_text[40], server_path[128], server_command[33024];
static wchar_t app_registration_path[256];
static CLSID activator_clsid;
static DWORD class_cookie;
static bool initialized, ro_owned, ro_initialized;
static IToastNotifier *notifier;
static IToastNotificationHistory *history;
static IUnknown *marshaller;
typedef struct FailedHandler FailedHandler;
typedef struct Notice {
    long long id;
    wchar_t token[33];
    IToastNotification *toast;
    FailedHandler *failed;
    EventRegistrationToken failed_token;
    struct Notice *next;
} Notice;
static Notice *notices;
static long long next_id = 1;
static unsigned notice_count;
typedef struct ActionEvent {
    wchar_t token[33], action[65];
    struct ActionEvent *next;
} ActionEvent;
static ActionEvent *actions_head, *actions_tail;
static unsigned action_count;
static void notify_thread(void) {
    DWORD id = GetCurrentThreadId();
    if (!notify_owner)
        notify_owner = id;
    if (id != notify_owner)
        minyar_native_stop("Windows notifications require their owning thread.");
}
static MinyarBytes *notify_result(uint32_t error, HRESULT native, int64_t value) {
    MinyarBytes *b = minyar_bytes_new(16);
    memcpy((void *)b->bytes, &error, 4);
    memcpy((unsigned char *)b->bytes + 4, &native, 4);
    memcpy((unsigned char *)b->bytes + 8, &value, 8);
    return b;
}
static MinyarBytes *notify_hresult(HRESULT hr, int64_t value) {
    return notify_result(SUCCEEDED(hr) ? 0 : (hr == E_ACCESSDENIED ? 8 : 7), hr, value);
}
static wchar_t *notify_wide(const MinyarText *text, unsigned maximum) {
    if (text->byte_length < 0 || text->byte_length > INT_MAX ||
        memchr(text->bytes, 0, (size_t)text->byte_length))
        return NULL;
    int length = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, (const char *)text->bytes,
                                     (int)text->byte_length, NULL, 0);
    if ((!length && text->byte_length) || (unsigned)length >= maximum)
        return NULL;
    wchar_t *out = calloc((size_t)length + 1, sizeof(*out));
    if (!out)
        minyar_native_stop("Notification allocation failed.");
    MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, (const char *)text->bytes,
                        (int)text->byte_length, out, length);
    for (int i = 0; i < length; i++)
        if ((out[i] < 32 && out[i] != 9 && out[i] != 10 && out[i] != 13) || out[i] == 0xfffe ||
            out[i] == 0xffff) {
            free(out);
            return NULL;
        }
    return out;
}
static bool identifier(const wchar_t *value, unsigned maximum) {
    unsigned n = 0;
    for (; value[n]; n++)
        if (n >= maximum ||
            !((value[n] >= 'A' && value[n] <= 'Z') || (value[n] >= 'a' && value[n] <= 'z') ||
              (value[n] >= '0' && value[n] <= '9') || value[n] == '.' || value[n] == '_' ||
              value[n] == '-'))
            return false;
    return n > 0;
}
static HRESULT digest(const void *bytes, ULONG length, unsigned char output[32]) {
    BCRYPT_ALG_HANDLE algorithm = NULL;
    BCRYPT_HASH_HANDLE hash = NULL;
    NTSTATUS status = BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, NULL, 0);
    if (status >= 0)
        status = BCryptCreateHash(algorithm, &hash, NULL, 0, NULL, 0, 0);
    if (status >= 0)
        status = BCryptHashData(hash, (PUCHAR)bytes, length, 0);
    if (status >= 0)
        status = BCryptFinishHash(hash, output, 32, 0);
    if (hash)
        BCryptDestroyHash(hash);
    if (algorithm)
        BCryptCloseAlgorithmProvider(algorithm, 0);
    return status >= 0 ? S_OK : E_FAIL;
}
static HRESULT prepare_identity(const wchar_t *id) {
    if (!identifier(id, 128))
        return E_INVALIDARG;
    DWORD size = GetModuleFileNameW(NULL, executable, 32768);
    if (!size || size >= 32768)
        return HRESULT_FROM_WIN32(GetLastError());
    wcscpy(app_id, id);
    unsigned char hash[32];
    HRESULT hr = digest(id, (ULONG)(wcslen(id) * sizeof(wchar_t)), hash);
    if (FAILED(hr))
        return hr;
    memcpy(&activator_clsid, hash, 16);
    activator_clsid.Data3 = (activator_clsid.Data3 & 0x0fff) | 0x5000;
    activator_clsid.Data4[0] = (activator_clsid.Data4[0] & 0x3f) | 0x80;
    StringFromGUID2(&activator_clsid, clsid_text, 40);
    swprintf(registry_path, 256, L"Software\\Minyar\\Notifications\\%ls", id);
    swprintf(server_path, 128, L"Software\\Classes\\CLSID\\%ls\\LocalServer32", clsid_text);
    swprintf(app_registration_path, 256, L"Software\\Classes\\AppUserModelId\\%ls", id);
    swprintf(server_command, 33024, L"\"%ls\" --minyar-toast-activate %ls", executable, id);
    PWSTR programs = NULL;
    hr = SHGetKnownFolderPath(&FOLDERID_Programs, 0, NULL, &programs);
    if (SUCCEEDED(hr)) {
        if (wcslen(programs) + wcslen(clsid_text) + 30 >= 32768)
            hr = E_INVALIDARG;
        else
            swprintf(shortcut_path, 32768, L"%ls\\Minyar-%ls.lnk", programs, clsid_text);
        CoTaskMemFree(programs);
    }
    return hr;
}
static LSTATUS read_string(HKEY root, const wchar_t *path, const wchar_t *name, wchar_t *out,
                           DWORD capacity) {
    DWORD size = capacity * sizeof(wchar_t), type = 0;
    HKEY key = NULL;
    LSTATUS status = RegOpenKeyExW(root, path, 0, KEY_QUERY_VALUE, &key);
    if (!status)
        status = RegQueryValueExW(key, name, NULL, &type, (BYTE *)out, &size);
    if (key)
        RegCloseKey(key);
    if (!status &&
        (type != REG_SZ || !size || size > capacity * sizeof(wchar_t) || size % sizeof(wchar_t) ||
         out[size / sizeof(wchar_t) - 1] != 0 || wcslen(out) + 1 != size / sizeof(wchar_t)))
        status = ERROR_INVALID_DATA;
    return status;
}
static HRESULT owned_value(const wchar_t *path, const wchar_t *name, const wchar_t *expected,
                           bool required) {
    wchar_t actual[33024];
    LSTATUS status = read_string(HKEY_CURRENT_USER, path, name, actual, 33024);
    if (status == ERROR_FILE_NOT_FOUND && !required) {
        HKEY key = NULL;
        status = RegOpenKeyExW(HKEY_CURRENT_USER, path, 0, KEY_QUERY_VALUE, &key);
        if (key)
            RegCloseKey(key);
        return status == ERROR_FILE_NOT_FOUND ? S_OK : E_ACCESSDENIED;
    }
    if (status)
        return required && status == ERROR_FILE_NOT_FOUND ? HRESULT_FROM_WIN32(ERROR_NOT_FOUND)
                                                          : E_ACCESSDENIED;
    return wcscmp(actual, expected) ? E_ACCESSDENIED : S_OK;
}
static HRESULT write_string(const wchar_t *path, const wchar_t *name, const wchar_t *value) {
    HKEY key = NULL;
    LSTATUS status =
        RegCreateKeyExW(HKEY_CURRENT_USER, path, 0, NULL, 0, KEY_SET_VALUE, NULL, &key, NULL);
    if (!status)
        status = RegSetValueExW(key, name, 0, REG_SZ, (const BYTE *)value,
                                (DWORD)((wcslen(value) + 1) * sizeof(wchar_t)));
    if (key)
        RegCloseKey(key);
    return HRESULT_FROM_WIN32(status);
}
static HRESULT shortcut(bool create) {
    IShellLinkW *link = NULL;
    IPropertyStore *properties = NULL;
    IPersistFile *persist = NULL;
    HRESULT hr = CoCreateInstance(&CLSID_ShellLink, NULL, CLSCTX_INPROC_SERVER, &IID_IShellLinkW,
                                  (void **)&link);
    if (SUCCEEDED(hr))
        hr = IShellLinkW_QueryInterface(link, &IID_IPropertyStore, (void **)&properties);
    if (SUCCEEDED(hr))
        hr = IShellLinkW_QueryInterface(link, &IID_IPersistFile, (void **)&persist);
    if (SUCCEEDED(hr) && GetFileAttributesW(shortcut_path) != INVALID_FILE_ATTRIBUTES) {
        hr = IPersistFile_Load(persist, shortcut_path, STGM_READ);
        wchar_t path[32768];
        PROPVARIANT value;
        PropVariantInit(&value);
        if (SUCCEEDED(hr))
            hr = IShellLinkW_GetPath(link, path, 32768, NULL, SLGP_RAWPATH);
        if (SUCCEEDED(hr) && _wcsicmp(path, executable))
            hr = E_ACCESSDENIED;
        if (SUCCEEDED(hr))
            hr = IPropertyStore_GetValue(properties, &PKEY_AppUserModel_ID, &value);
        if (SUCCEEDED(hr) &&
            (value.vt != VT_LPWSTR || !value.pwszVal || wcscmp(value.pwszVal, app_id)))
            hr = E_ACCESSDENIED;
        PropVariantClear(&value);
        if (SUCCEEDED(hr))
            hr =
                IPropertyStore_GetValue(properties, &PKEY_AppUserModel_ToastActivatorCLSID, &value);
        if (SUCCEEDED(hr) &&
            (value.vt != VT_CLSID || !value.puuid || !IsEqualGUID(value.puuid, &activator_clsid)))
            hr = E_ACCESSDENIED;
        PropVariantClear(&value);
    } else if (SUCCEEDED(hr) && !create)
        hr = HRESULT_FROM_WIN32(ERROR_NOT_FOUND);
    if (SUCCEEDED(hr) && create) {
        hr = IShellLinkW_SetPath(link, executable);
        PROPVARIANT value;
        PropVariantInit(&value);
        value.vt = VT_LPWSTR;
        value.pwszVal = app_id;
        if (SUCCEEDED(hr))
            hr = IPropertyStore_SetValue(properties, &PKEY_AppUserModel_ID, &value);
        value.vt = VT_CLSID;
        value.puuid = &activator_clsid;
        if (SUCCEEDED(hr))
            hr =
                IPropertyStore_SetValue(properties, &PKEY_AppUserModel_ToastActivatorCLSID, &value);
        if (SUCCEEDED(hr))
            hr = IPropertyStore_Commit(properties);
        if (SUCCEEDED(hr))
            hr = IPersistFile_Save(persist, shortcut_path, TRUE);
    }
    if (persist)
        IPersistFile_Release(persist);
    if (properties)
        IPropertyStore_Release(properties);
    if (link)
        IShellLinkW_Release(link);
    return hr;
}
static HRESULT initialize_ro(void) {
    if (ro_initialized)
        return S_OK;
    HRESULT hr = RoInitialize(RO_INIT_MULTITHREADED);
    if (SUCCEEDED(hr))
        ro_owned = true;
    if (SUCCEEDED(hr) || hr == RPC_E_CHANGED_MODE)
        ro_initialized = true;
    return hr == RPC_E_CHANGED_MODE ? S_OK : hr;
}
static HRESULT open_history(void) {
    if (history)
        return S_OK;
    HSTRING name = NULL;
    IToastNotificationManagerStatics2 *manager = NULL;
    HRESULT hr = WindowsCreateString(
        L"Windows.UI.Notifications.ToastNotificationManager",
        (UINT32)wcslen(L"Windows.UI.Notifications.ToastNotificationManager"), &name);
    if (SUCCEEDED(hr))
        hr =
            RoGetActivationFactory(name, &IID_IToastNotificationManagerStatics2, (void **)&manager);
    if (SUCCEEDED(hr))
        hr = IToastNotificationManagerStatics2_get_History(manager, &history);
    if (manager)
        IToastNotificationManagerStatics2_Release(manager);
    WindowsDeleteString(name);
    return hr;
}
static HRESULT remove_history(const wchar_t *token) {
    HSTRING tag = NULL, group = NULL, id = NULL;
    HRESULT hr = open_history();
    if (SUCCEEDED(hr))
        hr = WindowsCreateString(token, 32, &tag);
    if (SUCCEEDED(hr))
        hr = WindowsCreateString(L"Minyar", 6, &group);
    if (SUCCEEDED(hr))
        hr = WindowsCreateString(app_id, (UINT32)wcslen(app_id), &id);
    if (SUCCEEDED(hr))
        hr = IToastNotificationHistory_RemoveGroupedTagWithId(history, tag, group, id);
    WindowsDeleteString(tag);
    WindowsDeleteString(group);
    WindowsDeleteString(id);
    return hr;
}
static bool valid_token(const wchar_t *token) {
    if (wcslen(token) != 32)
        return false;
    for (unsigned i = 0; i < 32; i++)
        if (!((token[i] >= '0' && token[i] <= '9') || (token[i] >= 'a' && token[i] <= 'f')))
            return false;
    return true;
}
static bool pending_fresh(const wchar_t *path) {
    HKEY key = NULL;
    ULONGLONG created = 0;
    DWORD type = 0, size = sizeof(created);
    LSTATUS status = RegOpenKeyExW(HKEY_CURRENT_USER, path, 0, KEY_QUERY_VALUE, &key);
    if (!status)
        status = RegQueryValueExW(key, L"Created", NULL, &type, (BYTE *)&created, &size);
    if (key)
        RegCloseKey(key);
    FILETIME time;
    GetSystemTimeAsFileTime(&time);
    ULONGLONG now = ((ULONGLONG)time.dwHighDateTime << 32) | time.dwLowDateTime;
    return !status && type == REG_QWORD && size == sizeof(created) && created <= now &&
           now - created <= NOTICE_MAX_AGE;
}
// Bound persisted registrations across process lifetimes, not just native handles.
// Only this app's owned subtree and scoped Action Center history are touched.
static HRESULT pending_guard(HANDLE *out) {
    wchar_t name[96];
    swprintf(name, 96, L"Local\\Minyar.Notifications.%ls", clsid_text);
    *out = CreateMutexW(NULL, FALSE, name);
    if (!*out)
        return HRESULT_FROM_WIN32(GetLastError());
    DWORD waited = WaitForSingleObject(*out, 1000);
    if (waited == WAIT_OBJECT_0 || waited == WAIT_ABANDONED)
        return S_OK;
    HRESULT hr = HRESULT_FROM_WIN32(waited == WAIT_TIMEOUT ? ERROR_TIMEOUT : GetLastError());
    CloseHandle(*out);
    *out = NULL;
    return hr;
}
static void pending_unguard(HANDLE guard) {
    ReleaseMutex(guard);
    CloseHandle(guard);
}
static HRESULT prune_pending_unlocked(unsigned *remaining) {
    wchar_t root[320];
    swprintf(root, 320, L"%ls\\Pending", registry_path);
    HKEY key = NULL;
    LSTATUS status = RegOpenKeyExW(HKEY_CURRENT_USER, root, 0, KEY_READ | KEY_WRITE, &key);
    *remaining = 0;
    if (status == ERROR_FILE_NOT_FOUND)
        return S_OK;
    if (status)
        return HRESULT_FROM_WIN32(status);
    DWORD index = 0;
    HRESULT hr = S_OK;
    for (unsigned visited = 0; visited <= NOTICE_LIMIT * 4; visited++) {
        wchar_t token[256], path[600];
        DWORD length = 256;
        status = RegEnumKeyExW(key, index, token, &length, NULL, NULL, NULL, NULL);
        if (status == ERROR_NO_MORE_ITEMS)
            break;
        if (status || visited == NOTICE_LIMIT * 4) {
            hr = HRESULT_FROM_WIN32(status ? status : ERROR_INVALID_DATA);
            break;
        }
        swprintf(path, 600, L"%ls\\%ls", root, token);
        if (valid_token(token) && pending_fresh(path)) {
            (*remaining)++;
            index++;
        } else {
            status = RegDeleteTreeW(key, token);
            if (status && status != ERROR_FILE_NOT_FOUND) {
                hr = HRESULT_FROM_WIN32(status);
                break;
            }
            if (valid_token(token)) {
                hr = remove_history(token);
                if (FAILED(hr))
                    break;
            }
        }
    }
    RegCloseKey(key);
    return hr;
}
static HRESULT prune_pending(unsigned *remaining) {
    HANDLE guard = NULL;
    HRESULT hr = pending_guard(&guard);
    if (SUCCEEDED(hr)) {
        hr = prune_pending_unlocked(remaining);
        pending_unguard(guard);
    }
    return hr;
}
// A callback must match both app identity and the persisted notification allowlist.
// Consumption and queue insertion share a lock, so duplicates and close races cannot dispatch.
static HRESULT activate_notice(const wchar_t *app, const wchar_t *argument, ULONG inputs) {
    if (!app || !argument || inputs || wcsnlen(app, 129) >= 129 || wcsnlen(argument, 99) >= 99)
        return E_INVALIDARG;
    if (wcslen(argument) < 34 || argument[32] != ':')
        return E_INVALIDARG;
    wchar_t token[33], action[65];
    memcpy(token, argument, 32 * sizeof(wchar_t));
    token[32] = 0;
    wcscpy(action, argument + 33);
    if (!valid_token(token))
        return E_INVALIDARG;
    if (!identifier(action, 64))
        return E_INVALIDARG;
    AcquireSRWLockExclusive(&notify_lock);
    HRESULT hr = initialized && !wcscmp(app, app_id) ? S_OK : E_ACCESSDENIED;
    wchar_t path[320], allowed[512];
    swprintf(path, 320, L"%ls\\Pending\\%ls", registry_path, token);
    if (SUCCEEDED(hr)) {
        LSTATUS status = read_string(HKEY_CURRENT_USER, path, L"Actions", allowed, 512);
        if (status)
            hr = E_ACCESSDENIED;
        else {
            if (!pending_fresh(path))
                hr = E_ACCESSDENIED;
            bool found = false;
            wchar_t *part = allowed;
            while (*part) {
                wchar_t *end = wcschr(part, L'\n');
                if (end)
                    *end = 0;
                if (!wcscmp(part, action))
                    found = true;
                if (!end)
                    break;
                part = end + 1;
            }
            if (!found)
                hr = E_ACCESSDENIED;
        }
    }
    if (SUCCEEDED(hr) && action_count >= ACTION_QUEUE_LIMIT)
        hr = E_OUTOFMEMORY;
    ActionEvent *event = NULL;
    if (SUCCEEDED(hr)) {
        event = calloc(1, sizeof(*event));
        if (!event)
            hr = E_OUTOFMEMORY;
    }
    if (SUCCEEDED(hr)) {
        LSTATUS status = RegDeleteTreeW(HKEY_CURRENT_USER, path);
        if (status)
            hr = HRESULT_FROM_WIN32(status);
        else {
            wcscpy(event->token, token);
            wcscpy(event->action, action);
            if (actions_tail)
                actions_tail->next = event;
            else
                actions_head = event;
            actions_tail = event;
            action_count++;
            PostThreadMessageW(notify_owner, WM_APP + 0x249, 0, 0);
            event = NULL;
        }
    }
    free(event);
    ReleaseSRWLockExclusive(&notify_lock);
    return hr;
}
typedef struct Activator {
    INotificationActivationCallback iface;
    volatile LONG refs;
} Activator;
static HRESULT STDMETHODCALLTYPE activation_query(INotificationActivationCallback *self, REFIID iid,
                                                  void **out) {
    if (!out)
        return E_POINTER;
    *out = NULL;
    if (IsEqualIID(iid, &IID_IUnknown) || IsEqualIID(iid, &IID_INotificationActivationCallback)) {
        *out = self;
        self->lpVtbl->AddRef(self);
        return S_OK;
    }
    if (IsEqualIID(iid, &IID_IMarshal)) {
        AcquireSRWLockShared(&notify_lock);
        IUnknown *held = marshaller;
        if (held)
            IUnknown_AddRef(held);
        ReleaseSRWLockShared(&notify_lock);
        if (held) {
            HRESULT hr = IUnknown_QueryInterface(held, iid, out);
            IUnknown_Release(held);
            return hr;
        }
    }
    return E_NOINTERFACE;
}
static ULONG STDMETHODCALLTYPE activation_ref(INotificationActivationCallback *self) {
    return (ULONG)InterlockedIncrement(&((Activator *)self)->refs);
}
static ULONG STDMETHODCALLTYPE activation_release(INotificationActivationCallback *self) {
    return (ULONG)InterlockedDecrement(&((Activator *)self)->refs);
}
static HRESULT STDMETHODCALLTYPE activation_call(INotificationActivationCallback *self, LPCWSTR app,
                                                 LPCWSTR args,
                                                 const NOTIFICATION_USER_INPUT_DATA *data,
                                                 ULONG count) {
    (void)self;
    (void)data;
    return activate_notice(app, args, count);
}
static INotificationActivationCallbackVtbl activation_vtable = {
    activation_query, activation_ref, activation_release, activation_call};
static Activator activator = {{&activation_vtable}, 1};
typedef struct Factory {
    IClassFactory iface;
    volatile LONG refs;
} Factory;
static HRESULT STDMETHODCALLTYPE factory_query(IClassFactory *self, REFIID iid, void **out) {
    if (!out)
        return E_POINTER;
    *out = NULL;
    if (IsEqualIID(iid, &IID_IUnknown) || IsEqualIID(iid, &IID_IClassFactory)) {
        *out = self;
        self->lpVtbl->AddRef(self);
        return S_OK;
    }
    return E_NOINTERFACE;
}
static ULONG STDMETHODCALLTYPE factory_ref(IClassFactory *self) {
    return (ULONG)InterlockedIncrement(&((Factory *)self)->refs);
}
static ULONG STDMETHODCALLTYPE factory_release(IClassFactory *self) {
    return (ULONG)InterlockedDecrement(&((Factory *)self)->refs);
}
static HRESULT STDMETHODCALLTYPE factory_create(IClassFactory *self, IUnknown *outer, REFIID iid,
                                                void **out) {
    (void)self;
    if (outer)
        return CLASS_E_NOAGGREGATION;
    return activation_query(&activator.iface, iid, out);
}
static HRESULT STDMETHODCALLTYPE factory_lock(IClassFactory *self, BOOL lock) {
    (void)self;
    (void)lock;
    return S_OK;
}
static IClassFactoryVtbl factory_vtable = {factory_query, factory_ref, factory_release,
                                           factory_create, factory_lock};
static Factory factory = {{&factory_vtable}, 1};
struct FailedHandler {
    __FITypedEventHandler_2_Windows__CUI__CNotifications__CToastNotification_Windows__CUI__CNotifications__CToastFailedEventArgs
        iface;
    volatile LONG refs, error;
};
typedef __FITypedEventHandler_2_Windows__CUI__CNotifications__CToastNotification_Windows__CUI__CNotifications__CToastFailedEventArgs
    FailedInterface;
static HRESULT STDMETHODCALLTYPE failed_query(FailedInterface *self, REFIID iid, void **out) {
    if (!out)
        return E_POINTER;
    *out = NULL;
    if (IsEqualIID(iid, &IID_IUnknown) || IsEqualIID(iid, &IID_IAgileObject) ||
        IsEqualIID(
            iid,
            &IID___FITypedEventHandler_2_Windows__CUI__CNotifications__CToastNotification_Windows__CUI__CNotifications__CToastFailedEventArgs)) {
        *out = self;
        self->lpVtbl->AddRef(self);
        return S_OK;
    }
    return E_NOINTERFACE;
}
static ULONG STDMETHODCALLTYPE failed_ref(FailedInterface *self) {
    return (ULONG)InterlockedIncrement(&((FailedHandler *)self)->refs);
}
static ULONG STDMETHODCALLTYPE failed_release(FailedInterface *self) {
    LONG refs = InterlockedDecrement(&((FailedHandler *)self)->refs);
    if (!refs)
        free(self);
    return (ULONG)refs;
}
static HRESULT STDMETHODCALLTYPE failed_call(FailedInterface *self, IToastNotification *sender,
                                             IToastFailedEventArgs *args) {
    (void)sender;
    HRESULT hr = E_FAIL;
    IToastFailedEventArgs_get_ErrorCode(args, &hr);
    if (SUCCEEDED(hr))
        hr = E_FAIL;
    InterlockedExchange(&((FailedHandler *)self)->error, hr);
    return S_OK;
}
static __FITypedEventHandler_2_Windows__CUI__CNotifications__CToastNotification_Windows__CUI__CNotifications__CToastFailedEventArgsVtbl
    failed_vtable = {failed_query, failed_ref, failed_release, failed_call};
static void release_notice(Notice *notice) {
    if (notice->toast && notice->failed)
        IToastNotification_remove_Failed(notice->toast, notice->failed_token);
    if (notice->failed)
        failed_release(&notice->failed->iface);
    if (notice->toast)
        IToastNotification_Release(notice->toast);
    free(notice);
}
MinyarBytes *minyar_winnotify_registerRaw(const MinyarText *app, const MinyarText *display) {
    notify_thread();
    wchar_t *id = notify_wide(app, 129), *name = notify_wide(display, 129);
    if (!id || !name || !*name || !identifier(id, 128)) {
        free(id);
        free(name);
        return notify_result(6, E_INVALIDARG, 0);
    }
    if (initialized) {
        free(id);
        free(name);
        return notify_result(6, E_UNEXPECTED, 0);
    }
    HRESULT hr = initialize_ro();
    if (SUCCEEDED(hr))
        hr = prepare_identity(id);
    if (SUCCEEDED(hr))
        hr = owned_value(registry_path, L"Owner", executable, false);
    if (SUCCEEDED(hr))
        hr = owned_value(server_path, NULL, server_command, false);
    if (SUCCEEDED(hr))
        hr = owned_value(app_registration_path, L"CustomActivator", clsid_text, false);
    if (SUCCEEDED(hr) && GetFileAttributesW(shortcut_path) != INVALID_FILE_ATTRIBUTES)
        hr = shortcut(false);
    if (SUCCEEDED(hr))
        hr = write_string(registry_path, L"Owner", executable);
    if (SUCCEEDED(hr))
        hr = write_string(registry_path, L"DisplayName", name);
    if (SUCCEEDED(hr))
        hr = write_string(server_path, NULL, server_command);
    if (SUCCEEDED(hr))
        hr = write_string(app_registration_path, L"CustomActivator", clsid_text);
    if (SUCCEEDED(hr))
        hr = write_string(app_registration_path, L"DisplayName", name);
    if (SUCCEEDED(hr))
        hr = shortcut(true);
    free(id);
    free(name);
    return notify_hresult(hr, 1);
}
MinyarBytes *minyar_winnotify_initializeRaw(const MinyarText *app) {
    notify_thread();
    wchar_t *id = notify_wide(app, 129);
    if (!id || !identifier(id, 128)) {
        free(id);
        return notify_result(6, E_INVALIDARG, 0);
    }
    if (initialized) {
        HRESULT hr = !wcscmp(id, app_id) ? S_OK : E_INVALIDARG;
        free(id);
        return notify_hresult(hr, 1);
    }
    HRESULT hr = initialize_ro();
    if (SUCCEEDED(hr))
        hr = prepare_identity(id);
    free(id);
    if (SUCCEEDED(hr))
        hr = owned_value(registry_path, L"Owner", executable, true);
    if (SUCCEEDED(hr))
        hr = owned_value(server_path, NULL, server_command, true);
    if (SUCCEEDED(hr))
        hr = owned_value(app_registration_path, L"CustomActivator", clsid_text, true);
    if (hr == HRESULT_FROM_WIN32(ERROR_NOT_FOUND))
        return notify_result(9, hr, 0);
    if (SUCCEEDED(hr))
        hr = shortcut(false);
    if (SUCCEEDED(hr))
        hr = SetCurrentProcessExplicitAppUserModelID(app_id);
    if (SUCCEEDED(hr)) {
        MSG message;
        PeekMessageW(&message, NULL, WM_USER, WM_USER, PM_NOREMOVE);
    }
    if (SUCCEEDED(hr))
        hr = CoCreateFreeThreadedMarshaler((IUnknown *)&activator.iface, &marshaller);
    if (SUCCEEDED(hr))
        hr = CoRegisterClassObject(&activator_clsid, (IUnknown *)&factory.iface,
                                   CLSCTX_LOCAL_SERVER, REGCLS_MULTIPLEUSE, &class_cookie);
    HSTRING class_name = NULL, id_string = NULL;
    IToastNotificationManagerStatics *manager = NULL;
    if (SUCCEEDED(hr))
        hr = WindowsCreateString(
            L"Windows.UI.Notifications.ToastNotificationManager",
            (UINT32)wcslen(L"Windows.UI.Notifications.ToastNotificationManager"), &class_name);
    if (SUCCEEDED(hr))
        hr = RoGetActivationFactory(class_name, &IID_IToastNotificationManagerStatics,
                                    (void **)&manager);
    if (SUCCEEDED(hr))
        hr = WindowsCreateString(app_id, (UINT32)wcslen(app_id), &id_string);
    if (SUCCEEDED(hr))
        hr = IToastNotificationManagerStatics_CreateToastNotifierWithId(manager, id_string,
                                                                        &notifier);
    if (SUCCEEDED(hr))
        hr = open_history();
    if (SUCCEEDED(hr)) {
        unsigned pending;
        hr = prune_pending(&pending);
    }
    if (manager)
        IToastNotificationManagerStatics_Release(manager);
    WindowsDeleteString(class_name);
    WindowsDeleteString(id_string);
    AcquireSRWLockExclusive(&notify_lock);
    initialized = SUCCEEDED(hr);
    ReleaseSRWLockExclusive(&notify_lock);
    if (FAILED(hr)) {
        if (class_cookie) {
            CoRevokeClassObject(class_cookie);
            class_cookie = 0;
        }
        AcquireSRWLockExclusive(&notify_lock);
        IUnknown *old = marshaller;
        marshaller = NULL;
        ReleaseSRWLockExclusive(&notify_lock);
        if (old)
            IUnknown_Release(old);
        if (notifier) {
            IToastNotifier_Release(notifier);
            notifier = NULL;
        }
        if (history) {
            IToastNotificationHistory_Release(history);
            history = NULL;
        }
    }
    return notify_hresult(hr, 1);
}
typedef struct ActionDefinition {
    wchar_t id[65];
    wchar_t *label;
} ActionDefinition;
static bool parse_actions(const MinyarBytes *raw, ActionDefinition definitions[5],
                          unsigned *count) {
    *count = 0;
    if (raw->byte_length == 0)
        return true;
    if (raw->byte_length < 1 || raw->bytes[0] > ACTION_LIMIT)
        return false;
    *count = raw->bytes[0];
    size_t at = 1, total = (size_t)raw->byte_length;
    for (unsigned i = 0; i < *count; i++) {
        if (at + 2 > total)
            return false;
        unsigned length = raw->bytes[at] | ((unsigned)raw->bytes[at + 1] << 8);
        at += 2;
        if (!length || length > 64 || at + length + 2 > total)
            return false;
        for (unsigned j = 0; j < length; j++) {
            unsigned char c = raw->bytes[at + j];
            if (!c || c > 127)
                return false;
            definitions[i].id[j] = c;
        }
        definitions[i].id[length] = 0;
        at += length;
        if (!identifier(definitions[i].id, 64) || !wcscmp(definitions[i].id, L"default"))
            return false;
        for (unsigned j = 0; j < i; j++)
            if (!wcscmp(definitions[i].id, definitions[j].id))
                return false;
        length = raw->bytes[at] | ((unsigned)raw->bytes[at + 1] << 8);
        at += 2;
        if (!length || length > 512 || at + length > total)
            return false;
        MinyarText text = {0};
        text.bytes = raw->bytes + at;
        text.byte_length = length;
        definitions[i].label = notify_wide(&text, 129);
        if (!definitions[i].label || !*definitions[i].label)
            return false;
        at += length;
    }
    return at == total;
}
static bool xml_append(wchar_t *xml, size_t *used, const wchar_t *text, bool escape) {
    for (size_t i = 0; text[i]; i++) {
        const wchar_t *entity = NULL;
        if (escape)
            switch (text[i]) {
            case '&':
                entity = L"&amp;";
                break;
            case '<':
                entity = L"&lt;";
                break;
            case '>':
                entity = L"&gt;";
                break;
            case '"':
                entity = L"&quot;";
                break;
            case '\'':
                entity = L"&apos;";
                break;
            }
        size_t n = entity ? wcslen(entity) : 1;
        if (*used + n >= 65536)
            return false;
        if (entity)
            memcpy(xml + *used, entity, n * sizeof(wchar_t));
        else
            xml[*used] = text[i];
        *used += n;
        xml[*used] = 0;
    }
    return true;
}
static HRESULT create_notice_xml(const wchar_t *title, const wchar_t *body, const wchar_t *token,
                                 ActionDefinition definitions[5], unsigned count,
                                 IXmlDocument **document) {
    wchar_t *xml = calloc(65536, sizeof(wchar_t));
    if (!xml)
        return E_OUTOFMEMORY;
    size_t used = 0;
    bool ok = xml_append(xml, &used, L"<toast launch=\"", false) &&
              xml_append(xml, &used, token, false) &&
              xml_append(xml, &used,
                         L":default\"><visual><binding template=\"ToastGeneric\"><text>", false) &&
              xml_append(xml, &used, title, true) &&
              xml_append(xml, &used, L"</text><text>", false) &&
              xml_append(xml, &used, body, true) &&
              xml_append(xml, &used, L"</text></binding></visual><actions>", false);
    for (unsigned i = 0; i < count && ok; i++) {
        ok = xml_append(xml, &used, L"<action activationType=\"background\" content=\"", false) &&
             xml_append(xml, &used, definitions[i].label, true) &&
             xml_append(xml, &used, L"\" arguments=\"", false) &&
             xml_append(xml, &used, token, false) && xml_append(xml, &used, L":", false) &&
             xml_append(xml, &used, definitions[i].id, false) &&
             xml_append(xml, &used, L"\"/>", false);
    }
    ok = ok && xml_append(xml, &used, L"</actions></toast>", false);
    HSTRING class_name = NULL, xml_string = NULL;
    IInspectable *instance = NULL;
    IXmlDocumentIO *io = NULL;
    HRESULT hr =
        ok ? WindowsCreateString(L"Windows.Data.Xml.Dom.XmlDocument",
                                 (UINT32)wcslen(L"Windows.Data.Xml.Dom.XmlDocument"), &class_name)
           : E_INVALIDARG;
    if (SUCCEEDED(hr))
        hr = RoActivateInstance(class_name, &instance);
    if (SUCCEEDED(hr))
        hr = IInspectable_QueryInterface(instance, &IID_IXmlDocument, (void **)document);
    if (SUCCEEDED(hr))
        hr = IInspectable_QueryInterface(instance, &IID_IXmlDocumentIO, (void **)&io);
    if (SUCCEEDED(hr))
        hr = WindowsCreateString(xml, (UINT32)used, &xml_string);
    if (SUCCEEDED(hr))
        hr = IXmlDocumentIO_LoadXml(io, xml_string);
    if (io)
        IXmlDocumentIO_Release(io);
    if (instance)
        IInspectable_Release(instance);
    WindowsDeleteString(xml_string);
    WindowsDeleteString(class_name);
    free(xml);
    return hr;
}
static HRESULT persist_notice(Notice *notice, ActionDefinition definitions[5], unsigned count) {
    HANDLE guard = NULL;
    HRESULT hr = pending_guard(&guard);
    if (FAILED(hr))
        return hr;
    unsigned pending;
    hr = prune_pending_unlocked(&pending);
    if (FAILED(hr) || pending >= NOTICE_LIMIT) {
        pending_unguard(guard);
        if (SUCCEEDED(hr))
            hr = E_OUTOFMEMORY;
        return hr;
    }
    wchar_t allowed[512] = L"default", path[320];
    for (unsigned i = 0; i < count; i++) {
        wcscat(allowed, L"\n");
        wcscat(allowed, definitions[i].id);
    }
    swprintf(path, 320, L"%ls\\Pending\\%ls", registry_path, notice->token);
    HKEY key = NULL;
    DWORD disposition = 0;
    LSTATUS status = RegCreateKeyExW(HKEY_CURRENT_USER, path, 0, NULL, 0, KEY_SET_VALUE, NULL, &key,
                                     &disposition);
    if (!status && disposition != REG_CREATED_NEW_KEY)
        status = ERROR_ALREADY_EXISTS;
    if (!status)
        status = RegSetValueExW(key, L"Actions", 0, REG_SZ, (const BYTE *)allowed,
                                (DWORD)((wcslen(allowed) + 1) * sizeof(wchar_t)));
    FILETIME time;
    GetSystemTimeAsFileTime(&time);
    if (!status)
        status = RegSetValueExW(key, L"Created", 0, REG_QWORD, (const BYTE *)&time, sizeof(time));
    if (key)
        RegCloseKey(key);
    if (status && disposition == REG_CREATED_NEW_KEY)
        RegDeleteTreeW(HKEY_CURRENT_USER, path);
    hr = HRESULT_FROM_WIN32(status);
    pending_unguard(guard);
    return hr;
}
static HRESULT delete_pending(const Notice *notice) {
    wchar_t path[320];
    swprintf(path, 320, L"%ls\\Pending\\%ls", registry_path, notice->token);
    LSTATUS status = RegDeleteTreeW(HKEY_CURRENT_USER, path);
    return status == ERROR_FILE_NOT_FOUND ? S_OK : HRESULT_FROM_WIN32(status);
}
static Notice *find_notice(long long id) {
    for (Notice *notice = notices; notice; notice = notice->next)
        if (notice->id == id)
            return notice;
    return NULL;
}
MinyarBytes *minyar_winnotify_showRaw(const MinyarText *title, const MinyarText *body,
                                      const MinyarBytes *raw_actions) {
    notify_thread();
    wchar_t *heading = notify_wide(title, 1025), *text = notify_wide(body, 8193);
    ActionDefinition definitions[5] = {0};
    unsigned count = 0;
    bool valid = heading && text && parse_actions(raw_actions, definitions, &count);
    HRESULT hr = valid ? S_OK : E_INVALIDARG;
    uint32_t error = valid ? 0 : 6;
    if (valid && !initialized) {
        hr = E_UNEXPECTED;
        error = 9;
    }
    if (valid && initialized && (notice_count >= NOTICE_LIMIT || next_id == INT64_MAX)) {
        hr = E_OUTOFMEMORY;
        error = 7;
    }
    Notice *notice = NULL;
    IXmlDocument *document = NULL;
    IToastNotificationFactory *toast_factory = NULL;
    HSTRING class_name = NULL;
    if (SUCCEEDED(hr)) {
        notice = calloc(1, sizeof(*notice));
        if (!notice)
            hr = E_OUTOFMEMORY;
    }
    if (SUCCEEDED(hr)) {
        unsigned char random[16];
        NTSTATUS status = BCryptGenRandom(NULL, random, 16, BCRYPT_USE_SYSTEM_PREFERRED_RNG);
        if (status < 0)
            hr = E_FAIL;
        else
            for (unsigned i = 0; i < 16; i++)
                swprintf(notice->token + 2 * i, 3, L"%02x", random[i]);
    }
    if (SUCCEEDED(hr))
        hr = create_notice_xml(heading, text, notice->token, definitions, count, &document);
    if (SUCCEEDED(hr))
        hr = WindowsCreateString(L"Windows.UI.Notifications.ToastNotification",
                                 (UINT32)wcslen(L"Windows.UI.Notifications.ToastNotification"),
                                 &class_name);
    if (SUCCEEDED(hr))
        hr = RoGetActivationFactory(class_name, &IID_IToastNotificationFactory,
                                    (void **)&toast_factory);
    if (SUCCEEDED(hr))
        hr = IToastNotificationFactory_CreateToastNotification(toast_factory, document,
                                                               &notice->toast);
    if (SUCCEEDED(hr)) {
        IToastNotification2 *tagged = NULL;
        HSTRING tag = NULL, group = NULL;
        hr = IToastNotification_QueryInterface(notice->toast, &IID_IToastNotification2,
                                               (void **)&tagged);
        if (SUCCEEDED(hr))
            hr = WindowsCreateString(notice->token, 32, &tag);
        if (SUCCEEDED(hr))
            hr = WindowsCreateString(L"Minyar", 6, &group);
        if (SUCCEEDED(hr))
            hr = IToastNotification2_put_Tag(tagged, tag);
        if (SUCCEEDED(hr))
            hr = IToastNotification2_put_Group(tagged, group);
        if (tagged)
            IToastNotification2_Release(tagged);
        WindowsDeleteString(tag);
        WindowsDeleteString(group);
    }
    if (SUCCEEDED(hr)) {
        notice->failed = calloc(1, sizeof(*notice->failed));
        if (!notice->failed)
            hr = E_OUTOFMEMORY;
        else {
            notice->failed->iface.lpVtbl = &failed_vtable;
            notice->failed->refs = 1;
            hr = IToastNotification_add_Failed(notice->toast, &notice->failed->iface,
                                               &notice->failed_token);
        }
    }
    enum __x_ABI_CWindows_CUI_CNotifications_CNotificationSetting setting;
    if (SUCCEEDED(hr))
        hr = IToastNotifier_get_Setting(notifier, &setting);
    if (SUCCEEDED(hr) && setting != NotificationSetting_Enabled)
        hr = E_ACCESSDENIED;
    if (SUCCEEDED(hr))
        hr = persist_notice(notice, definitions, count);
    if (SUCCEEDED(hr))
        hr = IToastNotifier_Show(notifier, notice->toast);
    long long id = 0;
    if (SUCCEEDED(hr)) {
        id = notice->id = next_id++;
        notice->next = notices;
        notices = notice;
        notice_count++;
        notice = NULL;
    }
    if (notice) {
        delete_pending(notice);
        release_notice(notice);
    }
    if (toast_factory)
        IToastNotificationFactory_Release(toast_factory);
    if (document)
        IXmlDocument_Release(document);
    WindowsDeleteString(class_name);
    free(heading);
    free(text);
    for (unsigned i = 0; i < ACTION_LIMIT; i++)
        free(definitions[i].label);
    return error ? notify_result(error, hr, 0) : notify_hresult(hr, id);
}
MinyarBytes *minyar_winnotify_statusRaw(long long id) {
    notify_thread();
    Notice *notice = find_notice(id);
    if (!notice)
        return notify_result(4, HRESULT_FROM_WIN32(ERROR_INVALID_HANDLE), 0);
    HRESULT hr =
        notice->failed ? (HRESULT)InterlockedCompareExchange(&notice->failed->error, 0, 0) : S_OK;
    return notify_hresult(hr, 1);
}
// The caller holds notify_lock, matching activation's consume-and-enqueue lock.
static void discard_actions(const wchar_t *token) {
    ActionEvent **event = &actions_head;
    actions_tail = NULL;
    while (*event) {
        if (!wcscmp((*event)->token, token)) {
            ActionEvent *old = *event;
            *event = old->next;
            free(old);
            action_count--;
        } else {
            actions_tail = *event;
            event = &(*event)->next;
        }
    }
}
MinyarBytes *minyar_winnotify_closeRaw(long long id) {
    notify_thread();
    Notice **link = &notices;
    while (*link && (*link)->id != id)
        link = &(*link)->next;
    if (!*link)
        return notify_result(4, HRESULT_FROM_WIN32(ERROR_INVALID_HANDLE), 0);
    Notice *notice = *link;
    AcquireSRWLockExclusive(&notify_lock);
    HRESULT hr = delete_pending(notice);
    if (SUCCEEDED(hr))
        discard_actions(notice->token);
    ReleaseSRWLockExclusive(&notify_lock);
    if (FAILED(hr))
        return notify_hresult(hr, 0);
    *link = notice->next;
    notice_count--;
    hr = notice->toast ? IToastNotifier_Hide(notifier, notice->toast) : S_OK;
    HRESULT removed = remove_history(notice->token);
    if (SUCCEEDED(hr))
        hr = removed;
    release_notice(notice);
    return notify_hresult(hr, 0);
}
MinyarBytes *minyar_winnotify_cancelTokenRaw(const MinyarText *raw_token) {
    notify_thread();
    wchar_t *token = notify_wide(raw_token, 33);
    if (!token || !valid_token(token)) {
        free(token);
        return notify_result(6, E_INVALIDARG, 0);
    }
    if (!initialized) {
        free(token);
        return notify_result(9, E_UNEXPECTED, 0);
    }
    for (Notice *notice = notices; notice; notice = notice->next)
        if (!wcscmp(notice->token, token)) {
            free(token);
            return minyar_winnotify_closeRaw(notice->id);
        }
    Notice persisted = {0};
    wcscpy(persisted.token, token);
    AcquireSRWLockExclusive(&notify_lock);
    HRESULT hr = delete_pending(&persisted);
    if (SUCCEEDED(hr))
        discard_actions(token);
    ReleaseSRWLockExclusive(&notify_lock);
    if (SUCCEEDED(hr))
        hr = remove_history(token);
    free(token);
    return notify_hresult(hr, 0);
}
MinyarBytes *minyar_winnotify_tokenRaw(long long id) {
    notify_thread();
    Notice *notice = find_notice(id);
    if (!notice)
        return notify_result(4, HRESULT_FROM_WIN32(ERROR_INVALID_HANDLE), 0);
    MinyarBytes *b = minyar_bytes_new(16 + 32);
    uint32_t length = 32;
    memset((void *)b->bytes, 0, 16);
    memcpy((unsigned char *)b->bytes + 8, &length, 4);
    for (unsigned i = 0; i < 32; i++)
        ((unsigned char *)b->bytes)[16 + i] = (unsigned char)notice->token[i];
    return b;
}
MinyarBytes *minyar_winnotify_nextActionRaw(void) {
    notify_thread();
    if (!initialized)
        return notify_result(9, E_UNEXPECTED, 0);
    AcquireSRWLockExclusive(&notify_lock);
    ActionEvent *event = actions_head;
    if (event) {
        actions_head = event->next;
        if (!actions_head)
            actions_tail = NULL;
        action_count--;
    }
    ReleaseSRWLockExclusive(&notify_lock);
    if (!event)
        return notify_result(1, HRESULT_FROM_WIN32(ERROR_NO_MORE_ITEMS), 0);
    size_t length = 32 + 1 + wcslen(event->action);
    MinyarBytes *b = minyar_bytes_new((long long)length + 16);
    memset((void *)b->bytes, 0, 16);
    uint32_t size = (uint32_t)length;
    memcpy((unsigned char *)b->bytes + 8, &size, 4);
    for (unsigned i = 0; i < 32; i++)
        ((unsigned char *)b->bytes)[16 + i] = (unsigned char)event->token[i];
    ((unsigned char *)b->bytes)[48] = ':';
    for (unsigned i = 0; event->action[i]; i++)
        ((unsigned char *)b->bytes)[49 + i] = (unsigned char)event->action[i];
    free(event);
    return b;
}
static void stop_notifications(bool cancel) {
    AcquireSRWLockExclusive(&notify_lock);
    initialized = false;
    ReleaseSRWLockExclusive(&notify_lock);
    if (class_cookie) {
        CoRevokeClassObject(class_cookie);
        class_cookie = 0;
    }
    CoDisconnectObject((IUnknown *)&activator.iface, 0);
    while (notices) {
        Notice *notice = notices;
        notices = notice->next;
        if (cancel) {
            delete_pending(notice);
            if (notice->toast)
                IToastNotifier_Hide(notifier, notice->toast);
        }
        release_notice(notice);
    }
    notice_count = 0;
    AcquireSRWLockExclusive(&notify_lock);
    while (actions_head) {
        ActionEvent *event = actions_head;
        actions_head = event->next;
        free(event);
    }
    actions_tail = NULL;
    action_count = 0;
    IUnknown *old = marshaller;
    marshaller = NULL;
    ReleaseSRWLockExclusive(&notify_lock);
    if (notifier) {
        IToastNotifier_Release(notifier);
        notifier = NULL;
    }
    if (history) {
        IToastNotificationHistory_Release(history);
        history = NULL;
    }
    if (old)
        IUnknown_Release(old);
    if (ro_owned) {
        RoUninitialize();
        ro_owned = false;
    }
    ro_initialized = false;
}
MinyarBytes *minyar_winnotify_stopRaw(void) {
    notify_thread();
    stop_notifications(false);
    return notify_result(0, S_OK, 0);
}
MinyarBytes *minyar_winnotify_unregisterRaw(void) {
    notify_thread();
    if (!app_id[0])
        return notify_result(9, E_UNEXPECTED, 0);
    HRESULT hr = initialize_ro();
    if (SUCCEEDED(hr))
        hr = owned_value(registry_path, L"Owner", executable, true);
    if (SUCCEEDED(hr))
        hr = owned_value(server_path, NULL, server_command, true);
    if (SUCCEEDED(hr))
        hr = owned_value(app_registration_path, L"CustomActivator", clsid_text, true);
    bool has_shortcut = GetFileAttributesW(shortcut_path) != INVALID_FILE_ATTRIBUTES;
    if (SUCCEEDED(hr) && has_shortcut)
        hr = shortcut(false);
    if (FAILED(hr))
        return notify_hresult(hr, 0);
    hr = open_history();
    HSTRING id = NULL;
    if (SUCCEEDED(hr))
        hr = WindowsCreateString(app_id, (UINT32)wcslen(app_id), &id);
    if (SUCCEEDED(hr))
        hr = IToastNotificationHistory_ClearWithId(history, id);
    WindowsDeleteString(id);
    if (FAILED(hr))
        return notify_hresult(hr, 0);
    stop_notifications(true);
    if (has_shortcut && !DeleteFileW(shortcut_path))
        hr = HRESULT_FROM_WIN32(GetLastError());
    wchar_t parent[128];
    wcscpy(parent, server_path);
    *wcsrchr(parent, L'\\') = 0;
    if (SUCCEEDED(hr))
        hr = HRESULT_FROM_WIN32(RegDeleteTreeW(HKEY_CURRENT_USER, parent));
    if (SUCCEEDED(hr))
        hr = HRESULT_FROM_WIN32(RegDeleteTreeW(HKEY_CURRENT_USER, registry_path));
    if (SUCCEEDED(hr))
        hr = HRESULT_FROM_WIN32(RegDeleteTreeW(HKEY_CURRENT_USER, app_registration_path));
    app_id[0] = 0;
    return notify_hresult(hr, 0);
}
#ifdef MINYAR_NOTIFY_TEST
const CLSID *minyar_winnotify_testClsid(void) {
    return &activator_clsid;
}
void minyar_winnotify_testForeignOwner(bool foreign) {
    assert(SUCCEEDED(write_string(registry_path, L"Owner", foreign ? L"foreign.exe" : executable)));
}
void minyar_winnotify_testCreated(long long id, ULONGLONG value) {
    Notice *notice = find_notice(id);
    assert(notice);
    wchar_t path[320];
    swprintf(path, 320, L"%ls\\Pending\\%ls", registry_path, notice->token);
    HKEY key = NULL;
    assert(RegOpenKeyExW(HKEY_CURRENT_USER, path, 0, KEY_SET_VALUE, &key) == 0);
    assert(RegSetValueExW(key, L"Created", 0, REG_QWORD, (const BYTE *)&value, sizeof(value)) == 0);
    RegCloseKey(key);
}
HRESULT minyar_winnotify_testActivate(const wchar_t *app, const wchar_t *argument, ULONG inputs) {
    return activate_notice(app, argument, inputs);
}
MinyarBytes *minyar_winnotify_testPrepare(const MinyarBytes *raw_actions) {
    ActionDefinition definitions[5] = {0};
    unsigned count = 0;
    bool valid = parse_actions(raw_actions, definitions, &count);
    if (!valid) {
        for (unsigned i = 0; i < 5; i++)
            free(definitions[i].label);
        return notify_result(6, E_INVALIDARG, 0);
    }
    Notice *notice = calloc(1, sizeof(*notice));
    if (!notice)
        minyar_native_stop("Notification test allocation failed.");
    unsigned char random[16];
    assert(BCryptGenRandom(NULL, random, 16, BCRYPT_USE_SYSTEM_PREFERRED_RNG) >= 0);
    for (unsigned i = 0; i < 16; i++)
        swprintf(notice->token + 2 * i, 3, L"%02x", random[i]);
    IXmlDocument *document = NULL;
    HRESULT hr =
        create_notice_xml(L"<&日本語", L"\" body", notice->token, definitions, count, &document);
    if (document)
        IXmlDocument_Release(document);
    if (SUCCEEDED(hr))
        hr = persist_notice(notice, definitions, count);
    for (unsigned i = 0; i < 5; i++)
        free(definitions[i].label);
    if (FAILED(hr)) {
        release_notice(notice);
        return notify_hresult(hr, 0);
    }
    notice->id = next_id++;
    notice->next = notices;
    notices = notice;
    notice_count++;
    return notify_result(0, S_OK, notice->id);
}
#endif
