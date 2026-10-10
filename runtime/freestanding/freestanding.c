/*
 * The C library subset the Minyar runtime needs when a program runs on bare
 * hardware with `--freestanding`, on x86-64 or 64-bit Arm. Standard output and
 * standard error go to the first serial port (the PC's COM1, or the PL011 of
 * QEMU's Arm virt board), the heap is the linker-provided region between
 * __heap_start and __heap_end, and exit() reports its status (to QEMU's
 * isa-debug-exit device on x86) and stops the machine. Everything the program
 * itself does is written in Minyar; this file only gives the language runtime
 * its footing.
 */
#include <stdarg.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

struct MinyarFile { int unused; };
static FILE serial_file;
FILE *stdin = &serial_file, *stdout = &serial_file, *stderr = &serial_file;

/* ----- Serial output ----- */

#if defined(__x86_64__)
static inline void port_out(unsigned short port, unsigned char value) {
    __asm__ volatile("outb %0, %1" : : "a"(value), "Nd"(port));
}
static inline unsigned char port_in(unsigned short port) {
    unsigned char value;
    __asm__ volatile("inb %1, %0" : "=a"(value) : "Nd"(port));
    return value;
}

static void serial_byte(unsigned char byte) {
    static int ready;
    if (!ready) {
        port_out(0x3F9, 0x00);
        port_out(0x3FB, 0x80);
        port_out(0x3F8, 0x01); /* 115200 baud */
        port_out(0x3F9, 0x00);
        port_out(0x3FB, 0x03);
        port_out(0x3FA, 0xC7);
        ready = 1;
    }
    for (int spins = 0; spins < 100000 && !(port_in(0x3FD) & 0x20); spins++) {}
    port_out(0x3F8, byte);
}
#elif defined(__aarch64__)
/* The PL011 UART of QEMU's virt board: wait while the transmit FIFO is full. */
#define UART 0x09000000UL
static void serial_byte(unsigned char byte) {
    volatile unsigned int *uart = (volatile unsigned int *)UART;
    for (int spins = 0; spins < 100000 && (uart[0x18 / 4] & 0x20); spins++) {}
    uart[0] = byte;
}
#else
#error "freestanding Minyar programs support x86-64 and 64-bit Arm"
#endif

size_t fwrite(const void *data, size_t size, size_t count, FILE *file) {
    (void)file;
    const unsigned char *bytes = data;
    for (size_t i = 0; i < size * count; i++) serial_byte(bytes[i]);
    return count;
}
int fputs(const char *text, FILE *file) { fwrite(text, 1, strlen(text), file); return 0; }
int fputc(int character, FILE *file) { (void)file; serial_byte((unsigned char)character); return character; }
int putchar(int character) { return fputc(character, stdout); }
int puts(const char *text) { fputs(text, stdout); serial_byte('\n'); return 0; }
int fflush(FILE *file) { (void)file; return 0; }
size_t fread(void *data, size_t size, size_t count, FILE *file) { (void)data; (void)size; (void)count; (void)file; return 0; }
FILE *fopen(const char *path, const char *mode) { (void)path; (void)mode; return NULL; }
int fclose(FILE *file) { (void)file; return 0; }
int fseek(FILE *file, long offset, int origin) { (void)file; (void)offset; (void)origin; return -1; }
long ftell(FILE *file) { (void)file; return -1; }
int fgetc(FILE *file) { (void)file; return EOF; }
int ferror(FILE *file) { (void)file; return 1; }

_Noreturn void exit(int status) {
    char line[48];
    int length = snprintf(line, sizeof(line), "\n[minyar exited with status %d]\n", status);
    fwrite(line, 1, (size_t)length, stdout);
#if defined(__x86_64__)
    port_out(0xF4, (unsigned char)status);
    for (;;) __asm__ volatile("cli; hlt");
#else
    /* PSCI SYSTEM_OFF; QEMU then exits. */
    register unsigned long function __asm__("x0") = 0x84000008;
    __asm__ volatile("hvc #0" : "+r"(function) : : "memory");
    for (;;) __asm__ volatile("msr daifset, #0xf; wfi");
#endif
}

