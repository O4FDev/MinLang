#if defined(MINYAR_SYSTEM_HEAP) && defined(MINYAR_LAZY_HEAP) && !defined(MINYAR_COMPILER_ARENA)
#error Lazy pool backing cannot be combined with the system heap.
#endif
#if defined(MINYAR_SYSTEM_HEAP) && defined(MINYAR_BOUNDED_HEAP) && !defined(MINYAR_COMPILER_ARENA)
#error Select either the system heap or the bounded pool, not both.
#endif
#if (defined(MINYAR_SYSTEM_HEAP) || defined(MINYAR_BOUNDED_HEAP)) && !defined(MINYAR_COMPILER_ARENA)
#define MINYAR_BOUNDED_RC 1
#endif
/* Compiler-inserted reference counting. There is no heap tracing or cycle
 * collector. Potentially cyclic List mutations are rejected before codegen.
 * Counts belong to locals, expression temporaries and typed container slots.
 * Runtime constructors return one owned reference; Text literals and caches are immortal.
 * The compiler's process-lifetime arena compiles ownership operations away. */
#ifdef MINYAR_COMPILER_ARENA
void minyar_rc_enter(long long locals) { (void)locals; }
void minyar_rc_leave(void) {}
void minyar_rc_keep(void *value) { (void)value; }
void minyar_rc_borrow(void *value) { (void)value; }
void minyar_rc_local(long long index, void *value) { (void)index; (void)value; }
void minyar_rc_local_take(long long index, void *value) { (void)index; (void)value; }
void minyar_rc_local_move(long long index) { (void)index; }
void minyar_rc_step(void) {}
void minyar_rc_retain(void *value) { (void)value; }
void minyar_rc_release(void *value) { (void)value; }
#else
enum { RC_TEXT = 1, RC_LIST = 2, RC_REFERENCES = 3, RC_RECORD = 4, RC_SCALAR_RECORD = 5, RC_REFERENCES_IMMORTAL = 6 };
typedef struct { size_t ownership; } RcObject;
typedef struct { size_t size; } RcData;
_Static_assert(sizeof(RcObject) == 8, "LLVM literal ownership header must match");

#ifdef MINYAR_BOUNDED_RC
#define MINYAR_BOUNDED_TEMP_CHUNKS 1
#define MINYAR_BOUNDED_TRACKED_LOCALS 1
enum { RC_TEMPORARY_CHUNK_SLOTS = 8 };
typedef struct RcTemporaryChunk {
    struct RcTemporaryChunk *next;
    size_t count;
    void *values[RC_TEMPORARY_CHUNK_SLOTS];
} RcTemporaryChunk;
#endif

typedef struct RcFrame {
    struct RcFrame *previous;
    void **locals;
    size_t local_count, local_capacity;
#ifdef MINYAR_BOUNDED_RC
    RcTemporaryChunk *temporary_head, *temporary_tail;
    size_t temporary_count, written_count;
#else
    void **temporaries;
    size_t temporary_count, temporary_capacity;
#endif
} RcFrame;
static RcFrame *rc_frames, *rc_free_frames;
#ifdef MINYAR_BOUNDED_RC
static size_t rc_pending_count;
#ifdef MINYAR_RC_TESTING
static size_t rc_bounded_last_work;
#endif
static size_t rc_bounded_cached_frame_bytes;
#ifndef MINYAR_FRAME_CACHE_BYTES
#define MINYAR_FRAME_CACHE_BYTES (256u * 1024u)
#endif
static size_t *rc_bounded_local_indices(RcFrame *frame) {
    return (size_t *)(frame->locals + frame->local_capacity);
}
static void *rc_bounded_local_value(RcFrame *frame, size_t index) {
    return (void *)((uintptr_t)frame->locals[index] & ~(uintptr_t)1);
}
static void *rc_bounded_pending_local_value(RcFrame *frame, size_t position) {
    return rc_bounded_local_value(frame, rc_bounded_local_indices(frame)[position]);
}
#else
static RcObject **rc_pending;
static size_t rc_pending_count, rc_pending_capacity;
#endif
#ifdef MINYAR_RC_TESTING
static size_t rc_object_count, rc_bytes, rc_immortal_object_count;
#define RC_ACCOUNT(expression) ((void)(expression))
#else
#define RC_ACCOUNT(expression) ((void)0)
#endif

