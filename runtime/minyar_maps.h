/* Native open-addressed Map. The opaque header is an ordinary fixed record. Its
 * buckets are one owned record of three fields per bucket: hash, key and value
 * side by side, so finding a key touches one bucket line. The record's
 * per-field reference flags mark the key and value fields that hold
 * references, so every allocator/RC profile retires it as an ordinary record.
 * Buckets never escape to language code. Empty hashes are zero; deletion closes
 * probe gaps, so repeated remove/insert never accumulates tombstones.
 * References occupy zeroed holes and are owned exactly once by the buckets. */
enum { MAP_ENTRIES, MAP_CAPACITY, MAP_GROW_AT, MAP_KEY_KIND, MAP_VALUE_REFERENCES, MAP_LENGTH,
       MAP_FIELDS, MAP_EQUAL_CALLBACK = MAP_FIELDS, MAP_HASH_CALLBACK, MAP_COPY_CALLBACK,
       MAP_RECORD_FIELDS };
typedef uint64_t (*MinyarRecordHash)(const MinyarRecord *);
typedef _Bool (*MinyarRecordEqual)(const MinyarRecord *, const MinyarRecord *);
typedef MinyarRecord *(*MinyarRecordCopy)(const MinyarRecord *);
MINYAR_HOT int map_key_references(long long kind) { return kind == 2 || kind >= 1000; }

/* Callback scopes keep every inspected Map alive and prevent callbacks from
 * invalidating cached bucket arrays. Cooperative recovery returns through the
 * scope's ordinary cleanup; no pointer to a returned stack frame survives. */
typedef struct MinyarMapReadGuard {
    const MinyarRecord *first, *second;
    struct MinyarMapReadGuard *previous;
} MinyarMapReadGuard;
static MINYAR_THREAD_LOCAL MinyarMapReadGuard *map_active_reads;

static inline void map_read_begin(MinyarMapReadGuard *guard, const MinyarRecord *first,
                                  const MinyarRecord *second) {
    guard->first = first;
    guard->second = second != first ? second : NULL;
    guard->previous = map_active_reads;
    if (!first) return;
    minyar_rc_retain((void *)first);
    if (guard->second) minyar_rc_retain((void *)guard->second);
    map_active_reads = guard;
}
static inline void map_read_end(const MinyarMapReadGuard *guard) {
    if (!guard->first) return;
    map_active_reads = guard->previous;
    if (guard->second) minyar_rc_release((void *)guard->second);
    minyar_rc_release((void *)guard->first);
}
MINYAR_HOT void map_check_mutation(const MinyarRecord *map) {
    for (const MinyarMapReadGuard *guard = map_active_reads; guard; guard = guard->previous)
        if (guard->first == map || guard->second == map)
            minyar_stop("a Map cannot be mutated from its hash or equality method.");
}

MINYAR_HOT MinyarRecord *map_entries(const MinyarRecord *map) {
    return (MinyarRecord *)(uintptr_t)map->values[MAP_ENTRIES];
}
MINYAR_HOT size_t map_capacity(const MinyarRecord *map) { return (size_t)map->values[MAP_CAPACITY]; }
#define MAP_HASH(entries, bucket) ((entries)->values[3 * (bucket)])
#define MAP_KEY(entries, bucket) ((entries)->values[3 * (bucket) + 1])
#define MAP_VALUE(entries, bucket) ((entries)->values[3 * (bucket) + 2])
/* One widening multiply and one xor-shift per 8-byte word of a Text key. Folding
 * the high half of the product back down lets the low bucket bits depend on
 * every input bit after a single multiply, so keys that share a prefix, a suffix
 * or a fixed stride still spread across buckets; the xor-shift then stirs the
 * low bits again. Measured at least as even as the full finaliser on word
 * lists, prefix/stride keys, paths, e-mail and city-shaped keys, for fewer
 * instructions. */
MINYAR_HOT uint64_t map_text_mix(uint64_t value) {
    __uint128_t product = (__uint128_t)value * UINT64_C(0xff51afd7ed558ccd);
    value = (uint64_t)product ^ (uint64_t)(product >> 64);
    return value ^ (value >> 29);
}
static long long map_canonical_key(long long kind, long long key) {
    if (kind == 7) {
        uint64_t bits = (uint64_t)key;
        if ((bits & UINT64_C(0x7fffffffffffffff)) == 0) return 0;
        if ((bits & UINT64_C(0x7ff0000000000000)) == UINT64_C(0x7ff0000000000000) &&
            (bits & UINT64_C(0x000fffffffffffff)))
            minyar_stop_program("NaN cannot be used as a Map key or Set element.");
    }
    return key;
}
#if defined(__GNUC__) || defined(__clang__)
#define MAP_GENERAL __attribute__((noinline))
#else
#define MAP_GENERAL
#endif
MINYAR_HOT uint64_t map_nonzero_hash(uint64_t hash) { return hash ? hash : UINT64_C(0x9e3779b97f4a7c15); }
/* Scalar keys (Integer, Character, Boolean, Float) need no avalanche: one
 * multiply by an odd constant is a bijection on the low bits, so runs of keys
 * never share a bucket, and folding the high half back down spreads keys that
 * are multiples of a power of two. Equal keys still hash alike, and Map
 * iteration order stays deterministic for a given key sequence. */
MINYAR_HOT uint64_t map_scalar_hash(uint64_t value) {
    value *= UINT64_C(0xff51afd7ed558ccd);
    return map_nonzero_hash(value ^ (value >> 29));
}
/* Text hashing loops over the bytes; it stays one out-of-line function so the
 * inlined Map paths keep the same shape for every key kind. */
