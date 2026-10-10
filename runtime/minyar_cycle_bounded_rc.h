/* Adapted from port/astra-cycles-v2 at 976a75a8c51518006cb654d6e6304f425e2eab91.
 * Selected only by the separate cycle runtime; ordinary runtime files retain
 * their original implementation. See docs/managed-graphs.md. */
/* Finite-heap profile: no allocation in the pending queue:
 * a dead object's header becomes a tagged recent-stack or captured-batch link.
 * Its payload is retained until a cursor has processed every field. Only
 * zero-count objects enter the object queue; detached frames and temporary
 * chunks have separate queues.
 * A work unit visits one owner/field or retires one task (up to three frees).
 * Pool frees have at most log2(heap/minimum-block) merge steps. System
 * allocator calls have no runtime-imposed execution-time bound.
 * Work bounds exclude startup, data copying and OS scheduling/page faults. */
static RcObject *rc_bounded_head, *rc_bounded_tail, *rc_bounded_active;
static size_t rc_bounded_cursor;
#define MINYAR_RC_RECENT_OBJECTS 1
static RcObject *rc_bounded_recent_head, *rc_bounded_recent_tail;
static unsigned rc_bounded_recent_turn;

/* Dead List capacity is spare. Dead record map bytes retain their low-bit
 * reference flag and store seven cursor bits each. The loop executes at most
 * ceil(sizeof(size_t)*CHAR_BIT/7) iterations, independent of graph size. */
static size_t rc_bounded_saved_cursor(RcObject *object) {
    if ((object->ownership & 7) == RC_TEXT) return 0;
    if ((object->ownership & 7) == RC_REFERENCES || rc_kind(object) == RC_REFERENCES)
        return (size_t)((MinyarList *)(object + 1))->capacity;
    MinyarRecord *record = (MinyarRecord *)(object + 1);
    unsigned char *map = (unsigned char *)(record->values + record->length);
    size_t cursor = 0;
    for (size_t i = 0; i < (size_t)record->length && i * 7 < sizeof(size_t) * CHAR_BIT; i++)
        cursor |= (size_t)(map[i] >> 1) << (i * 7);
    return cursor;
}

static void rc_bounded_save_cursor(RcObject *object, size_t cursor) {
    if ((object->ownership & 7) == RC_TEXT) return;
    if ((object->ownership & 7) == RC_REFERENCES || rc_kind(object) == RC_REFERENCES) {
        ((MinyarList *)(object + 1))->capacity = (long long)cursor;
        return;
    }
    MinyarRecord *record = (MinyarRecord *)(object + 1);
    unsigned char *map = (unsigned char *)(record->values + record->length);
    for (size_t i = 0; i < (size_t)record->length && i * 7 < sizeof(size_t) * CHAR_BIT; i++) {
        map[i] = (unsigned char)((map[i] & 1) | ((cursor & 127) << 1));
        cursor >>= 7;
    }
}

/* A dead RC_TRACED object frees from its cycle metadata. */
static inline void rc_bounded_finish_traced(RcObject *object) {
    RcCycle *cycle = rc_cycle_metadata(object);
    if (cycle->record) {
#ifdef MINYAR_RC_TESTING
        MinyarRecord *record = (MinyarRecord *)(object + 1);
#endif
        RC_ACCOUNT(rc_bytes -= sizeof(*object) + sizeof(MinyarRecord)
                   + (size_t)record->length * (sizeof(long long) + 1));
    } else {
        MinyarList *list = (MinyarList *)(object + 1);
        rc_free_data(list->values);
        RC_ACCOUNT(rc_bytes -= sizeof(*object) + sizeof(*list));
    }
    RC_ACCOUNT(rc_bytes -= sizeof(RcCycle));
    RC_DEALLOCATE(cycle);
    RC_ACCOUNT(rc_object_count--);
}

