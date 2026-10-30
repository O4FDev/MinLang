/* Stable List sorting. Natural permutations have no collector service points:
 * slot ownership and the multiset of traced edges remain unchanged. */
typedef long long (*MinyarSortComparator)(void *, long long, long long);
typedef struct {
    long long kind;
    const long long *snapshot;
    void *context;
    MinyarSortComparator comparator;
} MinyarSortOrder;

long long minyar_compare_slots(long long kind, long long a, long long b) {
    if (kind == 7) {
        double x, y;
        memcpy(&x, &a, sizeof(x)); memcpy(&y, &b, sizeof(y));
        if (isnan(x)) return !isnan(y);
        if (isnan(y)) return -1;
        return (x > y) - (x < y);
    }
    if (kind == 2) {
        if (!a || !b) return (a != 0) - (b != 0);
        const MinyarText *x = (const void *)(uintptr_t)a, *y = (const void *)(uintptr_t)b;
        size_t length = (size_t)(x->byte_length < y->byte_length ? x->byte_length : y->byte_length);
        int result = length ? memcmp(x->bytes, y->bytes, length) : 0;
        return result ? result : (x->byte_length > y->byte_length) - (x->byte_length < y->byte_length);
    }
    return (a > b) - (a < b);
}

_Bool minyar_equal_slots(long long kind, long long a, long long b) {
    if (kind == 2) return minyar_compare_slots(kind, a, b) == 0;
    if (kind == 7) {
        double x, y;
        memcpy(&x, &a, sizeof(x)); memcpy(&y, &b, sizeof(y));
        return x == y;
    }
    return a == b;
}

static int list_sort_compare(const MinyarSortOrder *order, long long a, long long b) {
    if (order->comparator) {
        if (minyar_recovery_pending()) return 0;
        minyar_runtime_callers++; /* a stop here must not leave a merge half done */
        long long result = order->comparator(order->context, order->snapshot[a], order->snapshot[b]);
        minyar_runtime_callers--;
        if (minyar_recovery_pending()) return 0;
        return (result > 0) - (result < 0);
    }
    long long result = minyar_compare_slots(order->kind, a, b);
    return (result > 0) - (result < 0);
}

/* Copy only the left run. Taking its equal element first preserves stability.
 * A shared ceil(n/2)-slot buffer suffices at every recursion depth. */
static void list_sort_merge(long long *values, size_t count, long long *scratch,
                            const MinyarSortOrder *order) {
    if (count < 2 || (order->comparator && minyar_recovery_pending())) return;
    size_t left_count = count / 2, right_count = count - left_count;
    list_sort_merge(values, left_count, scratch, order);
    if (order->comparator && minyar_recovery_pending()) return;
    list_sort_merge(values + left_count, right_count, scratch, order);
    int comparison = list_sort_compare(order, values[left_count - 1], values[left_count]);
    if ((order->comparator && minyar_recovery_pending()) || comparison <= 0) return;
    memcpy(scratch, values, left_count * sizeof(*scratch));
    size_t left = 0, right = left_count, output = 0;
    while (left < left_count && right < count) {
        comparison = list_sort_compare(order, scratch[left], values[right]);
        if (order->comparator && minyar_recovery_pending()) return;
        if (comparison <= 0)
            values[output++] = scratch[left++];
        else
            values[output++] = values[right++];
    }
    if (left < left_count) memcpy(values + output, scratch + left, (left_count - left) * sizeof(*values));
}

/* Natural orders get one merge sort per slot kind with the comparison inlined:
 * runs of up to LIST_SORT_SMALL slots use insertion sort, an ordered pair of
 * halves skips its merge, and a wholly non-descending or strictly descending
 * List is finished in one scan. Taking the left slot unless the right one is
 * strictly smaller keeps every merge stable, and reversing only a strictly
 * descending List never reorders equal slots. The scratch bound is unchanged. */