#if defined(__aarch64__)
/* Called by the exception vectors in os/arch/arm64/head.S. */
_Noreturn void minyar_arm_exception(unsigned long kind, unsigned long syndrome, unsigned long address, unsigned long fault) {
    static const char *const kinds[4] = {"synchronous exception", "interrupt", "fast interrupt", "system error"};
    fprintf(stderr, "\nMinyar stopped: %s (vector %lu) at %#lx, ESR %#lx, FAR %#lx\n",
            kinds[kind & 3], kind, address, syndrome, fault);
    exit(1);
}
#endif
_Noreturn void abort(void) { exit(134); }
int atexit(void (*function)(void)) { (void)function; return 0; }

/* ----- Memory ----- */

typedef unsigned long long chunk __attribute__((vector_size(16), aligned(1)));

__attribute__((no_builtin)) void *memcpy(void *restrict destination, const void *restrict source, size_t count) {
    unsigned char *out = destination;
    const unsigned char *in = source;
    while (count >= 64) {
        chunk a = *(const chunk *)in, b = *(const chunk *)(in + 16);
        chunk c = *(const chunk *)(in + 32), d = *(const chunk *)(in + 48);
        *(chunk *)out = a; *(chunk *)(out + 16) = b;
        *(chunk *)(out + 32) = c; *(chunk *)(out + 48) = d;
        in += 64; out += 64; count -= 64;
    }
    while (count >= 16) { *(chunk *)out = *(const chunk *)in; in += 16; out += 16; count -= 16; }
    while (count--) *out++ = *in++;
    return destination;
}

__attribute__((no_builtin)) void *memmove(void *destination, const void *source, size_t count) {
    unsigned char *out = destination;
    const unsigned char *in = source;
    if (out == in || count == 0) return destination;
    if (out < in || out >= in + count) return memcpy(destination, source, count);
    out += count; in += count;
    while (count >= 16) { in -= 16; out -= 16; *(chunk *)out = *(const chunk *)in; count -= 16; }
    while (count--) *--out = *--in;
    return destination;
}

__attribute__((no_builtin)) void *memset(void *destination, int value, size_t count) {
    unsigned char *out = destination;
    unsigned long long byte = (unsigned char)value;
    unsigned long long word = byte * 0x0101010101010101ull;
    chunk fill = {word, word};
    while (count >= 16) { *(chunk *)out = fill; out += 16; count -= 16; }
    while (count--) *out++ = (unsigned char)value;
    return destination;
}

int memcmp(const void *left, const void *right, size_t count) {
    const unsigned char *a = left, *b = right;
    for (size_t i = 0; i < count; i++)
        if (a[i] != b[i]) return a[i] < b[i] ? -1 : 1;
    return 0;
}
size_t strlen(const char *text) { size_t n = 0; while (text[n]) n++; return n; }
void *memchr(const void *data, int value, size_t count) {
    const unsigned char *bytes = data;
    for (size_t i = 0; i < count; i++)
        if (bytes[i] == (unsigned char)value) return (void *)(bytes + i);
    return NULL;
}
char *strchr(const char *text, int character) {
    for (;; text++) {
        if (*text == (char)character) return (char *)text;
        if (!*text) return NULL;
    }
}
int atoi(const char *text) {
    int sign = 1, value = 0;
    while (*text == ' ') text++;
    if (*text == '-' || *text == '+') sign = *text++ == '-' ? -1 : 1;
    while (*text >= '0' && *text <= '9') value = value * 10 + (*text++ - '0');
    return sign * value;
}
int strcmp(const char *left, const char *right) {
    while (*left && *left == *right) { left++; right++; }
    return (unsigned char)*left - (unsigned char)*right;
}

/*
 * A size-class allocator: blocks are powers of two from 32 bytes, each with a
 * 16-byte header naming its class, and freed blocks wait on per-class lists.
 * Fresh blocks come from a bump pointer across the linker's heap region.
 */
