/* Native host coordination for deterministic C fixtures on POSIX/Windows. */
typedef struct { void (*run)(void *); void *argument; } RcTestStart;
#ifdef _WIN32
typedef HANDLE RcTestThread;
static inline unsigned __stdcall rc_test_entry(void *p) {
    RcTestStart start = *(RcTestStart *)p;
    free(p);
    start.run(start.argument);
    return 0;
}
#else
typedef pthread_t RcTestThread;
static inline void *rc_test_entry(void *p) {
    RcTestStart start = *(RcTestStart *)p;
    free(p);
    start.run(start.argument);
    return NULL;
}
#endif
static inline RcTestThread rc_test_start(void (*run)(void *), void *argument) {
    RcTestStart *start = malloc(sizeof(*start));
    assert(start);
    *start = (RcTestStart){run, argument};
#ifdef _WIN32
    RcTestThread thread = (HANDLE)_beginthreadex(NULL, 0, rc_test_entry, start, 0, NULL);
    assert(thread);
#else
    RcTestThread thread;
    assert(!pthread_create(&thread, NULL, rc_test_entry, start));
#endif
    return thread;
}
static inline void rc_test_join(RcTestThread thread) {
#ifdef _WIN32
    assert(WaitForSingleObject(thread, INFINITE) == WAIT_OBJECT_0);
    assert(CloseHandle(thread));
#else
    assert(!pthread_join(thread, NULL));
#endif
}
typedef struct { RcThreadMutex mutex; RcThreadCondition changed; unsigned count, target; } RcTestGate;
static inline void rc_test_gate_init(RcTestGate *g, unsigned target) {
    assert(!rc_thread_mutex_init(&g->mutex));
    assert(!rc_thread_condition_init(&g->changed));
    g->count = 0;
    g->target = target;
}
static inline void rc_test_gate_arrive(RcTestGate *g) {
    rc_thread_mutex_lock(&g->mutex);
    if (++g->count == g->target) rc_thread_condition_wake(&g->changed);
    while (g->count < g->target) rc_thread_condition_wait(&g->changed, &g->mutex);
    rc_thread_mutex_unlock(&g->mutex);
}
static inline void rc_test_gate_dispose(RcTestGate *g) {
    rc_thread_condition_destroy(&g->changed);
    rc_thread_mutex_destroy(&g->mutex);
}
