/*
 * The `graphics` standard library package: one window, keyboard and mouse
 * input, and a small OpenGL 3.3 renderer for textured meshes, lines and a 2D
 * overlay. Minyar code reaches these functions through library/graphics.min.
 *
 * Mesh vertices are 32 bytes: position x, y, z, texture u, v and colour
 * r, g, b, each a little-endian Float32. The colour multiplies the texel, so
 * it also carries lighting. Texels with alpha below one half are discarded.
 */
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
#include <math.h>
#include "../minyar_native.h"

enum { VERTEX_FLOATS = 8, VERTEX_BYTES = VERTEX_FLOATS * 4, KEY_COUNT = GLFW_KEY_LAST + 1, BUTTON_COUNT = 8 };

typedef struct {
    GLuint array, buffer;
    GLsizei count;
    int used;
} Mesh;

typedef struct {
    float *values;
    size_t length, capacity;
} FloatBuffer;

static GLFWwindow *window;
static GLuint world_program, overlay_program, texture, white_texture;
static GLuint line_array, line_buffer, overlay_array, overlay_buffer;
static Mesh *meshes;
static size_t mesh_count, mesh_capacity;
static FloatBuffer lines, overlay;
enum { OVERLAY_FLOATS = 9 };
static float view_projection[16], camera[3], fog_color[3] = {0.6f, 0.75f, 0.95f}, fog_range[2] = {1e6f, 1e6f + 1};
static int texture_width = 1, texture_height = 1;
static unsigned char key_down[KEY_COUNT], key_pressed[KEY_COUNT];
static unsigned char button_down[BUTTON_COUNT], button_pressed[BUTTON_COUNT];
static double mouse_x, mouse_y, mouse_move_x, mouse_move_y, scroll_total;
static int mouse_known, frame_started;
static double start_time, previous_time, frame_seconds;
static int framebuffer_width, framebuffer_height;

static void use_world_program(void);

static void stop_graphics(const char *message) {
    minyar_native_stop(message);
}

static void require_window(void) {
    if (!window) stop_graphics("open a window with graphics.openWindow before drawing or reading input.");
}

/* ---------- small matrix helpers (column-major, like OpenGL) ---------- */

static void multiply(float *out, const float *a, const float *b) {
    float result[16];
    for (int column = 0; column < 4; column++)
        for (int row = 0; row < 4; row++) {
            float sum = 0;
            for (int k = 0; k < 4; k++) sum += a[k * 4 + row] * b[column * 4 + k];
            result[column * 4 + row] = sum;
        }
    memcpy(out, result, sizeof(result));
}

static void perspective(float *out, float field_of_view_degrees, float aspect, float near_plane, float far_plane) {
    float f = 1.0f / tanf(field_of_view_degrees * 0.5f * 3.14159265f / 180.0f);
    memset(out, 0, 16 * sizeof(float));
    out[0] = f / aspect;
    out[5] = f;
    out[10] = (far_plane + near_plane) / (near_plane - far_plane);
    out[11] = -1;
    out[14] = 2 * far_plane * near_plane / (near_plane - far_plane);
}

/* Yaw 0 looks toward -Z and positive yaw turns toward +X; positive pitch looks up. */
static void look(float *out, const float *eye, float yaw, float pitch) {
    float forward[3] = {sinf(yaw) * cosf(pitch), sinf(pitch), -cosf(yaw) * cosf(pitch)};
    float right[3] = {cosf(yaw), 0, sinf(yaw)};
    float up[3] = {
        right[1] * forward[2] - right[2] * forward[1],
        right[2] * forward[0] - right[0] * forward[2],
        right[0] * forward[1] - right[1] * forward[0],
    };
    float view[16] = {
        right[0], up[0], -forward[0], 0,
        right[1], up[1], -forward[1], 0,
        right[2], up[2], -forward[2], 0,
        -(right[0] * eye[0] + right[1] * eye[1] + right[2] * eye[2]),
        -(up[0] * eye[0] + up[1] * eye[1] + up[2] * eye[2]),
        forward[0] * eye[0] + forward[1] * eye[1] + forward[2] * eye[2],
        1,
    };
    memcpy(out, view, sizeof(view));
}

/* ---------- shaders ---------- */

