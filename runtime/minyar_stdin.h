/* io.readLine: buffered, UTF-8-preserving line reads from standard input.
 *
 * The reader keeps one process-wide buffer, so only one thread may read
 * standard input at a time; io.readLine is not a `parallel function`.
 * A line is everything up to and including the next '\n'; the terminator is
 * dropped and one trailing '\r' before it is dropped too, so both LF and CRLF
 * input yield the same Text. End of input after at least one byte returns the
 * final unterminated line, and only an empty read at end of input reports the
 * end. Bytes are copied into the result exactly once per buffer fill and no
 * per-byte allocation happens.
 *
 * A line longer than MINYAR_STDIN_MAXIMUM_LINE bytes is MINYAR_STDIN_TOO_LONG:
 * the reader never silently truncates, it discards the remainder of that line,
 * and the next call reads the line after it. The marker is a private negative
 * value rather than -EOVERFLOW, whose number differs between platforms.
 * Invalid UTF-8 is reported by io.readLine's Text decoding, which sees the raw
 * bytes of a whole line. */

#include <errno.h>

#define MINYAR_STDIN_TOO_LONG (-1000001)
#define MINYAR_STDIN_MAXIMUM_LINE (1 << 20)
#define MINYAR_STDIN_BUFFER (1 << 16)

static unsigned char minyar_stdin_buffer[MINYAR_STDIN_BUFFER];
static long long minyar_stdin_start, minyar_stdin_end;

#if defined(__STDC_HOSTED__) && __STDC_HOSTED__
#if defined(_WIN32)
#include <io.h>
#include <stdio.h>
static long long stdin_read_bytes(unsigned char *buffer, size_t count) {
    int got = _read(_fileno(stdin), buffer, (unsigned int)count);
    return got < 0 ? -(long long)errno : (long long)got;
}
#else
#include <unistd.h>
static long long stdin_read_bytes(unsigned char *buffer, size_t count) {
    for (;;) {
        ssize_t got = read(0, buffer, count);
        if (got >= 0) return (long long)got;
        if (errno != EINTR) return -(long long)errno;
    }
}
#endif
#else
static long long stdin_read_bytes(unsigned char *buffer, size_t count) {
    (void)buffer;
    (void)count;
    return -38; /* ENOSYS: a freestanding program has no standard input */
}
#endif

/* Fill the buffer. Returns the bytes read, 0 at end of input, or -errno. */
static long long minyar_stdin_fill(void) {
    minyar_stdin_start = 0;
    minyar_stdin_end = 0;
    long long got = stdin_read_bytes(minyar_stdin_buffer, sizeof(minyar_stdin_buffer));
    if (got <= 0) return got;
    minyar_stdin_end = got;
    return got;
}

/* Discard buffered input through the next newline, refilling as needed, so a
 * rejected over-long line does not leave the reader inside it. */
static void minyar_stdin_skip_line(void) {
    for (;;) {
        if (minyar_stdin_start < minyar_stdin_end) {
            const unsigned char *base = minyar_stdin_buffer + minyar_stdin_start;
            size_t available = (size_t)(minyar_stdin_end - minyar_stdin_start);
            const unsigned char *newline = memchr(base, '\n', available);
            if (newline) {
                minyar_stdin_start += (long long)(newline - base) + 1;
                return;
            }
            minyar_stdin_start = minyar_stdin_end;
        }
        if (minyar_stdin_fill() <= 0) return;
    }
}

/* io.readLine's native half: a record whose data field holds the line and
 * whose code field is 0 for a line (possibly empty), 1 at end of input,
 * MINYAR_STDIN_TOO_LONG for an over-long line, and -errno for a read failure. */
MinyarRecord *minyar_runtime_readLineOutcome(void) {
    MinyarBytes *line = minyar_bytes_new(0);
    long long code = 1;
    for (;;) {
        if (minyar_stdin_start < minyar_stdin_end) {
            const unsigned char *base = minyar_stdin_buffer + minyar_stdin_start;
            size_t available = (size_t)(minyar_stdin_end - minyar_stdin_start);
            const unsigned char *newline = memchr(base, '\n', available);
            size_t take = newline ? (size_t)(newline - base) : available;
            if (line->byte_length + (long long)take > MINYAR_STDIN_MAXIMUM_LINE) {
                minyar_stdin_skip_line();
                code = MINYAR_STDIN_TOO_LONG;
                break;
            }
            if (take) memcpy(minyar_bytes_extend(line, (long long)take), base, take);
            minyar_stdin_start += (long long)take;
            if (newline) {
                minyar_stdin_start += 1;
                code = 0;
                break;
            }
        }
        long long got = minyar_stdin_fill();
        if (got == 0) {
            /* End of input: the bytes collected so far are the last line. */
            code = line->byte_length > 0 ? 0 : 1;
            break;
        }
        if (got < 0) {
            code = got;
            break;
        }
    }
    if (code == 0 && line->byte_length > 0 &&
        ((const unsigned char *)line->bytes)[line->byte_length - 1] == '\r') {
        line->byte_length -= 1;
    }
    MinyarRecord *record = minyar_record_new(2);
    minyar_record_set_take(record, 0, (long long)(intptr_t)line);
    minyar_record_set(record, 1, code);
    return record;
}