extern unsigned char __heap_start[], __heap_end[];
enum { HEADER = 16, CLASSES = 40 };
typedef struct Block { struct Block *next; unsigned long long size_class; } Block;
static Block *free_blocks[CLASSES];
static unsigned char *heap_next;
static size_t heap_used;

static int class_for(size_t bytes) {
    size_t total = bytes + HEADER;
    int size_class = 5;
    while (((size_t)1 << size_class) < total) size_class++;
    return size_class;
}

void *malloc(size_t bytes) {
    int size_class = class_for(bytes);
    if (size_class >= CLASSES) return NULL;
    Block *block = free_blocks[size_class];
    if (block) {
        free_blocks[size_class] = block->next;
    } else {
        if (!heap_next) heap_next = (unsigned char *)(((uintptr_t)__heap_start + 63) & ~(uintptr_t)63);
        size_t size = (size_t)1 << size_class;
        if ((size_t)(__heap_end - heap_next) < size) return NULL;
        block = (Block *)heap_next;
        heap_next += size;
    }
    block->size_class = (unsigned long long)size_class;
    heap_used += (size_t)1 << size_class;
    return (unsigned char *)block + HEADER;
}

void free(void *pointer) {
    if (!pointer) return;
    Block *block = (Block *)((unsigned char *)pointer - HEADER);
    int size_class = (int)block->size_class;
    heap_used -= (size_t)1 << size_class;
    block->next = free_blocks[size_class];
    free_blocks[size_class] = block;
}

void *calloc(size_t count, size_t bytes) {
    if (bytes && count > (size_t)-1 / bytes) return NULL;
    void *pointer = malloc(count * bytes);
    if (pointer) memset(pointer, 0, count * bytes);
    return pointer;
}

void *realloc(void *pointer, size_t bytes) {
    if (!pointer) return malloc(bytes);
    Block *block = (Block *)((unsigned char *)pointer - HEADER);
    size_t capacity = ((size_t)1 << block->size_class) - HEADER;
    if (bytes <= capacity) return pointer;
    void *resized = malloc(bytes);
    if (!resized) return NULL;
    memcpy(resized, pointer, capacity);
    free(pointer);
    return resized;
}

/* Bytes of heap currently handed out, for the program's own diagnostics. */
long long minyar_freestanding_heap_used(void) { return (long long)heap_used; }

/* ----- Randomness ----- */

#if defined(__x86_64__)
/* randomBytes() on bare metal: the processor's RDRAND generator. */
void minyar_platform_random(unsigned char *out, size_t count) {
    while (count) {
        unsigned long long value;
        unsigned char ok = 0;
        for (int attempt = 0; attempt < 32 && !ok; attempt++)
            __asm__ volatile("rdrand %0; setc %1" : "=r"(value), "=qm"(ok));
        if (!ok) {
            fputs("Minyar stopped: the processor has no working RDRAND.\n", stderr);
            exit(1);
        }
        for (int i = 0; i < 8 && count; i++, count--) {
            *out++ = (unsigned char)value;
            value >>= 8;
        }
    }
}
#else
/* Arm processors without FEAT_RNG (such as Apple's M1) have no random
 * instruction, so the kernel fills this pool from a virtio entropy device; see
 * os/arch/arm64/head.S. Bytes are used from the end and never reused. */
extern struct { unsigned long long available; unsigned char bytes[4096]; } minyar_entropy;
void minyar_platform_random(unsigned char *out, size_t count) {
    if (count > minyar_entropy.available) {
        fputs("Minyar stopped: no entropy is available; give the machine a virtio-rng device.\n", stderr);
        exit(1);
    }
    while (count) {
        unsigned long long at = --minyar_entropy.available;
        *out++ = minyar_entropy.bytes[at];
        minyar_entropy.bytes[at] = 0;
        count--;
    }
}
#endif

/* ----- Number formatting ----- */

typedef struct { char *out; size_t capacity, length; } Sink;
static void put(Sink *sink, char character) {
    if (sink->length + 1 < sink->capacity) sink->out[sink->length] = character;
    sink->length++;
}
static void put_text(Sink *sink, const char *text) { while (*text) put(sink, *text++); }

