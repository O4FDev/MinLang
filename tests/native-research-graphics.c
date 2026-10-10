/* Headless CPU contracts for the real renderer, with typed GL and I/O seams. */
#include <assert.h>
#include <stdint.h>
#include <time.h>
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

void minyar_rc_release(void *value);
void minyar_bytes_clear(MinyarBytes *bytes);
void minyar_bytes_resize(MinyarBytes *bytes, long long length);

static size_t extension_calls, extension_bytes, write_calls, allocated_bytes;
static int io_fault;
static int allocation_fault;
static GLuint next_gl_name = 1;
static void *tracked_allocations[3];
static size_t tracked_sizes[3], tracked_count, live_bytes, peak_bytes;

static unsigned char *counted_extend(MinyarBytes *bytes, long long count) {
    extension_calls++;
    extension_bytes += (size_t)count;
    return minyar_bytes_extend(bytes, count);
}

static void *counted_malloc(size_t size) {
    allocated_bytes += size;
    void *pointer = malloc(size);
    assert(tracked_count < 3);
    tracked_allocations[tracked_count] = pointer;
    tracked_sizes[tracked_count++] = size;
    live_bytes += size;
    if (live_bytes > peak_bytes)
        peak_bytes = live_bytes;
    return pointer;
}

static void counted_free(void *pointer) {
    for (size_t i = 0; i < tracked_count; i++)
        if (tracked_allocations[i] == pointer) {
            live_bytes -= tracked_sizes[i];
            tracked_allocations[i] = NULL;
            break;
        }
    free(pointer);
}

static void *controlled_realloc(void *pointer, size_t size) {
    return allocation_fault ? NULL : realloc(pointer, size);
}

static size_t controlled_write(const void *data, size_t size, size_t count, FILE *file) {
    write_calls++;
    if ((io_fault == 1 && write_calls == 2) || (io_fault < 0 && write_calls == (size_t)-io_fault))
        return 0;
    return fwrite(data, size, count, file);
}

static int controlled_close(FILE *file) {
    int result = fclose(file);
    return io_fault == 2 ? EOF : result;
}

static void fake_read_pixels(GLint x, GLint y, GLsizei width, GLsizei height, GLenum format,
                             GLenum type, void *out) {
    (void)x;
    (void)y;
    assert(format == GL_RGBA && type == GL_UNSIGNED_BYTE);
    unsigned char *pixels = out;
    for (int row = 0; row < height; row++)
        for (int column = 0; column < width; column++) {
            size_t offset = ((size_t)row * width + column) * 4;
            pixels[offset] = (unsigned char)column;
            pixels[offset + 1] = (unsigned char)row;
            pixels[offset + 2] = (unsigned char)(column ^ row);
            pixels[offset + 3] = 255;
        }
}

static void fake_gen(GLsizei count, GLuint *names) {
    for (int i = 0; i < count; i++)
        names[i] = next_gl_name++;
}
static void fake_bind_array(GLuint name) {
    (void)name;
}
static void fake_bind_buffer(GLenum target, GLuint name) {
    (void)target;
    (void)name;
}
static void fake_enable(GLuint index) {
    (void)index;
}
static void fake_attribute(GLuint index, GLint size, GLenum type, GLboolean normalized,
                           GLsizei stride, const void *pointer) {
    (void)index;
    (void)size;
    (void)type;
    (void)normalized;
    (void)stride;
    (void)pointer;
}
static void fake_delete(GLsizei count, const GLuint *names) {
    (void)count;
    (void)names;
}

#ifndef NATIVE_RESEARCH_NO_VERTEX_COUNTS
#define minyar_bytes_extend counted_extend
#endif
#define malloc counted_malloc
#define free counted_free
#define realloc controlled_realloc
#define fwrite controlled_write
#define fclose controlled_close
#define glReadPixels fake_read_pixels
#define glGenVertexArrays fake_gen
#define glGenBuffers fake_gen
#define glBindVertexArray fake_bind_array
#define glBindBuffer fake_bind_buffer
#define glEnableVertexAttribArray fake_enable
#define glVertexAttribPointer fake_attribute
#define glDeleteBuffers fake_delete
#define glDeleteVertexArrays fake_delete
#include "../runtime/native/graphics.c"
#undef minyar_bytes_extend
#undef malloc
#undef free
#undef realloc
#undef fwrite
#undef fclose

static size_t lighting_visits, filtering_visits;
void minyar_native_research_begin(void) {
    extension_calls = extension_bytes = 0;
    lighting_visits = filtering_visits = 0;
}
long long minyar_native_research_extensions(void) {
    return (long long)extension_calls;
}
static clock_t phase_started;
void minyar_native_research_startCpu(void) {
    phase_started = clock();
}
double minyar_native_research_cpuSeconds(void) {
    return (double)(clock() - phase_started) / CLOCKS_PER_SEC;
}
void minyar_native_research_lightingVisit(void) {
    lighting_visits++;
}
void minyar_native_research_filteringVisit(void) {
    filtering_visits++;
}
long long minyar_native_research_lightingVisits(void) {
    return (long long)lighting_visits;
}
long long minyar_native_research_filteringVisits(void) {
    return (long long)filtering_visits;
}

