/* The standard library does not yet expose stdin. Keep this bridge scalar:
 * command parsing, bounded lines, state and rendering stay in Minyar. */
#include <stdio.h>

long long minyar_trailinput_nextByte(void) {
    int value = getchar();
    if (value == EOF) return ferror(stdin) ? -2 : -1;
    return value;
}

void minyar_trailinput_prompt(void) {
    fputs("> ", stdout);
    fflush(stdout);
}
