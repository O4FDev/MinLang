/*
 * Stage one of the Minyar OS boot: the 512-byte master boot record.
 *
 * The BIOS loads this sector at 0x7C00 in 16-bit real mode. It does only what
 * must happen before 64-bit code can run, then hands over to the stage-two
 * loader, which is a Minyar program:
 *
 *   1. record the BIOS memory map (E820) in the boot information block,
 *   2. read the stage-two loader from disk to 0x10000 using BIOS LBA reads,
 *   3. identity-map the first 4 GiB with 2 MiB pages,
 *   4. enable SSE, PAE and long mode, and jump to the loader's _start.
 *
 * Boot information block (0x0800):
 *   0x0800  u64  magic "MINYARBT"
 *   0x0808  u64  number of E820 entries
 *   0x0810  24-byte E820 entries (base, length, type, attributes), at most 32
 *   0x0C00  fields written later by the stage-two loader
 *
 * The image builder patches loader_lba and loader_sectors at offset 0x1F0.
 * There is no partition table; the disk belongs to Minyar OS.
 */
    .code16
    .section .text
    .global _start
_start:
    cli
    xorw %ax, %ax
    movw %ax, %ds
    movw %ax, %es
    movw %ax, %ss
    movw $0x7C00, %sp
    ljmp $0, $normalized
normalized:
    sti
    movb %dl, boot_drive

    movw $banner, %si
    call print

    /* Fast A20 gate. */
    inb $0x92, %al
    orb $2, %al
    andb $0xFE, %al
    outb %al, $0x92

    /* E820 memory map. */
    movl $0x594E494D, 0x0800   /* "MINY" */
    movl $0x54425241, 0x0804   /* "ARBT" */
    movw $0x0810, %di
    xorl %ebx, %ebx
    xorw %bp, %bp
memory_map:
    movl $0xE820, %eax
    movl $24, %ecx
    movl $0x534D4150, %edx
    movl $1, 20(%di)
    int $0x15
    jc memory_map_done
    cmpl $0x534D4150, %eax
    jne memory_map_done
    addw $24, %di
    incw %bp
    cmpw $32, %bp
    je memory_map_done
    testl %ebx, %ebx
    jnz memory_map
memory_map_done:
    movzwl %bp, %eax
    movl %eax, 0x0808

    /* Read the loader in chunks of up to 64 sectors (32 KiB). */
    movl loader_lba, %eax
    movl %eax, packet_lba
    movw loader_sectors, %cx
    movw $0x1000, packet_segment
read_chunk:
    testw %cx, %cx
    jz read_done
    movw %cx, %ax
    cmpw $64, %ax
    jbe 1f
    movw $64, %ax
1:  movw %ax, packet_count
    pushw %cx
    pushw %ax
    movw $packet, %si
    movb $0x42, %ah
    movb boot_drive, %dl
    int $0x13
    jc disk_error
    popw %ax
    popw %cx
    subw %ax, %cx
    movzwl %ax, %eax
    addl %eax, packet_lba
    shlw $5, %ax
    addw %ax, packet_segment
    jmp read_chunk
read_done:

    /* Page tables: PML4 at 0x1000, PDPT at 0x2000, four directories from 0x3000. */
    cld
    movw $0x1000, %di
    xorl %eax, %eax
    movw $0x3000, %cx
    rep stosw
    movl $0x2003, 0x1000
    movl $0x3003, 0x2000
    movl $0x4003, 0x2008
    movl $0x5003, 0x2010
    movl $0x6003, 0x2018
    movw $0x3000, %di
    movl $0x83, %eax
    movw $2048, %cx
map_page:
    movl %eax, (%di)
    addl $0x200000, %eax
    addw $8, %di
    loop map_page

    /* Mask the legacy interrupt controllers; the kernel programs them itself. */
    cli
    movb $0xFF, %al
    outb %al, $0xA1
    outb %al, $0x21

    lgdtl gdt_descriptor
    movl $0x620, %eax          /* PAE | OSFXSR | OSXMMEXCPT */
    movl %eax, %cr4
    movl $0x1000, %eax
    movl %eax, %cr3
    movl $0xC0000080, %ecx     /* EFER.LME */
    rdmsr
    orl $0x100, %eax
    wrmsr
    movl %cr0, %eax
    andl $0xFFFFFFFB, %eax     /* clear EM */
    orl $0x80000003, %eax      /* PG | MP | PE */
    movl %eax, %cr0
    ljmpl $0x08, $long_mode

disk_error:
    movw $failure, %si
    call print
halt:
    hlt
    jmp halt

print:
    lodsb
    testb %al, %al
    jz 1f
    movb $0x0E, %ah
    movw $0x0007, %bx
    int $0x10
    jmp print
1:  ret

    .code64
long_mode:
    movw $0x10, %ax
    movw %ax, %ds
    movw %ax, %es
    movw %ax, %ss
    movw %ax, %fs
    movw %ax, %gs
    movq $0x7C00, %rsp
    movl $0x0800, %edi
    movl $0x10000, %eax
    jmp *%rax

banner:  .asciz "Minyar boot\r\n"
failure: .asciz "disk error"
boot_drive: .byte 0

    .p2align 3
gdt:                           /* the unused null descriptor holds the GDT pointer */
gdt_descriptor:
    .word 23
    .long gdt
    .word 0
    .quad 0x00AF9A000000FFFF   /* 64-bit code */
    .quad 0x00CF92000000FFFF   /* data */

    .p2align 2
packet:
    .byte 16, 0
packet_count:   .word 0
packet_offset:  .word 0
packet_segment: .word 0
packet_lba:     .long 0, 0

    .org 0x1F0
loader_lba:     .long 1
loader_sectors: .word 0

    .org 0x1FE
    .byte 0x55, 0xAA
