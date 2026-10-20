#ifndef MINYAR_DMA_H
#define MINYAR_DMA_H
/* Include once, immediately after minyar_bytes.h in the common runtime.
 * One serialized boot CPU, coherent identity-mapped hardware DMA only; no IRQ
 * allocation, thread safety, IOMMU, cache maintenance or safe-reset claim.
 * Handles are ordinary three-scalar MinyarRecords, never custom RC objects.
 * The registry owns payload references independently of handle RC. */

enum {
    MINYAR_DMA_DEAD, MINYAR_DMA_CPU, MINYAR_DMA_PENDING,
    MINYAR_DMA_COMPLETED, MINYAR_DMA_RETIRED
};
enum { MINYAR_DMA_MODEL = 1, MINYAR_DMA_VIRTIO = 2 };
enum { MINYAR_DMA_MAX_SPINS = 1000000 };

typedef struct MinyarDmaQueue MinyarDmaQueue;
typedef struct MinyarDmaAllocation {
    struct MinyarDmaAllocation *next;
    uint64_t id, incarnation, capability_epoch;
    unsigned state, hardware_pinned;
    MinyarBytes *owner;
    unsigned char *base;
    size_t capacity, accessible, submitted, completed;
    MinyarDmaQueue *queue;
    uint64_t generation;
} MinyarDmaAllocation;

typedef struct {
    volatile uint64_t sequence;
    volatile uint64_t device, queue, slot, generation, length, queue_epoch;
} MinyarDmaCompletion;

struct MinyarDmaQueue {
    MinyarDmaQueue *next;
    uint64_t id, incarnation, epoch, device, generation;
    unsigned kind, failed, used_once;
    MinyarDmaAllocation *active;
    MinyarDmaCompletion completion;
    MinyarRecord *ring_owner;
    uintptr_t descriptors, available, used, notify;
    uint16_t size, index, used_start;
};

static MinyarDmaAllocation *minyar_dma_allocations;
static MinyarDmaQueue *minyar_dma_queues;
/* Shared namespace prevents Queue records from being accepted as Cpu handles
 * even when their incarnation/epoch values happen to coincide. */
static uint64_t minyar_dma_identity_id;

static inline void minyar_dma_fence(void) {
#if defined(__aarch64__)
    __asm__ volatile("dmb sy" ::: "memory");
#elif defined(__x86_64__)
    __asm__ volatile("mfence" ::: "memory");
#else
    __atomic_thread_fence(__ATOMIC_SEQ_CST); /* MODEL only on other targets. */
#endif
}

static inline void minyar_dma_pause(void) {
#if defined(__aarch64__)
    __asm__ volatile("yield" ::: "memory");
#elif defined(__x86_64__)
    __asm__ volatile("pause" ::: "memory");
#else
    __atomic_signal_fence(__ATOMIC_SEQ_CST);
#endif
}

static uint64_t minyar_dma_next(uint64_t value) {
    if (value >= (uint64_t)LLONG_MAX)
        minyar_stop("DMA identity counter exhausted; reuse is forbidden.");
    return value + 1;
}

static MinyarRecord *minyar_dma_handle(uint64_t id, uint64_t incarnation, uint64_t epoch) {
    MinyarRecord *record = minyar_record_new_scalar(3);
    minyar_record_set_scalar(record, 0, (long long)id);
    minyar_record_set_scalar(record, 1, (long long)incarnation);
    minyar_record_set_scalar(record, 2, (long long)epoch);
    return record;
}

static uint64_t minyar_dma_handle_field(const MinyarRecord *record, long long field) {
    if (!record || record->length != 3)
        minyar_stop("DMA requires an opaque three-field handle.");
    long long value = minyar_record_get(record, field);
    if (value <= 0) minyar_stop("DMA handle identity is invalid.");
    return (uint64_t)value;
}

static MinyarDmaAllocation *minyar_dma_allocation(const MinyarRecord *handle, unsigned states) {
    uint64_t id = minyar_dma_handle_field(handle, 0);
    uint64_t incarnation = minyar_dma_handle_field(handle, 1);
    uint64_t epoch = minyar_dma_handle_field(handle, 2);
    for (MinyarDmaAllocation *entry = minyar_dma_allocations; entry; entry = entry->next) {
        if (entry->id != id) continue;
        if (entry->incarnation != incarnation || entry->capability_epoch != epoch ||
            !(states & (1u << entry->state)))
            minyar_stop("DMA capability was moved, retired, disposed, or is in the wrong phase.");
        return entry;
    }
    minyar_stop("DMA allocation identity is unknown.");
}

