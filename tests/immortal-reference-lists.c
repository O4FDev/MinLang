#define MINYAR_BOUNDED_HEAP 1
#define MINYAR_LAZY_HEAP 1
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>
static const struct { size_t ownership; MinyarText value; } literal={0,{(const unsigned char *)"x",1,1,NULL}};
static unsigned kind(MinyarList *l){return ((RcObject *)l-1)->ownership&7;}
int main(void){
    for(unsigned mode=0;mode<4;mode++) {
        MinyarList *l=minyar_list_new(); minyar_list_references(l);
        assert(kind(l)==RC_REFERENCES_IMMORTAL);
        for(size_t i=0;i<8191;i++) minyar_list_add(l,(long long)(uintptr_t)&literal.value);
        assert(kind(l)==RC_REFERENCES_IMMORTAL);
        if(mode==0){minyar_rc_release(l); assert(!rc_pending_count&&!rc_object_count);continue;}
        MinyarRecord *r=minyar_record_new_scalar(1);
        if(mode==1) minyar_list_add(l,(long long)(uintptr_t)r);
        if(mode==2){minyar_rc_retain(r); minyar_list_add_take(l,(long long)(uintptr_t)r);}
        if(mode==3) minyar_list_set(l,4095,(long long)(uintptr_t)r);
        minyar_list_references(l); /* Internal marking must not demote a populated List. */
        assert(kind(l)==RC_REFERENCES && (((RcObject *)r-1)->ownership>>3)==2);
        minyar_list_set(l,mode==3?4095:8191,(long long)(uintptr_t)&literal.value);
        assert(kind(l)==RC_REFERENCES && (((RcObject *)r-1)->ownership>>3)==1);
        minyar_rc_release(l); while(rc_pending_count) minyar_rc_poll(1); minyar_rc_release(r);
        assert(!rc_bytes&&!minyar_pool_used);
    }
    MinyarRecord *shared=minyar_record_new_scalar(1);
    for(size_t repeat=0;repeat<96;repeat++){
        MinyarList *l=minyar_list_new();minyar_list_references(l);
        for(size_t i=0;i<8191;i++) minyar_list_add_take(l,(long long)(uintptr_t)&literal.value);
        minyar_list_add(l,(long long)(uintptr_t)shared);
        minyar_rc_release(l);
    }
    assert(rc_bytes<300000);
    while(rc_pending_count) minyar_rc_poll(1);minyar_rc_release(shared);
    assert(!rc_bytes&&!minyar_pool_used);
    puts("immortal lists skip scans; add/take/set transitions preserve owners and late-conversion debt");
}
