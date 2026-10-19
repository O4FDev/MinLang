#ifndef MINYAR_TRACE_SYMBOLS_H
#define MINYAR_TRACE_SYMBOLS_H
/* Names, rather than function pointers, let LLVM discard unused functions.
 * Resolve surviving addresses only on failure. Stripped images use the entry
 * location; no symbol lookup runs on the successful path. */
#include <stdlib.h>
static int minyar_trace_name_equal(const char *left, const char *right) {
    while (*left && *left == *right) { left++; right++; }
    return *left == *right;
}
#if defined(__APPLE__) && (!defined(__STDC_HOSTED__) || __STDC_HOSTED__)
#include <mach-o/loader.h>
#include <mach-o/nlist.h>
extern const struct mach_header_64 _mh_execute_header;
static const char *minyar_trace_symbol(uintptr_t address, char **owned) {
    *owned = NULL;
    const struct symtab_command *symbols = NULL;
    uintptr_t slide = 0, link = 0, link_end = 0;
    const struct load_command *command = (const void *)(&_mh_execute_header + 1);
    for (uint32_t index = 0; index < _mh_execute_header.ncmds; index++) {
        if (command->cmd == LC_SYMTAB) symbols = (const void *)command;
        if (command->cmd == LC_SEGMENT_64) {
            const struct segment_command_64 *segment = (const void *)command;
            if (segment->fileoff == 0 && segment->filesize)
                slide = (uintptr_t)&_mh_execute_header - (uintptr_t)segment->vmaddr;
        }
        command = (const void *)((const unsigned char *)command + command->cmdsize);
    }
    command = (const void *)(&_mh_execute_header + 1);
    for (uint32_t index = 0; index < _mh_execute_header.ncmds; index++) {
        if (command->cmd == LC_SEGMENT_64) {
            const struct segment_command_64 *segment = (const void *)command;
            const char *name = segment->segname;
            if (name[0]=='_' && name[1]=='_' && name[2]=='L' && name[3]=='I' && name[4]=='N' && name[5]=='K' && name[6]=='E' && name[7]=='D' && name[8]=='I' && name[9]=='T' && !name[10]) {
                link = slide + (uintptr_t)segment->vmaddr - (uintptr_t)segment->fileoff;
                link_end = (uintptr_t)segment->fileoff + (uintptr_t)segment->filesize;
            }
        }
        command = (const void *)((const unsigned char *)command + command->cmdsize);
    }
    if (!symbols || !link || symbols->symoff > link_end ||
        (uint64_t)symbols->nsyms * sizeof(struct nlist_64) > link_end - symbols->symoff ||
        symbols->stroff > link_end || symbols->strsize > link_end - symbols->stroff) return NULL;
    const struct nlist_64 *rows = (const void *)(link + symbols->symoff);
    const char *strings = (const void *)(link + symbols->stroff);
    for (uint32_t index = 0; index < symbols->nsyms; index++) {
        if ((rows[index].n_type & N_STAB) || (rows[index].n_type & N_TYPE) != N_SECT ||
            rows[index].n_value + slide != address || rows[index].n_un.n_strx >= symbols->strsize) continue;
        const char *name = strings + rows[index].n_un.n_strx;
        size_t remaining = symbols->strsize - rows[index].n_un.n_strx;
        size_t length = 0; while (length < remaining && name[length]) length++;
        if (length == remaining) return NULL;
        return *name == '_' ? name + 1 : name;
    }
    return NULL;
}
#elif defined(__linux__) && (!defined(__STDC_HOSTED__) || __STDC_HOSTED__)
#include <elf.h>
extern const unsigned char __ehdr_start[];
static const char *minyar_trace_symbol(uintptr_t address, char **owned) {
    *owned = NULL;
    FILE *file = fopen("/proc/self/exe", "rb");
    if (!file) return NULL;
    Elf64_Ehdr header;
    if (fread(&header, sizeof header, 1, file) != 1 || header.e_ident[EI_CLASS] != ELFCLASS64 ||
        header.e_shentsize != sizeof(Elf64_Shdr) || header.e_phentsize != sizeof(Elf64_Phdr)) { fclose(file); return NULL; }
    uintptr_t slide = 0;
    for (unsigned index = 0; index < header.e_phnum; index++) {
        Elf64_Phdr segment;
        if (fseek(file, (long)(header.e_phoff + index * sizeof segment), SEEK_SET) || fread(&segment, sizeof segment, 1, file) != 1) break;
        if (segment.p_type == PT_LOAD && !segment.p_offset) { slide = (uintptr_t)__ehdr_start - segment.p_vaddr; break; }
    }
    for (unsigned section = 0; section < header.e_shnum; section++) {
        Elf64_Shdr symbols, strings;
        if (fseek(file, (long)(header.e_shoff + section * sizeof symbols), SEEK_SET) || fread(&symbols, sizeof symbols, 1, file) != 1) break;
        if (symbols.sh_type != SHT_SYMTAB || symbols.sh_entsize != sizeof(Elf64_Sym) || symbols.sh_link >= header.e_shnum) continue;
        if (fseek(file, (long)(header.e_shoff + symbols.sh_link * sizeof strings), SEEK_SET) || fread(&strings, sizeof strings, 1, file) != 1) break;
        for (uint64_t index = 0; index < symbols.sh_size / sizeof(Elf64_Sym); index++) {
            Elf64_Sym symbol;
            if (fseek(file, (long)(symbols.sh_offset + index * sizeof symbol), SEEK_SET) || fread(&symbol, sizeof symbol, 1, file) != 1) break;
            if (ELF64_ST_TYPE(symbol.st_info) != STT_FUNC || symbol.st_value + slide != address || symbol.st_name >= strings.sh_size) continue;
            size_t capacity = (size_t)(strings.sh_size - symbol.st_name);
            char *name = malloc(capacity);
            if (!name) break;
            if (!fseek(file, (long)(strings.sh_offset + symbol.st_name), SEEK_SET) && fread(name, 1, capacity, file) == capacity) {
                for (size_t length = 0; length < capacity; length++) if (!name[length]) { *owned = name; fclose(file); return name; }
            }
            free(name); break;
        }
    }
    fclose(file); return NULL;
}
#else
static const char *minyar_trace_symbol(uintptr_t address, char **owned) { (void)address; *owned = NULL; return NULL; }
#endif
#endif
