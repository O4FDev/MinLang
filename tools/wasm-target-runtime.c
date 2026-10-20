/* Browser/WASI programs retain the complete ordinary language runtime,
 * including escaping callbacks and cyclic managed graphs. Eager reclamation
 * uses libc storage without the native-only bounded stack ownership ABI. */
#define MINYAR_MAP_CYCLE_RUNTIME 1
#define MINYAR_SORT_GRAPH 1
#define MINYAR_RUNTIME_CALLBACKS 1
#define MINYAR_NOINLINE __attribute__((noinline))
/* The engine execution stack is independent of wasm-ld's linear stack. */
#define MINYAR_MAX_CALL_DEPTH 1024u
#include "../runtime/minyar_runtime.c"
#include "../runtime/minyar_stack_frames.h"

/* Clang gives C main the WASI CRT's __main_argc_argv binding. LLVM emitted
 * directly by Minyar needs this small source-level entry adapter. */
extern int minyar_wasm_main(int argc, char **argv);
int main(int argc, char **argv) { return minyar_wasm_main(argc, argv); }
