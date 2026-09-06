/* Isolated stack API contracts; shared independent object graph oracle. */
#include <stddef.h>
#include <stdint.h>
#include <alloca.h>
static size_t scan_frame_owners(void);
#define PRODUCTION_EXTRA_OWNER_SCAN() scan_frame_owners()
#define main unused_graph_oracle_main
#include "../experiments/memory/production-live-oracle.c"
#undef main
#ifdef STACK_BASELINE
static void minyar_rc_enter_stack_v1(void *header, void *storage, long long n) {
    (void)header; (void)storage; minyar_rc_enter(n);
}
static void minyar_rc_leave_stack_v1(void *header) { (void)header; minyar_rc_leave(); }
#endif

/* Address rejection happens BEFORE following a link or reading its fields. */
static uintptr_t forbidden_start[2], forbidden_end[2];
static void *immortal_value;
static size_t scan_calls;
static int require_stack;
static int eligible(size_t n) { return n >= 1 && n <= 8 && n < MINYAR_RC_POLL_BUDGET; }
static void outside_stack(const void *p) {
    uintptr_t a = (uintptr_t)p;
    for (size_t i = 0; i < 2; ++i)
        assert(!p || a < forbidden_start[i] || a >= forbidden_end[i]);
}
static void owner(void *p) {
    if (p && p != immortal_value) entries[entry((RcObject *)p - 1)].expected++;
}
static void scan_locals(RcFrame *f, int pending) {
    size_t count = pending ? f->local_count : f->written_count;
    assert(count <= f->local_capacity && f->local_capacity <= 32);
    size_t *indices = f->locals ? (size_t *)(f->locals + f->local_capacity) : NULL;
    unsigned char seen[32] = {0};
    for (size_t i = 0; i < count; ++i) {
        size_t slot = indices[i]; assert(slot < f->local_capacity && !seen[slot]);
        seen[slot] = 1; assert((uintptr_t)f->locals[slot] & 1);
        if (pending) owner((void *)((uintptr_t)f->locals[slot] & ~(uintptr_t)1));
    }
    if (!pending) {
        size_t tags = 0;
        for (size_t i = 0; i < f->local_count; ++i) {
            tags += (uintptr_t)f->locals[i] & 1;
            owner((void *)((uintptr_t)f->locals[i] & ~(uintptr_t)1));
        }
        assert(tags == count);
    }
}
static size_t scan_chunks(RcTemporaryChunk *chunk) {
    size_t count = 0;
    while (chunk) {
        outside_stack(chunk); assert(++count < 8192 && chunk->count <= 8);
        for (size_t i = 0; i < chunk->count; ++i) { outside_stack(chunk->values[i]); owner(chunk->values[i]); }
        chunk = chunk->next;
    }
    return count;
}
static size_t scan_frame_owners(void) {
    size_t count = 0, active = 0;
    ++scan_calls;
    for (RcFrame *f = rc_frames; f; f = f->previous) {
        assert(++active < 32); scan_locals(f, 0); scan_chunks(f->temporary_head);
    }
    for (RcFrame *f = rc_bounded_frame_head; f; f = f->previous) {
        outside_stack(f); outside_stack(f->locals); assert(++count < 8192);
        scan_locals(f, 1); assert(!f->temporary_head && !f->temporary_tail && !f->temporary_count);
        for (RcFrame *cached = rc_free_frames; cached; cached = cached->previous) {
            outside_stack(cached); assert(cached != f);
        }
    }
    size_t cached_bytes = 0, cached_count = 0;
    for (RcFrame *f = rc_free_frames; f; f = f->previous) {
        outside_stack(f); outside_stack(f->locals); assert(++cached_count < 8192);
        cached_bytes += rc_heap_charge(f, sizeof(*f));
        if (f->locals) cached_bytes += rc_heap_charge(f->locals, f->local_capacity * 16);
    }
    assert(cached_bytes == rc_bounded_cached_frame_bytes);
    return count + scan_chunks(rc_bounded_chunk_head);
}
static void clean_cache(void) {
    while (rc_free_frames) {
        RcFrame *f = rc_free_frames; rc_free_frames = f->previous;
        outside_stack(f); outside_stack(f->locals);
        rc_heap_deallocate(f->locals); rc_heap_deallocate(f);
    }
    rc_bounded_cached_frame_bytes = 0;
}
static void drain(MinyarRecord **roots) {
    size_t guard = 0;
    while (rc_pending_count) { verify(roots); assert(minyar_rc_poll(1) == 1); assert(++guard < 100000); }
    verify(roots);
}
static MinyarRecord *record(long long serial) {
    MinyarRecord *p = minyar_record_new(4); minyar_record_set(p, 0, serial); return p;
}
static size_t backing(void) {
#ifdef MINYAR_SYSTEM_HEAP
    return rc_heap_allocation_count;
#else
    return minyar_pool_used;
#endif
}
static void ranges(void *header, void *storage, size_t n) {
    forbidden_start[0] = (uintptr_t)header; forbidden_end[0] = (uintptr_t)header + 64;
    forbidden_start[1] = (uintptr_t)storage; forbidden_end[1] = (uintptr_t)storage + (n ? 16*n : 16);
}