static MinyarDmaQueue *minyar_dma_queue(const MinyarRecord *handle) {
    uint64_t id = minyar_dma_handle_field(handle, 0);
    uint64_t incarnation = minyar_dma_handle_field(handle, 1);
    uint64_t epoch = minyar_dma_handle_field(handle, 2);
    for (MinyarDmaQueue *queue = minyar_dma_queues; queue; queue = queue->next) {
        if (queue->id != id) continue;
        if (queue->incarnation != incarnation || queue->epoch != epoch)
            minyar_stop("DMA queue incarnation is stale.");
        return queue;
    }
    minyar_stop("DMA queue identity is unknown.");
}

static void minyar_dma_quarantine(MinyarDmaAllocation *entry) {
    entry->state = MINYAR_DMA_RETIRED;
    if (entry->capability_epoch < (uint64_t)LLONG_MAX) entry->capability_epoch++;
    if (entry->queue) entry->queue->failed = 1;
    /* Neither payload, ring owner nor mappings are released here. */
}

static MINYAR_COLD MINYAR_NORETURN void minyar_dma_bad_completion(
        MinyarDmaAllocation *entry, const char *message) {
    minyar_dma_quarantine(entry);
    minyar_stop(message);
}

static uint64_t minyar_dma_transition_epoch(MinyarDmaAllocation *entry) {
    if (entry->capability_epoch >= (uint64_t)LLONG_MAX)
        minyar_dma_bad_completion(entry, "DMA capability epoch exhausted; allocation quarantined.");
    return entry->capability_epoch + 1;
}

static void minyar_dma_bounds(MinyarDmaAllocation *entry, long long offset, long long count) {
    if (offset < 0 || count < 0 || (uint64_t)count > entry->accessible ||
        (uint64_t)offset > entry->accessible - (size_t)count)
        minyar_stop("DMA CPU access is outside its accessible bytes.");
}

MinyarRecord *minyar_dma_allocate(long long size, long long alignment) {
    if (size <= 0 || alignment <= 0 || ((uint64_t)alignment & ((uint64_t)alignment - 1)) ||
        (uint64_t)size > (uint64_t)LLONG_MAX - (uint64_t)alignment + 1 ||
        (uint64_t)size + (uint64_t)alignment - 1 >= SIZE_MAX / 2)
        minyar_stop("DMA allocation needs a bounded positive size and power-of-two alignment.");
    MinyarDmaAllocation *entry = minyar_dma_allocations;
    while (entry && !(entry->state == MINYAR_DMA_DEAD && !entry->hardware_pinned &&
                      !entry->owner && entry->incarnation < (uint64_t)LLONG_MAX))
        entry = entry->next;
    if (!entry) {
        uint64_t id = minyar_dma_next(minyar_dma_identity_id);
        entry = malloc(sizeof(*entry));
        if (!entry) out_of_memory();
        memset(entry, 0, sizeof(*entry));
        entry->id = minyar_dma_identity_id = id;
        entry->next = minyar_dma_allocations;
        minyar_dma_allocations = entry;
    }
    uint64_t incarnation = minyar_dma_next(entry->incarnation);
    MinyarRecord *handle = minyar_dma_handle(entry->id, incarnation, 1);
    MinyarBytes *owner = minyar_bytes_new(size + alignment - 1);
    /* Adopt the constructor's one owned reference; no RC frame/handle owns it. */
    entry->owner = owner;
    uintptr_t start = (uintptr_t)owner->bytes;
    if (start > UINTPTR_MAX - (uintptr_t)alignment + 1)
        minyar_stop("DMA aligned address overflowed.");
    entry->base = (unsigned char *)((start + (uintptr_t)alignment - 1) &
                                    ~((uintptr_t)alignment - 1));
    entry->incarnation = incarnation;
    entry->capability_epoch = 1;
    entry->capacity = entry->accessible = (size_t)size;
    entry->submitted = entry->completed = 0;
    entry->queue = NULL;
    entry->generation = 0;
    entry->state = MINYAR_DMA_CPU;
    return handle;
}

