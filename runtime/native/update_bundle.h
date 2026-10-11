/* Deliberately small uncompressed format. No archive-library or shell parser.
 * All path names, modes and bytes are authenticated by the outer manifest. */
#include <stdint.h>
#include <ctype.h>
enum { UPD_ENTRIES = 4096, UPD_BUNDLE_PATH = 512 };
static const unsigned char bundle_magic[] = "MINYAR-BUNDLE-1\n";
typedef struct {
    char path[UPD_BUNDLE_PATH + 1];
    unsigned char type; /* D: directory, F: regular file */
    unsigned char executable;
    const unsigned char *data;
    size_t size;
} BundleEntry;
typedef struct {
    BundleEntry *entries;
    size_t count;
    size_t main;
} UpdateBundle;

static bool path_valid(const unsigned char *path, size_t length) {
    if (!length || length > UPD_BUNDLE_PATH)
        return false;
    size_t start = 0;
    for (size_t i = 0; i <= length; i++) {
        if (i < length && path[i] != '/') {
            unsigned char c = path[i];
            if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') ||
                  c == '.' || c == '_' || c == '-' || c == ' '))
                return false;
            continue;
        }
        size_t n = i - start;
        if (!n || n > 64 || path[start] == ' ' || path[i - 1] == ' ' || path[i - 1] == '.' ||
            (n == 1 && path[start] == '.') ||
            (n == 2 && path[start] == '.' && path[start + 1] == '.'))
            return false;
        char stem[65];
        size_t end = 0;
        while (end < n && path[start + end] != '.') {
            stem[end] = (char)toupper(path[start + end]);
            end++;
        }
        stem[end] = 0;
        if (!strcmp(stem, "CON") || !strcmp(stem, "PRN") || !strcmp(stem, "AUX") ||
            !strcmp(stem, "NUL") || !strcmp(stem, "CONIN$") || !strcmp(stem, "CONOUT$") ||
            (end == 4 && (!memcmp(stem, "COM", 3) || !memcmp(stem, "LPT", 3)) && stem[3] >= '0' &&
             stem[3] <= '9'))
            return false;
        start = i + 1;
    }
    return true;
}
static int fold_compare(const char *left, const char *right) {
    while (*left && *right) {
        int a = tolower((unsigned char)*left++), b = tolower((unsigned char)*right++);
        if (a != b)
            return a - b;
    }
    return (unsigned char)*left - (unsigned char)*right;
}
static bool bundle_number(const MinyarBytes *bytes, size_t *at, unsigned width, uint64_t *result) {
    size_t length = (size_t)bytes->byte_length;
    if (*at > length || width > length - *at)
        return false;
    *result = 0;
    for (unsigned i = 0; i < width; i++)
        *result = (*result << 8) | bytes->bytes[(*at)++];
    return true;
}
static bool is_bundle(const MinyarBytes *bytes) {
    return bytes->byte_length >= (long long)(sizeof(bundle_magic) - 1) &&
           !memcmp(bytes->bytes, bundle_magic, sizeof(bundle_magic) - 1);
}
static void bundle_free(UpdateBundle *bundle) {
    free(bundle->entries);
    memset(bundle, 0, sizeof(*bundle));
}
static bool bundle_parse(const MinyarBytes *bytes, UpdateBundle *bundle) {
    memset(bundle, 0, sizeof(*bundle));
    if (!is_bundle(bytes) || bytes->byte_length > UPD_ARTIFACT)
        return problem("invalid bundle header");
    size_t at = sizeof(bundle_magic) - 1;
    uint64_t n, count;
    char main[UPD_BUNDLE_PATH + 1];
    if (!bundle_number(bytes, &at, 4, &n) || n > UPD_BUNDLE_PATH ||
        n > (size_t)bytes->byte_length - at || !path_valid(bytes->bytes + at, (size_t)n))
        return problem("invalid bundle entrypoint");
    memcpy(main, bytes->bytes + at, (size_t)n);
    main[n] = 0;
    at += (size_t)n;
    if (!bundle_number(bytes, &at, 4, &count) || count < 1 || count > UPD_ENTRIES)
        return problem("invalid bundle entry count");
    bundle->entries = calloc((size_t)count, sizeof(BundleEntry));
    if (!bundle->entries)
        return problem("cannot allocate bundle index");
    bundle->count = (size_t)count;
    bundle->main = (size_t)count;
    for (size_t i = 0; i < bundle->count; i++) {
        BundleEntry *entry = &bundle->entries[i];
        uint64_t type, mode, size;
        if (!bundle_number(bytes, &at, 1, &type) || !bundle_number(bytes, &at, 1, &mode) ||
            !bundle_number(bytes, &at, 4, &n) || !bundle_number(bytes, &at, 8, &size) ||
            (type != 'D' && type != 'F') || mode > 1 || (type == 'D' && (size || mode)) ||
            size > UPD_ARTIFACT || n > (size_t)bytes->byte_length - at ||
            !path_valid(bytes->bytes + at, (size_t)n))
            goto invalid;
        memcpy(entry->path, bytes->bytes + at, (size_t)n);
        entry->path[n] = 0;
        at += (size_t)n;
        if (size > (size_t)bytes->byte_length - at)
            goto invalid;
        entry->data = bytes->bytes + at;
        entry->size = (size_t)size;
        at += (size_t)size;
        entry->type = (unsigned char)type;
        entry->executable = (unsigned char)mode;
        if (i && strcmp(bundle->entries[i - 1].path, entry->path) >= 0)
            goto invalid;
        for (size_t j = 0; j < i; j++)
            if (!fold_compare(bundle->entries[j].path, entry->path))
                goto invalid;
        char parent[UPD_BUNDLE_PATH + 1];
        memcpy(parent, entry->path, (size_t)n + 1);
        char *slash = strrchr(parent, '/');
        if (slash) {
            *slash = 0;
            bool found = false;
            for (size_t j = 0; j < i; j++)
                if (!strcmp(bundle->entries[j].path, parent) && bundle->entries[j].type == 'D')
                    found = true;
            if (!found)
                goto invalid;
        }
        if (!strcmp(entry->path, main)) {
            if (type != 'F' || !mode || size < 4)
                goto invalid;
            bundle->main = i;
        }
    }
    if (at != (size_t)bytes->byte_length || bundle->main == bundle->count)
        goto invalid;
    return true;
invalid:
    bundle_free(bundle);
    return problem("invalid, ambiguous or incomplete bundle index");
}
