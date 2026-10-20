#ifndef MINYAR_MOBILE_ANDROID_TRANSPORT_H
#define MINYAR_MOBILE_ANDROID_TRANSPORT_H

/* Only copied native bytes/scalars cross this transport. No Minyar or JNI
 * types belong here. A single worker owns the managed runtime; Java callers
 * may only bind, copy snapshots, and enqueue bounded events. */
#include <errno.h>
#include <limits.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define MA_MAX_NODES 1024u
#define MA_MAX_DEPTH 64u
#define MA_MAX_KEY 256u
#define MA_MAX_TEXT 16384u
#define MA_MAX_SNAPSHOT (1024u * 1024u)
#define MA_MAX_EVENTS 64u
#define MA_MAX_EVENT_BYTES (256u * 1024u)
#define MA_MAGIC UINT32_C(0x4d594131)

typedef struct {
    uint32_t parent, kind, spacing, padding, checked;
    const unsigned char *key, *text;
    size_t key_length, text_length;
} MaNode;

typedef struct {
    unsigned char *bytes;
    size_t length, count;
    MaNode *nodes; /* Key/text pointers refer only into bytes. */
} MaSnapshot;

typedef struct {
    uint64_t sequence;
    uint32_t node, kind;
    bool checked;
    size_t key_length, text_length;
    unsigned char *bytes; /* key followed by text, neither zero terminated. */
} MaEvent;

typedef struct {
    pthread_mutex_t mutex;
    pthread_cond_t condition;
    bool closed;
    uint64_t next_binding, binding, next_event, applied, revision;
    MaEvent events[MA_MAX_EVENTS];
    size_t head, count, event_bytes;
    MaSnapshot *snapshot;
} MaTransport;

#define MA_TRANSPORT_INITIALIZER { .mutex = PTHREAD_MUTEX_INITIALIZER, .condition = PTHREAD_COND_INITIALIZER }

/* Strict standard UTF-8, excluding zero because shared ui.View forbids it.
 * Accept lengths explicitly: JNI Modified UTF-8 and C strings are not used. */
static inline bool ma_utf8(const unsigned char *bytes, size_t length) {
    if (length && !bytes) return false;
    size_t offset = 0;
    while (offset < length) {
        unsigned c = bytes[offset++], following;
        uint32_t scalar, minimum;
        if (c > 0 && c < 0x80) continue;
        if (c >= 0xc2 && c <= 0xdf) { following = 1; scalar = c & 31u; minimum = 0x80; }
        else if (c >= 0xe0 && c <= 0xef) { following = 2; scalar = c & 15u; minimum = 0x800; }
        else if (c >= 0xf0 && c <= 0xf4) { following = 3; scalar = c & 7u; minimum = 0x10000; }
        else return false;
        if (following > length - offset) return false;
        for (unsigned index = 0; index < following; index++) {
            c = bytes[offset++];
            if ((c & 0xc0u) != 0x80u) return false;
            scalar = (scalar << 6) | (c & 63u);
        }
        if (scalar < minimum || scalar > 0x10ffff || (scalar >= 0xd800 && scalar <= 0xdfff)) return false;
    }
    return true;
}

static inline void ma_u32(unsigned char *out, uint32_t value) {
    for (unsigned index = 0; index < 4; index++) out[index] = (unsigned char)(value >> (24 - index * 8));
}
static inline void ma_u64(unsigned char *out, uint64_t value) {
    for (unsigned index = 0; index < 8; index++) out[index] = (unsigned char)(value >> (56 - index * 8));
}
static inline void ma_snapshot_free(MaSnapshot *snapshot) {
    if (!snapshot) return;
    free(snapshot->nodes);
    free(snapshot->bytes);
    free(snapshot);
}

/* Build privately, validate fully, then publish atomically. Caller input is
 * borrowed only for this call; every byte is copied into the resulting frame. */
