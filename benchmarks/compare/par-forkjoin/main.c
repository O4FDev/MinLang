// C peer for main.min: the same fork-join on a hand-written work-stealing pool
// (Chase-Lev deques, 4 threads including the caller, stack tasks, help-while-waiting).
#include <pthread.h>
#include <sched.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

enum { THREADS = 4, SIZE = 4096, CUTOFF = 25, LEAF = 4096 };
typedef struct { void (*run)(void *); void *arg; _Atomic int done; } Task;
typedef struct { _Alignas(64) _Atomic long long top; _Alignas(64) _Atomic long long bottom; _Atomic(Task *) slots[SIZE]; } Deque;
static Deque deques[THREADS];
static _Atomic int active = 1;
static _Thread_local int self;

static int push(Deque *d, Task *t) {
    long long b = atomic_load_explicit(&d->bottom, memory_order_relaxed), top = atomic_load_explicit(&d->top, memory_order_acquire);
    if (b - top >= SIZE) return 0;
    atomic_store_explicit(&d->slots[b & (SIZE - 1)], t, memory_order_relaxed);
    atomic_store_explicit(&d->bottom, b + 1, memory_order_release);
    return 1;
}
static Task *pop(Deque *d) {
    long long b = atomic_load_explicit(&d->bottom, memory_order_relaxed) - 1;
    atomic_store_explicit(&d->bottom, b, memory_order_relaxed);
    atomic_thread_fence(memory_order_seq_cst);
    long long t = atomic_load_explicit(&d->top, memory_order_relaxed);
    Task *x = NULL;
    if (t <= b) {
        x = atomic_load_explicit(&d->slots[b & (SIZE - 1)], memory_order_relaxed);
        if (t == b) {
            if (!atomic_compare_exchange_strong(&d->top, &t, t + 1)) x = NULL;
            atomic_store_explicit(&d->bottom, b + 1, memory_order_relaxed);
        }
    } else atomic_store_explicit(&d->bottom, b + 1, memory_order_relaxed);
    return x;
}
static Task *steal(Deque *d) {
    long long t = atomic_load_explicit(&d->top, memory_order_acquire);
    atomic_thread_fence(memory_order_seq_cst);
    long long b = atomic_load_explicit(&d->bottom, memory_order_acquire);
    if (t >= b) return NULL;
    Task *x = atomic_load_explicit(&d->slots[t & (SIZE - 1)], memory_order_relaxed);
    if (!atomic_compare_exchange_strong(&d->top, &t, t + 1)) return NULL;
    return x;
}
static void execute(Task *t) { t->run(t->arg); atomic_store_explicit(&t->done, 1, memory_order_release); }
static int steal_once(void) {
    for (int k = 1; k < THREADS; ++k) { Task *t = steal(&deques[(self + k) % THREADS]); if (t) { execute(t); return 1; } }
    return 0;
}
static void idle(unsigned *n) {
    if (++*n < 64) {
#if defined(__x86_64__)
        __builtin_ia32_pause();
#elif defined(__aarch64__)
        __asm__ __volatile__("yield");
#endif
    } else sched_yield();
}
static void join(void (*a)(void *), void *ea, void (*b)(void *), void *eb) {
    Task task = { b, eb, 0 };
    if (!push(&deques[self], &task)) { a(ea); b(eb); return; }
    a(ea);
    Task *p = pop(&deques[self]);
    if (p == &task) { b(eb); return; }
    if (p) push(&deques[self], p);
    unsigned n = 0;
    while (!atomic_load_explicit(&task.done, memory_order_acquire)) { if (steal_once()) n = 0; else idle(&n); }
}
static void *worker(void *arg) {
    self = (int)(intptr_t)arg;
    unsigned n = 0;
    while (atomic_load_explicit(&active, memory_order_acquire)) {
        Task *t = pop(&deques[self]);
        if (t) { execute(t); n = 0; continue; }
        if (steal_once()) n = 0; else idle(&n);
    }
    return NULL;
}

static long long fib_serial(long long n) { return n < 2 ? n : fib_serial(n - 1) + fib_serial(n - 2); }
typedef struct { long long n, result; } Fib;
static void fib(void *arg) {
    Fib *f = arg;
    if (f->n < CUTOFF) { f->result = fib_serial(f->n); return; }
    Fib l = { f->n - 1, 0 }, r = { f->n - 2, 0 };
    join(fib, &l, fib, &r);
    f->result = l.result + r.result;
}
static long long mix(long long value) {
    for (long long round = 0; round < 4; ++round) {
        value ^= value >> 31;
        value = (long long)((unsigned long long)value * 0x2545F4914F6CDD1DULL);
        value ^= value >> 29;
        value = (long long)((unsigned long long)value + (unsigned long long)round);
    }
    return value;
}
typedef struct { const long long *values; long long first, after, result; } Sum;
static void total(void *arg) {
    Sum *s = arg;
    if (s->after - s->first <= LEAF) { long long sum = 0; for (long long i = s->first; i < s->after; ++i) sum += s->values[i]; s->result = sum; return; }
    long long middle = s->first + (s->after - s->first) / 2;
    Sum l = { s->values, s->first, middle, 0 }, r = { s->values, middle, s->after, 0 };
    join(total, &l, total, &r);
    s->result = l.result + r.result;
}

int main(int argc, char **argv) {
    (void)argc;
    long long n = atoll(argv[1]);
    pthread_t threads[THREADS - 1];
    for (int k = 1; k < THREADS; ++k) pthread_create(&threads[k - 1], NULL, worker, (void *)(intptr_t)k);
    Fib f = { n, 0 };
    fib(&f);
    printf("fib %lld %lld\n", n, f.result);
    long long count = n * 262144;
    long long *values = malloc((size_t)count * sizeof(long long));
    for (long long i = 0; i < count; ++i) values[i] = (mix(i) >> 40) & 65535;
    Sum s = { values, 0, count, 0 };
    total(&s);
    printf("sum %lld %lld\n", count, s.result);
    atomic_store(&active, 0);
    for (int k = 1; k < THREADS; ++k) pthread_join(threads[k - 1], NULL);
    free(values);
    return 0;
}
