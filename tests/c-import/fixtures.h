#ifndef MINYAR_C_IMPORT_FIXTURES_H
#define MINYAR_C_IMPORT_FIXTURES_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef struct LanternPoint {
    int32_t east;
    int32_t north;
} LanternPoint;

typedef struct LanternReading {
    uint8_t id;
    LanternPoint place;
    double glow;
    bool lit;
    uint8_t trail[3];
} LanternReading;

typedef struct __attribute__((packed)) LanternPacked {
    uint8_t tag;
    uint32_t value;
} LanternPacked;

typedef enum LanternSeason {
    LanternWinter = 3,
    LanternSpring = LanternWinter + 4,
    LanternAutumn = -2
} LanternSeason;

typedef uint32_t LanternCount;
typedef uint16_t LanternWidth;
typedef struct { int32_t lower; int32_t upper; } LanternSpan;
typedef struct LanternPath { LanternSpan span; LanternWidth width; } LanternPath;
typedef enum { LanternDim = 1, LanternBright = 9 } LanternTone;

#define LANTERN_SHIFTED ((unsigned int)(3 << 4) | 2U)
#define LANTERN_COMPOSED (LANTERN_SHIFTED + LanternWinter)
#define LANTERN_WINDOW ((int)sizeof(LanternPoint) + 3)
#define LANTERN_CHOICE ((sizeof(uint32_t) == 4) ? 42 : 0)
#ifndef LANTERN_THEME
#define LANTERN_THEME 2
#endif
#define LANTERN_FROM_FLAG (LANTERN_THEME + 1)
static const int LanternGolden = 21 * 2;

int32_t lantern_add(int32_t first, int32_t second);
int8_t lantern_narrow(int8_t value);
uint8_t lantern_byte(uint8_t value);
LanternCount lantern_count(LanternCount value);
uint64_t lantern_u64(uint64_t value);
bool lantern_boolean(bool value);
float lantern_scale(float value);
double lantern_warm(double value);
LanternSeason lantern_season(LanternSeason value);
void lantern_reset(void);
int32_t lantern_resets(void);
LanternReading lantern_measure(LanternPoint place, double glow);
LanternReading lantern_echo(LanternReading value);
LanternPacked lantern_packed(LanternPacked value);
LanternSpan lantern_span(LanternSpan value);
LanternPath lantern_path(LanternPath value);

/* Unselected unsafe declarations must not poison a safe import. */
typedef union LanternUnion { int32_t integer; double floating; } LanternUnion;
typedef struct LanternBitfield { unsigned int enabled : 1; } LanternBitfield;
typedef struct LanternFlexible { int32_t count; uint8_t data[]; } LanternFlexible;
typedef struct __attribute__((aligned(16))) LanternAligned { int64_t value; } LanternAligned;
typedef void (*LanternCallback)(int32_t value);
int32_t lantern_pointer(const int32_t *value);
int32_t lantern_callback(LanternCallback callback);
int32_t lantern_variadic(int32_t count, ...);
long double lantern_extended(long double value);
#define LANTERN_SQUARE(value) ((value) * (value))
#define LANTERN_TEXT "a warm window"
#define LANTERN_HALF 0.5
#define LANTERN_TOO_LARGE UINT64_C(18446744073709551615)

#endif
