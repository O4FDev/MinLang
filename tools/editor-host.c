#ifndef _GNU_SOURCE
#define _GNU_SOURCE 1
#endif
#include "../runtime/minyar_native.h"
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>
#include <unistd.h>

static char *editor_path(const MinyarText *text) {
    if (!text || text->byte_length <= 0 || text->byte_length >= PATH_MAX ||
        memchr(text->bytes, 0, (size_t)text->byte_length)) return NULL;
    char *path = malloc((size_t)text->byte_length + 1);
    if (path) { memcpy(path, text->bytes, (size_t)text->byte_length); path[text->byte_length] = 0; }
    return path;
}
MinyarText *minyar_editorhost_kind(const MinyarText *text) {
    char *path = editor_path(text);
    struct stat info;
    char kind = '?';
    if (path && !lstat(path, &info)) kind = S_ISREG(info.st_mode) ? 'f' : S_ISDIR(info.st_mode) ? 'd' : 'o';
    free(path);
    return minyar_native_copy_text((const unsigned char *)&kind, 1);
}
long long minyar_editorhost_replace(const MinyarText *text, const MinyarBytes *before, const MinyarBytes *after) {
    char *path = editor_path(text);
    if (!path) return -EINVAL;
    struct stat info;
    int input = open(path, O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
    int error = 0;
    if (input < 0) { error = errno; free(path); return -error; }
    if (fstat(input, &info)) error = errno;
    else if (!S_ISREG(info.st_mode) || info.st_size != before->byte_length) error = EBUSY;
    unsigned char buffer[8192];
    long long offset = 0;
    while (!error && offset < before->byte_length) {
        size_t count = (size_t)(before->byte_length - offset);
        if (count > sizeof buffer) count = sizeof buffer;
        ssize_t got = read(input, buffer, count);
        if (got < 0 && errno == EINTR) continue;
        if (got <= 0 || memcmp(buffer, before->bytes + offset, (size_t)got)) { error = EBUSY; break; }
        offset += got;
    }
    close(input);
    char *temporary = malloc(strlen(path) + 24);
    if (!temporary) error = ENOMEM;
    int output = -1;
    if (!error) {
        sprintf(temporary, "%s.fmt.XXXXXXXX", path);
        output = mkstemp(temporary);
        if (output < 0) error = errno;
    }
    if (!error && fchmod(output, info.st_mode & 0777)) error = errno;
    offset = 0;
    while (!error && offset < after->byte_length) {
        ssize_t count = write(output, after->bytes + offset, (size_t)(after->byte_length - offset));
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) { error = count < 0 ? errno : EIO; break; }
        offset += count;
    }
    if (!error && fsync(output)) error = errno;
    if (output >= 0 && close(output) && !error) error = errno;
    struct stat current;
    if (!error && (lstat(path, &current) || current.st_dev != info.st_dev || current.st_ino != info.st_ino || current.st_size != info.st_size || current.st_mtime != info.st_mtime)) error = EBUSY;
    if (!error && rename(temporary, path)) error = errno;
    if (error && output >= 0) unlink(temporary);
    free(temporary);
    free(path);
    return -error;
}

static int editor_frame_error;
long long minyar_editorhost_frameError(void) { return editor_frame_error; }
static MinyarBytes *editor_empty(int error) { editor_frame_error = error; return minyar_bytes_new(0); }
MinyarBytes *minyar_editorhost_readFrame(void) {
    // LSP's ASCII headers end at CRLF CRLF; Content-Length counts UTF-8 bytes.
    char header[8193];
    size_t used = 0;
    int byte;
    while ((byte = fgetc(stdin)) != EOF) {
        if (used == sizeof header - 1) return editor_empty(EMSGSIZE);
        header[used++] = (char)byte;
        if (used >= 4 && !memcmp(header + used - 4, "\r\n\r\n", 4)) break;
    }
    if (!used && byte == EOF) return editor_empty(ferror(stdin) ? EIO : 0);
    if (byte == EOF) return editor_empty(EPROTO);
    header[used] = 0;
    size_t length = 0;
    bool found = false;
    char *line = header;
    while (*line) {
        char *end = strstr(line, "\r\n");
        if (!end) return editor_empty(EPROTO);
        *end = 0;
        if (!*line) break;
        if (!strncasecmp(line, "Content-Length:", 15)) {
            if (found) return editor_empty(EPROTO);
            char *digits = line + 15;
            while (*digits == ' ' || *digits == '\t') digits++;
            if (*digits < '0' || *digits > '9') return editor_empty(EPROTO);
            while (*digits >= '0' && *digits <= '9') {
                length = length * 10 + (unsigned)(*digits++ - '0');
                if (length > 16 * 1024 * 1024) return editor_empty(EMSGSIZE);
            }
            while (*digits == ' ' || *digits == '\t') digits++;
            if (*digits) return editor_empty(EPROTO);
            found = true;
        }
        line = end + 2;
    }
    if (!found || !length) return editor_empty(EPROTO);
    MinyarBytes *body = minyar_bytes_new((long long)length);
    size_t offset = 0;
    while (offset < length) {
        size_t count = fread((unsigned char *)body->bytes + offset, 1, length - offset, stdin);
        if (!count) { body->byte_length = 0; editor_frame_error = EPROTO; return body; }
        offset += count;
    }
    editor_frame_error = 0;
    return body;
}
