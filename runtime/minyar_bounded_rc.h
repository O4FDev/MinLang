/* Finite-heap profile: no allocation in the pending queue:
 * a dead object's header becomes a tagged recent-stack or captured-batch link.
 * Its payload is retained until a cursor has processed every field. Only
 * zero-count objects enter the object queue; detached frames and temporary
 * chunks have separate queues.
 * A work unit visits one owner/field or retires one task (up to three frees).
 * Pool frees have at most log2(heap/minimum-block) merge steps. System
 * allocator calls have no runtime-imposed execution-time bound.
 * Work bounds exclude startup, data copying and OS scheduling/page faults. */
/* The object scheduler's state is one struct. Units take it by pointer, so
 * the object-only scheduler loop runs on a local copy (registers) and
 * publishes it once per service point; elsewhere the pointer names the
 * thread's own instance. The old names stay as views of its fields. */
typedef struct {
    RcObject *head, *tail, *active, *recent_head, *recent_tail;
    size_t cursor;
    unsigned recent_turn;
} RcBoundedObjects;
static MINYAR_THREAD_LOCAL RcBoundedObjects rc_objects;
#define rc_bounded_head (rc_objects.head)
#define rc_bounded_tail (rc_objects.tail)
#define rc_bounded_active (rc_objects.active)
#define rc_bounded_cursor (rc_objects.cursor)
#define MINYAR_RC_RECENT_OBJECTS 1
#define rc_bounded_recent_head (rc_objects.recent_head)
#define rc_bounded_recent_tail (rc_objects.recent_tail)
#define rc_bounded_recent_turn (rc_objects.recent_turn)

/* The old-object backlog: object tasks still pending at the end of the
 * service point after the one that queued them. It is a second instance of the object scheduler
 * state above, swapped in while it is serviced, so its tasks keep their
 * cursors, order and recent/captured alternation, and objects that its units
 * free join it rather than the fresh queue. rc_pending_count counts fresh
 * tasks only, so ordinary service points ignore the backlog's
 * rc_backlog_count tasks; rc_bounded_owner_tasks counts queued frames and
 * temporary chunks, so fresh object tasks are the remainder. */
#define MINYAR_RC_BACKLOG 1
static MINYAR_THREAD_LOCAL RcBoundedObjects rc_backlog;
static MINYAR_THREAD_LOCAL size_t rc_backlog_credit, rc_bounded_owner_tasks;
static MINYAR_THREAD_LOCAL unsigned rc_bounded_fresh_aged;

#if defined(MINYAR_SYSTEM_HEAP) && !defined(MINYAR_OBJECT_SLOT_HEADERS)
#error minyar_heap.h must say whether objects carry slot headers
#endif

/* Dead List capacity is spare. Dead record map bytes retain their low-bit
 * reference flag and store seven cursor bits each. The loop executes at most
 * ceil(sizeof(size_t)*CHAR_BIT/7) iterations, independent of graph size. */
MINYAR_HOT size_t rc_bounded_saved_cursor(RcObject *object) {
    if ((object->ownership & 7) == RC_TEXT) return 0;
    if ((object->ownership & 7) == RC_REFERENCES)
        return (size_t)((MinyarList *)(object + 1))->capacity;
#if defined(MINYAR_SYSTEM_HEAP) && MINYAR_OBJECT_SLOT_HEADERS
    return ((RcSystemSlot *)object - 1)->value.bytes;
#else
    MinyarRecord *record = (MinyarRecord *)(object + 1);
    unsigned char *map = (unsigned char *)(record->values + record->length);
    size_t cursor = 0;

    size_t remaining = (size_t)record->length;
    for (size_t i = 0; remaining; i++, remaining >>= 7)
        cursor |= (size_t)(map[i] >> 1) << (i * 7);
    return cursor;
#endif
}

MINYAR_HOT void rc_bounded_save_cursor(RcObject *object, size_t cursor) {
    if ((object->ownership & 7) == RC_TEXT) return;
    if ((object->ownership & 7) == RC_REFERENCES) {
        ((MinyarList *)(object + 1))->capacity = (long long)cursor;
        return;
    }
#if defined(MINYAR_SYSTEM_HEAP) && MINYAR_OBJECT_SLOT_HEADERS
    ((RcSystemSlot *)object - 1)->value.bytes = cursor;
#else
    MinyarRecord *record = (MinyarRecord *)(object + 1);
    unsigned char *map = (unsigned char *)(record->values + record->length);
    size_t remaining = (size_t)record->length;
    for (size_t i = 0; remaining; i++, remaining >>= 7) {
        map[i] = (unsigned char)((map[i] & 1) | ((cursor & 127) << 1));
        cursor >>= 7;
    }
#endif
}

