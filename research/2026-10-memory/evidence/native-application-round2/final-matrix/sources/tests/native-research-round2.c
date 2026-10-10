/* Real native renderer with bounded, typed CPU-side GL and allocation seams. */
#define _POSIX_C_SOURCE 200809L
#ifdef __APPLE__
#define _DARWIN_C_SOURCE
#endif
#include <assert.h>
#include <stdint.h>
#include <time.h>
#include <sys/resource.h>
#define GLFW_INCLUDE_NONE
#include <GLFW/glfw3.h>
#ifdef __APPLE__
#define GL_SILENCE_DEPRECATION
#include <OpenGL/gl3.h>
#else
#define GL_GLEXT_PROTOTYPES
#include <GL/gl.h>
#include <GL/glext.h>
#endif
#include "../runtime/minyar_native.h"

void minyar_bytes_clear(MinyarBytes *bytes);
void minyar_bytes_resize(MinyarBytes *bytes, long long length);
void minyar_rc_release(void *value);

enum { MAX_HANDLES = 256, MAX_NAMES = 512, MAX_VERTICES = 96 };
static size_t malloc_calls, failed_call, allocated_bytes, live_bytes, peak_bytes;
static size_t read_calls, open_calls, write_calls, close_calls;
static void *staging[3];
static size_t staging_sizes[3], staging_count;
static int print_exit_stats;
static size_t realloc_calls, registry_bytes, registry_peak;
static size_t uploads, draws, draw_calls, creates, deletes, updates, checks;
static size_t slot_checks;
static size_t dense_prefix_checks, mixed_iterations;

static uint64_t hash_bytes(const void *data, size_t length) {
    const unsigned char *bytes = data;
    uint64_t hash = UINT64_C(14695981039346656037);
    for (size_t i = 0; i < length; i++)
        hash = (hash ^ bytes[i]) * UINT64_C(1099511628211);
    return hash;
}

static void *staged_malloc(size_t size) {
    malloc_calls++;
    if (malloc_calls == failed_call)
        return NULL;
    void *pointer = malloc(size);
    assert(pointer && staging_count < 3);
    staging[staging_count] = pointer;
    staging_sizes[staging_count++] = size;
    allocated_bytes += size;
    live_bytes += size;
    if (live_bytes > peak_bytes)
        peak_bytes = live_bytes;
    return pointer;
}

static void staged_free(void *pointer) {
    for (size_t i = 0; i < staging_count; i++)
        if (staging[i] == pointer && pointer) {
            live_bytes -= staging_sizes[i];
            staging[i] = NULL;
            break;
        }
    free(pointer);
}

static void *registry_realloc(void *pointer, size_t size) {
    realloc_calls++;
    void *grown = realloc(pointer, size);
    assert(grown);
    registry_bytes = size;
    if (registry_bytes > registry_peak)
        registry_peak = registry_bytes;
    return grown;
}

static FILE *counted_open(const char *path, const char *mode) {
    open_calls++;
    return fopen(path, mode);
}
static size_t counted_write(const void *data, size_t size, size_t count, FILE *file) {
    write_calls++;
    return fwrite(data, size, count, file);
}
static int counted_close(FILE *file) {
    close_calls++;
    return fclose(file);
}
static void fake_pixels(GLint x, GLint y, GLsizei width, GLsizei height, GLenum format, GLenum type,
                        void *output) {
    assert(x == 0 && y == 0 && format == GL_RGBA && type == GL_UNSIGNED_BYTE);
    read_calls++;
    unsigned char *bytes = output;
    for (int row = 0; row < height; row++)
        for (int column = 0; column < width; column++) {
            size_t offset = ((size_t)row * width + column) * 4;
            bytes[offset] = (unsigned char)column;
            bytes[offset + 1] = (unsigned char)row;
            bytes[offset + 2] = (unsigned char)(column ^ row);
            bytes[offset + 3] = 255;
        }
}