/* Called noinline so immediate stack reuse precedes subsequent queue draining. */
__attribute__((noinline)) static void activation(MinyarRecord **roots, size_t n, size_t written, unsigned temps) {
    void *header = alloca(64), *storage = alloca(n ? 16*n : 16);
    assert((uintptr_t)header % _Alignof(RcFrame) == 0);
    assert((uintptr_t)storage % _Alignof(size_t) == 0);
    ranges(header, storage, n);
    size_t before = backing(); RcFrame *caller = rc_frames;
    minyar_rc_enter_stack_v1(header, storage, (long long)n);
    int stack = rc_frames == header;
    if (require_stack) {
        if (eligible(n)) {
            if (!stack) fprintf(stderr, "STACK_ADMISSION_MISSING N=%zu K=%u\n", n, MINYAR_RC_POLL_BUDGET);
            assert(stack);
            assert(backing() == before); /* Entry has no pending debt here. */
        } else assert(!stack);
    }
    assert(rc_frames->previous == caller && rc_frames->local_count == n);
    if (stack) assert(rc_frames->locals == storage && rc_frames->local_capacity == n);
    verify(roots);
    for (size_t i = 0; i < written; ++i) {
        minyar_rc_local((long long)i, roots[0]); verify(roots);
        minyar_rc_local((long long)i, NULL); verify(roots);
        minyar_rc_local_take((long long)i, NULL); verify(roots);
        minyar_rc_local((long long)i, immortal_value); verify(roots);
        minyar_rc_local((long long)i, roots[i % 2]); verify(roots);
    }
    assert(rc_frames->written_count == written);
    for (unsigned i = 0; i < temps; ++i) minyar_rc_borrow(roots[i % 2]);
    verify(roots);
    /* Return a retained alias before local ownership disappears. */
    roots[2] = roots[0]; minyar_rc_retain(roots[2]);
    minyar_rc_leave_stack_v1(header);
    assert(rc_frames == caller && rc_bounded_last_work <= MINYAR_RC_POLL_BUDGET);
    if (stack) assert(rc_bounded_last_work >= written);
    verify(roots); /* Reject queued stack addresses before memory overwrite. */
    memset(header, 0xa5, 64); memset(storage, 0x5a, n ? 16*n : 16);
    verify(roots);
}

/* This fixture's chain nodes each require four field visits and one final
 * retirement. Their live descendants are already included, independently of
 * when rc_drop enqueues them. Only roots0/1 are externally anchored. */
static size_t remaining_chain_debt(void) {
    size_t debt = (rc_object_count - 2) * 5;
    for (size_t i=0;i<entry_count;++i) if(entries[i].dead) {
        RcObject *o=entries[i].object;
        size_t cursor=o==rc_bounded_active ? rc_bounded_cursor
                        : saved_record_cursor((MinyarRecord *)(o+1));
        assert(cursor <= 4 && debt >= cursor); debt-=cursor;
    }
    for(RcFrame *f=rc_bounded_frame_head;f;f=f->previous) debt += f->local_count+1;
    for(RcTemporaryChunk *c=rc_bounded_chunk_head;c;c=c->next) debt += c->count+1;
    return debt;
}
static void caller_scope(void) {
    MinyarRecord *roots[ROOTS]={record(71),record(72)};
    minyar_rc_enter(1); RcFrame *caller=rc_frames;
    minyar_rc_borrow(roots[0]);
    void *header=alloca(64), *storage=alloca(16); ranges(header,storage,1);
    minyar_rc_enter_stack_v1(header,storage,1);
    minyar_rc_borrow(roots[1]); minyar_rc_step();
    verify(roots);
    assert(caller->temporary_count==1); /* Callee step cannot detach caller. */
    assert((((RcObject*)roots[0]-1)->ownership>>3)==2);
    minyar_rc_local(0,roots[1]);
    roots[2]=roots[1]; minyar_rc_retain(roots[2]);
    minyar_rc_leave_stack_v1(header); verify(roots);
    memset(header,0x5a,64); memset(storage,0xa5,16); drain(roots);
    assert(rc_frames==caller && caller->temporary_count==1);
    assert(roots[2]->values[0]==72);
    minyar_rc_step(); drain(roots);
    assert((((RcObject*)roots[0]-1)->ownership>>3)==1);
    minyar_rc_leave(); drain(roots);
    for(size_t i=0;i<3;++i){minyar_rc_release(roots[i]);roots[i]=NULL;}
    drain(roots); clean_cache(); assert_backend_empty();
    memset(forbidden_start,0,sizeof(forbidden_start));memset(forbidden_end,0,sizeof(forbidden_end));
}