static const char *world_vertex_source =
    "#version 330 core\n"
    "layout(location = 0) in vec3 position;\n"
    "layout(location = 1) in vec2 uv;\n"
    "layout(location = 2) in vec3 color;\n"
    "uniform mat4 viewProjection;\n"
    "uniform vec3 camera;\n"
    "out vec2 fragmentUv;\n"
    "out vec3 fragmentColor;\n"
    "out float fragmentDistance;\n"
    "void main() {\n"
    "    gl_Position = viewProjection * vec4(position, 1.0);\n"
    "    fragmentUv = uv;\n"
    "    fragmentColor = color;\n"
    "    fragmentDistance = length(position - camera);\n"
    "}\n";

static const char *world_fragment_source =
    "#version 330 core\n"
    "in vec2 fragmentUv;\n"
    "in vec3 fragmentColor;\n"
    "in float fragmentDistance;\n"
    "uniform sampler2D atlas;\n"
    "uniform vec3 fogColor;\n"
    "uniform vec2 fogRange;\n"
    "out vec4 result;\n"
    "void main() {\n"
    "    vec4 texel = texture(atlas, fragmentUv);\n"
    "    if (texel.a < 0.5) discard;\n"
    "    float fog = clamp((fragmentDistance - fogRange.x) / (fogRange.y - fogRange.x), 0.0, 1.0);\n"
    "    result = vec4(mix(texel.rgb * fragmentColor, fogColor, fog), 1.0);\n"
    "}\n";

static const char *overlay_vertex_source =
    "#version 330 core\n"
    "layout(location = 0) in vec2 position;\n"
    "layout(location = 1) in vec2 uv;\n"
    "layout(location = 2) in vec4 color;\n"
    "layout(location = 3) in float textured;\n"
    "uniform vec2 screen;\n"
    "out vec2 fragmentUv;\n"
    "out vec4 fragmentColor;\n"
    "out float fragmentTextured;\n"
    "void main() {\n"
    "    gl_Position = vec4(position.x / screen.x * 2.0 - 1.0, 1.0 - position.y / screen.y * 2.0, 0.0, 1.0);\n"
    "    fragmentUv = uv;\n"
    "    fragmentColor = color;\n"
    "    fragmentTextured = textured;\n"
    "}\n";

static const char *overlay_fragment_source =
    "#version 330 core\n"
    "in vec2 fragmentUv;\n"
    "in vec4 fragmentColor;\n"
    "in float fragmentTextured;\n"
    "uniform sampler2D atlas;\n"
    "out vec4 result;\n"
    "void main() {\n"
    "    vec4 texel = (fragmentTextured > 0.5 ? texture(atlas, fragmentUv) : vec4(1.0)) * fragmentColor;\n"
    "    if (texel.a < 0.01) discard;\n"
    "    result = texel;\n"
    "}\n";

static GLuint compile_shader(GLenum kind, const char *source) {
    GLuint shader = glCreateShader(kind);
    glShaderSource(shader, 1, &source, NULL);
    glCompileShader(shader);
    GLint ok = 0;
    glGetShaderiv(shader, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        char log[1024];
        glGetShaderInfoLog(shader, sizeof(log), NULL, log);
        fprintf(stderr, "%s\n", log);
        stop_graphics("the graphics shaders could not be compiled.");
    }
    return shader;
}

static GLuint link_program(const char *vertex_source, const char *fragment_source) {
    GLuint program = glCreateProgram();
    GLuint vertex = compile_shader(GL_VERTEX_SHADER, vertex_source);
    GLuint fragment = compile_shader(GL_FRAGMENT_SHADER, fragment_source);
    glAttachShader(program, vertex);
    glAttachShader(program, fragment);
    glLinkProgram(program);
    GLint ok = 0;
    glGetProgramiv(program, GL_LINK_STATUS, &ok);
    if (!ok) stop_graphics("the graphics shaders could not be linked.");
    glDeleteShader(vertex);
    glDeleteShader(fragment);
    return program;
}

static void world_layout(void) {
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, VERTEX_BYTES, (void *)0);
    glEnableVertexAttribArray(1);
    glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, VERTEX_BYTES, (void *)12);
    glEnableVertexAttribArray(2);
    glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, VERTEX_BYTES, (void *)20);
}

