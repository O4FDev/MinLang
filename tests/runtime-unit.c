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
    MinyarText *slice = minyar_text_slice(unicode, 1, 2);
    minyar_rc_keep(slice);
    minyar_rc_enter(0);
    minyar_rc_step(); /* Caller expression owners survive nested calls. */
    assert(minyar_text_character_at(slice, 0) == 0x1f642);
    minyar_rc_leave();
    minyar_rc_local(0, NULL);
    assert(rc_object_count == 1);
    minyar_rc_step();
    empty_heap();

    /* Consuming operations move exactly one owned count, including aliases. */
    MinyarText *owned = copy_c_text("transferred");
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