MINYAR_HOT uint64_t map_bytes_hash(const unsigned char *p, size_t n) {
    /* Read immutable UTF-8 bytes, never the lazy character-offset cache.
     * Word mixing makes path/index keys cheap without decoding Unicode. */
    uint64_t hash = UINT64_C(0x9e3779b97f4a7c15) ^ (uint64_t)n;
    while (n >= 8) {
        /* One little-endian load per whole word: the same value eight byte
         * shifts used to assemble, and the same hash for every key. */
        uint64_t word;
        memcpy(&word, p, sizeof(word));
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
        word = __builtin_bswap64(word);
#endif
        hash = map_text_mix(hash ^ word); p += 8; n -= 8;
    }
    /* The same little-endian tail value from at most two loads; the
     * overlapping bytes are identical, so OR keeps them unchanged. */
    uint64_t tail = 0;
    if (n >= 4) {
        uint32_t low, high;
        memcpy(&low, p, sizeof(low));
        memcpy(&high, p + n - 4, sizeof(high));
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
        low = __builtin_bswap32(low);
        high = __builtin_bswap32(high);
#endif
        tail = (uint64_t)low | (uint64_t)high << (8 * (n - 4));
    } else if (n) {
        tail = (uint64_t)p[0] | (uint64_t)p[n / 2] << (8 * (n / 2)) | (uint64_t)p[n - 1] << (8 * (n - 1));
    }
    hash = map_text_mix(hash ^ tail);
    return map_nonzero_hash(hash);
}
static MAP_GENERAL uint64_t map_text_hash(const MinyarText *text) {
    return map_bytes_hash(text->bytes, (size_t)text->byte_length);
}
static uint64_t minyar_map_hash(long long kind, long long key) {
    if (kind == 2) return map_text_hash((const MinyarText *)(uintptr_t)key);
    return map_scalar_hash((uint64_t)map_canonical_key(kind, key));
}
uint64_t minyar_hash_slot(long long kind, long long key) {
    if (kind == 2 && !key) return 0; /* Inactive choice/Result payload. */
    return minyar_map_hash(kind, key);
}
static inline uint64_t map_hash_key(const MinyarRecord *map, long long key) {
    if (minyar_recovery_pending()) return 0;
    if (map->values[MAP_KEY_KIND] < 1000) return minyar_map_hash(map->values[MAP_KEY_KIND], key);
    MinyarRecordHash hash = (MinyarRecordHash)(uintptr_t)map->values[MAP_HASH_CALLBACK];
    minyar_runtime_callers++; /* stops inside a key callback are never contained */
    uint64_t value = hash((const MinyarRecord *)(uintptr_t)key);
    minyar_runtime_callers--;
    if (minyar_recovery_pending()) return 0;
    return value ? value : UINT64_C(0x9e3779b97f4a7c15);
}
/* Equal byte runs of one length. Keys are mostly short: up to 16 bytes compare
 * as two overlapping words (or halves, or three bytes) with no library call. */
MINYAR_HOT int map_bytes_equal(const unsigned char *a, const unsigned char *b, size_t n) {
    if (n >= 8) {
        if (n > 16) return !memcmp(a, b, n);
        uint64_t a0, b0, a1, b1;
        memcpy(&a0, a, 8); memcpy(&b0, b, 8);
        memcpy(&a1, a + n - 8, 8); memcpy(&b1, b + n - 8, 8);
        return !((a0 ^ b0) | (a1 ^ b1));
    }
    if (n >= 4) {
        uint32_t a0, b0, a1, b1;
        memcpy(&a0, a, 4); memcpy(&b0, b, 4);
        memcpy(&a1, a + n - 4, 4); memcpy(&b1, b + n - 4, 4);
        return !((a0 ^ b0) | (a1 ^ b1));
    }
    /* Positions 0, n/2 and n-1 cover every byte of a run of at most three. */
    return !n || (a[0] == b[0] && a[n / 2] == b[n / 2] && a[n - 1] == b[n - 1]);
}
MINYAR_HOT int map_key_equal(long long kind, long long a, long long b) {
    if (a == b) return 1;
    if (kind != 2) return 0;
    const MinyarText *left = (const MinyarText *)(uintptr_t)a;
    const MinyarText *right = (const MinyarText *)(uintptr_t)b;
    return left->byte_length == right->byte_length &&
        (left->bytes == right->bytes ||
         map_bytes_equal(left->bytes, right->bytes, (size_t)left->byte_length));
}

static inline int map_keys_equal(const MinyarRecord *map, long long a, long long b) {
    if (minyar_recovery_pending()) return 0;
    if (map->values[MAP_KEY_KIND] < 1000) return map_key_equal(map->values[MAP_KEY_KIND], a, b);
    MinyarRecordEqual equal = (MinyarRecordEqual)(uintptr_t)map->values[MAP_EQUAL_CALLBACK];
    minyar_runtime_callers++;
    int result = equal((const MinyarRecord *)(uintptr_t)a, (const MinyarRecord *)(uintptr_t)b);
    minyar_runtime_callers--;
    return !minyar_recovery_pending() && result;
}
/* The last slot found for a scalar or Text key, per thread, so an update such as
 * `if m.has(k) { m[k] += 1 }` hashes and probes k once. A present hit is
 * verified against the key stored in that slot; keys are unique, so a stale
 * entry after growth, removal or address reuse only misses. An absent hit
 * records the empty bucket that ended the probe and the hash, and is used only
 * while `map_epoch` says no bucket array of this thread's world changed since,
 * so a `has`/`getOr` miss followed by `m[k] = v` inserts at that bucket without
 * hashing or probing again. */
