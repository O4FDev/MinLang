/* Compiler diagnostics use raw stderr and best-effort source reads. Neither
 * helper runs on a successful compiler path. Source files may be unavailable
 * when a tool checks an in-memory syntax tree; keep its location and message. */
void minyar_runtime_diagnosticWrite(const MinyarText *text) {
    (void)fwrite(text->bytes, 1, (size_t)text->byte_length, stderr);
    (void)fflush(stderr);
}

static long long minyar_source_error, minyar_source_line = 1, minyar_source_column = 1;

/* Never panic while trying to explain an earlier error. Validate UTF-8 before
 * crossing the native Text boundary; an invalid byte gets a visible marker. */
MinyarText *minyar_runtime_diagnosticReadSource(const MinyarText *path_text) {
    minyar_source_error = 0; minyar_source_line = minyar_source_column = 1;
    if (memchr(path_text->bytes, 0, (size_t)path_text->byte_length)) {
        minyar_source_error = 5; return copy_c_text("");
    }
    char *path = text_as_path(path_text);
    FILE *file = open_text_path(path, "rb");
#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_COMPILER_ARENA)
    rc_heap_deallocate(path);
#else
    free(path);
#endif
    if (!file) { minyar_source_error = 1; return copy_c_text(""); }
    if (fgetc(file) == EOF && ferror(file)) {
        fclose(file); minyar_source_error = 2; return copy_c_text("");
    }
#ifdef _WIN32
    __int64 length;
    int failed = _fseeki64(file, 0, SEEK_END) != 0 || (length = _ftelli64(file)) < 0 || _fseeki64(file, 0, SEEK_SET) != 0;
#else
    long length;
    int failed = fseek(file, 0, SEEK_END) != 0 || (length = ftell(file)) < 0 || fseek(file, 0, SEEK_SET) != 0;
#endif
    if (failed || (unsigned long long)length >= SIZE_MAX - 3) {
        fclose(file); minyar_source_error = 2; return copy_c_text("");
    }
    unsigned char *bytes = malloc((size_t)length + 3);
    if (!bytes) { fclose(file); minyar_source_error = 4; return copy_c_text(""); }
    size_t received = fread(bytes, 1, (size_t)length, file);
    int closed = fclose(file);
    if (received != (size_t)length || closed != 0) {
        free(bytes); minyar_source_error = 2; return copy_c_text("");
    }
    size_t position = 0;
    while (position < received) {
        unsigned first = bytes[position], width = 1;
        if (first >= 0x80) {
            if (first >= 0xc2 && first <= 0xdf) width = 2;
            else if (first >= 0xe0 && first <= 0xef) width = 3;
            else if (first >= 0xf0 && first <= 0xf4) width = 4;
            else width = 0;
            if (width && width > received - position) width = 0;
            if (width) {
                for (unsigned index = 1; index < width; index++)
                    if ((bytes[position + index] & 0xc0) != 0x80) { width = 0; break; }
            }
            if (width && ((first == 0xe0 && bytes[position + 1] < 0xa0) ||
                          (first == 0xed && bytes[position + 1] >= 0xa0) ||
                          (first == 0xf0 && bytes[position + 1] < 0x90) ||
                          (first == 0xf4 && bytes[position + 1] >= 0x90))) width = 0;
        }
        if (!width) {
            minyar_source_error = 3;
            bytes[position] = 0xef; bytes[position + 1] = 0xbf; bytes[position + 2] = 0xbd;
            received = position + 3; break;
        }
        if (first == '\n') { minyar_source_line++; minyar_source_column = 1; }
        else minyar_source_column++;
        position += width;
    }
    MinyarText *result = minyar_native_copy_text(bytes, (long long)received);
    free(bytes);
    return result;
}
long long minyar_runtime_diagnosticReadError(void) { return minyar_source_error; }
long long minyar_runtime_diagnosticReadLine(void) { return minyar_source_line; }
long long minyar_runtime_diagnosticReadColumn(void) { return minyar_source_column; }
MinyarText *minyar_runtime_diagnosticSource(const MinyarText *path) {
    return minyar_runtime_diagnosticReadSource(path);
}

/* Compiler options live in this process only. Normal programs never query
 * them; JSON selection adds no generated program instructions. */