/* Queue debt is created after entry to test the composed leave budget. A chain
 * needs >K operations even at K1024, so exact K service is observable. */
static void pending_case(size_t n) {
    MinyarRecord *roots[ROOTS] = {0}; roots[0] = record(11); roots[1] = record(12);
    for (size_t i = 0; i < 1100; ++i) {
        MinyarRecord *p = record((long long)i + 100);
        minyar_record_set_take(p, 1, (long long)(uintptr_t)roots[3]); roots[3] = p;
    }
    void *header = alloca(64), *storage = alloca(16*n); ranges(header, storage, n);
    minyar_rc_enter_stack_v1(header, storage, (long long)n);
    int stack = rc_frames == header;
    for (size_t i = 0; i < n; ++i) minyar_rc_local((long long)i, roots[0]);
    for (unsigned i = 0; i < 65; ++i) minyar_rc_borrow(roots[1]);
    verify(roots);
    /* Internal rc_drop transfers the external root into pending work without
     * consuming the debt this fixture intentionally presents to leave. */
    assert(rc_drop(roots[3]) == 0); roots[3] = NULL; verify(roots);
    size_t old_objects = rc_object_count;
    size_t before_debt = (old_objects-2)*5 + 65 + 9 + n + (stack ? 0 : 1);
    minyar_rc_leave_stack_v1(header);
    assert(rc_bounded_last_work == MINYAR_RC_POLL_BUDGET);
    verify(roots);
    size_t after_debt = remaining_chain_debt();
    assert(before_debt >= after_debt && before_debt-after_debt == MINYAR_RC_POLL_BUDGET);
    if (stack) {
        assert(!rc_bounded_frame_head);
        /* Every stack local owner is already gone. Temporary owners are roots1. */
        assert((((RcObject *)roots[0]-1)->ownership >> 3) == 1);
        assert(rc_object_count <= old_objects);
    }
    memset(header, 0xa5, 64); memset(storage, 0x5a, 16*n);
    drain(roots);
    minyar_rc_release(roots[0]); roots[0] = NULL;
    minyar_rc_release(roots[1]); roots[1] = NULL; drain(roots); clean_cache(); assert_backend_empty();
    memset(forbidden_start,0,sizeof(forbidden_start)); memset(forbidden_end,0,sizeof(forbidden_end));
}
int main(int argc, char **argv) {
    (void)argv; require_stack = argc > 1;
    _Static_assert(sizeof(RcFrame) == 64 && sizeof(void*) == 8 && sizeof(size_t) == 8, "64-bit private ABI");
    /* Untyped alloca memory models an immortal generated literal safely. */
    RcObject *immortal = alloca(sizeof(RcObject) + sizeof(MinyarRecord) + 36);
    immortal->ownership = RC_RECORD;
    MinyarRecord *literal = (MinyarRecord *)(immortal + 1); literal->length = 4;
    memset(literal->values,0,36); immortal_value = literal;
    const size_t sizes[] = {0,1,2,7,8,9};
    size_t cases = 0;
    for (size_t z = 0; z < sizeof(sizes)/sizeof(*sizes); ++z) {
        size_t n = sizes[z];
        for (size_t w = 0; w <= n; ++w) {
            MinyarRecord *roots[ROOTS] = {record(11),record(12)};
            activation(roots,n,w,w%2 ? 19 : 0);
            drain(roots); assert(roots[2]->values[0] == 11);
            for (size_t i=0;i<3;++i) { minyar_rc_release(roots[i]); roots[i]=NULL; }
            drain(roots); clean_cache(); assert(!rc_object_count && !rc_bytes); assert_backend_empty();
            memset(forbidden_start,0,sizeof(forbidden_start)); memset(forbidden_end,0,sizeof(forbidden_end));
            cases++;
        }
    }
    pending_case(1); pending_case(8); caller_scope();
    printf("PASS stack-contract cases=%zu scans=%zu K=%u structural=%d\n",cases+3,scan_calls,MINYAR_RC_POLL_BUDGET,require_stack);
    return 0;
}