static MINYAR_THREAD_LOCAL struct {
    const MinyarRecord *map;
    long long key;
    uint64_t hash;
    size_t bucket;
    size_t capacity;
    unsigned long long epoch;
    int present;
} map_recent;
/* Bumped whenever a bucket array changes shape or contents: insert, grow,
 * removal and clear. A Map is never mutated by two threads at once, so a
 * per-thread counter is enough to prove nothing touched the recorded slot. */
static MINYAR_THREAD_LOCAL unsigned long long map_epoch = 1;
MINYAR_HOT void map_structure_changed(void) { map_epoch++; }
MINYAR_HOT size_t map_recent_find(const MinyarRecord *map, long long kind, long long key) {
    if (map_recent.map != map || map_recent.key != key || kind >= 1000 || !map_recent.present)
        return SIZE_MAX;
    const MinyarRecord *entries = map_entries(map);
    size_t bucket = map_recent.bucket;
    if (bucket >= map_capacity(map) || !MAP_HASH(entries, bucket) ||
        !map_key_equal(kind, MAP_KEY(entries, bucket), key))
        return SIZE_MAX;
    return bucket;
}
MINYAR_HOT void map_remember(const MinyarRecord *map, long long kind, long long key, size_t bucket,
                             uint64_t hash) {
    if (kind >= 1000) return;
    map_recent.map = map;
    map_recent.key = key;
    map_recent.hash = hash;
    map_recent.bucket = bucket;
    map_recent.capacity = map_capacity(map);
    map_recent.epoch = map_epoch;
    map_recent.present = 1;
}
MINYAR_HOT void map_remember_absent(const MinyarRecord *map, long long kind, long long key, size_t bucket,
                                    uint64_t hash) {
    if (kind >= 1000) return;
    map_recent.map = map;
    map_recent.key = key;
    map_recent.hash = hash;
    map_recent.bucket = bucket;
    map_recent.capacity = map_capacity(map);
    map_recent.epoch = map_epoch;
    map_recent.present = 0;
}
/* Zeroed buckets whose key and value fields are flagged as references when
 * the Map's keys or values are references. */