static GLuint make_texture(const unsigned char *pixels, int width, int height, int mipmaps) {
    GLuint name;
    glGenTextures(1, &name);
    glBindTexture(GL_TEXTURE_2D, name);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, pixels);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    if (mipmaps) {
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST_MIPMAP_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAX_LEVEL, 4);
        glGenerateMipmap(GL_TEXTURE_2D);
    } else {
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    }
    return name;
}

/* ---------- input callbacks ---------- */

static void on_key(GLFWwindow *source, int key, int scancode, int action, int mods) {
    (void)source; (void)scancode; (void)mods;
    if (key < 0 || key >= KEY_COUNT) return;
    if (action == GLFW_PRESS) { key_down[key] = 1; key_pressed[key] = 1; }
    if (action == GLFW_RELEASE) key_down[key] = 0;
}

static void on_button(GLFWwindow *source, int button, int action, int mods) {
    (void)source; (void)mods;
    if (button < 0 || button >= BUTTON_COUNT) return;
    if (action == GLFW_PRESS) { button_down[button] = 1; button_pressed[button] = 1; }
    if (action == GLFW_RELEASE) button_down[button] = 0;
}

static void on_cursor(GLFWwindow *source, double x, double y) {
    (void)source;
    if (mouse_known) {
        mouse_move_x += x - mouse_x;
        mouse_move_y += y - mouse_y;
    }
    mouse_x = x;
    mouse_y = y;
    mouse_known = 1;
}

static void on_scroll(GLFWwindow *source, double x, double y) {
    (void)source; (void)x;
    scroll_total += y;
}

static void on_error(int code, const char *description) {
    (void)code;
    fprintf(stderr, "graphics: %s\n", description);
}

/* ---------- window ---------- */

void minyar_graphics_openWindow(long long width, long long height, const MinyarText *title) {
    if (window) stop_graphics("only one window can be open at a time.");
    if (width < 1 || height < 1 || width > 16384 || height > 16384)
        stop_graphics("a window needs a width and height between 1 and 16384.");
    char name[256];
    minyar_native_text(title, name, sizeof(name));
    glfwSetErrorCallback(on_error);
    if (!glfwInit()) stop_graphics("the graphics system could not start.");
    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3);
    glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE);
    glfwWindowHint(GLFW_OPENGL_FORWARD_COMPAT, GLFW_TRUE);
    glfwWindowHint(GLFW_SAMPLES, 4);
    window = glfwCreateWindow((int)width, (int)height, name, NULL, NULL);
    if (!window) stop_graphics("the window could not be opened.");
    glfwMakeContextCurrent(window);
    glfwSwapInterval(1);
    glfwSetKeyCallback(window, on_key);
    glfwSetMouseButtonCallback(window, on_button);
    glfwSetCursorPosCallback(window, on_cursor);
    glfwSetScrollCallback(window, on_scroll);
    if (glfwRawMouseMotionSupported()) glfwSetInputMode(window, GLFW_RAW_MOUSE_MOTION, GLFW_TRUE);

    world_program = link_program(world_vertex_source, world_fragment_source);
    overlay_program = link_program(overlay_vertex_source, overlay_fragment_source);
    const unsigned char white[4] = {255, 255, 255, 255};
    white_texture = make_texture(white, 1, 1, 0);
    texture = white_texture;

    glGenVertexArrays(1, &line_array);
    glGenBuffers(1, &line_buffer);
    glBindVertexArray(line_array);
    glBindBuffer(GL_ARRAY_BUFFER, line_buffer);
    world_layout();

    glGenVertexArrays(1, &overlay_array);
    glGenBuffers(1, &overlay_buffer);
    glBindVertexArray(overlay_array);
    glBindBuffer(GL_ARRAY_BUFFER, overlay_buffer);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, OVERLAY_FLOATS * 4, (void *)0);
    glEnableVertexAttribArray(1);
    glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, OVERLAY_FLOATS * 4, (void *)8);
    glEnableVertexAttribArray(2);
    glVertexAttribPointer(2, 4, GL_FLOAT, GL_FALSE, OVERLAY_FLOATS * 4, (void *)16);
    glEnableVertexAttribArray(3);
    glVertexAttribPointer(3, 1, GL_FLOAT, GL_FALSE, OVERLAY_FLOATS * 4, (void *)32);
    glBindVertexArray(0);

    glEnable(GL_DEPTH_TEST);
    glEnable(GL_CULL_FACE);
    glCullFace(GL_BACK);
    glFrontFace(GL_CCW);
    start_time = previous_time = glfwGetTime();
    glfwGetFramebufferSize(window, &framebuffer_width, &framebuffer_height);
    float identity[16] = {1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1};
    memcpy(view_projection, identity, sizeof(identity));
}