static _Bool minyar_diagnostic_json;
void minyar_runtime_diagnosticSetJSON(_Bool enabled) { minyar_diagnostic_json = enabled; }
_Bool minyar_runtime_diagnosticJSON(void) { return minyar_diagnostic_json; }

/* Compilation configuration, never emitted into the compiled kernel. */
static long long minyar_compiler_kernel_target;
void minyar_runtime_compilerSetKernelTarget(long long target) { minyar_compiler_kernel_target = target; }
long long minyar_runtime_compilerKernelTarget(void) { return minyar_compiler_kernel_target; }

/* This private boundary is used by the compiler, never emitted into a user
 * program. Only an explicit diagnostic can jump here; runtime faults remain
 * fatal. Unwind ownership while callback stack storage is still live. */
/* Freestanding runtimes are always compiled with -ffreestanding and have no
 * setjmp.h; they get the fail-closed stubs below. Hosted tests that define
 * MINYAR_FREESTANDING (parallel-backend) keep the real boundary. */
#if defined(__STDC_HOSTED__) && __STDC_HOSTED__
#include <setjmp.h>
typedef struct MinyarDiagnosticBoundary {
    jmp_buf *jump;
    struct MinyarDiagnosticBoundary *previous;
    void *job;
    size_t depth, limit;
#ifndef MINYAR_COMPILER_ARENA
    RcFrame *frames;
    MinyarRcScope *scopes;
#endif
} MinyarDiagnosticBoundary;
static MinyarDiagnosticBoundary *minyar_diagnostic_boundary;
static long long minyar_diagnostic_errors;

_Bool minyar_compiler_try(void (*compile)(void *), void *job) {
    jmp_buf jump;
    MinyarDiagnosticBoundary boundary = {&jump, minyar_diagnostic_boundary, job,
                                        minyar_call_depth, minyar_depth_limit
#ifndef MINYAR_COMPILER_ARENA
                                        , rc_frames, rc_scopes
#endif
    };
    minyar_diagnostic_boundary = &boundary;
    int rejected = setjmp(jump);
    if (!rejected) compile(job);
    minyar_diagnostic_boundary = boundary.previous;
    return !rejected;
}

static MINYAR_NORETURN void minyar_diagnostic_jump(int reason) {
    MinyarDiagnosticBoundary *boundary = minyar_diagnostic_boundary;
    if (!boundary) exit(1);
#ifndef MINYAR_COMPILER_ARENA
    rc_scope_unwind(boundary->scopes);
#ifdef MINYAR_BOUNDED_RC
    if (!minyar_stack_bounds_ready) minyar_find_stack_bounds();
#endif
    while (rc_frames != boundary->frames) {
#ifdef MINYAR_BOUNDED_RC
        uintptr_t address = (uintptr_t)rc_frames;
        if (address >= minyar_stack_low && address < minyar_stack_high) {
            /* Match leave_stack_v1 without requiring that optional ABI in
             * an ordinary runtime object. The header cannot enter a queue. */
            RcFrame *frame = rc_frames;
            size_t written = frame->written_count;
            rc_frames = frame->previous;
            rc_bounded_retire_temporaries(frame);
            while (frame->written_count)
                rc_drop(rc_bounded_pending_local_value(frame, --frame->written_count));
            size_t work = written + minyar_rc_poll(MINYAR_RC_POLL_BUDGET - written);
#ifdef MINYAR_RC_TESTING
            rc_bounded_last_work = work;
#else
            (void)work;
#endif
        } else
#endif
            minyar_rc_leave();
    }
#endif
    minyar_call_depth = boundary->depth;
    minyar_depth_limit = boundary->limit;
    /* An omitted empty scope has no header for the unwind walk to leave. */
    minyar_rc_scope_leave_empty_v1();
    longjmp(*boundary->jump, reason);
}

_Bool minyar_runtime_diagnosticHasJob(void) { return minyar_diagnostic_boundary != NULL; }
void *minyar_runtime_diagnosticCurrentJob(void) {
    void *job = minyar_diagnostic_boundary ? minyar_diagnostic_boundary->job : NULL;
    minyar_rc_retain(job);
    return job;
}
long long minyar_runtime_diagnosticErrorCount(void) { return minyar_diagnostic_errors; }
MINYAR_NORETURN void minyar_runtime_diagnosticRaise(void) {
    minyar_diagnostic_errors++;
    if (minyar_diagnostic_errors >= 20) exit(1);
    minyar_diagnostic_jump(1);
}
MINYAR_NORETURN void minyar_runtime_diagnosticDiscard(void) { minyar_diagnostic_jump(2); }
#else
/* The private compiler-only recovery ABI needs hosted setjmp/longjmp.
 * Normal freestanding programs never call it; fail closed if requested. */