static MinyarRecord *map_new_entries(long long capacity, int key_references, int value_references) {
    MinyarRecord *entries;
    if (key_references || value_references) {
        entries = minyar_record_new(capacity * 3);
#ifndef MINYAR_COMPILER_ARENA
        unsigned char *references = (unsigned char *)(entries->values + entries->length);
        for (long long bucket = 0; bucket < capacity; bucket++) {
            references[3 * bucket + 1] = (unsigned char)key_references;
            references[3 * bucket + 2] = (unsigned char)value_references;
        }
#endif
        return entries;
    }
    /* Scalar keys and values: only the hash column has to start zero, because
     * an empty bucket is "hash 0" and its key and value are never read. */
    entries = minyar_record_new_unzeroed_scalar(capacity * 3);
    for (long long bucket = 0; bucket < capacity; bucket++) entries->values[3 * bucket] = 0;
    return entries;
}
static MinyarRecord *map_create(long long key_kind, long long value_references, long long fields) {
    MinyarRecord *map = minyar_record_new(fields);
    minyar_record_set(map, MAP_KEY_KIND, key_kind);
    minyar_record_set(map, MAP_VALUE_REFERENCES, !!value_references);
    minyar_record_set_take(map, MAP_ENTRIES, (long long)(uintptr_t)map_new_entries(0, map_key_references(key_kind), !!value_references));
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
    /* Compiler record ids can shift while dependency bodies remain cached.
     * Callbacks carry the statically checked layout; storage needs one record kind. */
    MinyarRecord *map = map_create(1000, value_references, MAP_RECORD_FIELDS);
    minyar_record_set(map, MAP_HASH_CALLBACK, (long long)(uintptr_t)hash);
    minyar_record_set(map, MAP_EQUAL_CALLBACK, (long long)(uintptr_t)equal);
    minyar_record_set(map, MAP_COPY_CALLBACK, (long long)(uintptr_t)copy);
    return map;
}
static inline size_t map_find(const MinyarRecord *map, long long key, uint64_t hash) {
    if (minyar_recovery_pending()) return SIZE_MAX;
    const MinyarRecord *entries = map_entries(map);
    size_t capacity = map_capacity(map);
    if (!capacity) return SIZE_MAX;
    size_t mask = capacity - 1, bucket = (size_t)hash & mask;
    while (MAP_HASH(entries, bucket)) {
        if ((uint64_t)MAP_HASH(entries, bucket) == hash) {
            int equal = map_keys_equal(map, MAP_KEY(entries, bucket), key);
            if (minyar_recovery_pending()) return SIZE_MAX;
            if (equal) return bucket;
        }
        bucket = (bucket + 1) & mask;
    }
    return bucket;
}
static MINYAR_COLD void map_grow(MinyarRecord *map) {
    MinyarRecord *old = map_entries(map);
    long long old_capacity = map->values[MAP_CAPACITY];
    long long capacity = old_capacity ? old_capacity : 4;
    if (capacity > LLONG_MAX / 6 || (uint64_t)capacity > SIZE_MAX / (6 * (sizeof(long long) + 1)))
        minyar_stop("this Map became too large.");
    capacity *= 2;
    MinyarRecord *fresh = map_new_entries(capacity, map_key_references(map->values[MAP_KEY_KIND]),
                                          !!map->values[MAP_VALUE_REFERENCES]);
    size_t mask = (size_t)capacity - 1;
    for (size_t i = 0; i < (size_t)old_capacity; i++) {
        uint64_t hash = (uint64_t)MAP_HASH(old, i);
        if (!hash) continue;
        size_t bucket = (size_t)hash & mask;
        while (MAP_HASH(fresh, bucket)) bucket = (bucket + 1) & mask;
        MAP_HASH(fresh, bucket) = MAP_HASH(old, i);
        MAP_KEY(fresh, bucket) = MAP_KEY(old, i);
        MAP_VALUE(fresh, bucket) = MAP_VALUE(old, i);
    }
    /* Transfer the owners before releasing the old buckets; no retain/release
     * per move. Emptied, the old record releases as one unit; deallocation
     * does not depend on its length, and its field bytes are accounted here. */
#ifndef MINYAR_COMPILER_ARENA
    RC_ACCOUNT(rc_bytes -= (size_t)old->length *
               (sizeof(long long) + (map_key_references(map->values[MAP_KEY_KIND]) ||
                                     map->values[MAP_VALUE_REFERENCES] ? 1 : 0)));
#endif
    old->length = 0;
    map->values[MAP_ENTRIES] = (long long)(uintptr_t)fresh;
    map->values[MAP_CAPACITY] = capacity;
    map->values[MAP_GROW_AT] = capacity - capacity / 4;
    minyar_rc_release(old);
    map_structure_changed();
}
static MAP_GENERAL _Bool map_has_general(const MinyarRecord *map, long long key) {
    if (minyar_recovery_pending()) return 0;
    long long kind = map->values[MAP_KEY_KIND]; key = map_canonical_key(kind, key);
    if (map_recent_find(map, kind, key) != SIZE_MAX) return 1;
    MinyarMapReadGuard guard;
    map_read_begin(&guard, kind >= 1000 ? map : NULL, NULL);
    int result = 0;
    uint64_t hash = map_hash_key(map, key);
    if (minyar_recovery_pending()) goto done;
    size_t bucket = map_find(map, key, hash);
    if (!minyar_recovery_pending())
        result = bucket != SIZE_MAX && MAP_HASH(map_entries(map), bucket) != 0;
    if (result) map_remember(map, kind, key, bucket, hash);
done:
    map_read_end(&guard);
    return result;
}
static MAP_GENERAL long long map_get_general(const MinyarRecord *map, long long key) {
    if (minyar_recovery_pending()) return 0;
    long long kind = map->values[MAP_KEY_KIND]; key = map_canonical_key(kind, key);
    size_t recent = map_recent_find(map, kind, key);
    if (recent != SIZE_MAX) return MAP_VALUE(map_entries(map), recent);
    MinyarMapReadGuard guard;
    map_read_begin(&guard, kind >= 1000 ? map : NULL, NULL);
    long long result = 0;
    int absent = 0;
    uint64_t hash = map_hash_key(map, key);
    if (minyar_recovery_pending()) goto done;
    size_t bucket = map_find(map, key, hash);
    if (minyar_recovery_pending()) goto done;
    if (bucket == SIZE_MAX || !MAP_HASH(map_entries(map), bucket)) absent = 1;
    else {
        result = MAP_VALUE(map_entries(map), bucket); /* Borrowed, like List.get. */
        map_remember(map, kind, key, bucket, hash);
    }
done:
    map_read_end(&guard);
    if (absent) minyar_stop_program("Map key is absent.");
    return result;
}
/* map.getOr(key, fallback): one probe; the stored value or the fallback,
 * borrowed either way like map[key]. */