static void put_unsigned(Sink *sink, unsigned long long value, unsigned base, int minimum) {
    char digits[32];
    int count = 0;
    do { digits[count++] = "0123456789abcdef"[value % base]; value /= base; } while (value);
    while (count < minimum) digits[count++] = '0';
    while (count) put(sink, digits[--count]);
}

/* Extended precision for decimal conversion. x86-64 has the x87's 80-bit
 * long double; on 64-bit Arm, long double is a 128-bit software type that
 * needs a compiler support library, so a value is instead the unevaluated sum
 * of two doubles (about 106 bits), kept exact with fused multiply-add. */
#if defined(__x86_64__)
typedef long double Wide;
static Wide wide_of(unsigned long long value) { return (Wide)value; }
static Wide wide_times(Wide a, Wide b) { return a * b; }
static Wide wide_scaled(Wide a, double b) { return a * b; }
static Wide wide_divided(Wide a, Wide b) { return a / b; }
static int wide_below(Wide a, double b) { return a < b; }
static int wide_floor(Wide a) { return (int)a; }
static Wide wide_minus(Wide a, int b) { return a - b; }
static Wide wide_one(double value) { return value; }
static double wide_value(Wide a) { return (double)a; }
#else
typedef struct { double high, low; } Wide;
static Wide wide_sum(double a, double b) {
    double sum = a + b, part = sum - a;
    return (Wide){sum, (a - (sum - part)) + (b - part)};
}
static Wide wide_normal(double high, double low) {
    double sum = high + low;
    return (Wide){sum, low - (sum - high)};
}
static Wide wide_of(unsigned long long value) {
    double high = (double)value;
    return (Wide){high, (double)(long long)(value - (unsigned long long)high)};
}
static Wide wide_times(Wide a, Wide b) {
    double product = a.high * b.high;
    double error = __builtin_elementwise_fma(a.high, b.high, -product) + (a.high * b.low + a.low * b.high);
    return wide_normal(product, error);
}
static Wide wide_scaled(Wide a, double b) { return wide_times(a, (Wide){b, 0}); }
static Wide wide_divided(Wide a, Wide b) {
    double first = a.high / b.high;
    Wide back = wide_times((Wide){first, 0}, b);
    Wide rest = wide_sum(a.high, -back.high);
    rest.low += a.low - back.low;
    double second = (rest.high + rest.low) / b.high;
    return wide_normal(first, second);
}
static int wide_below(Wide a, double b) { return a.high < b || (a.high == b && a.low < 0); }
/* The integer part of a non-negative value. */
static int wide_floor(Wide a) {
    int whole = (int)a.high;
    if ((double)whole > a.high || ((double)whole == a.high && a.low < 0)) whole--;
    return whole;
}
static Wide wide_minus(Wide a, int b) {
    Wide sum = wide_sum(a.high, -(double)b);
    return wide_normal(sum.high, sum.low + a.low);
}
static Wide wide_one(double value) { return (Wide){value, 0}; }
static double wide_value(Wide a) { return a.high + a.low; }
#endif

/* 10 to the power `n`, for 0 <= n <= 308. */
static Wide wide_power10(int n) {
    Wide scale = wide_one(10.0), result = wide_one(1.0);
    while (n) { if (n & 1) result = wide_times(result, scale); scale = wide_times(scale, scale); n >>= 1; }
    return result;
}

/* Scientific notation with `precision` digits after the point, rounded from
 * an extended-precision decimal expansion of the value. */
