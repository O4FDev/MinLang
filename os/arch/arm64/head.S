/*
 * Entry point and exception vectors for 64-bit Minyar programs on QEMU's Arm
 * `virt` board, the arm64 counterpart of os/arch/x86_64/boot/entry.S.
 *
 * QEMU loads kernel.elf and starts the boot processor at _start in EL1 with
 * the MMU off. _start clears .bss, builds identity page tables, turns on the
 * MMU and caches (Minyar code makes unaligned accesses, which fault while all
 * memory is Device memory), enables the FP/SIMD unit and the GICv3 CPU
 * interface, installs the vectors and calls the Minyar `main`. The other
 * processors start at minyar_secondary_entry through PSCI CPU_ON.
 *
 * As on x86, interrupts count themselves in minyar_interrupt_counts, which
 * the program reads with machine.interruptCount; the virtual timer (GIC
 * interrupt 27) re-arms itself every minyar_timer_period counter ticks, so it
 * is a steady clock tick like the PC's PIT. Exceptions report their state on
 * the serial port and stop.
 */

/* Memory attributes: 0 Device-nGnRE, 1 Normal write-back, 2 Normal non-cacheable. */
#define MAIR_VALUE 0x44FF04
/* 39-bit addresses from TTBR0 with 4 KiB pages, cacheable walks, no TTBR1, 40-bit physical. */
#define TCR_VALUE 0x200803519
#define BLOCK_DEVICE 0x0060000000000401
#define BLOCK_NORMAL 0x0000000000000705
#define BLOCK_UNCACHED 0x0060000000000609
#define TIMER_INTERRUPT 27
#define COUNTED_INTERRUPTS 256

    .section .text.entry, "ax"
    .global _start
_start:
    msr daifset, #0xf
    adrp x0, __bss_start
    add x0, x0, :lo12:__bss_start
    adrp x1, __bss_end
    add x1, x1, :lo12:__bss_end
1:  cmp x0, x1
    b.hs 2f
    stp xzr, xzr, [x0], #16
    b 1b
2:  bl build_tables
    bl enable_processor
    adrp x0, __stack_top
    add x0, x0, :lo12:__stack_top
    mov sp, x0
    mov x29, #0
    mov x0, #0
    mov x1, #0
    bl main
    bl exit
3:  wfi
    b 3b

/*
 * Other processors, started with PSCI CPU_ON(target, minyar_secondary_entry,
 * context). The context holds the stack top, the parallel function to call
 * and its two Integer arguments.
 */
    .global minyar_secondary_entry
