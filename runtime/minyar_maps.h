/* Native open-addressed Map. The opaque header is an ordinary fixed record;
 * its three owned Lists preserve every allocator/RC profile's existing ABI.
 * Bucket arrays never escape to language code. Empty hashes are zero; deletion
 * closes probe gaps, so repeated remove/insert never accumulates tombstones.
 * References occupy zeroed holes and are owned exactly once by their array. */
enum { MAP_HASHES, MAP_KEYS, MAP_VALUES, MAP_KEY_KIND, MAP_VALUE_REFERENCES, MAP_LENGTH,
       MAP_FIELDS, MAP_EQUAL_CALLBACK = MAP_FIELDS, MAP_HASH_CALLBACK, MAP_COPY_CALLBACK,
       MAP_RECORD_FIELDS };
typedef uint64_t (*MinyarRecordHash)(const MinyarRecord *);
typedef _Bool (*MinyarRecordEqual)(const MinyarRecord *, const MinyarRecord *);
typedef MinyarRecord *(*MinyarRecordCopy)(const MinyarRecord *);
static inline int map_key_references(long long kind) { return kind == 2 || kind >= 1000; }

static inline MinyarList *map_array(const MinyarRecord *map, unsigned field) {
    return (MinyarList *)(uintptr_t)map->values[field];
}
static inline uint64_t map_mix(uint64_t x) {
    x ^= x >> 30; x *= UINT64_C(0xbf58476d1ce4e5b9);
    x ^= x >> 27; x *= UINT64_C(0x94d049bb133111eb);
    return x ^ (x >> 31);
}
static long long map_canonical_key(long long kind, long long key) {
    if (kind == 7) {
        uint64_t bits = (uint64_t)key;
        if ((bits & UINT64_C(0x7fffffffffffffff)) == 0) return 0;
        if ((bits & UINT64_C(0x7ff0000000000000)) == UINT64_C(0x7ff0000000000000) &&
            (bits & UINT64_C(0x000fffffffffffff)))
            minyar_stop("NaN cannot be used as a Map key.");
    }
    return key;
}
static uint64_t minyar_map_hash(long long kind, long long key) {
    uint64_t hash;
    if (kind == 2) {
        const MinyarText *text = (const MinyarText *)(uintptr_t)key;
        /* Read immutable UTF-8 bytes, never the lazy character-offset cache.
         * Word mixing makes path/index keys cheap without decoding Unicode. */
        hash = UINT64_C(0x9e3779b97f4a7c15) ^ (uint64_t)text->byte_length;
        const unsigned char *p = text->bytes;
        size_t n = (size_t)text->byte_length;
        while (n >= 8) {
            uint64_t word = 0;
            /* Byte order is explicit, also avoiding unaligned reads. */
            for (unsigned i = 0; i < 8; i++) word |= (uint64_t)p[i] << (8 * i);
            hash = map_mix(hash ^ word); p += 8; n -= 8;
        }
        uint64_t tail = 0;
        for (unsigned i = 0; i < n; i++) tail |= (uint64_t)p[i] << (8 * i);
        hash = map_mix(hash ^ tail);
    } else hash = map_mix((uint64_t)map_canonical_key(kind, key));
    return hash ? hash : UINT64_C(0x9e3779b97f4a7c15);
}
uint64_t minyar_hash_slot(long long kind, long long key) {
    if (kind == 2 && !key) return 0; /* Inactive choice/Result payload. */
    return minyar_map_hash(kind, key);
}
static inline uint64_t map_hash_key(const MinyarRecord *map, long long key) {
    if (map->values[MAP_KEY_KIND] < 1000) return minyar_map_hash(map->values[MAP_KEY_KIND], key);
    MinyarRecordHash hash = (MinyarRecordHash)(uintptr_t)map->values[MAP_HASH_CALLBACK];
    uint64_t value = hash((const MinyarRecord *)(uintptr_t)key);
    return value ? value : UINT64_C(0x9e3779b97f4a7c15);
}
static inline int map_key_equal(long long kind, long long a, long long b) {
    if (a == b) return 1;
    if (kind != 2) return 0;
    const MinyarText *left = (const MinyarText *)(uintptr_t)a;
    const MinyarText *right = (const MinyarText *)(uintptr_t)b;
    return left->byte_length == right->byte_length &&
        (!left->byte_length || !memcmp(left->bytes, right->bytes, (size_t)left->byte_length));
}

