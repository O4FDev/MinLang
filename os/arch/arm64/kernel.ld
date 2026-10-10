/* The arm64 kernel: an ELF executable QEMU loads at 0x4008_0000, just above
 * the device tree it places at the start of RAM (0x4000_0000). Its heap runs
 * from the end of the image to 64 MiB below the end of 1 GiB of RAM. */
OUTPUT_FORMAT("elf64-littleaarch64")
ENTRY(_start)
PHDRS { image PT_LOAD; }
SECTIONS
{
    . = 0x40080000;
    .text : { *(.text.entry) *(.text .text.*) } :image
    .rodata : { *(.rodata .rodata.*) } :image
    .data : { *(.data .data.*) } :image
    . = ALIGN(4096);
    __bss_start = .;
    .bss (NOLOAD) : {
        *(.bss .bss.*) *(COMMON)
        . = ALIGN(16);
        . += 0x400000;
        __stack_top = .;
    } :image
    __bss_end = .;
    __heap_start = ALIGN(0x200000);
    __heap_end = 0x7C000000;
    /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
