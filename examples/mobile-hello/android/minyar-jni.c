#include <jni.h>

/* This is a one-shot startup boundary, not a way to share managed objects
 * between Java threads. The example computes a small answer synchronously. */
int minyar_mobile_entry(void);

JNIEXPORT jint JNICALL Java_org_minyar_hello_MainActivity_answer(JNIEnv *environment, jobject activity) {
    (void)environment;
    (void)activity;
    return (jint)minyar_mobile_entry();
}