static MAP_GENERAL long long map_get_or_general(const MinyarRecord *map, long long key, long long fallback) {
    if (minyar_recovery_pending()) return fallback;
    long long kind = map->values[MAP_KEY_KIND]; key = map_canonical_key(kind, key);
    size_t recent = map_recent_find(map, kind, key);
    if (recent != SIZE_MAX) return MAP_VALUE(map_entries(map), recent);
    MinyarMapReadGuard guard;
    map_read_begin(&guard, kind >= 1000 ? map : NULL, NULL);
    long long result = fallback;
    uint64_t hash = map_hash_key(map, key);
    if (minyar_recovery_pending()) goto done;
    size_t bucket = map_find(map, key, hash);
    if (minyar_recovery_pending()) goto done;
    if (bucket != SIZE_MAX && MAP_HASH(map_entries(map), bucket)) {
        result = MAP_VALUE(map_entries(map), bucket);
        map_remember(map, kind, key, bucket, hash);
    }
done:
    map_read_end(&guard);
    return result;
}
MINYAR_HOT void map_store_reference(MinyarRecord *entries, size_t field, long long value) {
#ifdef MINYAR_MAP_CYCLE_RUNTIME
    /* Bucket owners are untraced, but their children can be traced. The store
     * must shade retained children during a collector snapshot. Grow and
     * backshift transfer an existing owner without changing its count or its
     * (zero) traced incoming-edge count. Clear uses ordinary RC retirement,
     * whose cycle implementation also handles traced children. */
    minyar_record_replace_traced(entries, (long long)field, value, 0);
#else
    minyar_record_replace(entries, (long long)field, value, 0);
#endif
}
MINYAR_HOT void map_store_key(MinyarRecord *map, size_t bucket, long long key) {
    if (map_key_references(map->values[MAP_KEY_KIND])) map_store_reference(map_entries(map), 3 * bucket + 1, key);
    else MAP_KEY(map_entries(map), bucket) = key;
}
MINYAR_HOT void map_store_value(MinyarRecord *map, size_t bucket, long long value) {
    if (map->values[MAP_VALUE_REFERENCES]) map_store_reference(map_entries(map), 3 * bucket + 2, value);
    else MAP_VALUE(map_entries(map), bucket) = value;
}
static MAP_GENERAL void map_set_general(MinyarRecord *map, long long key, long long value) {
    if (minyar_recovery_pending()) return;
    map_check_mutation(map);
    long long kind = map->values[MAP_KEY_KIND]; key = map_canonical_key(kind, key);
    size_t recent = map_recent_find(map, kind, key);
    if (recent != SIZE_MAX) {
        map_store_value(map, recent, value);
        return;
    }
    MinyarMapReadGuard guard;
    map_read_begin(&guard, kind >= 1000 ? map : NULL, NULL);
    uint64_t hash = map_hash_key(map, key);
    if (minyar_recovery_pending()) goto done;
    size_t bucket = map_find(map, key, hash);
    if (minyar_recovery_pending()) goto done;
    if (bucket != SIZE_MAX && MAP_HASH(map_entries(map), bucket)) {
        /* Retain before replacing, including m[k] = m[k]. Keep the first key. */
        map_store_value(map, bucket, value);
        goto done;
    }
    if (map->values[MAP_LENGTH] >= map->values[MAP_GROW_AT]) {
        map_grow(map);
        /* Absence was established before mutation. Rehashing moves stored
         * hashes, so finding the new empty slot needs no further user call. */
        const MinyarRecord *entries = map_entries(map);
        size_t mask = map_capacity(map) - 1;
        bucket = (size_t)hash & mask;
        while (MAP_HASH(entries, bucket)) bucket = (bucket + 1) & mask;
    }
    if (kind >= 1000) {
        MinyarRecordCopy copy = (MinyarRecordCopy)(uintptr_t)map->values[MAP_COPY_CALLBACK];
        minyar_runtime_callers++;
        MinyarRecord *snapshot = copy((const MinyarRecord *)(uintptr_t)key);
        minyar_runtime_callers--;
        map_store_key(map, bucket, (long long)(uintptr_t)snapshot);
        minyar_rc_release(snapshot);
    } else map_store_key(map, bucket, key);
    map_store_value(map, bucket, value);
    MAP_HASH(map_entries(map), bucket) = (long long)hash;
    map->values[MAP_LENGTH]++;
    map_structure_changed();
    map_remember(map, kind, key, bucket, hash);
done:
    map_read_end(&guard);
}
/* Save references, close the cluster, then release. RC polls cannot see a
 * duplicate owner or a removed slot while buckets are being moved. */
MINYAR_HOT void map_remove_bucket(MinyarRecord *map, long long kind, size_t hole) {
    MinyarRecord *entries = map_entries(map);
    long long removed_key = MAP_KEY(entries, hole), removed_value = MAP_VALUE(entries, hole);
    size_t mask = map_capacity(map) - 1, scan = (hole + 1) & mask;
    while (MAP_HASH(entries, scan)) {
        size_t home = (size_t)(uint64_t)MAP_HASH(entries, scan) & mask;
        if (((hole - home) & mask) < ((scan - home) & mask)) {
            MAP_HASH(entries, hole) = MAP_HASH(entries, scan);
            MAP_KEY(entries, hole) = MAP_KEY(entries, scan);
            MAP_VALUE(entries, hole) = MAP_VALUE(entries, scan);
            hole = scan;
        }
        scan = (scan + 1) & mask;
    }
    MAP_HASH(entries, hole) = 0;
    MAP_KEY(entries, hole) = 0;
    MAP_VALUE(entries, hole) = 0;
    map->values[MAP_LENGTH]--;
    map_structure_changed();
    if (map_key_references(kind)) minyar_rc_release((void *)(uintptr_t)removed_key);
    if (map->values[MAP_VALUE_REFERENCES]) minyar_rc_release((void *)(uintptr_t)removed_value);
}
static MAP_GENERAL _Bool map_remove_general(MinyarRecord *map, long long key) {
    if (minyar_recovery_pending()) return 0;
    map_check_mutation(map);
    long long kind = map->values[MAP_KEY_KIND]; key = map_canonical_key(kind, key);
    MinyarMapReadGuard guard;
    map_read_begin(&guard, kind >= 1000 ? map : NULL, NULL);
    int result = 0;
    uint64_t hash = map_hash_key(map, key);
    if (minyar_recovery_pending()) goto done;
    size_t hole = map_find(map, key, hash);
    if (minyar_recovery_pending()) goto done;
    if (hole == SIZE_MAX || !MAP_HASH(map_entries(map), hole)) goto done;
    map_remove_bucket(map, kind, hole);
    result = 1;
done:
    map_read_end(&guard);
    return result;
}
/* Built-in keys (Integer, Text, Character, Boolean: kinds 1-4) hash and compare
 * without running user code, so their paths check recovery once on entry and
 * then probe with no further checks or read guards. Float keys (NaN rejection,
 * signed zero) and record keys (hash, equality and copy callbacks) take the
 * general paths above. The probe and hash helpers are always inlined and the
 * general paths are never inlined, so each entry point has one fixed shape and
 * adding an entry point cannot change how another one is compiled. */
MINYAR_HOT int map_builtin_kind(long long kind) { return kind < 7; }
/* map_text_hash's own result for byte_length < 8, without its out-of-line call:
 * no whole words to mix, one tail word and one mix, so short keys stay inside
 * the inlined entry point. */
