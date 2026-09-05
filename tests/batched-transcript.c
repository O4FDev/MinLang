#define MINYAR_SYSTEM_HEAP 1
#define MINYAR_RC_TESTING 1
#ifndef BATCH_RUNTIME
#define BATCH_RUNTIME "../runtime/minyar_runtime.c"
#endif
#include BATCH_RUNTIME
#include <assert.h>
int main(void) {
    MinyarRecord *shared=minyar_record_new_scalar(1);
    MinyarList *list=minyar_list_new();minyar_list_references(list);
    for(size_t i=0;i<4096;i++) {
        MinyarRecord *child;
        if(i%37==0){child=minyar_record_new(2);minyar_record_set_reference(child,1,(long long)(uintptr_t)shared);}
        else child=minyar_record_new_scalar(1);
        minyar_record_set(child,0,(long long)i);
        minyar_list_add_take(list,(long long)(uintptr_t)child);
    }
    minyar_rc_enter(3);minyar_rc_local(2,shared);
    for(size_t i=0;i<19;i++)minyar_rc_borrow(shared);
    rc_drop(list);minyar_rc_leave();
    unsigned rng=92731;size_t iteration=0;
    while(rc_pending_count) {
        rng=rng*1664525u+1013904223u;
        size_t requested=(rng>>12)%(MINYAR_RC_POLL_BUDGET+1);
        size_t work=minyar_rc_poll(requested);
        assert(work<=requested && work<=MINYAR_RC_POLL_BUDGET);
        printf("%zu %zu %zu %zu %zu %zu %u %u %zu\n",iteration++,work,rc_pending_count,rc_object_count,rc_bytes,
               rc_bounded_active?rc_bounded_cursor:0,rc_bounded_recent_turn,rc_bounded_next_queue,
               ((RcObject *)shared-1)->ownership>>3);
    }
    assert((((RcObject *)shared-1)->ownership>>3)==1);minyar_rc_release(shared);
    while(rc_free_frames){RcFrame *f=rc_free_frames;rc_free_frames=f->previous;rc_heap_deallocate(f->locals);rc_heap_deallocate(f);}
    rc_bounded_cached_frame_bytes=0;
    assert(!rc_bytes&&!rc_object_count&&!rc_heap_allocation_count);
}