static void *rc_bounded_finish_object(RcObject *object, unsigned kind) {
    if (kind == RC_TRACED) {
        rc_bounded_finish_traced(object);
        return NULL;
    }
    void *text_backing = NULL;
    if (kind == RC_TEXT) {
        MinyarText *text = (MinyarText *)(object + 1);
        text_backing = text->backing;
        if (!text_backing) rc_free_data((void *)text->bytes);
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
    RC_DEALLOCATE(object);
    RC_ACCOUNT(rc_object_count--);
    return text_backing;
}

static void rc_bounded_enqueue(RcObject *object) {
    rc_bounded_save_cursor(object, 0);
    object->ownership |= (size_t)(uintptr_t)rc_bounded_recent_head;
    rc_bounded_recent_head = object;
    if (!rc_bounded_recent_tail) rc_bounded_recent_tail = object;
    rc_pending_count++;
}

/* Count drop of an RC_TRACED object: the same work as rc_drop, plus the
 * collector's snapshot barriers, gray pinning and registry removal. */
static inline unsigned rc_drop_traced(RcObject *object) {
    rc_cycle_before_drop(object);
    object->ownership -= 8;
    if (object->ownership >> 3) { rc_cycle_after_drop(object); return 0; }
    if (rc_cycle_defer_zero(object)) return 0;
    rc_cycle_unregister(object);
    RcCycle *cycle = rc_cycle_metadata(object);
    if (cycle->cleared || !(cycle->record ? ((MinyarRecord *)(object + 1))->length
                                          : ((MinyarList *)(object + 1))->length)) {
        rc_bounded_finish_traced(object);
        return 1;
    }
    rc_bounded_enqueue(object);
    return 0;
}

static unsigned rc_drop(void *value) {
    if (!value) return 0;
    RcObject *object = (RcObject *)value - 1;
    size_t ownership = object->ownership;
    /* Exactly one owner and no child fields: no zero-count store or broad
     * kind dispatch is needed before returning this allocation. Shared scalar
     * records continue through the ordinary checked decrement below. */
    if (ownership == (8 | RC_SCALAR_RECORD)) {
        rc_bounded_finish_object(object, RC_SCALAR_RECORD);
        return 1;
    }
    if (!(ownership >> 3)) return 0;
    if ((ownership & 7) == RC_TRACED) return rc_drop_traced(object);
    object->ownership = ownership - 8;
    if (object->ownership >> 3) return 0;
    unsigned kind = object->ownership & 7;
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
                if (!(root->ownership >> 3)) rc_bounded_enqueue(root);
            }
        }
        return 1;
    }
    if (kind == RC_LIST || kind == RC_REFERENCES_IMMORTAL ||
        (kind == RC_REFERENCES && !((MinyarList *)(object + 1))->length) ||
        (kind == RC_RECORD && !((MinyarRecord *)(object + 1))->length)) {
        rc_bounded_finish_object(object, kind);
        return 1;
    }
    rc_bounded_enqueue(object);
    return 0;
}

/* Visit field `cursor` of a dead RC_TRACED object as one unit, removing its
 * incoming edge first; returns 0 once every field was visited. A recent task
 * saves its cursor before the drop, exactly as the untraced paths do. */
static inline int rc_bounded_traced_visit(RcObject *object, size_t cursor, int recent) {
    RcCycle *cycle = rc_cycle_metadata(object);
    void *child;
    if (cycle->record) {
        MinyarRecord *record = (MinyarRecord *)(object + 1);
        if (cursor >= (size_t)record->length) return 0;
        unsigned char *map = (unsigned char *)(record->values + record->length);
        child = (map[cursor] & 1) ? (void *)(uintptr_t)record->values[cursor] : NULL;
    } else {
        MinyarList *list = (MinyarList *)(object + 1);
        if (cursor >= (size_t)list->length) return 0;
        child = (void *)(uintptr_t)list->values[cursor];
    }
    if (recent) rc_bounded_save_cursor(object, cursor + 1);
    else rc_bounded_cursor = cursor + 1;
    rc_cycle_edge_remove(child);
    rc_drop(child);
    return 1;
}

static RcFrame *rc_bounded_frame_head, *rc_bounded_frame_tail;
static RcTemporaryChunk *rc_bounded_chunk_head, *rc_bounded_chunk_tail;
static unsigned rc_bounded_next_queue;

