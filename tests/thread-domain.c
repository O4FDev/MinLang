#define MINYAR_RC_TESTING 1
#ifdef MINYAR_TEST_CYCLES
#include "../build/thread-cycle-engine.c"
#else
#include "../runtime/minyar_runtime.c"
#endif
#include <assert.h>
#include <stdatomic.h>
static _Atomic unsigned destroyed;
static void release_leaf(void *p) { assert(p == &destroyed); atomic_fetch_add(&destroyed, 1); }
static void exercise(void) {
    rc_thread_domain_init();
    minyar_rc_enter(2);
    RcThreadLeaf *leaf = rc_allocate_object(sizeof(*leaf), 0);
    *leaf = (RcThreadLeaf){&destroyed, release_leaf};
    minyar_rc_local_take(0, leaf);
    minyar_rc_retain(leaf);
    minyar_rc_release(leaf);
    MinyarText *literal = minyar_thread_text_literal(&(MinyarText){
        .bytes = (const unsigned char *)"λ🐈", .byte_length = 6});
    assert(minyar_text_length(literal) == 2);
    minyar_rc_local_take(1, literal);
    (void)minyar_integer_text(7);
    (void)minyar_character_text('x');
#ifdef MINYAR_TEST_CYCLES
    MinyarRecord *cycle = minyar_record_new_traced(2);
    minyar_record_set_reference_traced(cycle, 0, (long long)(uintptr_t)cycle);
    minyar_record_set_reference_traced(cycle, 1, (long long)(uintptr_t)leaf);
    minyar_rc_release(cycle);
#endif
    minyar_rc_leave();
    rc_thread_domain_dispose();
    assert(rc_object_count == 0 && rc_bytes == 0);
}
#ifndef _WIN32
static void *worker(void *p) { (void)p; exercise(); return NULL; }
#endif
int main(void) {
#ifndef _WIN32
    pthread_t threads[4];
    for (unsigned i = 0; i < 4; i++) assert(!pthread_create(&threads[i], NULL, worker, NULL));
    for (unsigned i = 0; i < 4; i++) assert(!pthread_join(threads[i], NULL));
    assert(atomic_load(&destroyed) == 4);
#else
    exercise();
    assert(atomic_load(&destroyed) == 1);
#endif
    puts("thread domain TLS, leaf destruction and cleanup passed");
}
