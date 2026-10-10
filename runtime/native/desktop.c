/* The hosted Linux backend reports an unavailable desktop capability. The
 * Windows provider supplies the same envelope ABI in this translation unit. */
#include "../minyar_native.h"

static MinyarBytes *desktop_unavailable(long long size) {
    MinyarBytes *result = minyar_bytes_new(size);
    memset((void *)result->bytes, 0, (size_t)size);
    ((unsigned char *)result->bytes)[0] = 9;
    return result;
}
MinyarBytes *minyar_desktop_powerRaw(void) {
    return desktop_unavailable(32);
}
MinyarBytes *minyar_desktop_networkRaw(void) {
    return desktop_unavailable(48);
}
MinyarBytes *minyar_desktop_networkStopRaw(void) {
    return desktop_unavailable(16);
}
MinyarBytes *minyar_desktop_launchAtLoginStatusRaw(void) {
    return desktop_unavailable(16);
}
MinyarBytes *minyar_desktop_setLaunchAtLoginRaw(bool enabled) {
    (void)enabled;
    return desktop_unavailable(16);
}
MinyarBytes *minyar_desktop_notifyRaw(const MinyarText *title, const MinyarText *body) {
    (void)title;
    (void)body;
    return desktop_unavailable(16);
}
MinyarBytes *minyar_desktop_notificationStatusRaw(long long handle) {
    (void)handle;
    return desktop_unavailable(16);
}
MinyarBytes *minyar_desktop_notificationCloseRaw(long long handle) {
    (void)handle;
    return desktop_unavailable(16);
}
