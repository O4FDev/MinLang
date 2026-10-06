/* Adapted round6 hidden/FBO/evidence/cleanup helpers; repository MIT LICENSE archived. */
/* One approved hidden context; real production shaders/layout/mesh operations.
 * The sole routing seam adds visibility hints immediately before GLFW creation.
 * A separate, single-sample fixture FBO supplies deterministic readback storage.
 */
#define GLFW_INCLUDE_NONE
#include <GLFW/glfw3.h>
#include <stddef.h>

static GLFWwindow *hidden_create(int width, int height, const char *title, GLFWmonitor *monitor,
                                 GLFWwindow *share);
#define glfwCreateWindow hidden_create
#include "../runtime/native/graphics.c"
#undef glfwCreateWindow

enum { FIXTURE_SIZE = 64 };
static GLuint fixture_framebuffer, fixture_color, fixture_depth;
static unsigned creation_calls;
static int completed;

static void fail(const char *message) {
    fprintf(stderr, "round9 fixture: %s\n", message);
    exit(90);
}

static void check_gl(const char *stage) {
    GLenum error = glGetError();
    if (error != GL_NO_ERROR) {
        fprintf(stderr, "round9 GL error at %s: 0x%x\n", stage, error);
        exit(90);
    }
}

static void json_string(const char *value) {
    putchar('"');
    for (const unsigned char *p = (const unsigned char *)value; *p; p++) {
        if (*p == '"' || *p == '\\')
            printf("\\%c", *p);
        else if (*p < 32 || *p > 126)
            printf("\\u%04x", *p);
        else
            putchar(*p);
    }
    putchar('"');
}

static GLFWwindow *hidden_create(int width, int height, const char *title, GLFWmonitor *monitor,
                                 GLFWwindow *share) {
    if (++creation_calls != 1 || width != FIXTURE_SIZE || height != FIXTURE_SIZE || monitor ||
        share)
        fail("creation is restricted to one unshared windowed 64x64 context");
    glfwWindowHint(GLFW_VISIBLE, GLFW_FALSE);
    glfwWindowHint(GLFW_FOCUSED, GLFW_FALSE);
    glfwWindowHint(GLFW_FOCUS_ON_SHOW, GLFW_FALSE);
    GLFWwindow *created = glfwCreateWindow(width, height, title, monitor, share);
    if (created && (glfwGetWindowAttrib(created, GLFW_VISIBLE) ||
                    glfwGetWindowAttrib(created, GLFW_FOCUSED))) {
        glfwDestroyWindow(created);
        fail("hidden/unfocused prerequisite unavailable");
    }
    return created;
}

/* Production closeWindow only marks should-close. This is test cleanup, and
 * does not establish production application teardown or driver-memory release.
 */
static void cleanup(void) {
    if (window) {
        glfwMakeContextCurrent(window);
        for (size_t i = 0; i < mesh_count; i++)
            if (meshes[i].used)
                minyar_graphics_deleteMesh((long long)i + 1);
        glBindFramebuffer(GL_FRAMEBUFFER, 0);
        glBindVertexArray(0);
        glBindBuffer(GL_ARRAY_BUFFER, 0);
        glUseProgram(0);
        glBindTexture(GL_TEXTURE_2D, 0);
        if (fixture_depth)
            glDeleteRenderbuffers(1, &fixture_depth);
        if (fixture_color)
            glDeleteRenderbuffers(1, &fixture_color);
        if (fixture_framebuffer)
            glDeleteFramebuffers(1, &fixture_framebuffer);
        if (texture && texture != white_texture)
            glDeleteTextures(1, &texture);
        if (white_texture)
            glDeleteTextures(1, &white_texture);
        if (line_buffer)
            glDeleteBuffers(1, &line_buffer);
        if (line_array)
            glDeleteVertexArrays(1, &line_array);
        if (overlay_buffer)
            glDeleteBuffers(1, &overlay_buffer);
        if (overlay_array)
            glDeleteVertexArrays(1, &overlay_array);
        if (world_program)
            glDeleteProgram(world_program);
        if (overlay_program)
            glDeleteProgram(overlay_program);
        GLenum error = glGetError();
        glfwMakeContextCurrent(NULL);
        glfwDestroyWindow(window);
        window = NULL;
        glfwTerminate();
        free(meshes);
        meshes = NULL;
        free(lines.values);
        lines.values = NULL;
        free(overlay.values);
        overlay.values = NULL;
        printf("{\"kind\":\"cleanup\",\"completed\":%s,\"gl_error\":%u,"
               "\"context_destroyed\":true,\"test_buffers_freed\":true}\n",
               completed ? "true" : "false", error);
        if (completed && error != GL_NO_ERROR)
            _Exit(90);
    } else {
        glfwTerminate();
        puts("{\"kind\":\"cleanup\",\"completed\":false,\"context_destroyed\":false}");
    }
}

