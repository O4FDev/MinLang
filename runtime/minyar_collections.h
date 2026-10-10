/* Runtime implementation fragment; included once by minyar_runtime.c. */

MinyarList *minyar_list_new(void) {
    MinyarList *list = object_allocate(sizeof(*list), 2);
    list->values = NULL;
    list->length = 0;
    list->capacity = 0;
    return list;
}

/* A List whose element type can reach the List type itself. Its slots are
 * owning edges for the cycle tracer; the compiler selects this constructor
 * from the static type, so other Lists carry no cycle metadata. */
MinyarList *minyar_list_new_traced(void) {
#ifdef MINYAR_COMPILER_ARENA
    return minyar_list_new();
#else
    MinyarList *list = rc_allocate_object(sizeof(*list), RC_TRACED);
    list->values = NULL;
    list->length = 0;
    list->capacity = 0;
    return list;
#endif
}

/* Called once, while an inferred empty List is still empty. */
void minyar_list_references(MinyarList *list) {
#ifndef MINYAR_COMPILER_ARENA
    RcObject *object = (RcObject *)list - 1;
    if ((object->ownership & 7) == RC_TRACED)
        return;
#ifdef MINYAR_BOUNDED_RC
    unsigned kind = object->ownership & 7;
    if (kind == RC_REFERENCES || kind == RC_REFERENCES_IMMORTAL)
        return;
    object->ownership =
        (object->ownership & ~(size_t)7) | (list->length ? RC_REFERENCES : RC_REFERENCES_IMMORTAL);
#else
    object->ownership = (object->ownership & ~(size_t)7) | RC_REFERENCES;
#endif
#else
    (void)list;
#endif
}

MINYAR_HOT long long list_next_capacity(long long current) {
    if (current < 0)
        minyar_stop("this List became too large.");
#if defined(MINYAR_BOUNDED_HEAP) && !defined(MINYAR_COMPILER_ARENA)
    /* Leave room for RcData inside each power-of-two backing block. A capacity
       of 2^n entries plus a header would waste almost half the finite pool. */
    _Static_assert(sizeof(RcData) == sizeof(long long), "bounded List header layout");
    if (current > (LLONG_MAX - 1) / 2)
        minyar_stop("this List became too large.");
    long long capacity = current == 0 ? 3 : current * 2 + 1;
#else
    /* Most Lists stay tiny, so they start small; large ones grow fast enough
       that the copies made before they settle in the large-list arena stay
       a fraction of their final size. */
    long long factor = current >= LARGE_LIST_CAPACITY ? 4 : 2;
    if (current > LLONG_MAX / factor)
        minyar_stop("this List became too large.");
    long long capacity = current == 0 ? 2 : current * factor;
#endif
    return capacity;
}

MINYAR_HOT void list_resize(MinyarList *list, long long capacity) {
    long long *values;
    if (capacity < list->capacity || (unsigned long long)capacity > SIZE_MAX / sizeof(*values))
        minyar_stop("this List became too large.");
#ifdef MINYAR_COMPILER_ARENA
    if (list->values && list_arena_for(list->capacity) == list_arena_for(capacity) &&
        arena_extend(list_arena_for(capacity), list->values,
                     (size_t)list->capacity * sizeof(*values),
                     (size_t)(capacity - list->capacity) * sizeof(*values))) {
        list->capacity = capacity;
        return;
    }
    values = list_allocate(capacity, (size_t)capacity * sizeof(*values));
    if (list->values)
        memcpy(values, list->values, (size_t)list->length * sizeof(*values));
#else
    values = rc_reallocate_data(list->values, (size_t)capacity * sizeof(*values));
    if (!values)
        out_of_memory();
#endif
    list->values = values;
    list->capacity = capacity;
}

/* Plan the existing geometric policy before touching storage. Known-length
 * construction needs one reservation, without copying empty intermediate
 * buffers or retaining them in a compiler arena. */
