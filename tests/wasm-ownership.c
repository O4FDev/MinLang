/* Use the production WASI target with allocation accounting enabled. */
#define MINYAR_RC_TESTING 1
#include "../tools/wasm-target-runtime.c"

static void assert_wasm_ownership(void) {
    if (rc_object_count != rc_immortal_object_count || rc_pending_count) {
        fprintf(stderr, "WASI ownership retained %zu objects and %zu pending releases\n",
                rc_object_count - rc_immortal_object_count, rc_pending_count);
        exit(90);
    }
    puts("WASI ownership: no live managed objects");
}

void minyar_wasmtest_watch(void) {
    if (atexit(assert_wasm_ownership) != 0) exit(91);
}
