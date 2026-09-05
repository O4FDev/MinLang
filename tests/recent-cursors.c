#define MINYAR_BOUNDED_HEAP 1
#define MINYAR_LAZY_HEAP 1
#define MINYAR_RC_TESTING 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>
int main(void) {
    for (size_t n=1;n<=130;n++) {
        MinyarRecord *r=minyar_record_new((long long)n);
        unsigned char *map=(unsigned char *)(r->values+n);
        for(size_t i=0;i<n;i++) map[i]=(unsigned char)(i%2);
        for(size_t c=0;c<=n;c++) {
            rc_bounded_save_cursor((RcObject *)r-1,c);
            assert(rc_bounded_saved_cursor((RcObject *)r-1)==c);
            for(size_t i=0;i<n;i++) assert((map[i]&1)==i%2);
        }
        rc_bounded_save_cursor((RcObject *)r-1,0);
        minyar_rc_release(r);
        while(rc_pending_count) minyar_rc_poll(1);
    }
    const size_t lengths[]={255,256,257,16383,16384,16385};
    for(size_t i=0;i<sizeof(lengths)/sizeof(*lengths);i++) {
        size_t n=lengths[i]; MinyarRecord *r=minyar_record_new((long long)n);
        size_t cs[]={0,1,127,128,255,256,n-1,n};
        for(size_t j=0;j<sizeof(cs)/sizeof(*cs);j++) if(cs[j]<=n) {
            rc_bounded_save_cursor((RcObject *)r-1,cs[j]);
            assert(rc_bounded_saved_cursor((RcObject *)r-1)==cs[j]);
        }
        rc_bounded_save_cursor((RcObject *)r-1,0);
        minyar_rc_release(r); while(rc_pending_count) minyar_rc_poll(1);
    }
    assert(!minyar_pool_used);
    puts("cursor encoding preserves reference flags and all tested bit boundaries");
}