MINYAR_HOT void *rc_bounded_finish_object(RcObject *object, unsigned kind) {
    void *text_backing = NULL;
#if MINYAR_THREADED
    if (kind == 0) {
        RcThreadLeaf *leaf = (RcThreadLeaf *)(object + 1);
        leaf->release(leaf->control);
        RC_ACCOUNT(rc_bytes -= sizeof(*object) + sizeof(*leaf));
    } else
#endif
    if (kind == RC_TEXT) {
        MinyarText *text = (MinyarText *)(object + 1);
        text_backing = text->backing;
        if (!text_backing) rc_free_text_bytes(text);
        rc_free_data(text->character_offsets);
        RC_ACCOUNT(rc_bytes -= sizeof(*object) + sizeof(*text));
    } else if (kind == RC_LIST || kind == RC_REFERENCES || kind == RC_REFERENCES_IMMORTAL) {
        MinyarList *list = (MinyarList *)(object + 1);
        rc_free_data(list->values);
        RC_ACCOUNT(rc_bytes -= sizeof(*object) + sizeof(*list));
    } else {
#ifdef MINYAR_RC_TESTING
        MinyarRecord *record = (MinyarRecord *)(object + 1);
#endif
        RC_ACCOUNT(rc_bytes -= sizeof(*object) + sizeof(MinyarRecord)
                   + (size_t)record->length * (sizeof(long long) + (kind == RC_RECORD)));
    }
#if defined(MINYAR_RC_TESTING) && defined(MINYAR_RC_OBJECT_RELEASE_OBSERVER)
    MINYAR_RC_OBJECT_RELEASE_OBSERVER(object);
#endif
    RC_DEALLOCATE(object);
    RC_ACCOUNT(rc_object_count--);
    return text_backing;
}

#if defined(__GNUC__) || defined(__clang__)
#define RC_QUEUE_INLINE static inline __attribute__((always_inline))
#else
#define RC_QUEUE_INLINE static inline
#endif

/* rc_bounded_finish_object for a record with no queued fields, from a hot
 * site outside the scheduler (a `try` taking a Result's payload): the free
 * inlined (system heap). Testing builds keep the accounting and release
 * observer; the pool heap keeps its own free. */
RC_QUEUE_INLINE void rc_bounded_finish_record_fast(RcObject *object, unsigned kind) {
#if defined(MINYAR_SYSTEM_HEAP) && !defined(MINYAR_RC_TESTING)
    (void)kind;
    rc_heap_deallocate_fast(object);
#else
    rc_bounded_finish_object(object, kind);
#endif
}
#define RC_FINISH_RECORD_FAST(object, kind) rc_bounded_finish_record_fast((object), (kind))

/* A dead record's cursor, for callers that already know the kind: with slot
 * headers it is one load or store, without the kind tests above. */
RC_QUEUE_INLINE size_t rc_record_saved_cursor(RcObject *object) {
#if defined(MINYAR_SYSTEM_HEAP) && MINYAR_OBJECT_SLOT_HEADERS
    return ((RcSystemSlot *)object - 1)->value.bytes;
#else
    return rc_bounded_saved_cursor(object);
#endif
}

RC_QUEUE_INLINE void rc_record_save_cursor(RcObject *object, size_t cursor) {
#if defined(MINYAR_SYSTEM_HEAP) && MINYAR_OBJECT_SLOT_HEADERS
    ((RcSystemSlot *)object - 1)->value.bytes = cursor;
#else
    rc_bounded_save_cursor(object, cursor);
#endif
}

RC_QUEUE_INLINE void rc_bounded_enqueue_in(RcBoundedObjects *q, size_t *pending, RcObject *object) {
    rc_bounded_save_cursor(object, 0);
    object->ownership |= (size_t)(uintptr_t)q->recent_head;
    q->recent_head = object;
    if (!q->recent_tail) q->recent_tail = object;
    ++*pending;
}

MINYAR_HOT void rc_bounded_enqueue(RcObject *object) {
    rc_bounded_enqueue_in(&rc_objects, &rc_pending_count, object);
}

RC_QUEUE_INLINE unsigned rc_drop_in(RcBoundedObjects *q, size_t *pending, void *value) {
    if (!value) return 0;
    RcObject *object = (RcObject *)value - 1;
    size_t ownership = object->ownership;
    /* Most releases leave another owner: decrement before any kind test. */
    if (ownership >= 16) {
        object->ownership = ownership - 8;
        return 0;
    }
    /* Exactly one owner and no child fields: no zero-count store or broad
     * kind dispatch is needed before returning this allocation. */
    if (ownership == (8 | RC_LIST)) {
        rc_bounded_finish_object(object, RC_LIST);
        return 1;
    }
    if (ownership == (8 | RC_SCALAR_RECORD)) {
        rc_bounded_finish_object(object, RC_SCALAR_RECORD);
        return 1;
    }
    if (ownership < 8) return 0; /* Immortal literal or cache. */
    object->ownership = ownership - 8;
    unsigned kind = object->ownership & 7;
#if MINYAR_THREADED
    if (kind == 0) {
        rc_bounded_finish_object(object, kind);
        return 1;
    }
#endif
    if (kind == RC_TEXT) {
        void *backing = rc_bounded_finish_object(object, kind);
        /* A view owns a direct reference to an owning Text, never another
         * view. Its destruction already costs one unit. Decrement the root
         * without destroying a second object in that unit; a newly dead root
         * becomes a fieldless task in the existing object queue. */
        if (backing) {
            RcObject *root = (RcObject *)backing - 1;
            if (root->ownership >> 3) {
                root->ownership -= 8;
                if (!(root->ownership >> 3)) rc_bounded_enqueue_in(q, pending, root);
            }
        }
        return 1;
    }
    /* The usual interior node of a dead graph becomes a recent task with its
     * cursor stored without the generic kind tests. */
    if (kind == RC_RECORD && ((MinyarRecord *)(object + 1))->length) {
        rc_record_save_cursor(object, 0);
        object->ownership = RC_RECORD | (size_t)(uintptr_t)q->recent_head;
        q->recent_head = object;
        if (!q->recent_tail) q->recent_tail = object;
        ++*pending;
        return 0;
    }
    if (kind == RC_LIST || kind == RC_REFERENCES_IMMORTAL ||
        (kind == RC_REFERENCES && !((MinyarList *)(object + 1))->length) ||
        (kind == RC_RECORD && !((MinyarRecord *)(object + 1))->length)) {
        rc_bounded_finish_object(object, kind);
        return 1;
    }
    rc_bounded_enqueue_in(q, pending, object);
    return 0;
}

