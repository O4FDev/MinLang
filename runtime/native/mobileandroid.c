#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif
#include <jni.h>
#include <stdatomic.h>
#include "../minyar_native.h"
#include "mobile-callback.h"
#include "mobile-android-transport.h"

/* The Java-created worker owns ordinary Minyar main for its entire lifetime.
 * These JNI local references remain valid during that one blocking nativeRun
 * invocation and are used only by that same worker. No Activity ref is saved. */
static MaTransport android_transport = MA_TRANSPORT_INITIALIZER;
static atomic_flag android_entry_started = ATOMIC_FLAG_INIT;
static pthread_t android_worker;
static JNIEnv *android_environment;
static jclass android_host;
static jmethodID android_request_frame;
static bool android_failed, android_running, android_building;
static void *android_session;
static unsigned char *android_title;
static size_t android_title_length, android_node_count, android_pending_bytes;
static MaNode android_nodes[MA_MAX_NODES];
static MaEvent android_event;

int minyar_mobile_entry(void);

static void android_check_worker(void) {
    if (!android_environment || !pthread_equal(pthread_self(), android_worker))
        minyar_native_stop("Android managed calls belong to the creating worker.");
}
static void android_clear_nodes(void) {
    for (size_t index = 0; index < android_node_count; index++) {
        free((void *)android_nodes[index].key);
        free((void *)android_nodes[index].text);
    }
    android_node_count = 0;
}
static unsigned char *android_copy_text(MinyarText *text, size_t limit) {
    if (!text || text->byte_length < 0 || (unsigned long long)text->byte_length > limit ||
        !ma_utf8(text->bytes, (size_t)text->byte_length)) minyar_native_stop("Android text exceeds its limit or is not valid nonzero UTF-8.");
    size_t length = (size_t)text->byte_length;
    unsigned char *copy = malloc(length ? length : 1);
    if (!copy) minyar_native_stop("Android text allocation failed.");
    if (length) memcpy(copy, text->bytes, length);
    return copy;
}
static void android_notify(void) {
    if (android_failed) return;
    /* No transport mutex is held and this call returns no local reference.
     * Preserve a Java exception for nativeRun's eventual return; stop dispatch
     * and unwind ordinary Minyar frames rather than continuing JNI calls. */
    (*android_environment)->CallStaticVoidMethod(android_environment, android_host, android_request_frame);
    if ((*android_environment)->ExceptionCheck(android_environment)) {
        android_failed = true;
        ma_close(&android_transport);
    }
}

void minyar_mobileandroid_begin(void) {
    android_check_worker();
    if (!android_session || android_building) minyar_native_stop("Android begin needs one active snapshot.");
    android_building = true;
    android_clear_nodes();
    android_pending_bytes = 28 + android_title_length;
}
long long minyar_mobileandroid_node(long long parent, long long kind, MinyarText *key, MinyarText *text,
                                   bool checked, long long spacing, long long padding) {
    android_check_worker();
    if (!android_building || android_node_count >= MA_MAX_NODES || parent < 0 || (unsigned long long)parent > android_node_count ||
        kind < 1 || kind > 7 || spacing < 0 || spacing > 256 || padding < 0 || padding > 256 ||
        !key || !text || key->byte_length < 0 || key->byte_length > MA_MAX_KEY ||
        text->byte_length < 0 || text->byte_length > MA_MAX_TEXT)
        minyar_native_stop("invalid Android view descriptor.");
    size_t addition = 28 + (size_t)key->byte_length + (size_t)text->byte_length;
    if (addition > MA_MAX_SNAPSHOT - android_pending_bytes) minyar_native_stop("Android snapshot exceeds one MiB.");
    android_pending_bytes += addition;
    MaNode *node = &android_nodes[android_node_count];
    *node = (MaNode){.parent = (uint32_t)parent, .kind = (uint32_t)kind, .spacing = (uint32_t)spacing,
                     .padding = (uint32_t)padding, .checked = checked};
    node->key = android_copy_text(key, MA_MAX_KEY);
    node->text = android_copy_text(text, MA_MAX_TEXT);
    node->key_length = (size_t)key->byte_length;
    node->text_length = (size_t)text->byte_length;
    return (long long)++android_node_count;
}
void minyar_mobileandroid_end(void) {
    android_check_worker();
    if (!android_session || !android_building) minyar_native_stop("Android end needs an active snapshot.");
    MaSnapshot *snapshot = ma_snapshot_build(android_title, android_title_length, android_nodes, android_node_count);
    android_clear_nodes();
    android_building = false;
    if (!snapshot) minyar_native_stop("invalid or oversized Android view snapshot.");
    if (!ma_publish(&android_transport, snapshot)) {
        ma_snapshot_free(snapshot);
        /* Test shutdown may race a callback's final redraw. Stop gracefully
         * after that callback returns; never unwind it from Java's thread. */
        android_failed = true;
        return;
    }
    android_notify();
}
MinyarText *minyar_mobileandroid_eventKeyRaw(void) {
    android_check_worker();
    return minyar_native_copy_text(android_event.bytes, (long long)android_event.key_length);
}
MinyarText *minyar_mobileandroid_eventTextRaw(void) {
    android_check_worker();
    return minyar_native_copy_text(android_event.bytes ? android_event.bytes + android_event.key_length : NULL,
                                   (long long)android_event.text_length);
}
bool minyar_mobileandroid_eventCheckedRaw(void) { android_check_worker(); return android_event.checked; }

