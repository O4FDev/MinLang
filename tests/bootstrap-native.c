/* Distinct names ensure the stage0 test calls native wrappers rather than
 * one of its historical built-in io/process shortcuts. */
#include <stdbool.h>
typedef struct { const unsigned char *bytes; long long length; } TextPrefix;
extern void *minyar_native_copy_text(const unsigned char *, long long);
void *minyar_runtime_bootstrapNativeText(const TextPrefix *text) {
    return minyar_native_copy_text(text->bytes, text->length);
}
bool minyar_runtime_bootstrapNativeBoolean(bool value) { return !value; }
long long minyar_runtime_bootstrapNativeInteger(long long value) { return value; }
int minyar_runtime_bootstrapNativeCharacter(int value) { return value; }
static long long count;
void minyar_runtime_bootstrapNativeSet(long long value) { count = value; }
long long minyar_runtime_bootstrapNativeCount(void) { return count; }