_Bool minyar_compiler_try(void (*compile)(void *), void *job) {
    (void)compile;
    (void)job;
    minyar_stop("compiler diagnostic recovery is unavailable in freestanding programs.");
}
_Bool minyar_runtime_diagnosticHasJob(void) { return 0; }
void *minyar_runtime_diagnosticCurrentJob(void) { return NULL; }
long long minyar_runtime_diagnosticErrorCount(void) { return 0; }
MINYAR_NORETURN void minyar_runtime_diagnosticRaise(void) { exit(1); }
MINYAR_NORETURN void minyar_runtime_diagnosticDiscard(void) { exit(1); }
#endif

/* Terminal cell ranges generated from Unicode 16.0.0 categories Mn/Me
 * and assigned East_Asian_Width W/F. Source coordinates remain scalars. */
static const unsigned minyar_diagnostic_zero[][2] = {
    {0x300,0x36f},
    {0x483,0x489},
    {0x591,0x5bd},
    {0x5bf,0x5bf},
    {0x5c1,0x5c2},
    {0x5c4,0x5c5},
    {0x5c7,0x5c7},
    {0x610,0x61a},
    {0x64b,0x65f},
    {0x670,0x670},
    {0x6d6,0x6dc},
    {0x6df,0x6e4},
    {0x6e7,0x6e8},
    {0x6ea,0x6ed},
    {0x711,0x711},
    {0x730,0x74a},
    {0x7a6,0x7b0},
    {0x7eb,0x7f3},
    {0x7fd,0x7fd},
    {0x816,0x819},
    {0x81b,0x823},
    {0x825,0x827},
    {0x829,0x82d},
    {0x859,0x85b},
    {0x897,0x89f},
    {0x8ca,0x8e1},
    {0x8e3,0x902},
    {0x93a,0x93a},
    {0x93c,0x93c},
    {0x941,0x948},
    {0x94d,0x94d},
    {0x951,0x957},
    {0x962,0x963},
    {0x981,0x981},
    {0x9bc,0x9bc},
    {0x9c1,0x9c4},
    {0x9cd,0x9cd},
    {0x9e2,0x9e3},
    {0x9fe,0x9fe},
    {0xa01,0xa02},
    {0xa3c,0xa3c},
    {0xa41,0xa42},
    {0xa47,0xa48},
    {0xa4b,0xa4d},
    {0xa51,0xa51},
    {0xa70,0xa71},
    {0xa75,0xa75},
    {0xa81,0xa82},
    {0xabc,0xabc},
    {0xac1,0xac5},
    {0xac7,0xac8},
    {0xacd,0xacd},
    {0xae2,0xae3},
    {0xafa,0xaff},
    {0xb01,0xb01},
    {0xb3c,0xb3c},
    {0xb3f,0xb3f},
    {0xb41,0xb44},
    {0xb4d,0xb4d},
    {0xb55,0xb56},
    {0xb62,0xb63},
    {0xb82,0xb82},
    {0xbc0,0xbc0},
    {0xbcd,0xbcd},
    {0xc00,0xc00},
    {0xc04,0xc04},
    {0xc3c,0xc3c},
    {0xc3e,0xc40},
    {0xc46,0xc48},
    {0xc4a,0xc4d},
    {0xc55,0xc56},
    {0xc62,0xc63},
    {0xc81,0xc81},
    {0xcbc,0xcbc},
    {0xcbf,0xcbf},
    {0xcc6,0xcc6},
    {0xccc,0xccd},
    {0xce2,0xce3},
    {0xd00,0xd01},
    {0xd3b,0xd3c},
    {0xd41,0xd44},
    {0xd4d,0xd4d},
    {0xd62,0xd63},
    {0xd81,0xd81},
    {0xdca,0xdca},
    {0xdd2,0xdd4},
    {0xdd6,0xdd6},
    {0xe31,0xe31},
    {0xe34,0xe3a},
    {0xe47,0xe4e},
    {0xeb1,0xeb1},
    {0xeb4,0xebc},
    {0xec8,0xece},
    {0xf18,0xf19},
    {0xf35,0xf35},
    {0xf37,0xf37},
    {0xf39,0xf39},
    {0xf71,0xf7e},
    {0xf80,0xf84},
    {0xf86,0xf87},
    {0xf8d,0xf97},
    {0xf99,0xfbc},
    {0xfc6,0xfc6},
    {0x102d,0x1030},
    {0x1032,0x1037},
    {0x1039,0x103a},
    {0x103d,0x103e},
    {0x1058,0x1059},
    {0x105e,0x1060},
    {0x1071,0x1074},
    {0x1082,0x1082},
    {0x1085,0x1086},
    {0x108d,0x108d},
    {0x109d,0x109d},
    {0x135d,0x135f},
    {0x1712,0x1714},
    {0x1732,0x1733},
    {0x1752,0x1753},
    {0x1772,0x1773},
    {0x17b4,0x17b5},
    {0x17b7,0x17bd},
    {0x17c6,0x17c6},
    {0x17c9,0x17d3},
    {0x17dd,0x17dd},
    {0x180b,0x180d},
    {0x180f,0x180f},
    {0x1885,0x1886},
    {0x18a9,0x18a9},
    {0x1920,0x1922},
    {0x1927,0x1928},
    {0x1932,0x1932},
    {0x1939,0x193b},
    {0x1a17,0x1a18},
    {0x1a1b,0x1a1b},
    {0x1a56,0x1a56},
    {0x1a58,0x1a5e},
    {0x1a60,0x1a60},
    {0x1a62,0x1a62},
    {0x1a65,0x1a6c},
    {0x1a73,0x1a7c},
    {0x1a7f,0x1a7f},
    {0x1ab0,0x1ace},
    {0x1b00,0x1b03},
    {0x1b34,0x1b34},
    {0x1b36,0x1b3a},
    {0x1b3c,0x1b3c},
    {0x1b42,0x1b42},
    {0x1b6b,0x1b73},
    {0x1b80,0x1b81},
    {0x1ba2,0x1ba5},
    {0x1ba8,0x1ba9},
    {0x1bab,0x1bad},
    {0x1be6,0x1be6},
    {0x1be8,0x1be9},
    {0x1bed,0x1bed},
    {0x1bef,0x1bf1},
    {0x1c2c,0x1c33},
    {0x1c36,0x1c37},
    {0x1cd0,0x1cd2},
    {0x1cd4,0x1ce0},
    {0x1ce2,0x1ce8},
    {0x1ced,0x1ced},
    {0x1cf4,0x1cf4},
    {0x1cf8,0x1cf9},
    {0x1dc0,0x1dff},
    {0x200c,0x200d},
    {0x20d0,0x20f0},
    {0x2cef,0x2cf1},
    {0x2d7f,0x2d7f},
    {0x2de0,0x2dff},
    {0x302a,0x302d},
    {0x3099,0x309a},
    {0xa66f,0xa672},
    {0xa674,0xa67d},
    {0xa69e,0xa69f},
    {0xa6f0,0xa6f1},
    {0xa802,0xa802},
    {0xa806,0xa806},
    {0xa80b,0xa80b},
    {0xa825,0xa826},
    {0xa82c,0xa82c},
    {0xa8c4,0xa8c5},
    {0xa8e0,0xa8f1},
    {0xa8ff,0xa8ff},
    {0xa926,0xa92d},
    {0xa947,0xa951},
    {0xa980,0xa982},
    {0xa9b3,0xa9b3},
    {0xa9b6,0xa9b9},
    {0xa9bc,0xa9bd},
    {0xa9e5,0xa9e5},
    {0xaa29,0xaa2e},
    {0xaa31,0xaa32},
    {0xaa35,0xaa36},
    {0xaa43,0xaa43},
    {0xaa4c,0xaa4c},
    {0xaa7c,0xaa7c},
    {0xaab0,0xaab0},
    {0xaab2,0xaab4},
    {0xaab7,0xaab8},
    {0xaabe,0xaabf},
    {0xaac1,0xaac1},
    {0xaaec,0xaaed},
    {0xaaf6,0xaaf6},
    {0xabe5,0xabe5},
    {0xabe8,0xabe8},
    {0xabed,0xabed},
    {0xfb1e,0xfb1e},
    {0xfe00,0xfe0f},
    {0xfe20,0xfe2f},
    {0x101fd,0x101fd},
    {0x102e0,0x102e0},
    {0x10376,0x1037a},
    {0x10a01,0x10a03},
    {0x10a05,0x10a06},
    {0x10a0c,0x10a0f},
    {0x10a38,0x10a3a},
    {0x10a3f,0x10a3f},
    {0x10ae5,0x10ae6},
    {0x10d24,0x10d27},
    {0x10d69,0x10d6d},
    {0x10eab,0x10eac},
    {0x10efc,0x10eff},
    {0x10f46,0x10f50},
    {0x10f82,0x10f85},
    {0x11001,0x11001},
    {0x11038,0x11046},
    {0x11070,0x11070},
    {0x11073,0x11074},
    {0x1107f,0x11081},
    {0x110b3,0x110b6},
    {0x110b9,0x110ba},
    {0x110c2,0x110c2},
    {0x11100,0x11102},
    {0x11127,0x1112b},
    {0x1112d,0x11134},
    {0x11173,0x11173},
    {0x11180,0x11181},
    {0x111b6,0x111be},
    {0x111c9,0x111cc},
    {0x111cf,0x111cf},
    {0x1122f,0x11231},
    {0x11234,0x11234},
    {0x11236,0x11237},
    {0x1123e,0x1123e},
    {0x11241,0x11241},
    {0x112df,0x112df},
    {0x112e3,0x112ea},
    {0x11300,0x11301},
    {0x1133b,0x1133c},
    {0x11340,0x11340},
    {0x11366,0x1136c},
    {0x11370,0x11374},
    {0x113bb,0x113c0},
    {0x113ce,0x113ce},
    {0x113d0,0x113d0},
    {0x113d2,0x113d2},
    {0x113e1,0x113e2},
    {0x11438,0x1143f},
    {0x11442,0x11444},
    {0x11446,0x11446},
    {0x1145e,0x1145e},
    {0x114b3,0x114b8},
    {0x114ba,0x114ba},
    {0x114bf,0x114c0},
    {0x114c2,0x114c3},
    {0x115b2,0x115b5},
    {0x115bc,0x115bd},
    {0x115bf,0x115c0},
    {0x115dc,0x115dd},
    {0x11633,0x1163a},
    {0x1163d,0x1163d},
    {0x1163f,0x11640},
    {0x116ab,0x116ab},
    {0x116ad,0x116ad},
    {0x116b0,0x116b5},
    {0x116b7,0x116b7},
    {0x1171d,0x1171d},
    {0x1171f,0x1171f},
    {0x11722,0x11725},
    {0x11727,0x1172b},
    {0x1182f,0x11837},
    {0x11839,0x1183a},
    {0x1193b,0x1193c},
    {0x1193e,0x1193e},
    {0x11943,0x11943},
    {0x119d4,0x119d7},
    {0x119da,0x119db},
    {0x119e0,0x119e0},
    {0x11a01,0x11a0a},
    {0x11a33,0x11a38},
    {0x11a3b,0x11a3e},
    {0x11a47,0x11a47},
    {0x11a51,0x11a56},
    {0x11a59,0x11a5b},
    {0x11a8a,0x11a96},
    {0x11a98,0x11a99},
    {0x11c30,0x11c36},
    {0x11c38,0x11c3d},
    {0x11c3f,0x11c3f},
    {0x11c92,0x11ca7},
    {0x11caa,0x11cb0},
    {0x11cb2,0x11cb3},
    {0x11cb5,0x11cb6},
    {0x11d31,0x11d36},
    {0x11d3a,0x11d3a},
    {0x11d3c,0x11d3d},
    {0x11d3f,0x11d45},
    {0x11d47,0x11d47},
    {0x11d90,0x11d91},
    {0x11d95,0x11d95},
    {0x11d97,0x11d97},
    {0x11ef3,0x11ef4},
    {0x11f00,0x11f01},
    {0x11f36,0x11f3a},
    {0x11f40,0x11f40},
    {0x11f42,0x11f42},
    {0x11f5a,0x11f5a},
    {0x13440,0x13440},
    {0x13447,0x13455},
    {0x1611e,0x16129},
    {0x1612d,0x1612f},
    {0x16af0,0x16af4},
    {0x16b30,0x16b36},
    {0x16f4f,0x16f4f},
    {0x16f8f,0x16f92},
    {0x16fe4,0x16fe4},
    {0x1bc9d,0x1bc9e},
    {0x1cf00,0x1cf2d},
    {0x1cf30,0x1cf46},
    {0x1d167,0x1d169},
    {0x1d17b,0x1d182},
    {0x1d185,0x1d18b},
    {0x1d1aa,0x1d1ad},
    {0x1d242,0x1d244},
    {0x1da00,0x1da36},
    {0x1da3b,0x1da6c},
    {0x1da75,0x1da75},
    {0x1da84,0x1da84},
    {0x1da9b,0x1da9f},
    {0x1daa1,0x1daaf},
    {0x1e000,0x1e006},
    {0x1e008,0x1e018},
    {0x1e01b,0x1e021},
    {0x1e023,0x1e024},
    {0x1e026,0x1e02a},
    {0x1e08f,0x1e08f},
    {0x1e130,0x1e136},
    {0x1e2ae,0x1e2ae},
    {0x1e2ec,0x1e2ef},
    {0x1e4ec,0x1e4ef},
    {0x1e5ee,0x1e5ef},
    {0x1e8d0,0x1e8d6},
    {0x1e944,0x1e94a},
    {0x1f3fb,0x1f3ff},
    {0xe0100,0xe01ef},
};
static const unsigned minyar_diagnostic_wide[][2] = {
    {0x1100,0x115f},
    {0x231a,0x231b},
    {0x2329,0x232a},
    {0x23e9,0x23ec},
    {0x23f0,0x23f0},
    {0x23f3,0x23f3},
    {0x25fd,0x25fe},
    {0x2614,0x2615},
    {0x2630,0x2637},
    {0x2648,0x2653},
    {0x267f,0x267f},
    {0x268a,0x268f},
    {0x2693,0x2693},
    {0x26a1,0x26a1},
    {0x26aa,0x26ab},
    {0x26bd,0x26be},
    {0x26c4,0x26c5},
    {0x26ce,0x26ce},
    {0x26d4,0x26d4},
    {0x26ea,0x26ea},
    {0x26f2,0x26f3},
    {0x26f5,0x26f5},
    {0x26fa,0x26fa},
    {0x26fd,0x26fd},
    {0x2705,0x2705},
    {0x270a,0x270b},
    {0x2728,0x2728},
    {0x274c,0x274c},
    {0x274e,0x274e},
    {0x2753,0x2755},
    {0x2757,0x2757},
    {0x2795,0x2797},
    {0x27b0,0x27b0},
    {0x27bf,0x27bf},
    {0x2b1b,0x2b1c},
    {0x2b50,0x2b50},
    {0x2b55,0x2b55},
    {0x2e80,0x2e99},
    {0x2e9b,0x2ef3},
    {0x2f00,0x2fd5},
    {0x2ff0,0x3029},
    {0x302e,0x303e},
    {0x3041,0x3096},
    {0x309b,0x30ff},
    {0x3105,0x312f},
    {0x3131,0x318e},
    {0x3190,0x31e5},
    {0x31ef,0x321e},
    {0x3220,0x3247},
    {0x3250,0xa48c},
    {0xa490,0xa4c6},
    {0xa960,0xa97c},
    {0xac00,0xd7a3},
    {0xf900,0xfa6d},
    {0xfa70,0xfad9},
    {0xfe10,0xfe19},
    {0xfe30,0xfe52},
    {0xfe54,0xfe66},
    {0xfe68,0xfe6b},
    {0xff01,0xff60},
    {0xffe0,0xffe6},
    {0x16fe0,0x16fe3},
    {0x16ff0,0x16ff1},
    {0x17000,0x187f7},
    {0x18800,0x18cd5},
    {0x18cff,0x18d08},
    {0x1aff0,0x1aff3},
    {0x1aff5,0x1affb},
    {0x1affd,0x1affe},
    {0x1b000,0x1b122},
    {0x1b132,0x1b132},
    {0x1b150,0x1b152},
    {0x1b155,0x1b155},
    {0x1b164,0x1b167},
    {0x1b170,0x1b2fb},
    {0x1d300,0x1d356},
    {0x1d360,0x1d376},
    {0x1f004,0x1f004},
    {0x1f0cf,0x1f0cf},
    {0x1f18e,0x1f18e},
    {0x1f191,0x1f19a},
    {0x1f200,0x1f202},
    {0x1f210,0x1f23b},
    {0x1f240,0x1f248},
    {0x1f250,0x1f251},
    {0x1f260,0x1f265},
    {0x1f300,0x1f320},
    {0x1f32d,0x1f335},
    {0x1f337,0x1f37c},
    {0x1f37e,0x1f393},
    {0x1f3a0,0x1f3ca},
    {0x1f3cf,0x1f3d3},
    {0x1f3e0,0x1f3f0},
    {0x1f3f4,0x1f3f4},
    {0x1f3f8,0x1f3fa},
    {0x1f400,0x1f43e},
    {0x1f440,0x1f440},
    {0x1f442,0x1f4fc},
    {0x1f4ff,0x1f53d},
    {0x1f54b,0x1f54e},
    {0x1f550,0x1f567},
    {0x1f57a,0x1f57a},
    {0x1f595,0x1f596},
    {0x1f5a4,0x1f5a4},
    {0x1f5fb,0x1f64f},
    {0x1f680,0x1f6c5},
    {0x1f6cc,0x1f6cc},
    {0x1f6d0,0x1f6d2},
    {0x1f6d5,0x1f6d7},
    {0x1f6dc,0x1f6df},
    {0x1f6eb,0x1f6ec},
    {0x1f6f4,0x1f6fc},
    {0x1f7e0,0x1f7eb},
    {0x1f7f0,0x1f7f0},
    {0x1f90c,0x1f93a},
    {0x1f93c,0x1f945},
    {0x1f947,0x1f9ff},
    {0x1fa70,0x1fa7c},
    {0x1fa80,0x1fa89},
    {0x1fa8f,0x1fac6},
    {0x1face,0x1fadc},
    {0x1fadf,0x1fae9},
    {0x1faf0,0x1faf8},
    {0x20000,0x2a6df},
    {0x2a700,0x2b739},
    {0x2b740,0x2b81d},
    {0x2b820,0x2cea1},
    {0x2ceb0,0x2ebe0},
    {0x2ebf0,0x2ee5d},
    {0x2f800,0x2fa1d},
    {0x30000,0x3134a},
    {0x31350,0x323af},
};

