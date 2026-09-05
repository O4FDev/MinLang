#define MINYAR_RC_TESTING
#include MINYAR_RUNTIME_SOURCE
#include <assert.h>
static size_t calls;
size_t minyar_rc_poll(size_t budget) { ++calls; return probe_poll_impl(budget); }
int main(void) {
 minyar_rc_enter(0);
 for (int i=0; i<25; ++i) {
  MinyarRecord *value=minyar_record_new_scalar(1);
  minyar_record_set_scalar(value,0,i);
  assert(!rc_pending_count);
  calls=0;
  minyar_rc_keep(value);
  assert(calls==0);
  assert(rc_bounded_last_work==0);
  assert(minyar_record_get(value,0)==i);
 }
 minyar_rc_step();minyar_rc_leave();
 while(rc_pending_count) assert(minyar_rc_poll(MINYAR_RC_POLL_BUDGET)>0);
 assert(!rc_frames&&!rc_object_count&&!rc_bytes&&!rc_immortal_object_count);
 puts("idle keep avoids cleanup calls and retires all owners");
}
