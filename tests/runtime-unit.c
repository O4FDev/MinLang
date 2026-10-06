/* Exact ownership accounting complements native-language and sanitizer tests. */
#define MINYAR_RC_TESTING
#include "../runtime/minyar_runtime.c"
#include <assert.h>

static void empty_heap(void) {
    assert(rc_object_count == 0);
    assert(rc_bytes == 0);
}

/* A bounded abstract machine models owned and borrowed parameter slots. Every
 * transition checks actual counts against all modeled owners, not just exit. */
static void borrowed_frame_model(void) {
    enum { DEPTH = 16, SLOTS = 3, OBJECTS = 64, STEPS = 10000 };
    int values[DEPTH][SLOTS], owns[DEPTH][SLOTS] = {{0}};
    unsigned counts[OBJECTS] = {0};
    MinyarText *objects[OBJECTS] = {0};
    for (int d = 0; d < DEPTH; d++)
        for (int s = 0; s < SLOTS; s++) values[d][s] = -1;
    unsigned random = 0x7151;
    int depth = 1;
    minyar_rc_enter(SLOTS);
    for (int step = 0; step < STEPS; step++) {
        random = random * 1664525u + 1013904223u;
        int slot = (int)((random >> 8) % SLOTS);
        int other = (int)((random >> 16) % SLOTS);
        unsigned action = random % 5;
        int top = depth - 1;
        if (action == 0) {
            int id = 0;
            while (id < OBJECTS && counts[id]) id++;
            assert(id < OBJECTS);
            objects[id] = copy_c_text("modeled owner");
            minyar_rc_local_take(slot, objects[id]);
            values[top][slot] = id;
            owns[top][slot] = 1;
        } else if (action == 1) {
            int id = values[top][other];
            minyar_rc_local(slot, id < 0 ? NULL : objects[id]);
            values[top][slot] = id;
            owns[top][slot] = 1;
        } else if (action == 2 && depth < DEPTH) {
            int id = values[top][slot];
            minyar_rc_enter(SLOTS);
            for (int s = 0; s < SLOTS; s++) {
                values[depth][s] = -1;
                owns[depth][s] = 0;
            }
            values[depth][0] = id; /* Borrowed; no runtime local owner. */
            depth++;
        } else if (action == 3 && depth > 1) {
            int id = values[top][slot];
            MinyarText *result = id < 0 ? NULL : objects[id];
            minyar_rc_retain(result); /* Return a borrowed result as owned. */
            minyar_rc_leave();
            depth--;
            minyar_rc_local_take(other, result);
            values[depth - 1][other] = id;
            owns[depth - 1][other] = 1;
        } else {
            minyar_rc_local(slot, NULL);
            values[top][slot] = -1;
            owns[top][slot] = 0;
        }
        memset(counts, 0, sizeof(counts));
        for (int d = 0; d < depth; d++)
            for (int s = 0; s < SLOTS; s++)
                if (owns[d][s] && values[d][s] >= 0) counts[values[d][s]]++;
        size_t live = 0;
        for (int id = 0; id < OBJECTS; id++) {
            if (counts[id]) {
                live++;
                assert((((RcObject *)objects[id] - 1)->ownership >> 3) == counts[id]);
            }
        }
        for (int d = 0; d < depth; d++)
            for (int s = 0; s < SLOTS; s++)
                if (values[d][s] >= 0) assert(counts[values[d][s]] > 0);
        assert(rc_object_count == live);
    }
    while (depth--) minyar_rc_leave();
    empty_heap();
}

/* Full UTF-8 indexes can contain entirely ASCII sparse blocks. Independent
 * scalar/byte tables exercise both index widths and every boundary without
 * using the runtime decoder to construct expected values. */
