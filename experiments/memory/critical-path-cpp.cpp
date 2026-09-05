// Same defined-domain arithmetic and storage layout as the Minyar fixture.
// Overflow and bounds checks remain enabled. These are hot-path comparisons;
// setup and destruction are measured separately by the existing memory study.
#include <cstdlib>
#include <climits>

using Integer = long long;
struct Book { Integer *values; Integer length, capacity; };
struct Pair { Integer x, y; };

static Integer add(Integer a, Integer b) {
    Integer result;
    if (__builtin_add_overflow(a, b, &result)) std::abort();
    return result;
}
static Integer multiply(Integer a, Integer b) {
    Integer result;
    if (__builtin_mul_overflow(a, b, &result)) std::abort();
    return result;
}
static Integer remainder(Integer a, Integer b) {
    if (!b || (a == LLONG_MIN && b == -1)) std::abort();
    return a % b;
}
static Integer &at(Book *book, Integer index) {
    if (index < 0 || index >= book->length) std::abort();
    return book->values[index];
}
extern "C" Integer cppArithmetic(Integer count, Integer seed) {
    Integer state = seed, total = 0;
    for (Integer position = 0; position < count; position = add(position, 1)) {
        state = remainder(add(multiply(state, 17), 23), 1000003);
        total = remainder(add(total, state), 1000003);
    }
    return total;
}
extern "C" Integer cppBook(Book *book, Integer count, Integer seed) {
    Integer state = seed, total = 0;
    for (Integer position = 0; position < count; position = add(position, 1)) {
        state = remainder(add(multiply(state, 17), 23), 1000003);
        Integer index = remainder(state, book->length);
        at(book, index) = state;
        total = remainder(add(total, at(book, index)), 1000003);
    }
    return total;
}
extern "C" Integer cppRecords(Integer count, Integer seed) {
    Integer state = seed, total = 0;
    for (Integer position = 0; position < count; position = add(position, 1)) {
        state = remainder(add(multiply(state, 17), 23), 1000003);
        Pair pair{state, total};
        total = remainder(add(pair.x, pair.y), 1000003);
    }
    return total;
}
