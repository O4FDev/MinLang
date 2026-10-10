/* The stage-two loader: a flat image the MBR reads to 0x10000. Its zeroed
 * data, stack and heap sit well above the region where it places the kernel. */
OUTPUT_FORMAT("elf64-x86-64")
ENTRY(_start)
SECTIONS
{
    . = 0x10000;
    .text : { *(.text.entry) *(.text .text.*) }
    .rodata : { *(.rodata .rodata.*) . = ALIGN(16); *(.ap_trampoline) }
    .data : { *(.data .data.*) }
    /* The image must fit in conventional memory, below the BIOS data that
     * ends it at 0x9FC00; from 0xA0000 up is video memory. */
    ASSERT(. <= 0x9F000, "the loader image has outgrown conventional memory")
    /* Zeroed data and the stack take no room in the image, so they go above
     * the kernel's place (from 1 MiB) and below the heap. */
    . = 0x03000000;
    __bss_start = .;
    .bss (NOLOAD) : {
        *(.bss .bss.*) *(COMMON)
        . = ALIGN(16);
        . += 0x20000;
        __stack_top = .;
    }
    __bss_end = .;
    __heap_start = 0x04000000;
    __heap_end = 0x0C000000;
    /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
