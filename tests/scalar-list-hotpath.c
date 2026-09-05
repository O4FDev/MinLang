#define MINYAR_BOUNDED_HEAP 1
#define MINYAR_LAZY_HEAP 1
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>
int main(void) {
    const long long values[]={LLONG_MIN,LLONG_MAX,0,1,-1,7,8,9};
    for(unsigned take=0;take<2;take++) {
        MinyarList *list=minyar_list_new();
        for(size_t i=0;i<127;i++) minyar_list_add(list,0);
        list->length=0; /* Reserve capacity without triggering growth in tested path. */
        MinyarRecord *old=minyar_record_new(8192);
        rc_drop(old); assert(minyar_rc_poll(1)==1);
        RcObject *active=rc_bounded_active; size_t cursor=rc_bounded_cursor;
        for(size_t i=0;i<127;i++) {
            long long value=values[i%8];
            if(take) minyar_list_add_take(list,value);else minyar_list_add(list,value);
            assert(minyar_list_get(list,(long long)i)==value);
            assert(rc_bounded_active==active && rc_bounded_cursor==cursor);
        }
        minyar_rc_release(list);while(rc_pending_count) minyar_rc_poll(1);
        assert(!rc_bytes&&!rc_object_count&&!minyar_pool_used);
    }
    puts("scalar add/take preserves all bit patterns and performs no unrelated retirement");
}
