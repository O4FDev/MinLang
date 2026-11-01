/* Native halves of the systems batch: CRC-32, CRC-64/NVME, Base64, the buffered
 * standard-input reader, and the lock, canonical-path, identity and
 * temporary-directory calls. Compiled with the runtime itself, so ASan and
 * UBSan see every allocation these paths make. The Minyar-level API, the time
 * module and MD5 are covered by tests/sys-files.min, tests/checksums-encoding.min,
 * tests/time-civil.min and tests/io-lines.min. */
/* No feature-test macro: the runtime headers need the platform's default
 * visibility (arc4random_buf, MAP_ANON, sysconf) and mkdtemp needs the same. */
#include "../runtime/minyar_runtime.c"
/* The file-system calls live in their own translation unit, linked alongside. */
MinyarText *minyar_files_realPathNative(const MinyarText *path);
MinyarText *minyar_files_canonicalPathNative(const MinyarText *path);
MinyarBytes *minyar_files_identityNative(const MinyarText *path);
MinyarText *minyar_files_temporaryDirectoryNative(const MinyarText *prefix);
long long minyar_files_lockNative(long long fd, _Bool exclusive, _Bool wait);
long long minyar_files_unlockNative(long long fd);
long long minyar_files_lastError(void);
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

static MinyarBytes *bytes_of(const char *text) {
    MinyarBytes *bytes = minyar_bytes_new((long long)strlen(text));
    memcpy((void *)bytes->bytes, text, strlen(text));
    return bytes;
}

static MinyarText *text_of(const char *text) {
    return minyar_native_copy_text((const unsigned char *)text, (long long)strlen(text));
}

/* ----------------------------------------------------------------- CRC-32 */

static void crc32_vectors(void) {
    MinyarBytes *check = bytes_of("123456789");
    assert(minyar_runtime_crc32(0, check, 0, check->byte_length) == 0xCBF43926LL);
    assert(minyar_runtime_crc32(0, check, 0, 0) == 0);
    assert(minyar_runtime_crc32(-4294967296LL, check, 0, check->byte_length) == 0xCBF43926LL);
    assert(minyar_runtime_crc32(0, bytes_of("abc"), 0, 3) == 0x352441C2LL);
    /* Chaining: the continuation of a partial range equals the whole. */
    long long first = minyar_runtime_crc32(0, check, 0, 4);
    assert(minyar_runtime_crc32(first, check, 4, 5) == 0xCBF43926LL);
    /* CRC-32 and CRC-32C are different polynomials over the same bytes. */
    assert(minyar_runtime_crc32(0, check, 0, check->byte_length) !=
           minyar_runtime_crc32c(0, check, 0, check->byte_length));
    /* A large range reads in the slicing-by-eight path and stays chainable. */
    MinyarBytes *large = minyar_bytes_new(1 << 16);
    memset((void *)large->bytes, 0xA5, 1 << 16);
    long long whole = minyar_runtime_crc32(0, large, 0, large->byte_length);
    long long split = minyar_runtime_crc32(0, large, 0, 1000);
    split = minyar_runtime_crc32(split, large, 1000, (1 << 16) - 1000);
    assert(whole == split);
}

/* ------------------------------------------------------------ CRC-64/NVME */

static void crc64_vectors(void) {
    static const struct { const char *text; unsigned char expected[8]; } vectors[] = {
        {"", {0, 0, 0, 0, 0, 0, 0, 0}},
        {"123456789", {0xae, 0x8b, 0x14, 0x86, 0x0a, 0x79, 0x98, 0x88}},
        {"The quick brown fox jumps over the lazy dog", {0xd7, 0x6c, 0x54, 0x05, 0x49, 0x54, 0xc1, 0x43}},
    };
    for (size_t index = 0; index < sizeof vectors / sizeof vectors[0]; index++) {
        MinyarBytes *digest = minyar_runtime_crc64(bytes_of(vectors[index].text));
        assert(digest->byte_length == 8);
        assert(memcmp((const void *)digest->bytes, vectors[index].expected, 8) == 0);
    }
}

/* ------------------------------------------------------------------ Base64 */

