/* Windows opengl32 exports OpenGL 1.1. Resolve the renderer's newer API
 * after GLFW makes its OpenGL 3.3 context current. Other hosts can force this
 * path for display-independent tests of real API pointer types. */
#ifndef MINYAR_OPENGL_FUNCTIONS_H
#define MINYAR_OPENGL_FUNCTIONS_H
#if defined(_WIN32) || defined(MINYAR_GRAPHICS_LOAD_GL)
static PFNGLACTIVETEXTUREPROC minyar_glActiveTexture;
#define glActiveTexture minyar_glActiveTexture
static PFNGLATTACHSHADERPROC minyar_glAttachShader;
#define glAttachShader minyar_glAttachShader
static PFNGLBINDBUFFERPROC minyar_glBindBuffer;
#define glBindBuffer minyar_glBindBuffer
static PFNGLBINDVERTEXARRAYPROC minyar_glBindVertexArray;
#define glBindVertexArray minyar_glBindVertexArray
static PFNGLBUFFERDATAPROC minyar_glBufferData;
#define glBufferData minyar_glBufferData
static PFNGLCOMPILESHADERPROC minyar_glCompileShader;
#define glCompileShader minyar_glCompileShader
static PFNGLCREATEPROGRAMPROC minyar_glCreateProgram;
#define glCreateProgram minyar_glCreateProgram
static PFNGLCREATESHADERPROC minyar_glCreateShader;
#define glCreateShader minyar_glCreateShader
static PFNGLDELETEBUFFERSPROC minyar_glDeleteBuffers;
#define glDeleteBuffers minyar_glDeleteBuffers
static PFNGLDELETESHADERPROC minyar_glDeleteShader;
#define glDeleteShader minyar_glDeleteShader
static PFNGLDELETEVERTEXARRAYSPROC minyar_glDeleteVertexArrays;
#define glDeleteVertexArrays minyar_glDeleteVertexArrays
static PFNGLENABLEVERTEXATTRIBARRAYPROC minyar_glEnableVertexAttribArray;
#define glEnableVertexAttribArray minyar_glEnableVertexAttribArray
static PFNGLGENBUFFERSPROC minyar_glGenBuffers;
#define glGenBuffers minyar_glGenBuffers
static PFNGLGENVERTEXARRAYSPROC minyar_glGenVertexArrays;
#define glGenVertexArrays minyar_glGenVertexArrays
static PFNGLGENERATEMIPMAPPROC minyar_glGenerateMipmap;
#define glGenerateMipmap minyar_glGenerateMipmap
static PFNGLGETPROGRAMIVPROC minyar_glGetProgramiv;
#define glGetProgramiv minyar_glGetProgramiv
static PFNGLGETSHADERINFOLOGPROC minyar_glGetShaderInfoLog;
#define glGetShaderInfoLog minyar_glGetShaderInfoLog
static PFNGLGETSHADERIVPROC minyar_glGetShaderiv;
#define glGetShaderiv minyar_glGetShaderiv
static PFNGLGETUNIFORMLOCATIONPROC minyar_glGetUniformLocation;
#define glGetUniformLocation minyar_glGetUniformLocation
static PFNGLLINKPROGRAMPROC minyar_glLinkProgram;
#define glLinkProgram minyar_glLinkProgram
static PFNGLSHADERSOURCEPROC minyar_glShaderSource;
#define glShaderSource minyar_glShaderSource
static PFNGLUNIFORM1FPROC minyar_glUniform1f;
#define glUniform1f minyar_glUniform1f
static PFNGLUNIFORM1IPROC minyar_glUniform1i;
#define glUniform1i minyar_glUniform1i
static PFNGLUNIFORM2FPROC minyar_glUniform2f;
#define glUniform2f minyar_glUniform2f
static PFNGLUNIFORM2FVPROC minyar_glUniform2fv;
#define glUniform2fv minyar_glUniform2fv
static PFNGLUNIFORM3FVPROC minyar_glUniform3fv;
#define glUniform3fv minyar_glUniform3fv
static PFNGLUNIFORMMATRIX4FVPROC minyar_glUniformMatrix4fv;
#define glUniformMatrix4fv minyar_glUniformMatrix4fv
static PFNGLUSEPROGRAMPROC minyar_glUseProgram;
#define glUseProgram minyar_glUseProgram
static PFNGLVERTEXATTRIBPOINTERPROC minyar_glVertexAttribPointer;
#define glVertexAttribPointer minyar_glVertexAttribPointer