MINYAR_HOT uint64_t map_text_hash_short(const MinyarText *text) {
    uint64_t hash = UINT64_C(0x9e3779b97f4a7c15) ^ (uint64_t)text->byte_length;
    const unsigned char *p = text->bytes;
    size_t n = (size_t)text->byte_length;
    uint64_t tail = 0;
    if (n >= 4) {
        uint32_t low, high;
        memcpy(&low, p, sizeof(low));
        memcpy(&high, p + n - 4, sizeof(high));
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
        low = __builtin_bswap32(low);
        high = __builtin_bswap32(high);
#endif
        tail = (uint64_t)low | (uint64_t)high << (8 * (n - 4));
    } else if (n)
        tail = (uint64_t)p[0] | (uint64_t)p[n / 2] << (8 * (n / 2)) | (uint64_t)p[n - 1] << (8 * (n - 1));
    return map_nonzero_hash(map_text_mix(hash ^ tail));
}
MINYAR_HOT uint64_t map_builtin_hash(long long kind, long long key) {
    if (kind == 2) {
        const MinyarText *text = (const MinyarText *)(uintptr_t)key;
        if ((size_t)text->byte_length < 8) return map_text_hash_short(text);
        return map_text_hash(text);
    }
    return map_scalar_hash((uint64_t)key);
}
/* The bucket holding key, or the empty bucket that ends its probe run. Stored
 * hashes are compared first, so Text bytes are compared only on a full hash
 * match. The load factor bound keeps an empty bucket in every table. */
MINYAR_HOT size_t map_builtin_probe(const MinyarRecord *entries, size_t mask, long long kind,
                                    long long key, uint64_t hash) {
    size_t bucket = (size_t)hash & mask;
    for (;;) {
        uint64_t stored = (uint64_t)MAP_HASH(entries, bucket);
        if (stored == hash) {
            long long other = MAP_KEY(entries, bucket);
            if (other == key || (kind == 2 && map_key_equal(2, other, key))) return bucket;
        } else if (!stored) return bucket;
        bucket = (bucket + 1) & mask;
    }
}
/* The present bucket for key, or SIZE_MAX; remembers a hit, and remembers the
 * empty bucket a miss ended at so a following store inserts without probing. */
MINYAR_HOT size_t map_builtin_find(const MinyarRecord *map, long long kind, long long key) {
    if (map_recent.map == map && map_recent.key == key) {
        size_t recent = map_recent_find(map, kind, key);
        if (recent != SIZE_MAX) return recent;
    }
    size_t capacity = map_capacity(map);
    if (!capacity) return SIZE_MAX;
    const MinyarRecord *entries = map_entries(map);
    uint64_t hash = map_builtin_hash(kind, key);
    size_t bucket = map_builtin_probe(entries, capacity - 1, kind, key, hash);
    if (!MAP_HASH(entries, bucket)) {
        map_remember_absent(map, kind, key, bucket, hash);
        return SIZE_MAX;
    }
    map_remember(map, kind, key, bucket, hash);
    return bucket;
}
static MINYAR_COLD MINYAR_NORETURN void map_key_absent(void) { minyar_stop_program("Map key is absent."); }
/* Insert an absent built-in key whose probe ended at the empty bucket. */
MINYAR_HOT void map_builtin_insert(MinyarRecord *map, long long kind, long long key, long long value,
                                   uint64_t hash, size_t bucket) {
    if (map->values[MAP_LENGTH] >= map->values[MAP_GROW_AT]) {
        map_grow(map);
        const MinyarRecord *entries = map_entries(map);
        size_t mask = map_capacity(map) - 1;
        bucket = (size_t)hash & mask;
        while (MAP_HASH(entries, bucket)) bucket = (bucket + 1) & mask;
    }
    map_store_key(map, bucket, key);
    map_store_value(map, bucket, value);
    MAP_HASH(map_entries(map), bucket) = (long long)hash;
    map->values[MAP_LENGTH]++;
    map_structure_changed();
    map_remember(map, kind, key, bucket, hash);
}

long long minyar_map_length(const MinyarRecord *map) { return map->values[MAP_LENGTH]; }
MINYAR_INLINE_ENTRY _Bool minyar_map_has(const MinyarRecord *map, long long key) {
    long long kind = map->values[MAP_KEY_KIND];
    if (!map_builtin_kind(kind)) return map_has_general(map, key);
    if (minyar_recovery_pending()) return 0;
    return map_builtin_find(map, kind, key) != SIZE_MAX;
}
MINYAR_INLINE_ENTRY long long minyar_map_get(const MinyarRecord *map, long long key) {
    long long kind = map->values[MAP_KEY_KIND];
    if (!map_builtin_kind(kind)) return map_get_general(map, key);
    if (minyar_recovery_pending()) return 0;
    size_t bucket = map_builtin_find(map, kind, key);
    if (bucket == SIZE_MAX) map_key_absent();
    return MAP_VALUE(map_entries(map), bucket); /* Borrowed, like List.get. */
}
/* map.getOr(key, fallback): one probe; the stored value or the fallback,
 * borrowed either way like map[key]. */
MINYAR_INLINE_ENTRY long long minyar_map_get_or(const MinyarRecord *map, long long key, long long fallback) {
    long long kind = map->values[MAP_KEY_KIND];
    if (!map_builtin_kind(kind)) return map_get_or_general(map, key, fallback);
    if (minyar_recovery_pending()) return fallback;
    size_t bucket = map_builtin_find(map, kind, key);
    return bucket == SIZE_MAX ? fallback : MAP_VALUE(map_entries(map), bucket);
}
/* A Text key a split index holds, probed without making the piece: the hash
 * and the comparison read the piece's bytes where they lie. */
