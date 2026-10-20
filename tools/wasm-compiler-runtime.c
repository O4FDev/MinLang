/* The real self-hosted frontend runs once per isolated WASI instance. */
#define MINYAR_COMPILER_ARENA 1
#define MINYAR_MAX_CALL_DEPTH 1024u
#include "../runtime/minyar_runtime.c"

/* WASI's C startup calls __main_argc_argv rather than the raw LLVM main. */
extern int minyar_wasm_main(int argc, char **argv);
int main(int argc, char **argv) { return minyar_wasm_main(argc, argv); }