static MINYAR_COLD void list_reserve(MinyarList *list, long long minimum) {
    long long capacity = list->capacity;
    if (minimum < 0 || capacity < 0)
        minyar_stop("this List became too large.");
    if (capacity >= minimum)
        return;
    while (capacity < minimum)
        capacity = list_next_capacity(capacity);
    list_resize(list, capacity);
}

/* Compiler-only scalar literal path. The source is immutable, non-overlapping
 * i64 data; every evaluation still owns a fresh mutable backing allocation. */
void minyar_list_append_scalars(MinyarList *list, const long long *values, long long count) {
    if (count < 0 || list->length < 0 || count > LLONG_MAX - list->length ||
        (unsigned long long)(list->length + count) > SIZE_MAX / sizeof(*values))
        minyar_stop("this List became too large.");
    if (!count)
        return;
    long long length = list->length + count;
    list_reserve(list, length);
    memcpy(list->values + list->length, values, (size_t)count * sizeof(*values));
    list->length = length;
}

static MINYAR_COLD void list_grow(MinyarList *list) {
    list_resize(list, list_next_capacity(list->capacity));
}

#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_COMPILER_ARENA)
/* The first mortal member permanently promotes an immortal-only List. Service
 * during preceding appends still pays potential scan work if promotion happens
 * later; when no work is pending this is only one cheap count test. */
static inline unsigned list_store_kind(MinyarList *list, long long value, unsigned kind) {
    RcObject *object = (RcObject *)list - 1;
    if (kind == RC_REFERENCES_IMMORTAL && value &&
        (((RcObject *)(uintptr_t)value - 1)->ownership >> 3)) {
        object->ownership = (object->ownership & ~(size_t)7) | RC_REFERENCES;
        kind = RC_REFERENCES;
    }
    return kind;
}
#endif

void minyar_list_add(MinyarList *list, long long value) {
    if (list->length == list->capacity)
        list_grow(list);
#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_COMPILER_ARENA)
    unsigned kind = ((RcObject *)list - 1)->ownership & 7;
    if (kind == RC_LIST) {
        list->values[list->length++] = value;
        return;
    }
    kind = list_store_kind(list, value, kind);
    if (kind == RC_REFERENCES || kind == RC_TRACED) {
        minyar_rc_retain((void *)(uintptr_t)value);
        if (kind == RC_TRACED) rc_cycle_edge_add(list, (void *)(uintptr_t)value);
    }
    list->values[list->length++] = value;
    if (rc_pending_count)
        minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
#else
#ifndef MINYAR_COMPILER_ARENA
    unsigned kind = ((RcObject *)list - 1)->ownership & 7;
    if (kind == RC_REFERENCES || kind == RC_TRACED) {
        minyar_rc_retain((void *)(uintptr_t)value);
        if (kind == RC_TRACED) rc_cycle_edge_add(list, (void *)(uintptr_t)value);
    }
#endif
    list->values[list->length++] = value;
#endif
}

/* The compiler transfers an existing owned reference into this new slot. */
void minyar_list_add_take(MinyarList *list, long long value) {
    if (list->length == list->capacity)
        list_grow(list);
#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_COMPILER_ARENA)
    unsigned kind = ((RcObject *)list - 1)->ownership & 7;
    if (kind == RC_LIST) {
        list->values[list->length++] = value;
        return;
    }
    kind = list_store_kind(list, value, kind);
    if (kind == RC_TRACED)
        rc_cycle_edge_add(list, (void *)(uintptr_t)value);
#elif !defined(MINYAR_COMPILER_ARENA)
    if ((((RcObject *)list - 1)->ownership & 7) == RC_TRACED)
        rc_cycle_edge_add(list, (void *)(uintptr_t)value);
#endif
    list->values[list->length++] = value;
#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_COMPILER_ARENA)
    if (rc_pending_count)
        minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
#endif
}

long long minyar_list_length(const MinyarList *list) {
    return list->length;
}