static void mixed_ascii_index_blocks(void) {
    const int lengths[] = {1, 63, 64, 65, 127, 128, 129, 191, 192, 193, 257};
    const int positions[] = {0, 1, 62, 63, 64, 65, 126, 127, 128, 191, 192, 256};
    const unsigned char encodings[][4] = {{0xc3, 0xa9}, {0xe2, 0x82, 0xac}, {0xf0, 0x9f, 0x99, 0x82}};
    const int widths[] = {2, 3, 4}, scalars[] = {0xe9, 0x20ac, 0x1f642};
    for (size_t n = 0; n < sizeof(lengths) / sizeof(*lengths); ++n) {
        int length = lengths[n];
        for (size_t p = 0; p < sizeof(positions) / sizeof(*positions); ++p) {
            int special = positions[p];
            if (special >= length) continue;
            for (int encoding = 0; encoding < 3; ++encoding) {
                unsigned char *bytes = new_bytes(length + widths[encoding] - 1);
                long long offsets[258];
                int expected[257];
                long long count = 0;
                for (int i = 0; i < length; ++i) {
                    offsets[i] = count;
                    expected[i] = i == special ? scalars[encoding] : i % 128;
                    if (i == special) {
                        memcpy(bytes + count, encodings[encoding], (size_t)widths[encoding]);
                        count += widths[encoding];
                    } else bytes[count++] = (unsigned char)expected[i];
                }
                offsets[length] = count;
                bytes[count] = 0;
                MinyarText *text = new_text(bytes, count, -1);
                assert(minyar_text_length(text) == length && text->character_offsets);
                /* Reverse then forward queries repeatedly cross cached mixed
                 * blocks, complete ASCII blocks and their shorter final tail. */
                for (int direction = 0; direction < 2; ++direction) {
                    for (int step = 0; step <= length; ++step) {
                        int i = direction ? step : length - step;
                        int first = i / TEXT_INDEX_STRIDE * TEXT_INDEX_STRIDE;
                        int last = first + TEXT_INDEX_STRIDE;
                        if (last > length) last = length;
                        int ascii = special < first || special >= last;
                        size_t before = text_decode_count;
                        assert(indexed_byte_offset(text, i) == offsets[i]);
                        if (ascii) assert(text_decode_count == before);
                        if (i < length) {
                            before = text_decode_count;
                            assert(minyar_text_character_at(text, i) == expected[i]);
                            if (ascii) assert(text_decode_count == before);
                        }
                    }
                }
                const int starts[] = {0, 1, 63, 64, 65, 127, 128, length};
                for (size_t s = 0; s < sizeof(starts) / sizeof(*starts); ++s) {
                    int first = starts[s];
                    if (first > length) continue;
                    MinyarText *slice = minyar_text_slice(text, first, length);
                    assert(slice->byte_length == count - offsets[first]);
                    assert(memcmp(slice->bytes, bytes + offsets[first], (size_t)slice->byte_length) == 0);
                    assert(minyar_text_length(slice) == length - first);
                    minyar_rc_release(slice);
                }
                minyar_rc_release(text);
                empty_heap();
            }
        }
    }
    /* Synthetic tables isolate offset arithmetic without claiming enormous
     * allocated UTF-8 texts. No payload byte is dereferenced. The final full
     * block and position==length must not read the following cursor as a
     * breadcrumb; wide byte + absolute position would overflow before subtract. */
    const long long narrow_limit = UINT32_MAX >> 1;
    uint32_t narrow[5] = {0};
    MinyarText small_index = {NULL, narrow_limit, 128, narrow, NULL};
    text_index_store(&small_index, 1, ((uint64_t)(narrow_limit - 64) << 1) | 1);
    text_index_store(&small_index, 2, ((uint64_t)narrow_limit << 1) | 1);
    assert(narrow[2] == UINT32_MAX);
    assert(indexed_byte_offset(&small_index, 64) == narrow_limit - 64);
    assert(indexed_byte_offset(&small_index, 127) == narrow_limit - 1);
    assert(indexed_byte_offset(&small_index, 128) == narrow_limit);
    const long long wide_limits[] = {narrow_limit + 1, LLONG_MAX};
    for (size_t i = 0; i < sizeof(wide_limits) / sizeof(*wide_limits); ++i) {
        long long limit = wide_limits[i];
        uint64_t wide[5] = {0};
        MinyarText wide_index = {NULL, limit, 128, wide, NULL};
        text_index_store(&wide_index, 1, ((uint64_t)(limit - 64) << 1) | 1);
        text_index_store(&wide_index, 2, ((uint64_t)limit << 1) | 1);
        assert(wide[2] == ((uint64_t)limit << 1) + 1);
        assert(indexed_byte_offset(&wide_index, 64) == limit - 64);
        assert(indexed_byte_offset(&wide_index, 127) == limit - 1);
        assert(indexed_byte_offset(&wide_index, 128) == limit);
    }
}