static size_t map_range_probe(const MinyarRecord *entries, size_t mask, const unsigned char *bytes,
                              size_t length, uint64_t hash) {
    size_t bucket = (size_t)hash & mask;
    for (;;) {
        uint64_t stored = (uint64_t)MAP_HASH(entries, bucket);
        if (stored == hash) {
            const MinyarText *key = (const MinyarText *)(uintptr_t)MAP_KEY(entries, bucket);
            if ((size_t)key->byte_length == length && map_bytes_equal(key->bytes, bytes, length))
                return bucket;
        } else if (!stored) {
            return bucket;
        }
        bucket = (bucket + 1) & mask;
    }
}
static size_t map_split_index_find(const MinyarRecord *map, MinyarText *index, long long position) {
    long long start, end;
    text_index_range(index, position, &start, &end);
    size_t capacity = map_capacity(map);
    if (!capacity) return SIZE_MAX;
    const MinyarRecord *entries = map_entries(map);
    const unsigned char *bytes = index->bytes + start;
    size_t length = (size_t)(end - start);
    size_t bucket = map_range_probe(entries, capacity - 1, bytes, length, map_bytes_hash(bytes, length));
    return MAP_HASH(entries, bucket) ? bucket : SIZE_MAX;
}
MINYAR_INLINE_ENTRY _Bool minyar_map_text_split_index_has(const MinyarRecord *map, MinyarText *index,
                                                          long long position) {
    if (map->values[MAP_KEY_KIND] != 2 || minyar_recovery_pending()) return 0;
    return map_split_index_find(map, index, position) != SIZE_MAX;
}
MINYAR_INLINE_ENTRY long long minyar_map_text_split_index_get(const MinyarRecord *map, MinyarText *index,
                                                              long long position) {
    if (map->values[MAP_KEY_KIND] != 2 || minyar_recovery_pending()) return 0;
    size_t bucket = map_split_index_find(map, index, position);
    if (bucket == SIZE_MAX) map_key_absent();
    return MAP_VALUE(map_entries(map), bucket);
}

MINYAR_INLINE_ENTRY void minyar_map_set(MinyarRecord *map, long long key, long long value) {
    long long kind = map->values[MAP_KEY_KIND];
    if (!map_builtin_kind(kind)) { map_set_general(map, key, value); return; }
    if (minyar_recovery_pending()) return;
    map_check_mutation(map);
    if (map_recent.map == map && map_recent.key == key) {
        size_t recent = map_recent_find(map, kind, key);
        if (recent != SIZE_MAX) { map_store_value(map, recent, value); return; }
    }
    size_t capacity = map_capacity(map), bucket = 0;
    if (capacity && map_recent.map == map && map_recent.key == key && !map_recent.present &&
        map_recent.epoch == map_epoch && map_recent.capacity == capacity &&
        map_recent.bucket < capacity && !MAP_HASH(map_entries(map), map_recent.bucket) &&
        /* A Text key is a pointer: a freed key's address can hold another Text
         * by the time the store runs, so its stored hash must still match. Equal
         * keys always hash alike, so a match keeps this the same probe run. */
        (kind != 2 || map_recent.hash == map_builtin_hash(2, key))) {
        /* `has` or `getOr` just found this key absent and left the empty bucket
         * its probe ended at; nothing changed the bucket array since, so this is
         * one find-or-insert: no second hash and no second probe. */
        map_builtin_insert(map, kind, key, value, map_recent.hash, map_recent.bucket);
        return;
    }
    uint64_t hash = map_builtin_hash(kind, key);
    if (capacity) {
        const MinyarRecord *entries = map_entries(map);
        bucket = map_builtin_probe(entries, capacity - 1, kind, key, hash);
        if (MAP_HASH(entries, bucket)) {
            /* Retain before replacing, including m[k] = m[k]. Keep the first key. */
            map_store_value(map, bucket, value);
            map_remember(map, kind, key, bucket, hash);
            return;
        }
    }
    map_builtin_insert(map, kind, key, value, hash, bucket);
}
/* `m[k] op= v` with a scalar value finds the bucket once: the slot call reads
 * like minyar_map_get, failures included, and the compiler emits the store
 * call in place of minyar_map_set only when nothing between the two can run
 * user code, so the bucket cannot move. Where minyar_map_set would not simply
 * store (pending recovery, Float or record keys, or a Map read by an active
 * hash or equality method), the slot is a per-thread scratch copy and the
 * store runs minyar_map_set. */
