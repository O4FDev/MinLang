/* Matched RTC comparator. Source-only; no compile or test result is asserted. */
/* BEGIN MATCHED PRODUCTION: declarations, decoder, reader, port adapter. */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

struct Calendar {
    int year;
    int month;
    int day;
    int hour;
    int minute;
    int second;
};

enum RtcError {
    RTC_OK = 0,
    RTC_INVALID_BYTE,
    RTC_INVALID_BCD,
    RTC_INVALID_CALENDAR,
    RTC_INVALID_ATTEMPTS,
    RTC_UPDATE_TIMEOUT,
    RTC_INVALID_READER
};

struct RtcResult {
    enum RtcError error;
    struct Calendar calendar;
};

typedef int64_t (*RtcReadRegister)(void *context, uint8_t register_index);

static struct RtcResult rtc_error(enum RtcError error) {
    struct RtcResult result = {error, {0, 0, 0, 0, 0, 0}};
    return result;
}

static bool rtc_byte(int64_t value) {
    return value >= 0 && value <= 255;
}

static bool rtc_number(int64_t raw, bool binary, int *value) {
    if (binary) {
        *value = (int)raw;
        return true;
    }
    int high = (int)raw / 16;
    int low = (int)raw % 16;
    if (high > 9 || low > 9) return false;
    *value = high * 10 + low;
    return true;
}

/* Raw fields and mode are signed so invalid callback/decoder values survive. */
struct RtcResult rtc_decode(int64_t status_b, int64_t raw_year,
                            int64_t raw_month, int64_t raw_day,
                            int64_t raw_hour, int64_t raw_minute,
                            int64_t raw_second) {
    if (!rtc_byte(status_b) || !rtc_byte(raw_year) || !rtc_byte(raw_month) ||
        !rtc_byte(raw_day) || !rtc_byte(raw_hour) || !rtc_byte(raw_minute) ||
        !rtc_byte(raw_second)) return rtc_error(RTC_INVALID_BYTE);

    bool binary = (status_b & 4) != 0;
    bool hour24 = (status_b & 2) != 0;
    bool pm = (raw_hour & 128) != 0;
    if (hour24 && pm) return rtc_error(RTC_INVALID_CALENDAR);
    raw_hour &= 127; /* Strip PM before examining BCD nibbles. */
    int year, month, day, hour, minute, second;
    if (!rtc_number(raw_year, binary, &year) ||
        !rtc_number(raw_month, binary, &month) ||
        !rtc_number(raw_day, binary, &day) ||
        !rtc_number(raw_hour, binary, &hour) ||
        !rtc_number(raw_minute, binary, &minute) ||
        !rtc_number(raw_second, binary, &second)) return rtc_error(RTC_INVALID_BCD);

    if (year > 99 || month < 1 || month > 12 || second > 59 || minute > 59)
        return rtc_error(RTC_INVALID_CALENDAR);
    if (hour24) {
        if (hour > 23) return rtc_error(RTC_INVALID_CALENDAR);
    } else {
        if (hour < 1 || hour > 12) return rtc_error(RTC_INVALID_CALENDAR);
        hour = hour % 12 + (pm ? 12 : 0);
    }
    year += 2000;
    bool leap = year % 4 == 0 && (year % 100 != 0 || year % 400 == 0);
    int days = month == 2 ? (leap ? 29 : 28) :
               ((month == 4 || month == 6 || month == 9 || month == 11) ? 30 : 31);
    if (day < 1 || day > days) return rtc_error(RTC_INVALID_CALENDAR);
    struct RtcResult result = {RTC_OK, {year, month, day, hour, minute, second}};
    return result;
}

static bool rtc_read_byte(RtcReadRegister read, void *context,
                          uint8_t register_index, uint8_t *value) {
    int64_t raw = read(context, register_index);
    if (!rtc_byte(raw)) return false;
    *value = (uint8_t)raw;
    return true;
}

/* Finite callback count, not a wall-clock deadline or a suspension proof. */
struct RtcResult rtc_read(RtcReadRegister read, void *context, int64_t attempts) {
    if (attempts < 1 || attempts > 1000000) return rtc_error(RTC_INVALID_ATTEMPTS);
    if (read == NULL) return rtc_error(RTC_INVALID_READER);
    for (int64_t attempt = 0; attempt < attempts; ++attempt) {
        uint8_t before, checked, after, status_a, status_b;
        uint8_t minute, hour, day, month, year;
        if (!rtc_read_byte(read, context, 0, &before) ||
            !rtc_read_byte(read, context, 10, &status_a)) return rtc_error(RTC_INVALID_BYTE);
        if ((status_a & 128) != 0) continue;
        if (!rtc_read_byte(read, context, 0, &checked)) return rtc_error(RTC_INVALID_BYTE);
        if (checked != before) continue;
        if (!rtc_read_byte(read, context, 11, &status_b) ||
            !rtc_read_byte(read, context, 2, &minute) ||
            !rtc_read_byte(read, context, 4, &hour) ||
            !rtc_read_byte(read, context, 7, &day) ||
            !rtc_read_byte(read, context, 8, &month) ||
            !rtc_read_byte(read, context, 9, &year) ||
            !rtc_read_byte(read, context, 10, &status_a)) return rtc_error(RTC_INVALID_BYTE);
        if ((status_a & 128) != 0) continue;
        if (!rtc_read_byte(read, context, 0, &after)) return rtc_error(RTC_INVALID_BYTE);
        if (after != before) continue;
        return rtc_decode(status_b, year, month, day, hour, minute, before);
    }
    return rtc_error(RTC_UPDATE_TIMEOUT);
}

