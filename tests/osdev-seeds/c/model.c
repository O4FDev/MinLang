/* Host device model and platform hooks for the C entropy driver. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "model.h"

#define MODEL_MAX_ALLOCS 64

struct model_state model = { .reported_len = -1 };

struct dma_alloc {
    uintptr_t base; /* 0 = free slot */
    size_t size;    /* requested size (bounds checks use this, not the rounding) */
};

static struct dma_alloc allocs[MODEL_MAX_ALLOCS];

static void fault(const char *msg)
{
    if (model.faults++ == 0)
        snprintf(model.fault_msg, sizeof model.fault_msg, "%s", msg);
}

uint8_t model_byte(unsigned gen, size_t i)
{
    return (uint8_t)(0x10 + (i + 7u * gen) % 0x80);
}

size_t model_live_allocations(void)
{
    size_t n = 0;
    for (size_t i = 0; i < MODEL_MAX_ALLOCS; i++)
        n += allocs[i].base != 0;
    return n;
}

/* ---- platform hooks ---- */

void *platform_dma_alloc(size_t size, size_t align)
{
    size_t rounded;
    void *p;

    if (align == 0 || (align & (align - 1)) != 0)
        return NULL;
    /* C11 aligned_alloc wants size to be a multiple of align. */
    rounded = size == 0 ? align : (size + align - 1) & ~(align - 1);
    for (size_t i = 0; i < MODEL_MAX_ALLOCS; i++) {
        if (allocs[i].base != 0)
            continue;
        p = aligned_alloc(align, rounded);
        if (!p)
            return NULL;
        allocs[i].base = (uintptr_t)p;
        allocs[i].size = size;
        return p;
    }
    fault("DMA allocation table full");
    return NULL;
}

/* Does the descriptor at `head` currently name memory inside [base, base+size)? */
static int desc_overlaps(const struct vq *q, uint16_t head, uintptr_t base, size_t size)
{
    const struct vring_desc *d = &q->desc[head];
    uintptr_t host;

    if (d->addr < PHYS_OFFSET)
        return 0;
    host = (uintptr_t)(d->addr - PHYS_OFFSET);
    return host < base + size && base < host + d->len;
}

void platform_dma_free(void *p)
{
    uintptr_t base = (uintptr_t)p;

    if (!p)
        return;
    for (size_t i = 0; i < MODEL_MAX_ALLOCS; i++) {
        if (allocs[i].base != base)
            continue;
        /* Freeing a buffer the device has not completed yet. */
        if (model.pending_q) {
            struct vq *q = model.pending_q;
            for (uint16_t a = model.last_avail; a != q->avail->idx; a++) {
                uint16_t head = q->avail->ring[a % q->size];
                if (head < q->size && desc_overlaps(q, head, base, allocs[i].size))
                    fault("DMA buffer freed while the device still owns it");
            }
        }
        allocs[i].base = 0;
        allocs[i].size = 0;
        free(p);
        return;
    }
    fault("free of a pointer that is not a live DMA buffer");
}

uint64_t platform_virt_to_phys(const void *p)
{
    return (uint64_t)(uintptr_t)p + PHYS_OFFSET;
}

void *model_phys_to_host(uint64_t phys)
{
    return (void *)(uintptr_t)(phys - PHYS_OFFSET);
}

/* Host pointer for [phys, phys+len) if it lies inside one live allocation. */
static uint8_t *live_range(uint64_t phys, uint32_t len)
{
    uintptr_t host;

    if (phys < PHYS_OFFSET)
        return NULL;
    host = (uintptr_t)(phys - PHYS_OFFSET);
    for (size_t i = 0; i < MODEL_MAX_ALLOCS; i++) {
        struct dma_alloc *a = &allocs[i];
        if (a->base != 0 && host >= a->base && len <= a->size &&
            host - a->base <= a->size - len)
            return (uint8_t *)host;
    }
    return NULL;
}

/* ---- device ---- */

/* Consume every new avail entry: fill the buffer and post a used entry. */
static void model_complete(struct vq *q)
{
    uint16_t avail_idx = __atomic_load_n(&q->avail->idx, __ATOMIC_ACQUIRE);

    while (model.last_avail != avail_idx) {
        uint16_t head = q->avail->ring[model.last_avail % q->size];
        struct vring_desc *d;
        uint8_t *host;
        uint16_t used_idx;
        uint32_t len;

        model.last_avail++;
        if (head >= q->size) {
            fault("avail ring names a descriptor outside the table");
            continue;
        }
        d = &q->desc[head];
        if (!(d->flags & VRING_DESC_F_WRITE)) {
            fault("descriptor is not device-writable");
            continue;
        }
        if (d->flags & VRING_DESC_F_NEXT) {
            fault("unexpected chained descriptor");
            continue;
        }
        if (d->len == 0) {
            fault("zero-length descriptor");
            continue;
        }
        host = live_range(d->addr, d->len);
        if (!host) {
            fault("descriptor address is not a live DMA buffer");
            continue;
        }
        model.saw_poison = host[0] == 0xA5;
        for (uint32_t i = 0; i < d->len; i++)
            host[i] = model_byte(model.completions, i);

        len = model.reported_len < 0 ? d->len : (uint32_t)model.reported_len;
        used_idx = q->used->idx;
        q->used->ring[used_idx % q->size].id = head;
        q->used->ring[used_idx % q->size].len = len;
        __atomic_store_n(&q->used->idx, (uint16_t)(used_idx + 1), __ATOMIC_RELEASE);
        model.completions++;
    }
}

void model_notify(struct vq *q)
{
    if (__atomic_load_n(&q->avail->idx, __ATOMIC_ACQUIRE) == model.last_avail) {
        fault("notify without a new avail entry");
        return;
    }
    if (model.delay == 0) {
        model_complete(q);
        return;
    }
    model.pending_q = q;
    model.countdown = model.delay;
}

void platform_relax(void)
{
    struct vq *q = model.pending_q;

    if (!q || model.countdown == 0)
        return;
    if (--model.countdown == 0) {
        model_complete(q);
        model.pending_q = NULL;
    }
}

void model_device_reset(struct vq *q)
{
    model.pending_q = NULL;
    model.countdown = 0;
    model.last_avail = q->avail->idx;
}

/* ---- rings ---- */

struct vq *model_queue_create(uint16_t size, uint16_t start_idx)
{
    struct vq *q = calloc(1, sizeof *q);

    if (!q)
        return NULL;
    q->desc = calloc(size, sizeof *q->desc);
    q->avail = calloc(1, sizeof *q->avail + (size + 1u) * sizeof(uint16_t));
    q->used = calloc(1, sizeof *q->used + size * sizeof(struct vring_used_elem) +
                            sizeof(uint16_t));
    if (!q->desc || !q->avail || !q->used) {
        model_queue_destroy(q);
        return NULL;
    }
    q->size = size;
    q->avail->idx = start_idx;
    q->used->idx = start_idx;
    q->last_used = start_idx;
    q->notify = model_notify;

    model.pending_q = NULL;
    model.countdown = 0;
    model.last_avail = start_idx;
    return q;
}

void model_queue_destroy(struct vq *q)
{
    if (!q)
        return;
    if (model.pending_q == q)
        model.pending_q = NULL;
    free(q->desc);
    free(q->avail);
    free(q->used);
    free(q);
}