static void base64_vectors(void) {
    static const struct { const char *plain; const char *standard; const char *web; } vectors[] = {
        {"", "", ""}, {"f", "Zg==", "Zg"}, {"fo", "Zm8=", "Zm8"}, {"foo", "Zm9v", "Zm9v"},
        {"foob", "Zm9vYg==", "Zm9vYg"}, {"fooba", "Zm9vYmE=", "Zm9vYmE"}, {"foobar", "Zm9vYmFy", "Zm9vYmFy"},
        {"Many hands make light work.", "TWFueSBoYW5kcyBtYWtlIGxpZ2h0IHdvcmsu",
         "TWFueSBoYW5kcyBtYWtlIGxpZ2h0IHdvcmsu"},
    };
    for (size_t index = 0; index < sizeof vectors / sizeof vectors[0]; index++) {
        MinyarBytes *plain = bytes_of(vectors[index].plain);
        MinyarText *standard = minyar_runtime_base64EncodeNative(plain, 0);
        MinyarText *web = minyar_runtime_base64EncodeNative(plain, 1);
        assert(standard->byte_length == (long long)strlen(vectors[index].standard));
        assert(memcmp((const void *)standard->bytes, vectors[index].standard, strlen(vectors[index].standard)) == 0);
        assert(web->byte_length == (long long)strlen(vectors[index].web));
        assert(memcmp((const void *)web->bytes, vectors[index].web, strlen(vectors[index].web)) == 0);

        MinyarRecord *decoded = minyar_runtime_base64DecodeNative(standard, 0);
        long long code = minyar_record_get(decoded, 1);
        assert(code == 0);
        MinyarBytes *back = (MinyarBytes *)(intptr_t)minyar_record_get(decoded, 0);
        assert(back->byte_length == plain->byte_length);
        assert(plain->byte_length == 0 || memcmp((const void *)back->bytes, (const void *)plain->bytes,
                                                 (size_t)plain->byte_length) == 0);
        decoded = minyar_runtime_base64DecodeNative(web, 1);
        assert(minyar_record_get(decoded, 1) == 0);
        back = (MinyarBytes *)(intptr_t)minyar_record_get(decoded, 0);
        assert(back->byte_length == plain->byte_length);
    }
    /* The URL-safe alphabet is the standard one with two characters changed. */
    unsigned char high[2] = {0xfb, 0xff};
    MinyarBytes *raw = minyar_bytes_new(2);
    memcpy((void *)raw->bytes, high, 2);
    MinyarText *standard = minyar_runtime_base64EncodeNative(raw, 0);
    assert(standard->byte_length == 4 && memcmp((const void *)standard->bytes, "+/8=", 4) == 0);
    MinyarText *web = minyar_runtime_base64EncodeNative(raw, 1);
    assert(web->byte_length == 3 && memcmp((const void *)web->bytes, "-_8", 3) == 0);

    /* Rejections: every one reports a negative code and no data. */
    static const char *rejected[] = {"Zg", "Zg=", "Zg===", "Z=g=", "Z g==", "Zg== ", "Zm9v!", "Zm9v\n", "Zh==", "Z"};
    for (size_t index = 0; index < sizeof rejected / sizeof rejected[0]; index++) {
        MinyarRecord *outcome = minyar_runtime_base64DecodeNative(text_of(rejected[index]), 0);
        assert(minyar_record_get(outcome, 1) != 0);
        MinyarBytes *data = (MinyarBytes *)(intptr_t)minyar_record_get(outcome, 0);
        assert(data->byte_length == 0 && ((const unsigned char *)data->bytes)[0] == 0);
    }
    /* The URL-safe alphabet rejects standard characters and padded groups. */
    assert(minyar_record_get(minyar_runtime_base64DecodeNative(text_of("+/8="), 1), 1) != 0);
    assert(minyar_record_get(minyar_runtime_base64DecodeNative(text_of("-_8"), 1), 1) == 0);
    assert(minyar_record_get(minyar_runtime_base64DecodeNative(text_of("Pj8"), 1), 1) == 0);
    /* Non-canonical trailing bits are rejected, not silently zeroed. */
    assert(minyar_record_get(minyar_runtime_base64DecodeNative(text_of("_8"), 1), 1) != 0);
}

/* --------------------------------------------------------- standard input */

static MinyarRecord *next_line(void) { return minyar_runtime_readLineOutcome(); }

static void expect_line(const char *expected, long long code) {
    MinyarRecord *outcome = next_line();
    assert(minyar_record_get(outcome, 1) == code);
    MinyarBytes *line = (MinyarBytes *)(intptr_t)minyar_record_get(outcome, 0);
    if (expected) {
        assert(line->byte_length == (long long)strlen(expected));
        assert(line->byte_length == 0 || memcmp((const void *)line->bytes, expected, (size_t)line->byte_length) == 0);
    }
}

/* Feed `content` as standard input through a real file, then restore the
 * original descriptor. A pipe would block the writer until the reader drains
 * it, and these checks are single-threaded. */