enum { LIST_SORT_SMALL = 20 };
#define LIST_SORT_DEFINE(NAME, LESS)                                                          \
    static void NAME##_insert(long long *values, size_t count) {                             \
        for (size_t i = 1; i < count; i++) {                                                  \
            long long value = values[i];                                                      \
            size_t j = i;                                                                     \
            for (; j > 0 && LESS(value, values[j - 1]); j--) values[j] = values[j - 1];      \
            values[j] = value;                                                                \
        }                                                                                     \
    }                                                                                         \
    static void NAME##_merge(long long *values, size_t count, long long *scratch) {          \
        if (count <= LIST_SORT_SMALL) {                                                       \
            NAME##_insert(values, count);                                                     \
            return;                                                                           \
        }                                                                                     \
        size_t left_count = count / 2;                                                        \
        NAME##_merge(values, left_count, scratch);                                            \
        NAME##_merge(values + left_count, count - left_count, scratch);                       \
        if (!LESS(values[left_count], values[left_count - 1])) return;                       \
        memcpy(scratch, values, left_count * sizeof(*scratch));                               \
        size_t left = 0, right = left_count, output = 0;                                      \
        while (left < left_count && right < count) {                                          \
            long long candidate = values[right], held = scratch[left];                        \
            _Bool take_right = LESS(candidate, held);                                         \
            values[output++] = take_right ? candidate : held;                                 \
            right += take_right;                                                              \
            left += !take_right;                                                              \
        }                                                                                     \
        if (left < left_count)                                                                \
            memcpy(values + output, scratch + left, (left_count - left) * sizeof(*values));   \
    }                                                                                         \
    static void NAME(long long *values, size_t count, long long *scratch) {                  \
        size_t ordered = 1;                                                                   \
        while (ordered < count && !LESS(values[ordered], values[ordered - 1])) ordered++;    \
        if (ordered == count) return;                                                         \
        if (ordered == 1) {                                                                   \
            size_t descending = 1;                                                            \
            while (descending < count && LESS(values[descending], values[descending - 1]))   \
                descending++;                                                                 \
            if (descending == count) {                                                        \
                for (size_t i = 0, j = count - 1; i < j; i++, j--) {                          \
                    long long held = values[i];                                               \
                    values[i] = values[j];                                                    \
                    values[j] = held;                                                         \
                }                                                                             \
                return;                                                                       \
            }                                                                                 \
        }                                                                                     \
        NAME##_merge(values, count, scratch);                                                 \
    }

#define LIST_SORT_INTEGER_LESS(a, b) ((a) < (b))
static inline _Bool list_sort_float_less(long long a, long long b) {
    double x, y;
    memcpy(&x, &a, sizeof(x)); memcpy(&y, &b, sizeof(y));
    /* NaNs come last and equal one another; signed zeros compare equal. */
    return !isnan(x) && (isnan(y) || x < y);
}
static inline _Bool list_sort_text_less(long long a, long long b) {
    return minyar_compare_slots(2, a, b) < 0;
}
LIST_SORT_DEFINE(list_sort_integers, LIST_SORT_INTEGER_LESS)
LIST_SORT_DEFINE(list_sort_floats, list_sort_float_less)
LIST_SORT_DEFINE(list_sort_texts, list_sort_text_less)
#undef LIST_SORT_INTEGER_LESS
#undef LIST_SORT_DEFINE

static size_t list_sort_count(const MinyarList *list) {
    if (list->length < 0 || (unsigned long long)list->length > SIZE_MAX / sizeof(long long))
        minyar_stop("this List became too large.");
    return (size_t)list->length;
}
static long long *list_sort_allocate(size_t slots) {
    if (slots > SIZE_MAX / sizeof(long long)) out_of_memory();
    if (!slots) return NULL;
    long long *storage = malloc(slots * sizeof(*storage));
    if (!storage) out_of_memory();
    return storage;
}

/* The graph engine supplies these macros when it substitutes its audited
 * collection header. Ordinary artifacts contain only ordinary RC/stores. */
#ifndef MINYAR_SORT_GRAPH
#define SORT_RETAIN minyar_rc_retain
#define SORT_ADD minyar_list_add
#else
#define SORT_RETAIN minyar_rc_retain_traced
#define SORT_ADD minyar_list_add_traced
#define SORT_SET minyar_list_set_traced
#endif

static MinyarList *list_sort_new(const MinyarList *source, long long references) {
    MinyarList *result;
#if defined(MINYAR_SORT_GRAPH) && !defined(MINYAR_COMPILER_ARENA)
    result = ((((const RcObject *)source - 1)->ownership & 7) == RC_TRACED)
                 ? minyar_list_new_traced() : minyar_list_new();
#else
    (void)source;
    result = minyar_list_new();
#endif
    if (references) minyar_list_references(result);
    return result;
}

