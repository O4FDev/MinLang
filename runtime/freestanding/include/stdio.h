/* Freestanding stdio for the Minyar runtime: output goes to the first serial
 * port and there is no file system, so opening a file always fails. */
#ifndef MINYAR_FREESTANDING_STDIO_H
#define MINYAR_FREESTANDING_STDIO_H
#include <stddef.h>
#include <stdarg.h>

typedef struct MinyarFile FILE;
extern FILE *stdin, *stdout, *stderr;
#define EOF (-1)
#define SEEK_SET 0
#define SEEK_CUR 1
#define SEEK_END 2

size_t fwrite(const void *data, size_t size, size_t count, FILE *file);
size_t fread(void *data, size_t size, size_t count, FILE *file);
int fputs(const char *text, FILE *file);
int fputc(int character, FILE *file);
int putchar(int character);
int puts(const char *text);
int fflush(FILE *file);
int printf(const char *format, ...);
int fprintf(FILE *file, const char *format, ...);
int snprintf(char *out, size_t capacity, const char *format, ...);
int vsnprintf(char *out, size_t capacity, const char *format, va_list arguments);
FILE *fopen(const char *path, const char *mode);
int fclose(FILE *file);
int fseek(FILE *file, long offset, int origin);
long ftell(FILE *file);
int fgetc(FILE *file);
int ferror(FILE *file);
#endif
