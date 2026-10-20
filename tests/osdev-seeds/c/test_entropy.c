/* Host tests for the conventional C virtio entropy driver.
 * Prints "C ENTROPY HOST PASS" and exits 0, or names the failing case and
 * exits 1. Meant to run clean under -fsanitize=address,undefined. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "model.h"

#define SENTINEL 0xEE /* caller-side fill; model_byte() never produces it */
#define QSIZE 4
#define ROUNDS 6      /* > QSIZE, so ring positions wrap */

static char case_name[96];

#define CHECK(cond, what)                                                      \
    do {                                                                       \
        if (!(cond)) {                                                         \
            printf("C ENTROPY HOST FAIL: %s: %s (line %d)\n", case_name, what, \
                   __LINE__);                                                  \
            if (model.faults)                                                  \
                printf("  model fault (%u): %s\n", model.faults,              \
                       model.fault_msg);                                       \
            goto out;                                                          \
        }                                                                      \
    } while (0)

/* Fresh queue and model configuration for one case. */
static struct vq *setup(uint16_t start_idx, unsigned delay)
{
    model.delay = delay;
    model.reported_len = -1;
    return model_queue_create(QSIZE, start_idx);
}

/* ROUNDS successful reads of `count` bytes with completion after `delay`. */
static int case_read(size_t count, unsigned delay, uint16_t start_idx)
{
    struct vq *q = setup(start_idx, delay);
    uint8_t *buf = NULL;
    int ok = 0;

    snprintf(case_name, sizeof case_name, "read count=%zu delay=%u start=%u",
             count, delay, (unsigned)start_idx);
    CHECK(q != NULL, "queue allocation");
    for (int r = 0; r < ROUNDS; r++) {
        unsigned gen = model.completions;
        int rc;

        buf = malloc(count);
        CHECK(buf != NULL, "out buffer allocation");
        memset(buf, SENTINEL, count);
        model.saw_poison = 0;

        rc = virtio_entropy_read(q, buf, count, 1000);
        CHECK(rc == 0, "virtio_entropy_read did not return 0");
        CHECK(model.faults == 0, "model recorded a fault");
        CHECK(model.completions == gen + 1, "device did not complete exactly once");
        CHECK(model.saw_poison, "device did not see the 0xA5 poison byte");
        CHECK(buf[0] != 0xA5, "poison byte was not overwritten");
        for (size_t i = 0; i < count; i++)
            CHECK(buf[i] == model_byte(gen, i), "returned bytes differ from the device bytes");
        CHECK(model_live_allocations() == 0, "DMA buffer leaked after read");
        free(buf);
        buf = NULL;
    }
    CHECK(q->last_used == (uint16_t)(start_idx + ROUNDS), "last_used did not advance");
    ok = 1;
out:
    free(buf);
    model_queue_destroy(q);
    return ok;
}

/* Device completes after max_spins: driver must time out and must not free
 * the buffer the device still owns. The late completion must then land in a
 * live buffer; after a device reset the test reclaims it. */
static int case_timeout(void)
{
    struct vq *q = setup(0, 50);
    uint8_t buf[16];
    int ok = 0;
    int rc;

    snprintf(case_name, sizeof case_name, "timeout delay=50 max_spins=10");
    CHECK(q != NULL, "queue allocation");
    memset(buf, SENTINEL, sizeof buf);
    rc = virtio_entropy_read(q, buf, sizeof buf, 10);
    CHECK(rc == -1, "expected -1 (timeout)");
    CHECK(model.faults == 0, "model recorded a fault");
    CHECK(buf[0] == SENTINEL, "caller buffer written on timeout");
    CHECK(model_live_allocations() == 1, "timed-out buffer should stay with the device");

    for (int i = 0; i < 100; i++)
        platform_relax();
    CHECK(model.faults == 0, "late completion did not land in a live buffer");

    model_device_reset(q);
    platform_dma_free(model_phys_to_host(q->desc[0].addr));
    CHECK(model.faults == 0, "reclaim after reset faulted");
    CHECK(model_live_allocations() == 0, "DMA buffer leaked after reset");
    ok = 1;
out:
    model_queue_destroy(q);
    return ok;
}