static void push(FloatBuffer *buffer, const float *values, size_t count) {
    if (buffer->length + count > buffer->capacity) {
        size_t capacity = buffer->capacity ? buffer->capacity * 2 : 1024;
        while (capacity < buffer->length + count) capacity *= 2;
        float *grown = realloc(buffer->values, capacity * sizeof(float));
        if (!grown) stop_graphics("the computer ran out of memory.");
        buffer->values = grown;
        buffer->capacity = capacity;
    }
    memcpy(buffer->values + buffer->length, values, count * sizeof(float));
    buffer->length += count;
}

/* ---------- screenshots: an uncompressed PNG needs only CRC-32 and Adler-32 ---------- */

static char screenshot_path[1024];

static unsigned long png_crc(unsigned long crc, const unsigned char *data, size_t length) {
    static unsigned long table[256];
    static int ready;
    if (!ready) {
        for (unsigned long n = 0; n < 256; n++) {
            unsigned long c = n;
            for (int k = 0; k < 8; k++) c = c & 1 ? 0xedb88320UL ^ (c >> 1) : c >> 1;
            table[n] = c;
        }
        ready = 1;
    }
    for (size_t i = 0; i < length; i++) crc = table[(crc ^ data[i]) & 0xff] ^ (crc >> 8);
    return crc;
}

static void png_u32(unsigned char *out, unsigned long value) {
    out[0] = (unsigned char)(value >> 24); out[1] = (unsigned char)(value >> 16);
    out[2] = (unsigned char)(value >> 8); out[3] = (unsigned char)value;
}

static void png_chunk(FILE *file, const char *type, const unsigned char *data, size_t length) {
    unsigned char header[8];
    png_u32(header, (unsigned long)length);
    memcpy(header + 4, type, 4);
    fwrite(header, 1, 8, file);
    if (length) fwrite(data, 1, length, file);
    unsigned long crc = png_crc(0xffffffffUL, header + 4, 4);
    crc = png_crc(crc, data, length) ^ 0xffffffffUL;
    unsigned char tail[4];
    png_u32(tail, crc);
    fwrite(tail, 1, 4, file);
}

static void write_screenshot(void) {
    int width = framebuffer_width, height = framebuffer_height;
    size_t row = (size_t)width * 3 + 1, raw_length = row * (size_t)height;
    unsigned char *pixels = malloc((size_t)width * height * 4), *raw = malloc(raw_length);
    size_t blocks = raw_length / 65535 + 1;
    unsigned char *compressed = malloc(raw_length + blocks * 5 + 6);
    if (!pixels || !raw || !compressed) stop_graphics("the computer ran out of memory.");
    glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE, pixels);
    for (int y = 0; y < height; y++) {
        unsigned char *target = raw + row * (size_t)y;
        const unsigned char *source = pixels + (size_t)(height - 1 - y) * width * 4;
        target[0] = 0;
        for (int x = 0; x < width; x++) memcpy(target + 1 + x * 3, source + x * 4, 3);
    }
    size_t length = 0, offset = 0;
    unsigned long a = 1, b = 0;
    compressed[length++] = 0x78;
    compressed[length++] = 0x01;
    while (offset < raw_length || offset == 0) {
        size_t size = raw_length - offset > 65535 ? 65535 : raw_length - offset;
        compressed[length++] = offset + size == raw_length ? 1 : 0;
        compressed[length++] = (unsigned char)size;
        compressed[length++] = (unsigned char)(size >> 8);
        compressed[length++] = (unsigned char)~size;
        compressed[length++] = (unsigned char)(~size >> 8);
        memcpy(compressed + length, raw + offset, size);
        for (size_t i = 0; i < size; i++) { a = (a + raw[offset + i]) % 65521; b = (b + a) % 65521; }
        length += size;
        offset += size;
        if (!size) break;
    }
    png_u32(compressed + length, (b << 16) | a);
    length += 4;
    FILE *file = fopen(screenshot_path, "wb");
    if (!file) stop_graphics("the screenshot file could not be created.");
    static const unsigned char signature[8] = {137, 80, 78, 71, 13, 10, 26, 10};
    unsigned char header[13];
    png_u32(header, (unsigned long)width);
    png_u32(header + 4, (unsigned long)height);
    header[8] = 8; header[9] = 2; header[10] = 0; header[11] = 0; header[12] = 0;
    fwrite(signature, 1, 8, file);
    png_chunk(file, "IHDR", header, 13);
    png_chunk(file, "IDAT", compressed, length);
    png_chunk(file, "IEND", NULL, 0);
    fclose(file);
    free(pixels); free(raw); free(compressed);
    screenshot_path[0] = 0;
}

