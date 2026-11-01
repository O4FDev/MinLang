/* Included by system.c before system_process.h: PTY sessions for the `system` package.
 *
 * openPty creates a matched controller/terminal pair and reports both; spawnOnTerminal starts a child on that
 * terminal as its controlling tty (setsid, then the child opens the terminal itself, which is what makes it the
 * controlling tty) using the same process registry, so system.wait/poll/childProcessId work on the returned handle;
 * resizeTerminal sets the window size the kernel reports to the child. The controller is an ordinary descriptor:
 * read and write it with `files`, and watch it with `eventloop`. It is non-blocking and close-on-exec, so a read
 * with no output ready reports EAGAIN and the descriptor never leaks into the child. */
#ifndef _WIN32
#ifndef __linux__
#include <stdlib.h>   /* grantpt, unlockpt, ptsname */
#endif
#include <limits.h>
#include <sys/ioctl.h>
#include <termios.h>

enum { SYSTEM_TERMINAL_PATH = 256, SYSTEM_TERMINAL_TRANSFER = 1048576, SYSTEM_TERMINAL_CHUNK = 65536 };

/* Little-endian u64, matching how Bytes carry packed scalars. */
static void system_terminal_put64(unsigned char *bytes, uint64_t value) {
    for (unsigned at = 0; at < 8; at++) bytes[at] = (unsigned char)(value >> (at * 8));
}

static bool system_terminal_path(int controller, char *path, size_t capacity);

/* Geometry requested while the terminal was not open yet. Darwin destroys a pty's terminal state when its last
 * terminal descriptor closes, so a size set before any open would be lost; spawnOnTerminal replays the pending
 * geometry through a temporary descriptor instead. */
enum { SYSTEM_TERMINAL_PENDING = 4 };
static MINYAR_NATIVE_THREAD_LOCAL struct {
    int controller; unsigned short rows, columns;
} system_terminal_pending[SYSTEM_TERMINAL_PENDING];
static MINYAR_NATIVE_THREAD_LOCAL size_t system_terminal_pending_count;

static bool system_terminal_pending_record(int controller, unsigned short rows, unsigned short columns) {
    for (size_t at = 0; at < system_terminal_pending_count; at++)
        if (system_terminal_pending[at].controller == controller) {
            system_terminal_pending[at].rows = rows;
            system_terminal_pending[at].columns = columns;
            return true;
        }
    if (system_terminal_pending_count == SYSTEM_TERMINAL_PENDING) return false;
    system_terminal_pending[system_terminal_pending_count].controller = controller;
    system_terminal_pending[system_terminal_pending_count].rows = rows;
    system_terminal_pending[system_terminal_pending_count].columns = columns;
    system_terminal_pending_count += 1;
    return true;
}

static bool system_terminal_pending_take(int controller, struct winsize *size) {
    for (size_t at = 0; at < system_terminal_pending_count; at++)
        if (system_terminal_pending[at].controller == controller) {
            memset(size, 0, sizeof(*size));
            size->ws_row = system_terminal_pending[at].rows;
            size->ws_col = system_terminal_pending[at].columns;
            system_terminal_pending_count -= 1;
            system_terminal_pending[at] = system_terminal_pending[system_terminal_pending_count];
            return true;
        }
    return false;
}

/* Darwin accepts TIOCSWINSZ on a controller only while some descriptor holds the terminal, and forgets the size when
 * the last one closes; Linux keeps it on the controller. So a successful request here means the size is live. */
static int system_terminal_apply(int controller, const struct winsize *size) {
    struct winsize *request = (struct winsize *)size;
    return ioctl(controller, TIOCSWINSZ, request) < 0 ? errno : 0;
}

/* Apply geometry that was recorded before the terminal existed. The returned descriptor must stay open across the
 * spawn (it holds the terminal's state, including that size) and be closed once the child has opened it too. Returns
 * -1 when nothing is pending or the terminal cannot be opened. */
static int system_terminal_guard(int controller) {
    struct winsize size;
    if (!system_terminal_pending_take(controller, &size)) return -1;
    char path[SYSTEM_TERMINAL_PATH];
    if (!system_terminal_path(controller, path, sizeof(path))) return -1;
    int terminal = open(path, O_RDWR | O_NOCTTY | O_CLOEXEC);
    if (terminal < 0) return -1;
    if (ioctl(terminal, TIOCSWINSZ, &size) < 0) { close(terminal); return -1; }
    return terminal;
}

/* The terminal path that belongs to `controller`, for example /dev/pts/3. */
static bool system_terminal_path(int controller, char *path, size_t capacity) {
    if (capacity == 0) { errno = EINVAL; return false; }
#if defined(__linux__)
    int error = ptsname_r(controller, path, capacity);
    if (error) { errno = error; return false; }
#else
    const char *name = ptsname(controller);
    if (!name) { if (!errno) errno = ENODEV; return false; }
    size_t length = strlen(name);
    if (length >= capacity) { errno = ENAMETOOLONG; return false; }
    memcpy(path, name, length + 1);
#endif
    return true;
}

/* Raise a descriptor to 3 or above: a controller that landed on 0, 1 or 2 would confuse the child's redirects. */
static int system_terminal_lift(int descriptor) {
    if (descriptor >= 3) return descriptor;
    int lifted = fcntl(descriptor, F_DUPFD_CLOEXEC, 3);
    int error = errno;
    close(descriptor);
    errno = error;
    return lifted;
}