/* count out of range: -2, no allocation, nothing published. */
static int case_bad_length(size_t count)
{
    struct vq *q = setup(0, 0);
    uint8_t buf[1] = { SENTINEL };
    unsigned gen = model.completions;
    int ok = 0;

    snprintf(case_name, sizeof case_name, "bad length count=%zu", count);
    CHECK(q != NULL, "queue allocation");
    CHECK(virtio_entropy_read(q, buf, count, 1000) == -2, "expected -2 (bad length)");
    CHECK(q->avail->idx == 0, "request published for a bad length");
    CHECK(model.completions == gen, "device completed a bad-length request");
    CHECK(model.faults == 0, "model recorded a fault");
    CHECK(model_live_allocations() == 0, "DMA buffer leaked");
    ok = 1;
out:
    model_queue_destroy(q);
    return ok;
}

/* Device reports len = count + 1: driver must reject it and free. */
static int case_overlong_report(void)
{
    struct vq *q = setup(0, 3);
    uint8_t buf[16];
    int ok = 0;

    snprintf(case_name, sizeof case_name, "device reports len > count");
    CHECK(q != NULL, "queue allocation");
    memset(buf, SENTINEL, sizeof buf);
    model.reported_len = (long)sizeof buf + 1;
    CHECK(virtio_entropy_read(q, buf, sizeof buf, 1000) == -2, "expected -2 (bad length)");
    CHECK(buf[0] == SENTINEL, "caller buffer written for a bad completion");
    CHECK(model.faults == 0, "model recorded a fault");
    CHECK(model_live_allocations() == 0, "DMA buffer leaked");
    ok = 1;
out:
    model_queue_destroy(q);
    return ok;
}

/* Device reports len = count - 1: only that many bytes are copied. */
static int case_short_report(void)
{
    struct vq *q = setup(0, 3);
    uint8_t buf[16];
    unsigned gen = model.completions;
    int ok = 0;

    snprintf(case_name, sizeof case_name, "device reports len < count");
    CHECK(q != NULL, "queue allocation");
    memset(buf, SENTINEL, sizeof buf);
    model.reported_len = (long)sizeof buf - 1;
    CHECK(virtio_entropy_read(q, buf, sizeof buf, 1000) == 0, "expected 0");
    for (size_t i = 0; i + 1 < sizeof buf; i++)
        CHECK(buf[i] == model_byte(gen, i), "returned bytes differ from the device bytes");
    CHECK(buf[sizeof buf - 1] == SENTINEL, "copied past the reported length");
    CHECK(model.faults == 0, "model recorded a fault");
    CHECK(model_live_allocations() == 0, "DMA buffer leaked");
    ok = 1;
out:
    model_queue_destroy(q);
    return ok;
}

int main(void)
{
    static const size_t counts[] = { 1, 16, 64, VIRTIO_ENTROPY_MAX_READ };
    static const unsigned delays[] = { 0, 3, 50 };

    for (size_t c = 0; c < sizeof counts / sizeof counts[0]; c++)
        for (size_t d = 0; d < sizeof delays / sizeof delays[0]; d++)
            if (!case_read(counts[c], delays[d], 0))
                return 1;
    if (!case_read(16, 3, 0xFFFE)) /* 16-bit index wrap */
        return 1;
    if (!case_timeout())
        return 1;
    if (!case_bad_length(0) || !case_bad_length(VIRTIO_ENTROPY_MAX_READ + 1))
        return 1;
    if (!case_overlong_report() || !case_short_report())
        return 1;
    if (model.faults != 0) {
        printf("C ENTROPY HOST FAIL: model fault: %s\n", model.fault_msg);
        return 1;
    }
    if (model_live_allocations() != 0) {
        printf("C ENTROPY HOST FAIL: %zu DMA buffers still live\n", model_live_allocations());
        return 1;
    }
    printf("C ENTROPY HOST PASS\n");
    return 0;
}