MINYAR_HOT unsigned rc_drop(void *value) {
    return rc_drop_in(&rc_objects, &rc_pending_count, value);
}

static MINYAR_THREAD_LOCAL RcFrame *rc_bounded_frame_head, *rc_bounded_frame_tail;
static MINYAR_THREAD_LOCAL RcTemporaryChunk *rc_bounded_chunk_head, *rc_bounded_chunk_tail;
static MINYAR_THREAD_LOCAL unsigned rc_bounded_next_queue;

static void rc_bounded_retire_temporaries(RcFrame *frame) {
    if (!frame->temporary_head) return;
    if (rc_bounded_chunk_tail) rc_bounded_chunk_tail->next = frame->temporary_head;
    else rc_bounded_chunk_head = frame->temporary_head;
    rc_bounded_chunk_tail = frame->temporary_tail;
    size_t chunks = frame->temporary_count / RC_TEMPORARY_CHUNK_SLOTS
                  + (frame->temporary_count % RC_TEMPORARY_CHUNK_SLOTS != 0);
    rc_pending_count += chunks;
    rc_bounded_owner_tasks += chunks;
    frame->temporary_head = frame->temporary_tail = NULL;
    frame->temporary_count = 0;
}

#if defined(__GNUC__) || defined(__clang__)
#define RC_BOUNDED_INLINE static inline __attribute__((always_inline))
#else
#define RC_BOUNDED_INLINE static inline
#endif

RC_BOUNDED_INLINE void rc_bounded_old_object_unit_in(RcBoundedObjects *q, size_t *pending) {
    if (!q->active) {
        q->active = q->head;
        q->head = (RcObject *)(uintptr_t)(q->active->ownership & ~(size_t)7);
        if (!q->head) q->tail = NULL;
        q->active->ownership &= 7;
        q->cursor = (q->active->ownership & 7) == RC_RECORD ? rc_record_saved_cursor(q->active)
                                                             : rc_bounded_saved_cursor(q->active);
    }
    RcObject *object = q->active;
    unsigned kind = object->ownership & 7;
    if (kind == RC_RECORD) {
        MinyarRecord *record = (MinyarRecord *)(object + 1);
        if (q->cursor < (size_t)record->length) {
            unsigned char *map = (unsigned char *)(record->values + record->length);
            size_t index = q->cursor++;
            if (map[index] & 1) rc_drop_in(q, pending, (void *)(uintptr_t)record->values[index]);
            return;
        }
    } else if (kind == RC_REFERENCES) {
        MinyarList *list = (MinyarList *)(object + 1);
        if (q->cursor < (size_t)list->length) {
            rc_drop_in(q, pending, (void *)(uintptr_t)list->values[q->cursor++]);
            return;
        }
    }
    /* A Text task can hold a shared backing (a Text view of frozen storage).
     * finish returns that backing instead of freeing it; release it here, so a
     * queued view task cannot drop an owning root on the floor. */
    void *backing = rc_bounded_finish_object(object, kind);
    --*pending;
    q->active = NULL;
    if (backing) rc_drop_in(q, pending, backing);
}

/* A recent task remains linked while visiting its next owner. Saving the
 * cursor before dropping that owner lets newly dead children preempt it without
 * recursion or an auxiliary allocation. */
RC_BOUNDED_INLINE void rc_bounded_recent_object_unit_in(RcBoundedObjects *q, size_t *pending) {
    RcObject *object = q->recent_head;
    unsigned kind = object->ownership & 7;
    if (kind == RC_RECORD) {
        MinyarRecord *record = (MinyarRecord *)(object + 1);
        size_t cursor = rc_record_saved_cursor(object);
        if (cursor < (size_t)record->length) {
            unsigned char *map = (unsigned char *)(record->values + record->length);
            void *child = (map[cursor] & 1) ? (void *)(uintptr_t)record->values[cursor] : NULL;
            rc_record_save_cursor(object, cursor + 1);
            rc_drop_in(q, pending, child);
            return;
        }
        q->recent_head = (RcObject *)(uintptr_t)(object->ownership & ~(size_t)7);
        if (!q->recent_head) q->recent_tail = NULL;
        rc_bounded_finish_object(object, RC_RECORD);
        --*pending;
        return;
    }
    size_t cursor = rc_bounded_saved_cursor(object);
    if (kind == RC_REFERENCES) {
        MinyarList *list = (MinyarList *)(object + 1);
        if (cursor < (size_t)list->length) {
            void *child = (void *)(uintptr_t)list->values[cursor];
            rc_bounded_save_cursor(object, cursor + 1);
            rc_drop_in(q, pending, child);
            return;
        }
    }
    q->recent_head = (RcObject *)(uintptr_t)(object->ownership & ~(size_t)7);
    if (!q->recent_head) q->recent_tail = NULL;
    void *backing = rc_bounded_finish_object(object, kind);
    --*pending;
    if (backing) rc_drop_in(q, pending, backing);
}

/* Reserve alternating object units for the oldest finite batch. Whenever that
 * batch is exhausted, capture the recent stack in O(1). New arrivals cannot
 * enter the captured batch, so every captured task has finite predecessors.
 * Recent service follows freshly dead children promptly, while oldest service
 * cannot be starved by a stream of new tasks. */