long long minyar_dma_load8(const MinyarRecord *cpu, long long offset) {
    MinyarDmaAllocation *entry = minyar_dma_allocation(cpu, 1u << MINYAR_DMA_CPU);
    minyar_dma_bounds(entry, offset, 1);
    return entry->base[(size_t)offset];
}

void minyar_dma_store8(const MinyarRecord *cpu, long long offset, long long value) {
    MinyarDmaAllocation *entry = minyar_dma_allocation(cpu, 1u << MINYAR_DMA_CPU);
    minyar_dma_bounds(entry, offset, 1);
    if (value < 0 || value > 255) minyar_stop("DMA store8 value does not fit in a byte.");
    entry->base[(size_t)offset] = (unsigned char)value;
}

MinyarBytes *minyar_dma_copyOut(const MinyarRecord *cpu, long long offset, long long count) {
    MinyarDmaAllocation *entry = minyar_dma_allocation(cpu, 1u << MINYAR_DMA_CPU);
    minyar_dma_bounds(entry, offset, count);
    MinyarBytes *copy = minyar_bytes_new(count);
    if (count) memcpy((void *)copy->bytes, entry->base + (size_t)offset, (size_t)count);
    return copy;
}

void minyar_dma_dispose(const MinyarRecord *cpu) {
    MinyarDmaAllocation *entry = minyar_dma_allocation(cpu, 1u << MINYAR_DMA_CPU);
    entry->capability_epoch = minyar_dma_transition_epoch(entry);
    entry->state = MINYAR_DMA_DEAD;
    entry->accessible = 0;
    if (!entry->hardware_pinned) {
        MinyarBytes *owner = entry->owner;
        entry->owner = NULL;
        entry->base = NULL;
        minyar_rc_release(owner);
    }
    /* Once exposed to hardware, backing stays pinned for VM lifetime. */
}

static MinyarDmaQueue *minyar_dma_new_queue(unsigned kind) {
    uint64_t id = minyar_dma_next(minyar_dma_identity_id);
    MinyarDmaQueue *queue = malloc(sizeof(*queue));
    if (!queue) out_of_memory();
    memset(queue, 0, sizeof(*queue));
    queue->id = minyar_dma_identity_id = id;
    queue->device = id;
    queue->incarnation = queue->epoch = 1;
    queue->kind = kind;
    queue->next = minyar_dma_queues;
    minyar_dma_queues = queue;
    return queue;
}

MinyarRecord *minyar_dma_model_modelQueue(void) {
    MinyarDmaQueue *queue = minyar_dma_new_queue(MINYAR_DMA_MODEL);
    return minyar_dma_handle(queue->id, queue->incarnation, queue->epoch);
}

static inline int minyar_dma_overlap(uintptr_t first, size_t first_size,
                                     uintptr_t second, size_t second_size) {
    return first < second + second_size && second < first + first_size;
}

/* Compiler-owned unsafe bridge only, never a public Integer-address factory.
 * Caller proves: actual retained Queue, exclusive fresh rings, coherent RAM,
 * identity translation, 16-bit PCI notify register, initialized/ready device.
 * Parent compiler restricts this intrinsic to kernel targets. No reset/close.
 * Ring/payload roots and metadata intentionally survive until VM termination. */