static void rc_bounded_retire_temporaries(RcFrame *frame) {
    if (!frame->temporary_head) return;
    if (rc_bounded_chunk_tail) rc_bounded_chunk_tail->next = frame->temporary_head;
    else rc_bounded_chunk_head = frame->temporary_head;
    rc_bounded_chunk_tail = frame->temporary_tail;
    rc_pending_count += frame->temporary_count / RC_TEMPORARY_CHUNK_SLOTS
                      + (frame->temporary_count % RC_TEMPORARY_CHUNK_SLOTS != 0);
    frame->temporary_head = frame->temporary_tail = NULL;
    frame->temporary_count = 0;
}

static void rc_bounded_old_object_unit(void) {
    if (!rc_bounded_active) {
        rc_bounded_active = rc_bounded_head;
        rc_bounded_head = (RcObject *)(uintptr_t)(rc_bounded_active->ownership & ~(size_t)7);
        if (!rc_bounded_head) rc_bounded_tail = NULL;
        rc_bounded_active->ownership &= 7;
        rc_bounded_cursor = rc_bounded_saved_cursor(rc_bounded_active);
    }
    RcObject *object = rc_bounded_active;
    unsigned kind = object->ownership & 7;
    if (kind == RC_REFERENCES) {
        MinyarList *list = (MinyarList *)(object + 1);
        if (rc_bounded_cursor < (size_t)list->length) {
            rc_drop((void *)(uintptr_t)list->values[rc_bounded_cursor++]);
            return;
        }
    } else if (kind == RC_RECORD) {
        MinyarRecord *record = (MinyarRecord *)(object + 1);
        if (rc_bounded_cursor < (size_t)record->length) {
            unsigned char *map = (unsigned char *)(record->values + record->length);
            size_t index = rc_bounded_cursor++;
            if (map[index] & 1) rc_drop((void *)(uintptr_t)record->values[index]);
            return;
        }
    } else if (kind == RC_TRACED && rc_bounded_traced_visit(object, rc_bounded_cursor, 0)) {
        return;
    }
    rc_bounded_finish_object(object, kind);
    rc_pending_count--;
    rc_bounded_active = NULL;
}

/* A recent task remains linked while visiting its next owner. Saving the
 * cursor before dropping that owner lets newly dead children preempt it without
 * recursion or an auxiliary allocation. */
static void rc_bounded_recent_object_unit(void) {
    RcObject *object = rc_bounded_recent_head;
    unsigned kind = object->ownership & 7;
    size_t cursor = rc_bounded_saved_cursor(object);
    if (kind == RC_REFERENCES) {
        MinyarList *list = (MinyarList *)(object + 1);
        if (cursor < (size_t)list->length) {
            void *child = (void *)(uintptr_t)list->values[cursor];
            rc_bounded_save_cursor(object, cursor + 1);
            rc_drop(child);
            return;
        }
    } else if (kind == RC_RECORD) {
        MinyarRecord *record = (MinyarRecord *)(object + 1);
        if (cursor < (size_t)record->length) {
            unsigned char *map = (unsigned char *)(record->values + record->length);
            void *child = (map[cursor] & 1) ? (void *)(uintptr_t)record->values[cursor] : NULL;
            rc_bounded_save_cursor(object, cursor + 1);
            rc_drop(child);
            return;
        }
    } else if (kind == RC_TRACED && rc_bounded_traced_visit(object, cursor, 1)) {
        return;
    }
    rc_bounded_recent_head = (RcObject *)(uintptr_t)(object->ownership & ~(size_t)7);
    if (!rc_bounded_recent_head) rc_bounded_recent_tail = NULL;
    rc_bounded_finish_object(object, kind);
    rc_pending_count--;
}

/* Reserve alternating object units for the oldest finite batch. Whenever that
 * batch is exhausted, capture the recent stack in O(1). New arrivals cannot
 * enter the captured batch, so every captured task has finite predecessors.
 * Recent service follows freshly dead children promptly, while oldest service
 * cannot be starved by a stream of new tasks. */
