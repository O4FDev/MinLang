#define _GNU_SOURCE
#include "../minyar_native.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <linux/openat2.h>
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
    EInode *hash_next;
};
struct ENode {
    char *name;
    EInode *inode;
    ENode *parent;
    ENode **children;
    size_t count, capacity;
};
typedef struct {
    EInode **inodes;
    size_t count, capacity;
    EInode *hash[65536];
    ENode *root;
    int source_fd, output_fd;
    uint64_t maximum, position;
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
    int fd = (int)syscall(SYS_openat2, w->source_fd, i->source, &how, sizeof(how));
    if (fd < 0) return errno;
    struct stat st;
    int error = fstat(fd, &st) ? errno : 0;
    if (!error && (st.st_ino != i->st.st_ino || st.st_dev != i->st.st_dev || st.st_size != i->st.st_size || !S_ISREG(st.st_mode))) error = ESTALE;
    off_t input = 0, output = (off_t)i->block * 4096;
    uint64_t remaining = i->size;
    unsigned char *buffer = NULL;
    while (!error && remaining) {
        size_t count = remaining > 1048576 ? 1048576 : (size_t)remaining;
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
    if (!error) {
        if (fstat(fd, &st)) error = errno;
        else if (st.st_size != i->st.st_size || st.st_mtim.tv_sec != i->st.st_mtim.tv_sec || st.st_mtim.tv_nsec != i->st.st_mtim.tv_nsec || st.st_ctim.tv_sec != i->st.st_ctim.tv_sec || st.st_ctim.tv_nsec != i->st.st_ctim.tv_nsec) error = ESTALE;
    }
    free(buffer); close(fd); return error;
}
static int e_image(EWriter *w) {
    int error = e_dirs(w->root, -1);
    uint64_t metadata = 0;
    for (size_t n = 0; !error && n < w->count; ++n) {
        EInode *i = w->inodes[n];
        if ((metadata & 4095) == 4064) metadata += 32;
        i->nid = metadata / 32;
        metadata = e_align(metadata + 64 + i->attrs_size, 32);
    }
    uint64_t position = 4096 + e_align(metadata, 4096);
    for (size_t n = 0; !error && n < w->count; ++n) {
        EInode *i = w->inodes[n];
        if (position / 4096 >= UINT32_MAX || i->size > w->maximum || position > w->maximum - i->size) { error = EFBIG; break; }
        i->block = (uint32_t)(position / 4096); position += e_align(i->size, 4096);
    }
    if (error) return error;
    if (position > w->maximum || position / 4096 >= UINT32_MAX) return EFBIG;
    if (ftruncate(w->output_fd, (off_t)position)) return errno;
    unsigned char super[128] = {0};
    e32(super, 0xe0f5e1e2); e32(super + 8, 2); super[12] = 12;
    e64(super + 16, w->count); e32(super + 36, (uint32_t)(position / 4096)); e32(super + 40, 1);
    error = e_write(w->output_fd, super, sizeof(super), 1024);
    for (size_t n = 0; !error && n < w->count; ++n) {
        EInode *i = w->inodes[n];
        unsigned char inode[64] = {0};
        e16(inode, 1); e16(inode + 2, i->attrs_size ? (uint16_t)((i->attrs_size - 12) / 4 + 1) : 0);
        e16(inode + 4, (uint16_t)i->st.st_mode); e64(inode + 8, i->size);
        uint32_t device = i->block;
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
        if (!error && S_ISREG(i->st.st_mode)) error = e_copy(w, i);
        if (!error && S_ISLNK(i->st.st_mode)) error = e_write(w->output_fd, i->link, (size_t)i->size, (uint64_t)i->block * 4096);
    }
    if (!error) error = e_dirs(w->root, w->output_fd);
    return error;
}
static void e_free_node(ENode *node) {
    if (!node) return;
    for (size_t n = 0; n < node->count; ++n) e_free_node(node->children[n]);
    free(node->children); free(node->name); free(node);
}
static void e_free(EWriter *w) {
    e_free_node(w->root);
    for (size_t n = 0; n < w->count; ++n) {
        EInode *i = w->inodes[n]; free(i->source); free(i->link); free(i->attrs); free(i);
    }
    free(w->inodes); free(w);
}
static int e_directory_image(const char *source, const char *destination, long long compression, long long level, long long maximum) {
    (void)level;
    if (compression != 0) return ENOTSUP;
    if (maximum < 4096 || maximum > 17592186040320ll) return EINVAL;
    EWriter *w = calloc(1, sizeof(*w));
    if (!w) return ENOMEM;
    w->source_fd = open(source, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (w->source_fd < 0) { int error = errno; free(w); return error; }
    w->maximum = (uint64_t)maximum; w->root = calloc(1, sizeof(*w->root));
    int error = w->root ? 0 : ENOMEM;
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
static char *e_text(const MinyarText *text) {
    if (!text || text->byte_length <= 0 || text->byte_length > 1048576 || memchr(text->bytes, 0, (size_t)text->byte_length)) return NULL;
    return strndup((const char *)text->bytes, (size_t)text->byte_length);
}
MinyarBytes *minyar_erofs_directoryStatus(const MinyarText *source, const MinyarText *destination, long long compression, long long level, long long maximum) {
    char *s = e_text(source), *d = e_text(destination);
    int error = s && d ? e_directory_image(s, d, compression, level, maximum) : EINVAL;
    free(s); free(d);
    const char *message = error ? strerror(error) : "";
    size_t length = strlen(message);
    MinyarBytes *result = minyar_bytes_new((long long)length + 8);
    e64((unsigned char *)result->bytes, (uint64_t)error);
    memcpy((unsigned char *)result->bytes + 8, message, length);
    return result;
}