static void put_scientific(Sink *sink, double value, int precision) {
    if (value < 0 || (value == 0 && signbit(value))) { put(sink, '-'); value = -value; }
    if (precision > 30) precision = 30;
    Wide scaled = wide_one(value);
    int exponent = 0;
    if (value != 0) {
        while (!wide_below(scaled, 1e32)) { scaled = wide_divided(scaled, wide_power10(32)); exponent += 32; }
        while (!wide_below(scaled, 10.0)) { scaled = wide_divided(scaled, wide_one(10.0)); exponent++; }
        while (wide_below(scaled, 1e-31)) { scaled = wide_scaled(wide_scaled(scaled, 1e16), 1e16); exponent -= 32; }
        while (wide_below(scaled, 1.0)) { scaled = wide_scaled(scaled, 10.0); exponent--; }
    }
    char digits[40];
    for (int i = 0; i <= precision + 1; i++) {
        int digit = wide_floor(scaled);
        if (digit > 9) digit = 9;
        digits[i] = (char)('0' + digit);
        scaled = wide_scaled(wide_minus(scaled, digit), 10.0);
    }
    if (digits[precision + 1] >= '5') {
        int i = precision;
        while (i >= 0 && digits[i] == '9') digits[i--] = '0';
        if (i >= 0) digits[i]++;
        else { digits[0] = '1'; exponent++; }
    }
    put(sink, digits[0]);
    if (precision > 0) {
        put(sink, '.');
        for (int i = 1; i <= precision; i++) put(sink, digits[i]);
    }
    put(sink, 'e');
    put(sink, exponent < 0 ? '-' : '+');
    put_unsigned(sink, (unsigned long long)(exponent < 0 ? -exponent : exponent), 10, 2);
}

int vsnprintf(char *out, size_t capacity, const char *format, va_list arguments) {
    Sink sink = {out, capacity, 0};
    for (; *format; format++) {
        if (*format != '%') { put(&sink, *format); continue; }
        format++;
        int plus = 0, precision = -1, longs = 0;
        if (*format == '+') { plus = 1; format++; }
        if (*format == '.') {
            format++;
            if (*format == '*') { precision = va_arg(arguments, int); format++; }
            else { precision = 0; while (*format >= '0' && *format <= '9') precision = precision * 10 + (*format++ - '0'); }
        }
        while (*format == 'l' || *format == 'z') { longs++; format++; }
        switch (*format) {
        case 'd': case 'i': {
            long long value = longs ? va_arg(arguments, long long) : va_arg(arguments, int);
            if (value < 0) { put(&sink, '-'); put_unsigned(&sink, 0ull - (unsigned long long)value, 10, 1); }
            else { if (plus) put(&sink, '+'); put_unsigned(&sink, (unsigned long long)value, 10, 1); }
            break;
        }
        case 'u': put_unsigned(&sink, longs ? va_arg(arguments, unsigned long long) : va_arg(arguments, unsigned), 10, 1); break;
        case 'x': put_unsigned(&sink, longs ? va_arg(arguments, unsigned long long) : va_arg(arguments, unsigned), 16, 1); break;
        case 'p': put_text(&sink, "0x"); put_unsigned(&sink, (uintptr_t)va_arg(arguments, void *), 16, 1); break;
        case 's': put_text(&sink, va_arg(arguments, const char *)); break;
        case 'c': put(&sink, (char)va_arg(arguments, int)); break;
        case 'e': put_scientific(&sink, va_arg(arguments, double), precision < 0 ? 6 : precision); break;
        case 'g': put_scientific(&sink, va_arg(arguments, double), 16); break;
        case '%': put(&sink, '%'); break;
        default: put(&sink, '%'); put(&sink, *format); break;
        }
    }
    if (capacity) out[sink.length < capacity ? sink.length : capacity - 1] = 0;
    return (int)sink.length;
}

int snprintf(char *out, size_t capacity, const char *format, ...) {
    va_list arguments;
    va_start(arguments, format);
    int length = vsnprintf(out, capacity, format, arguments);
    va_end(arguments);
    return length;
}

int fprintf(FILE *file, const char *format, ...) {
    char buffer[512];
    va_list arguments;
    va_start(arguments, format);
    int length = vsnprintf(buffer, sizeof(buffer), format, arguments);
    va_end(arguments);
    fwrite(buffer, 1, (size_t)(length < (int)sizeof(buffer) ? length : (int)sizeof(buffer) - 1), file);
    return length;
}