static void rc_bounded_object_unit(void) {
    if (!rc_bounded_active && !rc_bounded_head) {
        rc_bounded_head = rc_bounded_recent_head;
        rc_bounded_tail = rc_bounded_recent_tail;
        rc_bounded_recent_head = rc_bounded_recent_tail = NULL;
    }
    unsigned recent = rc_bounded_recent_turn;
    rc_bounded_recent_turn ^= 1;
    if (recent && rc_bounded_recent_head) {
        /* Finish the sole captured unary parent before its recent child.
         * This is still one unit. With no captured successors, the next
         * object unit captures the recent stack and services its head, so
         * recent progress is delayed by at most one object unit here. */
        RcObject *active = rc_bounded_active;
        if (!rc_bounded_head && active && (active->ownership & 7) == RC_RECORD &&
            ((MinyarRecord *)(active + 1))->length == 1 && rc_bounded_cursor == 1)
            rc_bounded_old_object_unit();
        else rc_bounded_recent_object_unit();
    } else rc_bounded_old_object_unit();
}

static void rc_bounded_frame_unit(void) {
    RcFrame *frame = rc_bounded_frame_head;
    if (frame->local_count) {
        rc_drop(rc_bounded_pending_local_value(frame, --frame->local_count));
        return;
    }
    rc_bounded_frame_head = frame->previous;
    if (!rc_bounded_frame_head) rc_bounded_frame_tail = NULL;
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
    rc_pending_count--;
}

static void rc_bounded_chunk_unit(void) {
    RcTemporaryChunk *chunk = rc_bounded_chunk_head;
    if (chunk->count) {
        rc_drop(chunk->values[--chunk->count]);
        return;
    }
    rc_bounded_chunk_head = chunk->next;
    if (!rc_bounded_chunk_head) rc_bounded_chunk_tail = NULL;
    rc_heap_deallocate(chunk);
    rc_pending_count--;
}

/* Round-robin service across three queues, or four once the program has
 * allocated an RC_TRACED object (cycles != 0, a compile-time constant in each
 * instantiation below). Every continuously ready queue receives one unit
 * within three (four) units in the general scheduler, even with budget 1. A
 * cycle job requested inside an object-only batch can wait for that bounded
 * batch to return before entering the general scheduler. rc_pending_count
 * includes objects, detached frames, temporary chunks and one cycle job. */
