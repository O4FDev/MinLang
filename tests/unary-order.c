#include <stdlib.h>
#include <assert.h>
static void *tracked[65];
static size_t freed[65], freed_count, tracked_count;
static void observe_free(void *pointer) {
    for(size_t i=0;i<tracked_count;i++)if(pointer==tracked[i]){freed[freed_count++]=i;break;}
    free(pointer);
}
#define free observe_free
#define MINYAR_SYSTEM_HEAP 1
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#undef free
static size_t completed_units;
static void drain(void) {
    while(rc_pending_count) {
        size_t work=minyar_rc_poll(MINYAR_RC_POLL_BUDGET);
        assert(work>0 && work<=MINYAR_RC_POLL_BUDGET);
        completed_units+=work;
    }
}
int main(void) {
    for(int shared=0;shared<=1;shared++) {
        void *root=NULL,*alias=NULL;
        tracked_count=freed_count=completed_units=0;
        for(size_t i=0;i<65;i++) {
            MinyarRecord *r=minyar_record_new(1);
            minyar_record_set_take(r,0,(long long)(uintptr_t)root);
            tracked[tracked_count++]=(RcObject *)r-1;
            if(shared && i==31){alias=r;minyar_rc_retain(alias);}
            root=r;
        }
        minyar_rc_release(root);
        assert(rc_bounded_last_work<=MINYAR_RC_POLL_BUDGET);
        completed_units+=rc_bounded_last_work;
        drain();
        assert(freed_count==(shared?33:65));
        assert(completed_units==(shared?66:130));
        for(size_t i=0;i<freed_count;i++)assert(freed[i]==64-i);
        if(shared) {
            assert(((RcObject *)alias-1)->ownership==(8|RC_RECORD));
            assert(minyar_record_get(alias,0)!=0);
            minyar_rc_release(alias);completed_units+=rc_bounded_last_work;drain();
        }
        assert(freed_count==65 && completed_units==130);
        for(size_t i=0;i<freed_count;i++)assert(freed[i]==64-i);
        assert(!rc_object_count&&!rc_bytes&&!rc_heap_allocation_count);
    }
    tracked_count=0;
    rc_bounded_recent_turn=0;
    MinyarRecord *successor=minyar_record_new(1);
    MinyarRecord *child=minyar_record_new(1);
    MinyarRecord *parent=minyar_record_new(1);
    minyar_record_set_take(parent,0,(long long)(uintptr_t)child);
    rc_drop(successor);rc_drop(parent);
    assert(minyar_rc_poll(1)==1);
    assert(rc_bounded_active==(RcObject *)parent-1 && rc_bounded_head==(RcObject *)successor-1);
    assert(minyar_rc_poll(1)==1);
    /* An older captured successor disables the exception: recent child wins. */
    assert(rc_object_count==3 && rc_bounded_active==(RcObject *)parent-1);
    assert(rc_bounded_saved_cursor((RcObject *)child-1)==1);
    drain();
    rc_bounded_recent_turn=0;
    child=minyar_record_new(128);parent=minyar_record_new(1);
    minyar_record_set_take(parent,0,(long long)(uintptr_t)child);
    rc_drop(parent);
    assert(minyar_rc_poll(1)==1);
    assert(minyar_rc_poll(1)==1 && rc_object_count==1);
    assert(minyar_rc_poll(1)==1);
    assert(rc_bounded_active==(RcObject *)child-1 && rc_bounded_cursor==1);
    drain();
    assert(!rc_object_count&&!rc_bytes&&!rc_heap_allocation_count);
    puts("completed unary parents retire in allocation-reverse order; aliases and K hold");
}