/* Save the next shown frame as a PNG file. */
void minyar_graphics_saveScreenshot(const MinyarText *path) {
    require_window();
    minyar_native_text(path, screenshot_path, sizeof(screenshot_path));
}

/* Draw the batched lines and overlay, then present the frame. */
static void finish_frame(void) {
    if (lines.length) {
        use_world_program();
        glBindTexture(GL_TEXTURE_2D, white_texture);
        glBindVertexArray(line_array);
        glBindBuffer(GL_ARRAY_BUFFER, line_buffer);
        glBufferData(GL_ARRAY_BUFFER, (GLsizeiptr)(lines.length * sizeof(float)), lines.values, GL_STREAM_DRAW);
        glDrawArrays(GL_LINES, 0, (GLsizei)(lines.length / VERTEX_FLOATS));
        lines.length = 0;
    }
    if (overlay.length) {
        glDisable(GL_DEPTH_TEST);
        glDisable(GL_CULL_FACE);
        glEnable(GL_BLEND);
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
        glUseProgram(overlay_program);
        int window_width, window_height;
        glfwGetWindowSize(window, &window_width, &window_height);
        glUniform2f(glGetUniformLocation(overlay_program, "screen"), (float)window_width, (float)window_height);
        glBindVertexArray(overlay_array);
        glBindBuffer(GL_ARRAY_BUFFER, overlay_buffer);
        glUniform1i(glGetUniformLocation(overlay_program, "atlas"), 0);
        glActiveTexture(GL_TEXTURE0);
        glBindTexture(GL_TEXTURE_2D, texture);
        glBufferData(GL_ARRAY_BUFFER, (GLsizeiptr)(overlay.length * sizeof(float)), overlay.values, GL_STREAM_DRAW);
        glDrawArrays(GL_TRIANGLES, 0, (GLsizei)(overlay.length / OVERLAY_FLOATS));
        overlay.length = 0;
        glDisable(GL_BLEND);
        glEnable(GL_DEPTH_TEST);
        glEnable(GL_CULL_FACE);
    }
    glBindVertexArray(0);
    if (screenshot_path[0]) write_screenshot();
    glfwSwapBuffers(window);
}

bool minyar_graphics_nextFrame(void) {
    require_window();
    if (frame_started) finish_frame();
    frame_started = 1;
    memset(key_pressed, 0, sizeof(key_pressed));
    memset(button_pressed, 0, sizeof(button_pressed));
    mouse_move_x = mouse_move_y = 0;
    scroll_total = 0;
    glfwPollEvents();
    double now = glfwGetTime();
    frame_seconds = now - previous_time;
    if (frame_seconds > 0.1) frame_seconds = 0.1;
    previous_time = now;
    glfwGetFramebufferSize(window, &framebuffer_width, &framebuffer_height);
    glViewport(0, 0, framebuffer_width, framebuffer_height);
    return !glfwWindowShouldClose(window);
}

void minyar_graphics_closeWindow(void) {
    require_window();
    glfwSetWindowShouldClose(window, GLFW_TRUE);
}

void minyar_graphics_setTitle(const MinyarText *title) {
    require_window();
    char name[256];
    minyar_native_text(title, name, sizeof(name));
    glfwSetWindowTitle(window, name);
}

long long minyar_graphics_width(void) { require_window(); return framebuffer_width; }
long long minyar_graphics_height(void) { require_window(); return framebuffer_height; }

long long minyar_graphics_windowWidth(void) {
    require_window();
    int width, height;
    glfwGetWindowSize(window, &width, &height);
    return width;
}

