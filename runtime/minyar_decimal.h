/* Exact decimal-to-binary64 conversion; included once by minyar_numbers.h.
 * JSON validates its spelling before this call; malformed lexemes still return
 * NaN. The valid borrowed Text ABI is required. No locale, floating arithmetic,
 * heap or host libc parser.
 *
 * A binary64 rounding midpoint is M * 2^e, with M < 2^54 and e >= -1075.
 * Its terminating decimal has at most 768 significant digits. Keep 800 digits
 * and a nonzero-tail bit: a discarded suffix can affect rounding only when
 * the retained prefix is exactly a midpoint. Powers and scaled remainders
 * need at most 3732 bits; 128 base-2^30 limbs leave a checked margin. */
enum { DECIMAL_LIMBS = 128, DECIMAL_DIGITS = 800 };
#define DECIMAL_MASK UINT32_C(0x3fffffff)
typedef struct {
    uint32_t limbs[DECIMAL_LIMBS];
    size_t length;
} DecimalNatural;
typedef struct {
    DecimalNatural value;
    uint64_t significant;
    unsigned kept;
    _Bool sticky;
} DecimalInput;

static void decimal_workspace(void) {
    minyar_stop("decimal conversion exceeded its workspace.");
}
static void decimal_trim(DecimalNatural *value) {
    while (value->length && !value->limbs[value->length - 1])
        value->length--;
}
static void decimal_multiply(DecimalNatural *value, unsigned factor, unsigned add) {
    uint64_t carry = add;
    for (size_t i = 0; i < value->length; i++) {
        uint64_t product = (uint64_t)value->limbs[i] * factor + carry;
        value->limbs[i] = (uint32_t)product & DECIMAL_MASK;
        carry = product >> 30;
    }
    if (carry) {
        if (value->length == DECIMAL_LIMBS)
            decimal_workspace();
        value->limbs[value->length++] = (uint32_t)carry;
    }
}
static void decimal_digit(DecimalInput *input, unsigned digit) {
    if (!digit && !input->significant)
        return;
    input->significant++;
    if (input->kept < DECIMAL_DIGITS) {
        decimal_multiply(&input->value, 10, digit);
        input->kept++;
    } else if (digit)
        input->sticky = 1;
}
static void decimal_shift(DecimalNatural *value, unsigned bits) {
    if (!value->length || !bits)
        return;
    size_t words = bits / 30;
    unsigned part = bits % 30;
    if (value->length + words + (part != 0) > DECIMAL_LIMBS)
        decimal_workspace();
    uint64_t carry = 0;
    if (part) {
        for (size_t i = 0; i < value->length; i++) {
            uint64_t shifted = ((uint64_t)value->limbs[i] << part) | carry;
            value->limbs[i] = (uint32_t)shifted & DECIMAL_MASK;
            carry = shifted >> 30;
        }
        if (carry)
            value->limbs[value->length++] = (uint32_t)carry;
    }
    for (size_t i = value->length; i; i--)
        value->limbs[i - 1 + words] = value->limbs[i - 1];
    for (size_t i = 0; i < words; i++)
        value->limbs[i] = 0;
    value->length += words;
}
static void decimal_half(DecimalNatural *value) {
    uint32_t carry = 0;
    for (size_t i = value->length; i; i--) {
        uint32_t limb = value->limbs[i - 1];
        value->limbs[i - 1] = (limb >> 1) | (carry << 29);
        carry = limb & 1;
    }
    decimal_trim(value);
}
static int decimal_compare(const DecimalNatural *left, const DecimalNatural *right) {
    if (left->length != right->length)
        return left->length > right->length ? 1 : -1;
    for (size_t i = left->length; i; i--)
        if (left->limbs[i - 1] != right->limbs[i - 1])
            return left->limbs[i - 1] > right->limbs[i - 1] ? 1 : -1;
    return 0;
}
static void decimal_subtract(DecimalNatural *left, const DecimalNatural *right) {
    uint64_t borrow = 0;
    for (size_t i = 0; i < left->length; i++) {
        uint64_t a = left->limbs[i];
        uint64_t b = (i < right->length ? right->limbs[i] : 0) + borrow;
        left->limbs[i] = (uint32_t)(a - b) & DECIMAL_MASK;
        borrow = a < b;
    }
    decimal_trim(left);
}
static int decimal_bits(const DecimalNatural *value) {
    if (!value->length)
        return 0;
    uint32_t top = value->limbs[value->length - 1];
    int bits = (int)(value->length - 1) * 30;
    do {
        bits++;
        top >>= 1;
    } while (top);
    return bits;
}
static _Bool decimal_u64(const DecimalNatural *value, uint64_t *result) {
    if (value->length > 3 || (value->length == 3 && value->limbs[2] > 15))
        return 0;
    uint64_t scalar = 0;
    for (size_t i = value->length; i; i--)
        scalar = (scalar << 30) | value->limbs[i - 1];
    *result = scalar;
    return 1;
}
static double decimal_float(uint64_t bits, _Bool negative) {
    if (negative)
        bits |= UINT64_C(0x8000000000000000);
    double value;
    memcpy(&value, &bits, sizeof(value));
    return value;
}
static _Bool decimal_is_digit(unsigned char value) {
    return value >= '0' && value <= '9';
}