static const char *minyar_load_opengl(void) {
    minyar_glActiveTexture = (PFNGLACTIVETEXTUREPROC)glfwGetProcAddress("glActiveTexture");
    if (!minyar_glActiveTexture) return "glActiveTexture";
    minyar_glAttachShader = (PFNGLATTACHSHADERPROC)glfwGetProcAddress("glAttachShader");
    if (!minyar_glAttachShader) return "glAttachShader";
    minyar_glBindBuffer = (PFNGLBINDBUFFERPROC)glfwGetProcAddress("glBindBuffer");
    if (!minyar_glBindBuffer) return "glBindBuffer";
    minyar_glBindVertexArray = (PFNGLBINDVERTEXARRAYPROC)glfwGetProcAddress("glBindVertexArray");
    if (!minyar_glBindVertexArray) return "glBindVertexArray";
    minyar_glBufferData = (PFNGLBUFFERDATAPROC)glfwGetProcAddress("glBufferData");
    if (!minyar_glBufferData) return "glBufferData";
    minyar_glCompileShader = (PFNGLCOMPILESHADERPROC)glfwGetProcAddress("glCompileShader");
    if (!minyar_glCompileShader) return "glCompileShader";
    minyar_glCreateProgram = (PFNGLCREATEPROGRAMPROC)glfwGetProcAddress("glCreateProgram");
    if (!minyar_glCreateProgram) return "glCreateProgram";
    minyar_glCreateShader = (PFNGLCREATESHADERPROC)glfwGetProcAddress("glCreateShader");
    if (!minyar_glCreateShader) return "glCreateShader";
    minyar_glDeleteBuffers = (PFNGLDELETEBUFFERSPROC)glfwGetProcAddress("glDeleteBuffers");
    if (!minyar_glDeleteBuffers) return "glDeleteBuffers";
    minyar_glDeleteShader = (PFNGLDELETESHADERPROC)glfwGetProcAddress("glDeleteShader");
    if (!minyar_glDeleteShader) return "glDeleteShader";
    minyar_glDeleteVertexArrays = (PFNGLDELETEVERTEXARRAYSPROC)glfwGetProcAddress("glDeleteVertexArrays");
    if (!minyar_glDeleteVertexArrays) return "glDeleteVertexArrays";
    minyar_glEnableVertexAttribArray = (PFNGLENABLEVERTEXATTRIBARRAYPROC)glfwGetProcAddress("glEnableVertexAttribArray");
    if (!minyar_glEnableVertexAttribArray) return "glEnableVertexAttribArray";
    minyar_glGenBuffers = (PFNGLGENBUFFERSPROC)glfwGetProcAddress("glGenBuffers");
    if (!minyar_glGenBuffers) return "glGenBuffers";
    minyar_glGenVertexArrays = (PFNGLGENVERTEXARRAYSPROC)glfwGetProcAddress("glGenVertexArrays");
    if (!minyar_glGenVertexArrays) return "glGenVertexArrays";
    minyar_glGenerateMipmap = (PFNGLGENERATEMIPMAPPROC)glfwGetProcAddress("glGenerateMipmap");
    if (!minyar_glGenerateMipmap) return "glGenerateMipmap";
    minyar_glGetProgramiv = (PFNGLGETPROGRAMIVPROC)glfwGetProcAddress("glGetProgramiv");
    if (!minyar_glGetProgramiv) return "glGetProgramiv";
    minyar_glGetShaderInfoLog = (PFNGLGETSHADERINFOLOGPROC)glfwGetProcAddress("glGetShaderInfoLog");
    if (!minyar_glGetShaderInfoLog) return "glGetShaderInfoLog";
    minyar_glGetShaderiv = (PFNGLGETSHADERIVPROC)glfwGetProcAddress("glGetShaderiv");
    if (!minyar_glGetShaderiv) return "glGetShaderiv";
    minyar_glGetUniformLocation = (PFNGLGETUNIFORMLOCATIONPROC)glfwGetProcAddress("glGetUniformLocation");
    if (!minyar_glGetUniformLocation) return "glGetUniformLocation";
    minyar_glLinkProgram = (PFNGLLINKPROGRAMPROC)glfwGetProcAddress("glLinkProgram");
    if (!minyar_glLinkProgram) return "glLinkProgram";
    minyar_glShaderSource = (PFNGLSHADERSOURCEPROC)glfwGetProcAddress("glShaderSource");
    if (!minyar_glShaderSource) return "glShaderSource";
    minyar_glUniform1f = (PFNGLUNIFORM1FPROC)glfwGetProcAddress("glUniform1f");
    if (!minyar_glUniform1f) return "glUniform1f";
    minyar_glUniform1i = (PFNGLUNIFORM1IPROC)glfwGetProcAddress("glUniform1i");
    if (!minyar_glUniform1i) return "glUniform1i";
    minyar_glUniform2f = (PFNGLUNIFORM2FPROC)glfwGetProcAddress("glUniform2f");
    if (!minyar_glUniform2f) return "glUniform2f";
    minyar_glUniform2fv = (PFNGLUNIFORM2FVPROC)glfwGetProcAddress("glUniform2fv");
    if (!minyar_glUniform2fv) return "glUniform2fv";
    minyar_glUniform3fv = (PFNGLUNIFORM3FVPROC)glfwGetProcAddress("glUniform3fv");
    if (!minyar_glUniform3fv) return "glUniform3fv";
    minyar_glUniformMatrix4fv = (PFNGLUNIFORMMATRIX4FVPROC)glfwGetProcAddress("glUniformMatrix4fv");
    if (!minyar_glUniformMatrix4fv) return "glUniformMatrix4fv";
    minyar_glUseProgram = (PFNGLUSEPROGRAMPROC)glfwGetProcAddress("glUseProgram");
    if (!minyar_glUseProgram) return "glUseProgram";
    minyar_glVertexAttribPointer = (PFNGLVERTEXATTRIBPOINTERPROC)glfwGetProcAddress("glVertexAttribPointer");
    if (!minyar_glVertexAttribPointer) return "glVertexAttribPointer";
    return NULL;
}
#else
static const char *minyar_load_opengl(void) { return NULL; }
#endif
#endif