/* BEGIN MATCHED PORT ADAPTER.
 * QEMU x86, bootstrap CPU before SMP, exclusive CMOS selector ownership.
 * Selecting with bit7 clear explicitly enables NMI; it does not restore a
 * guessed prior NMI state. No handler/NMI or other CPU may access CMOS here.
 * Only read-only calendar/status registers are accepted; never Register C.
 * Host tests use their supplied callback and MUST NOT call this function.
 */
int64_t rtc_cmos_read_port(void *context, uint8_t register_index) {
    (void)context;
    switch (register_index) {
        case 0: case 2: case 4: case 7: case 8: case 9: case 10: case 11: break;
        default: return -1;
    }
#if defined(__i386__) || defined(__x86_64__)
    uint8_t value;
    __asm__ volatile ("outb %0, %1" : : "a"(register_index), "Nd"((uint16_t)0x70) : "memory");
    __asm__ volatile ("inb %1, %0" : "=a"(value) : "Nd"((uint16_t)0x71) : "memory");
    return value;
#else
    return -1;
#endif
}
/* END MATCHED PORT ADAPTER. */
/* END MATCHED PRODUCTION. */

#ifdef RTC_COMPARATOR_CLI
/* BEGIN HOST WRAPPER: optional test-only transport/protocol, counted apart. */
#include <ctype.h>
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const char *rtc_cli_error(enum RtcError error) {
    switch (error) {
        case RTC_OK: return "ok";
        case RTC_INVALID_BYTE: return "invalid_byte";
        case RTC_INVALID_BCD: return "invalid_bcd";
        case RTC_INVALID_CALENDAR: return "invalid_calendar";
        case RTC_INVALID_ATTEMPTS: return "invalid_attempts";
        case RTC_UPDATE_TIMEOUT: return "update_timeout";
        case RTC_INVALID_READER: return "invalid_reader";
    }
    return "unknown_error";
}

static bool rtc_cli_integer(const char *text, int64_t *value) {
    char *end;
    errno = 0;
    intmax_t parsed = strtoimax(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0' ||
        parsed < INT64_MIN || parsed > INT64_MAX) return false;
    *value = (int64_t)parsed;
    return true;
}

/* 1 = integer, 0 = EOF, -1 = malformed token. No variable-sized buffer. */
static int rtc_cli_token(FILE *input, int64_t *value) {
    int character;
    do { character = fgetc(input); } while (character != EOF && isspace((unsigned char)character));
    if (character == EOF) return 0;
    char token[64];
    size_t length = 0;
    bool oversized = false;
    do {
        if (length < sizeof(token) - 1) token[length++] = (char)character;
        else oversized = true;
        character = fgetc(input);
    } while (character != EOF && !isspace((unsigned char)character));
    token[length] = '\0';
    return !oversized && rtc_cli_integer(token, value) ? 1 : -1;
}

struct RtcCliScript {
    uint64_t reads;
    const char *error;
};

static int64_t rtc_cli_read(void *context, uint8_t register_index) {
    struct RtcCliScript *script = context;
    printf("%s%u", script->reads == 0 ? "" : ",", (unsigned)register_index);
    script->reads++;
    int64_t expected, value;
    int register_token = rtc_cli_token(stdin, &expected);
    int value_token = rtc_cli_token(stdin, &value);
    if (register_token == 0 || value_token == 0) {
        script->error = "exhausted";
        return -1;
    }
    if (register_token < 0 || value_token < 0) {
        script->error = "bad_token";
        return -1;
    }
    if (expected != register_index) {
        script->error = "register_mismatch";
        return -1;
    }
    return value;
}

static void rtc_cli_result(struct RtcResult result) {
    printf("\"error\":\"%s\",\"calendar\":", rtc_cli_error(result.error));
    if (result.error == RTC_OK) {
        struct Calendar value = result.calendar;
        printf("[%d,%d,%d,%d,%d,%d]", value.year, value.month, value.day,
               value.hour, value.minute, value.second);
    } else {
        printf("null");
    }
}

static int rtc_cli_usage(void) {
    fputs("usage: rtc-comparator decode B YEAR MONTH DAY HOUR MINUTE SECOND\n"
          "       rtc-comparator read ATTEMPTS < register-value-pairs.txt\n", stderr);
    return 64;
}

int main(int argc, char **argv) {
    if (argc == 9 && strcmp(argv[1], "decode") == 0) {
        int64_t raw[7];
        for (int i = 0; i < 7; ++i) if (!rtc_cli_integer(argv[i + 2], &raw[i])) return rtc_cli_usage();
        struct RtcResult result = rtc_decode(raw[0], raw[1], raw[2], raw[3], raw[4], raw[5], raw[6]);
        printf("{");
        rtc_cli_result(result);
        puts("}");
        return 0;
    }
    if (argc == 3 && strcmp(argv[1], "read") == 0) {
        int64_t attempts;
        if (!rtc_cli_integer(argv[2], &attempts)) return rtc_cli_usage();
        struct RtcCliScript script = {0, "none"};
        printf("{\"trace\":[");
        struct RtcResult result = rtc_read(rtc_cli_read, &script, attempts);
        printf("],\"reads\":%" PRIu64 ",", script.reads);
        rtc_cli_result(result);
        printf(",\"script_error\":\"%s\"}\n", script.error);
        return strcmp(script.error, "none") == 0 ? 0 : 64;
    }
    return rtc_cli_usage();
}
/* END HOST WRAPPER. */
#endif