static inline int map_keys_equal(const MinyarRecord *map, long long a, long long b) {
    if (map->values[MAP_KEY_KIND] < 1000) return map_key_equal(map->values[MAP_KEY_KIND], a, b);
    MinyarRecordEqual equal = (MinyarRecordEqual)(uintptr_t)map->values[MAP_EQUAL_CALLBACK];
    return equal((const MinyarRecord *)(uintptr_t)a, (const MinyarRecord *)(uintptr_t)b);
}
static MinyarList *map_new_array(long long capacity, int references) {
    MinyarList *array = minyar_list_new();
    if (references) minyar_list_references(array);
    if (capacity) {
        list_resize(array, capacity);
        memset(array->values, 0, (size_t)capacity * sizeof(*array->values));
    }
    array->length = capacity; /* Existing RC scans each possibly occupied slot. */
    return array;
}
static MinyarRecord *map_create(long long key_kind, long long value_references, long long fields) {
    MinyarRecord *map = minyar_record_new(fields);
    minyar_record_set(map, MAP_KEY_KIND, key_kind);
    minyar_record_set(map, MAP_VALUE_REFERENCES, !!value_references);
    minyar_record_set_take(map, MAP_HASHES, (long long)(uintptr_t)map_new_array(0, 0));
    minyar_record_set_take(map, MAP_KEYS, (long long)(uintptr_t)map_new_array(0, map_key_references(key_kind)));
    minyar_record_set_take(map, MAP_VALUES, (long long)(uintptr_t)map_new_array(0, !!value_references));
    return map;
}
MinyarRecord *minyar_map_new(long long key_kind, long long value_references) {
    if (key_kind != 1 && key_kind != 2 && key_kind != 3 && key_kind != 4 && key_kind != 7)
        minyar_stop("invalid Map key kind.");
    return map_create(key_kind, value_references, MAP_FIELDS);
}
MinyarRecord *minyar_map_new_record(long long key_kind, long long value_references,
                                    MinyarRecordHash hash, MinyarRecordEqual equal,
                                    MinyarRecordCopy copy) {
    if (key_kind < 1000 || !hash || !equal || !copy) minyar_stop("invalid record Map key callbacks.");
    MinyarRecord *map = map_create(key_kind, value_references, MAP_RECORD_FIELDS);
    minyar_record_set(map, MAP_HASH_CALLBACK, (long long)(uintptr_t)hash);
    minyar_record_set(map, MAP_EQUAL_CALLBACK, (long long)(uintptr_t)equal);
    minyar_record_set(map, MAP_COPY_CALLBACK, (long long)(uintptr_t)copy);
    return map;
}
static inline size_t map_find(const MinyarRecord *map, long long key, uint64_t hash) {
    MinyarList *hashes = map_array(map, MAP_HASHES), *keys = map_array(map, MAP_KEYS);
    if (!hashes->length) return SIZE_MAX;
    size_t mask = (size_t)hashes->length - 1, bucket = (size_t)hash & mask;
    while (hashes->values[bucket]) {
        if ((uint64_t)hashes->values[bucket] == hash &&
            map_keys_equal(map, keys->values[bucket], key)) return bucket;
        bucket = (bucket + 1) & mask;
    }
    return bucket;
}
static MINYAR_COLD void map_grow(MinyarRecord *map) {
    MinyarList *old[3] = {map_array(map, MAP_HASHES), map_array(map, MAP_KEYS), map_array(map, MAP_VALUES)};
    long long capacity = old[0]->length ? old[0]->length : 4;
    if (capacity > LLONG_MAX / 2 || (uint64_t)capacity > SIZE_MAX / (2 * sizeof(long long)))
        minyar_stop("this Map became too large.");
    capacity *= 2;
    MinyarList *fresh[3] = {map_new_array(capacity, 0),
        map_new_array(capacity, map_key_references(map->values[MAP_KEY_KIND])),
        map_new_array(capacity, !!map->values[MAP_VALUE_REFERENCES])};
#ifndef MINYAR_COMPILER_ARENA
    /* Preserve immortal-only promotion state when moving existing owners. */
    for (unsigned f = 1; f < 3; f++) {
        RcObject *dst = (RcObject *)fresh[f] - 1, *src = (RcObject *)old[f] - 1;
        dst->ownership = (dst->ownership & ~(size_t)7) | (src->ownership & 7);
    }
#endif
    size_t mask = (size_t)capacity - 1;
    for (size_t i = 0; i < (size_t)old[0]->length; i++) {
        uint64_t hash = (uint64_t)old[0]->values[i];
        if (!hash) continue;
        size_t bucket = (size_t)hash & mask;
        while (fresh[0]->values[bucket]) bucket = (bucket + 1) & mask;
        for (unsigned f = 0; f < 3; f++) fresh[f]->values[bucket] = old[f]->values[i];
    }
    /* Transfer the slots before releasing arrays; no retain/release per move. */
    for (unsigned f = 0; f < 3; f++) old[f]->length = 0;
    for (unsigned f = 0; f < 3; f++) map->values[f] = (long long)(uintptr_t)fresh[f];
    for (unsigned f = 0; f < 3; f++) minyar_rc_release(old[f]);
}
long long minyar_map_length(const MinyarRecord *map) { return map->values[MAP_LENGTH]; }
_Bool minyar_map_has(const MinyarRecord *map, long long key) {
    long long kind = map->values[MAP_KEY_KIND]; key = map_canonical_key(kind, key);
    size_t bucket = map_find(map, key, map_hash_key(map, key));
    return bucket != SIZE_MAX && map_array(map, MAP_HASHES)->values[bucket] != 0;
}
long long minyar_map_get(const MinyarRecord *map, long long key) {
    long long kind = map->values[MAP_KEY_KIND]; key = map_canonical_key(kind, key);
    size_t bucket = map_find(map, key, map_hash_key(map, key));
    if (bucket == SIZE_MAX || !map_array(map, MAP_HASHES)->values[bucket])
        minyar_stop("Map key is absent.");
    return map_array(map, MAP_VALUES)->values[bucket]; /* Borrowed, like List.get. */
}
static inline void map_store(MinyarList *array, size_t bucket, long long value) {
#ifdef MINYAR_MAP_CYCLE_RUNTIME
    /* Bucket owners are untraced, but their children can be traced. The store
     * must shade retained children during a collector snapshot. Grow and
     * backshift transfer an existing owner without changing its count or its
     * (zero) traced incoming-edge count. Clear uses ordinary RC retirement,
     * whose cycle implementation also handles traced children. */
    minyar_list_set_traced(array, (long long)bucket, value);
#else
    minyar_list_set(array, (long long)bucket, value);
#endif
}
void minyar_map_set(MinyarRecord *map, long long key, long long value) {
    long long kind = map->values[MAP_KEY_KIND]; key = map_canonical_key(kind, key);
    uint64_t hash = map_hash_key(map, key);
    size_t bucket = map_find(map, key, hash);
    if (bucket != SIZE_MAX && map_array(map, MAP_HASHES)->values[bucket]) {
        /* Retain before replacing, including m[k] = m[k]. Keep the first key. */
        map_store(map_array(map, MAP_VALUES), bucket, value);
        return;
    }
    long long capacity = map_array(map, MAP_HASHES)->length;
    if (!capacity || map->values[MAP_LENGTH] >= capacity - capacity / 4) {
        map_grow(map); bucket = map_find(map, key, hash);
    }
    if (kind >= 1000) {
        MinyarRecordCopy copy = (MinyarRecordCopy)(uintptr_t)map->values[MAP_COPY_CALLBACK];
        MinyarRecord *snapshot = copy((const MinyarRecord *)(uintptr_t)key);
        map_store(map_array(map, MAP_KEYS), bucket, (long long)(uintptr_t)snapshot);
        minyar_rc_release(snapshot);
    } else map_store(map_array(map, MAP_KEYS), bucket, key);
    map_store(map_array(map, MAP_VALUES), bucket, value);
    map_array(map, MAP_HASHES)->values[bucket] = (long long)hash;
    map->values[MAP_LENGTH]++;
}
_Bool minyar_map_remove(MinyarRecord *map, long long key) {
    long long kind = map->values[MAP_KEY_KIND]; key = map_canonical_key(kind, key);
    size_t hole = map_find(map, key, map_hash_key(map, key));
    MinyarList *arrays[3] = {map_array(map, MAP_HASHES), map_array(map, MAP_KEYS), map_array(map, MAP_VALUES)};
    if (hole == SIZE_MAX || !arrays[0]->values[hole]) return 0;
    /* Save references, close the cluster, then release. RC polls cannot see a
     * duplicate owner or a removed slot while the arrays are being moved. */
    long long removed_key = arrays[1]->values[hole], removed_value = arrays[2]->values[hole];
    size_t mask = (size_t)arrays[0]->length - 1, scan = (hole + 1) & mask;
    while (arrays[0]->values[scan]) {
        size_t home = (size_t)(uint64_t)arrays[0]->values[scan] & mask;
        if (((hole - home) & mask) < ((scan - home) & mask)) {
            for (unsigned f = 0; f < 3; f++) arrays[f]->values[hole] = arrays[f]->values[scan];
            hole = scan;
        }
        scan = (scan + 1) & mask;
    }
    for (unsigned f = 0; f < 3; f++) arrays[f]->values[hole] = 0;
    map->values[MAP_LENGTH]--;
    if (map_key_references(kind)) minyar_rc_release((void *)(uintptr_t)removed_key);
    if (map->values[MAP_VALUE_REFERENCES]) minyar_rc_release((void *)(uintptr_t)removed_value);
    return 1;
}
void minyar_map_clear(MinyarRecord *map) {
    if (!map->values[MAP_LENGTH]) return;
    MinyarList *old[3] = {map_array(map, MAP_HASHES), map_array(map, MAP_KEYS), map_array(map, MAP_VALUES)};
    MinyarList *fresh[3] = {map_new_array(0, 0), map_new_array(0, map_key_references(map->values[MAP_KEY_KIND])),
                          map_new_array(0, !!map->values[MAP_VALUE_REFERENCES])};
    for (unsigned f = 0; f < 3; f++) map->values[f] = (long long)(uintptr_t)fresh[f];
    map->values[MAP_LENGTH] = 0;
    /* In bounded profiles array scans run through the existing cleanup budget. */
    for (unsigned f = 0; f < 3; f++) minyar_rc_release(old[f]);
}