int printf(const char *format, ...) {
    char buffer[512];
    va_list arguments;
    va_start(arguments, format);
    int length = vsnprintf(buffer, sizeof(buffer), format, arguments);
    va_end(arguments);
    fwrite(buffer, 1, (size_t)(length < (int)sizeof(buffer) ? length : (int)sizeof(buffer) - 1), stdout);
    return length;
}

double strtod(const char *text, char **end) {
    const char *at = text;
    while (*at == ' ' || *at == '\t' || *at == '\n') at++;
    int negative = 0;
    if (*at == '-' || *at == '+') negative = *at++ == '-';
    unsigned long long mantissa = 0;
    int digits = 0, exponent = 0, any = 0;
    for (; *at >= '0' && *at <= '9'; at++, any = 1) {
        if (digits < 19) { mantissa = mantissa * 10 + (unsigned long long)(*at - '0'); if (mantissa) digits++; }
        else exponent++;
    }
    if (*at == '.') {
        at++;
        for (; *at >= '0' && *at <= '9'; at++, any = 1) {
            if (digits < 19) { mantissa = mantissa * 10 + (unsigned long long)(*at - '0'); if (mantissa) digits++; exponent--; }
        }
    }
    if (any && (*at == 'e' || *at == 'E')) {
        const char *mark = at++;
        int sign = 1, power = 0, seen = 0;
        if (*at == '-' || *at == '+') sign = *at++ == '-' ? -1 : 1;
        for (; *at >= '0' && *at <= '9'; at++, seen = 1) if (power < 10000) power = power * 10 + (*at - '0');
        if (seen) exponent += sign * power; else at = mark;
    }
    if (end) *end = (char *)(any ? at : text);
    double result = 0;
    if (mantissa != 0 && exponent > 330) {
        result = __builtin_inf();
    } else if (mantissa != 0 && exponent >= -400) {
        Wide value = wide_of(mantissa);
        while (exponent < -300) { value = wide_divided(value, wide_power10(300)); exponent += 300; }
        value = exponent < 0 ? wide_divided(value, wide_power10(-exponent)) : wide_times(value, wide_power10(exponent));
        result = wide_value(value);
    }
    return negative ? -result : result;
}

/* ----- Mathematics ----- */

double fabs(double x) { return __builtin_fabs(x); }
double sqrt(double x) { return __builtin_sqrt(x); }
double trunc(double x) {
    if (!(fabs(x) < 4503599627370496.0)) return x;
    return (double)(long long)x;
}
double floor(double x) { double t = trunc(x); return t > x ? t - 1.0 : t; }
double ceil(double x) { double t = trunc(x); return t < x ? t + 1.0 : t; }
double round(double x) { return x < 0 ? -floor(-x + 0.5) : floor(x + 0.5); }
double fmod(double x, double y) {
    if (y == 0 || isnan(x) || isnan(y) || isinf(x)) return NAN;
    return x - trunc(x / y) * y;
}
double ldexp(double x, int exponent) {
    while (exponent > 1000) { x *= 0x1p1000; exponent -= 1000; }
    while (exponent < -1000) { x *= 0x1p-1000; exponent += 1000; }
    union { double d; unsigned long long u; } scale = {.u = (unsigned long long)(exponent + 1023) << 52};
    return x * scale.d;
}
double frexp(double x, int *exponent) {
    union { double d; unsigned long long u; } bits = {x};
    int e = (int)((bits.u >> 52) & 0x7FF);
    if (e == 0) { if (x == 0) { *exponent = 0; return x; } x *= 0x1p64; bits.d = x; e = (int)((bits.u >> 52) & 0x7FF) - 64; }
    else if (e == 0x7FF) { *exponent = 0; return x; }
    *exponent = e - 1022;
    bits.u = (bits.u & ~(0x7FFull << 52)) | (1022ull << 52);
    return bits.d;
}

static const double PI = 3.14159265358979323846;

