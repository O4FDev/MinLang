/* Runtime implementation fragment; included once by minyar_runtime.c. */

/* Unconditional failure ABI lets generated checks expose their success path
 * to LLVM without making assumptions about a conditional C function. */
MINYAR_COLD MINYAR_NORETURN void minyar_fail_integer_overflow(void) {
    fputs("Minyar stopped: this Integer calculation is outside the supported range.\n", stderr);
    exit(1);
}

void minyar_check_integer_overflow(_Bool overflowed) {
    if (overflowed)
        minyar_fail_integer_overflow();
}

static MINYAR_COLD MINYAR_NORETURN void integer_division_stop(const char *message) {
    fputs("Minyar stopped: ", stderr);
    fputs(message, stderr);
    fputc('\n', stderr);
    exit(1);
}

MINYAR_COLD MINYAR_NORETURN void minyar_fail_integer_division(long long right) {
    integer_division_stop(right == 0 ? "an Integer cannot be divided by zero."
                                     : "this Integer division is outside the supported range.");
}

void minyar_check_integer_division(long long left, long long right) {
    if (right == 0 || (left == LLONG_MIN && right == -1))
        minyar_fail_integer_division(right);
}

/* Float text uses the shortest decimal digits that read back as the same
 * value. Plain notation is used for ordinary magnitudes and always keeps a
 * point, so a printed Float cannot be mistaken for an Integer. */
static _Bool adjacent_float_decimal(char *scientific, double value, int direction) {
    char candidate[40];
    memcpy(candidate, scientific, strlen(scientific) + 1);
    char *first = candidate + (*candidate == '-');
    char *exponent_start = strchr(candidate, 'e');
    int exponent = atoi(exponent_start + 1);
    _Bool carried = 1;
    for (char *digit = exponent_start; digit > first;) {
        digit--;
        if (*digit == '.')
            continue;
        if (direction > 0) {
            if (*digit < '9') {
                (*digit)++;
                carried = 0;
                break;
            }
            *digit = '0';
        } else {
            if (*digit > '0') {
                (*digit)--;
                carried = 0;
                break;
            }
            *digit = '9';
        }
    }
    if (carried) {
        /* 9.99 -> 1.00e+1: preserve the significant-digit budget. */
        *first = '1';
        exponent++;
    } else if (*first == '0') {
        /* 1.00 -> 9.99e-1: the grid becomes finer below a decimal power. */
        for (char *digit = first; digit < exponent_start; digit++)
            if (*digit != '.')
                *digit = '9';
        exponent--;
    }
    snprintf(exponent_start, sizeof(candidate) - (size_t)(exponent_start - candidate), "e%+d",
             exponent);
    if (strtod(candidate, NULL) != value)
        return 0;
    memcpy(scientific, candidate, strlen(candidate) + 1);
    return 1;
}

