/* Adapted from port/astra-cycles-v2 at 976a75a8c51518006cb654d6e6304f425e2eab91.
 * Selected only by the separate cycle runtime; ordinary runtime files retain
 * their original implementation. See docs/managed-graphs.md. */
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
        if (!rc_cycle_rescan && !rc_cycle_local_requested &&
            rc_cycle_proof_valid && rc_cycle_anchor_held()) {
            /* One real bounded unit retires the coalesced read requests.
             * Graph/anchor invalidation changes this to a normal scan. */
            rc_cycle_requested = rc_cycle_pending = 0;
#ifdef MINYAR_BOUNDED_RC
            rc_pending_count--;
#endif
            RC_ACCOUNT(rc_cycle_cached_requests++);
            return;
        }
        rc_cycle_local_job = !rc_cycle_rescan && rc_cycle_local_requested &&
                             rc_cycle_proof_valid && rc_cycle_anchor_held();
        rc_cycle_local_requested = 0;
        rc_cycle_temporary_valid = 0;
        rc_cycle_temporary_build = rc_cycle_local_job;
        rc_cycle_temporary_covered = 1;
        rc_cycle_temporary_anchor = NULL;
        if (!rc_cycle_local_job)
            rc_cycle_join_known();
        rc_cycle_proof_preserve = rc_cycle_proof_valid && rc_cycle_anchor_held();
        rc_cycle_proof_build = !rc_cycle_local_job;
        rc_cycle_proof_after_retry = !rc_cycle_proof_retry;
        if (!rc_cycle_proof_preserve)
            rc_cycle_proof_anchor = NULL;
        rc_cycle_rescan = 0;
        rc_cycle_requested = 0;
        if (rc_cycle_local_job)
            rc_cycle_local_generation ^= 1;
        else
            rc_cycle_generation ^= 1;
        rc_cycle_last = rc_cycle_tail;
        rc_cycle_cohort = rc_cycle_cursor = rc_cycle_head;
        rc_cycle_phase = RC_CYCLE_ROOTS;
        rc_cycle_shading = 1;
        RC_ACCOUNT(rc_cycle_epochs++);
        return;
    }
    if (rc_cycle_phase == RC_CYCLE_ROOTS) {
        RcCycle *cycle = rc_cycle_cursor;
        if (!cycle) {
            if (!rc_cycle_proof_anchor)
                rc_cycle_proof_retry = NULL;
            rc_cycle_phase = RC_CYCLE_MARK;
            return;
        }
        rc_cycle_cursor = rc_cycle_cohort_next(cycle);
        if (cycle->marked == 3)
            cycle->marked = 0;
        if (rc_cycle_local_job) {
            cycle->gray_next |= 4;
            /* Temporary paths are rebuilt for each finite local cohort. */
            if (((cycle->gray_next >> 1) & 1) != rc_cycle_proof_generation)
                cycle->gray_next &= ~(uintptr_t)1;
        } else {
            /* A canceled local mark may have scanned a known parent outside
             * its finite sweep cohort. Its completed mark belongs to the old
             * snapshot; queued marks still belong to this ROOTS pass. */
            if (cycle->marked == 2)
                cycle->marked = 0;
            /* Previous temporary tags can equal the new full generation.
             * Clear them before they enter the full proof namespace. */
            if ((cycle->gray_next & 4) &&
                ((cycle->gray_next >> 1) & 1) != rc_cycle_proof_generation)
                cycle->gray_next &= ~(uintptr_t)1;
            cycle->gray_next &= ~(uintptr_t)4;
            cycle->generation = rc_cycle_generation ^ 1;
        }
        if (!rc_cycle_proof_preserve)
            cycle->gray_next &= ~(uintptr_t)1;
        if (rc_cycle_local_job && rc_cycle_proof_valid && rc_cycle_anchor_held() &&
            rc_cycle_proven(cycle))
            rc_cycle_shade_proven(cycle);
        if (cycle == rc_cycle_proof_retry)
            rc_cycle_proof_after_retry = 1;
        if ((rc_cycle_object(cycle)->ownership >> 3) > cycle->incoming) {
            if (!rc_cycle_local_job && !rc_cycle_proof_anchor && rc_cycle_proof_after_retry &&
                cycle != rc_cycle_proof_retry)
                rc_cycle_proof_anchor = cycle;
            if (cycle == rc_cycle_proof_anchor)
                rc_cycle_shade_proven(cycle);
            else if (rc_cycle_local_job && rc_cycle_temporary_build) {
                if (!rc_cycle_temporary_anchor)
                    rc_cycle_temporary_anchor = cycle;
                if (cycle == rc_cycle_temporary_anchor)
                    rc_cycle_shade_temporary(cycle);
                else
                    rc_cycle_shade(cycle);
            } else
                rc_cycle_shade(cycle);
        }
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
            if (slot) {
                RcCycle *child = rc_cycle_value((void *)(uintptr_t)*slot);
                /* A skipped empty container keeps this history through
                 * namespace flips and shared incoming-edge removals. */
                if (child && !child->registered)
                    child->gray_next |= 4;
                /* A new registered child is outside this captured cohort.
                 * Its proven parent must not retire to the known registry
                 * before a joined scan can discover that owning path. */
                if (child && child->registered && child->marked == 3 &&
                    rc_cycle_snapshot_new(child) && rc_cycle_proven(cycle) &&
                    (rc_cycle_proof_build ||
                     (rc_cycle_local_job && rc_cycle_proof_valid && rc_cycle_anchor_held()))) {
                    rc_cycle_proof_valid = rc_cycle_proof_build = 0;
                    rc_cycle_join_known();
                    rc_cycle_rescan = rc_cycle_requested = 1;
                }
                if ((rc_cycle_proof_build ||
                     (rc_cycle_local_job && rc_cycle_proof_valid && rc_cycle_anchor_held())) &&
                    rc_cycle_proven(cycle))
                    rc_cycle_shade_proven(child);
                else if (rc_cycle_local_job && rc_cycle_temporary_build &&
                         rc_cycle_temporary_held() && rc_cycle_temporary_proven(cycle))
                    rc_cycle_shade_temporary(child);
                else
                    rc_cycle_shade(child);
            }
        }
        if (rc_cycle_index == rc_cycle_limit) {
            rc_cycle_active = NULL;
            cycle->marked = 2;
            if (cycle->pinned) {
                cycle->pinned = 0;
#ifdef MINYAR_BOUNDED_RC
                rc_drop_final_mark_pin(rc_cycle_object(cycle));
#else
                rc_drop(rc_cycle_object(cycle) + 1);
#endif
            }
        }
        return;
    }
    RcCycle *cycle = rc_cycle_active;
    if (!cycle) {
        cycle = rc_cycle_cursor;
        if (!cycle) {
            rc_cycle_cohort = rc_cycle_last = NULL;
            rc_cycle_completed++;
            rc_cycle_temporary_valid = rc_cycle_local_job &&
                rc_cycle_temporary_build && rc_cycle_temporary_covered &&
                rc_cycle_temporary_held() && rc_cycle_proof_valid && rc_cycle_anchor_held();
            if (rc_cycle_temporary_valid && !rc_cycle_rescan)
                rc_cycle_local_requested = 0;
            rc_cycle_temporary_build = 0;
            if (!rc_cycle_local_job) {
                rc_cycle_proof_valid = rc_cycle_proof_build && rc_cycle_anchor_held();
                rc_cycle_proof_generation = rc_cycle_generation;
                rc_cycle_local_generation = rc_cycle_generation;
                /* Paired dead-edge work can owe a local scan for private
                 * cycles outside this primary. A completed held proof covers
                 * the whole registry only if its unknown prefix is empty. */
                if (rc_cycle_proof_valid && rc_cycle_anchor_held() &&
                    !rc_cycle_rescan && !rc_cycle_head)
                    rc_cycle_local_requested = 0;
            }
            rc_cycle_proof_build = 0;
            rc_cycle_phase = RC_CYCLE_IDLE;
            rc_cycle_local_job = 0;
            if (!rc_cycle_requested && !rc_cycle_rescan && !rc_cycle_local_requested) {
                rc_cycle_pending = 0;
#ifdef MINYAR_BOUNDED_RC
                rc_pending_count--;
#endif
            }
            return;
        }
        rc_cycle_cursor = rc_cycle_cohort_next(cycle);
        /* A canceled local job omitted old certified roots. It cannot
         * reclaim whites: retain them for the mandatory joined full job. */
        unsigned live = cycle->marked || (rc_cycle_local_job && !rc_cycle_proof_valid);
        /* No certified bit may survive two generation flips unvisited.
         * A proof invalidated mid-cohort can leave old cached tags behind;
         * discard those in this already bounded survivor/white unit. */
        unsigned proof_generation = rc_cycle_local_job ? rc_cycle_proof_generation : rc_cycle_generation;
        unsigned temporary = rc_cycle_local_job && rc_cycle_temporary_build &&
                             rc_cycle_temporary_held() && rc_cycle_temporary_proven(cycle);
        if (((cycle->gray_next >> 1) & 1) != proof_generation && !temporary)
            cycle->gray_next &= ~(uintptr_t)1;
        unsigned certified = rc_cycle_proven(cycle);
        cycle->generation = rc_cycle_local_job ? rc_cycle_local_generation : rc_cycle_generation;
        cycle->gray_next |= 4;
        cycle->marked = 0;
        if (live) {
            if ((rc_cycle_proof_valid || rc_cycle_proof_build) &&
                rc_cycle_anchor_held() && certified)
                rc_cycle_promote(cycle);
            else if (!temporary)
                rc_cycle_temporary_covered = 0;
            return;
        }
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
    if (servicing)
        return;
    servicing = 1;
    while (rc_cycle_pending && budget--) {
        rc_cycle_unit();
        minyar_rc_release(NULL);
    }
    servicing = 0;
}
#endif
