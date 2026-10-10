#ifndef MINYAR_FREESTANDING_STDLIB_H
#define MINYAR_FREESTANDING_STDLIB_H
#include <stddef.h>
void *malloc(size_t bytes);
void *calloc(size_t count, size_t bytes);
void *realloc(void *pointer, size_t bytes);
void free(void *pointer);
_Noreturn void exit(int status);
_Noreturn void abort(void);
double strtod(const char *text, char **end);
int atoi(const char *text);
int atexit(void (*function)(void));
#endif