double minyar_runtime_jsonNumber(const MinyarText *text) {
    if (text->byte_length <= 0 || (uint64_t)text->byte_length > SIZE_MAX)
        return (double)NAN;
    const unsigned char *source = text->bytes;
    size_t length = (size_t)text->byte_length, position = 0;
    _Bool negative = source[position] == '-';
    if (negative && ++position == length)
        return (double)NAN;
    DecimalInput input = {0};
    if (source[position] == '0') {
        position++;
        if (position < length && decimal_is_digit(source[position]))
            return (double)NAN;
    } else {
        if (source[position] < '1' || source[position] > '9')
            return (double)NAN;
        do {
            decimal_digit(&input, source[position++] - '0');
        } while (position < length && decimal_is_digit(source[position]));
    }
    uint64_t fraction = 0;
    if (position < length && source[position] == '.') {
        size_t start = ++position;
        while (position < length && decimal_is_digit(source[position]))
            decimal_digit(&input, source[position++] - '0');
        if (position == start)
            return (double)NAN;
        fraction = position - start;
    }
    long long exponent = 0;
    _Bool exponent_negative = 0;
    if (position < length && (source[position] == 'e' || source[position] == 'E')) {
        position++;
        if (position < length && (source[position] == '-' || source[position] == '+'))
            exponent_negative = source[position++] == '-';
        size_t start = position;
        long long cap = text->byte_length > LLONG_MAX - 1200 ? LLONG_MAX : text->byte_length + 1200;
        while (position < length && decimal_is_digit(source[position])) {
            unsigned digit = source[position++] - '0';
            if (exponent > (cap - digit) / 10)
                exponent = cap;
            else
                exponent = exponent * 10 + digit;
        }
        if (position == start)
            return (double)NAN;
    }
    if (position != length)
        return (double)NAN;
    if (!input.significant)
        return decimal_float(0, negative);
    long long magnitude = (long long)input.significant - (long long)fraction;
    if (exponent_negative) {
        if (magnitude < LLONG_MIN + exponent)
            return decimal_float(0, negative);
        magnitude -= exponent;
    } else {
        if (magnitude > LLONG_MAX - exponent)
            return decimal_float(UINT64_C(0x7ff0000000000000), negative);
        magnitude += exponent;
    }
    /* Magnitude is floor(log10(abs(value))) + 1, not a scientific exponent. */
    if (magnitude > 309)
        return decimal_float(UINT64_C(0x7ff0000000000000), negative);
    if (magnitude < -323)
        return decimal_float(0, negative);
    int power = (int)magnitude - (int)input.kept;
    DecimalNatural numerator = input.value, denominator = {{1}, 1};
    if (power >= 0) {
        for (int i = 0; i < power; i++)
            decimal_multiply(&numerator, 10, 0);
    } else {
        for (int i = 0; i < -power; i++)
            decimal_multiply(&denominator, 10, 0);
    }
    int binary_exponent = decimal_bits(&numerator) - decimal_bits(&denominator);
    DecimalNatural divisor;
    if (binary_exponent >= 0) {
        divisor = denominator;
        decimal_shift(&divisor, (unsigned)binary_exponent);
        if (decimal_compare(&numerator, &divisor) < 0)
            binary_exponent--;
    } else {
        divisor = numerator;
        decimal_shift(&divisor, (unsigned)-binary_exponent);
        if (decimal_compare(&divisor, &denominator) < 0)
            binary_exponent--;
    }
    int shift = binary_exponent < -1022 ? 1074 : 52 - binary_exponent;
    if (shift >= 0)
        decimal_shift(&numerator, (unsigned)shift);
    else
        decimal_shift(&denominator, (unsigned)-shift);
    uint64_t significand, small_numerator, small_denominator;
    int halfway;
    if (decimal_u64(&numerator, &small_numerator) &&
        decimal_u64(&denominator, &small_denominator)) {
        /* Exact short-number path; compare r with d-r instead of overflowing 2r. */
        significand = small_numerator / small_denominator;
        uint64_t remainder = small_numerator % small_denominator;
        uint64_t complement = small_denominator - remainder;
        halfway = (remainder > complement) - (remainder < complement);
    } else {
        divisor = denominator;
        int highest = decimal_bits(&numerator) - decimal_bits(&denominator);
        if (highest >= 64)
            decimal_workspace();
        if (highest > 0)
            decimal_shift(&divisor, (unsigned)highest);
        significand = 0;
        for (int bit = highest; bit >= 0; bit--) {
            if (decimal_compare(&numerator, &divisor) >= 0) {
                decimal_subtract(&numerator, &divisor);
                significand |= UINT64_C(1) << bit;
            }
            decimal_half(&divisor);
        }
        decimal_shift(&numerator, 1);
        halfway = decimal_compare(&numerator, &denominator);
    }
    if (halfway > 0 || (halfway == 0 && ((significand & 1) || input.sticky)))
        significand++;
    if (binary_exponent < -1022)
        return decimal_float(significand, negative);
    if (significand == UINT64_C(0x20000000000000)) {
        significand >>= 1;
        binary_exponent++;
    }
    if (binary_exponent > 1023)
        return decimal_float(UINT64_C(0x7ff0000000000000), negative);
    return decimal_float(((uint64_t)(binary_exponent + 1023) << 52) |
                             (significand - UINT64_C(0x10000000000000)),
                         negative);
}
#undef DECIMAL_MASK