void minyar_mobileandroid_runRaw(MinyarText *title, void *session) {
    android_check_worker();
    if (android_running || !session) minyar_native_stop("Android run may start only once.");
    android_running = true;
    android_session = session; /* Borrowed for the entire blocking call. */
    android_title = android_copy_text(title, MA_MAX_TEXT);
    android_title_length = (size_t)title->byte_length;
    minyar_mobile_dispatch(android_session, 0);
    while (!android_failed) {
        long long wait = minyar_callbackruntime_serviceWait(-1);
        int ready = ma_take(&android_transport, wait, &android_event);
        if (ready < 0) break;
        if (!ready) continue;
        bool matches = ma_apply_event(&android_transport, &android_event);
        if (matches) minyar_mobile_dispatch(android_session, (long long)android_event.kind);
        else android_notify(); /* Publish watermark even for a stale descriptor. */
        ma_event_free(&android_event);
    }
    android_clear_nodes();
    android_building = false;
    free(android_title); android_title = NULL; android_title_length = 0;
    android_session = NULL;
}

JNIEXPORT void JNICALL Java_org_minyar_hello_MinyarActivity_nativeRun(JNIEnv *environment, jclass host) {
    if (atomic_flag_test_and_set_explicit(&android_entry_started, memory_order_relaxed)) return;
    android_worker = pthread_self();
    android_environment = environment;
    android_host = host;
    android_request_frame = (*environment)->GetStaticMethodID(environment, host, "requestFrame", "()V");
    if (!android_request_frame) { ma_close(&android_transport); android_environment = NULL; android_host = NULL; return; }
    (void)minyar_mobile_entry();
#ifdef MINYAR_ANDROID_TESTING
    extern void mobile_android_assert_cleanup(void);
    mobile_android_assert_cleanup(); /* Same worker, after ordinary main unwinds. */
#endif
    ma_close(&android_transport);
    /* Process-lifetime transport mutex remains valid for late UI JNI calls.
     * Release C-owned queue/frame payloads under its lock after main unwinds. */
    pthread_mutex_lock(&android_transport.mutex);
    for (size_t index = 0; index < MA_MAX_EVENTS; index++) ma_event_free(&android_transport.events[index]);
    ma_snapshot_free(android_transport.snapshot); android_transport.snapshot = NULL;
    android_transport.count = android_transport.event_bytes = 0;
    pthread_mutex_unlock(&android_transport.mutex);
    android_environment = NULL; android_host = NULL; android_request_frame = NULL;
}
#ifdef MINYAR_ANDROID_TESTING
JNIEXPORT void JNICALL Java_org_minyar_hello_MinyarActivity_nativeStop(JNIEnv *environment, jclass host) {
    (void)environment; (void)host;
    ma_close(&android_transport); /* Wake worker; only the worker unwinds Minyar. */
}
#endif
JNIEXPORT jlong JNICALL Java_org_minyar_hello_MinyarActivity_nativeAttach(JNIEnv *environment, jclass host) {
    (void)environment; (void)host;
    return (jlong)ma_attach(&android_transport);
}
JNIEXPORT void JNICALL Java_org_minyar_hello_MinyarActivity_nativeDetach(JNIEnv *environment, jclass host, jlong token) {
    (void)environment; (void)host;
    if (token > 0) ma_detach(&android_transport, (uint64_t)token);
}
JNIEXPORT jbyteArray JNICALL Java_org_minyar_hello_MinyarActivity_nativeSnapshot(JNIEnv *environment, jclass host, jlong token) {
    (void)host;
    if (token <= 0) return NULL;
    size_t length;
    unsigned char *copy = ma_snapshot_copy(&android_transport, (uint64_t)token, &length);
    if (!copy) return NULL;
    jbyteArray result = (*environment)->NewByteArray(environment, (jsize)length);
    if (result) (*environment)->SetByteArrayRegion(environment, result, 0, (jsize)length, (const jbyte *)copy);
    free(copy);
    /* On any allocation/copy exception return immediately to Java. */
    if ((*environment)->ExceptionCheck(environment)) return NULL;
    return result;
}
JNIEXPORT jlong JNICALL Java_org_minyar_hello_MinyarActivity_nativeEvent(JNIEnv *environment, jclass host, jlong token,
                                                                      jint node, jint kind, jbyteArray key, jbyteArray text, jboolean checked) {
    (void)host;
    if (token <= 0 || node <= 0 || !key || !text || (kind != 1 && kind != 2 && kind != 6)) return 0;
    jsize key_length = (*environment)->GetArrayLength(environment, key);
    jsize text_length = (*environment)->GetArrayLength(environment, text);
    if (key_length <= 0 || key_length > (jsize)MA_MAX_KEY || text_length < 0 || text_length > (jsize)MA_MAX_TEXT) return 0;
    unsigned char key_bytes[MA_MAX_KEY], text_bytes[MA_MAX_TEXT];
    (*environment)->GetByteArrayRegion(environment, key, 0, key_length, (jbyte *)key_bytes);
    if ((*environment)->ExceptionCheck(environment)) return 0;
    if (text_length) (*environment)->GetByteArrayRegion(environment, text, 0, text_length, (jbyte *)text_bytes);
    if ((*environment)->ExceptionCheck(environment)) return 0;
    return (jlong)ma_post(&android_transport, (uint64_t)token, (uint32_t)node, (uint32_t)kind,
                         key_bytes, (size_t)key_length, text_bytes, (size_t)text_length, checked == JNI_TRUE);
}