MinyarList *minyar_map_keys(const MinyarRecord *map) {
    MinyarList *result = minyar_list_new();
    if (map_key_references(map->values[MAP_KEY_KIND]))
        minyar_list_references(result);
    list_reserve(result, map->values[MAP_LENGTH]);
    MinyarList *hashes = map_array(map, MAP_HASHES), *keys = map_array(map, MAP_KEYS);
    for (long long bucket = 0; bucket < hashes->length; bucket++)
        if (hashes->values[bucket]) {
            if (map->values[MAP_KEY_KIND] >= 1000) {
                MinyarRecordCopy copy = (MinyarRecordCopy)(uintptr_t)map->values[MAP_COPY_CALLBACK];
                MinyarRecord *snapshot = copy((const MinyarRecord *)(uintptr_t)keys->values[bucket]);
                minyar_list_add(result, (long long)(uintptr_t)snapshot);
                minyar_rc_release(snapshot);
            } else minyar_list_add(result, keys->values[bucket]);
        }
    return result;
}

_Bool minyar_maps_are_equal(const MinyarRecord *left, const MinyarRecord *right,
                            long long value_type) {
    if (left->values[MAP_LENGTH] != right->values[MAP_LENGTH] ||
        left->values[MAP_KEY_KIND] != right->values[MAP_KEY_KIND])
        return 0;
    MinyarList *hashes = map_array(left, MAP_HASHES), *keys = map_array(left, MAP_KEYS);
    MinyarList *values = map_array(left, MAP_VALUES), *other_values = map_array(right, MAP_VALUES);
    for (long long bucket = 0; bucket < hashes->length; bucket++) {
        if (!hashes->values[bucket]) continue;
        size_t other = map_find(right, keys->values[bucket], (uint64_t)hashes->values[bucket]);
        if (other == SIZE_MAX || !map_array(right, MAP_HASHES)->values[other]) return 0;
        long long a = values->values[bucket], b = other_values->values[other];
        if (value_type == 2) {
            if (!map_key_equal(2, a, b)) return 0;
        } else if (value_type == 7) {
            double x, y;
            memcpy(&x, &a, sizeof(x)); memcpy(&y, &b, sizeof(y));
            if (!(x == y)) return 0;
        } else if (value_type < -8 && (-value_type % 8) != 0) {
            long long payload = -value_type / 8;
            if ((-value_type % 8) == 5) payload /= 100000;
            long long child = payload % 2 ? -(payload / 2) - 1 : payload / 2;
            if ((-value_type % 8) == 6) child = 4;
            if (!minyar_maps_are_equal((const MinyarRecord *)(uintptr_t)a,
                                      (const MinyarRecord *)(uintptr_t)b, child)) return 0;
        } else if (a != b) return 0;
    }
    return 1;
}