/* sin and cos on [-pi/4, pi/4] by Taylor series, after reducing by pi/2. */
static double sin_kernel(double x) {
    double x2 = x * x;
    return x * (1 - x2 / 6 * (1 - x2 / 20 * (1 - x2 / 42 * (1 - x2 / 72 * (1 - x2 / 110 * (1 - x2 / 156))))));
}
static double cos_kernel(double x) {
    double x2 = x * x;
    return 1 - x2 / 2 * (1 - x2 / 12 * (1 - x2 / 30 * (1 - x2 / 56 * (1 - x2 / 90 * (1 - x2 / 132 * (1 - x2 / 182))))));
}
static double trig(double x, int cosine) {
    if (isnan(x) || isinf(x)) return NAN;
    double quadrant = round(x / (PI / 2));
    double r = (x - quadrant * 1.5707963267341256) - quadrant * 6.077100506506192e-11;
    long long q = ((long long)fmod(quadrant, 4.0) + 4 + cosine) & 3;
    switch (q) {
    case 0: return sin_kernel(r);
    case 1: return cos_kernel(r);
    case 2: return -sin_kernel(r);
    default: return -cos_kernel(r);
    }
}
double sin(double x) { return trig(x, 0); }
double cos(double x) { return trig(x, 1); }
double tan(double x) { return sin(x) / cos(x); }

double atan(double x) {
    if (isnan(x)) return x;
    int negative = x < 0;
    if (negative) x = -x;
    int inverted = x > 1;
    if (inverted) x = 1 / x;
    /* Halve the angle twice so the series converges quickly. */
    double y = x / (1 + sqrt(1 + x * x));
    y = y / (1 + sqrt(1 + y * y));
    double y2 = y * y, term = y, sum = 0;
    for (int n = 1; n < 40; n += 2) { sum += term / n; term *= -y2; }
    double result = 4 * sum;
    if (inverted) result = PI / 2 - result;
    return negative ? -result : result;
}
double atan2(double y, double x) {
    if (isnan(x) || isnan(y)) return NAN;
    if (x > 0) return atan(y / x);
    if (x < 0) return y >= 0 ? atan(y / x) + PI : atan(y / x) - PI;
    if (y > 0) return PI / 2;
    if (y < 0) return -PI / 2;
    return signbit(x) ? (signbit(y) ? -PI : PI) : y;
}
double asin(double x) { if (x > 1 || x < -1) return NAN; return atan2(x, sqrt(1 - x * x)); }
double acos(double x) { if (x > 1 || x < -1) return NAN; return atan2(sqrt(1 - x * x), x); }

double exp(double x) {
    if (isnan(x)) return x;
    if (x > 709.8) return INFINITY;
    if (x < -745.2) return 0;
    double k = round(x / 0.6931471805599453);
    double r = x - k * 0.6931471805599453;
    double term = 1, sum = 1;
    for (int n = 1; n < 24; n++) { term *= r / n; sum += term; }
    return ldexp(sum, (int)k);
}
double log(double x) {
    if (isnan(x) || x < 0) return NAN;
    if (x == 0) return -INFINITY;
    if (isinf(x)) return x;
    int exponent;
    double m = frexp(x, &exponent); /* x = m * 2^exponent, m in [0.5, 1) */
    if (m < 0.70710678118654752) { m *= 2; exponent--; }
    double s = (m - 1) / (m + 1), s2 = s * s, term = s, sum = 0;
    for (int n = 1; n < 60; n += 2) { sum += term / n; term *= s2; }
    return 2 * sum + exponent * 0.6931471805599453;
}
double pow(double base, double power) {
    if (power == 0) return 1;
    if (isnan(base) || isnan(power)) return NAN;
    if (power == trunc(power) && fabs(power) < 1e9) {
        long long n = (long long)power;
        double result = 1, factor = base;
        unsigned long long remaining = n < 0 ? 0ull - (unsigned long long)n : (unsigned long long)n;
        while (remaining) { if (remaining & 1) result *= factor; factor *= factor; remaining >>= 1; }
        return n < 0 ? 1 / result : result;
    }
    if (base < 0) return NAN;
    if (base == 0) return power > 0 ? 0 : INFINITY;
    return exp(power * log(base));
}
