/* Exact numeric scalar-array adaptation of Ruby codepoints("abc").
 * Use the runtime ABI; no invented source ord API. */
#include <assert.h>
#include <stddef.h>

typedef struct MinyarText MinyarText;
/* Match the runtime's anonymous scalar List type across translation units. */
typedef struct {
    long long *values;
    long long length;
    long long capacity;
} MinyarList;
void minyar_initialize_arguments(int count, char **values);
MinyarText *minyar_argument(long long position);
long long minyar_text_length(MinyarText *text);
int minyar_text_character_at(MinyarText *text, long long position);
MinyarList *minyar_list_new(void);
void minyar_list_add(MinyarList *list, long long value);
long long minyar_list_length(const MinyarList *list);
long long minyar_list_get(const MinyarList *list, long long position);
void minyar_print_integer(long long value);
void minyar_rc_release(void *value);

static MinyarList *codepoints(MinyarText *text) {
    MinyarList *result = minyar_list_new();
    for (long long index = 0; index < minyar_text_length(text); index++) {
        minyar_list_add(result, minyar_text_character_at(text, index));
    }
    return result;
}

int main(int argc, char **argv) {
    assert(argc == 2);
    minyar_initialize_arguments(argc, argv);
    MinyarText *text = minyar_argument(0);
    MinyarList *values = codepoints(text);
    minyar_rc_release(text);
    const long long expected[] = {97, 98, 99};
    assert(minyar_list_length(values) == 3);
    minyar_print_integer(minyar_list_length(values));
    for (long long index = 0; index < 3; index++) {
        long long observed = minyar_list_get(values, index);
        assert(observed == expected[index]);
        minyar_print_integer(observed);
    }
    minyar_rc_release(values);
    return 0;
}
