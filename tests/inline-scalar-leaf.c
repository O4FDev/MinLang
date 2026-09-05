#define MINYAR_SYSTEM_HEAP 1
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>
int main(void) {
    MinyarList *list=minyar_list_new();minyar_list_references(list);
    MinyarRecord *shared=minyar_record_new_scalar(1);minyar_record_set_scalar(shared,0,1901);
    for(size_t i=0;i<1024;i++) {
        if(i%2)minyar_list_add(list,(long long)(uintptr_t)shared);
        else minyar_list_add_take(list,(long long)(uintptr_t)minyar_record_new_scalar(2));
    }
    minyar_rc_release(list);
    while(rc_pending_count){assert(minyar_rc_poll(1)==1);assert(minyar_record_get(shared,0)==1901);}
    assert((((RcObject *)shared-1)->ownership>>3)==1);minyar_rc_release(shared);
    assert(!rc_bytes&&!rc_object_count&&!rc_heap_allocation_count);
    puts("inlined List leaf free preserves shared aliases and one-unit visits");
}
