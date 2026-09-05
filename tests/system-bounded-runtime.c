#define MINYAR_SYSTEM_HEAP 1
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>
static void drain(void) {
    while(rc_pending_count) {
        size_t work=minyar_rc_poll(1);
        assert(work==1);
    }
}
static void clear_cache(void) {
    while(rc_free_frames) {
        RcFrame *frame=rc_free_frames;rc_free_frames=frame->previous;
        rc_heap_deallocate(frame->locals);rc_heap_deallocate(frame);
    }
    rc_bounded_cached_frame_bytes=0;
}
static void *volatile escaped_allocation;
int main(int argc,char **argv) {
    if(argc>1 && !strcmp(argv[1],"oom")) {escaped_allocation=rc_heap_allocate(SIZE_MAX);return 2;}
    if(argc>1 && !strcmp(argv[1],"stale")) {
        MinyarRecord *r=minyar_record_new_scalar(1);minyar_rc_release(r);
        return (int)*(volatile long long *)r;
    }
    /* Reservation is ordinary allocator policy, not the pool's64MiB ceiling. */
    size_t large=(size_t)80*1024*1024;
    unsigned char *data=rc_allocate_data(large);data[0]=17;data[large-1]=19;
    assert(data[0]==17 && data[large-1]==19);rc_free_data(data);
    assert(!rc_heap_allocation_count);
    MinyarRecord *root=NULL;
    for(size_t i=0;i<10000;i++) {
        MinyarRecord *next=minyar_record_new(2);minyar_record_set(next,0,(long long)i);
        minyar_record_set_take(next,1,(long long)(uintptr_t)root);root=next;
    }
    minyar_rc_release(root);assert(rc_bounded_last_work<=MINYAR_RC_POLL_BUDGET);
    drain();assert(!rc_bytes&&!rc_object_count&&!rc_heap_allocation_count);
    MinyarRecord *shared=minyar_record_new_scalar(1);
    minyar_rc_enter(8192);minyar_rc_local(8191,shared);
    for(size_t i=0;i<8192;i++) minyar_rc_borrow(shared);
    minyar_rc_leave();assert(rc_bounded_last_work<=MINYAR_RC_POLL_BUDGET);
    drain();assert((((RcObject *)shared-1)->ownership>>3)==1);
    minyar_rc_release(shared);clear_cache();
    assert(!rc_bytes&&!rc_object_count&&!rc_heap_allocation_count);
    puts("system backing:80MiB allocation, bounded graph/frame/temp retirement and full recovery");
}
