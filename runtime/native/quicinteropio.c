/* Test-fixture I/O only: no upstream protocol or secret storage. */
#include "../minyar_native.h"
static FILE *files[64];
static bool path_string(const MinyarText *text, char path[4096]) {
    if (text->byte_length < 1 || text->byte_length >= 4096 ||
        memchr(text->bytes, 0, (size_t)text->byte_length))
        return false;
    memcpy(path, text->bytes, (size_t)text->byte_length);
    path[text->byte_length] = 0;
    return true;
}
static long long open_file(const MinyarText *text, const char *mode) {
    char path[4096];
    if (!path_string(text, path))
        return -1;
    for (int i = 0; i < 64; i++)
        if (!files[i]) {
            files[i] = fopen(path, mode);
            return files[i] ? i + 1 : -1;
        }
    return -1;
}
long long minyar_quicinteropio_openRead(const MinyarText *path) {
    return open_file(path, "rb");
}
long long minyar_quicinteropio_openWrite(const MinyarText *path) {
    return open_file(path, "wb");
}
static FILE *file(long long handle) {
    return handle >= 1 && handle <= 64 ? files[handle - 1] : NULL;
}
long long minyar_quicinteropio_size(long long handle) {
    FILE *f = file(handle);
    if (!f)
        return -1;
    long at = ftell(f);
    if (at < 0 || fseek(f, 0, SEEK_END))
        return -1;
    long n = ftell(f);
    if (fseek(f, at, SEEK_SET))
        return -1;
    return n;
}
MinyarBytes *minyar_quicinteropio_read(long long handle, long long maximum) {
    FILE *f = file(handle);
    MinyarBytes *b = minyar_bytes_new(0);
    if (!f || maximum < 1 || maximum > 65536)
        return b;
    unsigned char data[65536];
    size_t n = fread(data, 1, (size_t)maximum, f);
    if (n)
        memcpy(minyar_bytes_extend(b, (long long)n), data, n);
    return b;
}
long long minyar_quicinteropio_write(long long handle, const MinyarBytes *data) {
    FILE *f = file(handle);
    if (!f || data->byte_length < 0 || data->byte_length > 65536)
        return -1;
    return (long long)fwrite(data->bytes, 1, (size_t)data->byte_length, f);
}
bool minyar_quicinteropio_close(long long handle) {
    FILE *f = file(handle);
    if (!f)
        return false;
    files[handle - 1] = NULL;
    return fclose(f) == 0;
}
bool minyar_quicinteropio_append(const MinyarText *path, const MinyarText *data) {
    char p[4096];
    if (!path_string(path, p) || data->byte_length < 0 || data->byte_length > 65536)
        return false;
    FILE *f = fopen(p, "ab");
    if (!f)
        return false;
    bool ok = fwrite(data->bytes, 1, (size_t)data->byte_length, f) == (size_t)data->byte_length;
    return fclose(f) == 0 && ok;
}
