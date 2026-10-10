/* The kernel: an ELF executable the stage-two loader places at 1 MiB. Its
 * heap runs from the end of the image to 960 MiB (QEMU is given 1 GiB). */
OUTPUT_FORMAT("elf64-x86-64")
ENTRY(_start)
PHDRS { image PT_LOAD; }
SECTIONS
{
    . = 0x100000;
    .text : { *(.text.entry) *(.text .text.*) } :image
    .rodata : { *(.rodata .rodata.*) . = ALIGN(4096); *(.ap_trampoline) } :image
    .data : { *(.data .data.*) } :image
    . = ALIGN(16);
    __bss_start = .;
    .bss (NOLOAD) : {
        *(.bss .bss.*) *(COMMON)
        . = ALIGN(16);
        . += 0x400000;
        __stack_top = .;
    } :image
    __bss_end = .;
    __heap_start = ALIGN(0x200000);
    __heap_end = 0x3C000000;
    /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
