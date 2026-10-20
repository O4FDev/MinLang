/* Conventional C counterpart of Minyar's readOneEntropyByte
 * (os/shared/virtio/virtio.min): allocate, poison, submit one
 * device-writable descriptor, poll the used ring, copy out, free.
 * Written the way a Linux/SerenityOS driver would be: raw ring writes,
 * explicit barriers, no ownership wrappers. */
#include <string.h>

#include "virtio_entropy.h"

/* Linux-style single-copy accessors. */
#define READ_ONCE(x)     __atomic_load_n(&(x), __ATOMIC_RELAXED)
#define WRITE_ONCE(x, v) __atomic_store_n(&(x), (v), __ATOMIC_RELAXED)

int virtio_entropy_read(struct vq *q, uint8_t *out, size_t count, long max_spins)
{
    uint8_t *buf;
    uint16_t avail_idx, used_idx;
    uint32_t len;
    long spins = 0;

    if (count == 0 || count > VIRTIO_ENTROPY_MAX_READ)
        return -2;

    buf = platform_dma_alloc(count, 64);
    if (!buf)
        return -3;
    buf[0] = 0xA5; /* poison: a completion that writes nothing stays visible */

    /* One descriptor, head index 0, device writes into buf. */
    q->desc[0].addr = platform_virt_to_phys(buf); /* SEED:phys */
    q->desc[0].len = (uint32_t)count;
    q->desc[0].flags = VRING_DESC_F_WRITE;
    q->desc[0].next = 0;

    /* Publish: ring entry and descriptor must be visible before idx. */
    avail_idx = q->avail->idx;
    q->avail->ring[avail_idx % q->size] = 0;
    __atomic_thread_fence(__ATOMIC_RELEASE); /* SEED:fence-publish */
    WRITE_ONCE(q->avail->idx, (uint16_t)(avail_idx + 1));
    q->notify(q);

    /* Poll the used ring. */
    while (READ_ONCE(q->used->idx) == q->last_used) { /* SEED:poll */
        if (spins++ >= max_spins)
            return -1; /* device may still DMA into buf: do not free it */
        platform_relax();
    }
    /* Used entry and buffer contents are only valid after idx is seen. */
    __atomic_thread_fence(__ATOMIC_ACQUIRE); /* SEED:fence-acquire */

    /* Only one descriptor is ever in flight, so the used id is always 0. */
    used_idx = q->last_used;
    len = q->used->ring[used_idx % q->size].len;
    q->last_used = (uint16_t)(used_idx + 1);

    if (len > count) {
        platform_dma_free(buf);
        return -2;
    }
    memcpy(out, buf, len); /* SEED:read */
    platform_dma_free(buf); /* SEED:free */
    return 0;
}