typedef struct {
    int used;
    size_t length;
    uint64_t hash;
} Buffer;
static Buffer buffers[MAX_NAMES];
static unsigned char arrays[MAX_NAMES];
static GLuint array_buffer[MAX_NAMES], bound_array, bound_buffer;
static GLuint generated_array, generated_buffer;
static size_t buffer_live, array_live, object_peak;

static void gen_arrays(GLsizei count, GLuint *names) {
    assert(count == 1);
    GLuint name = 1;
    while (name < MAX_NAMES && arrays[name])
        name++;
    assert(name < MAX_NAMES);
    arrays[name] = 1;
    array_buffer[name] = 0;
    array_live++;
    generated_array = names[0] = name;
}
static void gen_buffers(GLsizei count, GLuint *names) {
    assert(count == 1);
    GLuint name = 1;
    while (name < MAX_NAMES && buffers[name].used)
        name++;
    assert(name < MAX_NAMES);
    buffers[name] = (Buffer){1, 0, 0};
    buffer_live++;
    generated_buffer = names[0] = name;
    if (array_live + buffer_live > object_peak)
        object_peak = array_live + buffer_live;
}
static void bind_array(GLuint name) {
    assert(name < MAX_NAMES && (!name || arrays[name]));
    bound_array = name;
}
static void bind_buffer(GLenum target, GLuint name) {
    assert(target == GL_ARRAY_BUFFER && name < MAX_NAMES && buffers[name].used);
    bound_buffer = name;
}
static void enable_attribute(GLuint index) {
    assert(index < 4 && bound_array);
}
static void attribute(GLuint index, GLint size, GLenum type, GLboolean normalized, GLsizei stride,
                      const void *pointer) {
    const GLint sizes[4] = {3, 2, 3, 2};
    const uintptr_t offsets[4] = {0, 12, 20, 32};
    assert(index < 4 && size == sizes[index] && type == GL_FLOAT && normalized == GL_FALSE);
    assert(stride == 40 && (uintptr_t)pointer == offsets[index]);
    assert(bound_array && bound_buffer);
    array_buffer[bound_array] = bound_buffer;
}
static void delete_buffers(GLsizei count, const GLuint *names) {
    assert(count == 1 && names[0] < MAX_NAMES && buffers[names[0]].used);
    buffers[names[0]].used = 0;
    buffer_live--;
}
static void delete_arrays(GLsizei count, const GLuint *names) {
    assert(count == 1 && names[0] < MAX_NAMES && arrays[names[0]]);
    arrays[names[0]] = 0;
    array_live--;
}
static void upload(GLenum target, GLsizeiptr size, const void *data, GLenum usage) {
    assert(target == GL_ARRAY_BUFFER && usage == GL_STATIC_DRAW && size >= 0);
    assert(bound_buffer && buffers[bound_buffer].used && (size == 0 || data));
    buffers[bound_buffer].length = (size_t)size;
    buffers[bound_buffer].hash = hash_bytes(data, (size_t)size);
    uploads++;
}
static GLsizei last_draw_count;
static GLuint last_draw_array;
static void draw(GLenum mode, GLint first, GLsizei count) {
    assert(mode == GL_TRIANGLES && first == 0 && count > 0 && bound_array);
    GLuint buffer = array_buffer[bound_array];
    assert(buffers[buffer].used && buffers[buffer].length == (size_t)count * 40);
    last_draw_count = count;
    last_draw_array = bound_array;
    draws++;
}
static void use_program(GLuint program) {
    (void)program;
}
static GLint uniform_location(GLuint program, const GLchar *name) {
    (void)program;
    assert(name);
    return 1;
}
static void uniform_matrix(GLint location, GLsizei count, GLboolean transpose,
                           const GLfloat *value) {
    assert(location == 1 && count == 1 && transpose == GL_FALSE && value);
}
static void uniform_vector(GLint location, GLsizei count, const GLfloat *value) {
    assert(location == 1 && count == 1 && value);
}
static void uniform_float(GLint location, GLfloat value) {
    assert(location == 1 && value >= 0);
}
static void uniform_int(GLint location, GLint value) {
    assert(location == 1 && value == 0);
}
static void active_texture(GLenum unit) {
    assert(unit == GL_TEXTURE0);
}
static void bind_texture(GLenum target, GLuint name) {
    assert(target == GL_TEXTURE_2D);
    (void)name;
}

