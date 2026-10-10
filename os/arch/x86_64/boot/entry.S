/*
 * Entry point and interrupt stubs for 64-bit Minyar programs on bare metal.
 *
 * _start clears the program's .bss, switches to its own stack and calls the
 * Minyar `main`. Everything after that is Minyar. The interrupt stubs are the
 * small part the processor dictates: hardware interrupts (vectors 32-47) count
 * themselves in minyar_interrupt_counts and acknowledge the legacy interrupt
 * controllers, which the program reads with machine.interruptCount; processor
 * exceptions (vectors 0-31) report their state on the serial port and halt.
 */
    .section .text.entry, "ax"
    .code64
    .global _start
_start:
    cli
    movq %rdi, %r12
    leaq __bss_start(%rip), %rdi
    leaq __bss_end(%rip), %rcx
    subq %rdi, %rcx
    xorl %eax, %eax
    cld
    rep stosb
    leaq __stack_top(%rip), %rsp
    xorl %ebp, %ebp
    xorl %edi, %edi
    xorl %esi, %esi
    call main
    movl %eax, %edi
    call exit
1:  hlt
    jmp 1b

    .text
/* Hardware interrupts. */
.macro irq vector
irq_\vector:
    lock incq minyar_interrupt_counts + 8 * \vector(%rip)
    pushq %rax
    movb $0x20, %al
    .if \vector >= 40
    outb %al, $0xA0
    .endif
    outb %al, $0x20
    popq %rax
    iretq
.endm

/* Processor exceptions; some push an error code, the rest get a zero. */
.macro exception vector, has_error
exception_\vector:
    .if \has_error == 0
    pushq $0
    .endif
    pushq $\vector
    jmp exception_common
.endm

exception 0, 0
exception 1, 0
exception 2, 0
exception 3, 0
exception 4, 0
exception 5, 0
exception 6, 0
exception 7, 0
exception 8, 1
exception 9, 0
exception 10, 1
exception 11, 1
exception 12, 1
exception 13, 1
exception 14, 1
exception 15, 0
exception 16, 0
exception 17, 1
exception 18, 0
exception 19, 0
exception 20, 0
exception 21, 1
exception 22, 0
exception 23, 0
exception 24, 0
exception 25, 0
exception 26, 0
exception 27, 0
exception 28, 0
exception 29, 1
exception 30, 1
exception 31, 0
irq 32
irq 33
irq 34
irq 35
irq 36
irq 37
irq 38
irq 39
irq 40
irq 41
irq 42
irq 43
irq 44
irq 45
irq 46
irq 47

/* Vector 48: the wake-up IPI that tells sleeping processors new work is ready.
 * Acknowledge it in the local APIC; the woken processor checks for work. */
wake_48:
    pushq %rax
    movabsq $0xFEE000B0, %rax
    movl $0, (%rax)
    popq %rax
    iretq

/* Stack: vector, error code, rip, cs, rflags, rsp, ss. */
exception_common:
    leaq exception_text(%rip), %rsi
    call serial_text
    movq 0(%rsp), %rax
    call serial_hex
    leaq error_text(%rip), %rsi
    call serial_text
    movq 8(%rsp), %rax
    call serial_hex
    leaq rip_text(%rip), %rsi
    call serial_text
    movq 16(%rsp), %rax
    call serial_hex
    leaq rsp_text(%rip), %rsi
    call serial_text
    movq 40(%rsp), %rax
    call serial_hex
    leaq cr2_text(%rip), %rsi
    call serial_text
    movq %cr2, %rax
    call serial_hex
    movb $10, %al
    call serial_byte
    movb $3, %al
    outb %al, $0xF4
2:  cli
    hlt
    jmp 2b

serial_text:
    lodsb
    testb %al, %al
    jz 1f
    call serial_byte
    jmp serial_text
1:  ret

serial_hex:
    movq %rax, %rdx
    movl $16, %ecx
1:  rolq $4, %rdx
    movl %edx, %eax
    andl $15, %eax
    leaq hex_digits(%rip), %rsi
    movb (%rsi,%rax), %al
    call serial_byte
    decl %ecx
    jnz 1b
    ret

serial_byte:
    pushq %rdx
    pushq %rax
    movw $0x3FD, %dx
1:  inb %dx, %al
    testb $0x20, %al
    jz 1b
    popq %rax
    movw $0x3F8, %dx
    outb %al, %dx
    popq %rdx
    ret

    .section .rodata
exception_text: .asciz "\nMinyar OS processor exception "
error_text:     .asciz " error "
rip_text:       .asciz " rip "
rsp_text:       .asciz " rsp "
cr2_text:       .asciz " cr2 "
hex_digits:     .ascii "0123456789abcdef"

    .p2align 3
    .global minyar_interrupt_handlers
minyar_interrupt_handlers:
    .irp vector, 0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31
    .quad exception_\vector
    .endr
    .irp vector, 32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47
    .quad irq_\vector
    .endr
    .quad wake_48

/* Addresses for machine.symbol: trampoline, its end, and clock storage. */
    .global minyar_machine_symbols
minyar_machine_symbols:
    .quad minyar_ap_trampoline
    .quad minyar_ap_trampoline_end
    .quad minyar_clock

    .bss
    .p2align 3
    .global minyar_interrupt_counts
minyar_interrupt_counts:
    .zero 8 * 48
minyar_clock:
    .zero 8 * 3

/*
 * The trampoline that starts the other processors. The kernel copies it to
 * 0x8000 and sends each processor a start-up IPI with vector 8; the processor
 * begins here in 16-bit real mode, switches to 64-bit mode with the boot
 * page tables, claims a number, takes its stack and calls the parallel
 * function `worker(number, shared)` written in Minyar.
 *
 * Data written by the kernel before the start-up IPI (offsets from 0x8000):
 *   0x200 counter   0x208 stacks   0x210 stack size   0x218 worker   0x220 shared
 */
    .section .ap_trampoline, "a"
    .p2align 12
    .global minyar_ap_trampoline
minyar_ap_trampoline:
    .code16
    cli
    xorw %ax, %ax
    movw %ax, %ds
    lgdtl (ap_gdt_descriptor - minyar_ap_trampoline + 0x8000)
    movl $0x620, %eax
    movl %eax, %cr4
    movl $0x1000, %eax
    movl %eax, %cr3
    movl $0xC0000080, %ecx
    rdmsr
    orl $0x100, %eax
    wrmsr
    movl %cr0, %eax
    andl $0xFFFFFFFB, %eax
    orl $0x80000003, %eax
    movl %eax, %cr0
    ljmpl $0x08, $(ap_long - minyar_ap_trampoline + 0x8000)
    .code64
ap_long:
    movw $0x10, %ax
    movw %ax, %ds
    movw %ax, %es
    movw %ax, %ss
    movw %ax, %fs
    movw %ax, %gs
    movl $1, %edi
    lock xaddl %edi, 0x8200
    incl %edi
    movq 0x8208, %rsp
    movq 0x8210, %rax
    imulq %rdi, %rax
    addq %rax, %rsp
    movq 0x8220, %rsi
    movq 0x8218, %rax
    callq *%rax
1:  cli
    hlt
    jmp 1b

    .p2align 3
ap_gdt:
    .quad 0
    .quad 0x00AF9A000000FFFF
    .quad 0x00CF92000000FFFF
ap_gdt_descriptor:
    .word 23
    .long ap_gdt - minyar_ap_trampoline + 0x8000
    .org 0x200
ap_data:
    .zero 0x40
    .global minyar_ap_trampoline_end
minyar_ap_trampoline_end:
