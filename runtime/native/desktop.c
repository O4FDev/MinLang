#include "../minyar_native.h"
#include <stdint.h>
static void put(MinyarBytes *b, unsigned offset, int64_t value) {
    memcpy((unsigned char *)b->bytes + offset, &value, 8);
}
static MinyarBytes *result(unsigned size, uint32_t error, int32_t native, int64_t value) {
    MinyarBytes *b = minyar_bytes_new(size);
    memcpy((unsigned char *)b->bytes, &error, 4);
    memcpy((unsigned char *)b->bytes + 4, &native, 4);
    put(b, 8, value);
    return b;
}
#ifdef _WIN32
#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0600
#endif
#define WIN32_LEAN_AND_MEAN
#define COBJMACROS
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <iphlpapi.h>
#include <netioapi.h>
#include <netlistmgr.h>
#include <shellapi.h>
#include <bcrypt.h>

static DWORD owner;
static INetworkCostManager *cost_manager;
static bool com_owned, cost_initialized;
extern MinyarBytes *minyar_winnotify_showRaw(const MinyarText *, const MinyarText *,
                                             const MinyarBytes *);
extern MinyarBytes *minyar_winnotify_statusRaw(long long), *minyar_winnotify_closeRaw(long long);
static void thread(void) {
    DWORD current = GetCurrentThreadId();
    if (!owner)
        owner = current;
    if (owner != current)
        minyar_native_stop("desktop APIs require their owning main thread.");
}
static uint32_t kind(DWORD status) {
    return status == ERROR_ACCESS_DENIED ? 8 : 7;
}
static MinyarBytes *scalar(DWORD status, int64_t value) {
    return result(16, status ? kind(status) : 0, (int32_t)status, value);
}
MinyarBytes *minyar_desktop_powerRaw(void) {
    thread();
    SYSTEM_POWER_STATUS status;
    if (!GetSystemPowerStatus(&status)) {
        DWORD error = GetLastError();
        return result(32, kind(error), (int32_t)error, 0);
    }
    if (status.BatteryFlag == 255 || status.ACLineStatus == 255)
        return result(32, 9, ERROR_NOT_READY, 0);
    MinyarBytes *b = result(32, 0, 0, status.BatteryFlag != 255 && !(status.BatteryFlag & 128));
    put(b, 16, status.ACLineStatus == 1);
    put(b, 24, status.BatteryLifePercent <= 100 ? status.BatteryLifePercent : -1);
    return b;
}
static void initialize_cost(void) {
    if (cost_initialized)
        return;
    cost_initialized = true;
    HRESULT status = CoInitializeEx(NULL, COINIT_APARTMENTTHREADED);
    if (SUCCEEDED(status))
        com_owned = true;
    else if (status != RPC_E_CHANGED_MODE)
        return;
    CoCreateInstance(&CLSID_NetworkListManager, NULL, CLSCTX_INPROC_SERVER,
                     &IID_INetworkCostManager, (void **)&cost_manager);
}
MinyarBytes *minyar_desktop_networkRaw(void) {
    thread();
    SOCKADDR_INET destination = {0};
    NET_IFINDEX index = 0;
    destination.si_family = AF_INET;
    destination.Ipv4.sin_addr.s_addr = htonl(0x01010101);
    DWORD status = GetBestInterfaceEx((SOCKADDR *)&destination, &index);
    if (status) {
        memset(&destination, 0, sizeof(destination));
        destination.si_family = AF_INET6;
        unsigned char address[16] = {0x26, 0x06, 0x47, 0, 0x47, 0, 0,    0,
                                     0,    0,    0,    0, 0,    0, 0x11, 0x11};
        memcpy(&destination.Ipv6.sin6_addr, address, 16);
        status = GetBestInterfaceEx((SOCKADDR *)&destination, &index);
    }
    if (status && status != ERROR_NETWORK_UNREACHABLE && status != ERROR_NOT_FOUND &&
        status != ERROR_HOST_UNREACHABLE)
        return result(48, kind(status), (int32_t)status, 0);
    MinyarBytes *b = result(48, 0, 0, 1);
    MIB_IF_ROW2 row = {0};
    row.InterfaceIndex = index;
    if (!status) {
        status = GetIfEntry2(&row);
        if (status) {
            extern void minyar_rc_release(void *);
            minyar_rc_release(b);
            return result(48, kind(status), (int32_t)status, 0);
        }
        put(b, 16, row.OperStatus == IfOperStatusUp);
        put(b, 24, row.Type == IF_TYPE_IEEE80211);
        put(b, 32, row.Type == IF_TYPE_ETHERNET_CSMACD);
    }
    initialize_cost();
    DWORD cost = 0;
    int64_t flags = 4;
    NLM_SOCKADDR cost_address = {0};
    memcpy(cost_address.data, &destination, sizeof(destination));
    if (cost_manager &&
        SUCCEEDED(INetworkCostManager_GetCost(cost_manager, &cost, &cost_address)) &&
        cost != NLM_CONNECTION_COST_UNKNOWN) {
        flags = (cost & (NLM_CONNECTION_COST_FIXED | NLM_CONNECTION_COST_VARIABLE |
                         NLM_CONNECTION_COST_ROAMING | NLM_CONNECTION_COST_OVERDATALIMIT))
                    ? 1
                    : 0;
    }
    put(b, 40, flags);
    return b;
}
MinyarBytes *minyar_desktop_networkStopRaw(void) {
    thread();
    if (cost_manager) {
        INetworkCostManager_Release(cost_manager);
        cost_manager = NULL;
    }
    if (com_owned) {
        CoUninitialize();
        com_owned = false;
    }
    cost_initialized = false;
    return scalar(0, 0);
}
static DWORD registration(wchar_t **command, wchar_t name[72], wchar_t **path) {
    *path = calloc(32768, sizeof(wchar_t));
    if (!*path)
        minyar_native_stop("desktop allocation failed.");
    DWORD length = GetModuleFileNameW(NULL, *path, 32768);
    if (!length || length >= 32768) {
        DWORD status = GetLastError();
        free(*path);
        *path = NULL;
        return status ? status : ERROR_INSUFFICIENT_BUFFER;
    }
    unsigned char digest[32];
    BCRYPT_ALG_HANDLE algorithm = NULL;
    BCRYPT_HASH_HANDLE hash = NULL;
    NTSTATUS status = BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, NULL, 0);
    if (!status)
        status = BCryptCreateHash(algorithm, &hash, NULL, 0, NULL, 0, 0);
    if (!status)
        status = BCryptHashData(hash, (PUCHAR)*path, length * sizeof(wchar_t), 0);
    if (!status)
        status = BCryptFinishHash(hash, digest, 32, 0);
    if (hash)
        BCryptDestroyHash(hash);
    if (algorithm)
        BCryptCloseAlgorithmProvider(algorithm, 0);
    if (status) {
        free(*path);
        *path = NULL;
        return ERROR_INVALID_DATA;
    }
    memcpy(name, L"Minyar.", 7 * sizeof(wchar_t));
    for (unsigned i = 0; i < 32; i++) {
        name[7 + 2 * i] = L"0123456789abcdef"[digest[i] >> 4];
        name[8 + 2 * i] = L"0123456789abcdef"[digest[i] & 15];
    }
    name[71] = 0;
    *command = calloc((size_t)length + 3, sizeof(wchar_t));
    if (!*command)
        minyar_native_stop("desktop allocation failed.");
    (*command)[0] = L'"';
    memcpy(*command + 1, *path, length * sizeof(wchar_t));
    (*command)[length + 1] = L'"';
    return ERROR_SUCCESS;
}
static const wchar_t *login_key(void) {
#ifdef MINYAR_DESKTOP_TEST
    static wchar_t test_key[96];
    if (!test_key[0])
        swprintf(test_key, 96, L"Software\\Minyar\\DesktopTests\\%lu",
                 (unsigned long)GetCurrentProcessId());
    return test_key;
#else
    return L"Software\\Microsoft\\Windows\\CurrentVersion\\Run";
#endif
}
static DWORD login(bool write, bool enabled, int64_t *value) {
    wchar_t *command = NULL, *path = NULL, name[72];
    DWORD status = registration(&command, name, &path);
    if (status)
        return status;
    HKEY key = NULL;
    status = write ? RegCreateKeyExW(HKEY_CURRENT_USER, login_key(), 0, NULL, 0,
                                     KEY_QUERY_VALUE | KEY_SET_VALUE, NULL, &key, NULL)
                   : RegOpenKeyExW(HKEY_CURRENT_USER, login_key(), 0, KEY_QUERY_VALUE, &key);
    if (status == ERROR_FILE_NOT_FOUND && !write) {
        status = 0;
        *value = 0;
        goto done;
    }
    if (status)
        goto done;
    DWORD type = 0, size = 0;
    status = RegQueryValueExW(key, name, NULL, &type, NULL, &size);
    bool exists = status != ERROR_FILE_NOT_FOUND;
    if (status != ERROR_FILE_NOT_FOUND && status)
        goto done;
    if (exists) {
        if (type != REG_SZ || size > 65536 || size < sizeof(wchar_t) || size % sizeof(wchar_t)) {
            status = ERROR_ACCESS_DENIED;
            goto done;
        }
        wchar_t *stored = calloc((size_t)size + sizeof(wchar_t), 1);
        if (!stored)
            minyar_native_stop("desktop allocation failed.");
        status = RegQueryValueExW(key, name, NULL, &type, (BYTE *)stored, &size);
        if (!status && (type != REG_SZ || size != (wcslen(command) + 1) * sizeof(wchar_t) ||
                        memcmp(stored, command, size)))
            status = ERROR_ACCESS_DENIED;
        free(stored);
        if (status)
            goto done;
    }
    status = 0;
    *value = exists;
    if (write) {
        if (enabled)
            status = RegSetValueExW(key, name, 0, REG_SZ, (BYTE *)command,
                                    (DWORD)((wcslen(command) + 1) * sizeof(wchar_t)));
        else if (exists)
            status = RegDeleteValueW(key, name);
        if (!status)
            *value = enabled;
    }
done:
    if (key)
        RegCloseKey(key);
    free(command);
    free(path);
    return status;
}
MinyarBytes *minyar_desktop_launchAtLoginStatusRaw(void) {
    thread();
    int64_t value = 0;
    DWORD status = login(false, false, &value);
    return scalar(status, value);
}
MinyarBytes *minyar_desktop_setLaunchAtLoginRaw(bool enabled) {
    thread();
    int64_t value = 0;
    DWORD status = login(true, enabled, &value);
    return scalar(status, value);
}
MinyarBytes *minyar_desktop_notifyRaw(const MinyarText *title, const MinyarText *body) {
    thread();
    // Borrowed empty native bytes: the notification backend copies all inputs.
    MinyarBytes actions = {0};
    return minyar_winnotify_showRaw(title, body, &actions);
}
MinyarBytes *minyar_desktop_notificationStatusRaw(long long id) {
    thread();
    return minyar_winnotify_statusRaw(id);
}
MinyarBytes *minyar_desktop_notificationCloseRaw(long long id) {
    thread();
    return minyar_winnotify_closeRaw(id);
}
#ifdef MINYAR_DESKTOP_TEST
void minyar_desktop_testForeignLogin(void) {
    wchar_t *command = NULL, *path = NULL, name[72];
    if (registration(&command, name, &path))
        abort();
    HKEY key;
    if (RegCreateKeyExW(HKEY_CURRENT_USER, login_key(), 0, NULL, 0, KEY_SET_VALUE, NULL, &key,
                        NULL))
        abort();
    const wchar_t foreign[] = L"\"other-app.exe\" --do-not-delete";
    if (RegSetValueExW(key, name, 0, REG_SZ, (const BYTE *)foreign, sizeof(foreign)))
        abort();
    RegCloseKey(key);
    free(command);
    free(path);
}
void minyar_desktop_testCleanup(void) {
    RegDeleteTreeW(HKEY_CURRENT_USER, login_key());
}
#endif
#else
MinyarBytes *minyar_desktop_powerRaw(void) {
    return result(32, 9, 0, 0);
}
MinyarBytes *minyar_desktop_networkRaw(void) {
    return result(48, 9, 0, 0);
}
MinyarBytes *minyar_desktop_networkStopRaw(void) {
    return result(16, 9, 0, 0);
}
MinyarBytes *minyar_desktop_launchAtLoginStatusRaw(void) {
    return result(16, 9, 0, 0);
}
MinyarBytes *minyar_desktop_setLaunchAtLoginRaw(bool enabled) {
    (void)enabled;
    return result(16, 9, 0, 0);
}
MinyarBytes *minyar_desktop_notifyRaw(const MinyarText *title, const MinyarText *body) {
    (void)title;
    (void)body;
    return result(16, 9, 0, 0);
}
MinyarBytes *minyar_desktop_notificationStatusRaw(long long id) {
    (void)id;
    return result(16, 9, 0, 0);
}
MinyarBytes *minyar_desktop_notificationCloseRaw(long long id) {
    (void)id;
    return result(16, 9, 0, 0);
}
#endif
