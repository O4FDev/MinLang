/* Conventional split-virtqueue entropy read (virtio-rng), one descriptor.
 * Layouts follow the virtio 1.x split ring. Fields are little-endian on the
 * wire; this file assumes a little-endian CPU (x86_64) and does no swapping. */
#ifndef VIRTIO_ENTROPY_H
#define VIRTIO_ENTROPY_H

#include <stddef.h>
#include <stdint.h>

#define VRING_DESC_F_NEXT  1
#define VRING_DESC_F_WRITE 2

/* Largest single read the driver accepts (one page). */
#define VIRTIO_ENTROPY_MAX_READ 4096

struct vring_desc {
    uint64_t addr;  /* guest-physical address */
    uint32_t len;
    uint16_t flags;
    uint16_t next;
};

struct vring_avail {
    uint16_t flags;
    uint16_t idx;
    uint16_t ring[];  /* followed by used_event */
};

struct vring_used_elem {
    uint32_t id;
    uint32_t len;
};

struct vring_used {
    uint16_t flags;
    uint16_t idx;
    struct vring_used_elem ring[];  /* followed by avail_event */
};

struct vq {
    struct vring_desc *desc;
    struct vring_avail *avail;
    struct vring_used *used;
    uint16_t size;
    uint16_t last_used;
    void (*notify)(struct vq *);
};

/* Platform hooks (kernel or host model). */
uint64_t platform_virt_to_phys(const void *p);
void *platform_dma_alloc(size_t size, size_t align);
void platform_dma_free(void *p);
void platform_relax(void);  /* cpu_relax() */

/* Read `count` bytes of device entropy into `out`.
 * Returns 0 on success, -1 on timeout, -2 on bad length (count out of range
 * or the device reported more bytes than were offered), -3 if no DMA memory.
 * A short completion (len < count) copies only len bytes.
 * On timeout the buffer is left with the device (not freed): the caller must
 * reset the device before the memory can be reclaimed. */
int virtio_entropy_read(struct vq *q, uint8_t *out, size_t count, long max_spins);

#endif