RC_BOUNDED_INLINE void rc_bounded_object_unit_in(RcBoundedObjects *q, size_t *pending) {
    if (!q->active && !q->head) {
        q->head = q->recent_head;
        q->tail = q->recent_tail;
        q->recent_head = q->recent_tail = NULL;
    }
    unsigned recent = q->recent_turn;
    q->recent_turn ^= 1;
    if (recent && q->recent_head) {
        /* Finish the sole captured unary parent before its recent child.
         * This is still one unit. With no captured successors, the next
         * object unit captures the recent stack and services its head, so
         * recent progress is delayed by at most one object unit here. */
        RcObject *active = q->active;
        if (q->cursor == 1 && !q->head && active &&
            (active->ownership & 7) == RC_RECORD &&
            ((MinyarRecord *)(active + 1))->length == 1)
            rc_bounded_old_object_unit_in(q, pending);
        else rc_bounded_recent_object_unit_in(q, pending);
    } else rc_bounded_old_object_unit_in(q, pending);
}

RC_BOUNDED_INLINE void rc_bounded_object_unit(void) {
    rc_bounded_object_unit_in(&rc_objects, &rc_pending_count);
}

#undef RC_BOUNDED_INLINE

/* A retired frame's owners are all released: keep it for reuse within the
 * cache allowance, otherwise free it. */
static void rc_bounded_cache_frame(RcFrame *frame) {
    size_t bytes = rc_heap_charge(frame, sizeof(*frame));
    if (frame->locals) bytes += rc_heap_charge(frame->locals, frame->local_capacity * (sizeof(void *) + sizeof(size_t)));
    if (bytes <= MINYAR_FRAME_CACHE_BYTES &&
        rc_bounded_cached_frame_bytes <= MINYAR_FRAME_CACHE_BYTES - bytes) {
        frame->previous = rc_free_frames;
        rc_free_frames = frame;
        rc_bounded_cached_frame_bytes += bytes;
    } else {
        rc_heap_deallocate(frame->locals);
        rc_heap_deallocate(frame);
    }
}

static void rc_bounded_frame_unit(void) {
    RcFrame *frame = rc_bounded_frame_head;
    if (frame->local_count) {
        size_t index = rc_bounded_local_indices(frame)[--frame->local_count];
        void *value = rc_bounded_local_value(frame, index);
        /* A completed frame is already initialized for its next activation. */
        frame->locals[index] = NULL;
        rc_drop(value);
        return;
    }
    rc_bounded_frame_head = frame->previous;
    if (!rc_bounded_frame_head) rc_bounded_frame_tail = NULL;
    rc_bounded_cache_frame(frame);
    rc_pending_count--;
    rc_bounded_owner_tasks--;
}

static void rc_bounded_chunk_unit(void) {
    RcTemporaryChunk *chunk = rc_bounded_chunk_head;
    if (chunk->count) {
        rc_drop(chunk->values[--chunk->count]);
        return;
    }
    rc_bounded_chunk_head = chunk->next;
    if (!rc_bounded_chunk_head) rc_bounded_chunk_tail = NULL;
    rc_bounded_chunk_retire(chunk);
    rc_pending_count--;
    rc_bounded_owner_tasks--;
}

/* Round-robin service across three queues: every continuously ready queue
 * receives one unit within three units, including when the poll budget is 1.
 * Here rc_pending_count counts the selected instance's objects plus the
 * detached frames and temporary chunks (rc_bounded_poll_work excludes the
 * backlog's tasks while it runs). The caller limits budget to K. */
