/* Deterministic host model of a virtio-rng device plus the platform hooks
 * (DMA alloc/free, virt->phys, cpu_relax) for host tests. Single-threaded:
 * the "device" runs inside platform_relax(), so it can check addresses,
 * ownership and lengths, but it cannot observe missing memory barriers. */
#ifndef MODEL_H
#define MODEL_H

#include "virtio_entropy.h"

/* Host "physical" addresses are host pointers plus this offset, so a driver
 * that puts a virtual pointer in a descriptor hits no live buffer. Minyar-OS
 * on QEMU identity-maps low memory, where that same mistake is invisible. */
#define PHYS_OFFSET 0x100000000000ULL

struct model_state {
    /* configuration (set by the test) */
    unsigned delay;      /* relax calls between notify and completion; 0 = in notify */
    long reported_len;   /* -1: report the descriptor length in the used ring */

    /* device state */
    struct vq *pending_q; /* request waiting for `countdown` relax calls */
    unsigned countdown;
    uint16_t last_avail;

    /* observations */
    unsigned completions; /* also the generation used for model_byte() */
    int saw_poison;       /* last completed buffer still had 0xA5 at byte 0 */
    unsigned faults;
    char fault_msg[160];  /* first fault */
};

extern struct model_state model;

/* Rings are plain host memory (not counted as DMA buffers). `start_idx`
 * seeds avail->idx, used->idx and last_used to test 16-bit wrap. */
struct vq *model_queue_create(uint16_t size, uint16_t start_idx);
void model_queue_destroy(struct vq *q);

void model_notify(struct vq *q);
void model_device_reset(struct vq *q); /* device drops in-flight requests */

void *model_phys_to_host(uint64_t phys);
uint8_t model_byte(unsigned gen, size_t i); /* never 0xA5 or 0xEE */
size_t model_live_allocations(void);

#endif