static size_t format_float(double value, char *out, size_t capacity) {
    if (isnan(value))
        return (size_t)snprintf(out, capacity, "NaN");
    if (isinf(value))
        return (size_t)snprintf(out, capacity, value < 0 ? "-Infinity" : "Infinity");
    if (value == 0)
        return (size_t)snprintf(out, capacity, signbit(value) ? "-0.0" : "0.0");
    /* Every integer strictly inside +/-2^53 is exact and its decimal integer
     * spelling already has the fewest significant digits. All are within our
     * plain-notation range; avoid scientific formatting and reparsing. */
    if (value > -9007199254740992.0 && value < 9007199254740992.0) {
        long long integer = (long long)value;
        if ((double)integer == value)
            return (size_t)snprintf(out, capacity, "%lld.0", integer);
    }
    uint64_t encoding;
    memcpy(&encoding, &value, sizeof(encoding));
    /* At normal powers of two above the smallest normal, the predecessor gap
     * is half the successor gap. The closest rounded decimal can sit outside
     * that asymmetric interval while an adjacent decimal lies inside it. For
     * all other finite nonzero values the rounding interval is symmetric, so
     * a more distant decimal cannot rescue a rejected closest candidate. */
    _Bool asymmetric =
        (encoding & UINT64_C(0xfffffffffffff)) == 0 && ((encoding >> 52) & UINT64_C(0x7ff)) > 1;
    char scientific[40];
    int precision = 1;
    for (; precision <= 17; precision++) {
        snprintf(scientific, sizeof(scientific), "%.*e", precision - 1, value);
        if (precision == 17 || strtod(scientific, NULL) == value ||
            (asymmetric && (adjacent_float_decimal(scientific, value, 1) ||
                            adjacent_float_decimal(scientific, value, -1))))
            break;
    }
    char digits[24];
    size_t digit_count = 0;
    const char *cursor = scientific;
    int negative = *cursor == '-';
    if (negative)
        cursor++;
    for (; *cursor && *cursor != 'e'; cursor++)
        if (*cursor >= '0' && *cursor <= '9')
            digits[digit_count++] = *cursor;
    int exponent = atoi(cursor + 1);
    while (digit_count > 1 && digits[digit_count - 1] == '0')
        digit_count--;
    size_t length = 0;
#define FLOAT_PUT(character)                                                                       \
    do {                                                                                           \
        if (length + 1 < capacity)                                                                 \
            out[length] = (character);                                                             \
        length++;                                                                                  \
    } while (0)
    if (negative)
        FLOAT_PUT('-');
    if (exponent >= -7 && exponent < 21) {
        if (exponent < 0) {
            FLOAT_PUT('0');
            FLOAT_PUT('.');
            for (int zero = -1; zero > exponent; zero--)
                FLOAT_PUT('0');
            for (size_t i = 0; i < digit_count; i++)
                FLOAT_PUT(digits[i]);
        } else {
            for (int i = 0; i <= exponent; i++)
                FLOAT_PUT((size_t)i < digit_count ? digits[i] : '0');
            FLOAT_PUT('.');
            if ((size_t)exponent + 1 < digit_count)
                for (size_t i = (size_t)exponent + 1; i < digit_count; i++)
                    FLOAT_PUT(digits[i]);
            else
                FLOAT_PUT('0');
        }
    } else {
        FLOAT_PUT(digits[0]);
        FLOAT_PUT('.');
        if (digit_count > 1)
            for (size_t i = 1; i < digit_count; i++)
                FLOAT_PUT(digits[i]);
        else
            FLOAT_PUT('0');
        char suffix[8];
        snprintf(suffix, sizeof(suffix), "e%+d", exponent);
        for (const char *piece = suffix; *piece; piece++)
            FLOAT_PUT(*piece);
    }
#undef FLOAT_PUT
    if (capacity)
        out[length < capacity ? length : capacity - 1] = 0;
    return length;
}

void minyar_print_float(double value) {
    char text[48];
    format_float(value, text, sizeof(text));
    if (puts(text) == EOF || fflush(stdout) == EOF)
        output_error();
}

MinyarText *minyar_float_text(double value) {
    char text[48];
    size_t length = format_float(value, text, sizeof(text));
    unsigned char *bytes = new_bytes((long long)length);
    memcpy(bytes, text, length + 1);
    return new_text(bytes, (long long)length, (long long)length);
}

long long minyar_float_integer(double value) {
    /* Both bounds are exact powers of two, so the comparison is exact. */
    if (!(value >= -9223372036854775808.0 && value < 9223372036854775808.0))
        minyar_stop(isnan(value) ? "NaN cannot be converted to an Integer."
                                 : "this Float is outside the Integer range.");
    return (long long)value;
}

int minyar_integer_character(long long value) {
    if (value < 0 || value > 0x10ffff || (value >= 0xd800 && value <= 0xdfff))
        minyar_stop("this Integer is not a Unicode scalar value.");
    return (int)value;
}

long long minyar_integer_absolute(long long value) {
    if (value == LLONG_MIN)
        minyar_stop("the absolute value of this Integer is outside the supported range.");
    return value < 0 ? -value : value;
}

void minyar_check_clamp_integer(long long lower, long long upper) {
    if (lower > upper)
        minyar_stop("clamp needs a lower bound that is not above its upper bound.");
}

void minyar_check_clamp_float(double lower, double upper) {
    if (!(lower <= upper))
        minyar_stop("clamp needs a lower bound that is not above its upper bound.");
}

void minyar_check_shift(long long count) {
    if ((unsigned long long)count > 63)
        minyar_stop("a shift count must be between 0 and 63.");
}

double minyar_tan(double value) {
    return tan(value);
}
double minyar_asin(double value) {
    return asin(value);
}
double minyar_acos(double value) {
    return acos(value);
}
double minyar_atan(double value) {
    return atan(value);
}
double minyar_atan2(double y, double x) {
    return atan2(y, x);
}
