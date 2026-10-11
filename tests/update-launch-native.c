/* Fault injection only operates on locally compiled, signed owned fixtures. */
#include "../runtime/minyar_native.h"
#include "../vendor/monocypher/monocypher-ed25519.h"
#include <assert.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#include <sys/stat.h>
#endif
extern long long minyar_update_begin(const MinyarText *);
extern void minyar_update_end(long long);
extern bool minyar_update_activateChecked(long long, const MinyarText *, const MinyarBytes *,
                                          const MinyarBytes *, const MinyarText *,
                                          const MinyarBytes *);
extern long long minyar_update_launchChecked(long long, const MinyarText *, const MinyarBytes *,
                                             const MinyarBytes *, bool);
extern long long minyar_update_waitChild(long long);
extern MinyarText *minyar_update_lastError(void);
extern bool minyar_update_verify(const MinyarBytes *, const MinyarBytes *, const MinyarBytes *);
extern void minyar_rc_release(void *);
static const char *fault, *mutation, *action;

void minyar_update_test_hook(const char *point) {
    if (fault && strcmp(point, fault) == 0) {
#ifdef _WIN32
        ExitProcess(87);
#else
        _exit(87);
#endif
    }
    if (!mutation || strcmp(point, "launch-before-exec"))
        return;
    if (!strcmp(action, "ancestor") || !strcmp(action, "parent") ||
        !strcmp(action, "anchored-parent")) {
        char moved[4096];
        assert(snprintf(moved, sizeof(moved), "%s.moved", mutation) < (int)sizeof(moved));
        if (rename(mutation, moved))
            puts("MUTATION-BLOCKED");
        else
            puts("ANCESTOR-RENAMED");
        return;
    }
    if (!strcmp(action, "replace")) {
#ifdef _WIN32
        int removed = remove(mutation);
#else
        int removed = unlink(mutation);
#endif
        if (removed) {
            puts("MUTATION-BLOCKED");
            return;
        }
    }
#ifndef _WIN32
    if (!strcmp(action, "write"))
        assert(chmod(mutation, 0600) == 0);
#endif
    FILE *stream = fopen(mutation, "wb");
    if (!stream) {
        puts("MUTATION-BLOCKED");
        return;
    }
    assert(fwrite("changed owned fixture", 1, 21, stream) == 21);
    assert(fclose(stream) == 0);
    puts("MUTATED");
}
static MinyarText *text(const char *source) {
    return minyar_native_copy_text((const unsigned char *)source, (long long)strlen(source));
}
static MinyarBytes *file(const char *path) {
    FILE *stream = fopen(path, "rb");
    assert(stream);
    MinyarBytes *bytes = minyar_bytes_new(0);
    unsigned char buffer[65536];
    size_t count;
    while ((count = fread(buffer, 1, sizeof(buffer), stream))) {
        assert(bytes->byte_length + (long long)count <= 134217728);
        memcpy(minyar_bytes_extend(bytes, (long long)count), buffer, count);
    }
    assert(!ferror(stream));
    assert(fclose(stream) == 0);
    return bytes;
}
int main(int argc, char **argv) {
    assert(argc == 10);
    MinyarText *root = text(argv[1]), *digest = text(argv[4]), *hash = text(argv[5]);
    long long ancestor = -1;
    if (!strcmp(argv[7], "anchored-parent")) {
        MinyarText *parent = text(argv[9]);
        ancestor = minyar_update_begin(parent);
        minyar_rc_release(parent);
        assert(ancestor >= 0);
    }
    long long handle = minyar_update_begin(root);
    if (handle < 0) {
        puts("ERROR");
        MinyarText *message = minyar_update_lastError();
        fwrite(message->bytes, 1, (size_t)message->byte_length, stdout);
        putchar('\n');
        minyar_rc_release(message);
        minyar_rc_release(root);
        minyar_rc_release(digest);
        minyar_rc_release(hash);
        if (ancestor >= 0)
            minyar_update_end(ancestor);
        return 0;
    }
    if (!strcmp(argv[7], "hold")) {
        puts("LOCKED");
        fflush(stdout);
#ifdef _WIN32
        Sleep(2000);
#else
        sleep(2);
#endif
        minyar_update_end(handle);
        minyar_rc_release(root);
        minyar_rc_release(digest);
        minyar_rc_release(hash);
        return 0;
    }
    MinyarBytes *artifact = file(argv[2]), *receipt = file(argv[3]), *state = file(argv[6]);
    assert(receipt->byte_length > 64);
    MinyarBytes signature = {receipt->bytes, 64, 64, NULL, NULL};
    static const unsigned char domain[] = "MINYAR-UPDATE-SIGNATURE-V1";
    MinyarBytes *signed_bytes = minyar_bytes_new(0);
    memcpy(minyar_bytes_extend(signed_bytes, sizeof(domain)), domain, sizeof(domain));
    memcpy(minyar_bytes_extend(signed_bytes, receipt->byte_length - 64), receipt->bytes + 64,
           (size_t)receipt->byte_length - 64);
    static const unsigned char public_key[32] = {0xd7, 0x5a, 0x98, 0x01, 0x82, 0xb1, 0x0a, 0xb7,
                                                 0xd5, 0x4b, 0xfe, 0xd3, 0xc9, 0x64, 0x07, 0x3a,
                                                 0x0e, 0xe1, 0x72, 0xf3, 0xda, 0xa6, 0x23, 0x25,
                                                 0xaf, 0x02, 0x1a, 0x68, 0xf7, 0x07, 0x51, 0x1a};
    MinyarBytes key = {public_key, 32, 32, NULL, NULL};
    assert(minyar_update_verify(signed_bytes, &signature, &key));
    fault = *argv[8] ? argv[8] : NULL;
    action = argv[7];
    mutation = *argv[9] ? argv[9] : NULL;
    if (!strcmp(action, "install")) {
        bool ok = minyar_update_activateChecked(handle, digest, artifact, receipt, hash, state);
        puts(ok ? "ACTIVATED" : "ERROR");
    } else {
        unsigned char args[] = {'s', 'a', 'f', 'e', 0, 0};
        MinyarBytes arguments = {args, sizeof(args), sizeof(args), NULL, NULL};
        long long child = minyar_update_launchChecked(handle, digest, artifact, &arguments, false);
        if (child < 0)
            puts("ERROR");
        else {
            long long result = minyar_update_waitChild(child);
            assert(result == 23);
            assert(minyar_update_waitChild(child) < 0);
            puts("WAITED:23");
        }
    }
    minyar_update_end(handle);
    if (ancestor >= 0)
        minyar_update_end(ancestor);
    minyar_rc_release(root);
    minyar_rc_release(digest);
    minyar_rc_release(hash);
    minyar_rc_release(artifact);
    minyar_rc_release(receipt);
    minyar_rc_release(state);
    minyar_rc_release(signed_bytes);
    return 0;
}