#ifndef NATIVE_RESEARCH_LIBRARY_ONLY
static void check_vertex(void) {
    static const uint32_t expected[10] = {0x3f800000, 0xc0000000, 0x3f000000, 0x00000000,
                                          0x3f800000, 0x3e800000, 0x3f000000, 0x3f400000,
                                          0x3f800000, 0x00000000};
    MinyarBytes *bytes = minyar_bytes_new(0);
    minyar_graphics_addVertex(bytes, 1, -2, 0.5, 0, 1, 0.25, 0.5, 0.75);
    assert(bytes->byte_length == 40);
    for (size_t i = 0; i < 10; i++)
        for (size_t byte = 0; byte < 4; byte++)
            assert(bytes->bytes[i * 4 + byte] == (unsigned char)(expected[i] >> (8 * byte)));
    minyar_graphics_addLitVertex(bytes, 1, 2, 3, 4, 5, 6, 7, 8, 0.5, 0.25);
    assert(bytes->byte_length == 80);
    static const unsigned char light[8] = {0, 0, 0, 0x3f, 0, 0, 0x80, 0x3e};
    assert(!memcmp(bytes->bytes + 72, light, sizeof(light)));
    assert(extension_calls == 2 && extension_bytes == 80);
    /* clear preserves capacity; resize must still expose initialized bytes. */
    minyar_bytes_clear(bytes);
    minyar_graphics_addVertex(bytes, 1, -2, 0.5, 0, 1, 0.25, 0.5, 0.75);
    minyar_bytes_resize(bytes, 80);
    for (size_t i = 40; i < 80; i++)
        assert(bytes->bytes[i] == 0);
    minyar_rc_release(bytes);
}

static void check_helpers(void) {
    float a[16], b[16], result[16];
    for (int i = 0; i < 16; i++) {
        a[i] = (float)(i + 1);
        b[i] = (i / 4 == i % 4) ? 1 : 0;
    }
    multiply(result, a, b);
    assert(!memcmp(result, a, sizeof(a)));
    multiply(a, a, b);
    assert(!memcmp(result, a, sizeof(a)));
    FloatBuffer buffer = {0};
    float values[54];
    for (int i = 0; i < 54; i++)
        values[i] = (float)i;
    for (int i = 0; i < 100; i++)
        push(&buffer, values, 54);
    assert(buffer.length == 5400 && buffer.capacity == 8192);
    for (size_t i = 0; i < buffer.length; i++)
        assert(buffer.values[i] == (float)(i % 54));
    free(buffer.values);
    const unsigned char utf8[] = "a\xc3\xa9\xf0\x9f\x99\x82\nbc";
    MinyarText text = {utf8, sizeof(utf8) - 1, 6, NULL, NULL};
    assert(minyar_graphics_textWidth(&text, 2) == 34);
    on_key(NULL, -1, 0, GLFW_PRESS, 0);
    on_key(NULL, KEY_COUNT, 0, GLFW_PRESS, 0);
    on_key(NULL, GLFW_KEY_A, 0, GLFW_PRESS, 0);
    assert(minyar_graphics_keyDown(GLFW_KEY_A));
    on_key(NULL, GLFW_KEY_A, 0, GLFW_RELEASE, 0);
    assert(!minyar_graphics_keyDown(GLFW_KEY_A));
    assert(minyar_graphics_keyPressed(GLFW_KEY_A));
    assert(!minyar_graphics_keyDown(-1) && !minyar_graphics_keyDown(KEY_COUNT));
}

