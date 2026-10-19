/* Bounded ranged reads: real sparse large files and deterministic pseudo-files. */
#define _GNU_SOURCE 1
#include "../runtime/minyar_native.h"
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdint.h>
#include <sys/stat.h>
#include <unistd.h>
#include "files-test-path.h"
static int pseudo, calls, partial_failure;
static MinyarBytes *bounded_new(long long length) {
    assert(length <= 65536); return minyar_bytes_new(length);
}
static ssize_t ranged_pread(int fd, void *out, size_t length, off_t position) {
    if (!pseudo) return pread(fd, out, length, position);
    if (!calls++) { errno = EINTR; return -1; }
    if (partial_failure && position >= 2) { errno = EIO; return -1; }
    const char payload[] = "pseudo-data";
    if (position >= (off_t)sizeof(payload)-1) return 0;
    size_t count = sizeof(payload)-1-(size_t)position;
    if (count > length) count = length;
    if (count > 2) count = 2; /* retry short reads */
    memcpy(out, payload+position, count); return (ssize_t)count;
}
#define minyar_bytes_new bounded_new
#define pread ranged_pread
#include "../runtime/native/files.c"
#undef pread
#undef minyar_bytes_new
void minyar_rc_release(void *);
static void expect(long long fd, long long offset, long long length, const char *value, int error) {
    MinyarBytes *b = minyar_files_readAt(fd, offset, length);
    assert(minyar_files_lastError() == error);
    assert(b->byte_length == (long long)strlen(value));
    assert(!b->byte_length || !memcmp(b->bytes, value, (size_t)b->byte_length));
    minyar_rc_release(b);
}
int main(int argc, char **argv) {
    assert(argc == 2);
    char path[PATH_MAX]; files_test_path(path,sizeof(path),"minyar-ranges-XXXXXX");
    int fd = mkstemp(path); assert(fd >= 0); unlink(path);
    assert(write(fd, "abcdef", 6) == 6);
    if (!strcmp(argv[1], "huge")) {
        expect(fd, 2, 1LL<<40, "cdef", 0);
        MinyarBytes *b = minyar_bytes_new(2); memcpy((void *)b->bytes, "xy", 2);
        assert(minyar_files_readAppend(fd, 2, b, 1LL<<40) == 4);
        assert(!minyar_files_lastError() && b->byte_length == 6 && !memcmp(b->bytes, "xycdef", 6));
        minyar_rc_release(b);
    }
    else if (!strcmp(argv[1], "invalid")) {
        expect(-1, 0, 1, "", -EBADF); expect((long long)INT_MAX+1, 0, 0, "", -EBADF);
        assert(files_valid_utf8((const unsigned char *)"plain", 5));
        assert(files_valid_utf8((const unsigned char *)"\xc3\xa9\xe2\x82\xac\xf0\x9f\x8c\x8d", 9));
        assert(!files_valid_utf8((const unsigned char *)"\xff", 1));
        assert(!files_valid_utf8((const unsigned char *)"\xc0\xaf", 2));
        assert(!files_valid_utf8((const unsigned char *)"\xed\xa0\x80", 3));
        assert(!files_valid_utf8((const unsigned char *)"\xf4\x90\x80\x80", 4));
        assert(!files_valid_utf8((const unsigned char *)"\xe2\x82", 2));
#ifdef __linux__
        char directory[PATH_MAX]; files_test_path(directory,sizeof(directory),"minyar-invalid-names-XXXXXX");
        assert(mkdtemp(directory));
        char entry[PATH_MAX]; size_t prefix = strlen(directory);
        assert(prefix + 3 < sizeof(entry));
        memcpy(entry, directory, prefix); entry[prefix] = '/'; entry[prefix+1] = (char)0xff; entry[prefix+2] = 0;
        int bad = open(entry, O_WRONLY | O_CREAT | O_EXCL, 0600); assert(bad >= 0); close(bad);
        MinyarText dirtext = {(const unsigned char *)directory, (long long)prefix, 0, NULL, NULL};
        MinyarBytes *names = minyar_files_listNames(&dirtext);
        assert(names->byte_length == 0 && minyar_files_lastError() == -EILSEQ);
        minyar_rc_release(names); assert(!unlink(entry) && !rmdir(directory));
#endif
        close(fd); expect(fd, 0, 0, "", -EBADF); expect(fd, 0, 1LL<<40, "", -EBADF); return 0;
    } else if (!strcmp(argv[1], "pseudo")) {
        assert(!ftruncate(fd, 0)); pseudo = 1;
        expect(fd, 0, 1LL<<40, "pseudo-data", 0); assert(calls >= 7);
        MinyarBytes *b = minyar_bytes_new(2); memcpy((void *)b->bytes, "xy", 2);
        calls = 0;
        assert(minyar_files_readAppend(fd, 0, b, 1LL<<40) == 11);
        assert(!minyar_files_lastError() && b->byte_length == 13 && !memcmp(b->bytes, "xypseudo-data", 13));
        minyar_rc_release(b);
    } else if (!strcmp(argv[1], "large")) {
        long long offset = (1LL<<32)+123;
        assert(pwrite(fd, "large", 5, (off_t)offset) == 5);
        expect(fd, offset, 50, "large", 0); expect(fd, offset+5, 1LL<<40, "", 0);
        assert(lseek(fd, 0, SEEK_CUR) == 6);
    } else if (!strcmp(argv[1], "eof")) {
        expect(fd, 3, 20, "def", 0); expect(fd, 6, 4, "", 0); expect(fd, 30, 4, "", 0);
        expect(fd, 0, 0, "", 0); expect(fd, -1, 1, "", -EINVAL);
        expect(fd, LLONG_MAX-1, 3, "", -EOVERFLOW);
        expect(fd, 0, -1, "", -EINVAL);
        expect(fd, 0, LLONG_MAX, "", -EOVERFLOW);
        MinyarBytes *b = minyar_bytes_new(2); memcpy((void *)b->bytes, "xy", 2);
        long long capacity = b->character_length;
        assert(minyar_files_readAppend(fd, 6, b, 1LL<<40) == 0);
        assert(!minyar_files_lastError() && b->byte_length == 2 && b->character_length == capacity);
        assert(!memcmp(b->bytes, "xy", 2)); minyar_rc_release(b);
    } else if (!strcmp(argv[1], "partial-error")) {
        pseudo = partial_failure = 1;
        expect(fd, 0, 64, "", -EIO);
        MinyarBytes *b = minyar_bytes_new(2); memcpy((void *)b->bytes, "xy", 2);
        calls = 0;
        assert(minyar_files_readAppend(fd, 0, b, 64) == -EIO);
        assert(minyar_files_lastError() == -EIO && b->byte_length == 2 && !memcmp(b->bytes, "xy", 2));
        minyar_rc_release(b);
        pseudo = 0; expect(fd, 0, 6, "abcdef", 0);
    } else if (!strcmp(argv[1], "read-file")) {
        char pathname[PATH_MAX]; files_test_path(pathname,sizeof(pathname),"minyar-ranges-path-XXXXXX");
        int other = mkstemp(pathname); assert(other >= 0);
        assert(write(other, "contents", 8) == 8); close(other);
        MinyarText pathtext = {(const unsigned char *)pathname, (long long)strlen(pathname), 0, NULL, NULL};
        MinyarBytes *b = minyar_files_readFile(&pathtext);
        assert(b->byte_length == 8 && !memcmp(b->bytes,"contents",8) && !minyar_files_lastError());
        minyar_rc_release(b); unlink(pathname);
        b = minyar_files_readFile(&pathtext); assert(!b->byte_length && minyar_files_lastError()==-ENOENT);
        minyar_rc_release(b);
    } else if (!strcmp(argv[1], "procfs")) {
#ifdef __linux__
        int proc = open("/proc/self/cmdline", O_RDONLY); assert(proc >= 0);
        struct stat st; assert(!fstat(proc,&st) && st.st_size == 0);
        MinyarBytes *b = minyar_files_readAt(proc,0,1LL<<40);
        assert(b->byte_length > 0 && !minyar_files_lastError()); minyar_rc_release(b); close(proc);
        MinyarText pathtext = {(const unsigned char *)"/proc/self/cmdline", 18, 0, NULL, NULL};
        b = minyar_files_readFile(&pathtext); assert(b->byte_length > 0 && !minyar_files_lastError());
        minyar_rc_release(b);
#endif
    } else abort();
    close(fd); return 0;
}
