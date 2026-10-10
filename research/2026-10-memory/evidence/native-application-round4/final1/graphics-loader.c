/* Loader contract: no window/display is needed. Uses real platform GL types. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#define GLFW_INCLUDE_NONE
#include <GLFW/glfw3.h>
#ifdef __APPLE__
#define GL_SILENCE_DEPRECATION
#include <OpenGL/gl3.h>
#else
#include <GL/gl.h>
#include <GL/glext.h>
#endif
#define MINYAR_GRAPHICS_LOAD_GL 1
#include "/Users/luke/Projects/Minyar-Lang/runtime/native/opengl-functions.h"

static int resolved;
static const char *missing;
static void placeholder(void) {}
GLFWglproc glfwGetProcAddress(const char *name) {
    resolved++;
    return missing && !strcmp(name, missing) ? NULL : placeholder;
}
int main(void) {
    assert(minyar_load_opengl() == NULL);
    assert(resolved == 29);
    missing = "glCreateShader";
    const char *failure = minyar_load_opengl();
    assert(failure && !strcmp(failure, missing));
    missing = NULL;
    assert(minyar_load_opengl() == NULL);
    puts("OpenGL loader success, missing entry, and retry verified");
    return 0;
}
