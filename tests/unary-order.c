#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include <stdlib.h>
#include <assert.h>
static void *tracked[65];
static size_t freed[65], freed_count, tracked_count;
static void observe_release(void *pointer) {
    for(size_t i=0;i<tracked_count;i++)if(pointer==tracked[i]){freed[freed_count++]=i;break;}
}
#define MINYAR_RC_OBJECT_RELEASE_OBSERVER observe_release
#define MINYAR_SYSTEM_HEAP 1
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
/* Object work left at the end of a service point continues in the old-object
 * backlog, a second instance of the same queue. Idle polls give it the whole
 * budget, so these exact unit counts and orders hold in every configuration.
 * One unit retires up to RC_SMALL_RECORD_UNIT_OBJECTS small aggregates, so a
 * unary chain costs one unit per eight records whatever K is. */
static RcObject *active(void){return rc_backlog_count?rc_backlog.active:rc_bounded_active;}
static RcObject *captured(void){return rc_backlog_count?rc_backlog.head:rc_bounded_head;}
static size_t cursor(void){return rc_backlog_count?rc_backlog.cursor:rc_bounded_cursor;}
static size_t completed_units;
static void drain(void) {
    while(rc_pending_count) {
        size_t work=minyar_rc_poll_idle(MINYAR_RC_POLL_BUDGET);
        assert(work>0 && work<=MINYAR_RC_POLL_BUDGET);
        completed_units+=work;
    }
}
/* Units for a chain of records retired eight at a time. */
static size_t chain_units(size_t objects) {
    return (objects + RC_SMALL_RECORD_UNIT_OBJECTS - 1) / RC_SMALL_RECORD_UNIT_OBJECTS;
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
        assert(completed_units==chain_units(shared?33:65));
        /* A unit retires the small aggregates it reaches, newest slice first;
         * the order within a unit is not contractual, but every record is freed
         * exactly once and the chain costs one unit per eight records. */
        for(size_t i=0;i<freed_count;i++)
            for(size_t j=i+1;j<freed_count;j++) assert(freed[i]!=freed[j]);
        if(shared) {
            assert(((RcObject *)alias-1)->ownership==(8|RC_RECORD));
            assert(minyar_record_get(alias,0)!=0);
            minyar_rc_release(alias);completed_units+=rc_bounded_last_work;drain();
        }
        assert(freed_count==65 && completed_units==chain_units(33)+chain_units(32));
        assert(!rc_object_count&&!rc_bytes&&!rc_heap_allocation_count);
    }
    tracked_count=0;
    rc_bounded_recent_turn=0;
    /* A parent and its unary child are one small subtree: the unit that starts
     * at the parent retires both, and the captured successor waits its turn. */
    MinyarRecord *successor=minyar_record_new(1);
    MinyarRecord *child=minyar_record_new(1);
    MinyarRecord *parent=minyar_record_new(1);
    minyar_record_set_take(parent,0,(long long)(uintptr_t)child);
    rc_drop(successor);rc_drop(parent);
    assert(minyar_rc_poll_idle(1)==1);
    assert(rc_object_count==1 && captured()==(RcObject *)successor-1);
    assert(minyar_rc_poll_idle(1)==1 && !rc_object_count);
    drain();
    /* A big record is not a small aggregate: its fields are examined eight at a
     * time, one unit per eight slots, and the record is retired at the end. */
    rc_bounded_recent_turn=0;
    child=minyar_record_new(128);parent=minyar_record_new(1);
    minyar_record_set_take(parent,0,(long long)(uintptr_t)child);
    rc_drop(parent);
    assert(minyar_rc_poll_idle(1)==1);
    assert(minyar_rc_poll_idle(1)==1 && rc_object_count==1);
    assert(minyar_rc_poll_idle(1)==1 && rc_object_count==1);
    assert(active()==(RcObject *)child-1);
    drain();
    assert(!rc_object_count&&!rc_bytes&&!rc_heap_allocation_count);
    puts("small unary subtrees retire per unit, big records eight fields at a time; aliases and K hold");
}
