/* Research-only join: relocate the initially shared copy path's two K service
 * hooks. Allocation helpers explicitly omit paid hooks; no global suppression
 * switch changes other allocation sites. Never include this in production. */
#ifndef MINYAR_RESEARCH_CREDIT_RELOCATION_H
#define MINYAR_RESEARCH_CREDIT_RELOCATION_H
#ifndef MINYAR_RESEARCH_BASE_JOIN
#define MINYAR_RESEARCH_BASE_JOIN minyar_join_text_take_left
#endif

#ifdef MINYAR_BOUNDED_RC
static void *research_data_without_service(size_t size) {
    research_data_allocations++;
    if (size > SIZE_MAX - sizeof(RcData))
        out_of_memory();
    RcData *data = RC_ALLOCATE(sizeof(*data) + size);
    if (!data)
        out_of_memory();
    data->size = size;
    RC_ACCOUNT(rc_bytes += sizeof(*data) + size);
    research_note_storage();
    return data + 1;
}

static MinyarText *research_text_without_service(const unsigned char *bytes, long long length,
                                                 long long characters) {
    research_object_allocations++;
    RcObject *object = RC_ALLOCATE(sizeof(*object) + sizeof(MinyarText));
    if (!object)
        out_of_memory();
    object->ownership = 8 | RC_TEXT;
    RC_ACCOUNT(rc_object_count++);
    RC_ACCOUNT(rc_bytes += sizeof(*object) + sizeof(MinyarText));
    research_note_storage();
    MinyarText *text = (MinyarText *)(object + 1);
    text->bytes = bytes;
    text->byte_length = length;
    text->character_length = characters;
    text->character_offsets = NULL;
    text->backing = NULL;
    return text;
}

static unsigned char *research_resize_without_service(unsigned char *bytes, size_t size) {
    research_data_resizes++;
    if (size > SIZE_MAX - sizeof(RcData))
        out_of_memory();
    RcData *data = (RcData *)bytes - 1;
    RC_ACCOUNT(rc_bytes -= data->size);
    data = rc_heap_resize(data, sizeof(*data) + data->size, sizeof(*data) + size);
    if (!data)
        out_of_memory();
    data->size = size;
    RC_ACCOUNT(rc_bytes += size);
    research_note_storage();
    return (unsigned char *)(data + 1);
}
#endif

static MinyarText *research_credit_join(MinyarText *left, const MinyarText *right, int relocated) {
    if (left->byte_length > LLONG_MAX - right->byte_length)
        join_too_large();
#ifdef MINYAR_BOUNDED_RC
    RcObject *object = (RcObject *)left - 1;
    if (relocated && !left->backing && (object->ownership & 7) == RC_TEXT &&
        (object->ownership >> 3) > 1 && rc_pending_count) {
        long long left_length = left->byte_length, right_length = right->byte_length;
        long long length = left_length + right_length;
        /* The unchanged initial state would choose copy, which has these two
         * separate K hooks. They are not hypothetical credits on unique paths. */
        rc_service_pending(MINYAR_RC_POLL_BUDGET);
        rc_service_pending(MINYAR_RC_POLL_BUDGET);
        if (object->ownership == (8 | RC_TEXT)) {
            RcData *data = (RcData *)left->bytes - 1;
            size_t required = (size_t)length + 1, capacity = data->size;
            unsigned char *bytes = (unsigned char *)left->bytes;
            if (required > capacity) {
                size_t grown = capacity > SIZE_MAX / 2 ? SIZE_MAX : capacity * 2;
                if (grown < required)
                    grown = required;
                bytes = research_resize_without_service(bytes, grown);
            }
            const unsigned char *right_bytes = right == left ? bytes : right->bytes;
            copy_bytes(bytes + left_length, right_bytes, (size_t)right_length);
            bytes[length] = 0;
            rc_free_data(left->character_offsets);
            left->bytes = bytes;
            left->byte_length = length;
            left->character_length =
                left->character_length == left_length && right->character_length == right_length
                    ? length
                    : -1;
            left->character_offsets = NULL;
            return left;
        }
        unsigned char *bytes = research_data_without_service((size_t)length + 1);
        copy_bytes(bytes, left->bytes, (size_t)left_length);
        copy_bytes(bytes + left_length, right->bytes, (size_t)right_length);
        bytes[length] = 0;
        long long characters =
            left->character_length == left_length && right->character_length == right_length
                ? length
                : -1;
        MinyarText *result = research_text_without_service(bytes, length, characters);
        /* The old consuming release still has its own K-immediate allowance. */
        minyar_rc_release(left);
        return result;
    }
#else
    (void)relocated;
#endif
    return MINYAR_RESEARCH_BASE_JOIN(left, right);
}
#endif
