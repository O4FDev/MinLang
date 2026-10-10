/* RFC8032 section7.1 vector and adversarial mutation matrix, actual nativeABI. */
#include "../runtime/minyar_native.h"
#include <assert.h>
#include <stdio.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#endif

void minyar_rc_release(void *);
static const char *fault;
void minyar_update_test_hook(const char *point) {
    if (fault && strcmp(fault, point) == 0) {
#ifdef _WIN32
        ExitProcess(87);
#else
        _exit(87);
#endif
    }
}

extern bool minyar_update_verify(const MinyarBytes *, const MinyarBytes *, const MinyarBytes *);
extern long long minyar_update_begin(const MinyarText *);
extern MinyarBytes *minyar_update_readState(long long);
extern bool minyar_update_storeState(long long, const MinyarBytes *);
extern bool minyar_update_activate(long long, const MinyarText *, const MinyarBytes *,
                                   const MinyarBytes *);
extern void minyar_update_end(long long);

static MinyarBytes *hex(const char *source) {
    MinyarBytes *b = minyar_bytes_new((long long)strlen(source) / 2);
    for (long long i = 0; i < b->byte_length; i++) {
        unsigned int value;
        assert(sscanf(source + i * 2, "%2x", &value) == 1);
        ((unsigned char *)b->bytes)[i] = (unsigned char)value;
    }
    return b;
}

int main(int argc, char **argv) {
    assert(argc == 2 || argc == 3);
    if (argc == 3) {
        MinyarText *root =
            minyar_native_copy_text((const unsigned char *)argv[1], (long long)strlen(argv[1]));
        long long handle = minyar_update_begin(root);
        assert(handle > 0);
        if (strcmp(argv[2], "reopen") == 0) {
            MinyarBytes *value = minyar_update_readState(handle);
            fwrite(value->bytes, 1, (size_t)value->byte_length, stdout);
            minyar_rc_release(value);
        } else {
            MinyarText *old_digest = minyar_native_copy_text(
                (const unsigned char
                     *)"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                64);
            MinyarText *new_digest = minyar_native_copy_text(
                (const unsigned char
                     *)"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                64);
            MinyarBytes *old = minyar_native_copy_text((const unsigned char *)"old", 3);
            MinyarBytes *next = minyar_native_copy_text((const unsigned char *)"new", 3);
            assert(minyar_update_activate(handle, old_digest, old, old));
            fault = argv[2];
            assert(minyar_update_activate(handle, new_digest, next, next));
            minyar_rc_release(old_digest);
            minyar_rc_release(new_digest);
            minyar_rc_release(old);
            minyar_rc_release(next);
        }
        minyar_update_end(handle);
        minyar_rc_release(root);
        return 0;
    }
    MinyarBytes *pk = hex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a");
    MinyarBytes *sig = hex("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821"
                           "590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b");
    MinyarBytes *message = minyar_bytes_new(0);
    assert(minyar_update_verify(message, sig, pk));
    for (long long i = 0; i < 64; i++) {
        ((unsigned char *)sig->bytes)[i] ^= 1;
        assert(!minyar_update_verify(message, sig, pk));
        ((unsigned char *)sig->bytes)[i] ^= 1;
    }
    for (long long i = 0; i < 32; i++) {
        ((unsigned char *)pk->bytes)[i] ^= 1;
        assert(!minyar_update_verify(message, sig, pk));
        ((unsigned char *)pk->bytes)[i] ^= 1;
    }
    for (long long n = 0; n < 80; n++) {
        MinyarBytes *bad = minyar_bytes_new(n);
        if (n != 64)
            assert(!minyar_update_verify(message, bad, pk));
        if (n != 32)
            assert(!minyar_update_verify(message, sig, bad));
        minyar_rc_release(bad);
    }
    MinyarBytes *large = minyar_bytes_new(8193);
    assert(!minyar_update_verify(large, sig, pk));
    minyar_rc_release(large);
    MinyarText *root =
        minyar_native_copy_text((const unsigned char *)argv[1], (long long)strlen(argv[1]));
    long long handle = minyar_update_begin(root);
    assert(handle > 0);
    assert(minyar_update_begin(root) < 0); /* no concurrent update, no stale-lock race */
    MinyarBytes *read = minyar_update_readState(handle);
    assert(read->byte_length == 0);
    minyar_rc_release(read);
    MinyarBytes *state = minyar_native_copy_text((const unsigned char *)"durable floor 12", 16);
    assert(minyar_update_storeState(handle, state));
    read = minyar_update_readState(handle);
    assert(read->byte_length == 16);
    minyar_rc_release(read);
    MinyarText *digest = minyar_native_copy_text(
        (const unsigned char *)"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        64);
    MinyarBytes *artifact = minyar_native_copy_text((const unsigned char *)"fixture binary", 14);
    assert(minyar_update_activate(handle, digest, artifact, state));
    assert(minyar_update_activate(handle, digest, artifact,
                                  state)); /* retry after interrupted pointer activation */
    MinyarText *bad_path = minyar_native_copy_text((const unsigned char *)"../../escape", 12);
    assert(!minyar_update_activate(handle, bad_path, artifact, state));
    minyar_rc_release(bad_path);
    minyar_update_end(handle);
    handle = minyar_update_begin(root);
    assert(handle > 0);
    read = minyar_update_readState(handle);
    assert(read->byte_length == 16);
    minyar_rc_release(read);
    minyar_update_end(handle);
    minyar_rc_release(pk);
    minyar_rc_release(sig);
    minyar_rc_release(message);
    minyar_rc_release(root);
    minyar_rc_release(state);
    minyar_rc_release(digest);
    minyar_rc_release(artifact);
    puts("Ed25519 mutation and durable activation contracts passed");
    return 0;
}
