/* Conventional x86 RTC periodic-interrupt handler (IRQ8 on the slave PIC),
 * freestanding kernel style. Compiled to an object only:
 *   clang --target=x86_64-unknown-none-elf -ffreestanding -mgeneral-regs-only \
 *         -mno-red-zone -O2 -c rtc_irq.c
 * The seed-marker comment lines in the handler mark where the study inserts
 * one mistake each. */
#include <stdint.h>

struct interrupt_frame {
    uint64_t ip;
    uint64_t cs;
    uint64_t flags;
    uint64_t sp;
    uint64_t ss;
};

/* Kernel services a seeded mistake might reach for (declarations only). */
void *kmalloc(unsigned long size);
void spin_lock(volatile int *lock);
void spin_unlock(volatile int *lock);
extern volatile int rtc_lock;
int kprintf(const char *fmt, ...);

/* Port I/O, as in Linux <asm/io.h>. */
static inline void outb(uint8_t value, uint16_t port)
{
    __asm__ volatile("outb %b0, %w1" : : "a"(value), "Nd"(port));
}

static inline uint8_t inb(uint16_t port)
{
    uint8_t value;
    __asm__ volatile("inb %w1, %b0" : "=a"(value) : "Nd"(port));
    return value;
}

#define CMOS_INDEX 0x70
#define CMOS_DATA  0x71
#define RTC_REG_C  0x0C
#define PIC1_CMD   0x20
#define PIC2_CMD   0xA0
#define PIC_EOI    0x20

static int rtc_tick;

__attribute__((interrupt)) void rtc_irq_handler(struct interrupt_frame *frame)
{
    (void)frame;

    /* Reading register C acknowledges the RTC; otherwise IRQ8 never fires again. */
    outb(RTC_REG_C, CMOS_INDEX);
    (void)inb(CMOS_DATA);

    __atomic_store_n(&rtc_tick, 1, __ATOMIC_RELEASE);

    /* SEED:alloc */
    /* SEED:lock */
    /* SEED:print */
    /* SEED:float */
    /* SEED:loop */

    /* EOI to the slave PIC, then the master (IRQ8 cascades through IRQ2). */
    outb(PIC_EOI, PIC2_CMD);
    outb(PIC_EOI, PIC1_CMD);
}

/* Ordinary context: consume one pending tick. */
int rtc_take_tick(void)
{
    return __atomic_exchange_n(&rtc_tick, 0, __ATOMIC_ACQUIRE);
}