static int minyar_diagnostic_range(unsigned code, const unsigned (*ranges)[2], size_t count) {
    size_t first = 0, after = count;
    while (first < after) {
        size_t middle = first + (after - first) / 2;
        if (code < ranges[middle][0]) after = middle;
        else if (code > ranges[middle][1]) first = middle + 1;
        else return 1;
    }
    return 0;
}
long long minyar_runtime_diagnosticColumns(const MinyarText *text) {
    long long position = 0, columns = 0, previous_width = 0;
    unsigned previous = 0;
    int joined = 0, regional = 0;
    while (position < text->byte_length) {
        long long bytes;
        unsigned code = (unsigned)decode_character(text->bytes + position, text->byte_length - position, &bytes);
        position += bytes;
        if (code == 0x200d) { joined = 1; continue; }
        if (code == 0xfe0f && previous_width == 1 &&
            ((previous >= 0x2600 && previous <= 0x27bf) || previous == 0xa9 || previous == 0xae ||
             previous == 0x203c || previous == 0x2049 || previous == 0x2122 || previous == 0x2139 ||
             (previous >= 0x2194 && previous <= 0x21ff))) { columns++; previous_width = 2; continue; }
        if (minyar_diagnostic_range(code, minyar_diagnostic_zero, sizeof minyar_diagnostic_zero / sizeof *minyar_diagnostic_zero)) continue;
        long long width = minyar_diagnostic_range(code, minyar_diagnostic_wide, sizeof minyar_diagnostic_wide / sizeof *minyar_diagnostic_wide) ? 2 : 1;
        if (code >= 0x1f1e6 && code <= 0x1f1ff) {
            if (regional) { regional = 0; previous = code; continue; }
            regional = 1; width = 2;
        } else regional = 0;
        if (joined) { if (width > previous_width) columns += width - previous_width; joined = 0; }
        else columns += width;
        previous_width = width; previous = code;
    }
    return columns;
}