/* An owned controller descriptor, or -errno. The terminal itself is not opened here (the child opens it), so no
 * second descriptor hides the terminal's end of file. */
static int system_terminal_open(char *path, size_t capacity) {
    int controller = posix_openpt(O_RDWR | O_NOCTTY | O_NONBLOCK | O_CLOEXEC);
    if (controller < 0) return -errno;
    controller = system_terminal_lift(controller);
    if (controller < 0) return -errno;
    int error = 0;
    if (grantpt(controller) < 0 || unlockpt(controller) < 0) error = errno;
    else if (!system_terminal_path(controller, path, capacity)) error = errno;
    if (error) { close(controller); return -error; }
    return controller;
}

/* Payload layout: controller (i64, -errno on failure), path length (i64), path bytes. */
MinyarBytes *minyar_system_openPtyNative(void) {
    char path[SYSTEM_TERMINAL_PATH];
    int controller = system_terminal_open(path, sizeof(path));
    size_t length = controller < 0 ? 0 : strlen(path);
    MinyarBytes *result = minyar_bytes_new(16 + (long long)length);
    unsigned char *bytes = (unsigned char *)result->bytes;
    system_terminal_put64(bytes, (uint64_t)(long long)controller);
    system_terminal_put64(bytes + 8, (uint64_t)length);
    if (length) memcpy(bytes + 16, path, length);
    system_error = controller < 0 ? -controller : 0;
    return result;
}

/* TIOCSWINSZ: the kernel then reports the new size to the child and signals its foreground group with SIGWINCH. Linux
 * accepts the request on the controller, Darwin only on the terminal itself (the controller answers ENOTTY), so fall
 * back to opening the terminal for the ioctl and closing it again. O_NOCTTY keeps that open from adopting a controlling
 * terminal, and the descriptor is gone before the caller looks at the session. */
long long minyar_system_resizeTerminal(long long controller, long long rows, long long columns) {
    system_error = 0;
    if (controller < 0 || controller > INT_MAX || rows < 1 || rows > 65535 || columns < 1 || columns > 65535)
        return system_failure(EINVAL);
    struct winsize size;
    memset(&size, 0, sizeof(size));
    size.ws_row = (unsigned short)rows;
    size.ws_col = (unsigned short)columns;
    int failure = system_terminal_apply((int)controller, &size);
    if (!failure) return 0;
    /* No terminal state exists yet: remember the geometry for spawnOnTerminal, which applies it while the child's
     * terminal is open. */
    if (failure == ENOTTY && system_terminal_pending_record((int)controller, size.ws_row, size.ws_col)) return 0;
    return system_failure(failure);
}

/* Read what the terminal has ready into `buffer` (appended), at most one 64 KiB read per call. Non-blocking, so an
 * idle terminal reports -EAGAIN; -EIO is the Linux end of the session. */
long long minyar_system_readTerminal(long long controller, MinyarBytes *buffer, long long length) {
    system_error = 0;
    if (!system_valid_buffer(buffer) || length < 0 || length > SYSTEM_TERMINAL_TRANSFER) return system_failure(EINVAL);
    if (!length) return 0;
    unsigned char chunk[SYSTEM_TERMINAL_CHUNK];
    size_t want = (size_t)length < sizeof(chunk) ? (size_t)length : sizeof(chunk);
    ssize_t count;
    do { count = read((int)controller, chunk, want); } while (count < 0 && errno == EINTR);
    if (count <= 0) return count == 0 ? 0 : system_failure(errno);
    unsigned char *target = minyar_native_bytes_append(buffer, (long long)count);
    memcpy(target, chunk, (size_t)count);
    return (long long)count;
}

/* Write once, like write(2): a short count means the terminal is full, so retry from offset + count. */
long long minyar_system_writeTerminal(long long controller, const MinyarBytes *data, long long offset, long long length) {
    system_error = 0;
    if (!system_valid_buffer(data) || offset < 0 || length < 0 || offset > data->byte_length ||
        length > data->byte_length - offset || length > SYSTEM_TERMINAL_TRANSFER)
        return system_failure(EINVAL);
    if (!length) return 0;
    ssize_t count;
    do { count = write((int)controller, data->bytes + offset, (size_t)length); } while (count < 0 && errno == EINTR);
    return count < 0 ? system_failure(errno) : (long long)count;
}

#else   /* _WIN32: PTYs and controlling terminals are POSIX services. */

/* The same payload shape as the POSIX branch, carrying the failure as its controller. */
MinyarBytes *minyar_system_openPtyNative(void) {
    MinyarBytes *result = minyar_bytes_new(16);
    unsigned char *bytes = (unsigned char *)result->bytes;
    memset(bytes, 0xFF, 8);
    memset(bytes + 8, 0, 8);
    system_error = ENOTSUP;
    return result;
}
long long minyar_system_resizeTerminal(long long controller, long long rows, long long columns) {
    (void)controller; (void)rows; (void)columns;
    return system_failure(ENOTSUP);
}
long long minyar_system_readTerminal(long long controller, MinyarBytes *buffer, long long length) {
    (void)controller; (void)buffer; (void)length;
    return system_failure(ENOTSUP);
}
long long minyar_system_writeTerminal(long long controller, const MinyarBytes *data, long long offset, long long length) {
    (void)controller; (void)data; (void)offset; (void)length;
    return system_failure(ENOTSUP);
}

#endif  /* _WIN32 */