static int redirect_stdin(const void *content, size_t length) {
    FILE *file = tmpfile();
    assert(file);
    assert(fwrite(content, 1, length, file) == length);
    assert(fseek(file, 0, SEEK_SET) == 0);
    int saved = dup(0);
    assert(saved >= 0);
    assert(dup2(fileno(file), 0) == 0);
    fclose(file);
    return saved;
}

static void restore_stdin(int saved) {
    assert(dup2(saved, 0) == 0);
    close(saved);
}

static void stdin_reader(void) {
    /* alpha CRLF, beta LF, an empty line, and omega with no trailing newline. */
    const char *content = "alpha\r\nbeta\n\nomega";
    int saved = redirect_stdin(content, strlen(content));
    expect_line("alpha", 0);
    expect_line("beta", 0);
    expect_line("", 0);
    expect_line("omega", 0);
    expect_line(NULL, 1);
    expect_line(NULL, 1);
    restore_stdin(saved);
}

static void stdin_overlong(void) {
    /* One over-long line and then a short one: the reader discards the rest of
     * the rejected line and continues at the next one. */
    size_t overlong = (size_t)MINYAR_STDIN_MAXIMUM_LINE + 1;
    unsigned char *filler = malloc(overlong + 8);
    assert(filler);
    memset(filler, 'x', overlong);
    memcpy(filler + overlong, "\nafter\n", 7);
    int saved = redirect_stdin(filler, overlong + 7);
    free(filler);
    MinyarRecord *outcome = next_line();
    assert(minyar_record_get(outcome, 1) == MINYAR_STDIN_TOO_LONG);
    expect_line("after", 0);
    expect_line(NULL, 1);
    restore_stdin(saved);
}

/* ------------------------------------------------------------------- files */

/* `link` is also a local name in this function; link(2) is spelled once here. */
static int hard_link(const char *existing, const char *created) { return link(existing, created); }

static void write_file(const char *path, const char *content) {
    FILE *file = fopen(path, "wb");
    assert(file);
    assert(fwrite(content, 1, strlen(content), file) == strlen(content));
    fclose(file);
}

