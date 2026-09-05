#define MINYAR_SYSTEM_HEAP 1
#define MINYAR_RC_TESTING 1
#ifndef PAIR_RUNTIME
#define PAIR_RUNTIME "../runtime/minyar_runtime.c"
#endif
#include PAIR_RUNTIME
#include <assert.h>
static const struct { size_t ownership; MinyarText value; } literal={0,{(const unsigned char *)"x",1,1,NULL}};
static RcObject *ids[1024];static size_t id_count;
static size_t id(RcObject *p) {
    if(!p)return 0;
    for(size_t i=0;i<id_count;i++)if(ids[i]==p)return i+1;
    assert(0);return 0;
}
static void remember(void *p){ids[id_count++]=(RcObject *)p-1;}
static void list_queue(RcObject *p) {
    while(p){printf(" %zu:%zu",id(p),rc_bounded_saved_cursor(p));p=(RcObject *)(p->ownership&~(size_t)7);}
}
static void snapshot(size_t work,void *shared) {
    printf("%zu,%zu,%zu,%zu,%zu,%zu,%u,%u,%zu O",work,rc_pending_count,rc_object_count,rc_bytes,
           id(rc_bounded_active),rc_bounded_cursor,rc_bounded_recent_turn,rc_bounded_next_queue,
           shared?((RcObject *)shared-1)->ownership>>3:0);
    list_queue(rc_bounded_head);printf(" R");list_queue(rc_bounded_recent_head);
    printf(" T%zu/%zu\n",id(rc_bounded_tail),id(rc_bounded_recent_tail));
}
int main(void) {
 for(size_t budget=1;budget<=33;budget++)for(int kind=0;kind<11;kind++)for(int parity=0;parity<2;parity++) {
    id_count=0;rc_bounded_recent_turn=(unsigned)parity;rc_bounded_next_queue=2;rc_bounded_cursor=719;
    void *root=NULL,*shared=NULL;
    if(kind==1){shared=minyar_record_new_scalar(1);minyar_record_set_scalar(shared,0,713);root=shared;minyar_rc_retain(root);remember(root);}
    if(kind==2){root=minyar_record_new(3);remember(root);}
    if(kind==3){root=minyar_list_new();minyar_list_references(root);remember(root);minyar_list_add_take(root,(long long)(uintptr_t)minyar_record_new(1));remember((void *)(uintptr_t)((MinyarList *)root)->values[0]);}
    if(kind==4){root=copy_c_text("owned payload");remember(root);}
    if(kind==8){root=(void *)&literal.value;remember(root);}
    if(kind==9){root=minyar_record_new(1);remember(root);minyar_record_set(root,0,LLONG_MAX);}
    if(kind==10){root=minyar_list_new();remember(root);minyar_list_references(root);minyar_list_add(root,(long long)(uintptr_t)&literal.value);}
    for(size_t i=0;i<67;i++) {
       MinyarRecord *r=minyar_record_new((kind==5&&i%7==0)?2:1);remember(r);
       minyar_record_set_take(r,0,(long long)(uintptr_t)root);root=r;
    }
    if(kind==6){MinyarRecord *other=minyar_record_new(1);remember(other);rc_drop(other);}
    rc_drop(root);
    if(kind==7) {assert(minyar_rc_poll(1)==1);} /* Start with active/visited fallback. */
    printf("CASE %zu %d %d\n",budget,kind,parity);snapshot(0,shared);
    while(rc_pending_count){size_t work=minyar_rc_poll(budget);assert(work>0&&work<=budget);snapshot(work,shared);}
    if(shared){assert(minyar_record_get(shared,0)==713);minyar_rc_release(shared);}
    assert(!rc_object_count&&!rc_bytes&&!rc_heap_allocation_count);
 }
}