int main(int argc, char **argv) {
    if (argc == 3 && !strcmp(argv[1], "mesh-trap")) {
        if (!strcmp(argv[2], "window"))
            minyar_graphics_createMesh();
        window = (GLFWwindow *)(uintptr_t)1;
        if (!strcmp(argv[2], "alloc-initial")) {
            allocation_fault = 1;
            minyar_graphics_createMesh();
        }
        long long handle = minyar_graphics_createMesh();
        if (!strcmp(argv[2], "zero"))
            minyar_graphics_deleteMesh(0);
        if (!strcmp(argv[2], "negative"))
            minyar_graphics_deleteMesh(-1);
        if (!strcmp(argv[2], "future"))
            minyar_graphics_deleteMesh(2);
        if (!strcmp(argv[2], "alloc-full")) {
            for (size_t i = 1; i < 64; i++)
                minyar_graphics_createMesh();
            assert(mesh_count == mesh_capacity && mesh_capacity == 64);
            allocation_fault = 1;
            minyar_graphics_createMesh();
        }
        if (!strcmp(argv[2], "mesh-shape")) {
            MinyarBytes invalid = {NULL, 1, 1, NULL, NULL};
            minyar_graphics_updateMesh(handle, &invalid);
        }
        minyar_graphics_deleteMesh(handle);
        if (!strcmp(argv[2], "double-delete"))
            minyar_graphics_deleteMesh(handle);
        if (!strcmp(argv[2], "deleted"))
            find_mesh(handle);
        if (!strcmp(argv[2], "draw-deleted"))
            minyar_graphics_drawMesh(handle);
        if (!strcmp(argv[2], "update-deleted")) {
            MinyarBytes empty = {NULL, 0, 0, NULL, NULL};
            minyar_graphics_updateMesh(handle, &empty);
        }
        assert(!"expected native trap");
    }
    if (argc == 4 && !strcmp(argv[1], "mesh-bench")) {
        size_t count = (size_t)atoi(argv[2]);
        int repeats = atoi(argv[3]);
        assert(count > 0 && count <= 4096 && repeats > 0 && repeats <= 64);
        window = (GLFWwindow *)(uintptr_t)1;
        /* Warm registry storage. Timed batches reuse it through the public APIs. */
        for (size_t i = 0; i < count; i++)
            assert(minyar_graphics_createMesh() == (long long)i + 1);
        for (size_t i = 0; i < count; i++)
            minyar_graphics_deleteMesh((long long)i + 1);
        clock_t start = clock();
        size_t checksum = 0;
        for (int repeat = 0; repeat < repeats; repeat++) {
            for (size_t i = 0; i < count; i++) {
                long long handle = minyar_graphics_createMesh();
                assert(handle == (long long)i + 1);
                checksum += (size_t)handle;
            }
            for (size_t i = 0; i < count; i++)
                minyar_graphics_deleteMesh((long long)i + 1);
        }
        double cpu = (double)(clock() - start) / CLOCKS_PER_SEC;
        printf("{\"count\":%zu,\"repeats\":%d,\"checksum\":%zu,\"cpu_seconds\":%.9f}\n", count,
               repeats, checksum, cpu);
        free(meshes);
        return 0;
    }
    if (argc == 2 && !strcmp(argv[1], "mesh-model")) {
        unsigned char occupied[128] = {0};
        uint32_t state = 0x51f37;
        window = (GLFWwindow *)(uintptr_t)1;
        size_t operations = 0;
        for (int repeat = 0; repeat < 8192; repeat++) {
            state = state * 1664525u + 1013904223u;
            size_t first = 0;
            while (first < 128 && occupied[first])
                first++;
            if ((state & 3) && first < 128) {
                assert(minyar_graphics_createMesh() == (long long)first + 1);
                occupied[first] = 1;
                operations++;
            } else {
                size_t slot = (state >> 16) & 127;
                if (occupied[slot]) {
                    minyar_graphics_deleteMesh((long long)slot + 1);
                    occupied[slot] = 0;
                    operations++;
                }
            }
            for (size_t i = 0; i < 128; i++)
                assert((i < mesh_count && meshes[i].used) == occupied[i]);
        }
        printf("{\"seed\":%u,\"iterations\":8192,\"operations\":%zu}\n", 0x51f37, operations);
        free(meshes);
        return 0;
    }
    if (argc == 6 && !strcmp(argv[1], "png")) {
        framebuffer_width = atoi(argv[2]);
        framebuffer_height = atoi(argv[3]);
        assert(framebuffer_width >= 0 && framebuffer_width <= 1024);
        assert(framebuffer_height >= 0 && framebuffer_height <= 16384);
        assert(strlen(argv[4]) < sizeof(screenshot_path));
        strcpy(screenshot_path, argv[4]);
        io_fault = atoi(argv[5]);
        write_screenshot();
        printf("{\"write_calls\":%zu,\"allocated_bytes\":%zu,\"peak_bytes\":%zu,\"live_bytes\":%zu,"
               "\"pending\":%d}\n",
               write_calls, allocated_bytes, peak_bytes, live_bytes, screenshot_path[0] != 0);
        return 0;
    }
    if (argc == 3 && !strcmp(argv[1], "meshes")) {
        size_t count = (size_t)atoi(argv[2]);
        assert(count > 0 && count <= 16384);
        window = (GLFWwindow *)(uintptr_t)1;
        clock_t start = clock();
        for (size_t i = 0; i < count; i++)
            assert(minyar_graphics_createMesh() == (long long)i + 1);
        double cpu = (double)(clock() - start) / CLOCKS_PER_SEC;
#ifdef NATIVE_RESEARCH_SLOT_COUNTS
        size_t initial_checks = native_research_slot_checks;
        native_research_slot_checks = 0;
#endif
        for (size_t i = 0; i < count; i += 2)
            minyar_graphics_deleteMesh((long long)i + 1);
        for (size_t i = 0; i < count; i += 2)
            assert(minyar_graphics_createMesh() == (long long)i + 1);
        printf("{\"meshes\":%zu,\"capacity\":%zu,\"cpu_seconds\":%.9f", count, mesh_capacity, cpu);
#ifdef NATIVE_RESEARCH_SLOT_COUNTS
        printf(",\"initial_slot_checks\":%zu,\"reuse_slot_checks\":%zu", initial_checks,
               native_research_slot_checks);
#endif
        puts("}");
        free(meshes);
        return 0;
    }
    check_vertex();
    check_helpers();
    puts("vertex bytes, refill initialization, matrix alias, buffer growth, UTF8 width, input "
         "bounds");
    return 0;
}
#endif
