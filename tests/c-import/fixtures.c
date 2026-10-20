#include "fixtures.h"

static int32_t resets;

int32_t lantern_add(int32_t first, int32_t second) { return first + second; }
int8_t lantern_narrow(int8_t value) { return value; }
uint8_t lantern_byte(uint8_t value) { return value; }
LanternCount lantern_count(LanternCount value) { return value; }
uint64_t lantern_u64(uint64_t value) { return value; }
bool lantern_boolean(bool value) { return !value; }
float lantern_scale(float value) { return value * 2.0f; }
double lantern_warm(double value) { return value + 0.25; }
LanternSeason lantern_season(LanternSeason value) { return value; }
void lantern_reset(void) { ++resets; }
int32_t lantern_resets(void) { return resets; }

LanternReading lantern_measure(LanternPoint place, double glow) {
    LanternReading result = {
        .id = 7,
        .place = place,
        .glow = glow,
        .lit = true,
        .trail = {1, 2, 3}
    };
    return result;
}

LanternReading lantern_echo(LanternReading value) {
    value.place.east += 1;
    value.glow += 0.5;
    value.trail[2] += 1;
    return value;
}

LanternPacked lantern_packed(LanternPacked value) {
    value.tag += 1;
    value.value += 2;
    return value;
}

LanternSpan lantern_span(LanternSpan value) {
    value.lower -= 1;
    value.upper += 1;
    return value;
}

LanternPath lantern_path(LanternPath value) {
    value.span.lower += value.width;
    return value;
}
