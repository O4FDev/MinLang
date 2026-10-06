#define MINYAR_COMPILER_ARENA 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>

static size_t arena_used(MinyarArena *arena) {
    size_t used = 0;
    for (MinyarArenaBlock *block = arena->block; block; block = block->next)
        used += block->used;
    return used;
}

int main(void) {
    setvbuf(stdout, NULL, _IONBF, 0);
    MinyarList *source = minyar_list_new();
    for (long long i = 0; i < 1024; i++)
        minyar_list_add(source, i * 37);
    size_t before = arena_used(&list_arena) + arena_used(&large_list_arena);
    MinyarList *result = minyar_list_appended(source, 313, 0, 0);
    size_t retained = arena_used(&list_arena) + arena_used(&large_list_arena) - before;
    printf("appended arena retained bytes=%zu\n", retained);
    assert(result->capacity == 2048 && result->length == 1025);
    if (!getenv("MINYAR_RESEARCH_MEASURE_COUNTS"))
        assert(retained == 2048 * sizeof(long long));
    for (long long i = 0; i < 1024; i++) {
        assert(result->values[i] == i * 37);
        assert(source->values[i] == i * 37);
    }
    assert(result->values[1024] == 313 && source->length == 1024);
    puts("compiler arena reserves only the final backing buffer");
    return 0;
}