#ifdef MINYAR_BOUNDED_RC
#include "minyar_heap.h"
#ifndef MINYAR_RC_POLL_BUDGET
#define MINYAR_RC_POLL_BUDGET 32u
#endif
_Static_assert(MINYAR_RC_POLL_BUDGET > 0 && MINYAR_RC_POLL_BUDGET <= 1024,
               "cleanup budget must be between 1 and 1024");
size_t minyar_rc_poll(size_t budget);
/* Preserve poll instrumentation even when an idle service point takes only
 * the pending-count branch. This path is exercised by instrumented tests. */
static inline size_t rc_service_pending(size_t budget) {
    if (rc_pending_count) return minyar_rc_poll(budget);
#ifdef MINYAR_RC_TESTING
    rc_bounded_last_work = 0;
#endif
    return 0;
}
#define RC_ALLOCATE(size) rc_heap_allocate(size)
#define RC_DEALLOCATE(pointer) rc_heap_deallocate(pointer)
#else
#define RC_ALLOCATE(size) malloc(size)
#define RC_DEALLOCATE(pointer) free(pointer)
#endif

static void *rc_allocate_object(size_t size, unsigned kind) {
#ifdef MINYAR_BOUNDED_RC
    rc_service_pending(MINYAR_RC_POLL_BUDGET);
#endif
    if (size > SIZE_MAX - sizeof(RcObject)) out_of_memory();
    RcObject *object = RC_ALLOCATE(sizeof(*object) + size);
    if (!object) out_of_memory();
    object->ownership = 8 | kind;
    RC_ACCOUNT(rc_object_count++);
    RC_ACCOUNT(rc_bytes += sizeof(*object) + size);
    return object + 1;
}

static void *rc_allocate_data(size_t size) {
#ifdef MINYAR_BOUNDED_RC
    rc_service_pending(MINYAR_RC_POLL_BUDGET);
#endif
    if (size > SIZE_MAX - sizeof(RcData)) out_of_memory();
    RcData *data = RC_ALLOCATE(sizeof(*data) + size);
    if (!data) out_of_memory();
    data->size = size;
    RC_ACCOUNT(rc_bytes += sizeof(*data) + size);
    return data + 1;
}

static void rc_free_data(void *pointer) {
    if (!pointer) return;
    RcData *data = (RcData *)pointer - 1;
    RC_ACCOUNT(rc_bytes -= sizeof(*data) + data->size);
    RC_DEALLOCATE(data);
}

static void *rc_reallocate_data(void *pointer, size_t size) {
    if (!pointer) return rc_allocate_data(size);
#ifdef MINYAR_BOUNDED_RC
    rc_service_pending(MINYAR_RC_POLL_BUDGET);
#endif
    if (size > SIZE_MAX - sizeof(RcData)) out_of_memory();
    RcData *data = (RcData *)pointer - 1;
    RC_ACCOUNT(rc_bytes -= data->size);
#ifdef MINYAR_BOUNDED_RC
    data = rc_heap_resize(data, sizeof(*data) + data->size, sizeof(*data) + size);
#else
    data = realloc(data, sizeof(*data) + size);
#endif
    if (!data) out_of_memory();
    data->size = size;
    RC_ACCOUNT(rc_bytes += size);
    return data + 1;
}

void minyar_rc_retain(void *value) {
    if (!value) return;
    RcObject *object = (RcObject *)value - 1;
    if (!(object->ownership >> 3)) return; /* Immortal literal or cache. */
    if (object->ownership > SIZE_MAX - 8)
        minyar_stop("this value has too many references.");
    object->ownership += 8;
}