long long minyar_graphics_windowHeight(void) {
    require_window();
    int width, height;
    glfwGetWindowSize(window, &width, &height);
    return height;
}

double minyar_graphics_time(void) { require_window(); return glfwGetTime() - start_time; }
double minyar_graphics_frameTime(void) { require_window(); return frame_seconds; }

/* ---------- input ---------- */

static int valid_key(long long key) { return key >= 0 && key < KEY_COUNT; }
static int valid_button(long long button) { return button >= 0 && button < BUTTON_COUNT; }

bool minyar_graphics_keyDown(long long key) { return valid_key(key) && key_down[key]; }
bool minyar_graphics_keyPressed(long long key) { return valid_key(key) && key_pressed[key]; }
bool minyar_graphics_mouseDown(long long button) { return valid_button(button) && button_down[button]; }
bool minyar_graphics_mousePressed(long long button) { return valid_button(button) && button_pressed[button]; }
double minyar_graphics_mouseX(void) { return mouse_x; }
double minyar_graphics_mouseY(void) { return mouse_y; }
double minyar_graphics_mouseMoveX(void) { return mouse_move_x; }
double minyar_graphics_mouseMoveY(void) { return mouse_move_y; }
double minyar_graphics_scroll(void) { return scroll_total; }

void minyar_graphics_captureMouse(bool captured) {
    require_window();
    glfwSetInputMode(window, GLFW_CURSOR, captured ? GLFW_CURSOR_DISABLED : GLFW_CURSOR_NORMAL);
    mouse_known = 0;
    mouse_move_x = mouse_move_y = 0;
}

bool minyar_graphics_mouseCaptured(void) {
    require_window();
    return glfwGetInputMode(window, GLFW_CURSOR) == GLFW_CURSOR_DISABLED;
}

/* ---------- 3D drawing ---------- */