static void files_calls(void) {
    char root[] = "/tmp/minyar-sys-native-XXXXXX";
    assert(mkdtemp(root));
    char path[512], other[512], link[512];
    snprintf(path, sizeof path, "%s/one.txt", root);
    snprintf(link, sizeof link, "%s/link.txt", root);
    snprintf(other, sizeof other, "%s/other.txt", root);
    write_file(path, "lantern");
    write_file(other, "lantern");

    /* A shared lock blocks an exclusive try-lock on another description. */
    int first = open(path, O_RDWR);
    int second = open(path, O_RDONLY);
    assert(first >= 0 && second >= 0);
    assert(minyar_files_lockNative(second, 0, 0) == 0);
    long long refused = minyar_files_lockNative(first, 1, 0);
    assert(refused == -EWOULDBLOCK);
    assert(minyar_files_unlockNative(second) == 0);
    assert(minyar_files_lockNative(first, 1, 0) == 0);
    assert(minyar_files_unlockNative(first) == 0);
    /* Closing the descriptor releases its lock. */
    assert(minyar_files_lockNative(first, 1, 0) == 0);
    assert(close(first) == 0);
    assert(minyar_files_lockNative(second, 1, 0) == 0);
    assert(minyar_files_unlockNative(second) == 0);
    assert(close(second) == 0);
    assert(minyar_files_lockNative(-1, 1, 0) == -EBADF);
    assert(minyar_files_unlockNative(-1) == -EBADF);

    /* Canonical paths resolve symbolic links and keep missing paths recoverable. */
    assert(symlink("one.txt", link) == 0);
    MinyarText *resolved = minyar_files_realPathNative(text_of(link));
    MinyarText *direct = minyar_files_realPathNative(text_of(path));
    assert(resolved->byte_length > 0 && resolved->byte_length == direct->byte_length);
    assert(memcmp((const void *)resolved->bytes, (const void *)direct->bytes, (size_t)direct->byte_length) == 0);
    assert(minyar_files_lastError() == 0);
    char missing[512];
    snprintf(missing, sizeof missing, "%s/lantern-missing", root);
    MinyarText *absent = minyar_files_realPathNative(text_of(missing));
    assert(absent->byte_length == 0 && minyar_files_lastError() == -ENOENT);
    assert(minyar_files_realPathNative(text_of(""))->byte_length == 0 && minyar_files_lastError() == -ENAMETOOLONG);
    MinyarBytes *text_bytes = bytes_of("with/nul");
    ((unsigned char *)text_bytes->bytes)[3] = 0;
    assert(minyar_files_realPathNative(text_bytes)->byte_length == 0 && minyar_files_lastError() == -EINVAL);
    /* canonicalPath accepts a last component that does not exist yet, and
     * refuses a dangling link or a missing parent directory. */
    char pending[512];
    snprintf(pending, sizeof pending, "%s/not-created.txt", root);
    MinyarText *canonical = minyar_files_canonicalPathNative(text_of(pending));
    /* The temporary root itself may sit behind a symbolic link (/var on macOS),
     * so the expectation is built from its resolved form. */
    MinyarText *canonical_root = minyar_files_realPathNative(text_of(root));
    assert(canonical->byte_length == canonical_root->byte_length + (long long)strlen("/not-created.txt"));
    assert(memcmp((const void *)canonical->bytes, (const void *)canonical_root->bytes,
                  (size_t)canonical_root->byte_length) == 0);
    assert(memcmp((const void *)canonical->bytes + canonical_root->byte_length,
                  "/not-created.txt", strlen("/not-created.txt")) == 0);
    assert(minyar_files_lastError() == 0);
    char dangling[512];
    snprintf(dangling, sizeof dangling, "%s/lantern-dangling", root);
    assert(symlink("nowhere", dangling) == 0);
    assert(minyar_files_canonicalPathNative(text_of(dangling))->byte_length == 0);
    assert(minyar_files_lastError() == -ENOENT);
    char deep[512];
    snprintf(deep, sizeof deep, "%s/no-directory/file.txt", root);
    assert(minyar_files_canonicalPathNative(text_of(deep))->byte_length == 0);
    assert(minyar_files_lastError() == -ENOENT);

    /* Identity: a hard link and a symbolic link agree with their target. */
    char second_name[512];
    snprintf(second_name, sizeof second_name, "%s/two.txt", root);
    assert(hard_link(path, second_name) == 0);
    MinyarBytes *one = minyar_files_identityNative(text_of(path));
    MinyarBytes *two = minyar_files_identityNative(text_of(second_name));
    MinyarBytes *through = minyar_files_identityNative(text_of(link));
    MinyarBytes *different = minyar_files_identityNative(text_of(other));
    assert(one->byte_length == 16 && two->byte_length == 16 && through->byte_length == 16);
    assert(memcmp((const void *)one->bytes, (const void *)two->bytes, 16) == 0);
    assert(memcmp((const void *)one->bytes, (const void *)through->bytes, 16) == 0);
    assert(different->byte_length == 16 && memcmp((const void *)one->bytes, (const void *)different->bytes, 16) != 0);
    assert(minyar_files_identityNative(text_of(missing))->byte_length == 0 && minyar_files_lastError() == -ENOENT);

    /* Temporary directories: private, distinct, and empty. */
    MinyarText *created = minyar_files_temporaryDirectoryNative(text_of("minyar-sys-"));
    MinyarText *another = minyar_files_temporaryDirectoryNative(text_of("minyar-sys-"));
    assert(created->byte_length > 11 && another->byte_length == created->byte_length);
    assert(memcmp((const void *)created->bytes, (const void *)another->bytes, (size_t)created->byte_length) != 0);
    char created_path[512], another_path[512];
    assert(created->byte_length < (long long)sizeof created_path);
    memcpy(created_path, (const void *)created->bytes, (size_t)created->byte_length);
    created_path[created->byte_length] = 0;
    memcpy(another_path, (const void *)another->bytes, (size_t)another->byte_length);
    another_path[another->byte_length] = 0;
    struct stat status;
    assert(stat(created_path, &status) == 0 && S_ISDIR(status.st_mode));
    assert((status.st_mode & 077) == 0); /* mkdtemp creates 0700 */
    assert(rmdir(created_path) == 0 && rmdir(another_path) == 0);
    assert(minyar_files_temporaryDirectoryNative(text_of(""))->byte_length == 0 && minyar_files_lastError() == -EINVAL);
    assert(minyar_files_temporaryDirectoryNative(text_of("with/slash"))->byte_length == 0 &&
           minyar_files_lastError() == -EINVAL);

    char command[600];
    snprintf(command, sizeof command, "rm -rf '%s'", root);
    assert(system(command) == 0);
}

int main(void) {
    crc32_vectors();
    crc64_vectors();
    base64_vectors();
    stdin_reader();
    stdin_overlong();
    files_calls();
    printf("Native checksum, standard-input and file-system calls passed\n");
    return 0;
}
