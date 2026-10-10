/* Included after rc_drop and the ordinary cleanup implementation. Every call
 * performs one bounded unit: phase transition, root, survivor, or field.
 * Constant-size scan setup/completion accompanies the first/last field; a
 * unit never scans a second slot or starts another container after finishing.
 * New allocations prepend to the registry and cannot extend a captured cohort.
 * List scan limits are captured once; appends cannot extend an active scan. */
static size_t rc_cycle_length(RcCycle *cycle) {
    RcObject *object = rc_cycle_object(cycle);
    if (cycle->record)
        return (size_t)((MinyarRecord *)(object + 1))->length;
    return (size_t)((MinyarList *)(object + 1))->length;
}
static long long *rc_cycle_slot(RcCycle *cycle, size_t index) {
    RcObject *object = rc_cycle_object(cycle);
    if (cycle->record) {
        MinyarRecord *record = (MinyarRecord *)(object + 1);
        unsigned char *map = (unsigned char *)(record->values + record->length);
        return (map[index] & 1) ? &record->values[index] : NULL;
    }
    return &((MinyarList *)(object + 1))->values[index];
}
static void rc_cycle_unit_body(void) {
    RC_ACCOUNT(rc_cycle_units++);
    if (rc_cycle_phase == RC_CYCLE_IDLE) {
        rc_cycle_requested = 0;
        rc_cycle_generation ^= 1;
        rc_cycle_cohort = rc_cycle_cursor = rc_cycle_head;
        rc_cycle_phase = RC_CYCLE_ROOTS;
        rc_cycle_shading = 1;
        RC_ACCOUNT(rc_cycle_epochs++);
        return;
    }
    if (rc_cycle_phase == RC_CYCLE_ROOTS) {
        RcCycle *cycle = rc_cycle_cursor;
        if (!cycle) { rc_cycle_phase = RC_CYCLE_MARK; return; }
        rc_cycle_cursor = cycle->next;
        if ((rc_cycle_object(cycle)->ownership >> 3) > cycle->incoming)
            rc_cycle_shade(cycle);
        return;
    }
    if (rc_cycle_phase == RC_CYCLE_MARK) {
        RcCycle *cycle = rc_cycle_active;
        if (!cycle) {
            cycle = rc_cycle_gray_head;
            if (!cycle) {
                rc_cycle_phase = RC_CYCLE_SWEEP;
                rc_cycle_shading = 0;
                rc_cycle_cursor = rc_cycle_cohort;
                return;
            }
            rc_cycle_gray_pop();
            rc_cycle_active = cycle;
            rc_cycle_index = 0;
            rc_cycle_limit = rc_cycle_length(cycle);
        }
        if (rc_cycle_index < rc_cycle_limit) {
            long long *slot = rc_cycle_slot(cycle, rc_cycle_index++);
            if (slot) rc_cycle_shade(rc_cycle_value((void *)(uintptr_t)*slot));
        }
        if (rc_cycle_index == rc_cycle_limit) {
            rc_cycle_active = NULL;
            cycle->marked = 2;
            if (cycle->pinned) {
                cycle->pinned = 0;
                rc_drop(rc_cycle_object(cycle) + 1);
            }
        }
        return;
    }
    RcCycle *cycle = rc_cycle_active;
    if (!cycle) {
        cycle = rc_cycle_cursor;
        if (!cycle) {
            rc_cycle_cohort = NULL;
            rc_cycle_phase = RC_CYCLE_IDLE;
            if (!rc_cycle_requested) {
                rc_cycle_pending = 0;
#ifdef MINYAR_BOUNDED_RC
                rc_pending_count--;
#endif
            }
            return;
        }
        rc_cycle_cursor = cycle->next;
        unsigned live = cycle->marked;
        cycle->generation = rc_cycle_generation;
        cycle->marked = 0;
        if (live) return;
        minyar_rc_retain(rc_cycle_object(cycle) + 1);
        rc_cycle_active = cycle;
        rc_cycle_index = 0;
        rc_cycle_limit = rc_cycle_length(cycle);
    }
    if (rc_cycle_index < rc_cycle_limit) {
        long long *slot = rc_cycle_slot(cycle, rc_cycle_index++);
        if (slot) {
            void *child = (void *)(uintptr_t)*slot;
            *slot = 0;
            rc_cycle_edge_remove(child);
            rc_drop(child);
        }
    }
    if (rc_cycle_index == rc_cycle_limit) {
        rc_cycle_active = NULL;
        /* All outgoing slots were visited and cleared. Avoid revisiting
         * those null slots when the last incoming owner later retires. */
        RcObject *object = rc_cycle_object(cycle);
        cycle->cleared = 1;
        if (!cycle->record)
            ((MinyarList *)(object + 1))->length = 0;
        rc_cycle_unregister(object);
        /* The pin keeps self-edges safe while being severed. Other white
         * nodes remain protected by their ordinary, still counted edges. */
        rc_drop(rc_cycle_object(cycle) + 1);
    }
}
static MINYAR_NOINLINE void rc_cycle_unit(void) {
    rc_cycle_inside = 1;
    rc_cycle_unit_body();
    rc_cycle_inside = 0;
}
#ifndef MINYAR_BOUNDED_RC
static void rc_cycle_eager_service(size_t budget) {
    /* Recursive public releases only occur in the eager queue drain. */
    static unsigned servicing;
    if (servicing) return;
    servicing = 1;
    while (rc_cycle_pending && budget--) {
        rc_cycle_unit();
        minyar_rc_release(NULL);
    }
    servicing = 0;
}
#endif
