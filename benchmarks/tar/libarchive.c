/* Maintained-libarchive oracle and full metadata/payload-copy/write reference.
 * No extraction. Build: clang -O2 libarchive.c $(pkg-config --cflags --libs libarchive)
 */
#include <archive.h>
#include <archive_entry.h>
#include <inttypes.h>
#include <locale.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void hex(const void *p, size_t n) {
    const unsigned char *s = p;
    for (size_t i = 0; i < n; ++i) printf("%02x", s[i]);
}
static unsigned char *load(const char *path, size_t *length) {
    FILE *f = fopen(path,"rb"); if (!f) exit(2);
    if (fseek(f,0,SEEK_END)) exit(2);
    long n = ftell(f); if (n < 0 || fseek(f,0,SEEK_SET)) exit(2);
    unsigned char *p = malloc((size_t)n + 1); if (!p) exit(2);
    if (fread(p,1,(size_t)n,f) != (size_t)n || fclose(f)) exit(2);
    *length = (size_t)n; return p;
}
static int type(struct archive_entry *e) {
    if (archive_entry_hardlink(e)) return '1';
    switch (archive_entry_filetype(e)) {
        case AE_IFREG: return '0'; case AE_IFLNK: return '2';
        case AE_IFCHR: return '3'; case AE_IFBLK: return '4';
        case AE_IFDIR: return '5'; case AE_IFIFO: return '6'; default: return '?';
    }
}
static const char *linkname(struct archive_entry *e) {
    const char *s = archive_entry_hardlink(e);
    if (!s) s = archive_entry_hardlink_utf8(e);
    if (!s) s = archive_entry_symlink(e);
    if (!s) s = archive_entry_symlink_utf8(e);
    return s ? s : "";
}
static uint64_t run(const unsigned char *source, size_t length, int dump, size_t index, int write) {
    struct archive *a = archive_read_new();
    archive_read_support_filter_none(a); archive_read_support_format_tar(a);
    int code = archive_read_open_memory(a,source,length);
    uint64_t sum = 0;
    struct archive *w = NULL; unsigned char *out = NULL; size_t used = 0;
    if (write) {
        w = archive_write_new(); archive_write_set_format_pax_restricted(w);
        archive_write_set_bytes_per_block(w,512); archive_write_set_bytes_in_last_block(w,1);
        size_t cap = length * 2 + 1048576; out = malloc(cap); if (!out) exit(2);
        if (archive_write_open_memory(w,out,cap,&used) != ARCHIVE_OK) exit(2);
    }
    struct archive_entry *e = NULL;
    while (code >= ARCHIVE_WARN && (code = archive_read_next_header(a,&e)) != ARCHIVE_EOF) {
        if (code < ARCHIVE_WARN) break;
        int kind = type(e); int64_t size = archive_entry_size(e);
        if (size < 0 || (uint64_t)size > length) { code = ARCHIVE_FATAL; break; }
        size_t n = kind == '0' ? (size_t)size : 0;
        unsigned char *data = malloc(n + 1); if (!data) exit(2);
        size_t at = 0;
        while (at < n) {
            la_ssize_t got = archive_read_data(a,data+at,n-at);
            if (got <= 0) { code = ARCHIVE_FATAL; break; }
            at += (size_t)got;
        }
        if (at != n) { free(data); break; }
        const char *path = archive_entry_pathname(e); if (!path) path = "";
        const char *link = linkname(e);
        int64_t seconds = archive_entry_mtime(e); long nanos = archive_entry_mtime_nsec(e);
        if (nanos < 0) { --seconds; nanos += 1000000000; }
        sum += strlen(path) + strlen(link) + archive_entry_perm(e) + (uint64_t)archive_entry_uid(e) +
            (uint64_t)archive_entry_gid(e) + (uint64_t)seconds + (uint64_t)nanos + kind + (uint64_t)size +
            archive_entry_rdevmajor(e) + archive_entry_rdevminor(e);
        const char *uname = archive_entry_uname(e), *gname = archive_entry_gname(e);
        if (!uname) uname = archive_entry_uname_utf8(e);
        if (!gname) gname = archive_entry_gname_utf8(e);
        sum += uname ? strlen(uname) : 0; sum += gname ? strlen(gname) : 0;
        const char *attr; const void *val; size_t vlen;
        archive_entry_xattr_reset(e);
        while (archive_entry_xattr_next(e,&attr,&val,&vlen) == ARCHIVE_OK) sum += strlen(attr) + vlen;
        if (n) sum += data[0] + data[n-1];
        if (dump) {
            printf("%zu|ENTRY|",index); hex(path,strlen(path)); putchar('|'); hex(link,strlen(link));
            printf("|%d|%" PRId64 "|%" PRId64 "|%" PRId64 "|%ld|%d|%" PRId64 "|%" PRId64 "|%" PRId64 "|",
                   (int)archive_entry_perm(e),(int64_t)archive_entry_uid(e),(int64_t)archive_entry_gid(e),seconds,nanos,kind,size,
                   (int64_t)archive_entry_rdevmajor(e),(int64_t)archive_entry_rdevminor(e));
            hex(data,n); putchar('|'); hex(uname ? uname : "",uname ? strlen(uname) : 0);
            putchar('|'); hex(gname ? gname : "",gname ? strlen(gname) : 0); putchar('\n');
            archive_entry_xattr_reset(e);
            while (archive_entry_xattr_next(e,&attr,&val,&vlen) == ARCHIVE_OK) {
                printf("%zu|XATTR|",index); hex(path,strlen(path)); putchar('|'); hex(attr,strlen(attr)); putchar('|'); hex(val,vlen); putchar('\n');
            }
        }
        if (w) {
            if (archive_write_header(w,e) < ARCHIVE_WARN || (n && archive_write_data(w,data,n) != (la_ssize_t)n)) exit(3);
        }
        free(data);
    }
    if (dump) printf("%zu|%s\n",index,code == ARCHIVE_EOF ? "END" : "ERROR");
    archive_read_free(a);
    if (w) { if (archive_write_close(w) != ARCHIVE_OK) exit(3); archive_write_free(w); sum += used; free(out); }
    return sum;
}
int main(int argc, char **argv) {
    setlocale(LC_ALL,"");
    if (argc == 2 && !strcmp(argv[1],"version")) { printf("%d\n%s\n",archive_version_number(),archive_version_string()); return 0; }
    if (argc < 3) return 2;
    size_t n; unsigned char *p = load(argv[2],&n);
    uint64_t sum = 0;
    if (!strcmp(argv[1],"corpus")) {
        size_t at = 0, index = 0;
        while (at < n) {
            if (n-at < 4) return 2;
            size_t size = p[at] | (size_t)p[at+1]<<8 | (size_t)p[at+2]<<16 | (size_t)p[at+3]<<24;
            at += 4; if (size > n-at) return 2;
            run(p+at,size,1,index++,0); at += size;
        }
    } else if (!strcmp(argv[1],"verify")) run(p,n,1,0,0);
    else if (!strcmp(argv[1],"read") || !strcmp(argv[1],"roundtrip")) {
        int repeat = argc > 3 ? atoi(argv[3]) : 1; if (repeat < 1) return 2;
        for (int i=0;i<repeat;i++) sum += run(p,n,0,0,!strcmp(argv[1],"roundtrip"));
        printf("%" PRIu64 "\n",sum);
    } else return 2;
    free(p); return 0;
}
