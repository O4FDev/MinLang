#ifndef MINYAR_TRACES_DARWIN_H
#define MINYAR_TRACES_DARWIN_H
/* Cold reader for the compact-unwind and DWARF CFI already in a Mach-O
 * executable. It adds no loader imports and never changes a caller's frame. */
#include <mach-o/loader.h>
#include <mach-o/compact_unwind_encoding.h>
#include <string.h>
extern const struct mach_header_64 _mh_execute_header;
typedef struct { uintptr_t base; const unsigned char *compact, *eh; size_t compact_size, eh_size; } MinyarTraceImage;
typedef struct { const unsigned char *p, *end; int ok; } MinyarCFIReader;
typedef struct { unsigned cfa_register; int64_t cfa_offset, fp_offset, lr_offset; unsigned fp_kind, lr_kind; } MinyarCFIRules;
typedef struct { uintptr_t pc, sp, fp; } MinyarTraceRegisters;

static int minyar_trace_section_name(const char *name, const char *wanted) {
    for (unsigned index = 0; index < 16; index++) {
        if (name[index] != wanted[index]) return 0;
        if (!wanted[index]) return 1;
    }
    return 1;
}
static void minyar_trace_image(MinyarTraceImage *image) {
    image->base = (uintptr_t)&_mh_execute_header; image->compact = image->eh = NULL;
    image->compact_size = image->eh_size = 0;
    const struct load_command *command = (const void *)(&_mh_execute_header + 1);
    for (uint32_t index = 0; index < _mh_execute_header.ncmds; index++) {
        if (command->cmd == LC_SEGMENT_64) {
            const struct segment_command_64 *segment = (const void *)command;
            if (minyar_trace_section_name(segment->segname, "__TEXT")) {
                uintptr_t slide = image->base - (uintptr_t)segment->vmaddr;
                const struct section_64 *sections = (const void *)(segment + 1);
                for (uint32_t section = 0; section < segment->nsects; section++) {
                    const unsigned char *bytes = (const void *)((uintptr_t)sections[section].addr + slide);
                    if (minyar_trace_section_name(sections[section].sectname, "__unwind_info")) { image->compact = bytes; image->compact_size = (size_t)sections[section].size; }
                    if (minyar_trace_section_name(sections[section].sectname, "__eh_frame")) { image->eh = bytes; image->eh_size = (size_t)sections[section].size; }
                }
            }
        }
        command = (const void *)((const unsigned char *)command + command->cmdsize);
    }
}
static MINYAR_COLD uintptr_t minyar_trace_region(const MinyarTraceImage *image, uintptr_t pc, uint32_t *encoding) {
    if (!image->compact || pc < image->base || pc - image->base > UINT32_MAX) return 0;
    const struct unwind_info_section_header *header = (const void *)image->compact;
    if (header->version != UNWIND_SECTION_VERSION || header->indexCount < 2) return 0;
    uint32_t offset = (uint32_t)(pc - image->base);
    const struct unwind_info_section_header_index_entry *indices = (const void *)(image->compact + header->indexSectionOffset);
    if (offset < indices[0].functionOffset || offset >= indices[header->indexCount - 1].functionOffset) return 0;
    uint32_t low = 0, high = header->indexCount - 1;
    while (low + 1 < high) { uint32_t middle = low + (high - low) / 2; if (indices[middle].functionOffset <= offset) low = middle; else high = middle; }
    const unsigned char *page = image->compact + indices[low].secondLevelPagesSectionOffset;
    uint32_t kind = *(const uint32_t *)(const void *)page;
    if (kind == UNWIND_SECOND_LEVEL_REGULAR) {
        const struct unwind_info_regular_second_level_page_header *second = (const void *)page;
        const struct unwind_info_regular_second_level_entry *entries = (const void *)(page + second->entryPageOffset);
        uint32_t first = 0, after = second->entryCount;
        if (!after || offset < entries[0].functionOffset) return 0;
        while (first + 1 < after) { uint32_t middle = first + (after - first) / 2; if (entries[middle].functionOffset <= offset) first = middle; else after = middle; }
        *encoding = entries[first].encoding;
        return image->base + entries[first].functionOffset;
    }
    if (kind == UNWIND_SECOND_LEVEL_COMPRESSED) {
        const struct unwind_info_compressed_second_level_page_header *second = (const void *)page;
        const uint32_t *entries = (const void *)(page + second->entryPageOffset);
        uint32_t first = 0, after = second->entryCount, relative = offset - indices[low].functionOffset;
        if (!after || relative < UNWIND_INFO_COMPRESSED_ENTRY_FUNC_OFFSET(entries[0])) return 0;
        while (first + 1 < after) { uint32_t middle = first + (after - first) / 2; if (UNWIND_INFO_COMPRESSED_ENTRY_FUNC_OFFSET(entries[middle]) <= relative) first = middle; else after = middle; }
        uint32_t code = UNWIND_INFO_COMPRESSED_ENTRY_ENCODING_INDEX(entries[first]);
        if (code < header->commonEncodingsArrayCount) {
            const uint32_t *common = (const void *)(image->compact + header->commonEncodingsArraySectionOffset); *encoding = common[code];
        } else {
            code -= header->commonEncodingsArrayCount;
            if (code >= second->encodingsCount) return 0;
            const uint32_t *local = (const void *)(page + second->encodingsPageOffset); *encoding = local[code];
        }
        return image->base + indices[low].functionOffset + UNWIND_INFO_COMPRESSED_ENTRY_FUNC_OFFSET(entries[first]);
    }
    return 0;
}
static uint64_t minyar_cfi_unsigned(MinyarCFIReader *reader, unsigned bytes) {
    uint64_t value = 0;
    if (!reader->ok || (size_t)(reader->end - reader->p) < bytes) { reader->ok = 0; return 0; }
    for (unsigned index = 0; index < bytes; index++) value |= (uint64_t)*reader->p++ << (index * 8);
    return value;
}
static uint64_t minyar_cfi_uleb(MinyarCFIReader *reader) {
    uint64_t value = 0; unsigned shift = 0;
    while (reader->ok && shift < 64) { unsigned byte = (unsigned)minyar_cfi_unsigned(reader, 1); value |= (uint64_t)(byte & 127) << shift; if (!(byte & 128)) return value; shift += 7; }
    reader->ok = 0; return 0;
}
static int64_t minyar_cfi_sleb(MinyarCFIReader *reader) {
    uint64_t value = 0; unsigned shift = 0, byte = 0;
    do { byte = (unsigned)minyar_cfi_unsigned(reader, 1); value |= (uint64_t)(byte & 127) << shift; shift += 7; } while (reader->ok && (byte & 128) && shift < 64);
    if (byte & 128) { reader->ok = 0; return 0; }
    if (shift < 64 && (byte & 64)) value |= UINT64_MAX << shift;
    return (int64_t)value;
}
static uintptr_t minyar_cfi_pointer(MinyarCFIReader *reader, unsigned encoding) {
    uintptr_t base = (uintptr_t)reader->p; uint64_t value = 0;
    switch (encoding & 15) {
        case 0: value = minyar_cfi_unsigned(reader, 8); break;
        case 1: value = minyar_cfi_uleb(reader); break;
        case 2: value = minyar_cfi_unsigned(reader, 2); break;
        case 3: value = minyar_cfi_unsigned(reader, 4); break;
        case 4: value = minyar_cfi_unsigned(reader, 8); break;
        case 9: value = (uint64_t)minyar_cfi_sleb(reader); break;
        case 10: value = (uint64_t)(int64_t)(int16_t)minyar_cfi_unsigned(reader, 2); break;
        case 11: value = (uint64_t)(int64_t)(int32_t)minyar_cfi_unsigned(reader, 4); break;
        case 12: value = minyar_cfi_unsigned(reader, 8); break;
        default: reader->ok = 0;
    }
    unsigned application = encoding & 112;
    if (application != 0 && application != 16) reader->ok = 0;
    return (uintptr_t)value + (application == 16 ? base : 0);
}
static void minyar_cfi_rule(MinyarCFIRules *rules, uint64_t reg, unsigned kind, int64_t offset) {
    if (reg == 29) { rules->fp_kind = kind; rules->fp_offset = offset; }
    if (reg == 30) { rules->lr_kind = kind; rules->lr_offset = offset; }
}
static void minyar_cfi_copy(MinyarCFIRules *target, const MinyarCFIRules *source) {
    target->cfa_register = source->cfa_register; target->cfa_offset = source->cfa_offset;
    target->fp_offset = source->fp_offset; target->lr_offset = source->lr_offset;
    target->fp_kind = source->fp_kind; target->lr_kind = source->lr_kind;
}
static MINYAR_COLD int minyar_cfi_process(MinyarCFIReader *reader, MinyarCFIRules *rules, const MinyarCFIRules *initial, uintptr_t *location, uintptr_t target, uint64_t alignment, int64_t data_alignment, unsigned depth) {
    while (reader->ok && reader->p < reader->end) {
        unsigned code = (unsigned)minyar_cfi_unsigned(reader, 1), operand = code & 63;
        if ((code & 192) == 64) { *location += operand * alignment; if (*location > target) return 1; continue; }
        if ((code & 192) == 128) { minyar_cfi_rule(rules, operand, 1, (int64_t)minyar_cfi_uleb(reader) * data_alignment); continue; }
        if ((code & 192) == 192) { if (operand == 29) { rules->fp_kind = initial->fp_kind; rules->fp_offset = initial->fp_offset; } if (operand == 30) { rules->lr_kind = initial->lr_kind; rules->lr_offset = initial->lr_offset; } continue; }
        uint64_t reg, value;
        switch (code) {
            case 0: break;
            case 2: case 3: case 4: *location += minyar_cfi_unsigned(reader, code == 2 ? 1 : code == 3 ? 2 : 4) * alignment; if (*location > target) return reader->ok; break;
            case 5: reg = minyar_cfi_uleb(reader); value = minyar_cfi_uleb(reader); minyar_cfi_rule(rules, reg, 1, (int64_t)value * data_alignment); break;
            case 6: reg = minyar_cfi_uleb(reader); if (reg == 29) { rules->fp_kind = initial->fp_kind; rules->fp_offset = initial->fp_offset; } if (reg == 30) { rules->lr_kind = initial->lr_kind; rules->lr_offset = initial->lr_offset; } break;
            case 7: case 8: reg = minyar_cfi_uleb(reader); minyar_cfi_rule(rules, reg, code == 7 ? 2 : 0, 0); break;
            case 9: reg = minyar_cfi_uleb(reader); value = minyar_cfi_uleb(reader); if (reg == 29 || reg == 30) return 0; break;
            case 10: {
                if (depth == 16) return 0;
                MinyarCFIRules saved; minyar_cfi_copy(&saved, rules);
                int result = minyar_cfi_process(reader, rules, initial, location, target, alignment, data_alignment, depth + 1);
                if (result != 3) return result;
                minyar_cfi_copy(rules, &saved);
                break;
            }
            case 11: return depth ? 3 : 0;
            case 12: rules->cfa_register = (unsigned)minyar_cfi_uleb(reader); rules->cfa_offset = (int64_t)minyar_cfi_uleb(reader); break;
            case 13: rules->cfa_register = (unsigned)minyar_cfi_uleb(reader); break;
            case 14: rules->cfa_offset = (int64_t)minyar_cfi_uleb(reader); break;
            case 17: reg = minyar_cfi_uleb(reader); minyar_cfi_rule(rules, reg, 1, minyar_cfi_sleb(reader) * data_alignment); break;
            case 18: rules->cfa_register = (unsigned)minyar_cfi_uleb(reader); rules->cfa_offset = minyar_cfi_sleb(reader) * data_alignment; break;
            case 19: rules->cfa_offset = minyar_cfi_sleb(reader) * data_alignment; break;
            case 45: break; /* AArch64 return-address signing state. */
            case 46: (void)minyar_cfi_uleb(reader); break;
            default: return 0;
        }
    }
    return reader->ok ? 2 : 0;
}
static int minyar_cfi_instructions(MinyarCFIReader *reader, MinyarCFIRules *rules, const MinyarCFIRules *initial, uintptr_t start, uintptr_t target, uint64_t alignment, int64_t data_alignment) {
    int result = minyar_cfi_process(reader, rules, initial, &start, target, alignment, data_alignment, 0);
    return result == 1 || result == 2;
}
static MINYAR_COLD int minyar_trace_dwarf(const MinyarTraceImage *image, uint32_t offset, MinyarTraceRegisters *registers) {
    if (!image->eh || offset >= image->eh_size) return 0;
    MinyarCFIReader fde = {image->eh + offset, image->eh + image->eh_size, 1};
    uint64_t length = minyar_cfi_unsigned(&fde, 4); if (!length || length > (uint64_t)(fde.end - fde.p)) return 0; fde.end = fde.p + length;
    const unsigned char *cie_pointer = fde.p; uint64_t back = minyar_cfi_unsigned(&fde, 4); if (back > (uint64_t)(cie_pointer - image->eh)) return 0;
    MinyarCFIReader cie = {cie_pointer - back, image->eh + image->eh_size, 1};
    length = minyar_cfi_unsigned(&cie, 4); if (!length || length > (uint64_t)(cie.end - cie.p)) return 0; cie.end = cie.p + length;
    if (minyar_cfi_unsigned(&cie, 4) != 0) return 0;
    unsigned version = (unsigned)minyar_cfi_unsigned(&cie, 1); const unsigned char *augmentation = cie.p;
    while (cie.p < cie.end && *cie.p) cie.p++; if (cie.p == cie.end) return 0; cie.p++;
    if (version == 4) { if (minyar_cfi_unsigned(&cie, 1) != 8 || minyar_cfi_unsigned(&cie, 1) != 0) return 0; }
    if (version != 1 && version != 3 && version != 4) return 0;
    uint64_t alignment = minyar_cfi_uleb(&cie); int64_t data_alignment = minyar_cfi_sleb(&cie);
    uint64_t return_register = version == 1 ? minyar_cfi_unsigned(&cie, 1) : minyar_cfi_uleb(&cie); if (return_register != 30) return 0;
    unsigned encoding = 0;
    if (*augmentation == 'z') {
        uint64_t bytes = minyar_cfi_uleb(&cie); if (bytes > (uint64_t)(cie.end - cie.p)) return 0;
        const unsigned char *after = cie.p + bytes;
        for (const unsigned char *part = augmentation + 1; *part; part++) {
            if (*part == 'R') encoding = (unsigned)minyar_cfi_unsigned(&cie, 1);
            else if (*part == 'L') (void)minyar_cfi_unsigned(&cie, 1);
            else if (*part == 'P') { unsigned pointer = (unsigned)minyar_cfi_unsigned(&cie, 1); (void)minyar_cfi_pointer(&cie, pointer); }
            else if (*part != 'S') return 0;
        }
        cie.p = after;
    }
    MinyarCFIRules rules, defaults;
    rules.cfa_register = 31; rules.cfa_offset = rules.fp_offset = rules.lr_offset = 0;
    rules.fp_kind = rules.lr_kind = 0; minyar_cfi_copy(&defaults, &rules);
    if (!minyar_cfi_instructions(&cie, &rules, &defaults, 0, UINTPTR_MAX, alignment, data_alignment)) return 0;
    minyar_cfi_copy(&defaults, &rules);
    uintptr_t start = minyar_cfi_pointer(&fde, encoding); (void)minyar_cfi_pointer(&fde, encoding & 15);
    if (*augmentation == 'z') { uint64_t bytes = minyar_cfi_uleb(&fde); if (bytes > (uint64_t)(fde.end - fde.p)) return 0; fde.p += bytes; }
    if (!minyar_cfi_instructions(&fde, &rules, &defaults, start, registers->pc - 1, alignment, data_alignment)) return 0;
    uintptr_t source = rules.cfa_register == 31 ? registers->sp : rules.cfa_register == 29 ? registers->fp : 0;
    if (!source || rules.lr_kind != 1) return 0;
    uintptr_t cfa = source + (uintptr_t)rules.cfa_offset;
    if (cfa <= registers->sp || cfa - registers->sp > 1048576 || cfa % 16) return 0;
    uintptr_t lr = cfa + (uintptr_t)rules.lr_offset, fp = cfa + (uintptr_t)rules.fp_offset;
    if (lr < registers->sp || lr > cfa - 8) return 0;
    registers->pc = *(const uintptr_t *)lr;
    if (rules.fp_kind == 1) { if (fp < registers->sp || fp > cfa - 8) return 0; registers->fp = *(const uintptr_t *)fp; }
    else if (rules.fp_kind == 2) registers->fp = 0;
    registers->sp = cfa;
    return registers->pc != 0;
}
static MINYAR_COLD void minyar_trace_darwin(MinyarTrace *trace, uintptr_t *frame) {
    MinyarTraceImage image; minyar_trace_image(&image);
    MinyarTraceRegisters registers = {frame[1], (uintptr_t)(frame + 2), frame[0]};
    for (unsigned step = 0; step < 128 && registers.pc && trace->count < 12; step++) {
        uint32_t encoding = 0; uintptr_t region = minyar_trace_region(&image, registers.pc - 1, &encoding); if (!region) break;
        uintptr_t base = 0; const MinyarTraceRow *row = minyar_trace_find(region, &base, 0);
        if (row) { trace->rows[trace->count] = row; trace->bases[trace->count++] = base; }
        unsigned mode = encoding & UNWIND_ARM64_MODE_MASK;
        if (mode == UNWIND_ARM64_MODE_FRAME) {
            if (registers.fp < registers.sp || registers.fp - registers.sp > 1048576 || registers.fp % 16) break;
            uintptr_t *saved = (void *)registers.fp; registers.pc = saved[1]; registers.sp = (uintptr_t)(saved + 2); registers.fp = saved[0];
        } else if (mode == UNWIND_ARM64_MODE_DWARF) {
            if (!minyar_trace_dwarf(&image, encoding & UNWIND_ARM64_DWARF_SECTION_OFFSET, &registers)) break;
        } else break;
    }
}

#endif