static MINYAR_THREAD_LOCAL long long map_scratch_slot;
MINYAR_INLINE_ENTRY long long *minyar_map_value_slot(const MinyarRecord *map, long long key) {
    long long kind = map->values[MAP_KEY_KIND];
    if (!map_builtin_kind(kind) || map_active_reads) {
        long long value = minyar_map_get(map, key);
        map_scratch_slot = value;
        return &map_scratch_slot;
    }
    map_scratch_slot = 0;
    if (minyar_recovery_pending()) return &map_scratch_slot;
    size_t bucket = map_builtin_find(map, kind, key);
    if (bucket == SIZE_MAX) map_key_absent();
    return &MAP_VALUE(map_entries(map), bucket);
}
MINYAR_INLINE_ENTRY void minyar_map_store_slot(MinyarRecord *map, long long key, long long *slot, long long value) {
    if (slot == &map_scratch_slot || minyar_recovery_pending()) minyar_map_set(map, key, value);
    else *slot = value;
}
MINYAR_INLINE_ENTRY _Bool minyar_map_remove(MinyarRecord *map, long long key) {
    long long kind = map->values[MAP_KEY_KIND];
    if (!map_builtin_kind(kind)) return map_remove_general(map, key);
    if (minyar_recovery_pending()) return 0;
    map_check_mutation(map);
    size_t capacity = map_capacity(map);
    if (!capacity) return 0;
    const MinyarRecord *entries = map_entries(map);
    size_t bucket = map_builtin_probe(entries, capacity - 1, kind, key, map_builtin_hash(kind, key));
    if (!MAP_HASH(entries, bucket)) return 0;
    map_remove_bucket(map, kind, bucket);
    return 1;
}
void minyar_map_clear(MinyarRecord *map) {
    if (minyar_recovery_pending()) return;
    map_check_mutation(map);
    if (!map->values[MAP_LENGTH]) return;
    MinyarRecord *old = map_entries(map);
    map->values[MAP_ENTRIES] = (long long)(uintptr_t)map_new_entries(0, map_key_references(map->values[MAP_KEY_KIND]),
                                                                    !!map->values[MAP_VALUE_REFERENCES]);
    map->values[MAP_CAPACITY] = 0;
    map->values[MAP_GROW_AT] = 0;
    map->values[MAP_LENGTH] = 0;
    map_structure_changed();
    /* In bounded profiles bucket scans run through the existing cleanup budget. */
    minyar_rc_release(old);
}

MinyarList *minyar_map_keys(const MinyarRecord *map) {
    MinyarList *result = minyar_list_new();
    if (map_key_references(map->values[MAP_KEY_KIND]))
        minyar_list_references(result);
    list_reserve(result, map->values[MAP_LENGTH]);
    if (!map->values[MAP_LENGTH]) return result;
    for (size_t bucket = 0; bucket < map_capacity(map); bucket++)
        if (MAP_HASH(map_entries(map), bucket)) {
            long long key = MAP_KEY(map_entries(map), bucket);
            if (map->values[MAP_KEY_KIND] >= 1000) {
                MinyarRecordCopy copy = (MinyarRecordCopy)(uintptr_t)map->values[MAP_COPY_CALLBACK];
                minyar_runtime_callers++;
                MinyarRecord *snapshot = copy((const MinyarRecord *)(uintptr_t)key);
                minyar_runtime_callers--;
                minyar_list_add(result, (long long)(uintptr_t)snapshot);
                minyar_rc_release(snapshot);
            } else minyar_list_add(result, key);
        }
    return result;
}

/* Decode the compiler's reserved positive-child Map<Record, Enum> escape. */
static long long map_record_enum_value(long long type) {
    long long tag = -type % 8;
    long long index = tag - 1;
    if (tag == 7) index = 4;
    else if (tag < 1 || tag > 4) return 0;
    long long payload = -type / 8;
    if (payload % 2) return 0;
    long long child = payload / 2;
    if (child < 32 || (child >= 1000000000 && child < 1000099000)) return 0;
    long long remainder = child % 100000;
    if (remainder < 32 || remainder > 999) return 0;
    if (child >= 1000100000) child -= 100000;
    long long pair = (child / 100000 * 968 + remainder - 32) * 5 + index;
    if (pair >= 9801000000) return 0;
    return 1000000000 + pair % 99000;
}

_Bool minyar_maps_are_equal(const MinyarRecord *left, const MinyarRecord *right,
                            long long value_type) {
    if (minyar_recovery_pending()) return 0;
    if (!left || !right) return left == right;
    if (left->values[MAP_LENGTH] != right->values[MAP_LENGTH] ||
        left->values[MAP_KEY_KIND] != right->values[MAP_KEY_KIND])
        return 0;
    MinyarMapReadGuard guard;
    map_read_begin(&guard, left, right);
    int result = 0;
    if (!left->values[MAP_LENGTH]) { result = 1; goto done; }
    const MinyarRecord *entries = map_entries(left);
    for (size_t bucket = 0; bucket < map_capacity(left); bucket++) {
        if (!MAP_HASH(entries, bucket)) continue;
        size_t other = map_find(right, MAP_KEY(entries, bucket), (uint64_t)MAP_HASH(entries, bucket));
        if (minyar_recovery_pending()) goto done;
        if (other == SIZE_MAX || !MAP_HASH(map_entries(right), other)) goto done;
        long long a = MAP_VALUE(entries, bucket), b = MAP_VALUE(map_entries(right), other);
        if (value_type == 2) {
            if (!map_key_equal(2, a, b)) goto done;
        } else if (value_type == 7) {
            double x, y;
            memcpy(&x, &a, sizeof(x)); memcpy(&y, &b, sizeof(y));
            if (!(x == y)) goto done;
        } else if (value_type < -8 && (-value_type % 8) != 0) {
            long long payload = -value_type / 8;
            int enum_key = 0;
            if ((-value_type % 8) == 5) {
                enum_key = payload % 100000 < 1000;
                payload /= 100000;
                if (enum_key) payload /= 99;
            }
            long long child = payload % 2 ? -(payload / 2) - 1 : payload / 2;
            if (enum_key) {
                if (child >= 19 && child < 99019) child = 1000000000 + child - 19;
                else if (child >= 99019) child -= 99000;
            }
            long long enum_value = map_record_enum_value(value_type);
            if (enum_value) child = enum_value;
            if ((-value_type % 8) == 6) child = 4;
            if (!minyar_maps_are_equal((const MinyarRecord *)(uintptr_t)a,
                                      (const MinyarRecord *)(uintptr_t)b, child) ||
                minyar_recovery_pending()) goto done;
        } else if (a != b) goto done;
    }
    result = 1;
done:
    map_read_end(&guard);
    return result;
}