void minyar_graphics_clear(double red, double green, double blue) {
    require_window();
    glClearColor((float)red, (float)green, (float)blue, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
}

void minyar_graphics_setCamera(double x, double y, double z, double yaw, double pitch,
                               double field_of_view) {
    require_window();
    float projection[16], view[16];
    float aspect = framebuffer_height > 0 ? (float)framebuffer_width / (float)framebuffer_height : 1.0f;
    camera[0] = (float)x; camera[1] = (float)y; camera[2] = (float)z;
    perspective(projection, (float)field_of_view, aspect, 0.05f, 1000.0f);
    look(view, camera, (float)yaw, (float)pitch);
    multiply(view_projection, projection, view);
}

void minyar_graphics_setFog(double red, double green, double blue, double start, double end) {
    fog_color[0] = (float)red; fog_color[1] = (float)green; fog_color[2] = (float)blue;
    fog_range[0] = (float)start;
    fog_range[1] = end > start ? (float)end : (float)start + 1.0f;
}

void minyar_graphics_setTexture(const MinyarBytes *pixels, long long width, long long height) {
    require_window();
    if (width < 1 || height < 1 || width > 8192 || height > 8192 || pixels->byte_length != width * height * 4)
        stop_graphics("setTexture needs width * height * 4 bytes of RGBA pixels.");
    if (texture != white_texture) glDeleteTextures(1, &texture);
    texture = make_texture(pixels->bytes, (int)width, (int)height, 1);
    texture_width = (int)width;
    texture_height = (int)height;
}

static Mesh *find_mesh(long long handle) {
    if (handle < 1 || (size_t)handle > mesh_count || !meshes[handle - 1].used)
        stop_graphics("this mesh does not exist; create it with graphics.createMesh.");
    return &meshes[handle - 1];
}

long long minyar_graphics_createMesh(void) {
    require_window();
    size_t slot = 0;
    while (slot < mesh_count && meshes[slot].used) slot++;
    if (slot == mesh_count) {
        if (mesh_count == mesh_capacity) {
            size_t capacity = mesh_capacity ? mesh_capacity * 2 : 64;
            Mesh *grown = realloc(meshes, capacity * sizeof(Mesh));
            if (!grown) stop_graphics("the computer ran out of memory.");
            meshes = grown;
            mesh_capacity = capacity;
        }
        mesh_count++;
    }
    Mesh *mesh = &meshes[slot];
    memset(mesh, 0, sizeof(*mesh));
    mesh->used = 1;
    glGenVertexArrays(1, &mesh->array);
    glGenBuffers(1, &mesh->buffer);
    glBindVertexArray(mesh->array);
    glBindBuffer(GL_ARRAY_BUFFER, mesh->buffer);
    world_layout();
    glBindVertexArray(0);
    return (long long)slot + 1;
}

void minyar_graphics_updateMesh(long long handle, const MinyarBytes *vertices) {
    Mesh *mesh = find_mesh(handle);
    if (vertices->byte_length % VERTEX_BYTES)
        stop_graphics("mesh vertices are 32 bytes each: x, y, z, u, v, red, green, blue as Float32.");
    glBindBuffer(GL_ARRAY_BUFFER, mesh->buffer);
    glBufferData(GL_ARRAY_BUFFER, (GLsizeiptr)vertices->byte_length, vertices->bytes, GL_STATIC_DRAW);
    mesh->count = (GLsizei)(vertices->byte_length / VERTEX_BYTES);
}

static void use_world_program(void) {
    glUseProgram(world_program);
    glUniformMatrix4fv(glGetUniformLocation(world_program, "viewProjection"), 1, GL_FALSE, view_projection);
    glUniform3fv(glGetUniformLocation(world_program, "camera"), 1, camera);
    glUniform3fv(glGetUniformLocation(world_program, "fogColor"), 1, fog_color);
    glUniform2fv(glGetUniformLocation(world_program, "fogRange"), 1, fog_range);
    glUniform1i(glGetUniformLocation(world_program, "atlas"), 0);
    glActiveTexture(GL_TEXTURE0);
}

void minyar_graphics_drawMesh(long long handle) {
    Mesh *mesh = find_mesh(handle);
    if (!mesh->count) return;
    use_world_program();
    glBindTexture(GL_TEXTURE_2D, texture);
    glBindVertexArray(mesh->array);
    glDrawArrays(GL_TRIANGLES, 0, mesh->count);
    glBindVertexArray(0);
}

void minyar_graphics_deleteMesh(long long handle) {
    Mesh *mesh = find_mesh(handle);
    glDeleteBuffers(1, &mesh->buffer);
    glDeleteVertexArrays(1, &mesh->array);
    mesh->used = 0;
}

void minyar_graphics_drawLine(double x1, double y1, double z1, double x2, double y2, double z2,
                              double red, double green, double blue) {
    float line[16] = {
        (float)x1, (float)y1, (float)z1, 0.5f, 0.5f, (float)red, (float)green, (float)blue,
        (float)x2, (float)y2, (float)z2, 0.5f, 0.5f, (float)red, (float)green, (float)blue,
    };
    /* Lines are drawn with the camera in effect when the frame finishes. */
    push(&lines, line, 16);
}

/* ---------- 2D overlay, in window points with the origin at the top left ---------- */

static void overlay_quad(double x, double y, double width, double height,
                         double u1, double v1, double u2, double v2,
                         double red, double green, double blue, double alpha, float textured) {
    float x1 = (float)x, y1 = (float)y, x2 = (float)(x + width), y2 = (float)(y + height);
    float r = (float)red, g = (float)green, b = (float)blue, a = (float)alpha, t = textured;
    float quad[6 * OVERLAY_FLOATS] = {
        x1, y1, (float)u1, (float)v1, r, g, b, a, t,
        x1, y2, (float)u1, (float)v2, r, g, b, a, t,
        x2, y2, (float)u2, (float)v2, r, g, b, a, t,
        x1, y1, (float)u1, (float)v1, r, g, b, a, t,
        x2, y2, (float)u2, (float)v2, r, g, b, a, t,
        x2, y1, (float)u2, (float)v1, r, g, b, a, t,
    };
    push(&overlay, quad, 6 * OVERLAY_FLOATS);
}

void minyar_graphics_drawRectangle(double x, double y, double width, double height,
                                   double red, double green, double blue, double alpha) {
    overlay_quad(x, y, width, height, 0, 0, 1, 1, red, green, blue, alpha, 0);
}

void minyar_graphics_drawImage(double x, double y, double width, double height,
                               double u1, double v1, double u2, double v2) {
    overlay_quad(x, y, width, height, u1, v1, u2, v2, 1, 1, 1, 1, 1);
}