static size_t rc_bounded_schedule(size_t budget) {
    size_t work = 0;
    if (!rc_bounded_frame_head && !rc_bounded_chunk_head) {
        /* Run on a local copy of the object queue so its state stays in
         * registers across frees; publish it once below. Units here only
         * touch the object queue (no frame or chunk task can appear). */
        RcBoundedObjects local = rc_objects, *q = &local;
        size_t queued = rc_pending_count, *pending = &queued;
        /* Object processing can only enqueue objects. With no frame/chunk
         * tasks, skip repeated three-way selection for this entire poll.
         * Match the general scheduler's next queue after any object work;
         * empty and zero-budget polls leave that state unchanged. */
        while (work < budget && (*pending)) {
            /* With one unvisited unary record, locality makes its field visit
             * and finalization the next two units. There is no competing old
             * task to bypass, and dropping one child creates at most one task.
             * Keep per-unit state updates around rc_drop in reference order. */
            if ((*pending) == 1 && !q->active && budget - work >= 2) {
                RcObject *single = q->head ? q->head : q->recent_head;
                if (single && (single->ownership & 7) == RC_RECORD) {
                    MinyarRecord *record = (MinyarRecord *)(single + 1);
                    if (record->length == 1) {
                        unsigned char *map = (unsigned char *)(record->values + 1);
                        if (!rc_bounded_saved_cursor(single)) {
                            q->head = q->tail = NULL;
                            q->recent_head = q->recent_tail = NULL;
                            single->ownership = RC_RECORD;
                            q->active = single;
                            q->cursor = 1;
                            for (;;) {
                                RcObject *next = NULL;
                                /* Carry a unique unary child only when this
                                 * poll can also finish its next pair. The final
                                 * pair publishes normal queue/count state, so
                                 * an odd budget still resumes identically.
                                 * Intermediate dead ownership is local to this
                                 * non-reentrant poll, with no competing tasks. */
                                if (budget - work >= 4 && (map[0] & 1) && record->values[0]) {
                                    RcObject *child = (RcObject *)(uintptr_t)record->values[0] - 1;
                                    if (child->ownership == (8 | RC_RECORD) &&
                                        ((MinyarRecord *)(child + 1))->length == 1)
                                        next = child;
                                }
                                if (next) {
                                    /* Live maps contain flags0/1, hence their
                                     * saved cursor is already zero. No queue or
                                     * cursor initialization is needed in transit. */
                                    next->ownership = RC_RECORD;
                                    rc_bounded_finish_object(single, RC_RECORD);
                                    work += 2;
                                    single = next;
                                    record = (MinyarRecord *)(single + 1);
                                    map = (unsigned char *)(record->values + 1);
                                    q->active = single;
                                    continue;
                                }
                                q->recent_turn ^= 1;
                                if (map[0] & 1) rc_drop_in(q, pending, (void *)(uintptr_t)record->values[0]);
                                q->recent_turn ^= 1;
                                rc_bounded_finish_object(single, RC_RECORD);
                                --*pending;
                                q->active = NULL;
                                work += 2;
                                break;
                            }
                            continue;
                        }
                    }
                }
            }

            if (!q->recent_head && q->active &&
                (q->active->ownership & 7) == RC_RECORD) {
                MinyarRecord *record = (MinyarRecord *)(q->active + 1);
                unsigned char *map = (unsigned char *)(record->values + record->length);
                size_t available = (size_t)record->length - q->cursor;
                size_t count = budget - work;
                if (count > available) count = available;
                size_t end = q->cursor + count;
                while (q->cursor < end) {
                    q->recent_turn ^= 1;
                    size_t index = q->cursor++;
                    work++;
                    if (map[index] & 1) rc_drop_in(q, pending, (void *)(uintptr_t)record->values[index]);
                    if (q->recent_head) break;
                }
                if (count) {

                    if (!q->recent_head && q->cursor == (size_t)record->length &&
                        work < budget) {
                        RcObject *finished = q->active;
                        q->recent_turn ^= 1;
                        rc_bounded_finish_object(finished, RC_RECORD);
                        --*pending;
                        q->active = NULL;
                        work++;
                    }
                    continue;
                }
            }
            /* A ready recent task must preserve alternating service. Without
             * one, consume a bounded run of the active List's owner slots.
             * A newly dead nonleaf immediately ends this run, restoring the
             * ordinary scheduler before any further work. */
            if (!q->recent_head && q->active &&
                (q->active->ownership & 7) == RC_REFERENCES) {
                MinyarList *list = (MinyarList *)(q->active + 1);
                size_t available = (size_t)list->length - q->cursor;
                size_t count = budget - work;
                if (count > available) count = available;
                size_t end = q->cursor + count;
                while (q->cursor < end) {
                    q->recent_turn ^= 1;
                    void *value = (void *)(uintptr_t)list->values[q->cursor++];
                    RcObject *child = value ? (RcObject *)value - 1 : NULL;
                    work++;
                    /* Inline only the common unique scalar leaf. Its free
                     * cannot create a recent task; other owners retain the
                     * generic decrement and immediate queue-stop check. */
                    if (child && child->ownership == (8 | RC_SCALAR_RECORD))
                        rc_bounded_finish_object(child, RC_SCALAR_RECORD);
                    else {
                        rc_drop_in(q, pending, value);
                        if (q->recent_head) break;
                    }
                }
                if (count) continue;
            }
            rc_bounded_object_unit_in(q, pending);
            work++;
        }
        rc_objects = local;
        rc_pending_count = queued;
        if (work) rc_bounded_next_queue = 1;
    } else {
        while (work < budget && rc_pending_count) {
            unsigned queue = rc_bounded_next_queue;
            unsigned objects = rc_bounded_active || rc_bounded_head || rc_bounded_recent_head;
            if (queue == 0) {
                if (!objects) queue = rc_bounded_frame_head ? 1 : 2;
            } else if (queue == 1) {
                if (!rc_bounded_frame_head) queue = rc_bounded_chunk_head ? 2 : 0;
            } else if (!rc_bounded_chunk_head) queue = objects ? 0 : 1;
            if (queue == 0) {
                rc_bounded_next_queue = 1;
                rc_bounded_object_unit();
            } else if (queue == 1) {
                rc_bounded_next_queue = 2;
                rc_bounded_frame_unit();
            } else {
                rc_bounded_next_queue = 0;
                rc_bounded_chunk_unit();
            }
            work++;
        }
    }
    return work;
}

static void rc_bounded_swap_objects(void) {
    RcBoundedObjects fresh = {rc_bounded_head, rc_bounded_tail, rc_bounded_active,
                              rc_bounded_recent_head, rc_bounded_recent_tail,
                              rc_bounded_cursor, rc_bounded_recent_turn};
    rc_bounded_head = rc_backlog.head;
    rc_bounded_tail = rc_backlog.tail;
    rc_bounded_active = rc_backlog.active;
    rc_bounded_recent_head = rc_backlog.recent_head;
    rc_bounded_recent_tail = rc_backlog.recent_tail;
    rc_bounded_cursor = rc_backlog.cursor;
    rc_bounded_recent_turn = rc_backlog.recent_turn;
    rc_backlog = fresh;
}

/* Up to budget backlog units through the object scheduler. Fresh frames and
 * chunks are hidden meanwhile, and their queue turn is kept. */