static inline MaSnapshot *ma_snapshot_build(const unsigned char *title, size_t title_length,
                                          const MaNode *nodes, size_t count) {
    if (!nodes || !count || count > MA_MAX_NODES || title_length > MA_MAX_TEXT || !ma_utf8(title, title_length)) return NULL;
    size_t length = 28 + title_length;
    uint32_t depth[MA_MAX_NODES];
    for (size_t index = 0; index < count; index++) {
        const MaNode *node = &nodes[index];
        if (node->parent > index || (!index && node->parent) || (index && !node->parent) ||
            node->kind < 1 || node->kind > 7 || node->spacing > 256 || node->padding > 256 || node->checked > 1 ||
            node->key_length > MA_MAX_KEY || node->text_length > MA_MAX_TEXT ||
            !ma_utf8(node->key, node->key_length) || !ma_utf8(node->text, node->text_length)) return NULL;
        depth[index] = node->parent ? depth[node->parent - 1] + 1 : 1;
        if (depth[index] > MA_MAX_DEPTH || (node->parent && nodes[node->parent - 1].kind < 6)) return NULL;
        if (node->kind >= 3 && node->kind <= 5) {
            if (!node->key_length) return NULL;
            for (size_t prior = 0; prior < index; prior++) {
                const MaNode *other = &nodes[prior];
                if (other->kind >= 3 && other->kind <= 5 && other->key_length == node->key_length &&
                    !memcmp(other->key, node->key, node->key_length)) return NULL;
            }
        }
        size_t addition = 28 + node->key_length + node->text_length;
        if (addition > MA_MAX_SNAPSHOT - length) return NULL;
        length += addition;
    }
    MaSnapshot *snapshot = calloc(1, sizeof(*snapshot));
    if (!snapshot) return NULL;
    snapshot->bytes = malloc(length);
    snapshot->nodes = calloc(count, sizeof(*snapshot->nodes));
    if (!snapshot->bytes || !snapshot->nodes) { ma_snapshot_free(snapshot); return NULL; }
    snapshot->length = length;
    snapshot->count = count;
    unsigned char *out = snapshot->bytes;
    ma_u32(out, MA_MAGIC); ma_u64(out + 4, 0); ma_u64(out + 12, 0);
    ma_u32(out + 20, (uint32_t)count); ma_u32(out + 24, (uint32_t)title_length);
    out += 28;
    if (title_length) memcpy(out, title, title_length);
    out += title_length;
    for (size_t index = 0; index < count; index++) {
        const MaNode *node = &nodes[index];
        MaNode *copy = &snapshot->nodes[index];
        *copy = *node;
        ma_u32(out, node->parent); ma_u32(out + 4, node->kind);
        ma_u32(out + 8, node->spacing); ma_u32(out + 12, node->padding); ma_u32(out + 16, node->checked);
        ma_u32(out + 20, (uint32_t)node->key_length); out += 24;
        copy->key = out;
        if (node->key_length) memcpy(out, node->key, node->key_length);
        out += node->key_length;
        ma_u32(out, (uint32_t)node->text_length); out += 4;
        copy->text = out;
        if (node->text_length) memcpy(out, node->text, node->text_length);
        out += node->text_length;
    }
    return snapshot;
}

static inline uint64_t ma_attach(MaTransport *transport) {
    pthread_mutex_lock(&transport->mutex);
    uint64_t token = 0;
    if (!transport->closed && transport->next_binding < INT64_MAX) token = transport->binding = ++transport->next_binding;
    pthread_mutex_unlock(&transport->mutex);
    return token;
}
static inline void ma_detach(MaTransport *transport, uint64_t token) {
    pthread_mutex_lock(&transport->mutex);
    if (token && token == transport->binding) transport->binding = 0;
    pthread_mutex_unlock(&transport->mutex);
}
static inline void ma_event_free(MaEvent *event) {
    free(event->bytes);
    memset(event, 0, sizeof(*event));
}

/* Return positive admission sequence or zero for invalid/stale/full/closed.
 * The main thread never blocks waiting for queue capacity. Admitted events
 * remain owned by the worker queue even after their Activity detaches. */
static inline uint64_t ma_post(MaTransport *transport, uint64_t token, uint32_t node, uint32_t kind,
                               const unsigned char *key, size_t key_length,
                               const unsigned char *text, size_t text_length, bool checked) {
    if (!token || !node || (kind != 1 && kind != 2 && kind != 6) || !key_length || key_length > MA_MAX_KEY ||
        text_length > MA_MAX_TEXT || !ma_utf8(key, key_length) || !ma_utf8(text, text_length)) return 0;
    size_t bytes = key_length + text_length;
    unsigned char *copy = malloc(bytes);
    if (!copy) return 0;
    memcpy(copy, key, key_length);
    if (text_length) memcpy(copy + key_length, text, text_length);
    pthread_mutex_lock(&transport->mutex);
    uint64_t sequence = 0;
    if (!transport->closed && token == transport->binding && transport->snapshot &&
        transport->count < MA_MAX_EVENTS && bytes <= MA_MAX_EVENT_BYTES - transport->event_bytes && transport->next_event < INT64_MAX) {
        sequence = ++transport->next_event;
        size_t tail = (transport->head + transport->count) % MA_MAX_EVENTS;
        transport->events[tail] = (MaEvent){sequence, node, kind, checked, key_length, text_length, copy};
        transport->count++;
        transport->event_bytes += bytes;
        pthread_cond_signal(&transport->condition);
    }
    pthread_mutex_unlock(&transport->mutex);
    if (!sequence) free(copy);
    return sequence;
}

/* Single worker consumer. -1 = closed, 0 = timed wait elapsed, 1 = moved event.
 * Condvar uses its default CLOCK_REALTIME; compute matching absolute time.
 * Every wait checks its predicate under the same mutex used by producers. */
