// Typed test-only capture: no renderer body, GL library, window or retained Bytes pointer.
#include "../runtime/minyar_native.h"
#include <assert.h>
#include <math.h>

#include "native-research-round8-alias.h"

static long long creates, uploads, vertices, draws, lights, fogs;
static FILE *events;

static void event(const char *kind, long long handle, double a, double b, double c, double d,
                  double e) {
    if (!events) {
        events = fopen("events.txt", "w");
        assert(events);
    }
    assert(fprintf(events, "%s %lld %.17g %.17g %.17g %.17g %.17g\n", kind, handle, a, b, c, d, e) >
           0);
}

long long minyar_graphics_createMesh(void) {
    creates++;
    assert(creates <= 2);
    event("create", creates, 0, 0, 0, 0, 0);
    return creates;
}

void minyar_graphics_addVertex(MinyarBytes *bytes, double x, double y, double z, double u, double v,
                               double red, double green, double blue) {
    double values[8] = {x, y, z, u, v, red, green, blue};
    float packed[10];
    for (int i = 0; i < 8; i++) {
        assert(isfinite(values[i]));
        packed[i] = (float)values[i];
    }
    packed[8] = 1.0f;
    packed[9] = 0.0f;
    memcpy(minyar_bytes_extend(bytes, sizeof(packed)), packed, sizeof(packed));
    vertices++;
}

void minyar_graphics_updateMesh(long long handle, const MinyarBytes *bytes) {
    assert(handle == 1 || handle == 2);
    assert(bytes->byte_length >= 0 && bytes->byte_length % 120 == 0);
    assert(bytes->byte_length <= 60 * 60 * 36 * 40);
    char path[64];
    assert(snprintf(path, sizeof(path), "upload-%02lld-%lld.bin", uploads, handle) > 0);
    FILE *file = fopen(path, "wb");
    assert(file);
    assert(fwrite(bytes->bytes, 1, (size_t)bytes->byte_length, file) == (size_t)bytes->byte_length);
    assert(fclose(file) == 0);
    event("upload", handle, (double)bytes->byte_length, 0, 0, 0, 0);
    uploads++;
}

void minyar_graphics_setLight(double level) {
    assert(isfinite(level));
    event("light", 0, level, 0, 0, 0, 0);
    lights++;
}

void minyar_graphics_setFog(double red, double green, double blue, double start, double end) {
    event("fog", 0, red, green, blue, start, end);
    fogs++;
}

void minyar_graphics_drawMesh(long long handle) {
    assert(handle == 1 || handle == 2);
    event("draw", handle, 0, 0, 0, 0, 0);
    draws++;
}

double minyar_round8_periodic(long long px, long long py, long long cx, long long cy,
                              long long seed) {
    return round8_actual_tiled(px, py, cx, cy, seed);
}

void minyar_round8_finish(void) {
    assert(creates == 2 && uploads == 7 && draws == 4 && lights == 4 && fogs == 4);
    assert(events && fclose(events) == 0);
    events = NULL;
    printf("{\"creates\":%lld,\"uploads\":%lld,\"addVertex_calls\":%lld,"
           "\"draws\":%lld,\"lights\":%lld,\"fogs\":%lld}\n",
           creates, uploads, vertices, draws, lights, fogs);
}