MinyarRecord *minyar_dma_unsafeVirtioQueue(MinyarRecord *owner, long long descriptor_cpu,
        long long available_cpu, long long used_cpu, long long notify_cpu,
        long long queue_size, long long queue_index) {
#if (defined(__x86_64__) || defined(__aarch64__)) && \
    defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    if (!owner || descriptor_cpu <= 0 || available_cpu <= 0 || used_cpu <= 0 || notify_cpu <= 0 ||
        queue_size <= 0 || queue_size > 32768 || (queue_size & (queue_size - 1)) ||
        queue_index < 0 || queue_index > 65535)
        minyar_stop("DMA virtio factory needs a fresh bounded split queue.");
    uintptr_t descriptors = (uintptr_t)descriptor_cpu, available = (uintptr_t)available_cpu;
    uintptr_t used = (uintptr_t)used_cpu, notify = (uintptr_t)notify_cpu;
    size_t descriptor_bytes = (size_t)queue_size * 16;
    size_t available_bytes = 6 + (size_t)queue_size * 2;
    size_t used_bytes = 6 + (size_t)queue_size * 8;
    if ((descriptors & 15) || (available & 1) || (used & 3) || (notify & 1) ||
        descriptors > UINTPTR_MAX - descriptor_bytes || available > UINTPTR_MAX - available_bytes ||
        used > UINTPTR_MAX - used_bytes || notify > UINTPTR_MAX - 2 ||
        minyar_dma_overlap(descriptors, descriptor_bytes, available, available_bytes) ||
        minyar_dma_overlap(descriptors, descriptor_bytes, used, used_bytes) ||
        minyar_dma_overlap(available, available_bytes, used, used_bytes) ||
        minyar_dma_overlap(notify, 2, descriptors, descriptor_bytes) ||
        minyar_dma_overlap(notify, 2, available, available_bytes) ||
        minyar_dma_overlap(notify, 2, used, used_bytes))
        minyar_stop("DMA virtio rings must be aligned, nonoverlapping and bounded.");
    uintptr_t ranges[3] = { descriptors, available, used };
    size_t sizes[3] = { descriptor_bytes, available_bytes, used_bytes };
    for (MinyarDmaQueue *prior = minyar_dma_queues; prior; prior = prior->next) {
        if (prior->kind != MINYAR_DMA_VIRTIO) continue;
        if (prior->ring_owner == owner)
            minyar_stop("DMA virtio queue storage is already registered.");
        uintptr_t prior_ranges[3] = { prior->descriptors, prior->available, prior->used };
        size_t prior_sizes[3] = { (size_t)prior->size * 16, 6 + (size_t)prior->size * 2,
                                  6 + (size_t)prior->size * 8 };
        for (size_t first = 0; first < 3; first++) {
            if (minyar_dma_overlap(notify, 2, prior_ranges[first], prior_sizes[first]))
                minyar_stop("DMA notification overlaps existing queue memory.");
            for (size_t second = 0; second < 3; second++) {
                if (minyar_dma_overlap(ranges[first], sizes[first], prior_ranges[second], prior_sizes[second]) ||
                    minyar_dma_overlap(ranges[first], sizes[first], prior->notify, 2))
                    minyar_stop("DMA virtio queue storage is already registered.");
            }
        }
    }
    if (*(volatile uint16_t *)(available + 2) != 0 || *(volatile uint16_t *)(used + 2) != 0)
        minyar_stop("DMA virtio factory refuses a non-fresh queue epoch.");
    MinyarDmaQueue *queue = minyar_dma_new_queue(MINYAR_DMA_VIRTIO);
    minyar_rc_retain(owner);
    queue->ring_owner = owner;
    queue->descriptors = descriptors; queue->available = available;
    queue->used = used; queue->notify = notify;
    queue->size = (uint16_t)queue_size; queue->index = (uint16_t)queue_index;
    return minyar_dma_handle(queue->id, queue->incarnation, queue->epoch);
#else
    (void)owner; (void)descriptor_cpu; (void)available_cpu; (void)used_cpu; (void)notify_cpu;
    (void)queue_size; (void)queue_index;
    minyar_stop("DMA virtio backend requires a coherent little-endian 64-bit kernel target.");
#endif
}

