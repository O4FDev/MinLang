#ifndef MINYAR_COMPILER_ARENA
static struct {
    RcObject ownership;
    MinyarText text;
} c_external_backing = {{RC_TEXT}, {NULL, 0, 0, NULL, NULL}};
#endif

MinyarBytes *minyar_c_record_new(long long size) {
    MinyarBytes *value = minyar_bytes_new(size);
    value->character_length = -1;
    return value;
}

MinyarBytes *minyar_c_record_view(MinyarBytes *owner, long long offset, long long size) {
    if (size < 0 || offset < 0 || size > owner->byte_length || offset > owner->byte_length - size)
        minyar_stop("a C-layout view must fit within its backing Bytes.");
    MinyarBytes *view = new_text(owner->bytes + offset, size, -1);
#ifndef MINYAR_COMPILER_ARENA
    MinyarText *root = owner->backing ? owner->backing : owner;
    view->backing = root;
    minyar_rc_retain(root);
#endif
    owner->character_length = -1;
    return view;
}

MinyarBytes *minyar_c_record_at(long long address, long long size) {
    if (!address || size <= 0 || (uint64_t)address > UINTPTR_MAX - (uint64_t)size)
        minyar_stop("a C-layout address view needs a nonzero address and a valid size.");
    MinyarBytes *view = new_text((const unsigned char *)(uintptr_t)address, size, -1);
#ifndef MINYAR_COMPILER_ARENA
    view->backing = &c_external_backing.text;
#endif
    return view;
}

MinyarBytes *minyar_c_record_copy(const void *source, long long size) {
    if (!source)
        minyar_stop("a native C-layout record returned a null pointer.");
    MinyarBytes *value = minyar_c_record_new(size);
    memcpy((void *)value->bytes, source, (size_t)size);
    return value;
}

void minyar_c_record_store(MinyarBytes *target, long long offset, const MinyarBytes *source,
                           long long size) {
    if (source->byte_length != size)
        minyar_stop("a C-layout field value has the wrong byte length.");
    bytes_check(target, offset, size);
    memmove((unsigned char *)target->bytes + offset, source->bytes, (size_t)size);
}

void minyar_c_record_check_integer(long long value, long long bits, long long signed_value) {
    if (bits == 64)
        return;
    if (bits != 8 && bits != 16 && bits != 32)
        minyar_stop("invalid C-layout integer width.");
    long long minimum = signed_value ? -(1LL << (bits - 1)) : 0;
    long long maximum = signed_value ? (1LL << (bits - 1)) - 1 : (1LL << bits) - 1;
    if (value < minimum || value > maximum)
        minyar_stop("an Integer does not fit in its C-layout field.");
}

void *minyar_c_record_pointer(const MinyarBytes *value, long long alignment) {
    if (alignment <= 0 || ((uintptr_t)value->bytes % (uintptr_t)alignment))
        minyar_stop("a native C-layout record pointer is not correctly aligned.");
    return (void *)value->bytes;
}