static MINYAR_COLD MINYAR_NORETURN void list_position_stop(long long position, long long length) {
    char message[128];
    snprintf(message, sizeof(message), "List position %lld is outside its length of %lld.",
             position, length);
    minyar_stop(message);
}

long long minyar_list_get(const MinyarList *list, long long position) {
    if ((unsigned long long)position >= (unsigned long long)list->length)
        list_position_stop(position, list->length);
    return list->values[position];
}

static void minyar_list_set_owned(MinyarList *list, long long position, long long value,
                                  int retain_value) {
    if ((unsigned long long)position >= (unsigned long long)list->length)
        list_position_stop(position, list->length);
#ifndef MINYAR_COMPILER_ARENA
#ifdef MINYAR_BOUNDED_RC
    unsigned kind = list_store_kind(list, value, ((RcObject *)list - 1)->ownership & 7);
#else
    unsigned kind = ((RcObject *)list - 1)->ownership & 7;
#endif
    if (kind == RC_REFERENCES || kind == RC_TRACED) {
        if (retain_value)
            minyar_rc_retain((void *)(uintptr_t)value);
        long long previous = list->values[position];
        if (kind == RC_TRACED) {
            rc_cycle_edge_add(list, (void *)(uintptr_t)value);
            rc_cycle_edge_remove((void *)(uintptr_t)previous);
        }
        list->values[position] = value;
        minyar_rc_release((void *)(uintptr_t)previous);
        return;
    }
#else
    (void)retain_value;
#endif
    list->values[position] = value;
}

void minyar_list_set(MinyarList *list, long long position, long long value) {
    minyar_list_set_owned(list, position, value, 1);
}

/* The compiler transfers an existing owned reference into this slot. */
void minyar_list_set_take(MinyarList *list, long long position, long long value) {
    minyar_list_set_owned(list, position, value, 0);
}

/* Return a fresh List containing the old elements followed by value. Because
 * the result did not exist while its inputs were evaluated, this operation
 * cannot introduce the first ownership cycle, so it never enables tracing. The compiler supplies the
 * element ownership kind and may transfer the final value's existing owner. */
MinyarList *minyar_list_appended(const MinyarList *list, long long value, long long references,
                                 long long take_value) {
#ifdef MINYAR_COMPILER_ARENA
    MinyarList *result = minyar_list_new();
#else
    /* The result has the operand's static type, hence its traced layout. */
    MinyarList *result = (((RcObject *)list - 1)->ownership & 7) == RC_TRACED
                             ? minyar_list_new_traced() : minyar_list_new();
#endif
    if (references)
        minyar_list_references(result);
    if (list->length == LLONG_MAX)
        minyar_stop("this List became too large.");
    _Bool bulk_scalar = !references;
#ifdef MINYAR_BOUNDED_RC
    bulk_scalar = bulk_scalar && !rc_pending_count;
#endif
#ifdef MINYAR_BOUNDED_RC
    /* Intermediate growth services pending retirement. Keep that schedule
     * under debt: its releases can admit a final buffer in a tight pool. */
    if (rc_pending_count) {
        while (result->capacity < list->length + 1)
            list_grow(result);
    } else
#endif
        list_reserve(result, list->length + 1);
    if (bulk_scalar) {
        if (list->length)
            memcpy(result->values, list->values, (size_t)list->length * sizeof(*list->values));
        result->length = list->length;
    } else {
        for (long long position = 0; position < list->length; position++)
            minyar_list_add(result, list->values[position]);
    }
    if (take_value)
        minyar_list_add_take(result, value);
    else
        minyar_list_add(result, value);
    return result;
}