MinyarRecord *minyar_dma_submit(const MinyarRecord *queue_handle, const MinyarRecord *cpu,
                               long long length) {
    MinyarDmaQueue *queue = minyar_dma_queue(queue_handle);
    MinyarDmaAllocation *entry = minyar_dma_allocation(cpu, 1u << MINYAR_DMA_CPU);
    if (queue->failed || queue->active || (queue->kind == MINYAR_DMA_VIRTIO && queue->used_once))
        minyar_stop("DMA queue is busy, quarantined, or its one-shot slot was already used.");
    if (length <= 0 || (uint64_t)length > entry->capacity || (uint64_t)length > UINT32_MAX)
        minyar_stop("DMA submitted length exceeds its fresh allocation capacity.");
    if (queue->kind == MINYAR_DMA_VIRTIO &&
        (*(volatile uint16_t *)(queue->available + 2) != 0 ||
         *(volatile uint16_t *)(queue->used + 2) != 0))
        minyar_stop("DMA virtio slot is not in its fresh queue epoch.");
    uint64_t epoch = minyar_dma_transition_epoch(entry);
    uint64_t generation = minyar_dma_next(queue->generation);
    /* All allocations precede publication; a failed handle allocation cannot
     * leave published DMA with storage tied to an ordinary stack frame. */
    MinyarRecord *pending = minyar_dma_handle(entry->id, entry->incarnation, epoch);
    entry->capability_epoch = epoch;
    entry->state = MINYAR_DMA_PENDING;
    entry->accessible = 0;
    entry->submitted = (size_t)length;
    entry->completed = 0;
    entry->queue = queue;
    entry->generation = queue->generation = generation;
    queue->active = entry;
    queue->completion.sequence = 0;
    if (queue->kind == MINYAR_DMA_VIRTIO) {
        queue->used_once = 1;
        entry->hardware_pinned = 1;
        *(volatile uint64_t *)(queue->descriptors) = (uint64_t)(uintptr_t)entry->base;
        *(volatile uint32_t *)(queue->descriptors + 8) = (uint32_t)length;
        *(volatile uint16_t *)(queue->descriptors + 12) = 2; /* device WRITE, no chain */
        *(volatile uint16_t *)(queue->descriptors + 14) = 0;
        *(volatile uint16_t *)(queue->available) = 1; /* polling: NO_INTERRUPT */
        *(volatile uint16_t *)(queue->available + 4) = 0; /* sole fresh head */
        minyar_dma_fence();
        *(volatile uint16_t *)(queue->available + 2) = 1;
        minyar_dma_fence();
        *(volatile uint16_t *)(queue->notify) = queue->index;
    } else if (queue->kind == MINYAR_DMA_MODEL) {
        minyar_dma_fence();
    } else {
        minyar_dma_bad_completion(entry, "DMA queue backend is unknown.");
    }
    return pending;
}

_Bool minyar_dma_model_modelDeliver(const MinyarRecord *queue_handle, const MinyarBytes *data) {
    MinyarDmaQueue *queue = minyar_dma_queue(queue_handle);
    if (queue->kind != MINYAR_DMA_MODEL)
        minyar_stop("DMA model delivery cannot operate a hardware queue.");
    MinyarDmaAllocation *entry = queue->active;
    if (!data || data->byte_length < 0) minyar_stop("DMA model needs valid Bytes.");
    if (queue->failed || !entry || entry->state != MINYAR_DMA_PENDING ||
        queue->completion.sequence != 0 || (uint64_t)data->byte_length > entry->submitted)
        return 0;
    if (entry->queue != queue || entry->generation != queue->generation)
        minyar_dma_bad_completion(entry, "DMA model outstanding request identity is invalid.");
    if (data->byte_length) memcpy(entry->base, data->bytes, (size_t)data->byte_length);
    queue->completion.device = queue->device;
    queue->completion.queue = queue->id;
    queue->completion.slot = 0;
    queue->completion.generation = entry->generation;
    queue->completion.length = (uint64_t)data->byte_length;
    queue->completion.queue_epoch = queue->epoch;
    minyar_dma_fence();
    queue->completion.sequence = entry->generation;
    return 1;
}

void minyar_dma_model_modelCorrupt(const MinyarRecord *queue_handle, long long kind, long long value) {
    MinyarDmaQueue *queue = minyar_dma_queue(queue_handle);
    if (queue->kind != MINYAR_DMA_MODEL)
        minyar_stop("DMA model faults cannot operate a hardware queue.");
    if (!queue->active || queue->active->state != MINYAR_DMA_PENDING ||
        !queue->completion.sequence || queue->failed)
        minyar_stop("DMA model faults require delivery before completion acquisition.");
    uint64_t bits = (uint64_t)value;
    if (kind == 0) queue->completion.device = bits;
    else if (kind == 1) queue->completion.queue = bits;
    else if (kind == 2) queue->completion.slot = bits;
    else if (kind == 3) queue->completion.generation = bits;
    else if (kind == 4) queue->completion.length = bits;
    else if (kind == 5) queue->completion.queue_epoch = bits;
    else if (kind == 6) queue->completion.sequence = bits;
    else minyar_stop("DMA model fault kind is outside 0..6.");
    minyar_dma_fence();
}

