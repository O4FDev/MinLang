// Same operations and checked defined domain as checked-scalars.min.
// C++20 bit_cast and unsigned arithmetic preserve Minyar's wrapping addition
// and left shifts without C++ signed-overflow or signed-left-shift undefined behavior.
#include <bit>
#include <climits>
#include <cstdint>
#include <cstdlib>
using Integer = long long;
static_assert(sizeof(Integer) == sizeof(uint64_t) && sizeof(Integer) == 8);
static Integer add(Integer a, Integer b) {
    Integer r;
    if (__builtin_add_overflow(a, b, &r))
        std::abort();
    return r;
}
static Integer subtract(Integer a, Integer b) {
    Integer r;
    if (__builtin_sub_overflow(a, b, &r))
        std::abort();
    return r;
}
static Integer multiply(Integer a, Integer b) {
    Integer r;
    if (__builtin_mul_overflow(a, b, &r))
        std::abort();
    return r;
}
static Integer remainder(Integer a, Integer b) {
    if (!b || (a == LLONG_MIN && b == -1))
        std::abort();
    return a % b;
}
static Integer wrapAdd(Integer a, Integer b) {
    return std::bit_cast<Integer>(std::bit_cast<uint64_t>(a) + std::bit_cast<uint64_t>(b));
}
static Integer leftShift(Integer a, Integer b) {
    if (uint64_t(b) > 63)
        std::abort();
    return std::bit_cast<Integer>(std::bit_cast<uint64_t>(a) << b);
}
static Integer rightShift(Integer a, Integer b) {
    if (uint64_t(b) > 63)
        std::abort();
    return a >> b;
}
static Integer character(Integer value) {
    if (value < 0 || value > 0x10ffff || (value >= 0xd800 && value <= 0xdfff))
        std::abort();
    return value;
}
static Integer integer(double value) {
    if (!(value >= -0x1p63 && value < 0x1p63))
        std::abort();
    return static_cast<Integer>(value);
}
static Integer absolute(Integer value) {
    if (value == LLONG_MIN)
        std::abort();
    return value < 0 ? -value : value;
}
static Integer clamp(Integer v, Integer lo, Integer hi) {
    if (lo > hi)
        std::abort();
    v = v < lo ? lo : v;
    return v > hi ? hi : v;
}
extern "C" Integer cppScalarShift(Integer count, Integer seed) {
    Integer state = seed, total = 0;
    for (Integer position = 0; position < count; position = add(position, 1)) {
        Integer amount = state & 31;
        state = (leftShift(state, amount) ^ rightShift(state, subtract(31, amount))) & 2147483647;
        state = wrapAdd(state, 17) & 2147483647;
        total = wrapAdd(total, state);
    }
    return total;
}
extern "C" Integer cppScalarCharacter(Integer count, Integer seed) {
    Integer state = seed, total = 0;
    for (Integer position = 0; position < count; position = add(position, 1)) {
        state = remainder(add(multiply(state, 17), 23), 1000003);
        total = remainder(add(total, character(remainder(state, 55296))), 1000003);
    }
    return total;
}
extern "C" Integer cppScalarFloat(Integer count, Integer seed) {
    Integer state = seed, total = 0;
    for (Integer position = 0; position < count; position = add(position, 1)) {
        state = remainder(add(multiply(state, 17), 23), 1000003);
        double coordinate = (static_cast<double>(state) - 500001.0) * 0.25;
        total = wrapAdd(total, integer(coordinate));
    }
    return total;
}
extern "C" Integer cppScalarAbsClamp(Integer count, Integer seed) {
    Integer state = seed, total = 0;
    for (Integer position = 0; position < count; position = add(position, 1)) {
        state = remainder(add(multiply(state, 17), 23), 1000003);
        total = wrapAdd(total, clamp(absolute(subtract(state, 500001)), 0, 250000));
    }
    return total;
}
