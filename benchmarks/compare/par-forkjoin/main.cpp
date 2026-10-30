// C++ peer for main.min: the same fork-join on a hand-written work-stealing pool
// (Chase-Lev deques, 4 threads including the caller, stack tasks, help-while-waiting).
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <thread>
#include <vector>

constexpr int THREADS = 4, SIZE = 4096, CUTOFF = 25, LEAF = 4096;
struct Task { void (*run)(void *); void *arg; std::atomic<int> done{0}; };
struct Deque { alignas(64) std::atomic<long long> top{0}; alignas(64) std::atomic<long long> bottom{0}; std::atomic<Task *> slots[SIZE]; };
static Deque deques[THREADS];
static std::atomic<bool> active{true};
static thread_local int self = 0;

static bool push(Deque &d, Task *t) {
    long long b = d.bottom.load(std::memory_order_relaxed), top = d.top.load(std::memory_order_acquire);
    if (b - top >= SIZE) return false;
    d.slots[b & (SIZE - 1)].store(t, std::memory_order_relaxed);
    d.bottom.store(b + 1, std::memory_order_release);
    return true;
}
static Task *pop(Deque &d) {
    long long b = d.bottom.load(std::memory_order_relaxed) - 1;
    d.bottom.store(b, std::memory_order_relaxed);
    std::atomic_thread_fence(std::memory_order_seq_cst);
    long long t = d.top.load(std::memory_order_relaxed);
    Task *x = nullptr;
    if (t <= b) {
        x = d.slots[b & (SIZE - 1)].load(std::memory_order_relaxed);
        if (t == b) {
            if (!d.top.compare_exchange_strong(t, t + 1)) x = nullptr;
            d.bottom.store(b + 1, std::memory_order_relaxed);
        }
    } else d.bottom.store(b + 1, std::memory_order_relaxed);
    return x;
}
static Task *steal(Deque &d) {
    long long t = d.top.load(std::memory_order_acquire);
    std::atomic_thread_fence(std::memory_order_seq_cst);
    long long b = d.bottom.load(std::memory_order_acquire);
    if (t >= b) return nullptr;
    Task *x = d.slots[t & (SIZE - 1)].load(std::memory_order_relaxed);
    if (!d.top.compare_exchange_strong(t, t + 1)) return nullptr;
    return x;
}
static void execute(Task *t) { t->run(t->arg); t->done.store(1, std::memory_order_release); }
static bool steal_once() {
    for (int k = 1; k < THREADS; ++k) if (Task *t = steal(deques[(self + k) % THREADS])) { execute(t); return true; }
    return false;
}
static void idle(unsigned &n) {
    if (++n < 64) {
#if defined(__x86_64__)
        __builtin_ia32_pause();
#elif defined(__aarch64__)
        __asm__ __volatile__("yield");
#endif
    } else std::this_thread::yield();
}
static void join(void (*a)(void *), void *ea, void (*b)(void *), void *eb) {
    Task task{b, eb};
    if (!push(deques[self], &task)) { a(ea); b(eb); return; }
    a(ea);
    Task *p = pop(deques[self]);
    if (p == &task) { b(eb); return; }
    if (p) push(deques[self], p);
    unsigned n = 0;
    while (!task.done.load(std::memory_order_acquire)) { if (steal_once()) n = 0; else idle(n); }
}
static void worker(int k) {
    self = k;
    unsigned n = 0;
    while (active.load(std::memory_order_acquire)) {
        if (Task *t = pop(deques[self])) { execute(t); n = 0; continue; }
        if (steal_once()) n = 0; else idle(n);
    }
}

static long long fib_serial(long long n) { return n < 2 ? n : fib_serial(n - 1) + fib_serial(n - 2); }
struct Fib { long long n, result; };
static void fib(void *arg) {
    auto *f = static_cast<Fib *>(arg);
    if (f->n < CUTOFF) { f->result = fib_serial(f->n); return; }
    Fib l{f->n - 1, 0}, r{f->n - 2, 0};
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
struct Sum { const long long *values; long long first, after, result; };
static void total(void *arg) {
    auto *s = static_cast<Sum *>(arg);
    if (s->after - s->first <= LEAF) { long long sum = 0; for (long long i = s->first; i < s->after; ++i) sum += s->values[i]; s->result = sum; return; }
    long long middle = s->first + (s->after - s->first) / 2;
    Sum l{s->values, s->first, middle, 0}, r{s->values, middle, s->after, 0};
    join(total, &l, total, &r);
    s->result = l.result + r.result;
}

int main(int, char **argv) {
    long long n = std::atoll(argv[1]);
    std::vector<std::thread> threads;
    for (int k = 1; k < THREADS; ++k) threads.emplace_back(worker, k);
    Fib f{n, 0};
    fib(&f);
    std::printf("fib %lld %lld\n", n, f.result);
    long long count = n * 262144;
    std::vector<long long> values((size_t)count);
    for (long long i = 0; i < count; ++i) values[(size_t)i] = (mix(i) >> 40) & 65535;
    Sum s{values.data(), 0, count, 0};
    total(&s);
    std::printf("sum %lld %lld\n", count, s.result);
    active.store(false);
    for (auto &t : threads) t.join();
}