static inline int ma_take(MaTransport *transport, long long timeout_ms, MaEvent *event) {
    struct timespec deadline = {0, 0};
    if (timeout_ms > 0) {
        if (clock_gettime(CLOCK_REALTIME, &deadline)) return -1;
        deadline.tv_sec += (time_t)(timeout_ms / 1000);
        deadline.tv_nsec += (long)((timeout_ms % 1000) * 1000000);
        if (deadline.tv_nsec >= 1000000000) { deadline.tv_sec++; deadline.tv_nsec -= 1000000000; }
    }
    pthread_mutex_lock(&transport->mutex);
    while (!transport->closed && !transport->count) {
        if (!timeout_ms) { pthread_mutex_unlock(&transport->mutex); return 0; }
        int error = timeout_ms < 0 ? pthread_cond_wait(&transport->condition, &transport->mutex) :
                                   pthread_cond_timedwait(&transport->condition, &transport->mutex, &deadline);
        if (error && error != EINTR) { pthread_mutex_unlock(&transport->mutex); return error == ETIMEDOUT ? 0 : -1; }
    }
    if (transport->closed) { pthread_mutex_unlock(&transport->mutex); return -1; }
    *event = transport->events[transport->head];
    memset(&transport->events[transport->head], 0, sizeof(*event));
    transport->head = (transport->head + 1) % MA_MAX_EVENTS;
    transport->count--;
    transport->event_bytes -= event->key_length + event->text_length;
    pthread_mutex_unlock(&transport->mutex);
    return 1;
}

/* Check the latest descriptor immediately before dispatch. Even a structurally
 * stale admitted event advances the watermark, so UI pending edits can settle. */
static inline bool ma_apply_event(MaTransport *transport, const MaEvent *event) {
    pthread_mutex_lock(&transport->mutex);
    bool matches = false;
    if (transport->snapshot && event->node && event->node <= transport->snapshot->count) {
        const MaNode *node = &transport->snapshot->nodes[event->node - 1];
        matches = node->key_length == event->key_length && !memcmp(node->key, event->bytes, event->key_length) &&
                  ((node->kind == 3 && event->kind == 1) || (node->kind == 4 && (event->kind == 2 || event->kind == 6)) ||
                   (node->kind == 5 && event->kind == 2)) && (node->kind == 4 || event->text_length == 0) &&
                  (node->kind == 5 || !event->checked);
    }
    transport->applied = event->sequence;
    if (!matches && transport->snapshot && transport->revision < INT64_MAX) {
        ma_u64(transport->snapshot->bytes + 4, ++transport->revision);
        ma_u64(transport->snapshot->bytes + 12, transport->applied);
    }
    pthread_mutex_unlock(&transport->mutex);
    return matches;
}

/* Takes ownership on success only. Native snapshot readers receive a byte
 * copy, never this pointer or its descriptor references. */
static inline bool ma_publish(MaTransport *transport, MaSnapshot *snapshot) {
    if (!snapshot) return false;
    pthread_mutex_lock(&transport->mutex);
    if (transport->closed || transport->revision >= INT64_MAX) { pthread_mutex_unlock(&transport->mutex); return false; }
    ma_u64(snapshot->bytes + 4, ++transport->revision);
    ma_u64(snapshot->bytes + 12, transport->applied);
    MaSnapshot *before = transport->snapshot;
    transport->snapshot = snapshot;
    pthread_mutex_unlock(&transport->mutex);
    ma_snapshot_free(before);
    return true;
}

static inline unsigned char *ma_snapshot_copy(MaTransport *transport, uint64_t token, size_t *length) {
    *length = 0;
    pthread_mutex_lock(&transport->mutex);
    unsigned char *bytes = NULL;
    if (!transport->closed && token && token == transport->binding && transport->snapshot) {
        bytes = malloc(transport->snapshot->length);
        if (bytes) { *length = transport->snapshot->length; memcpy(bytes, transport->snapshot->bytes, *length); }
    }
    pthread_mutex_unlock(&transport->mutex);
    return bytes;
}

static inline void ma_close(MaTransport *transport) {
    pthread_mutex_lock(&transport->mutex);
    transport->closed = true;
    transport->binding = 0;
    pthread_cond_broadcast(&transport->condition);
    pthread_mutex_unlock(&transport->mutex);
}
/* Only after callers/consumer are joined. Tests explicitly prove ownership of
 * queued events and retained snapshots is reclaimed without a managed heap. */
static inline void ma_dispose(MaTransport *transport) {
    ma_close(transport);
    for (size_t index = 0; index < MA_MAX_EVENTS; index++) ma_event_free(&transport->events[index]);
    ma_snapshot_free(transport->snapshot);
    transport->snapshot = NULL;
    transport->count = transport->event_bytes = 0;
    pthread_cond_destroy(&transport->condition);
    pthread_mutex_destroy(&transport->mutex);
}

#endif
