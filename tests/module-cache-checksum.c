/* Produce a valid envelope checksum while deliberately corrupting its payload
 * in the driver tests. This reaches compiler validation past the outer check. */
#define main module_driver_main
#include "../tools/module-build.c"
#undef main
int main(int argc, char **argv) {
    if (argc != 2) return 2;
    Bytes value = read_path(argv[1], CACHE_LIMIT);
    if (!value.data) return 1;
    printf("%016" PRIx64 "\n", artifact_hash(value.data, value.size));
    free(value.data);
    return 0;
}