#if defined(__GNUC__) || defined(__clang__)
__attribute__((noinline))
#endif
static size_t rc_bounded_backlog_work(size_t budget) {
    RcFrame *frame_head = rc_bounded_frame_head, *frame_tail = rc_bounded_frame_tail;
    RcTemporaryChunk *chunk_head = rc_bounded_chunk_head, *chunk_tail = rc_bounded_chunk_tail;
    unsigned next_queue = rc_bounded_next_queue;
    size_t fresh = rc_pending_count;
    rc_bounded_frame_head = rc_bounded_frame_tail = NULL;
    rc_bounded_chunk_head = rc_bounded_chunk_tail = NULL;
    rc_bounded_swap_objects();
    rc_pending_count = rc_backlog_count;
    size_t work = rc_bounded_schedule(budget);
    rc_backlog_count = rc_pending_count;
    rc_pending_count = fresh;
    rc_bounded_swap_objects();
    rc_bounded_frame_head = frame_head;
    rc_bounded_frame_tail = frame_tail;
    rc_bounded_chunk_head = chunk_head;
    rc_bounded_chunk_tail = chunk_tail;
    rc_bounded_next_queue = next_queue;
    return work;
}

/* Fresh object tasks still pending when their service point ends join the
 * backlog's captured FIFO in the order the fresh scheduler would have served
 * them: recent stack, then the active object with its cursor, then the
 * captured batch. Constant work. */
static void rc_bounded_link(RcObject **first, RcObject **last, RcObject *head, RcObject *tail) {
    if (!head) return;
    if (*last) (*last)->ownership = ((*last)->ownership & 7) | (size_t)(uintptr_t)head;
    else *first = head;
    *last = tail;
}

static void rc_bounded_defer_objects(void) {
    if (!rc_backlog_count) {
        /* An empty backlog continues exactly where the fresh scheduler
         * stopped; the fresh queue keeps its alternation parity. */
        rc_backlog = (RcBoundedObjects){rc_bounded_head, rc_bounded_tail, rc_bounded_active,
                                        rc_bounded_recent_head, rc_bounded_recent_tail,
                                        rc_bounded_cursor, rc_bounded_recent_turn};
        rc_backlog_count = rc_pending_count - rc_bounded_owner_tasks;
        rc_pending_count = rc_bounded_owner_tasks;
        rc_bounded_head = rc_bounded_tail = rc_bounded_active = NULL;
        rc_bounded_recent_head = rc_bounded_recent_tail = NULL;
        return;
    }
    RcObject *first = NULL, *last = NULL;
    rc_bounded_link(&first, &last, rc_bounded_recent_head, rc_bounded_recent_tail);
    if (rc_bounded_active) {
        rc_bounded_save_cursor(rc_bounded_active, rc_bounded_cursor);
        rc_bounded_link(&first, &last, rc_bounded_active, rc_bounded_active);
    }
    rc_bounded_link(&first, &last, rc_bounded_head, rc_bounded_tail);
    RcObject *backlog_first = rc_backlog.head, *backlog_last = rc_backlog.tail;
    rc_bounded_link(&backlog_first, &backlog_last, first, last);
    rc_backlog.head = backlog_first;
    rc_backlog.tail = backlog_last;
    rc_backlog_count += rc_pending_count - rc_bounded_owner_tasks;
    rc_pending_count = rc_bounded_owner_tasks;
    rc_bounded_head = rc_bounded_tail = rc_bounded_active = NULL;
    rc_bounded_recent_head = rc_bounded_recent_tail = NULL;
}

/* The backlog earns MINYAR_RC_BACKLOG_BUDGET units of credit at each managed
 * allocation (object, data or resize) that finds it pending, up to K, and
 * spends the credit in one batch once a whole budget has accrued. Reclamation
 * of old work therefore keeps pace with allocation, at most that share per
 * allocation on average, while every other service point keeps its fast path
 * and each batch costs one scheduler entry. */
static inline size_t rc_bounded_backlog_allowance(void) {
    size_t credit = rc_backlog_credit + MINYAR_RC_BACKLOG_BUDGET;
    if (credit >= MINYAR_RC_POLL_BUDGET) credit = MINYAR_RC_POLL_BUDGET;
    rc_backlog_credit = credit;
    return credit == MINYAR_RC_POLL_BUDGET ? credit : 0;
}

/* One service point. Fresh work (frames, temporary chunks and objects queued
 * since the last service point) receives the budget; when the backlog may
 * work here, it first reserves min(budget, MINYAR_RC_BACKLOG_BUDGET) units
 * and then receives what fresh work leaves, up to allowance. Fresh objects
 * still pending become backlog. Out of line, like the scheduler: the inline
 * service entries must stay a pending-count test and a call. */
#if defined(__GNUC__) || defined(__clang__)
__attribute__((noinline))
#endif
static size_t rc_bounded_service(size_t budget, size_t allowance) {
    if (budget > MINYAR_RC_POLL_BUDGET) budget = MINYAR_RC_POLL_BUDGET;
    size_t share = 0;
    if (rc_backlog_count && allowance)
        share = budget < MINYAR_RC_BACKLOG_BUDGET ? budget : MINYAR_RC_BACKLOG_BUDGET;
    size_t work = rc_bounded_schedule(budget - share);
    if (share) {
        size_t limit = budget - work;
        if (limit > allowance) limit = allowance;
        size_t done = rc_bounded_backlog_work(limit);
        work += done;
        rc_backlog_credit = done < rc_backlog_credit ? rc_backlog_credit - done : 0;
        if (!rc_backlog_count) rc_backlog_credit = 0;
    }
    /* Object work still pending gets one more full service point; what
     * survives that becomes backlog. Drops that fit in 2K units keep exactly
     * the unpaced schedule. */
    if (MINYAR_RC_BACKLOG_BUDGET) {
        if (rc_pending_count == rc_bounded_owner_tasks) rc_bounded_fresh_aged = 0;
        else if (!rc_bounded_fresh_aged) rc_bounded_fresh_aged = 1;
        else {
            rc_bounded_defer_objects();
            rc_bounded_fresh_aged = 0;
        }
    }
#ifdef MINYAR_RC_TESTING
    rc_bounded_last_work = work;
#endif
    return work;
}

