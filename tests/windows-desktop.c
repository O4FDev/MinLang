#include "../runtime/minyar_native.h"
#include <windows.h>
#include <assert.h>
#include <stdint.h>
extern MinyarBytes *minyar_desktop_powerRaw(void), *minyar_desktop_networkRaw(void),
    *minyar_desktop_networkStopRaw(void);
extern MinyarBytes *minyar_desktop_launchAtLoginStatusRaw(void),
    *minyar_desktop_setLaunchAtLoginRaw(bool);
extern MinyarBytes *minyar_desktop_notifyRaw(const MinyarText *, const MinyarText *);
extern MinyarBytes *minyar_desktop_notificationStatusRaw(long long),
    *minyar_desktop_notificationCloseRaw(long long);
extern void minyar_desktop_testForeignLogin(void), minyar_desktop_testCleanup(void);
extern void minyar_rc_release(void *);
static int64_t value(MinyarBytes *b, unsigned offset) {
    int64_t v;
    memcpy(&v, b->bytes + offset, 8);
    return v;
}
static uint32_t error(MinyarBytes *b) {
    uint32_t v;
    assert(b->byte_length >= 8);
    memcpy(&v, b->bytes, 4);
    return v;
}
static int64_t scalar(MinyarBytes *b) {
    assert(b->byte_length == 16);
    assert(!error(b));
    int64_t v = value(b, 8);
    minyar_rc_release(b);
    return v;
}
int main(void) {
    MinyarBytes *power = minyar_desktop_powerRaw();
    assert(power->byte_length == 32);
    if (!error(power)) {
        assert(value(power, 8) == 0 || value(power, 8) == 1);
        assert(value(power, 16) == 0 || value(power, 16) == 1);
        assert(value(power, 24) >= -1 && value(power, 24) <= 100);
    } else
        assert(error(power) == 9 || error(power) == 7);
    minyar_rc_release(power);
    MinyarBytes *network = minyar_desktop_networkRaw();
    assert(network->byte_length == 48);
    if (!error(network)) {
        assert(value(network, 8) == 1);
        assert(value(network, 16) == 0 || value(network, 16) == 1);
        assert(!(value(network, 24) && value(network, 32)));
    }
    minyar_rc_release(network);
    assert(scalar(minyar_desktop_networkStopRaw()) == 0);
    assert(scalar(minyar_desktop_launchAtLoginStatusRaw()) == 0);
    assert(scalar(minyar_desktop_setLaunchAtLoginRaw(true)) == 1);
    assert(scalar(minyar_desktop_launchAtLoginStatusRaw()) == 1);
    assert(scalar(minyar_desktop_setLaunchAtLoginRaw(false)) == 0);
    minyar_desktop_testForeignLogin();
    MinyarBytes *foreign = minyar_desktop_setLaunchAtLoginRaw(false);
    assert(error(foreign) == 8);
    minyar_rc_release(foreign);
    foreign = minyar_desktop_setLaunchAtLoginRaw(true);
    assert(error(foreign) == 8);
    minyar_rc_release(foreign);
    minyar_desktop_testCleanup();
    MinyarText *title = minyar_native_copy_text((const unsigned char *)"Minyar test 日本語", 21);
    MinyarText *body =
        minyar_native_copy_text((const unsigned char *)"Windows notification fixture", 28);
    MinyarBytes *notify = minyar_desktop_notifyRaw(title, body);
    if (!error(notify)) {
        long long id = value(notify, 8);
        assert(id > 0);
        assert(scalar(minyar_desktop_notificationStatusRaw(id)) == 1);
        assert(scalar(minyar_desktop_notificationCloseRaw(id)) == 0);
        MinyarBytes *stale = minyar_desktop_notificationStatusRaw(id);
        assert(error(stale) == 4);
        minyar_rc_release(stale);
    } else
        assert(error(notify) == 9 || error(notify) == 8 || error(notify) == 7);
    minyar_rc_release(notify);
    minyar_rc_release(title);
    minyar_rc_release(body);
    unsigned char nul[] = {'a', 0, 'b'};
    title = minyar_native_copy_text(nul, 3);
    body = minyar_native_copy_text((const unsigned char *)"body", 4);
    notify = minyar_desktop_notifyRaw(title, body);
    assert(error(notify) == 6);
    minyar_rc_release(notify);
    minyar_rc_release(title);
    minyar_rc_release(body);
    puts("Windows desktop OS results, owned login registration and notification lifetime verified");
    return 0;
}