#define malloc staged_malloc
#define free staged_free
#define realloc registry_realloc
#define fopen counted_open
#define fwrite counted_write
#define fclose counted_close
#define glReadPixels fake_pixels
#define glGenVertexArrays gen_arrays
#define glGenBuffers gen_buffers
#define glBindVertexArray bind_array
#define glBindBuffer bind_buffer
#define glEnableVertexAttribArray enable_attribute
#define glVertexAttribPointer attribute
#define glDeleteBuffers delete_buffers
#define glDeleteVertexArrays delete_arrays
#define glBufferData upload
#define glDrawArrays draw
#define glUseProgram use_program
#define glGetUniformLocation uniform_location
#define glUniformMatrix4fv uniform_matrix
#define glUniform3fv uniform_vector
#define glUniform2fv uniform_vector
#define glUniform1f uniform_float
#define glUniform1i uniform_int
#define glActiveTexture active_texture
#define glBindTexture bind_texture
#include "../runtime/native/graphics.c"
#undef malloc
#undef free
#undef realloc
#undef fopen
#undef fwrite
#undef fclose

static void png_stats(void) {
    if (print_exit_stats)
        printf("{\"malloc_calls\":%zu,\"failed_call\":%zu,\"allocated_bytes\":%zu,"
               "\"peak_bytes\":%zu,\"live_bytes_at_exit\":%zu,\"read_calls\":%zu,"
               "\"open_calls\":%zu,\"write_calls\":%zu,\"close_calls\":%zu,\"pending\":%d}\n",
               malloc_calls, failed_call, allocated_bytes, peak_bytes, live_bytes, read_calls,
               open_calls, write_calls, close_calls, screenshot_path[0] != 0);
}

typedef struct {
    int occupied;
    GLuint array, buffer;
    size_t length;
    uint64_t hash;
} ExpectedMesh;
static ExpectedMesh expected[MAX_HANDLES];
static MinyarBytes *borrowed;
static size_t active;
static uint64_t trace_hash = UINT64_C(14695981039346656037);

