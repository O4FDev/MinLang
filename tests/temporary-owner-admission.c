/* Public-runtime pressure construction with independent aggregate poll-work
 * accounting. Creating an owner chunk must reuse work already in its budget. */
#define MINYAR_RC_TESTING
#define MINYAR_BOUNDED_HEAP 1
#define MINYAR_BOUNDED_HEAP_BYTES (MINYAR_RC_POLL_BUDGET <= 32 ? 4096 : 32768)
#include MINYAR_RUNTIME_SOURCE
#include <assert.h>
static size_t observed_calls, observed_work;
size_t minyar_rc_poll(size_t budget) {
 size_t work = probe_poll_impl(budget);
 observed_calls++; observed_work += work;
 return work;
}
static void drain(void) { while(rc_pending_count) assert(minyar_rc_poll(MINYAR_RC_POLL_BUDGET)>0); }
int main(int argc,char **argv) {
 assert(argc==3);int rollover=!strcmp(argv[1],"rollover"),borrowed=!strcmp(argv[2],"borrow"),existing=!strcmp(argv[1],"existing");
 assert(rollover||existing||!strcmp(argv[1],"first"));assert(borrowed||!strcmp(argv[2],"owned"));
 MinyarRecord *held[MINYAR_POOL_BYTES/32];size_t count=0;assert(!minyar_pool_used);
 minyar_rc_enter(0);MinyarRecord *value=minyar_record_new_scalar(1);minyar_record_set_scalar(value,0,123);
 if(rollover||existing)for(int i=0;i<(rollover?8:1);i++)minyar_rc_borrow(value);
 assert((rc_frames->temporary_tail!=NULL)==(rollover||existing));
 if(rollover)assert(rc_frames->temporary_tail->count==8);
 while(minyar_pool_used%128)held[count++]=minyar_record_new_scalar(1);
 size_t before_parent=minyar_pool_used;
 MinyarRecord *parent=minyar_record_new(MINYAR_RC_POLL_BUDGET);minyar_record_set_reference(parent,0,(long long)(intptr_t)value);
 for(size_t i=1;i<MINYAR_RC_POLL_BUDGET;i++)minyar_record_set(parent,(long long)i,0);
 size_t parent_block=minyar_pool_used-before_parent;
 size_t neighbor_count=parent_block<128?(128-parent_block)/32:0;
 MinyarRecord *neighbors[3];
 for(size_t i=0;i<neighbor_count;i++)neighbors[i]=minyar_record_new_scalar(1);
 while(minyar_pool_used<MINYAR_POOL_BYTES){assert(count<MINYAR_POOL_BYTES/32);held[count++]=minyar_record_new_scalar(1);}
 assert(minyar_pool_used==MINYAR_POOL_BYTES&&!rc_pending_count);
 for(size_t i=0;i<neighbor_count;i++)minyar_rc_release(neighbors[i]);
 minyar_rc_release(parent); /* Exactly K field visits leave one parent-retirement unit. */
 assert(rc_pending_count==1);size_t before=minyar_pool_used;
 assert(MINYAR_POOL_BYTES-before==neighbor_count*32);
 fprintf(stderr,"PRESSURE K=%u rollover=%d borrowed=%d used=%zu free=%zu pending=%zu value_refs=%zu\n",(unsigned)MINYAR_RC_POLL_BUDGET,rollover,borrowed,before,MINYAR_POOL_BYTES-before,rc_pending_count,((RcObject *)value-1)->ownership>>3);
 observed_calls=observed_work=0;
 size_t allocations_before=minyar_pool_allocation_count;
 if(borrowed)minyar_rc_borrow(value);else minyar_rc_keep(value);
 assert(observed_calls<=(existing?1u:2u));
 assert(observed_work<=MINYAR_RC_POLL_BUDGET*(existing?1u:2u));
 assert(observed_work==1);
 assert(minyar_pool_allocation_count==allocations_before+(existing?0u:1u));
 assert(!rc_pending_count);
 assert(minyar_record_get(value,0)==123);assert(rc_frames->temporary_tail->count==(existing?2u:1u));assert(rc_frames->temporary_tail->values[existing?1:0]==value);
 minyar_rc_step();minyar_rc_leave();drain();
 if(borrowed){assert(minyar_record_get(value,0)==123);minyar_rc_release(value);}
 for(size_t i=0;i<count;i++)minyar_rc_release(held[i]);drain();
 assert(!rc_frames&&!rc_object_count&&!rc_bytes&&!rc_immortal_object_count);assert(minyar_pool_used==rc_bounded_cached_frame_bytes);
 while(rc_free_frames){RcFrame *frame=rc_free_frames;rc_free_frames=frame->previous;minyar_pool_deallocate(frame->locals);minyar_pool_deallocate(frame);}
 rc_bounded_cached_frame_bytes=0;
 assert(!minyar_pool_used);void *whole=minyar_pool_try_allocate(MINYAR_POOL_BYTES);assert(whole==minyar_pool);minyar_pool_deallocate(whole);
 puts("one existing retirement admits chunk; aliases and complete object cleanup passed");
}
