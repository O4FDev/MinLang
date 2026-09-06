#include <alloca.h>
#include <assert.h>
#include <stdint.h>
#define MINYAR_RC_TESTING 1
#include MINYAR_RUNTIME_SOURCE
#ifdef STACK_BASELINE
static void minyar_rc_enter_stack_v1(void *header, void *storage, long long n) {
    (void)header; (void)storage; minyar_rc_enter(n);
}
static void minyar_rc_leave_stack_v1(void *header) { (void)header; minyar_rc_leave(); }
#endif
int main(void) {
    const long long sizes[] = {0,1,8,9};
    for (size_t i=0;i<sizeof(sizes)/sizeof(*sizes);++i) {
        void *header=alloca(64), *storage=alloca(16*(sizes[i]+1));
        memset(header,0x5a,64); memset(storage,0x6b,16*(sizes[i]+1));
        minyar_rc_enter_stack_v1(header,storage,sizes[i]);
#ifdef MINYAR_COMPILER_ARENA
        for(size_t j=0;j<64;++j) assert(((unsigned char*)header)[j]==0x5a);
        for(size_t j=0;j<16*(size_t)(sizes[i]+1);++j) assert(((unsigned char*)storage)[j]==0x6b);
#else
        assert(rc_frames != header && rc_frames->local_count == (size_t)sizes[i]);
        MinyarText *p=copy_c_text("borrowed return is retained before eager fallback leave");
        if(sizes[i]) minyar_rc_local(0,p);
        minyar_rc_borrow(p);
#endif
        minyar_rc_leave_stack_v1(header);
#ifdef MINYAR_COMPILER_ARENA
        for(size_t j=0;j<64;++j) assert(((unsigned char*)header)[j]==0x5a);
        for(size_t j=0;j<16*(size_t)(sizes[i]+1);++j) assert(((unsigned char*)storage)[j]==0x6b);
#else
        assert(!rc_frames && ((RcObject*)p-1)->ownership >> 3 == 1);
        assert(p->byte_length > 0); minyar_rc_release(p); assert(!rc_object_count && !rc_bytes);
        while(rc_free_frames) {
            RcFrame *f=rc_free_frames; rc_free_frames=f->previous;
            assert(f!=header && f->locals!=storage);
            free(f->locals); free(f->temporaries); free(f);
        }
#endif
    }
    puts("PASS private API eager fallback / arena no-op profile");
    return 0;
}