static void trace(unsigned char operation, size_t slot, size_t length) {
    unsigned char row[9] = {operation};
    for (size_t i = 0; i < 4; i++) {
        row[i + 1] = (unsigned char)(slot >> (8 * i));
        row[i + 5] = (unsigned char)(length >> (8 * i));
    }
    for (size_t i = 0; i < sizeof(row); i++)
        trace_hash = (trace_hash ^ row[i]) * UINT64_C(1099511628211);
}
static size_t create_expected(void) {
    size_t slot = 0;
    while (slot < MAX_HANDLES && expected[slot].occupied)
        slot++;
    assert(slot < MAX_HANDLES);
    assert(minyar_graphics_createMesh() == (long long)slot + 1);
    expected[slot] = (ExpectedMesh){1, generated_array, generated_buffer, 0, 0};
    creates++;
    active++;
    trace('C', slot, 0);
    return slot;
}
static void delete_expected(size_t slot) {
    assert(slot < MAX_HANDLES && expected[slot].occupied);
    minyar_graphics_deleteMesh((long long)slot + 1);
    assert(!arrays[expected[slot].array] && !buffers[expected[slot].buffer].used);
    expected[slot].occupied = 0;
    active--;
    deletes++;
    trace('D', slot, 0);
}
static void update_expected(size_t slot, size_t vertices, uint32_t salt) {
    assert(expected[slot].occupied && vertices <= MAX_VERTICES && vertices % 3 == 0);
    minyar_bytes_clear(borrowed);
    minyar_bytes_resize(borrowed, (long long)vertices * 40);
    unsigned char reference[MAX_VERTICES * 40];
    for (size_t i = 0; i < vertices * 10; i++) {
        /* Finite positive Float32, independent of renderer packing helpers. */
        uint32_t bits = UINT32_C(0x3f000000) | ((uint32_t)i * 97 + salt) % UINT32_C(0x800000);
        for (size_t byte = 0; byte < 4; byte++)
            reference[i * 4 + byte] = (unsigned char)(bits >> (8 * byte));
    }
    memcpy((void *)borrowed->bytes, reference, vertices * 40);
    size_t before = uploads;
    minyar_graphics_updateMesh((long long)slot + 1, borrowed);
    assert(uploads == before + 1 && bound_buffer == expected[slot].buffer);
    expected[slot].length = vertices * 40;
    expected[slot].hash = hash_bytes(reference, vertices * 40);
    assert(buffers[expected[slot].buffer].length == expected[slot].length);
    assert(buffers[expected[slot].buffer].hash == expected[slot].hash);
    /* GL seam retained only bytes' hash, never a borrowed runtime pointer. */
    minyar_bytes_clear(borrowed);
    updates++;
    trace('U', slot, vertices * 40);
}
static void draw_expected(size_t slot) {
    assert(expected[slot].occupied);
    size_t before = draws;
    minyar_graphics_drawMesh((long long)slot + 1);
    draw_calls++;
    if (expected[slot].length) {
        assert(draws == before + 1 && last_draw_array == expected[slot].array);
        assert(last_draw_count == (GLsizei)(expected[slot].length / 40));
        assert(buffers[expected[slot].buffer].hash == expected[slot].hash);
    } else {
        assert(draws == before);
    }
    trace('R', slot, expected[slot].length);
}
static void verify_all(void) {
    size_t count = 0;
    for (size_t slot = 0; slot < MAX_HANDLES; slot++) {
        assert((slot < mesh_count && meshes[slot].used) == expected[slot].occupied);
        if (expected[slot].occupied) {
            count++;
            assert(arrays[expected[slot].array] && buffers[expected[slot].buffer].used);
            assert(meshes[slot].count == (GLsizei)(expected[slot].length / 40));
        }
    }
    assert(count == active && array_live == active && buffer_live == active);
    assert(mesh_capacity <= MAX_HANDLES && registry_bytes == mesh_capacity * sizeof(Mesh));
    assert(mesh_next_slot <= mesh_count);
    for (size_t i = 0; i < mesh_next_slot; i++)
        assert(expected[i].occupied);
    checks++;
}

static uint32_t random_state;
static uint32_t next_random(void) {
    random_state = random_state * UINT32_C(1664525) + UINT32_C(1013904223);
    return random_state;
}
static void drain(void) {
    for (size_t i = 0; i < MAX_HANDLES; i++)
        if (expected[i].occupied)
            delete_expected(i);
    verify_all();
}
static void adversarial_batch(void) {
    for (size_t i = 0; i < 128; i++)
        create_expected();
    /* Restore the first slot, then force a scan across a dense prefix. */
    delete_expected(0);
    assert(create_expected() == 0);
    size_t before = slot_checks;
    assert(create_expected() == 128);
    dense_prefix_checks = slot_checks - before;
    assert(dense_prefix_checks == 127);
    for (size_t i = 1; i < 128; i += 2)
        delete_expected(i);
    for (size_t i = 1; i < 128; i += 2)
        assert(create_expected() == i);
    for (size_t i = 0; i < MAX_HANDLES; i++)
        if (!expected[i].occupied)
            create_expected();
    /* Nonmonotone holes span registry realloc boundaries. */
    const size_t holes[] = {255, 0, 64, 63, 128, 127, 1, 254};
    for (size_t i = 0; i < sizeof(holes) / sizeof(holes[0]); i++)
        delete_expected(holes[i]);
    for (size_t i = 0; i < sizeof(holes) / sizeof(holes[0]); i++)
        create_expected();
    for (size_t i = 0; i < MAX_HANDLES; i++) {
        update_expected(i, 3 * (i % 33), (uint32_t)i);
        draw_expected(i);
    }
    verify_all();
    drain();
}

