#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif
#include <assert.h>
#include <stdio.h>
#include "../runtime/native/mobile-android-transport.h"

static const unsigned char title[] = "Minyar";
static const unsigned char name[] = "name", welcome[] = "welcome", light[] = "light";
static const unsigned char unicode[] = "Zo\xc3\xab\xf0\x9f\x8c\xbf";

static void fixture_nodes(MaNode nodes[4]) {
    nodes[0] = (MaNode){.kind = 7, .spacing = 20, .padding = 24};
    nodes[1] = (MaNode){.parent = 1, .kind = 4, .spacing = 12, .key = name, .key_length = 4,
                        .text = unicode, .text_length = sizeof(unicode) - 1};
    nodes[2] = (MaNode){.parent = 1, .kind = 5, .spacing = 12, .checked = 1,
                        .key = welcome, .key_length = 7, .text = (const unsigned char *)"Say hello", .text_length = 9};
    nodes[3] = (MaNode){.parent = 1, .kind = 3, .spacing = 12, .key = light, .key_length = 5,
                        .text = (const unsigned char *)"Light", .text_length = 5};
}
static MaSnapshot *fixture(void) {
    MaNode nodes[4]; fixture_nodes(nodes);
    MaSnapshot *snapshot = ma_snapshot_build(title, sizeof(title) - 1, nodes, 4);
    assert(snapshot);
    return snapshot;
}
static uint32_t read32(const unsigned char *bytes, size_t length, size_t *offset) {
    assert(*offset <= length && length - *offset >= 4);
    uint32_t value = 0;
    for (unsigned index = 0; index < 4; index++) value = (value << 8) | bytes[(*offset)++];
    return value;
}
static uint64_t read64(const unsigned char *bytes, size_t length, size_t *offset) {
    uint64_t high = read32(bytes, length, offset), low = read32(bytes, length, offset);
    return (high << 32) | low;
}
static void verify_bytes(const unsigned char *bytes, size_t length, size_t *offset,
                         const unsigned char *expected, size_t expected_length) {
    uint32_t count = read32(bytes, length, offset);
    assert(count == expected_length && *offset <= length && count <= length - *offset);
    if (count) assert(!memcmp(bytes + *offset, expected, count));
    *offset += count;
}
static void wire(void) {
    MaTransport transport = MA_TRANSPORT_INITIALIZER;
    uint64_t binding = ma_attach(&transport);
    assert(binding == 1);
    MaNode nodes[4]; fixture_nodes(nodes);
    unsigned char borrowed[] = "Mutable";
    nodes[3].text = borrowed; nodes[3].text_length = 7;
    MaSnapshot *snapshot = ma_snapshot_build(title, 6, nodes, 4);
    assert(snapshot);
    borrowed[0] = 'X';
    assert(snapshot->nodes[3].text[0] == 'M');
    assert(ma_publish(&transport, snapshot));
    size_t length, offset = 0;
    unsigned char *bytes = ma_snapshot_copy(&transport, binding, &length);
    assert(bytes && bytes != snapshot->bytes);
    assert(read32(bytes, length, &offset) == MA_MAGIC);
    assert(read64(bytes, length, &offset) == 1);
    assert(read64(bytes, length, &offset) == 0);
    assert(read32(bytes, length, &offset) == 4);
    verify_bytes(bytes, length, &offset, title, 6);
    for (size_t index = 0; index < 4; index++) {
        const MaNode *node = &snapshot->nodes[index];
        assert(read32(bytes, length, &offset) == node->parent);
        assert(read32(bytes, length, &offset) == node->kind);
        assert(read32(bytes, length, &offset) == node->spacing);
        assert(read32(bytes, length, &offset) == node->padding);
        assert(read32(bytes, length, &offset) == node->checked);
        verify_bytes(bytes, length, &offset, node->key, node->key_length);
        verify_bytes(bytes, length, &offset, node->text, node->text_length);
    }
    assert(offset == length);
    assert(ma_publish(&transport, fixture()));
    assert(bytes[0] == 'M'); /* Prior Java-facing copy outlives frame replacement. */
    free(bytes);
    ma_dispose(&transport);
}
static void unicode_and_limits(void) {
    static const unsigned char valid[] = {1, 0x7f, 0xc2, 0x80, 0xe0, 0xa0, 0x80, 0xf4, 0x8f, 0xbf, 0xbf};
    static const unsigned char invalid[][4] = {{0}, {0xc0,0x80}, {0xed,0xa0,0x80}, {0xf4,0x90,0x80,0x80}, {0xe2,0x82}, {0x80}};
    static const size_t invalid_lengths[] = {1,2,3,4,2,1};
    assert(ma_utf8(valid, sizeof(valid)) && ma_utf8(NULL, 0));
    for (size_t index = 0; index < sizeof(invalid_lengths)/sizeof(*invalid_lengths); index++)
        assert(!ma_utf8(invalid[index], invalid_lengths[index]));
    assert(!ma_utf8(NULL, 1));
    MaNode nodes[MA_MAX_NODES + 1]; memset(nodes, 0, sizeof(nodes)); fixture_nodes(nodes);
    assert(!ma_snapshot_build(title, 6, nodes, 0));
    assert(!ma_snapshot_build(title, 6, nodes, MA_MAX_NODES + 1));
    nodes[3].key = welcome; nodes[3].key_length = 7;
    assert(!ma_snapshot_build(title, 6, nodes, 4));
    fixture_nodes(nodes); nodes[0].kind = 1;
    assert(!ma_snapshot_build(title, 6, nodes, 4));
    fixture_nodes(nodes); nodes[1].parent = 2;
    assert(!ma_snapshot_build(title, 6, nodes, 4));
    fixture_nodes(nodes); nodes[1].text = invalid[2]; nodes[1].text_length = 3;
    assert(!ma_snapshot_build(title, 6, nodes, 4));
    for (size_t index = 0; index < 65; index++) nodes[index] = (MaNode){.parent = (uint32_t)index, .kind = 7};
    MaSnapshot *snapshot = ma_snapshot_build(NULL, 0, nodes, 64); assert(snapshot); ma_snapshot_free(snapshot);
    assert(!ma_snapshot_build(NULL, 0, nodes, 65));
    unsigned char *large = malloc(MA_MAX_TEXT); assert(large); memset(large, 'a', MA_MAX_TEXT);
    nodes[0] = (MaNode){.kind = 7};
    for (size_t index = 1; index < 65; index++) nodes[index] = (MaNode){.parent = 1, .kind = 1, .text = large, .text_length = MA_MAX_TEXT};
    snapshot = ma_snapshot_build(NULL, 0, nodes, 64); assert(snapshot && snapshot->length < MA_MAX_SNAPSHOT); ma_snapshot_free(snapshot);
    assert(!ma_snapshot_build(NULL, 0, nodes, 65));
    free(large);
}
static void binding_and_events(void) {
    MaTransport transport = MA_TRANSPORT_INITIALIZER;
    uint64_t first = ma_attach(&transport);
    assert(!ma_post(&transport, first, 2, 2, name, 4, unicode, sizeof(unicode)-1, false)); /* No first frame. */
    assert(ma_publish(&transport, fixture()));
    unsigned char key[] = "name", text[] = "Copied";
    uint64_t sequence = ma_post(&transport, first, 2, 2, key, 4, text, 6, false); assert(sequence == 1);
    key[0] = 'X'; text[0] = 'X';
    uint64_t second = ma_attach(&transport); assert(second > first);
    ma_detach(&transport, first); /* Late previous Activity detach cannot unbind new Activity. */
    size_t length; assert(!ma_snapshot_copy(&transport, first, &length));
    unsigned char *bytes = ma_snapshot_copy(&transport, second, &length); assert(bytes); free(bytes);
    assert(!ma_post(&transport, first, 2, 2, name, 4, NULL, 0, false));
    MaEvent event = {0}; assert(ma_take(&transport, 0, &event) == 1);
    assert(event.sequence == 1 && !memcmp(event.bytes, "nameCopied", 10));
    assert(ma_apply_event(&transport, &event)); ma_event_free(&event);
    assert(ma_publish(&transport, fixture()));
    assert(ma_post(&transport, second, 4, 1, light, 5, NULL, 0, false) == 2);
    assert(ma_take(&transport, 0, &event) == 1 && ma_apply_event(&transport, &event)); ma_event_free(&event);
    assert(ma_post(&transport, second, 2, 6, name, 4, unicode, sizeof(unicode)-1, false) == 3);
    assert(ma_take(&transport, 0, &event) == 1 && ma_apply_event(&transport, &event)); ma_event_free(&event);
    assert(ma_post(&transport, second, 3, 2, welcome, 7, NULL, 0, true) == 4);
    MaNode changed[4]; fixture_nodes(changed); changed[2].kind = 1; changed[2].key = NULL; changed[2].key_length = 0;
    assert(ma_publish(&transport, ma_snapshot_build(title, 6, changed, 4)));
    assert(ma_take(&transport, 0, &event) == 1 && !ma_apply_event(&transport, &event)); ma_event_free(&event);
    bytes = ma_snapshot_copy(&transport, second, &length); assert(bytes);
    size_t offset = 12; assert(read64(bytes, length, &offset) == 4); free(bytes); /* Stale event acknowledged. */
    assert(ma_post(&transport, second, 2, 2, name, 4, unicode, sizeof(unicode)-1, true) == 5);
    assert(ma_take(&transport, 0, &event) == 1 && !ma_apply_event(&transport, &event)); ma_event_free(&event);
    assert(ma_post(&transport, second, 4, 1, light, 5, NULL, 0, true) == 6);
    assert(ma_take(&transport, 0, &event) == 1 && !ma_apply_event(&transport, &event)); ma_event_free(&event);
    bytes = ma_snapshot_copy(&transport, second, &length); assert(bytes);
    offset = 12; assert(read64(bytes, length, &offset) == 6); free(bytes);
    assert(!ma_post(&transport, second, 2, 99, name, 4, NULL, 0, false));
    const unsigned char zero = 0; assert(!ma_post(&transport, second, 2, 2, name, 4, &zero, 1, false));
    ma_detach(&transport, second);
    assert(!ma_post(&transport, second, 2, 2, name, 4, NULL, 0, false));
    ma_dispose(&transport);
}
static void backpressure(void) {
    MaTransport transport = MA_TRANSPORT_INITIALIZER;
    uint64_t token = ma_attach(&transport); assert(ma_publish(&transport, fixture()));
    MaEvent empty = {0};
    assert(ma_take(&transport, 0, &empty) == 0);
    assert(ma_take(&transport, 1, &empty) == 0);
    for (size_t index = 0; index < MA_MAX_EVENTS; index++)
        assert(ma_post(&transport, token, 4, 1, light, 5, NULL, 0, false) == index + 1);
    assert(!ma_post(&transport, token, 4, 1, light, 5, NULL, 0, false));
    for (size_t index = 0; index < MA_MAX_EVENTS; index++) {
        MaEvent event = {0}; assert(ma_take(&transport, 0, &event) == 1 && event.sequence == index + 1);
        ma_event_free(&event);
    }
    assert(transport.count == 0 && transport.event_bytes == 0);
    unsigned char *large = malloc(MA_MAX_TEXT + 1); assert(large); memset(large, 'a', MA_MAX_TEXT + 1);
    assert(!ma_post(&transport, token, 2, 2, name, 4, large, MA_MAX_TEXT + 1, false));
    size_t admitted = 0;
    while (ma_post(&transport, token, 2, 2, name, 4, large, MA_MAX_TEXT, false)) admitted++;
    assert(admitted == MA_MAX_EVENT_BYTES / (MA_MAX_TEXT + 4) && admitted < MA_MAX_EVENTS);
    free(large);
    ma_dispose(&transport); /* Frees every still-queued payload and retained frame. */
}
typedef struct {
    MaTransport *transport;
    pthread_mutex_t mutex;
    pthread_cond_t condition;
    bool ready;
    int result;
    MaEvent event;
} Waiter;
static void *consume(void *argument) {
    Waiter *waiter = argument;
    pthread_mutex_lock(&waiter->mutex); waiter->ready = true; pthread_cond_signal(&waiter->condition); pthread_mutex_unlock(&waiter->mutex);
    waiter->result = ma_take(waiter->transport, -1, &waiter->event);
    return NULL;
}
static void wake_case(bool close) {
    MaTransport transport = MA_TRANSPORT_INITIALIZER;
    uint64_t token = ma_attach(&transport); assert(ma_publish(&transport, fixture()));
    Waiter waiter = {.transport = &transport, .mutex = PTHREAD_MUTEX_INITIALIZER, .condition = PTHREAD_COND_INITIALIZER};
    pthread_t worker; assert(!pthread_create(&worker, NULL, consume, &waiter));
    pthread_mutex_lock(&waiter.mutex);
    while (!waiter.ready) assert(!pthread_cond_wait(&waiter.condition, &waiter.mutex));
    pthread_mutex_unlock(&waiter.mutex);
    if (close) ma_close(&transport);
    else assert(ma_post(&transport, token, 4, 1, light, 5, NULL, 0, false));
    assert(!pthread_join(worker, NULL));
    assert(waiter.result == (close ? -1 : 1));
    if (!close) { assert(waiter.event.sequence == 1); ma_event_free(&waiter.event); }
    ma_close(&transport);
    assert(!ma_attach(&transport));
    assert(!ma_post(&transport, token, 4, 1, light, 5, NULL, 0, false));
    assert(!ma_publish(&transport, NULL));
    ma_dispose(&transport);
    pthread_cond_destroy(&waiter.condition); pthread_mutex_destroy(&waiter.mutex);
}
int main(void) {
    wire(); unicode_and_limits(); binding_and_events(); backpressure(); wake_case(false); wake_case(true);
    puts("mobile Android transport passed: copied wire, UTF-8, bounds, bindings, events, backpressure, wake, cleanup");
    return 0;
}