_Bool minyar_dma_ready(const MinyarRecord *pending) {
    MinyarDmaAllocation *entry = minyar_dma_allocation(pending,
        (1u << MINYAR_DMA_PENDING) | (1u << MINYAR_DMA_COMPLETED));
    MinyarDmaQueue *queue = entry->queue;
    if (!queue || queue->failed || queue->active != entry || entry->generation != queue->generation)
        minyar_dma_bad_completion(entry, "DMA pending request has no matching outstanding queue slot.");
    if (entry->state == MINYAR_DMA_COMPLETED) return 1; /* private acquired witness */
    uint64_t length;
    if (queue->kind == MINYAR_DMA_MODEL) {
        uint64_t sequence = queue->completion.sequence;
        if (!sequence) return 0;
        minyar_dma_fence();
        if (sequence != entry->generation || queue->completion.device != queue->device ||
            queue->completion.queue != queue->id || queue->completion.slot != 0 ||
            queue->completion.generation != entry->generation ||
            queue->completion.queue_epoch != queue->epoch)
            minyar_dma_bad_completion(entry, "DMA completion device/queue/slot/generation witness is invalid.");
        length = queue->completion.length;
    } else if (queue->kind == MINYAR_DMA_VIRTIO) {
        uint16_t index = *(volatile uint16_t *)(queue->used + 2);
        uint16_t delta = (uint16_t)(index - queue->used_start);
        if (!delta) return 0;
        if (delta != 1)
            minyar_dma_bad_completion(entry, "DMA virtio used-index delta exceeds its one outstanding request.");
        minyar_dma_fence();
        if (*(volatile uint32_t *)(queue->used + 4) != 0)
            minyar_dma_bad_completion(entry, "DMA virtio completed a different descriptor head.");
        length = *(volatile uint32_t *)(queue->used + 8);
        /* Wire format has no generation cookie. This sole slot is never reused;
         * queue/slot/generation association relies on the fresh compliant device. */
    } else {
        minyar_dma_bad_completion(entry, "DMA completion backend is unknown.");
    }
    if (length > entry->submitted || length > entry->capacity)
        minyar_dma_bad_completion(entry, "DMA completion length exceeds the submitted capacity.");
    /* Coherent profile only. This orders payload access; it is not cache sync. */
    minyar_dma_fence();
    entry->completed = (size_t)length;
    entry->state = MINYAR_DMA_COMPLETED;
    return 1;
}

MinyarRecord *minyar_dma_reclaim(const MinyarRecord *pending, long long max_spins) {
    MinyarDmaAllocation *entry = minyar_dma_allocation(pending,
        (1u << MINYAR_DMA_PENDING) | (1u << MINYAR_DMA_COMPLETED));
    if (max_spins < 0 || max_spins > MINYAR_DMA_MAX_SPINS)
        minyar_dma_bad_completion(entry, "DMA reclaim retry bound is outside 0..1000000.");
    uint64_t epoch = minyar_dma_transition_epoch(entry);
    MinyarRecord *cpu = minyar_dma_handle(entry->id, entry->incarnation, epoch);
    long long retries = 0;
    while (!minyar_dma_ready(pending)) {
        if (retries >= max_spins) {
            minyar_rc_release(cpu);
            minyar_dma_bad_completion(entry, "DMA reclaim timed out; allocation and queue quarantined.");
        }
        minyar_dma_pause();
        retries++;
    }
    entry->capability_epoch = epoch;
    entry->state = MINYAR_DMA_CPU;
    entry->accessible = entry->completed;
    entry->queue->active = NULL;
    entry->queue = NULL;
    return cpu;
}

void minyar_dma_retire(const MinyarRecord *pending) {
    MinyarDmaAllocation *entry = minyar_dma_allocation(pending,
        (1u << MINYAR_DMA_PENDING) | (1u << MINYAR_DMA_COMPLETED));
    minyar_dma_quarantine(entry);
}

#endif
