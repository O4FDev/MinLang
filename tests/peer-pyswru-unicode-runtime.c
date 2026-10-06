/* Numeric scalar access uses Minyar's real runtime ABI, not a source ord shim. */
#include <assert.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>

typedef struct MinyarText MinyarText;
void minyar_initialize_arguments(int count, char **values);
MinyarText *minyar_argument(long long position);
long long minyar_text_length(MinyarText *text);
int minyar_text_character_at(MinyarText *text, long long position);
void minyar_print_integer(long long value);
void minyar_rc_release(void *value);

int main(int argc, char **argv) {
    assert(argc == 3);
    minyar_initialize_arguments(argc, argv);
    MinyarText *text = minyar_argument(0);
    long long value;
    if (strcmp(argv[2], "length") == 0) {
        value = minyar_text_length(text);
    } else {
        char *end;
        errno = 0;
        long long position = strtoll(argv[2], &end, 10);
        assert(errno == 0 && argv[2][0] != '\0' && *end == '\0');
        value = minyar_text_character_at(text, position);
    }
    minyar_rc_release(text);
    minyar_print_integer(value);
    return 0;
}