static inline __attribute__((always_inline)) size_t rc_bounded_poll_body(size_t budget, const int cycles) {
    if (budget > MINYAR_RC_POLL_BUDGET) budget = MINYAR_RC_POLL_BUDGET;
    size_t work = 0;
    if (!rc_bounded_frame_head && !rc_bounded_chunk_head && !(cycles && rc_cycle_pending)) {
        /* Object processing can enqueue objects or request a cycle job.
         * With no frame/chunk/cycle tasks, skip repeated queue selection.
         * Match the general scheduler's next queue after any object work;
         * empty and zero-budget polls leave that state unchanged. */
        while (work < budget && rc_pending_count && !(cycles && rc_cycle_pending)) {
            /* With one unvisited unary record, locality makes its field visit
             * and finalization the next two units. There is no competing old
             * task to bypass, and dropping one child creates at most one task.
             * Keep per-unit state updates around rc_drop in reference order. */
            if (budget - work >= 2 && rc_pending_count == 1 && !rc_bounded_active) {
                RcObject *single = rc_bounded_head ? rc_bounded_head : rc_bounded_recent_head;
                if (single && (single->ownership & 7) == RC_RECORD) {
                    MinyarRecord *record = (MinyarRecord *)(single + 1);
                    if (record->length == 1) {
                        unsigned char *map = (unsigned char *)(record->values + 1);
                        if (!(map[0] >> 1)) {
                            rc_bounded_head = rc_bounded_tail = NULL;
                            rc_bounded_recent_head = rc_bounded_recent_tail = NULL;
                            single->ownership = RC_RECORD;
                            rc_bounded_active = single;
                            rc_bounded_cursor = 1;
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
                                    rc_bounded_active = single;
                                    continue;
                                }
                                rc_bounded_recent_turn ^= 1;
                                if (map[0] & 1) rc_drop((void *)(uintptr_t)record->values[0]);
                                rc_bounded_recent_turn ^= 1;
                                rc_bounded_finish_object(single, RC_RECORD);
                                rc_pending_count--;
                                rc_bounded_active = NULL;
                                work += 2;
                                break;
                            }
                            continue;
                        }
                    }
                }
            }
            /* A ready recent task must preserve alternating service. Without
             * one, consume a bounded run of the active List's owner slots.
             * A newly dead nonleaf immediately ends this run, restoring the
             * ordinary scheduler before any further work. */
            if (!rc_bounded_recent_head && rc_bounded_active &&
                (rc_bounded_active->ownership & 7) == RC_REFERENCES) {
                MinyarList *list = (MinyarList *)(rc_bounded_active + 1);
                size_t available = (size_t)list->length - rc_bounded_cursor;
                size_t count = budget - work;
                if (count > available) count = available;
                size_t end = rc_bounded_cursor + count;
                while (rc_bounded_cursor < end) {
                    rc_bounded_recent_turn ^= 1;
                    void *value = (void *)(uintptr_t)list->values[rc_bounded_cursor++];
                    RcObject *child = value ? (RcObject *)value - 1 : NULL;
                    work++;
                    /* Inline only the common unique scalar leaf. Its free
                     * cannot create a recent task; other owners retain the
                     * generic decrement and immediate queue-stop check. */
                    if (child && child->ownership == (8 | RC_SCALAR_RECORD))
                        rc_bounded_finish_object(child, RC_SCALAR_RECORD);
                    else {
                        rc_drop(value);
                        if (rc_bounded_recent_head) break;
                    }
                }
                if (count) continue;
            }
            rc_bounded_object_unit();
            work++;
        }
        if (work) rc_bounded_next_queue = 1;
    } else {
        while (work < budget && rc_pending_count) {
            unsigned queue = rc_bounded_next_queue;
            const unsigned queues = cycles ? 4 : 3;
            for (unsigned tries = 0; tries < queues; tries++) {
                if ((queue == 0 && (rc_bounded_active || rc_bounded_head || rc_bounded_recent_head)) ||
                    (queue == 1 && rc_bounded_frame_head) ||
                    (queue == 2 && rc_bounded_chunk_head) ||
                    (cycles && queue == 3 && rc_cycle_pending)) break;
                queue = (queue + 1) % queues;
            }
            rc_bounded_next_queue = (queue + 1) % queues;
            if (queue == 0) rc_bounded_object_unit();
            else if (queue == 1) rc_bounded_frame_unit();
            else if (queue == 2) rc_bounded_chunk_unit();
            else rc_cycle_unit();
            work++;
        }
    }
#ifdef MINYAR_RC_TESTING
    rc_bounded_last_work = work;
#endif
    return work;
}

static MINYAR_NOINLINE size_t rc_bounded_poll_traced(size_t budget) {
    return rc_bounded_poll_body(budget, 1);
}

/* Programs that never allocate an RC_TRACED object keep v2's scheduler. */
static MINYAR_COLD size_t rc_bounded_poll_work(size_t budget) {
    if (rc_cycle_present) return rc_bounded_poll_traced(budget);
    return rc_bounded_poll_body(budget, 0);
}

/* Every queue holds pending work, so with nothing pending a poll does no work
 * and changes no state. Keep that constant-time test inline: generated code
 * polls at every loop iteration and call, and almost always finds nothing. */
size_t minyar_rc_poll(size_t budget) {
    if (!rc_pending_count) {
#ifdef MINYAR_RC_TESTING
        rc_bounded_last_work = 0;
#endif
        return 0;
    }
    return rc_bounded_poll_work(budget);
}

void minyar_rc_release(void *value) {
    unsigned immediate = rc_drop(value);
    rc_service_pending(immediate < MINYAR_RC_POLL_BUDGET
                       ? MINYAR_RC_POLL_BUDGET - immediate : 0);
#ifdef MINYAR_RC_TESTING
    rc_bounded_last_work += immediate;
#endif
}
