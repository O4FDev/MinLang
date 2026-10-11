/* Only locally compiled, signed fixture code is executed by updater tests. */
#include <stdio.h>
#ifdef __APPLE__
#include <CoreFoundation/CoreFoundation.h>
#endif
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#include <shellapi.h>
#else
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#endif
int main(int argc, char **argv) {
    puts("OWNED-HELPER");
#ifdef _WIN32
    (void)argv;
    wchar_t **values = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (!values)
        return 91;
#endif
    for (int i = 1; i < argc; i++) {
#ifdef _WIN32
        char value[32768];
        if (!WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, values[i], -1, value, sizeof(value),
                                 NULL, NULL))
            return 92;
        const char *argument = value;
#else
        const char *argument = argv[i];
#endif
        printf("%zu:", strlen(argument));
        const unsigned char *p = (const unsigned char *)argument;
        while (*p)
            printf("%02x", *p++);
        putchar('\n');
    }
#ifdef __APPLE__
    CFURLRef bundled =
        CFBundleCopyResourceURL(CFBundleGetMainBundle(), CFSTR("message"), CFSTR("txt"), NULL);
    if (bundled) {
        unsigned char path[4096];
        if (!CFURLGetFileSystemRepresentation(bundled, true, path, sizeof(path)))
            return 93;
        FILE *native_resource = fopen((const char *)path, "rb");
        if (!native_resource)
            return 94;
        char native_bytes[256];
        size_t native_count = fread(native_bytes, 1, sizeof(native_bytes), native_resource);
        fclose(native_resource);
        printf("NATIVE-BUNDLE-RESOURCE:");
        fwrite(native_bytes, 1, native_count, stdout);
        putchar('\n');
        CFRelease(bundled);
    }
#endif
    FILE *resource = fopen("App.app/Contents/Resources/message.txt", "rb");
    if (resource) {
        char buffer[256];
        size_t n = fread(buffer, 1, sizeof(buffer), resource);
        fclose(resource);
        printf("RESOURCE:");
        fwrite(buffer, 1, n, stdout);
        putchar('\n');
    }
#ifndef _WIN32
    int leaked = 0;
    for (int fd = 3; fd < 256; fd++)
        if (fcntl(fd, F_GETFD) >= 0 || errno != EBADF)
            leaked++;
    printf("LEAKED:%d\n", leaked);
#endif
#ifdef _WIN32
    LocalFree(values);
#endif
    return 23;
}