#if defined(__GNUC__) || defined(__clang__)
__attribute__((noinline))
#endif
static size_t rc_bounded_poll_work(size_t budget) {
    return rc_bounded_service(budget, 0);
}

/* Every queue holds pending work, so with nothing pending a poll does no work
 * and changes no state. Keep that constant-time test inline: generated code
 * polls at every loop iteration and call, and almost always finds nothing.
 * The backlog is not counted here: only allocations and idle points serve it. */
size_t minyar_rc_poll(size_t budget) {
    if (!rc_pending_count) {
#ifdef MINYAR_RC_TESTING
        rc_bounded_last_work = 0;
#endif
        return 0;
    }
    return rc_bounded_poll_work(budget);
}

/* The service point of a managed allocation. */
#if MINYAR_RC_BACKLOG_BUDGET
#if defined(__GNUC__) || defined(__clang__)
__attribute__((noinline))
#endif
static size_t rc_bounded_allocation_work(size_t budget) {
    size_t allowance = rc_backlog_count ? rc_bounded_backlog_allowance() : 0;
    if (!allowance && !rc_pending_count) {
#ifdef MINYAR_RC_TESTING
        rc_bounded_last_work = 0;
#endif
        return 0;
    }
    return rc_bounded_service(budget, allowance);
}
#endif

/* An idle service point (a sleep, or an event loop about to wait): the same
 * K limit, but the backlog may use all of it. */
size_t minyar_rc_poll_idle(size_t budget) {
    if (!rc_pending_count && !rc_backlog_count) {
#ifdef MINYAR_RC_TESTING
        rc_bounded_last_work = 0;
#endif
        return 0;
    }
    return rc_bounded_service(budget, MINYAR_RC_POLL_BUDGET);
}

/* Direct frame exit and statement cleanup perform what one poll would; test
 * probes that count poll work observe them here with the same total.
 * MINYAR_RC_DIRECT_SERVICE=0 sends them through the scheduler instead, the
 * reference for tests/direct-service-transcript.c. */
#ifndef MINYAR_RC_DIRECT_SERVICE
#define MINYAR_RC_DIRECT_SERVICE 1
#endif
#ifndef MINYAR_RC_DIRECT_SERVICE_OBSERVER
#define MINYAR_RC_DIRECT_SERVICE_OBSERVER(work) ((void)(work))
#endif

/* Frame exit that also retires the frame's statement temporaries, with
 * nothing else pending. The scheduler would
 * alternate the frame queue and the chunk queue from its current turn: frame
 * units visit the written slots in reverse order and then retire the frame;
 * chunk units release owners newest first, then retire each chunk, oldest
 * chunk first. Do exactly that here, with the same queue turns. If a release
 * queues an object, queue what remains and continue in the scheduler. */
#if defined(__GNUC__) || defined(__clang__)
__attribute__((noinline))
#endif
static int rc_bounded_leave_mixed(RcFrame *frame) {
    size_t chunks = frame->temporary_count / RC_TEMPORARY_CHUNK_SLOTS
                  + (frame->temporary_count % RC_TEMPORARY_CHUNK_SLOTS != 0);
    if (frame->written_count + 1 + frame->temporary_count + chunks > MINYAR_RC_POLL_BUDGET ||
        rc_pending_count) return 0;
    RcTemporaryChunk *chunk = frame->temporary_head, *tail = frame->temporary_tail;
    frame->temporary_head = frame->temporary_tail = NULL;
    frame->temporary_count = 0;
    frame->local_count = frame->written_count;
    size_t pending = rc_pending_count;
    size_t work = 0;
    unsigned queue = rc_bounded_next_queue;
    int live = 1;
    while (live || chunk) {
        /* rc_bounded_schedule's queue choice when no object is pending. */
        if (queue == 0) queue = live ? 1 : 2;
        else if (queue == 1) { if (!live) queue = 2; }
        else if (!chunk) queue = 1;
        if (queue == 1) {
            queue = 2;
            if (frame->local_count) {
                size_t index = rc_bounded_local_indices(frame)[--frame->local_count];
                void *value = rc_bounded_local_value(frame, index);
                frame->locals[index] = NULL;
                rc_drop(value);
            } else {
                rc_bounded_cache_frame(frame);
                live = 0;
            }
        } else {
            queue = 0;
            if (chunk->count) rc_drop(chunk->values[--chunk->count]);
            else {
                RcTemporaryChunk *next = chunk->next;
                rc_bounded_chunk_retire(chunk);
                chunks--;
                chunk = next;
            }
        }
        work++;
        if (rc_pending_count != pending) {
            if (live) {
                frame->previous = NULL;
                rc_bounded_frame_head = rc_bounded_frame_tail = frame;
                rc_pending_count++;
                rc_bounded_owner_tasks++;
            }
            if (chunk) {
                rc_bounded_chunk_head = chunk;
                rc_bounded_chunk_tail = tail;
                rc_pending_count += chunks;
                rc_bounded_owner_tasks += chunks;
            }
            rc_bounded_next_queue = queue;
            size_t more = rc_bounded_service(MINYAR_RC_POLL_BUDGET - work, 0);
#ifdef MINYAR_RC_TESTING
            rc_bounded_last_work = work + more;
#endif
            MINYAR_RC_DIRECT_SERVICE_OBSERVER(work + more);
            return 1;
        }
    }
    rc_bounded_next_queue = queue;
#ifdef MINYAR_RC_TESTING
    rc_bounded_last_work = work;
#endif
    MINYAR_RC_DIRECT_SERVICE_OBSERVER(work);
    return 1;
}