#ifdef MINYAR_BOUNDED_RC
#include "minyar_bounded_rc.h"
#else
static void rc_drop(void *value) {
    if (!value) return;
    RcObject *object = (RcObject *)value - 1;
    if (!(object->ownership >> 3)) return;
    object->ownership -= 8;
    if (object->ownership >> 3) return;
    unsigned kind = object->ownership & 7;
    MinyarText *text_backing = NULL;
    /* Leaves can be destroyed immediately, without recursion or queue space.
     * This matters for wide lists of small records and text fragments. */
    if (kind == RC_TEXT) {
        MinyarText *text = (MinyarText *)(object + 1);
        text_backing = text->backing;
        if (!text_backing) rc_free_data((void *)text->bytes);
        rc_free_data(text->character_offsets);
        RC_ACCOUNT(rc_bytes -= sizeof(*object) + sizeof(*text));
    } else if (kind == RC_LIST) {
        MinyarList *list = (MinyarList *)(object + 1);
        rc_free_data(list->values);
        RC_ACCOUNT(rc_bytes -= sizeof(*object) + sizeof(*list));
    } else if (kind == RC_SCALAR_RECORD) {
#ifdef MINYAR_RC_TESTING
        MinyarRecord *record = (MinyarRecord *)(object + 1);
#endif
        RC_ACCOUNT(rc_bytes -= sizeof(*object) + sizeof(MinyarRecord)
                               + (size_t)record->length * sizeof(long long));
    } else {
        if (rc_pending_count == rc_pending_capacity) {
            size_t capacity = rc_pending_capacity ? rc_pending_capacity * 2 : 64;
            if (capacity < rc_pending_capacity || capacity > SIZE_MAX / sizeof(*rc_pending))
                out_of_memory();
            RcObject **pending = realloc(rc_pending, capacity * sizeof(*pending));
            if (!pending) out_of_memory();
            rc_pending = pending;
            rc_pending_capacity = capacity;
        }
        rc_pending[rc_pending_count++] = object;
        return;
    }
    RC_ACCOUNT(rc_object_count--);
    free(object);
    /* Views point directly at an owning root, never at another view. */
    if (text_backing) rc_drop(text_backing);
}

void minyar_rc_release(void *value) {
    rc_drop(value);
    /* Iterative destruction: releasing a deep graph never recurses in C. */
    while (rc_pending_count) {
        RcObject *object = rc_pending[--rc_pending_count];
        unsigned kind = object->ownership & 7;
        if (kind == RC_REFERENCES) {
            MinyarList *list = (MinyarList *)(object + 1);
            for (long long i = 0; i < list->length; i++)
                rc_drop((void *)(uintptr_t)list->values[i]);
            rc_free_data(list->values);
            RC_ACCOUNT(rc_bytes -= sizeof(*object) + sizeof(*list));
        } else {
            MinyarRecord *record = (MinyarRecord *)(object + 1);
            unsigned char *references = (unsigned char *)(record->values + record->length);
            for (long long i = 0; i < record->length; i++)
                if (references[i]) rc_drop((void *)(uintptr_t)record->values[i]);
            RC_ACCOUNT(rc_bytes -= sizeof(*object) + sizeof(*record)
                                   + (size_t)record->length * (sizeof(long long) + 1));
        }
        RC_ACCOUNT(rc_object_count--);
        free(object);
    }
}

#endif

void minyar_rc_step(void);
void minyar_rc_enter(long long locals) {
#ifdef MINYAR_BOUNDED_RC
    minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
#endif
    RcFrame *frame = rc_free_frames;
    if (frame) {
        rc_free_frames = frame->previous;
#ifdef MINYAR_BOUNDED_RC
        rc_bounded_cached_frame_bytes -= rc_heap_charge(frame, sizeof(*frame));
        if (frame->locals)
            rc_bounded_cached_frame_bytes -= rc_heap_charge(frame->locals, frame->local_capacity * (sizeof(void *) + sizeof(size_t)));
#endif
    } else {
#ifdef MINYAR_BOUNDED_RC
        frame = rc_heap_allocate(sizeof(*frame));
        memset(frame, 0, sizeof(*frame));
#else
        frame = calloc(1, sizeof(*frame));
#endif
        if (!frame)
            out_of_memory();
    }
#ifdef MINYAR_BOUNDED_RC
    if ((unsigned long long)locals > SIZE_MAX / (sizeof(void *) + sizeof(size_t)))
        out_of_memory();
#else
    if ((unsigned long long)locals > SIZE_MAX / sizeof(void *))
        out_of_memory();
#endif
    size_t count = (size_t)locals;
    if (count > frame->local_capacity) {
#ifdef MINYAR_BOUNDED_RC
#ifdef MINYAR_SYSTEM_HEAP
        void **values = rc_heap_resize(frame->locals, frame->local_capacity * (sizeof(*values) + sizeof(size_t)),
                                          count * (sizeof(*values) + sizeof(size_t)));
#else
        /* Cached local values and written indices have finished retirement;
         * their old contents need not survive. New frames have no old buffer. */
        void **values = minyar_pool_resize_discard(frame->locals,
                                          count * (sizeof(*values) + sizeof(size_t)));
#endif
#else
        void **values = realloc(frame->locals, count * sizeof(*values));
#endif
        if (!values)
            out_of_memory();
        frame->locals = values;
        frame->local_capacity = count;
    }
    if (count)
        memset(frame->locals, 0, count * sizeof(*frame->locals));
    frame->local_count = count;
    frame->temporary_count = 0;
#ifdef MINYAR_BOUNDED_RC
    frame->written_count = 0;
#endif
    frame->previous = rc_frames;
    rc_frames = frame;
}