#ifdef MINYAR_BOUNDED_RC
MINYAR_HOT
#else
static
#endif
/* references: 0 scalar-only, 1 mixed, 2 mixed and traced (see list_new_traced). */
MinyarRecord *record_allocate(long long field_count, int references) {
    MinyarRecord *record;
    if (field_count < 0 || (unsigned long long)field_count > SIZE_MAX / sizeof(long long))
        minyar_stop("this record has too many fields.");
#ifdef MINYAR_COMPILER_ARENA
    (void)references;
    record = minyar_list_new();
    if (field_count > 0) {
        record->values = list_allocate(field_count, (size_t)field_count * sizeof(*record->values));
        memset(record->values, 0, (size_t)field_count * sizeof(*record->values));
    }
#else
    size_t field_size = sizeof(long long) + (references ? 1 : 0);
    if ((unsigned long long)field_count >
        (SIZE_MAX - sizeof(RcObject) - sizeof(*record)) / field_size)
        out_of_memory();
    record = rc_allocate_object(sizeof(*record) + (size_t)field_count * field_size,
                                references == 2 ? RC_TRACED : references ? RC_RECORD : RC_SCALAR_RECORD);
    if (references == 2)
        rc_cycle_metadata((RcObject *)record - 1)->record = 1;
    memset(record->values, 0, (size_t)field_count * field_size);
#endif
    record->length = field_count;
#ifdef MINYAR_COMPILER_ARENA
    record->capacity = field_count;
#endif
    return record;
}

MinyarRecord *minyar_record_new(long long field_count) {
    return record_allocate(field_count, 1);
}

MinyarRecord *minyar_record_new_traced(long long field_count) {
    return record_allocate(field_count, 2);
}

MinyarRecord *minyar_record_new_scalar(long long field_count) {
    return record_allocate(field_count, 0);
}

long long minyar_record_get(const MinyarRecord *record, long long field) {
    if ((unsigned long long)field >= (unsigned long long)record->length)
        list_position_stop(field, record->length);
    return record->values[field];
}

/* Compiler-selected entry point for scalar-only record fields. */
void minyar_record_set_scalar(MinyarRecord *record, long long field, long long value) {
    if ((unsigned long long)field >= (unsigned long long)record->length)
        list_position_stop(field, record->length);
    record->values[field] = value;
}

void minyar_record_set(MinyarRecord *record, long long field, long long value) {
    if ((unsigned long long)field >= (unsigned long long)record->length)
        list_position_stop(field, record->length);
    record->values[field] = value;
#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_COMPILER_ARENA)
    unsigned kind = ((RcObject *)record - 1)->ownership & 7;
    if (kind == RC_RECORD || kind == RC_TRACED)
        minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
#endif
}

void minyar_record_set_take(MinyarRecord *record, long long field, long long value) {
    if ((unsigned long long)field >= (unsigned long long)record->length)
        list_position_stop(field, record->length);
#ifndef MINYAR_COMPILER_ARENA
    unsigned char *references = (unsigned char *)(record->values + record->length);
    references[field] = 1;
    if ((((RcObject *)record - 1)->ownership & 7) == RC_TRACED)
        rc_cycle_edge_add(record, (void *)(uintptr_t)value);
#endif
    minyar_record_set(record, field, value);
}

void minyar_record_set_reference(MinyarRecord *record, long long field, long long value) {
    minyar_rc_retain((void *)(uintptr_t)value);
    minyar_record_set_take(record, field, value);
}

/* Replace an owning edge, preserving the collector snapshot before the poll. */
void minyar_record_replace(MinyarRecord *record, long long field, long long value,
                           long long take_value) {
    if ((unsigned long long)field >= (unsigned long long)record->length)
        list_position_stop(field, record->length);
#ifndef MINYAR_COMPILER_ARENA
    if (!take_value)
        minyar_rc_retain((void *)(uintptr_t)value);
    long long previous = record->values[field];
    if ((((RcObject *)record - 1)->ownership & 7) == RC_TRACED) {
        rc_cycle_edge_add(record, (void *)(uintptr_t)value);
        rc_cycle_edge_remove((void *)(uintptr_t)previous);
    }
    record->values[field] = value;
    minyar_rc_release((void *)(uintptr_t)previous);
#else
    (void)take_value;
    record->values[field] = value;
#endif
}