/* Frame exit with nothing else pending, the commonest service point. The
 * scheduler would give this frame every unit: one per written owner slot, in
 * reverse order, then one to retire it. Do exactly that here without queueing
 * the frame or entering the general scheduler. If a release queues an object,
 * link the frame with its remaining slots and continue in the scheduler from
 * the state it would have reached. Returns 0 when the general path must run. */
static int rc_bounded_leave_direct(RcFrame *frame) {
    if (!MINYAR_RC_DIRECT_SERVICE) return 0;
    if (frame->temporary_head) return rc_bounded_leave_mixed(frame);
    if (rc_pending_count || frame->written_count >= MINYAR_RC_POLL_BUDGET) return 0;
    size_t pending = rc_pending_count;
    size_t work = 0;
    frame->local_count = frame->written_count;
    rc_bounded_next_queue = 2;
    while (frame->local_count) {
        size_t index = rc_bounded_local_indices(frame)[--frame->local_count];
        void *value = rc_bounded_local_value(frame, index);
        /* A completed frame is already initialized for its next activation. */
        frame->locals[index] = NULL;
        rc_drop(value);
        work++;
        if (rc_pending_count != pending) {
            frame->previous = NULL;
            rc_bounded_frame_head = rc_bounded_frame_tail = frame;
            rc_pending_count++;
            rc_bounded_owner_tasks++;
            size_t more = rc_bounded_service(MINYAR_RC_POLL_BUDGET - work, 0);
#ifdef MINYAR_RC_TESTING
            rc_bounded_last_work = work + more;
#endif
            MINYAR_RC_DIRECT_SERVICE_OBSERVER(work + more);
            return 1;
        }
    }
    rc_bounded_cache_frame(frame);
#ifdef MINYAR_RC_TESTING
    rc_bounded_last_work = work + 1;
#endif
    MINYAR_RC_DIRECT_SERVICE_OBSERVER(work + 1);
    return 1;
}

/* Statement cleanup with nothing else pending. The scheduler would give the
 * statement's temporary chunks every unit: one per owner, newest first, then
 * one to retire each chunk, oldest chunk first. Do exactly that here; if a
 * release queues an object, queue the remaining chunks and continue in the
 * scheduler from the state it would have reached. */
#if defined(__GNUC__) || defined(__clang__)
__attribute__((noinline))
#endif
static int rc_bounded_step_chunks(RcFrame *frame) {
    if (!MINYAR_RC_DIRECT_SERVICE) return 0;
    RcTemporaryChunk *chunk = frame->temporary_head;
    size_t chunks = frame->temporary_count / RC_TEMPORARY_CHUNK_SLOTS
                  + (frame->temporary_count % RC_TEMPORARY_CHUNK_SLOTS != 0);
    if (frame->temporary_count + chunks > MINYAR_RC_POLL_BUDGET) return 0;
    RcTemporaryChunk *tail = frame->temporary_tail;
    frame->temporary_head = frame->temporary_tail = NULL;
    frame->temporary_count = 0;
    size_t pending = rc_pending_count;
    size_t work = 0;
    rc_bounded_next_queue = 0;
    while (chunk) {
        while (chunk->count) {
            rc_drop(chunk->values[--chunk->count]);
            work++;
            if (rc_pending_count != pending) {
                rc_bounded_chunk_head = chunk;
                rc_bounded_chunk_tail = tail;
                rc_pending_count += chunks;
                rc_bounded_owner_tasks += chunks;
                size_t more = rc_bounded_service(MINYAR_RC_POLL_BUDGET - work, 0);
#ifdef MINYAR_RC_TESTING
                rc_bounded_last_work = work + more;
#endif
                MINYAR_RC_DIRECT_SERVICE_OBSERVER(work + more);
                return 1;
            }
        }
        RcTemporaryChunk *next = chunk->next;
        rc_bounded_chunk_retire(chunk);
        chunks--;
        work++;
        chunk = next;
    }
#ifdef MINYAR_RC_TESTING
    rc_bounded_last_work = work;
#endif
    MINYAR_RC_DIRECT_SERVICE_OBSERVER(work);
    return 1;
}

#if defined(__GNUC__) || defined(__clang__)
__attribute__((noinline))
#endif
static void rc_bounded_release(void *value) {
    unsigned immediate = rc_drop(value);
    rc_service_pending(immediate < MINYAR_RC_POLL_BUDGET
                       ? MINYAR_RC_POLL_BUDGET - immediate : 0);
#ifdef MINYAR_RC_TESTING
    rc_bounded_last_work += immediate;
#endif
}

/* Most releases leave another owner: that decrement and the following
 * service point's pending test are inlined into callers (generated code and
 * scope releases); a last owner, an immortal value and NULL take the general
 * body. Same units and service as the general body. */
MINYAR_INLINE_ENTRY void minyar_rc_release(void *value) {
    if (value) {
        RcObject *object = (RcObject *)value - 1;
        size_t ownership = object->ownership;
        if (ownership >= 16) {
            object->ownership = ownership - 8;
            rc_service_pending(MINYAR_RC_POLL_BUDGET);
            return;
        }
    }
    rc_bounded_release(value);
}
