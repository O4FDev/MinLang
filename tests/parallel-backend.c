/* Run the bare-backend path through four actual processor-entry threads. */
#define MINYAR_FREESTANDING 1
#define MINYAR_SYSTEM_HEAP 1
#include "../runtime/minyar_runtime.c"
#include <assert.h>

typedef struct {
    void (*entry)(long long, long long);
    long long arguments, count, first;
} Processor;
static int values[10003];
static int schedules;
static pthread_t owner;
static _Atomic int foreign;

static void *processor(void *argument) {
    Processor *work = argument;
    for (long long item = work->first; item < work->count; item += 4) {
        if (!pthread_equal(pthread_self(), owner)) atomic_store(&foreign, 1);
        work->entry(item, work->arguments);
    }
    return NULL;
}

static void schedule(long long context, long long entry, long long count, long long arguments) {
    assert(context == 42 && count > 0);
    ++schedules;
    Processor work[4];
    pthread_t threads[3];
    for (int index = 0; index < 4; ++index)
        work[index] = (Processor){ (void (*)(long long, long long))(uintptr_t)entry, arguments, count, index };
    for (int index = 1; index < 4; ++index)
        assert(pthread_create(&threads[index - 1], NULL, processor, &work[index]) == 0);
    processor(&work[0]);
    for (int index = 1; index < 4; ++index) assert(pthread_join(threads[index - 1], NULL) == 0);
}

static void fill(long long first, long long after, void *argument) {
    int *output = argument;
    for (long long index = first; index < after; ++index) ++output[index];
}
static long long sum(long long first, long long after, void *argument) {
    (void)argument;
    long long total = 0;
    for (long long index = first; index < after; ++index) total += index;
    return total;
}

int main(void) {
    owner = pthread_self();
    minyar_runtime_setParallelScheduler((long long)(uintptr_t)schedule, 42);
    minyar_parallel_run(fill, 0, 10003, values);
    for (int index = 0; index < 10003; ++index) assert(values[index] == 1);
    assert(minyar_parallel_reduce(sum, 0, 5003, NULL, 1, 5) == 12512508);
    assert(minyar_parallel_reduce(sum, -1000, 1001, NULL, 1, 42) == 42);
    assert(schedules == 3 && atomic_load(&foreign));
    minyar_runtime_setParallelScheduler(0, 0);
    minyar_parallel_run(fill, 1, 3, values);
    assert(values[0] == 1 && values[1] == 2 && values[2] == 2 && values[3] == 1);
    assert(schedules == 3);
    puts("freestanding dispatcher: scalar jobs and reductions joined four processor entries");
}