static void program_evidence(GLuint program, const char *label) {
    GLint linked = 0;
    GLuint attached[2];
    GLsizei count = 0;
    char log[4096] = {0};
    glGetProgramiv(program, GL_LINK_STATUS, &linked);
    glGetProgramInfoLog(program, sizeof(log), NULL, log);
    glGetAttachedShaders(program, 2, &count, attached);
    printf("{\"kind\":\"program\",\"name\":");
    json_string(label);
    printf(",\"linked\":%d,\"link_log\":", linked);
    json_string(log);
    printf(",\"attached_shaders\":[");
    for (GLsizei i = 0; i < count; i++) {
        GLint compiled = 0, type = 0;
        glGetShaderiv(attached[i], GL_COMPILE_STATUS, &compiled);
        glGetShaderiv(attached[i], GL_SHADER_TYPE, &type);
        memset(log, 0, sizeof(log));
        glGetShaderInfoLog(attached[i], sizeof(log), NULL, log);
        if (i)
            putchar(',');
        printf("{\"type\":%d,\"compiled\":%d,\"log\":", type, compiled);
        json_string(log);
        putchar('}');
        if (!compiled)
            fail("retained shader compile status is false");
    }
    puts("]}");
    if (!linked || count != 2)
        fail("program did not link with two actual shaders");
    check_gl("program status and logs");
}

static void capabilities(void) {
    GLint major, minor, profile, flags, max_texture, max_renderbuffer, viewport[2], samples;
    glGetIntegerv(GL_MAJOR_VERSION, &major);
    glGetIntegerv(GL_MINOR_VERSION, &minor);
    glGetIntegerv(GL_CONTEXT_PROFILE_MASK, &profile);
    glGetIntegerv(GL_CONTEXT_FLAGS, &flags);
    glGetIntegerv(GL_MAX_TEXTURE_SIZE, &max_texture);
    glGetIntegerv(GL_MAX_RENDERBUFFER_SIZE, &max_renderbuffer);
    glGetIntegerv(GL_MAX_VIEWPORT_DIMS, viewport);
    glGetIntegerv(GL_SAMPLES, &samples);
    printf("{\"kind\":\"capabilities\",\"glfw\":");
    json_string(glfwGetVersionString());
    printf(",\"vendor\":");
    json_string((const char *)glGetString(GL_VENDOR));
    printf(",\"renderer\":");
    json_string((const char *)glGetString(GL_RENDERER));
    printf(",\"version\":");
    json_string((const char *)glGetString(GL_VERSION));
    printf(",\"glsl\":");
    json_string((const char *)glGetString(GL_SHADING_LANGUAGE_VERSION));
    printf(",\"major\":%d,\"minor\":%d,\"profile_mask\":%d,\"flags\":%d,"
           "\"max_texture\":%d,\"max_renderbuffer\":%d,\"max_viewport\":[%d,%d],"
           "\"default_samples\":%d,\"default_framebuffer\":[%d,%d],"
           "\"visible\":%d,\"focused\":%d,\"creation_calls\":%u}\n",
           major, minor, profile, flags, max_texture, max_renderbuffer, viewport[0], viewport[1],
           samples, framebuffer_width, framebuffer_height,
           glfwGetWindowAttrib(window, GLFW_VISIBLE), glfwGetWindowAttrib(window, GLFW_FOCUSED),
           creation_calls);
    if (major < 3 || (major == 3 && minor < 3) || !(profile & GL_CONTEXT_CORE_PROFILE_BIT))
        fail("actual context lacks requested 3.3 core prerequisite");
    check_gl("capability queries");
}

