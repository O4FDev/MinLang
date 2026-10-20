/* TEST ONLY, appended to the exact-cleanup runtime in the same translation
 * unit. Only the independent padding carrier owns a C count. All observed
 * source pointers are borrowed. Never write collector metadata/state. */
#ifdef MINYAR_COMPILER_ARENA
#error Container MARK proof requires real ownership
#endif
#if !defined(MINYAR_BOUNDED_RC) || !defined(MINYAR_SYSTEM_HEAP) || MINYAR_SYSTEM_SMALL_HEAP != 0 || MINYAR_RC_POLL_BUDGET != 1
#error Container MARK proof requires the plain-system bounded K1 profile
#endif

static MinyarRecord *mark_carrier, *mark_parent;
static MinyarList *mark_target;
static size_t mark_epoch, mark_index, mark_incoming, mark_mode, mark_checks;

static RcCycle *mark_list(void *value) {
    assert(value && (((RcObject *)value - 1)->ownership & 7) == RC_TRACED);
    RcCycle *cycle = rc_cycle_value(value);
    assert(cycle && !cycle->record && rc_kind((RcObject *)value - 1) == RC_REFERENCES);
    assert(!cycle->cleared && !cycle->pinned);
    return cycle;
}
static RcCycle *mark_record(MinyarRecord *value) {
    assert(value && (((RcObject *)value - 1)->ownership & 7) == RC_TRACED);
    RcCycle *cycle = rc_cycle_value(value);
    assert(cycle && cycle->record && !cycle->cleared && !cycle->pinned);
    return cycle;
}
static size_t mark_refs(void *value) { return ((RcObject *)value - 1)->ownership >> 3; }
static void mark_drain(void) {
    size_t turns = 0;
    while (rc_pending_count) {
        assert(++turns < 1000000);
        assert(minyar_rc_poll(1) == 1);
    }
    assert(rc_cycle_phase == RC_CYCLE_IDLE && !rc_cycle_inside);
}
static void mark_window(void) {
    assert(rc_cycle_phase == RC_CYCLE_MARK && rc_cycle_shading);
    assert(!rc_cycle_inside && !rc_cycle_local_job && rc_cycle_epochs == mark_epoch);
    assert(rc_cycle_active == rc_cycle_value(mark_carrier) && rc_cycle_limit == 4096);
    assert(rc_cycle_index >= mark_index && rc_cycle_limit - rc_cycle_index > 128);
    mark_index = rc_cycle_index;
}
static void mark_arm(unsigned mode) {
    assert(!mark_carrier && mark_mode == 0);
    /* Factory locals/deferred owners are gone before establishing the oracle. */
    mark_drain();
    mark_mode = mode;
    mark_incoming = mark_list(mark_target)->incoming;
    mark_carrier = minyar_record_new_traced(4096);
    minyar_record_set_reference_traced(mark_carrier, 0, (long long)(uintptr_t)mark_carrier);
    rc_cycle_request();
    size_t turns = 0;
    while (!(rc_cycle_phase == RC_CYCLE_MARK && rc_cycle_shading &&
             !rc_cycle_inside && !rc_cycle_local_job &&
             rc_cycle_active == rc_cycle_value(mark_carrier))) {
        assert(++turns < 1000000);
        assert(minyar_rc_poll(1) == 1);
    }
    mark_epoch = rc_cycle_epochs;
    mark_index = rc_cycle_index;
    mark_window();
}

long long minyar_choice_mark_armMark(MinyarRecord *parent) {
    mark_record(parent);
    mark_parent = parent;
    mark_target = (void *)(uintptr_t)parent->values[1];
    mark_arm(1);
    RcCycle *target = mark_list(mark_target);
    assert(target->registered && mark_refs(mark_target) == target->incoming);
    assert(mark_record(parent)->marked == 1 && target->marked == 0);
    assert(mark_target->length == 1);
    MinyarRecord *node = (void *)(uintptr_t)mark_target->values[0];
    mark_record(node);
    assert(node->values[0] == 431 && node->values[1] == (long long)(uintptr_t)mark_target);
    return 1;
}
long long minyar_choice_mark_assertSaved(void *saved) {
    assert(mark_mode == 1 && saved == mark_target);
    mark_window();
    assert(mark_list(saved)->marked != 0 && mark_refs(saved) > mark_list(saved)->incoming);
    assert(mark_record(mark_parent)->marked == 1);
    ++mark_checks;
    return 1;
}
long long minyar_choice_mark_assertRemoved(MinyarRecord *parent, void *saved) {
    assert(mark_mode == 1 && parent == mark_parent && saved == mark_target);
    mark_window();
    RcCycle *target = mark_list(saved);
    assert(parent->values[1] == 0 && target->incoming + 1 == mark_incoming);
    assert(target->marked != 0 && mark_refs(saved) > target->incoming);
    ++mark_checks;
    return 1;
}
long long minyar_choice_mark_armChain(void *chain) {
    mark_target = chain;
    mark_arm(2);
    assert(mark_target->length == 0);
    return 1;
}
long long minyar_choice_mark_assertChain(void *chain) {
    assert(mark_mode == 2 && chain == mark_target);
    mark_window();
    assert(mark_target->length == 1 && mark_target->values[0] == (long long)(uintptr_t)chain);
    assert(mark_list(chain)->incoming == mark_incoming + 1);
    ++mark_checks;
    return 1;
}
long long minyar_choice_mark_armNode(MinyarRecord *node) {
    mark_record(node);
    mark_parent = node;
    mark_target = (void *)(uintptr_t)node->values[0];
    mark_arm(3);
    assert(mark_target->length == 1 && mark_target->values[0] == (long long)(uintptr_t)node);
    return 1;
}
long long minyar_choice_mark_assertNode(MinyarRecord *node, void *saved) {
    assert(mark_mode == 3 && node == mark_parent && saved == mark_target);
    mark_window();
    RcCycle *target = mark_list(saved);
    assert(node->values[0] == 0 && target->incoming + 1 == mark_incoming);
    assert(mark_refs(saved) > target->incoming);
    ++mark_checks;
    return 1;
}
long long minyar_choice_mark_finishMark(void) {
    mark_window();
    MinyarRecord *carrier = mark_carrier;
    mark_target = NULL;
    mark_parent = NULL;
    mark_mode = 0;
    mark_carrier = NULL;
    minyar_record_replace_traced(carrier, 0, 0, 0);
    minyar_rc_release(carrier);
    return 1;
}
__attribute__((destructor)) static void check_container_mark_contract(void) {
    assert(!mark_carrier && !mark_target && !mark_parent && mark_mode == 0 && mark_checks == 4);
    assert(rc_frames == NULL);
    mark_drain();
    assert(rc_object_count == 0 && rc_bytes == 0 && rc_immortal_object_count == 0);
}