static void mixed_batch(size_t iterations) {
    for (size_t step = 0; step < iterations; step++) {
        mixed_iterations++;
        uint32_t value = next_random();
        size_t slot = (value >> 16) % MAX_HANDLES;
        if (!expected[slot].occupied) {
            if (active < MAX_HANDLES)
                slot = create_expected();
        } else if ((value & 7) == 0) {
            delete_expected(slot);
        }
        if (expected[slot].occupied) {
            update_expected(slot, 3 * ((value >> 8) % 33), value & UINT32_C(0xffff));
            draw_expected(slot);
        }
        verify_all();
    }
}

static double monotonic_seconds(void) {
    struct timespec now;
    assert(clock_gettime(CLOCK_MONOTONIC, &now) == 0);
    return (double)now.tv_sec + (double)now.tv_nsec / 1e9;
}
static double cpu_seconds(void) {
    return (double)clock() / CLOCKS_PER_SEC;
}

static void mesh_stats(size_t batches, double wall, double cpu) {
    struct rusage usage;
    assert(getrusage(RUSAGE_SELF, &usage) == 0);
    long long rss = (long long)usage.ru_maxrss;
#ifndef __APPLE__
    rss *= 1024;
#endif
    printf("{\"batches\":%zu,\"creates\":%zu,\"deletes\":%zu,\"updates\":%zu,\"uploads\":%zu,"
           "\"draws\":%zu,\"draw_calls\":%zu,\"full_checks\":%zu,\"active\":%zu,\"array_live\":%zu,"
           "\"buffer_live\":%zu,"
           "\"object_peak\":%zu,\"capacity\":%zu,\"registry_bytes\":%zu,\"registry_peak\":%zu,"
           "\"realloc_calls\":%zu,\"slot_checks\":%zu,\"dense_prefix_checks\":%zu,"
           "\"mixed_iterations\":%zu,\"trace_hash\":\"%016llx\","
           "\"wall_seconds\":%.6f,\"cpu_seconds\":%.6f,\"peak_rss_bytes\":%lld}\n",
           batches, creates, deletes, updates, uploads, draws, draw_calls, checks, active,
           array_live, buffer_live, object_peak, mesh_capacity, registry_bytes, registry_peak,
           realloc_calls, slot_checks, dense_prefix_checks, mixed_iterations,
           (unsigned long long)trace_hash, wall, cpu, rss);
    fflush(stdout);
}

