/* Exercise the runtime's actual file-length helper without allocating the
 * file contents. The Python driver creates a sparse file above 2 GiB. */
#include "../runtime/minyar_runtime.c"

int main(int count, char **arguments) {
    if (count != 2) return 2;
    FILE *file = fopen(arguments[1], "rb");
    if (!file) return 3;
    long long length = text_file_length(file);
    if (fclose(file) != 0) return 4;
    printf("%lld\n", length);
    return 0;
}
