/* Portable host for the real mobile.min boundary. This deliberately has no
 * UIKit dependency: it drives the production callback-dispatch header. */
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include "../runtime/minyar_native.h"
#include "../runtime/native/mobile-callback.h"

enum { ROUNDS = 64, FRAMES = 7, NODES = 5, EVENTS = 5 };
typedef struct {
    long long parent, kind, spacing, padding;
    bool checked;
    char key[64], text[256];
} Node;
static Node snapshot[NODES];
static int rounds, frames, node_count, total_frames, getter_calls[3];
static bool building, running, in_event;
static char event_key[64], event_text[256];
static bool event_checked;

static void copy_text(char *output, size_t capacity, const MinyarText *text) {
    assert(text && text->byte_length >= 0 && (size_t)text->byte_length < capacity);
    memcpy(output, text->bytes, (size_t)text->byte_length);
    output[text->byte_length] = '\0';
}

static void check_snapshot(int frame) {
    static const char *names[FRAMES] = {
        "Hello 🌍", "Hello 🌍", "Hello 🌍", "Zoë 🌕", "Zoë 🌕", "Zoë 🌕", "Zoë 🌕!"
    };
    assert(frame >= 0 && frame < FRAMES && node_count == NODES);
    assert(snapshot[0].parent == 0 && snapshot[0].kind == 7);
    assert(snapshot[0].spacing == 12 && snapshot[0].padding == 16);
    assert(!snapshot[0].checked && !strcmp(snapshot[0].key, "") && !strcmp(snapshot[0].text, ""));
    for (int at = 1; at < NODES; at++) {
        assert(snapshot[at].parent == 1);
        assert(snapshot[at].spacing == 0 && snapshot[at].padding == 0);
    }
    char label[256];
    int count = frame == 6 ? 11 : (frame >= 2 ? 1 : 0);
    assert(snprintf(label, sizeof(label), "Count %d: %s", count, names[frame]) > 0);
    assert(snapshot[1].kind == 1 && !strcmp(snapshot[1].key, "state"));
    assert(!strcmp(snapshot[1].text, label) && !snapshot[1].checked);
    assert(snapshot[2].kind == 3 && !strcmp(snapshot[2].key, "add"));
    assert(!strcmp(snapshot[2].text, "Add") && !snapshot[2].checked);
    assert(snapshot[3].kind == 4 && !strcmp(snapshot[3].key, "name"));
    assert(!strcmp(snapshot[3].text, names[frame]) && !snapshot[3].checked);
    assert(snapshot[4].kind == 5 && !strcmp(snapshot[4].key, "active"));
    assert(!strcmp(snapshot[4].text, "Ready ✓") && snapshot[4].checked == (frame == 4));
}

void minyar_mobileios_begin(void) {
    assert(running && !building && frames < FRAMES);
    // The previous draw's temporary Minyar Text has already been released.
    if (frames) check_snapshot(frames - 1);
    memset(snapshot, 0, sizeof(snapshot));
    node_count = 0;
    building = true;
}

long long minyar_mobileios_node(long long parent, long long kind,
        const MinyarText *key, const MinyarText *text, bool checked,
        long long spacing, long long padding) {
    assert(building && node_count < NODES);
    Node *node = &snapshot[node_count++];
    node->parent = parent;
    node->kind = kind;
    node->spacing = spacing;
    node->padding = padding;
    node->checked = checked;
    copy_text(node->key, sizeof(node->key), key);
    copy_text(node->text, sizeof(node->text), text);
    return node_count;
}

void minyar_mobileios_end(void) {
    assert(building);
    check_snapshot(frames);
    building = false;
    frames++;
    total_frames++;
}

MinyarText *minyar_mobileios_eventKeyRaw(void) {
    assert(in_event);
    getter_calls[0]++;
    return minyar_native_copy_text((const unsigned char *)event_key, (long long)strlen(event_key));
}

MinyarText *minyar_mobileios_eventTextRaw(void) {
    assert(in_event);
    getter_calls[1]++;
    return minyar_native_copy_text((const unsigned char *)event_text, (long long)strlen(event_text));
}

bool minyar_mobileios_eventCheckedRaw(void) {
    assert(in_event);
    getter_calls[2]++;
    return event_checked;
}

static void event(void *session, long long kind, const char *key, const char *text, bool checked) {
    assert(!in_event && !building);
    assert(strlen(key) < sizeof(event_key) && strlen(text) < sizeof(event_text));
    strcpy(event_key, key);
    strcpy(event_text, text);
    event_checked = checked;
    in_event = true;
    int before = frames;
    minyar_mobile_dispatch(session, kind);
    assert(frames == before + 1 && !building);
    in_event = false;
    memset(event_key, 'x', sizeof(event_key));
    memset(event_text, 'x', sizeof(event_text));
    // Also inspect the copied native snapshot after dispatch has returned.
    check_snapshot(frames - 1);
}

void minyar_mobileios_runRaw(const MinyarText *title, void *session) {
    assert(!running && rounds < ROUNDS);
    char copied_title[128], expected_title[128];
    copy_text(copied_title, sizeof(copied_title), title);
    assert(snprintf(expected_title, sizeof(expected_title), "Mobile 🌕 %d", rounds) > 0);
    assert(!strcmp(copied_title, expected_title));
    running = true;
    frames = 0;
    minyar_mobile_dispatch(session, 0);
    assert(frames == 1 && !in_event);
    minyar_mobile_dispatch(session, 0);
    assert(frames == 2 && !in_event);
    event(session, 1, "add", "", false);
    event(session, 2, "name", "Zoë 🌕", false);
    event(session, 2, "active", "", true);
    event(session, 2, "active", "", false);
    event(session, 6, "name", "Zoë 🌕!", false);
    assert(frames == FRAMES);
    running = false;
    rounds++;
}

void mobile_bridge_assert_finished(void) {
    assert(!running && !building && !in_event);
    assert(rounds == ROUNDS && total_frames == ROUNDS * FRAMES);
    for (int at = 0; at < 3; at++) assert(getter_calls[at] == ROUNDS * EVENTS);
}
