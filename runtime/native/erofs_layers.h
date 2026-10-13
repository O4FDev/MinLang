#include <archive.h>
#include <archive_entry.h>

typedef struct {
    char *path, *target;
    uint64_t id;
    unsigned char *attrs;
    size_t attrs_size;
} ELink;
typedef struct { ELink *links; size_t count, capacity; uint64_t next_id; } ELayer;

static int e_normalize(const char *path, char **result) {
    if (!path || *path == '/') return EINVAL;
    size_t length = strnlen(path, 1048577);
    if (length > 1048576) return ENAMETOOLONG;
    char *out = malloc(length + 1);
    if (!out) return ENOMEM;
    size_t at = 0, written = 0;
    unsigned depth = 0;
    while (at < length) {
        while (at < length && path[at] == '/') ++at;
        size_t first = at;
        while (at < length && path[at] != '/') ++at;
        size_t size = at - first;
        if (!size || (size == 1 && path[first] == '.')) continue;
        if (size == 2 && !memcmp(path + first, "..", 2)) { free(out); return EINVAL; }
        if (size > 255 || ++depth > 256) { free(out); return ENAMETOOLONG; }
        if (written) out[written++] = '/';
        memcpy(out + written, path + first, size); written += size;
    }
    out[written] = 0; *result = out; return 0;
}
static uint64_t e_name_hash(const char *name) {
    uint64_t hash = 1469598103934665603ull;
    for (const unsigned char *p = (const unsigned char *)name; *p; ++p) hash = (hash ^ *p) * 1099511628211ull;
    return hash;
}
static ENode *e_child(ENode *parent, const char *name) {
    if (!parent->bucket_count) return NULL;
    size_t bucket = (size_t)e_name_hash(name) & (parent->bucket_count - 1);
    for (ENode *node = parent->buckets[bucket]; node; node = node->hash_next) if (!strcmp(node->name, name)) return node;
    return NULL;
}
static int e_add_child(ENode *parent, const char *name, ENode **result) {
    if (!parent->bucket_count || parent->count + 1 > parent->bucket_count / 2) {
        size_t count = parent->bucket_count ? parent->bucket_count * 2 : 16;
        ENode **buckets = calloc(count, sizeof(*buckets));
        if (!buckets) return ENOMEM;
        for (size_t n = 0; n < parent->count; ++n) {
            ENode *node = parent->children[n]; size_t bucket = (size_t)e_name_hash(node->name) & (count - 1);
            node->hash_next = buckets[bucket]; buckets[bucket] = node;
        }
        free(parent->buckets); parent->buckets = buckets; parent->bucket_count = count;
    }
    int error = e_grow((void **)&parent->children, &parent->capacity, parent->count + 1, sizeof(*parent->children));
    if (error) return error;
    ENode *node = calloc(1, sizeof(*node));
    if (!node) return ENOMEM;
    node->name = strdup(name);
    if (!node->name) { free(node); return ENOMEM; }
    node->parent = parent; node->child_index = parent->count;
    parent->children[parent->count++] = node;
    size_t bucket = (size_t)e_name_hash(name) & (parent->bucket_count - 1);
    node->hash_next = parent->buckets[bucket]; parent->buckets[bucket] = node;
    *result = node; return 0;
}
static void e_clear_children(ENode *node) {
    for (size_t n = 0; n < node->count; ++n) e_free_node(node->children[n]);
    node->count = 0;
    if (node->bucket_count) memset(node->buckets, 0, node->bucket_count * sizeof(*node->buckets));
}
static EInode *e_virtual_inode(EWriter *w) {
    if (w->count >= 1000000 || e_grow((void **)&w->inodes, &w->capacity, w->count + 1, sizeof(*w->inodes))) return NULL;
    EInode *inode = calloc(1, sizeof(*inode));
    if (!inode) return NULL;
    inode->virtual_data = 1; inode->st.st_mode = S_IFDIR | 0755;
    inode->st.st_ino = w->count + 1;
    w->inodes[w->count++] = inode; return inode;
}
static int e_path(EWriter *w, const char *path, uint64_t layer, int create, ENode **result) {
    char *copy = strdup(path);
    if (!copy) return ENOMEM;
    ENode *node = w->root;
    int error = 0;
    char *at = copy;
    while (*at) {
        char *end = strchr(at, '/'); if (end) *end = 0;
        if (!node->inode || !S_ISDIR(node->inode->st.st_mode)) {
            if (!create) { node = NULL; break; }
            e_clear_children(node); node->inode = e_virtual_inode(w); node->pending_id = 0; node->generation = layer;
            if (!node->inode) { error = ENOMEM; break; }
        }
        ENode *child = e_child(node, at);
        if (!child && create) {
            error = e_add_child(node, at, &child);
            if (error) break;
            if (end) child->inode = e_virtual_inode(w);
            child->generation = layer;
            if (end && !child->inode) { error = ENOMEM; break; }
        }
        if (!child) { node = NULL; break; }
        node = child;
        if (!end) break;
        at = end + 1;
    }
    free(copy); *result = node; return error;
}
static void e_delete_child(ENode *node) {
    ENode *parent = node->parent;
    size_t bucket = (size_t)e_name_hash(node->name) & (parent->bucket_count - 1);
    ENode **link = &parent->buckets[bucket];
    while (*link != node) link = &(*link)->hash_next;
    *link = node->hash_next;
    ENode *last = parent->children[--parent->count];
    if (last != node) { parent->children[node->child_index] = last; last->child_index = node->child_index; }
    e_free_node(node);
}
static int e_remove_lower(ENode *node, uint64_t layer) {
    for (size_t n = 0; n < node->count;) {
        if (!e_remove_lower(node->children[n], layer)) ++n;
    }
    if (node->parent && node->generation < layer && !node->count) { e_delete_child(node); return 1; }
    return 0;
}
static int e_acl_order(const void *a, const void *b) {
    const unsigned char *x = a, *y = b;
    unsigned xt = x[0] | (unsigned)x[1] << 8, yt = y[0] | (unsigned)y[1] << 8;
    if (xt != yt) return xt < yt ? -1 : 1;
    uint32_t xi = x[4] | (uint32_t)x[5] << 8 | (uint32_t)x[6] << 16 | (uint32_t)x[7] << 24;
    uint32_t yi = y[4] | (uint32_t)y[5] << 8 | (uint32_t)y[6] << 16 | (uint32_t)y[7] << 24;
    return xi < yi ? -1 : xi > yi;
}
static int e_archive_acl(struct archive_entry *entry, int wanted, const char *key) {
    if (!(archive_entry_acl_types(entry) & wanted)) return 0;
    int count = archive_entry_acl_reset(entry, wanted);
    if (count < 1 || count > 8191) return EOVERFLOW;
    unsigned char *data = calloc(1, 4 + (size_t)count * 8);
    if (!data) return ENOMEM;
    e32(data, 2);
    size_t used = 0;
    int error = 0, type, perm, tag, qualifier, status;
    const char *name;
    while ((status = archive_entry_acl_next(entry, wanted, &type, &perm, &tag, &qualifier, &name)) == ARCHIVE_OK) {
        unsigned code;
        uint32_t id = UINT32_MAX;
        if (used >= (size_t)count || type != wanted || (perm & ~7)) { error = EINVAL; break; }
        if (tag == ARCHIVE_ENTRY_ACL_USER_OBJ) code = 1;
        else if (tag == ARCHIVE_ENTRY_ACL_USER) code = 2;
        else if (tag == ARCHIVE_ENTRY_ACL_GROUP_OBJ) code = 4;
        else if (tag == ARCHIVE_ENTRY_ACL_GROUP) code = 8;
        else if (tag == ARCHIVE_ENTRY_ACL_MASK) code = 16;
        else if (tag == ARCHIVE_ENTRY_ACL_OTHER) code = 32;
        else { error = ENOTSUP; break; }
        if (code == 2 || code == 8) { if (qualifier < 0) { error = ENOTSUP; break; } id = (uint32_t)qualifier; }
        unsigned char *p = data + 4 + used++ * 8; e16(p, (uint16_t)code); e16(p + 2, (uint16_t)perm); e32(p + 4, id);
    }
    if (!error && status != ARCHIVE_EOF) error = EINVAL;
    if (!error) { qsort(data + 4, used, 8, e_acl_order); archive_entry_xattr_add_entry(entry, key, data, 4 + used * 8); }
    free(data); return error;
}
static int e_archive_attrs(EInode *inode, struct archive_entry *entry) {
    if (archive_entry_acl_types(entry) & ARCHIVE_ENTRY_ACL_TYPE_NFS4) return ENOTSUP;
    int error = e_archive_acl(entry, ARCHIVE_ENTRY_ACL_TYPE_ACCESS, "system.posix_acl_access");
    if (!error) error = e_archive_acl(entry, ARCHIVE_ENTRY_ACL_TYPE_DEFAULT, "system.posix_acl_default");
    if (error) return error;
    int count = archive_entry_xattr_reset(entry);
    if (!count) return 0;
    size_t capacity = 0, size = 12;
    error = e_grow((void **)&inode->attrs, &capacity, size, 1);
    if (error) return error;
    memset(inode->attrs, 0, size);
    const char *name; const void *value; size_t value_size;
    while (archive_entry_xattr_next(entry, &name, &value, &value_size) == ARCHIVE_OK) {
        const char *suffix = name; unsigned index;
        if (!strncmp(name, "user.", 5)) { index = 1; suffix += 5; }
        else if (!strcmp(name, "system.posix_acl_access")) { index = 2; suffix += strlen(name); }
        else if (!strcmp(name, "system.posix_acl_default")) { index = 3; suffix += strlen(name); }
        else if (!strncmp(name, "trusted.", 8)) { index = 4; suffix += 8; }
        else if (!strncmp(name, "security.", 9)) { index = 6; suffix += 9; }
        else return ENOTSUP;
        size_t name_size = strlen(suffix);
        if (name_size > 255 || value_size > 65535) return EOVERFLOW;
        for (size_t at = 12; at < size;) {
            unsigned char *old = inode->attrs + at;
            size_t old_size = (size_t)e_align(4 + old[0] + (unsigned)old[2] + ((unsigned)old[3] << 8), 4);
            if (old[1] == index && old[0] == name_size && !memcmp(old + 4, suffix, name_size)) { memmove(old, old + old_size, size - at - old_size); size -= old_size; break; }
            at += old_size;
        }
        size_t length = (size_t)e_align(4 + name_size + value_size, 4);
        if (length > 262148 - size) return EOVERFLOW;
        error = e_grow((void **)&inode->attrs, &capacity, size + length, 1);
        if (error) return error;
        unsigned char *p = inode->attrs + size; memset(p, 0, length);
        p[0] = (unsigned char)name_size; p[1] = index; e16(p + 2, (uint16_t)value_size);
        memcpy(p + 4, suffix, name_size); if (value_size) memcpy(p + 4 + name_size, value, value_size);
        size += length;
    }
    inode->attrs_size = size; return 0;
}
static int e_archive_inode(EWriter *w, struct archive_entry *entry, EInode **result) {
    int64_t uid = archive_entry_uid(entry), gid = archive_entry_gid(entry), size = archive_entry_size(entry);
    long nanos = archive_entry_mtime_nsec(entry);
    mode_t mode = archive_entry_mode(entry);
    if (uid < 0 || (uint64_t)uid >= UINT32_MAX || gid < 0 || (uint64_t)gid >= UINT32_MAX || size < 0 || (uint64_t)size > 17592186040320ull || nanos < 0 || nanos >= 1000000000) return EOVERFLOW;
    if (!e_type(mode)) return ENOTSUP;
    EInode *inode = e_virtual_inode(w);
    if (!inode) return ENOMEM;
    inode->st.st_mode = mode; inode->st.st_uid = (uid_t)uid; inode->st.st_gid = (gid_t)gid;
    inode->st.st_mtim.tv_sec = archive_entry_mtime(entry); inode->st.st_mtim.tv_nsec = nanos;
    inode->size = S_ISREG(mode) ? (uint64_t)size : 0; inode->st.st_size = (off_t)inode->size;
    if (S_ISLNK(mode)) {
        const char *target = archive_entry_symlink(entry);
        if (!target || !*target || strlen(target) > 4095) return EINVAL;
        inode->link = strdup(target);
        if (!inode->link) return ENOMEM;
        inode->size = strlen(target); inode->st.st_size = (off_t)inode->size;
    } else if (S_ISCHR(mode) || S_ISBLK(mode)) {
        int64_t ma = archive_entry_rdevmajor(entry), mi = archive_entry_rdevminor(entry);
        if (ma < 0 || ma > 4095 || mi < 0 || mi > 1048575) return EOVERFLOW;
        inode->st.st_rdev = makedev((unsigned)ma, (unsigned)mi);
    }
    int error = e_archive_attrs(inode, entry);
    if (!error) *result = inode;
    return error;
}
static int e_layer_link(ELayer *layer, const char *path, const char *target, ENode *node, struct archive_entry *entry) {
    int error = e_grow((void **)&layer->links, &layer->capacity, layer->count + 1, sizeof(*layer->links));
    if (error) return error;
    ELink *link = &layer->links[layer->count++]; memset(link, 0, sizeof(*link));
    link->path = strdup(path); error = e_normalize(target, &link->target);
    if (!link->path) return ENOMEM;
    if (error) return error;
    link->id = ++layer->next_id; node->pending_id = link->id; node->inode = NULL;
    EInode attrs = {0}; error = e_archive_attrs(&attrs, entry);
    link->attrs = attrs.attrs; link->attrs_size = attrs.attrs_size; return error;
}
static int e_resolve_links(EWriter *w, ELayer *layer, uint64_t generation) {
    size_t remaining = layer->count;
    while (remaining) {
        size_t previous = remaining;
        for (size_t n = 0; n < layer->count; ++n) {
            ELink *link = &layer->links[n]; if (!link->id) continue;
            ENode *node = NULL, *target = NULL;
            int error = e_path(w, link->path, generation, 0, &node);
            if (error) return error;
            if (!node || node->pending_id != link->id) { link->id = 0; --remaining; continue; }
            error = e_path(w, link->target, generation, 0, &target);
            if (error) return error;
            if (!target || !target->inode) continue;
            if (S_ISDIR(target->inode->st.st_mode)) return EINVAL;
            node->inode = target->inode; node->pending_id = 0; link->id = 0; --remaining;
            if (link->attrs_size) { free(target->inode->attrs); target->inode->attrs = link->attrs; target->inode->attrs_size = link->attrs_size; link->attrs = NULL; }
        }
        if (previous == remaining) return EINVAL;
    }
    return 0;
}
static int e_apply_layer(EWriter *w, const char *path, uint64_t generation) {
    struct archive *reader = archive_read_new();
    if (!reader) return ENOMEM;
    int error = 0;
    if (archive_read_support_format_tar(reader) != ARCHIVE_OK || archive_read_support_filter_none(reader) != ARCHIVE_OK || archive_read_support_filter_gzip(reader) != ARCHIVE_OK || archive_read_support_filter_zstd(reader) != ARCHIVE_OK) error = ENOTSUP;
    if (!error && archive_read_open_filename(reader, path, 1048576) != ARCHIVE_OK) error = EINVAL;
    ELayer layer = {0};
    unsigned char *buffer = malloc(1048576);
    if (!buffer) error = ENOMEM;
    struct archive_entry *entry;
    size_t headers = 0;
    while (!error) {
        int status = archive_read_next_header(reader, &entry);
        if (status == ARCHIVE_EOF) break;
        if (status != ARCHIVE_OK || ++headers > 1000000) { error = EINVAL; break; }
        char *name = NULL;
        error = e_normalize(archive_entry_pathname(entry), &name);
        if (error) break;
        char *base = strrchr(name, '/'); base = base ? base + 1 : name;
        if (!strncmp(base, ".wh.", 4)) {
            if (archive_entry_size(entry) != 0 || !(archive_entry_filetype(entry) == AE_IFREG || (archive_entry_filetype(entry) == AE_IFCHR && !archive_entry_rdevmajor(entry) && !archive_entry_rdevminor(entry)))) error = EINVAL;
            if (!error) {
                char *parent = strdup(name);
                if (!parent) error = ENOMEM;
                else {
                    char *slash = strrchr(parent, '/'); if (slash) *slash = 0; else *parent = 0;
                    ENode *directory = NULL; error = e_path(w, parent, generation, 1, &directory);
                    if (!error && (!directory->inode || !S_ISDIR(directory->inode->st.st_mode))) {
                        e_clear_children(directory); directory->inode = e_virtual_inode(w); directory->pending_id = 0; directory->generation = generation;
                        if (!directory->inode) error = ENOMEM;
                    }
                    if (!error && !strcmp(base, ".wh..wh..opq")) {
                        for (size_t n = 0; n < directory->count;) if (!e_remove_lower(directory->children[n], generation)) ++n;
                    } else if (!error) {
                        if (!base[4] || !strcmp(base + 4, ".") || !strcmp(base + 4, "..")) error = EINVAL;
                        else { ENode *old = e_child(directory, base + 4); if (old) e_remove_lower(old, generation); }
                    }
                    free(parent);
                }
            }
        } else {
            ENode *node = NULL; error = e_path(w, name, generation, 1, &node);
            const char *hardlink = archive_entry_hardlink(entry);
            if (!error && !*name && (archive_entry_filetype(entry) != AE_IFDIR || hardlink)) error = EINVAL;
            if (!error) {
                if (hardlink || archive_entry_filetype(entry) != AE_IFDIR) e_clear_children(node);
                node->generation = generation; node->pending_id = 0;
                if (hardlink) error = e_layer_link(&layer, name, hardlink, node, entry);
                else {
                    EInode *inode = NULL; error = e_archive_inode(w, entry, &inode);
                    if (!error) node->inode = inode;
                    if (!error && S_ISREG(inode->st.st_mode)) {
                        inode->data_offset = w->spool_size;
                        if (inode->size > 17592186040320ull - w->spool_size) error = EFBIG;
                        uint64_t copied = 0;
                        while (!error && copied < inode->size) {
                            size_t want = inode->size - copied > 1048576 ? 1048576 : (size_t)(inode->size - copied);
                            la_ssize_t n = archive_read_data(reader, buffer, want);
                            if (n <= 0) { error = EINVAL; break; }
                            error = e_write(w->data_fd, buffer, (size_t)n, inode->data_offset + copied); copied += (uint64_t)n;
                        }
                        w->spool_size += inode->size;
                    }
                }
            }
        }
        free(name);
        if (!error && archive_read_data_skip(reader) < ARCHIVE_OK) error = EINVAL;
    }
    if (!error) error = e_resolve_links(w, &layer, generation);
    for (size_t n = 0; n < layer.count; ++n) { free(layer.links[n].path); free(layer.links[n].target); free(layer.links[n].attrs); }
    free(layer.links);free(buffer);
    if (archive_read_free(reader) != ARCHIVE_OK && !error) error = EINVAL;
    return error;
}
static int e_count_tree(ENode *node) {
    if (!node->inode) return EINVAL;
    EInode *inode = node->inode;
    if (S_ISDIR(inode->st.st_mode)) inode->links = 2;
    else { if (inode->links == UINT32_MAX) return EOVERFLOW; ++inode->links; }
    if (node->count > 1) qsort(node->children, node->count, sizeof(*node->children), e_order);
    for (size_t n = 0; n < node->count; ++n) {
        int error = e_count_tree(node->children[n]); if (error) return error;
        if (S_ISDIR(node->children[n]->inode->st.st_mode)) ++inode->links;
    }
    return 0;
}
static uint64_t e_read64(const unsigned char *p) {
    uint64_t value = 0;
    for (unsigned n = 0; n < 8; ++n) value |= (uint64_t)p[n] << (n * 8);
    return value;
}
static void e_inode_free(EInode *inode) { free(inode->source);free(inode->link);free(inode->attrs);free(inode); }
static int e_layers_image(const MinyarBytes *paths, const char *destination, long long compression, long long level, long long maximum) {
    if (!paths || paths->byte_length < 8 || compression < 0 || compression > 2 || maximum < 4096 || maximum > 17592186040320ll) return EINVAL;
    if (compression == 1 && (level < ZSTD_minCLevel() || level > ZSTD_maxCLevel())) return EINVAL;
    uint64_t layers = e_read64(paths->bytes);
    if (layers > 1000000) return EINVAL;
    EWriter *w = calloc(1, sizeof(*w));
    if (!w) return ENOMEM;
    w->source_fd = w->data_fd = w->output_fd = -1;
    w->maximum = (uint64_t)maximum; w->compression = (int)compression; w->level = (int)level;
    w->root = calloc(1, sizeof(*w->root));
    int error = w->root ? 0 : ENOMEM;
    if (!error) { w->root->name = strdup(""); w->root->inode = e_virtual_inode(w); if (!w->root->name || !w->root->inode) error = ENOMEM; }
    if (!error && compression == 1) { w->codec = ZSTD_createCCtx(); if (!w->codec) error = ENOMEM; }
    char *spool = NULL, *temporary = NULL;
    if (!error && asprintf(&spool, "%s.layers-XXXXXX", destination) < 0) error = ENOMEM;
    if (!error) { w->data_fd = mkstemp(spool); if (w->data_fd < 0) error = errno; }
    if (spool && w->data_fd >= 0 && unlink(spool) && !error) error = errno;
    size_t at = 8, length = (size_t)paths->byte_length;
    for (uint64_t n = 0; !error && n < layers; ++n) {
        if (at > length || length - at < 8) { error = EINVAL; break; }
        uint64_t size = e_read64(paths->bytes + at); at += 8;
        if (!size || size > 1048576 || size > length - at || memchr(paths->bytes + at, 0, (size_t)size)) { error = EINVAL; break; }
        char *path = strndup((const char *)paths->bytes + at, (size_t)size);
        if (!path) { error = ENOMEM; break; }
        error = e_apply_layer(w, path, n + 1); free(path); at += (size_t)size;
    }
    if (!error && at != length) error = EINVAL;
    if (!error) {
        for (size_t n = 0; n < w->count; ++n) w->inodes[n]->links = 0;
        error = e_count_tree(w->root);
        if (!error) {
            size_t count = 0;
            for (size_t n = 0; n < w->count; ++n) {
                if (w->inodes[n]->links) w->inodes[count++] = w->inodes[n];
                else e_inode_free(w->inodes[n]);
            }
            w->count = count;
        }
    }
    if (!error && asprintf(&temporary, "%s.erofs-XXXXXX", destination) < 0) error = ENOMEM;
    if (!error) { w->output_fd = mkstemp(temporary); if (w->output_fd < 0) error = errno; }
    if (!error) error = e_image(w);
    if (!error && fchmod(w->output_fd, 0644)) error = errno;
    if (w->output_fd >= 0 && close(w->output_fd) && !error) error = errno;
    if (!error && rename(temporary, destination)) error = errno;
    if (error && temporary) unlink(temporary);
    if (error && spool) unlink(spool);
    if (w->data_fd >= 0) close(w->data_fd);
    free(spool);free(temporary);e_free(w);return error;
}