static void own_framebuffer(void) {
    glGenFramebuffers(1, &fixture_framebuffer);
    glBindFramebuffer(GL_FRAMEBUFFER, fixture_framebuffer);
    glGenRenderbuffers(1, &fixture_color);
    glBindRenderbuffer(GL_RENDERBUFFER, fixture_color);
    glRenderbufferStorage(GL_RENDERBUFFER, GL_RGBA8, FIXTURE_SIZE, FIXTURE_SIZE);
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, fixture_color);
    glGenRenderbuffers(1, &fixture_depth);
    glBindRenderbuffer(GL_RENDERBUFFER, fixture_depth);
    glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, FIXTURE_SIZE, FIXTURE_SIZE);
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, fixture_depth);
    glDrawBuffer(GL_COLOR_ATTACHMENT0);
    glReadBuffer(GL_COLOR_ATTACHMENT0);
    GLenum status = glCheckFramebufferStatus(GL_FRAMEBUFFER);
    if (status != GL_FRAMEBUFFER_COMPLETE)
        fail("own RGBA8/depth FBO is incomplete");
    GLint samples = -1;
    glGetIntegerv(GL_SAMPLES, &samples);
    if (samples != 0)
        fail("fixture FBO must be single sample");
    glViewport(0, 0, FIXTURE_SIZE, FIXTURE_SIZE);
    glDisable(GL_DITHER);
    glDisable(GL_FRAMEBUFFER_SRGB);
    glPixelStorei(GL_PACK_ALIGNMENT, 1);
    check_gl("own framebuffer setup");
    puts("{\"kind\":\"framebuffer\",\"complete\":true,\"width\":64,\"height\":64,"
         "\"color\":\"RGBA8\",\"depth\":\"DEPTH_COMPONENT24\",\"samples\":0,"
         "\"dither\":false,\"srgb\":false,\"pack_alignment\":1}");
}

static void state(const char *label) {
    GLint depth_func, cull_mode, front, source, destination, viewport[4], pack;
    GLboolean depth_write, mask[4];
    GLfloat range[2], clear_depth;
    glGetIntegerv(GL_DEPTH_FUNC, &depth_func);
    glGetIntegerv(GL_CULL_FACE_MODE, &cull_mode);
    glGetIntegerv(GL_FRONT_FACE, &front);
    glGetIntegerv(GL_BLEND_SRC_RGB, &source);
    glGetIntegerv(GL_BLEND_DST_RGB, &destination);
    glGetIntegerv(GL_VIEWPORT, viewport);
    glGetIntegerv(GL_PACK_ALIGNMENT, &pack);
    glGetBooleanv(GL_DEPTH_WRITEMASK, &depth_write);
    glGetBooleanv(GL_COLOR_WRITEMASK, mask);
    glGetFloatv(GL_DEPTH_RANGE, range);
    glGetFloatv(GL_DEPTH_CLEAR_VALUE, &clear_depth);
    printf("{\"kind\":\"state\",\"label\":\"%s\",\"depth_test\":%d,\"cull\":%d,"
           "\"blend\":%d,\"depth_write\":%d,\"depth_func\":%d,\"cull_mode\":%d,"
           "\"front\":%d,\"blend_src\":%d,\"blend_dst\":%d,\"viewport\":[%d,%d,%d,%d],"
           "\"color_mask\":[%d,%d,%d,%d],\"depth_range\":[%.8g,%.8g],\"clear_depth\":%.8g,"
           "\"scissor\":%d,\"stencil\":%d,\"dither\":%d,\"srgb\":%d,\"pack\":%d}\n",
           label, glIsEnabled(GL_DEPTH_TEST), glIsEnabled(GL_CULL_FACE), glIsEnabled(GL_BLEND),
           depth_write, depth_func, cull_mode, front, source, destination, viewport[0], viewport[1],
           viewport[2], viewport[3], mask[0], mask[1], mask[2], mask[3], range[0], range[1],
           clear_depth, glIsEnabled(GL_SCISSOR_TEST), glIsEnabled(GL_STENCIL_TEST),
           glIsEnabled(GL_DITHER), glIsEnabled(GL_FRAMEBUFFER_SRGB), pack);
    check_gl(label);
}

static void upload(long long mesh, const char *name) {
    unsigned char packed[120];
    FILE *file = fopen(name, "rb");
    if (!file)
        fail("input open failed");
    size_t got = fread(packed, 1, sizeof(packed), file);
    int tail = fgetc(file), error = ferror(file);
    if (fclose(file) || got != sizeof(packed) || tail != EOF || error)
        fail("input must be exactly 120 bytes");
    MinyarBytes vertices = {packed, sizeof(packed), sizeof(packed), NULL, NULL};
    minyar_graphics_updateMesh(mesh, &vertices);
    check_gl("public upload");
}

static void readback(const char *label) {
    unsigned char pixels[64 * 64 * 4];
    glReadPixels(0, 0, 64, 64, GL_RGBA, GL_UNSIGNED_BYTE, pixels);
    check_gl("readback");
    char name[128];
    snprintf(name, sizeof(name), "%s-rgba8.bin", label);
    FILE *file = fopen(name, "wb");
    if (!file)
        fail("readback open failed");
    size_t got = fwrite(pixels, 1, sizeof(pixels), file);
    if (fclose(file) || got != sizeof(pixels))
        fail("readback write failed");
    printf("{\"kind\":\"readback\",\"case\":\"%s\",\"bytes\":16384}\n", label);
}