minyar_secondary_entry:
    msr daifset, #0xf
    mov x19, x0
    bl enable_processor
    ldr x0, [x19]
    mov sp, x0
    mov x29, #0
    ldr x2, [x19, #8]
    ldr x0, [x19, #16]
    ldr x1, [x19, #24]
    blr x2
4:  wfi
    b 4b

/*
 * Identity tables, 1 GiB blocks: the first GiB (devices) through 2 MiB blocks,
 * RAM from 1 GiB to 4 GiB, and the 1 GiB holding the PCIe configuration space
 * (ECAM) at 0x40_1000_0000. Devices are Device memory except 0x1000_0000 to
 * 0x17FF_FFFF, where PCI prefetchable BARs such as framebuffers go, which is
 * non-cacheable Normal memory so pixel code may access it unaligned.
 */
build_tables:
    adrp x0, page_level1
    add x0, x0, :lo12:page_level1
    adrp x1, page_level2
    add x1, x1, :lo12:page_level2
    orr x2, x1, #3
    str x2, [x0]
    ldr x3, =BLOCK_NORMAL
    mov x4, #1
5:  lsl x5, x4, #30
    orr x5, x5, x3
    str x5, [x0, x4, lsl #3]
    add x4, x4, #1
    cmp x4, #4
    b.lo 5b
    ldr x5, =(0x4000000000 | BLOCK_DEVICE)
    str x5, [x0, #(256 * 8)]
    mov x4, #0
6:  lsl x5, x4, #21
    ldr x6, =BLOCK_DEVICE
    cmp x4, #128
    b.lo 7f
    cmp x4, #192
    b.hs 7f
    ldr x6, =BLOCK_UNCACHED
7:  orr x5, x5, x6
    str x5, [x1, x4, lsl #3]
    add x4, x4, #1
    cmp x4, #512
    b.lo 6b
    dsb ish
    ret

/* Per processor: MMU and caches, FP/SIMD, the GIC CPU interface and vectors. */
enable_processor:
    ldr x0, =MAIR_VALUE
    msr mair_el1, x0
    ldr x0, =TCR_VALUE
    msr tcr_el1, x0
    adrp x0, page_level1
    add x0, x0, :lo12:page_level1
    msr ttbr0_el1, x0
    isb
    tlbi vmalle1
    dsb nsh
    isb
    mrs x0, sctlr_el1
    orr x0, x0, #1
    orr x0, x0, #(1 << 2)
    orr x0, x0, #(1 << 12)
    bic x0, x0, #2
    msr sctlr_el1, x0
    isb
    mov x0, #(3 << 20)
    msr cpacr_el1, x0
    isb
    mrs x0, icc_sre_el1
    orr x0, x0, #1
    msr icc_sre_el1, x0
    isb
    mov x0, #0xff
    msr icc_pmr_el1, x0
    mov x0, #1
    msr icc_igrpen1_el1, x0
    adrp x0, vectors
    add x0, x0, :lo12:vectors
    msr vbar_el1, x0
    isb
    ret

/*
 * Helpers os/arch/arm64/arch.min calls through machine.callEntry, for what
 * needs system registers: arm the virtual timer to interrupt every x0 counter
 * ticks, and wake every other processor with software interrupt 0.
 */
minyar_start_timer:
    adrp x1, minyar_timer_period
    str x0, [x1, :lo12:minyar_timer_period]
    mrs x1, cntvct_el0
    add x1, x1, x0
    msr cntv_cval_el0, x1
    mov x1, #1
    msr cntv_ctl_el0, x1
    isb
    ret

minyar_wake_others:
    mov x0, #(1 << 40)
    msr icc_sgi1r_el1, x0
    isb
    ret

/* ----- Exception vectors ----- */

.macro entry handler, kind
    .balign 0x80
    mov x1, #\kind
    b \handler
.endm

    .text
    .balign 0x800
vectors:
    entry exception, 0
    entry exception, 1
    entry exception, 2
    entry exception, 3
    entry exception, 4
    .balign 0x80
    b interrupt
    entry exception, 6
    entry exception, 7
    entry exception, 8
    entry exception, 9
    entry exception, 10
    entry exception, 11
    entry exception, 12
    entry exception, 13
    entry exception, 14
    entry exception, 15

/* Report the exception and stop: ESR, ELR and FAR say what, where and which address. */
exception:
    mov x0, x1
    mrs x1, esr_el1
    mrs x2, elr_el1
    mrs x3, far_el1
    bl minyar_arm_exception
8:  wfi
    b 8b

/* A hardware interrupt: every register it uses is restored before eret. */
interrupt:
    sub sp, sp, #48
    stp x0, x1, [sp]
    stp x2, x3, [sp, #16]
    str x4, [sp, #32]
    mrs x0, icc_iar1_el1
    and x1, x0, #0xffffff
    cmp x1, #1020
    b.hs 12f
    cmp x1, #COUNTED_INTERRUPTS
    b.hs 11f
    adrp x2, minyar_interrupt_counts
    add x2, x2, :lo12:minyar_interrupt_counts
    add x2, x2, x1, lsl #3
9:  ldxr x3, [x2]
    add x3, x3, #1
    stxr w4, x3, [x2]
    cbnz w4, 9b
    cmp x1, #TIMER_INTERRUPT
    b.ne 11f
    adrp x2, minyar_timer_period
    ldr x3, [x2, :lo12:minyar_timer_period]
    cbz x3, 10f
    mrs x2, cntv_cval_el0
    add x2, x2, x3
    mrs x4, cntvct_el0
    cmp x2, x4
    b.hi 13f
    add x2, x4, x3
13: msr cntv_cval_el0, x2
    b 11f
10: msr cntv_ctl_el0, xzr
11: msr icc_eoir1_el1, x0
12: ldp x0, x1, [sp]
    ldp x2, x3, [sp, #16]
    ldr x4, [sp, #32]
    add sp, sp, #48
    eret

/* ----- Data ----- */

/* Addresses for machine.symbol: secondary entry, timer period, clock storage,
 * entropy pool, and the two helpers above. */
    .data
    .p2align 3
    .global minyar_machine_symbols
minyar_machine_symbols:
    .quad minyar_secondary_entry
    .quad minyar_timer_period
    .quad minyar_clock
    .quad minyar_entropy
    .quad minyar_start_timer
    .quad minyar_wake_others

    .bss
    .p2align 12
page_level1:
    .zero 4096
page_level2:
    .zero 4096
    .global minyar_interrupt_counts
minyar_interrupt_counts:
    .zero 8 * COUNTED_INTERRUPTS
minyar_clock:
    .zero 8 * 3
minyar_timer_period:
    .zero 8
/* Bytes from an entropy device, used from the end: a count, then the bytes. */
    .global minyar_entropy
minyar_entropy:
    .zero 8 + 4096
