/* Test integration seam, NOT a proposed stable runtime ABI.
 * Supply --adapter /absolute/path/to/header.h to map these three operations to
 * a future runtime/event-loop implementation. The header is included after the
 * runtime and must define ACCEPTANCE_HAS_EVENT_SCOPE, ACCEPTANCE_HAS_IDLE,
 * acceptance_event_begin(size_t), acceptance_event_end(void), and
 * acceptance_idle(size_t, int (*ready)(void *), void *).
 *
 * The baseline below faithfully represents the missing host integration:
 * event boundaries do nothing and idle opportunities perform no cleanup.
 * Capability tests FAIL for these defaults. They are not a candidate fix.
 */
#define ACCEPTANCE_HAS_EVENT_SCOPE 0
#define ACCEPTANCE_HAS_IDLE 0
static void acceptance_event_begin(size_t budget) { (void)budget; }
static void acceptance_event_end(void) {}
static size_t acceptance_idle(size_t budget, int (*ready)(void *), void *context) {
    (void)budget; (void)ready; (void)context;
    return 0;
}