int main(void) {
    minyar_rc_release(NULL);
    minyar_rc_enter(3);
    MinyarText *unicode = copy_c_text("é🙂");
    minyar_rc_keep(unicode); /* Adopt constructor ownership. */
    minyar_rc_local(0, unicode);
    minyar_rc_step();
    assert(minyar_text_character_at(unicode, 0) == 0xe9);
    assert(minyar_text_character_at(unicode, 1) == 0x1f642);
    assert(minyar_text_length(unicode) == 2);
    assert(((RcData *)unicode->character_offsets - 1)->size == 3 * sizeof(uint32_t));
    MinyarText *slice = minyar_text_slice(unicode, 1, 2);
    assert(slice->backing == unicode);
    assert(slice->bytes == unicode->bytes + 2);
    minyar_rc_keep(slice);
    minyar_rc_enter(0);
    minyar_rc_step(); /* Caller expression owners survive nested calls. */
    assert(minyar_text_character_at(slice, 0) == 0x1f642);
    minyar_rc_leave();
    minyar_rc_local(0, NULL);
    assert(rc_object_count == 2); /* The view retains its flattened backing. */
    minyar_rc_step();
    empty_heap();

    /* Non-ASCII indexes store one breadcrumb per 64 characters and scan only
       within that bounded block. Exercise both sides of each boundary. */
    unsigned char breadcrumb_bytes[261];
    for (int i = 0; i < 130; i++) {
        breadcrumb_bytes[i * 2] = 0xc3;
        breadcrumb_bytes[i * 2 + 1] = 0xa9;
    }
    breadcrumb_bytes[260] = 0;
    MinyarText *breadcrumbs = copy_c_text((const char *)breadcrumb_bytes);
    assert(minyar_text_length(breadcrumbs) == 130);
    assert(((RcData *)breadcrumbs->character_offsets - 1)->size == 5 * sizeof(uint32_t));
    assert(minyar_text_character_at(breadcrumbs, 63) == 0xe9);
    assert(minyar_text_character_at(breadcrumbs, 64) == 0xe9);
    assert(minyar_text_character_at(breadcrumbs, 129) == 0xe9);
    /* A forward scan resumes from the previous character instead of decoding
       from each breadcrumb again. Each lookup decodes exactly its result. */
    text_decode_count = 0;
    for (int i = 0; i < 130; i++)
        assert(minyar_text_character_at(breadcrumbs, i) == 0xe9);
    assert(text_decode_count == 130);
    MinyarText *boundary = minyar_text_slice(breadcrumbs, 63, 65);
    assert(boundary->byte_length == 4);
    minyar_rc_release(boundary);
    minyar_rc_release(breadcrumbs);
    empty_heap();
    mixed_ascii_index_blocks();

    /* Full slices share the value itself; nested views retain the owning root
       directly and never form an unbounded destruction chain. */
    MinyarText *root = copy_c_text("abcdef");
    MinyarText *whole = minyar_text_slice(root, 0, 6);
    assert(whole == root);
    assert(((RcObject *)root - 1)->ownership >> 3 == 2);
    minyar_rc_release(whole);
    MinyarText *view = minyar_text_slice(root, 1, 5);
    MinyarText *nested_view = minyar_text_slice(view, 1, 3);
    assert(view->backing == root && nested_view->backing == root);
    assert(nested_view->bytes == root->bytes + 2);
    minyar_rc_release(view);
    minyar_rc_release(root);
    MinyarText *expected_view = copy_c_text("cd");
    assert(minyar_texts_are_equal(nested_view, expected_view));
    minyar_rc_release(expected_view);
    minyar_rc_release(nested_view);
    empty_heap();

    /* Tiny slices of large sources copy instead of retaining an oversized
       allocation. This is the bounded retention guard for substring views. */
    unsigned char *large_bytes = new_bytes(8192);
    memset(large_bytes, 'x', 8192);
    large_bytes[8192] = 0;
    MinyarText *large = new_text(large_bytes, 8192, 8192);
    MinyarText *tiny = minyar_text_slice(large, 0, 1);
    assert(!tiny->backing && tiny->bytes != large->bytes);
    minyar_rc_release(large);
    assert(tiny->bytes[0] == 'x');
    minyar_rc_release(tiny);
    empty_heap();

    /* A compiler-proven owned left result grows geometrically in place. A
       shared left value takes the copying fallback and consumes one owner. */
    MinyarText *text_chain = copy_c_text("a");
    MinyarText *suffix = copy_c_text("b");
    MinyarText *chain_identity = text_chain;
    for (int i = 0; i < 10000; i++)
        text_chain = minyar_join_text_take_left(text_chain, suffix);
    assert(text_chain == chain_identity && text_chain->byte_length == 10001);
    assert(((RcData *)text_chain->bytes - 1)->size >= (size_t)text_chain->byte_length + 1);
    assert(((RcData *)text_chain->bytes - 1)->size < ((size_t)text_chain->byte_length + 1) * 2);
    minyar_rc_release(suffix);
    minyar_rc_release(text_chain);
    empty_heap();

    MinyarText *shared_left = copy_c_text("left");
    MinyarText *shared_alias = shared_left;
    minyar_rc_retain(shared_alias);
    MinyarText *shared_right = copy_c_text("right");
    MinyarText *copied_join = minyar_join_text_take_left(shared_left, shared_right);
    assert(copied_join != shared_alias);
    assert(shared_alias->byte_length == 4);
    assert(copied_join->byte_length == 9);
    minyar_rc_release(shared_alias);
    minyar_rc_release(shared_right);
    minyar_rc_release(copied_join);
    empty_heap();

    /* Consuming operations move exactly one owned count, including aliases. */
    MinyarText *owned = copy_c_text("transferred");
    minyar_rc_local_take(0, owned);
    assert(((RcObject *)owned - 1)->ownership >> 3 == 1);
    minyar_rc_local_move(0);
    assert(rc_frames->locals[0] == NULL);
    minyar_rc_local_take(0, owned);
    assert(((RcObject *)owned - 1)->ownership >> 3 == 1);
    minyar_rc_retain(owned); /* A returned owned alias of the existing local. */
    minyar_rc_local_take(0, owned);
    assert(((RcObject *)owned - 1)->ownership >> 3 == 1);
    MinyarList *transfers = minyar_list_new();
    minyar_list_references(transfers);
    minyar_rc_retain(owned);
    minyar_list_add_take(transfers, (long long)(intptr_t)owned);
    assert(((RcObject *)owned - 1)->ownership >> 3 == 2);
    MinyarRecord *transfer_record = minyar_record_new(1);
    minyar_rc_retain(owned);
    minyar_record_set_take(transfer_record, 0, (long long)(intptr_t)owned);
    assert(((RcObject *)owned - 1)->ownership >> 3 == 3);
    minyar_list_add_take(transfers, (long long)(intptr_t)transfer_record);
    minyar_rc_local(0, NULL);
    assert(((RcObject *)owned - 1)->ownership >> 3 == 2);
    minyar_rc_release(transfers);
    empty_heap();

    MinyarList *children = minyar_list_new();
    minyar_list_references(children);
    MinyarRecord *record = minyar_record_new(2);
    MinyarText *text = copy_c_text("retained");
    minyar_record_set_reference(record, 0, (long long)(intptr_t)text);
    /* An Integer identical to an object address must never be released. */
    minyar_record_set(record, 1, (long long)(intptr_t)text);
    minyar_list_add(children, (long long)(intptr_t)record);
    minyar_list_add(children, (long long)(intptr_t)record);
    minyar_rc_release(text);
    minyar_rc_release(record);
    minyar_list_set(children, 0, minyar_list_get(children, 0));
    assert(rc_object_count == 3);
    minyar_rc_release(children);
    empty_heap();

    /* Replacement can consume a compiler-proven owned value without a
       retain/drop pair, while releasing exactly the displaced slot owner. */
    MinyarList *replacements = minyar_list_new();
    minyar_list_references(replacements);
    MinyarText *old_value = copy_c_text("old");
    minyar_list_add_take(replacements, (long long)(intptr_t)old_value);
    MinyarText *new_value = copy_c_text("new");
    minyar_list_set_take(replacements, 0, (long long)(intptr_t)new_value);
    assert(rc_object_count == 2);
    assert(minyar_list_get(replacements, 0) == (long long)(intptr_t)new_value);
    assert(((RcObject *)new_value - 1)->ownership >> 3 == 1);
    minyar_rc_release(replacements);
    empty_heap();

    MinyarList *original = minyar_list_new();
    minyar_list_references(original);
    MinyarText *first = copy_c_text("first");
    minyar_list_add_take(original, (long long)(intptr_t)first);
    MinyarText *second = copy_c_text("second");
    MinyarList *appended = minyar_list_appended(
        original, (long long)(intptr_t)second, 1, 1);
    assert(original->length == 1 && appended->length == 2);
    assert(minyar_list_get(original, 0) == (long long)(intptr_t)first);
    assert(minyar_list_get(appended, 0) == (long long)(intptr_t)first);
    assert(minyar_list_get(appended, 1) == (long long)(intptr_t)second);
    assert(((RcObject *)first - 1)->ownership >> 3 == 2);
    assert(((RcObject *)second - 1)->ownership >> 3 == 1);
    minyar_rc_release(original);
    minyar_rc_release(appended);
    empty_heap();

    MinyarList *values = minyar_list_new();
    for (long long i = 0; i < 10000; i++) minyar_list_add(values, i);
    for (long long i = 0; i < 10000; i++) assert(minyar_list_get(values, i) == i);
    minyar_rc_release(values);
    empty_heap();

    MinyarRecord *point = minyar_record_new_scalar(2);
    minyar_record_set(point, 0, 42);
    minyar_record_set(point, 1, -17);
    assert(minyar_record_get(point, 0) == 42);
    assert(minyar_record_get(point, 1) == -17);
    /* Two scalar fields need only ownership, field count and field values. */
    assert(rc_bytes == 4 * sizeof(long long));
    minyar_rc_release(point);
    empty_heap();

    /* Empty, large, mixed and partially initialized compact records. */
    for (long long fields = 0; fields <= 130; fields++) {
        MinyarRecord *mixed = minyar_record_new(fields);
        for (long long field = 0; field < fields; field++) {
            if (field % 3 == 0) {
                MinyarText *child = copy_c_text("child");
                minyar_record_set_take(mixed, field, (long long)(intptr_t)child);
            } else if (field % 3 == 1) {
                minyar_record_set(mixed, field, field);
            } /* Remaining reference-map bytes stay zero. */
        }
        for (long long field = 0; field < fields; field++) {
            long long value = minyar_record_get(mixed, field);
            if (field % 3 == 0)
                assert(minyar_text_length((MinyarText *)(intptr_t)value) == 5);
            else
                assert(value == (field % 3 == 1 ? field : 0));
        }
        minyar_rc_release(mixed);
        empty_heap();
    }

    borrowed_frame_model();

    /* A wide list of leaf records must not need a work queue per element. */
    MinyarList *wide = minyar_list_new();
    minyar_list_references(wide);
    for (int i = 0; i < 100000; i++) {
        MinyarRecord *leaf = minyar_record_new_scalar(1);
        minyar_record_set(leaf, 0, i);
        minyar_list_add(wide, (long long)(intptr_t)leaf);
        minyar_rc_release(leaf);
    }
    minyar_rc_release(wide);
    empty_heap();
    assert(rc_pending_capacity <= 64);

    /* Runtime stress, independent of the language's recursive-type restriction. */
    MinyarRecord *chain = NULL;
    for (int i = 0; i < 100000; i++) {
        MinyarRecord *next = minyar_record_new(1);
        minyar_record_set_reference(next, 0, (long long)(intptr_t)chain);
        minyar_rc_release(chain);
        chain = next;
    }
    assert(rc_object_count == 100000);
    minyar_rc_release(chain); /* Must not recurse on the native call stack. */
    empty_heap();

    const int scalars[] = {0, 0x7f, 0x80, 0x7ff, 0x800, 0xd7ff, 0xe000,
                           0xffff, 0x10000, 0x10ffff};
    for (size_t i = 0; i < sizeof(scalars) / sizeof(*scalars); i++) {
        MinyarText *character = minyar_character_text(scalars[i]);
        assert(minyar_text_character_at(character, 0) == scalars[i]);
        assert(minyar_text_length(character) == 1);
        minyar_rc_release(character);
    }
    empty_heap();

    /* Control and two-byte scalar vectors from the Ruby peer audit. */
    const struct { int scalar; int length; unsigned char bytes[2]; } small_scalars[] = {
        {1, 1, {0x01}}, {8, 1, {0x08}}, {15, 1, {0x0f}},
        {24, 1, {0x18}}, {31, 1, {0x1f}},
        {129, 2, {0xc2, 0x81}}, {255, 2, {0xc3, 0xbf}},
    };
    for (size_t i = 0; i < sizeof(small_scalars) / sizeof(*small_scalars); i++) {
        MinyarText *character = minyar_character_text(small_scalars[i].scalar);
        assert(character->byte_length == small_scalars[i].length);
        assert(memcmp(character->bytes, small_scalars[i].bytes, small_scalars[i].length) == 0);
        assert(minyar_text_length(character) == 1);
        assert(minyar_text_character_at(character, 0) == small_scalars[i].scalar);
        minyar_rc_release(character);
    }
    empty_heap();

    /* Every supplementary-plane endpoint, with independent UTF-8 byte oracles. */
    const struct { int scalar; unsigned char bytes[4]; } plane_edges[] = {
        {0x10000, {0xf0, 0x90, 0x80, 0x80}},
        {0x1ffff, {0xf0, 0x9f, 0xbf, 0xbf}},
        {0x20000, {0xf0, 0xa0, 0x80, 0x80}},
        {0x2ffff, {0xf0, 0xaf, 0xbf, 0xbf}},
        {0x30000, {0xf0, 0xb0, 0x80, 0x80}},
        {0x3ffff, {0xf0, 0xbf, 0xbf, 0xbf}},
        {0x40000, {0xf1, 0x80, 0x80, 0x80}},
        {0x4ffff, {0xf1, 0x8f, 0xbf, 0xbf}},
        {0x50000, {0xf1, 0x90, 0x80, 0x80}},
        {0x5ffff, {0xf1, 0x9f, 0xbf, 0xbf}},
        {0x60000, {0xf1, 0xa0, 0x80, 0x80}},
        {0x6ffff, {0xf1, 0xaf, 0xbf, 0xbf}},
        {0x70000, {0xf1, 0xb0, 0x80, 0x80}},
        {0x7ffff, {0xf1, 0xbf, 0xbf, 0xbf}},
        {0x80000, {0xf2, 0x80, 0x80, 0x80}},
        {0x8ffff, {0xf2, 0x8f, 0xbf, 0xbf}},
        {0x90000, {0xf2, 0x90, 0x80, 0x80}},
        {0x9ffff, {0xf2, 0x9f, 0xbf, 0xbf}},
        {0xa0000, {0xf2, 0xa0, 0x80, 0x80}},
        {0xaffff, {0xf2, 0xaf, 0xbf, 0xbf}},
        {0xb0000, {0xf2, 0xb0, 0x80, 0x80}},
        {0xbffff, {0xf2, 0xbf, 0xbf, 0xbf}},
        {0xc0000, {0xf3, 0x80, 0x80, 0x80}},
        {0xcffff, {0xf3, 0x8f, 0xbf, 0xbf}},
        {0xd0000, {0xf3, 0x90, 0x80, 0x80}},
        {0xdffff, {0xf3, 0x9f, 0xbf, 0xbf}},
        {0xe0000, {0xf3, 0xa0, 0x80, 0x80}},
        {0xeffff, {0xf3, 0xaf, 0xbf, 0xbf}},
        {0xf0000, {0xf3, 0xb0, 0x80, 0x80}},
        {0xfffff, {0xf3, 0xbf, 0xbf, 0xbf}},
        {0x100000, {0xf4, 0x80, 0x80, 0x80}},
        {0x10ffff, {0xf4, 0x8f, 0xbf, 0xbf}},
    };
    for (size_t i = 0; i < sizeof(plane_edges) / sizeof(*plane_edges); i++) {
        MinyarText *character = minyar_character_text(plane_edges[i].scalar);
        assert(character->byte_length == 4);
        assert(memcmp(character->bytes, plane_edges[i].bytes, 4) == 0);
        assert(minyar_text_length(character) == 1);
        assert(minyar_text_character_at(character, 0) == plane_edges[i].scalar);
        minyar_rc_release(character);
    }
    empty_heap();

    /* Deterministic model-based list mutation with exact live-object counts. */
    enum { WIDTH = 32, OPERATIONS = 10000 };
    MinyarList *aliases = minyar_list_new();
    minyar_list_references(aliases);
    unsigned model[WIDTH], seed = 17;
    for (unsigned i = 0; i < WIDTH; i++) {
        MinyarText *item = format_integer_text(i);
        minyar_list_add(aliases, (long long)(intptr_t)item);
        minyar_rc_release(item);
        model[i] = i;
    }
    for (unsigned i = 0; i < OPERATIONS; i++) {
        seed = seed * 1664525u + 1013904223u;
        unsigned target = (seed >> 8) % WIDTH, source = (seed >> 16) % WIDTH;
        minyar_list_set(aliases, target, minyar_list_get(aliases, source));
        model[target] = model[source];
        unsigned live = 0;
        for (unsigned j = 0; j < WIDTH; j++) {
            unsigned first = 1;
            for (unsigned k = 0; k < j; k++) if (model[k] == model[j]) first = 0;
            live += first;
        }
        assert(rc_object_count == live + 1);
    }
    minyar_rc_release(aliases);
    empty_heap();

    MinyarText *cached = minyar_integer_text(42);
    minyar_rc_keep(cached);
    minyar_rc_leave();
    assert(minyar_integer_text(42) == cached);
    assert(cached->byte_length == 2 && cached->bytes[0] == '4');
    minyar_rc_release(cached);
    assert(rc_object_count == 1); /* Bounded cache is explicitly immortal. */
    assert(rc_frames == NULL);
    puts("runtime ownership, Unicode, alias model, deep cleanup, growth and cache checks passed");
    return 0;
}
