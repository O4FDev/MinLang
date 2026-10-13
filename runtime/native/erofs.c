#define _GNU_SOURCE
#include "../minyar_native.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <linux/openat2.h>
#include <lz4.h>
#include <zstd.h>
#include <zstd_errors.h>
#include <stdint.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/sysmacros.h>
#include <sys/types.h>
#include <sys/xattr.h>
#include <unistd.h>

typedef struct EInode EInode;
typedef struct ENode ENode;
struct EInode {
    struct stat st;
    char *source, *link;
    unsigned char *attrs;
    size_t attrs_size;
    uint64_t nid, size;
    uint32_t block, links;
    uint64_t map_size;
    uint32_t stored_blocks;
    int virtual_data;
    uint64_t data_offset;
    EInode *hash_next;
};
struct ENode {
    char *name;
    EInode *inode;
    ENode *parent;
    ENode **children;
    size_t count, capacity;
    ENode **buckets, *hash_next;
    size_t bucket_count, child_index;
    uint64_t generation, pending_id;
};
typedef struct {
    EInode **inodes;
    size_t count, capacity;
    EInode *hash[65536];
    ENode *root;
    int source_fd, output_fd;
    uint64_t maximum, position;
    int compression;
    int level;
    size_t lz4_hint;
    ZSTD_CCtx *codec;
    int data_fd;
    uint64_t spool_size;
} EWriter;