void minyar_rc_leave(void) {
    RcFrame *frame = rc_frames;
#ifdef MINYAR_BOUNDED_RC
    rc_frames = frame->previous;
    rc_bounded_retire_temporaries(frame);
    frame->local_count = frame->written_count;
    frame->previous = NULL;
    if (rc_bounded_frame_tail) rc_bounded_frame_tail->previous = frame;
    else rc_bounded_frame_head = frame;
    rc_bounded_frame_tail = frame;
    rc_pending_count++;
    minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
#else
    minyar_rc_step();
    for (size_t i = 0; i < frame->local_count; i++)
        minyar_rc_release(frame->locals[i]);
    rc_frames = frame->previous;
    frame->previous = rc_free_frames;
    rc_free_frames = frame;
#endif
}

void minyar_rc_keep(void *value) {
    if (!value || !(((RcObject *)value - 1)->ownership >> 3))
        return;
    RcFrame *frame = rc_frames;
#ifdef MINYAR_BOUNDED_RC
    RcTemporaryChunk *chunk = frame->temporary_tail;
    if (!chunk || chunk->count == RC_TEMPORARY_CHUNK_SLOTS) {
        /* The incoming owned reference already protects value. Use the
         * chunk's existing extra service budget before requesting storage. */
        rc_service_pending(MINYAR_RC_POLL_BUDGET);
        chunk = rc_heap_allocate(sizeof(*chunk));
        chunk->next = NULL;
        chunk->count = 0;
        if (frame->temporary_tail) frame->temporary_tail->next = chunk;
        else frame->temporary_head = chunk;
        frame->temporary_tail = chunk;
    }
    chunk->values[chunk->count++] = value;
    frame->temporary_count++;
    rc_service_pending(MINYAR_RC_POLL_BUDGET);
#else
    if (frame->temporary_count == frame->temporary_capacity) {
        size_t capacity = frame->temporary_capacity ? frame->temporary_capacity * 2 : 8;
        if (capacity > SIZE_MAX / sizeof(void *))
            out_of_memory();
        void **values = realloc(frame->temporaries, capacity * sizeof(*values));
        if (!values)
            out_of_memory();
        frame->temporaries = values;
        frame->temporary_capacity = capacity;
    }
    frame->temporaries[frame->temporary_count++] = value;
#endif
}

void minyar_rc_local_take(long long index, void *value) {
#ifdef MINYAR_BOUNDED_RC
    uintptr_t previous = (uintptr_t)rc_frames->locals[index];
    if (!(previous & 1) && value)
        rc_bounded_local_indices(rc_frames)[rc_frames->written_count++] = (size_t)index;
    if (value || (previous & 1))
        rc_frames->locals[index] = (void *)((uintptr_t)value | 1);
    minyar_rc_release((void *)(previous & ~(uintptr_t)1));
#else
    void *previous = rc_frames->locals[index];
    rc_frames->locals[index] = value;
    minyar_rc_release(previous);
#endif
}

/* Transfer the local's existing ownership count into an expression without
 * changing the pointer stored in generated local storage. The next assignment
 * replaces that storage; the low bit keeps bounded frames' written-slot index. */
void minyar_rc_local_move(long long index) {
#ifdef MINYAR_BOUNDED_RC
    uintptr_t previous = (uintptr_t)rc_frames->locals[index];
    rc_frames->locals[index] = (void *)(previous & 1);
#else
    rc_frames->locals[index] = NULL;
#endif
}

void minyar_rc_local(long long index, void *value) {
    minyar_rc_retain(value);
    minyar_rc_local_take(index, value);
}

void minyar_rc_borrow(void *value) {
    minyar_rc_retain(value);
    minyar_rc_keep(value);
}

void minyar_rc_step(void) {
    RcFrame *frame = rc_frames;
#ifdef MINYAR_BOUNDED_RC
    rc_bounded_retire_temporaries(frame);
    minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
#else
    while (frame->temporary_count)
        minyar_rc_release(frame->temporaries[--frame->temporary_count]);
#endif
}
#endif