int main(int argc, char **argv) {
    if (argc != 2 || strcmp(argv[1], "--bounded-hidden64"))
        return 64;
    setbuf(stdout, NULL);
    if (atexit(cleanup))
        fail("cleanup registration failed");
    glfwInitHint(GLFW_COCOA_MENUBAR, GLFW_FALSE);
    glfwInitHint(GLFW_COCOA_CHDIR_RESOURCES, GLFW_FALSE);
    const unsigned char title_bytes[] = "Round9 hidden fixture";
    MinyarText title = {title_bytes, sizeof(title_bytes) - 1, sizeof(title_bytes) - 1, NULL, NULL};
    minyar_graphics_openWindow(64, 64, &title);
    check_gl("initialization");
    capabilities();
    program_evidence(world_program, "world");
    program_evidence(overlay_program, "overlay");
    state("production-defaults");
    own_framebuffer();
    glEnable(GL_DEPTH_TEST);
    glDepthFunc(GL_LESS);
    glDepthMask(GL_TRUE);
    glClearDepth(1);
    glDepthRange(0, 1);
    glEnable(GL_CULL_FACE);
    glCullFace(GL_BACK);
    glFrontFace(GL_CCW);
    glDisable(GL_BLEND);
    glBlendFunc(GL_ONE, GL_ZERO);
    glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);
    glDisable(GL_SCISSOR_TEST);
    glDisable(GL_STENCIL_TEST);
    glDisable(GL_RASTERIZER_DISCARD);
    glDisable(GL_POLYGON_OFFSET_FILL);
    glPolygonMode(GL_FRONT_AND_BACK, GL_FILL);
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
    state("explicit-fbo-defaults");
    const unsigned char atlas[] = {192, 64, 32, 127, 32, 160, 224, 128};
    MinyarBytes texels = {atlas, sizeof(atlas), sizeof(atlas), NULL, NULL};
    minyar_graphics_setTexture(&texels, 2, 1);
    minyar_graphics_setLight(1);
    minyar_graphics_setFog(0, 0, 0, 100, 101);
    long long a = minyar_graphics_createMesh();
    long long b = minyar_graphics_createMesh();
    long long c = minyar_graphics_createMesh();

    minyar_graphics_clear(.125, .25, .5);
    upload(a, "near-half.bin");
    upload(b, "far-full.bin");
    minyar_graphics_drawMesh(a);
    minyar_graphics_drawMesh(b);
    readback("depth-order");

    minyar_graphics_clear(.125, .25, .5);
    upload(a, "near-discard.bin");
    minyar_graphics_drawMesh(a);
    minyar_graphics_drawMesh(b);
    readback("alpha-discard-depth");

    minyar_graphics_clear(.125, .25, .5);
    upload(a, "near-full.bin");
    upload(b, "far-half.bin");
    minyar_graphics_drawMesh(a);
    minyar_graphics_drawMesh(b);
    readback("alpha128-survives");

    minyar_graphics_clear(.125, .25, .5);
    upload(a, "near-reversed.bin");
    upload(c, "middle-full.bin");
    minyar_graphics_drawMesh(b);
    minyar_graphics_drawTranslucentMesh(a, .5);
    state("after-translucent");
    readback("translucent-blend");
    minyar_graphics_drawMesh(c);
    minyar_graphics_drawMesh(b);
    state("after-later-opaque");
    readback("translucent-no-depth-write");

    minyar_graphics_clear(.125, .25, .5);
    upload(a, "camera-replacement.bin");
    minyar_graphics_setCamera(1, 0, 0, 0, 0, 90);
    minyar_graphics_drawMesh(a);
    state("after-camera-replacement");
    readback("camera-replacement");

    minyar_graphics_deleteMesh(a);
    minyar_graphics_deleteMesh(b);
    minyar_graphics_deleteMesh(c);
    check_gl("final deletion");
    if (glfwGetWindowAttrib(window, GLFW_VISIBLE) || glfwGetWindowAttrib(window, GLFW_FOCUSED))
        fail("visibility changed");
    puts("{\"kind\":\"render\",\"public_mesh_creates\":3,\"public_mesh_uploads\":8,"
         "\"public_mesh_draws\":10,\"translucent_draws\":1,\"public_mesh_deletes\":3,"
         "\"readbacks\":6,\"events_polled\":0,\"swaps\":0,\"gl_error\":0}");
    completed = 1;
    return 0;
}