static uint64_t e_align(uint64_t n, uint64_t a) { return (n + a - 1) & ~(a - 1); }
static void e16(unsigned char *p, uint16_t n) { p[0] = n; p[1] = n >> 8; }
static void e32(unsigned char *p, uint32_t n) { e16(p, n); e16(p + 2, n >> 16); }
static void e64(unsigned char *p, uint64_t n) { e32(p, n); e32(p + 4, n >> 32); }
static int e_write(int fd, const void *data, size_t size, uint64_t offset) {
    const unsigned char *p = data;
    while (size) {
        ssize_t n = pwrite(fd, p, size, (off_t)offset);
        if (n < 0) { if (errno == EINTR) continue; return errno; }
        if (!n) return EIO;
        p += n; size -= n; offset += n;
    }
    return 0;
}
static int e_grow(void **p, size_t *capacity, size_t count, size_t width) {
    if (count <= *capacity) return 0;
    size_t n = *capacity ? *capacity * 2 : 16;
    if (n < count) n = count;
    if (n > SIZE_MAX / width) return EOVERFLOW;
    void *q = realloc(*p, n * width);
    if (!q) return ENOMEM;
    *p = q; *capacity = n; return 0;
}
static char *e_join(const char *parent, const char *name) {
    char *result;
    if (asprintf(&result, "%s%s%s", parent, *parent ? "/" : "", name) < 0) return NULL;
    return result;
}
static int e_attrs(EInode *inode, const char *path) {
    ssize_t length = llistxattr(path, NULL, 0);
    if (length < 0) return errno == ENOTSUP ? 0 : errno;
    if (!length) return 0;
    char *names = malloc((size_t)length);
    if (!names) return ENOMEM;
    if (llistxattr(path, names, (size_t)length) != length) { free(names); return errno ? errno : ESTALE; }
    size_t capacity = 0, size = 12;
    int error = e_grow((void **)&inode->attrs, &capacity, size, 1);
    if (!error) memset(inode->attrs, 0, 12);
    for (size_t at = 0; !error && at < (size_t)length;) {
        const char *name = names + at, *suffix = name;
        size_t n = strnlen(name, (size_t)length - at);
        if (n == (size_t)length - at) { error = EIO; break; }
        at += n + 1;
        unsigned index = 0;
        if (!strncmp(name, "user.", 5)) { index = 1; suffix += 5; }
        else if (!strcmp(name, "system.posix_acl_access")) { index = 2; suffix += n; }
        else if (!strcmp(name, "system.posix_acl_default")) { index = 3; suffix += n; }
        else if (!strncmp(name, "trusted.", 8)) { index = 4; suffix += 8; }
        else if (!strncmp(name, "security.", 9)) { index = 6; suffix += 9; }
        else { error = ENOTSUP; break; }
        size_t nn = strlen(suffix);
        ssize_t vn = lgetxattr(path, name, NULL, 0);
        if (vn < 0) { error = errno; break; }
        if (nn > 255 || vn > 65535) { error = EOVERFLOW; break; }
        size_t entry = (size_t)e_align(4 + nn + (size_t)vn, 4);
        if (size + entry > 262148) { error = EOVERFLOW; break; }
        error = e_grow((void **)&inode->attrs, &capacity, size + entry, 1);
        if (error) break;
        unsigned char *p = inode->attrs + size;
        memset(p, 0, entry); p[0] = (unsigned char)nn; p[1] = index; e16(p + 2, (uint16_t)vn);
        memcpy(p + 4, suffix, nn);
        if (lgetxattr(path, name, p + 4 + nn, (size_t)vn) != vn) { error = errno ? errno : ESTALE; break; }
        size += entry;
    }
    free(names);
    if (!error) inode->attrs_size = size;
    return error;
}
static int e_order(const void *a, const void *b) {
    return strcmp((*(ENode *const *)a)->name, (*(ENode *const *)b)->name);
}
static int e_scan(EWriter *w, ENode *node, int parent_fd, const char *relative, unsigned depth) {
    if (depth > 256) return ELOOP;
    struct stat st;
    if (fstatat(parent_fd, node->parent ? node->name : ".", &st, AT_SYMLINK_NOFOLLOW)) return errno;
    if (S_ISSOCK(st.st_mode)) return ENOTSUP;
    unsigned bucket = ((uint64_t)st.st_ino ^ ((uint64_t)st.st_dev * 11400714819323198485ull)) & 65535;
    if (!S_ISDIR(st.st_mode) && st.st_nlink > 1) {
        for (EInode *i = w->hash[bucket]; i; i = i->hash_next) {
            if (i->st.st_dev == st.st_dev && i->st.st_ino == st.st_ino) {
                if (i->links == UINT32_MAX) return EOVERFLOW;
                node->inode = i; ++i->links; return 0;
            }
        }
    }
    int error = e_grow((void **)&w->inodes, &w->capacity, w->count + 1, sizeof(*w->inodes));
    if (error) return error;
    EInode *i = calloc(1, sizeof(*i));
    if (!i) return ENOMEM;
    w->inodes[w->count++] = i; node->inode = i; i->st = st;
    i->source = strdup(relative); i->size = S_ISREG(st.st_mode) ? (uint64_t)st.st_size : 0;
    i->links = S_ISDIR(st.st_mode) ? 2 : 1;
    if (!i->source) return ENOMEM;
    i->hash_next = w->hash[bucket]; w->hash[bucket] = i;
    char *path;
    if (asprintf(&path, "/proc/self/fd/%d/%s", parent_fd, node->parent ? node->name : ".") < 0) return ENOMEM;
    error = e_attrs(i, path); free(path);
    if (error) return error;
    if (S_ISLNK(st.st_mode)) {
        if (st.st_size < 0 || st.st_size > 65535) return EOVERFLOW;
        i->link = malloc((size_t)st.st_size + 1);
        if (!i->link) return ENOMEM;
        ssize_t n = readlinkat(parent_fd, node->name, i->link, (size_t)st.st_size + 1);
        if (n < 0) return errno;
        if (n != st.st_size) return ESTALE;
        i->size = (uint64_t)n;
    }
    if (!S_ISDIR(st.st_mode)) return 0;
    int fd = openat(parent_fd, node->parent ? node->name : ".", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (fd < 0) return errno;
    DIR *dir = fdopendir(fd);
    if (!dir) { error = errno; close(fd); return error; }
    struct dirent *entry;
    for (;;) {
        errno = 0; entry = readdir(dir);
        if (!entry) { if (errno) error = errno; break; }
        if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, "..")) continue;
        error = e_grow((void **)&node->children, &node->capacity, node->count + 1, sizeof(*node->children));
        if (error) break;
        ENode *child = calloc(1, sizeof(*child));
        if (!child) { error = ENOMEM; break; }
        node->children[node->count++] = child; child->parent = node; child->name = strdup(entry->d_name);
        if (!child->name) { error = ENOMEM; break; }
    }
    if (!error) {
        if (node->count > 1) qsort(node->children, node->count, sizeof(*node->children), e_order);
        for (size_t n = 0; n < node->count; ++n) {
            ENode *child = node->children[n];
            char *path2 = e_join(relative, child->name);
            if (!path2) { error = ENOMEM; break; }
            error = e_scan(w, child, fd, path2, depth + 1); free(path2);
            if (error) break;
            if (S_ISDIR(child->inode->st.st_mode)) ++i->links;
        }
    }
    closedir(dir); return error;
}
static unsigned e_type(mode_t mode) {
    if (S_ISREG(mode)) return 1;
    if (S_ISDIR(mode)) return 2;
    if (S_ISCHR(mode)) return 3;
    if (S_ISBLK(mode)) return 4;
    if (S_ISFIFO(mode)) return 5;
    if (S_ISLNK(mode)) return 7;
    return 0;
}
typedef struct { const char *name; EInode *inode; } EDirent;
static int e_dirorder(const void *a, const void *b) { return strcmp(((const EDirent *)a)->name, ((const EDirent *)b)->name); }
static int e_directory(ENode *node, int fd, uint64_t offset) {
    size_t count = node->count + 2;
    EDirent *entries = calloc(count, sizeof(*entries));
    if (!entries) return ENOMEM;
    entries[0] = (EDirent){".", node->inode};
    entries[1] = (EDirent){"..", node->parent ? node->parent->inode : node->inode};
    for (size_t n = 0; n < node->count; ++n) entries[n + 2] = (EDirent){node->children[n]->name, node->children[n]->inode};
    qsort(entries, count, sizeof(*entries), e_dirorder);
    uint64_t total = 0;
    int error = 0;
    for (size_t first = 0; first < count;) {
        size_t last = first, names = 0;
        while (last < count && (last - first + 1) * 12 + names + strlen(entries[last].name) <= 4096) names += strlen(entries[last++].name);
        if (last == first) { error = ENAMETOOLONG; break; }
        unsigned char block[4096] = {0};
        size_t at = (last - first) * 12;
        for (size_t n = first; n < last; ++n) {
            unsigned char *p = block + (n - first) * 12;
            e64(p, entries[n].inode->nid); e16(p + 8, (uint16_t)at); p[10] = e_type(entries[n].inode->st.st_mode);
            size_t length = strlen(entries[n].name); memcpy(block + at, entries[n].name, length); at += length;
        }
        if (fd >= 0) { error = e_write(fd, block, sizeof(block), offset + total); if (error) break; }
        total += last == count ? at : 4096;
        first = last;
    }
    free(entries);
    if (!error) node->inode->size = total;
    return error;
}
static int e_dirs(ENode *node, int fd) {
    if (!S_ISDIR(node->inode->st.st_mode)) return 0;
    int error = e_directory(node, fd, (uint64_t)node->inode->block * 4096);
    for (size_t n = 0; !error && n < node->count; ++n) error = e_dirs(node->children[n], fd);
    return error;
}
static int e_copy(EWriter *w, EInode *i) {
    struct open_how how = {.flags = O_RDONLY | O_CLOEXEC | O_NOFOLLOW, .resolve = RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS};
    int fd = i->virtual_data ? dup(w->data_fd) : (int)syscall(SYS_openat2, w->source_fd, i->source, &how, sizeof(how));
    if (fd < 0) return errno;
    struct stat st;
    int error = fstat(fd, &st) ? errno : 0;
    if (!error && !i->virtual_data && (st.st_ino != i->st.st_ino || st.st_dev != i->st.st_dev || st.st_size != i->st.st_size || !S_ISREG(st.st_mode))) error = ESTALE;
    off_t input = i->virtual_data ? (off_t)i->data_offset : 0, output = (off_t)i->block * 4096;
    uint64_t remaining = i->size;
    unsigned char *buffer = NULL;
    while (!error && remaining) {
        uint64_t limit = buffer ? 1048576 : 1073741824;
        size_t count = remaining > limit ? (size_t)limit : (size_t)remaining;
        ssize_t n;
        if (!buffer) {
            n = copy_file_range(fd, &input, w->output_fd, &output, count, 0);
            if (n < 0 && (errno == EXDEV || errno == EINVAL || errno == ENOSYS || errno == EOPNOTSUPP)) {
                buffer = malloc(1048576);
                if (!buffer) error = ENOMEM;
                continue;
            }
        } else {
            n = pread(fd, buffer, count, input);
            if (n > 0) { error = e_write(w->output_fd, buffer, (size_t)n, (uint64_t)output); input += n; output += n; }
        }
        if (n < 0) { if (errno == EINTR) continue; error = errno; }
        else if (!n) error = ESTALE;
        else remaining -= (uint64_t)n;
    }
    if (!error && !i->virtual_data) {
        if (fstat(fd, &st)) error = errno;
        else if (st.st_size != i->st.st_size || st.st_mtim.tv_sec != i->st.st_mtim.tv_sec || st.st_mtim.tv_nsec != i->st.st_mtim.tv_nsec || st.st_ctim.tv_sec != i->st.st_ctim.tv_sec || st.st_ctim.tv_nsec != i->st.st_ctim.tv_nsec) error = ESTALE;
    }
    free(buffer); close(fd); return error;
}
static unsigned e_compact_initial(EInode *i) { return (unsigned)((32 - (e_align(64 + i->attrs_size, 8) + 8) % 32) % 32 / 4); }
static uint64_t e_compact_middle(EInode *i, uint64_t clusters) { unsigned initial = e_compact_initial(i); return clusters > initial ? (clusters - initial) / 16 * 16 : 0; }
static int e_compress(EWriter *w, EInode *i) {
    struct open_how how = {.flags = O_RDONLY | O_CLOEXEC | O_NOFOLLOW, .resolve = RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS};
    int fd = i->virtual_data ? dup(w->data_fd) : (int)syscall(SYS_openat2, w->source_fd, i->source, &how, sizeof(how));
    if (fd < 0) return errno;
    struct stat st;
    int error = fstat(fd, &st) ? errno : 0;
    if (!error && !i->virtual_data && (st.st_ino != i->st.st_ino || st.st_dev != i->st.st_dev || st.st_size != i->st.st_size || !S_ISREG(st.st_mode))) error = ESTALE;
    uint64_t total_clusters = e_align(i->size, 4096) / 4096;
    unsigned char *map = calloc(1, (size_t)(16 + total_clusters * 8));
    unsigned char *compact = calloc(1, (size_t)i->map_size);
    unsigned char *input = malloc(1048576), *encoded = malloc(65536), *output = malloc(65536);
    if (!map || !compact || !input || !encoded || !output) error = ENOMEM;
    if (!error && w->compression == 1 && (ZSTD_isError(ZSTD_CCtx_setParameter(w->codec, ZSTD_c_compressionLevel, w->level)) || ZSTD_isError(ZSTD_CCtx_setParameter(w->codec, ZSTD_c_windowLog, 19)))) error = EINVAL;
    if (!error) { e16(map + 4, 7); map[6] = w->compression == 1 ? 3 : 0; }
    uint64_t at = 0, first_block = w->position / 4096;
    size_t buffered = 0, hint = w->compression == 2 && w->lz4_hint ? w->lz4_hint : 1048576;
    while (!error && at < i->size) {
        size_t size = i->size - at > hint ? hint : (size_t)(i->size - at);
        while (buffered < size) {
            ssize_t n = pread(fd, input + buffered, size - buffered, (off_t)(at + buffered + (i->virtual_data ? i->data_offset : 0)));
            if (n < 0) { if (errno == EINTR) continue; error = errno; break; }
            if (!n) { error = ESTALE; break; }
            buffered += (size_t)n;
        }
        if (error) break;
        int packed = 0;
        if (w->compression == 1) {
            size_t result = ZSTD_compress2(w->codec, encoded, 65536, input, size);
            if (ZSTD_isError(result)) {
                if (ZSTD_getErrorCode(result) != ZSTD_error_dstSize_tooSmall) { error = ZSTD_getErrorCode(result) == ZSTD_error_memory_allocation ? ENOMEM : EIO; break; }
                size_t low = 0, high = size / 4096 + 1;
                while (high > low + 1) {
                    size_t middle = (low + high) / 2;
                    result = ZSTD_compress2(w->codec, encoded, 65536, input, middle * 4096);
                    if (!ZSTD_isError(result)) low = middle;
                    else if (ZSTD_getErrorCode(result) == ZSTD_error_dstSize_tooSmall) high = middle;
                    else { error = ZSTD_getErrorCode(result) == ZSTD_error_memory_allocation ? ENOMEM : EIO; break; }
                }
                if (error) break;
                if (low) { size = low * 4096; result = ZSTD_compress2(w->codec, encoded, 65536, input, size); }
            }
            if (!ZSTD_isError(result)) packed = (int)result;
        } else {
            if (hint < 1048576) packed = LZ4_compress_default((const char *)input, (char *)encoded, (int)size, 65536);
            if (!packed) {
                int consumed = (int)size;
                packed = LZ4_compress_destSize((const char *)input, (char *)encoded, &consumed, 65536);
                if (packed > 0 && (size_t)consumed < size) {
                    size = (size_t)consumed & ~(size_t)4095;
                    packed = size ? LZ4_compress_default((const char *)input, (char *)encoded, (int)size, 65536) : 0;
                }
            }
        }
        if (!packed) size = buffered > 65536 ? 65536 : buffered;
        hint = size;
        if (packed > 0 && packed < 61440) {
            uint64_t next = (uint64_t)size * 65500 / (unsigned)packed;
            hint = (size_t)(next > 1048576 ? 1048576 : next) & ~(size_t)4095;
            if (hint < 4096) hint = 4096;
        }
        if (w->compression == 1) hint = 1048576;
        else if (at + size < i->size) w->lz4_hint = hint;
        unsigned clusters = (unsigned)e_align(size, 4096) / 4096;
        unsigned blocks = packed > 0 ? (unsigned)e_align((unsigned)packed, 4096) / 4096 : clusters;
        int compressed = blocks < clusters;
        if (!compressed) blocks = clusters;
        uint64_t physical_size = (uint64_t)blocks * 4096;
        if (physical_size > w->maximum || w->position > w->maximum - physical_size || w->position / 4096 + blocks >= UINT32_MAX) { error = EFBIG; break; }
        uint32_t address = (uint32_t)(w->position / 4096);
        for (unsigned n = 0; n < clusters; ++n) {
            unsigned char *index = map + 16 + (at / 4096 + n) * 8;
            if (compressed && n) {
                e16(index, 2); e16(index + 4, n == 1 ? (uint16_t)(2048 | blocks) : (uint16_t)n); e16(index + 6, (uint16_t)(clusters - n));
            } else {
                e16(index, compressed ? 1 : 0); e32(index + 4, address + (compressed ? 0 : n));
            }
        }
        if (compressed) {
            memset(output, 0, (size_t)physical_size);
            memcpy(output + physical_size - (size_t)packed, encoded, (size_t)packed);
            error = e_write(w->output_fd, output, (size_t)physical_size, w->position);
        } else {
            if (physical_size > size) memset(input + size, 0, (size_t)physical_size - size);
            error = e_write(w->output_fd, input, (size_t)physical_size, w->position);
        }
        w->position += physical_size; at += size;
        buffered -= size;
        if (buffered) memmove(input, input + size, buffered);
    }
    if (!error) {
        i->stored_blocks = (uint32_t)(w->position / 4096 - first_block);
        memcpy(compact, map, 8);
        uint32_t physical = (uint32_t)first_block;
        int preceding_head = 0;
        unsigned initial = e_compact_initial(i);
        uint64_t middle = e_compact_middle(i, total_clusters), offset = 8;
        for (uint64_t n = 0; n < total_clusters;) {
            unsigned count = n >= initial && n < initial + middle ? 16 : 2;
            unsigned width = count == 16 ? 2 : 4, bits = count == 16 ? 14 : 16;
            unsigned char *pair = compact + offset;
            uint32_t base = physical;
            for (unsigned k = 0; k < count && n + k < total_clusters; ++k) {
                unsigned char *entry = map + 16 + (n + k) * 8;
                unsigned type = entry[0] & 3;
                unsigned value = 0;
                if (type == 2) {
                    unsigned back = entry[4] | (unsigned)entry[5] << 8;
                    if (back & 2048) { value = back; physical += back & 2047; preceding_head = 0; }
                    else value = k + 1 == count ? entry[6] | (unsigned)entry[7] << 8 : back;
                } else {
                    if (preceding_head) { ++physical; if (!k) base = physical; }
                    preceding_head = 1;
                }
                unsigned encoded_index = type << 12 | value, bit = k * bits, byte = bit / 8, shift = bit % 8;
                pair[byte] |= (unsigned char)(encoded_index << shift);
                pair[byte + 1] |= (unsigned char)(encoded_index >> (8 - shift));
                pair[byte + 2] |= (unsigned char)(encoded_index >> (16 - shift));
            }
            e32(pair + count * width - 4, base);
            n += count; offset += count * width;
        }
        error = e_write(w->output_fd, compact, (size_t)i->map_size, e_align(4096 + i->nid * 32 + 64 + i->attrs_size, 8));
    }
    if (!error && !i->virtual_data) {
        if (fstat(fd, &st)) error = errno;
        else if (st.st_size != i->st.st_size || st.st_mtim.tv_sec != i->st.st_mtim.tv_sec || st.st_mtim.tv_nsec != i->st.st_mtim.tv_nsec || st.st_ctim.tv_sec != i->st.st_ctim.tv_sec || st.st_ctim.tv_nsec != i->st.st_ctim.tv_nsec) error = ESTALE;
    }
    free(map);free(compact);free(input);free(encoded);free(output);close(fd);return error;
}
static int e_image(EWriter *w) {
    int error = e_dirs(w->root, -1);
    uint64_t metadata = 0;
    for (size_t n = 0; !error && n < w->count; ++n) {
        EInode *i = w->inodes[n];
        if ((metadata & 4095) == 4064) metadata += 32;
        i->nid = metadata / 32;
        if (w->compression && S_ISREG(i->st.st_mode) && i->size) {
            uint64_t clusters = e_align(i->size, 4096) / 4096;
            i->map_size = 8 + e_align(clusters, 2) * 4 - e_compact_middle(i, clusters) * 2;
        }
        metadata = e_align(metadata + (i->map_size ? e_align(64 + i->attrs_size, 8) + i->map_size : 64 + i->attrs_size), 32);
    }
    uint64_t position = 4096 + e_align(metadata, 4096);
    for (size_t n = 0; !error && n < w->count; ++n) {
        EInode *i = w->inodes[n];
        if (position / 4096 >= UINT32_MAX || (!i->map_size && (i->size > w->maximum || position > w->maximum - i->size))) { error = EFBIG; break; }
        i->block = (uint32_t)(position / 4096);
        if (i->map_size) {
            w->position = position; error = e_compress(w, i); position = w->position;
        } else position += e_align(i->size, 4096);
    }
    if (error) return error;
    if (position > w->maximum || position / 4096 >= UINT32_MAX) return EFBIG;
    if (ftruncate(w->output_fd, (off_t)position)) return errno;
    unsigned char super[128] = {0};
    e32(super, 0xe0f5e1e2); e32(super + 8, 2); super[12] = 12;
    e64(super + 16, w->count); e32(super + 36, (uint32_t)(position / 4096)); e32(super + 40, 1);
    if (w->compression) { e32(super + 80, 3); e16(super + 84, w->compression == 1 ? 8 : 1); }
    error = e_write(w->output_fd, super, sizeof(super), 1024);
    if (!error && w->compression) {
        unsigned char config[16] = {0};
        if (w->compression == 1) { e16(config, 6); config[3] = 9; }
        else { e16(config, 14); e16(config + 2, 65535); e16(config + 4, 16); }
        error = e_write(w->output_fd, config, w->compression == 1 ? 8 : 16, 1152);
    }
    for (size_t n = 0; !error && n < w->count; ++n) {
        EInode *i = w->inodes[n];
        unsigned char inode[64] = {0};
        e16(inode, i->map_size ? 7 : 1); e16(inode + 2, i->attrs_size ? (uint16_t)((i->attrs_size - 12) / 4 + 1) : 0);
        e16(inode + 4, (uint16_t)i->st.st_mode); e64(inode + 8, i->size);
        uint32_t device = i->map_size ? i->stored_blocks : i->block;
        if (S_ISCHR(i->st.st_mode) || S_ISBLK(i->st.st_mode)) {
            unsigned ma = major(i->st.st_rdev), mi = minor(i->st.st_rdev);
            if (ma > 4095 || mi > 1048575) { error = EOVERFLOW; break; }
            device = (mi & 255) | (ma << 8) | ((mi & ~255u) << 12);
        }
        e32(inode + 16, device); e32(inode + 20, (uint32_t)n + 1);
        e32(inode + 24, i->st.st_uid); e32(inode + 28, i->st.st_gid);
        e64(inode + 32, (uint64_t)i->st.st_mtim.tv_sec); e32(inode + 40, (uint32_t)i->st.st_mtim.tv_nsec); e32(inode + 44, i->links);
        uint64_t at = 4096 + i->nid * 32;
        error = e_write(w->output_fd, inode, sizeof(inode), at);
        if (!error && i->attrs_size) error = e_write(w->output_fd, i->attrs, i->attrs_size, at + 64);
        if (!error && S_ISREG(i->st.st_mode) && !i->map_size) error = e_copy(w, i);
        if (!error && S_ISLNK(i->st.st_mode)) error = e_write(w->output_fd, i->link, (size_t)i->size, (uint64_t)i->block * 4096);
    }
    if (!error) error = e_dirs(w->root, w->output_fd);
    return error;
}
static void e_free_node(ENode *node) {
    if (!node) return;
    for (size_t n = 0; n < node->count; ++n) e_free_node(node->children[n]);
    free(node->children); free(node->buckets); free(node->name); free(node);
}
static void e_free(EWriter *w) {
    e_free_node(w->root);
    for (size_t n = 0; n < w->count; ++n) {
        EInode *i = w->inodes[n]; free(i->source); free(i->link); free(i->attrs); free(i);
    }
    free(w->inodes); ZSTD_freeCCtx(w->codec); free(w);
}
static int e_directory_image(const char *source, const char *destination, long long compression, long long level, long long maximum) {
    if (compression != 0 && compression != 1 && compression != 2) return ENOTSUP;
    if (compression == 1 && (level < ZSTD_minCLevel() || level > ZSTD_maxCLevel())) return EINVAL;
    if (maximum < 4096 || maximum > 17592186040320ll) return EINVAL;
    EWriter *w = calloc(1, sizeof(*w));
    if (!w) return ENOMEM;
    w->source_fd = open(source, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (w->source_fd < 0) { int error = errno; free(w); return error; }
    w->maximum = (uint64_t)maximum; w->compression = (int)compression; w->level = (int)level; w->root = calloc(1, sizeof(*w->root));
    int error = w->root ? 0 : ENOMEM;
    if (compression == 1) { w->codec = ZSTD_createCCtx(); if (!w->codec) error = ENOMEM; }
    if (!error) { w->root->name = strdup(""); if (!w->root->name) error = ENOMEM; }
    if (!error) error = e_scan(w, w->root, w->source_fd, "", 0);
    char *temporary = NULL;
    w->output_fd = -1;
    if (!error && asprintf(&temporary, "%s.erofs-XXXXXX", destination) < 0) error = ENOMEM;
    if (!error) { w->output_fd = mkstemp(temporary); if (w->output_fd < 0) error = errno; }
    if (!error) error = e_image(w);
    if (!error && fchmod(w->output_fd, 0644)) error = errno;
    if (w->output_fd >= 0 && close(w->output_fd) && !error) error = errno;
    if (!error && rename(temporary, destination)) error = errno;
    if (error && temporary) unlink(temporary);
    free(temporary); close(w->source_fd); e_free(w); return error;
}
#include "erofs_layers.h"
static char *e_text(const MinyarText *text) {
    if (!text || text->byte_length <= 0 || text->byte_length > 1048576 || memchr(text->bytes, 0, (size_t)text->byte_length)) return NULL;
    return strndup((const char *)text->bytes, (size_t)text->byte_length);
}
static MinyarBytes *e_result(int error) {
    const char *message = error ? strerror(error) : "";
    size_t length = strlen(message);
    MinyarBytes *result = minyar_bytes_new((long long)length + 8);
    e64((unsigned char *)result->bytes, (uint64_t)error);
    memcpy((unsigned char *)result->bytes + 8, message, length);
    return result;
}
MinyarBytes *minyar_erofs_directoryStatus(const MinyarText *source, const MinyarText *destination, long long compression, long long level, long long maximum) {
    char *s = e_text(source), *d = e_text(destination);
    int error = s && d ? e_directory_image(s, d, compression, level, maximum) : EINVAL;
    free(s);free(d);return e_result(error);
}
MinyarBytes *minyar_erofs_layersStatus(const MinyarBytes *paths, const MinyarText *destination, long long compression, long long level, long long maximum) {
    char *d = e_text(destination);
    int error = d ? e_layers_image(paths, d, compression, level, maximum) : EINVAL;
    free(d);return e_result(error);
}