void minyar_list_sort(MinyarList *list, long long kind) {
    if (minyar_recovery_pending()) return;
    if (kind != 1 && kind != 2 && kind != 3 && kind != 4 && kind != 7)
        minyar_stop("this List element type has no natural order.");
    size_t count = list_sort_count(list);
    if (count < 2) return;
    long long *scratch = count > LIST_SORT_SMALL ? list_sort_allocate(count / 2 + count % 2) : NULL;
    if (kind == 2) list_sort_texts(list->values, count, scratch);
    else if (kind == 7) list_sort_floats(list->values, count, scratch);
    else list_sort_integers(list->values, count, scratch);
    free(scratch);
}

MinyarList *minyar_list_sorted(MinyarList *list, long long kind, long long references) {
    if (minyar_recovery_pending()) return NULL;
    SORT_RETAIN(list);
    size_t count = list_sort_count(list);
    MinyarList *result = list_sort_new(list, references);
    list_reserve(result, (long long)count);
    for (size_t i = 0; i < count; i++) SORT_ADD(result, list->values[i]);
    minyar_list_sort(result, kind);
    minyar_rc_release(list);
    return result;
}

static MinyarList *list_sort_by(MinyarList *list, void *context, MinyarSortComparator comparator,
                                long long references, int copying) {
    if (minyar_recovery_pending()) return copying ? NULL : list;
    SORT_RETAIN(list);
    SORT_RETAIN(context);
    size_t count = list_sort_count(list), half = count / 2 + count % 2;
    /* Snapshot n, permutation n, merge scratch ceil(n/2): about 2.5n slots. */
    if (count > (SIZE_MAX / sizeof(long long) - half) / 2) out_of_memory();
    long long *storage = list_sort_allocate(count * 2 + half);
    long long *snapshot = storage, *indices = count ? storage + count : NULL;
    long long *scratch = count ? indices + count : NULL;
    if (count) memcpy(snapshot, list->values, count * sizeof(*snapshot));
    for (size_t i = 0; i < count; i++) {
        indices[i] = (long long)i;
        if (references) SORT_RETAIN((void *)(uintptr_t)snapshot[i]);
    }
    MinyarList *result = copying ? NULL : list;
    MinyarSortOrder order = {0, snapshot, context, comparator};
    list_sort_merge(indices, count, scratch, &order);
    /* A failed comparator may leave a partial permutation. Release its rooted
     * snapshot without committing that permutation or allocating a result. */
    if (minyar_recovery_pending()) goto done;
    if (list->length != (long long)count ||
        (count && memcmp(list->values, snapshot, count * sizeof(*snapshot))))
        minyar_stop("the List was mutated during its sort comparator.");
    if (copying) {
        result = list_sort_new(list, references);
        list_reserve(result, (long long)count);
        for (size_t i = 0; i < count; i++) SORT_ADD(result, snapshot[indices[i]]);
    } else {
#ifndef MINYAR_SORT_GRAPH
        /* The slots still equal the snapshot, so the permutation moves each
         * existing owner once, like the natural sort: no count changes. */
        for (size_t i = 0; i < count; i++) list->values[i] = snapshot[indices[i]];
#else
        for (size_t i = 0; i < count; i++) SORT_SET(list, (long long)i, snapshot[indices[i]]);
#endif
    }
done:
    for (size_t i = 0; references && i < count; i++) minyar_rc_release((void *)(uintptr_t)snapshot[i]);
    free(storage);
    minyar_rc_release(context);
    minyar_rc_release(list);
    return result;
}

void minyar_list_sort_by(MinyarList *list, void *context, MinyarSortComparator comparator,
                          long long references) {
    (void)list_sort_by(list, context, comparator, references, 0);
}
MinyarList *minyar_list_sorted_by(MinyarList *list, void *context, MinyarSortComparator comparator,
                                 long long references) {
    return list_sort_by(list, context, comparator, references, 1);
}
#undef SORT_RETAIN
#undef SORT_ADD
#undef SORT_SET