#ifndef NATIVE_RESEARCH_ROUND2_LIBRARY
int main(int argc, char **argv) {
    if (argc == 4 && (!strcmp(argv[1], "png-fault") || !strcmp(argv[1], "png-retry"))) {
        assert(strlen(argv[2]) < sizeof(screenshot_path));
        strcpy(screenshot_path, argv[2]);
        print_exit_stats = 1;
        assert(atexit(png_stats) == 0);
        if (!strcmp(argv[1], "png-fault")) {
            failed_call = (size_t)atoi(argv[3]);
            assert(failed_call >= 1 && failed_call <= 3);
            framebuffer_width = framebuffer_height = 8;
            write_screenshot();
            assert(!"PNG allocation failure must exit");
        }
        for (size_t repeat = 0; repeat < 6; repeat++) {
            framebuffer_width = repeat % 3 == 1 ? 8 : 0;
            framebuffer_height = repeat % 3 == 0 ? 8 : 0;
            write_screenshot();
            assert(!strcmp(screenshot_path, argv[2]));
            assert(!malloc_calls && !read_calls && !open_calls && !write_calls);
        }
        framebuffer_width = framebuffer_height = 8;
        write_screenshot();
        assert(!screenshot_path[0] && !live_bytes && read_calls == 1 && close_calls == 1);
        return 0;
    }
    if (argc == 5 && !strcmp(argv[1], "mesh")) {
        random_state = (uint32_t)strtoul(argv[2], NULL, 0);
        size_t iterations = (size_t)strtoul(argv[3], NULL, 0);
        double duration = strtod(argv[4], NULL);
        assert(iterations > 0 && iterations <= 65536 && duration >= 0 && duration <= 3600);
        window = (GLFWwindow *)(uintptr_t)1;
        borrowed = minyar_bytes_new(0);
        double start = monotonic_seconds(), cpu_start = cpu_seconds();
        size_t batches = 0;
        adversarial_batch();
        do {
            mixed_batch(iterations);
            drain();
            batches++;
            double wall = monotonic_seconds() - start, cpu = cpu_seconds() - cpu_start;
            if (!duration || wall >= duration) {
                mesh_stats(batches, wall, cpu);
                break;
            }
            if (batches % 16 == 0)
                mesh_stats(batches, wall, cpu);
            /* Active verified batches, paced to <=5% of one core; no timing claim. */
            double delay = cpu / 0.05 - wall;
            while (delay > 0 && monotonic_seconds() - start < duration) {
                double chunk = delay > 1 ? 1 : delay;
                struct timespec pause = {(time_t)chunk, (long)((chunk - (time_t)chunk) * 1e9)};
                nanosleep(&pause, NULL);
                delay = (cpu_seconds() - cpu_start) / 0.05 - (monotonic_seconds() - start);
            }
            assert(cpu <= 190 && registry_peak <= MAX_HANDLES * sizeof(Mesh));
            if (monotonic_seconds() - start >= duration) {
                mesh_stats(batches, monotonic_seconds() - start, cpu_seconds() - cpu_start);
                break;
            }
        } while (monotonic_seconds() - start <= duration + 2);
        minyar_rc_release(borrowed);
        free(meshes);
        registry_bytes = 0;
        return 0;
    }
    assert(!"unknown round2 fixture mode");
}
#endif

/* Generated application calls exercise borrowed upload/refill across real remeshes. */
long long minyar_native_round2_open(void) {
    window = (GLFWwindow *)(uintptr_t)1;
    return minyar_graphics_createMesh();
}
void minyar_native_round2_checkUpload(long long handle, const MinyarBytes *bytes) {
    size_t before = uploads;
    uint64_t expected_hash = hash_bytes(bytes->bytes, (size_t)bytes->byte_length);
    minyar_graphics_updateMesh(handle, bytes);
    assert(uploads == before + 1 && buffers[bound_buffer].length == (size_t)bytes->byte_length);
    assert(buffers[bound_buffer].hash == expected_hash);
    size_t before_draw = draws;
    minyar_graphics_drawMesh(handle);
    assert(draws == before_draw + (bytes->byte_length != 0));
}
void minyar_native_round2_finish(long long first, long long second) {
    minyar_graphics_deleteMesh(first);
    minyar_graphics_deleteMesh(second);
    assert(!array_live && !buffer_live);
    free(meshes);
    meshes = NULL;
    mesh_count = mesh_capacity = mesh_next_slot = 0;
}

static FILE *application_evidence;
void minyar_native_round2_startEvidence(const MinyarText *path) {
    char filename[1024];
    minyar_native_text(path, filename, sizeof(filename));
    application_evidence = fopen(filename, "wb");
    assert(application_evidence);
}
void minyar_native_round2_emit(const MinyarBytes *blocks, const MinyarBytes *metadata,
                               const MinyarBytes *solid, const MinyarBytes *water) {
    const MinyarBytes *parts[4] = {blocks, metadata, solid, water};
    for (size_t i = 0; i < 4; i++) {
        uint32_t length = (uint32_t)parts[i]->byte_length;
        unsigned char header[4];
        for (size_t byte = 0; byte < 4; byte++)
            header[byte] = (unsigned char)(length >> (byte * 8));
        assert(fwrite(header, 1, sizeof(header), application_evidence) == sizeof(header));
        assert(fwrite(parts[i]->bytes, 1, length, application_evidence) == length);
    }
    assert(fflush(application_evidence) == 0);
}
void minyar_native_round2_endEvidence(void) {
    assert(fclose(application_evidence) == 0);
    application_evidence = NULL;
}
