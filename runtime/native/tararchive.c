#include "../minyar_native.h"
#include <archive.h>
#include <archive_entry.h>
#include <limits.h>
#include <stdint.h>
#include <inttypes.h>
_Static_assert(sizeof(void *)==8 && sizeof(long long)==8 && sizeof(time_t)==8, "tar binding requires the 64-bit native ABI");

typedef struct NativeRecord NativeRecord;
typedef struct NativeList NativeList;
extern NativeRecord *minyar_record_new(long long);
extern long long minyar_record_get(const NativeRecord *, long long);
extern void minyar_record_set_scalar(NativeRecord *, long long, long long);
extern void minyar_record_set_take(NativeRecord *, long long, long long);
extern NativeList *minyar_list_new(void);
extern void minyar_list_references(NativeList *);
extern void minyar_list_add_take(NativeList *, long long);
extern long long minyar_list_length(const NativeList *);
extern long long minyar_list_get(const NativeList *, long long);
extern void minyar_rc_retain(void *);
extern void minyar_rc_release(void *);

typedef struct { const unsigned char *p; size_t n; } Blob;
typedef struct { unsigned char *key, *value; size_t kn, vn; } Attr;
typedef struct { Attr *a; size_t count, bytes; } Attrs;
typedef struct {
    const unsigned char *source; size_t length, position;
    size_t max_path, max_metadata, max_chain, max_headers, headers;
    Attrs globals;
    const char *last_error;
} Reader;
typedef struct {
    struct archive *archive;
    MinyarBytes *output;
    unsigned char *capture; size_t length, cn, cc, maximum;
    int capturing; const char *error;
} Writer;
typedef struct {
    int64_t type, mode, uid, gid, seconds, nanos, size, major, minor;
    Blob path, link, uname, gname; Attrs attrs;
    size_t start, header, offset, end; unsigned char *owned_path;
} Entry;

static MinyarBytes *result(int64_t status, const char *message) {
    size_t n = message ? strlen(message) : 0;
    MinyarBytes *b = minyar_bytes_new((long long)(8+n));
    memcpy((void *)b->bytes,&status,8); if (n) memcpy((void *)(b->bytes+8),message,n);
    return b;
}
static int grow(unsigned char **p, size_t *capacity, size_t need, size_t limit) {
    if (need > limit) return 0;
    if (need <= *capacity) return 1;
    size_t n = *capacity ? *capacity : 512;
    while (n < need) { if (n > limit/2) { n=limit; break; } n*=2; }
    if (n < need) return 0;
    void *q = realloc(*p,n); if (!q) return 0; *p=q; *capacity=n; return 1;
}
static Blob blob(const void *p, size_t n) { Blob b={p,n}; return b; }
static int equal(Blob a, const char *s) { size_t n=strlen(s); return a.n==n && !memcmp(a.p,s,n); }
static int begins(Blob a, const char *s) { size_t n=strlen(s); return a.n>=n && !memcmp(a.p,s,n); }
static int string_ok(Blob b, size_t maximum, int empty) { return b.n<=maximum && (empty || b.n) && (!b.n || !memchr(b.p,0,b.n)); }
static Blob field(const unsigned char *p, size_t n) { const unsigned char *zero=memchr(p,0,n); return blob(p,zero ? (size_t)(zero-p) : n); }
static void attrs_free(Attrs *m) {
    for (size_t i=0;i<m->count;i++) { free(m->a[i].key); free(m->a[i].value); }
    free(m->a); memset(m,0,sizeof(*m));
}
static int attrs_set(Attrs *m, Blob key, Blob value, size_t maximum) {
    size_t i; for (i=0;i<m->count;i++) if (m->a[i].kn==key.n && !memcmp(m->a[i].key,key.p,key.n)) break;
    size_t old=i<m->count ? m->a[i].kn+m->a[i].vn : 0;
    if (key.n > maximum || value.n > maximum-key.n || m->bytes-old > maximum-key.n-value.n || (i==m->count && i>=4096)) return 0;
    unsigned char *k=malloc(key.n+1), *v=malloc(value.n+1);
    if (!k || !v) { free(k); free(v); return 0; }
    memcpy(k,key.p,key.n); k[key.n]=0; if (value.n) memcpy(v,value.p,value.n); v[value.n]=0;
    if (i==m->count) {
        void *a=realloc(m->a,(i+1)*sizeof(Attr)); if (!a) { free(k); free(v); return 0; }
        m->a=a; m->count++;
    } else { free(m->a[i].key); free(m->a[i].value); }
    m->a[i]=(Attr){k,v,key.n,value.n}; m->bytes=m->bytes-old+key.n+value.n; return 1;
}
static void attrs_delete(Attrs *m, Blob key) {
    for (size_t i=0;i<m->count;i++) if (m->a[i].kn==key.n && !memcmp(m->a[i].key,key.p,key.n)) {
        m->bytes-=m->a[i].kn+m->a[i].vn; free(m->a[i].key); free(m->a[i].value);
        memmove(m->a+i,m->a+i+1,(m->count-i-1)*sizeof(Attr)); m->count--; return;
    }
}
static int attrs_merge(Attrs *out, const Attrs *global, const Attrs *local, size_t maximum) {
    // Every intermediate map must be a subset of the final map. Copying an
    // overridden global first can exceed the limit before a later deletion
    // or smaller replacement, making equivalent maps depend on keyword order.
    for (size_t i=0;i<global->count;i++) {
        const Attr *a=global->a+i; int overridden=0;
        for (size_t j=0;j<local->count;j++) if (local->a[j].kn==a->kn && !memcmp(local->a[j].key,a->key,a->kn)) { overridden=1; break; }
        if (!overridden && !attrs_set(out,blob(a->key,a->kn),blob(a->value,a->vn),maximum)) return 0;
    }
    for (size_t i=0;i<local->count;i++) {
        Blob k=blob(local->a[i].key,local->a[i].kn),v=blob(local->a[i].value,local->a[i].vn);
        if (v.n && !attrs_set(out,k,v,maximum)) return 0;
    }
    return 1;
}
static int decimal(Blob b, int allow_negative, int64_t *value) {
    size_t at=0; int neg=0; uint64_t n=0,limit=INT64_MAX;
    if (!b.n) return 0;
    if (allow_negative && b.p[0]=='-') { neg=1; at=1; limit=(uint64_t)INT64_MAX+1; }
    if (at==b.n) return 0;
    for (;at<b.n;at++) { unsigned d=b.p[at]-'0'; if (d>9 || n>(limit-d)/10) return 0; n=n*10+d; }
    *value=neg ? (n==limit ? INT64_MIN : -(int64_t)n) : (int64_t)n; return 1;
}
static int number(const unsigned char *p, size_t n, int64_t *value) {
    if (p[0]&128) {
        __int128 v=(p[0]&127)-(p[0]&64 ? 128 : 0);
        for (size_t i=1;i<n;i++) v=v*256+p[i];
        if (v<INT64_MIN || v>INT64_MAX) return 0; *value=(int64_t)v; return 1;
    }
    size_t at=0; uint64_t v=0;
    while (at<n && (p[at]==' ' || p[at]==0)) at++;
    while (at<n && p[at]>='0' && p[at]<='7') { unsigned d=p[at++]-'0'; if (v>((uint64_t)INT64_MAX-d)/8) return 0; v=v*8+d; }
    while (at<n) { if (p[at]!=0 && p[at]!=' ') return 0; at++; }
    *value=(int64_t)v; return 1;
}
static int timestamp(Blob b, int64_t *seconds, int64_t *nanos) {
    size_t dot=0; while (dot<b.n && b.p[dot]!='.') dot++;
    if (!decimal(blob(b.p,dot),1,seconds)) return 0;
    int64_t fraction=0; size_t width=0;
    if (dot<b.n) {
        if (++dot==b.n) return 0;
        for (;dot<b.n;dot++,width++) {
            unsigned d=b.p[dot]-'0'; if (d>9 || (width>=9 && d)) return 0;
            if (width<9) fraction=fraction*10+d;
        }
    }
    while (width++<9) fraction*=10;
    if (b.p[0]=='-' && fraction) { if (*seconds==INT64_MIN) return 0; (*seconds)--; fraction=1000000000-fraction; }
    *nanos=fraction; return 1;
}
static int sparse(Blob k) { return begins(k,"GNU.sparse.") || equal(k,"SCHILY.realsize"); }
static int pax_parse(Blob data, Attrs *attrs, size_t maximum, const char **error) {
    size_t at=0;
    while (at<data.n) {
        size_t space=at; while (space<data.n && data.p[space]>='0' && data.p[space]<='9') space++;
        int64_t size;
        if (space==data.n || data.p[space]!=' ' || !decimal(blob(data.p+at,space-at),0,&size) || size<(int64_t)(space-at+4) || (uint64_t)size>data.n-at || data.p[at+(size_t)size-1]!='\n') { *error="invalid PAX record span"; return 0; }
        size_t end=at+(size_t)size-1,equal_at=space+1;
        while (equal_at<end && data.p[equal_at]!='=') equal_at++;
        if (equal_at==space+1 || equal_at==end) { *error="invalid PAX keyword"; return 0; }
        Blob k=blob(data.p+space+1,equal_at-space-1),v=blob(data.p+equal_at+1,end-equal_at-1);
        for (size_t i=0;i<k.n;i++) if (k.p[i]<33 || k.p[i]>126) { *error="invalid PAX keyword"; return 0; }
        if (sparse(k) || (equal(k,"SCHILY.filetype") && equal(v,"sparse"))) { *error="unsupported sparse tar"; return 0; }
        if (!attrs_set(attrs,k,v,maximum)) { *error="PAX metadata/count limit exceeded"; return 0; }
        at+=(size_t)size;
    }
    return 1;
}
static int pax_global(Blob data, Attrs *globals, size_t maximum, const char **error) {
    Attrs changes={0},merged={0};
    // Bound the incoming wire map independently, then apply its final
    // replacements/deletions without transiently enlarging persistent state.
    int ok=pax_parse(data,&changes,maximum,error);
    if (ok && !attrs_merge(&merged,globals,&changes,maximum)) { *error="global PAX metadata/count limit exceeded"; ok=0; }
    attrs_free(&changes);
    if (!ok) { attrs_free(&merged); return 0; }
    attrs_free(globals); *globals=merged; return 1;
}
static int apply(Entry *e, const char **error) {
    for (size_t i=0;i<e->attrs.count;i++) {
        Attr *a=e->attrs.a+i; Blob k=blob(a->key,a->kn),v=blob(a->value,a->vn);
        if (equal(k,"path")) e->path=v;
        else if (equal(k,"linkpath")) e->link=v;
        else if (equal(k,"uname")) e->uname=v;
        else if (equal(k,"gname")) e->gname=v;
        else if (equal(k,"mtime")) { if (!timestamp(v,&e->seconds,&e->nanos)) { *error="invalid exact PAX timestamp"; return 0; } }
        else {
            int64_t *target=NULL;
            if (equal(k,"size")) target=&e->size;
            if (equal(k,"uid")) target=&e->uid;
            if (equal(k,"gid")) target=&e->gid;
            if (equal(k,"SCHILY.devmajor")) target=&e->major;
            if (equal(k,"SCHILY.devminor")) target=&e->minor;
            if (target && !decimal(v,target!=&e->size,target)) { *error="invalid PAX integer"; return 0; }
        }
    }
    return 1;
}
static int zero(const unsigned char *p,size_t n) { for (size_t i=0;i<n;i++) if (p[i]) return 0; return 1; }
static int scan(Reader *r, Entry *e, const char **error) {
    size_t at=r->position,start=at,chain=0,metadata=0; Attrs local={0};
    Blob long_path={0},long_link={0}; unsigned char combined[256]; int status=0;
    memset(e,0,sizeof(*e));
    for (;;) {
        if (r->length-at<512) { *error="truncated tar header/footer"; break; }
        const unsigned char *h=r->source+at;
        if (zero(h,512)) {
            if (chain) { *error="dangling tar extension"; break; }
            if (r->length-at<1024 || (r->length-at)%512 || !zero(h,r->length-at)) { *error="invalid tar footer/record padding"; break; }
            status=2; break;
        }
        if (r->headers>=r->max_headers) { *error="tar header limit exceeded"; break; } r->headers++;
        int64_t checksum, sum = 8 * ' ';
        for (size_t i = 0; i < 148; i++) sum += h[i];
        for (size_t i = 156; i < 512; i++) sum += h[i];
        if (!number(h + 148, 8, &checksum)) { *error = "tar checksum mismatch"; break; }
        if (checksum != sum) {
            int64_t signed_sum = 8 * ' ';
            for (size_t i = 0; i < 148; i++) signed_sum += (int8_t)h[i];
            for (size_t i = 156; i < 512; i++) signed_sum += (int8_t)h[i];
            if (checksum != signed_sum) { *error = "tar checksum mismatch"; break; }
        }
        int v7=zero(h+257,8),ustar=!memcmp(h+257,"ustar\00000",8),gnu=!memcmp(h+257,"ustar  \0",8);
        if (!v7 && !ustar && !gnu) { *error="unsupported tar magic/version"; break; }
        e->type=h[156] ? h[156] : '0'; e->path=field(h,100); e->link=field(h+157,100);
        e->uname=v7 ? blob(NULL,0) : field(h+265,32); e->gname=v7 ? blob(NULL,0) : field(h+297,32);
        if (ustar) {
            Blob pre=field(h+345,155);
            if (pre.n) { memcpy(combined,pre.p,pre.n); combined[pre.n]='/'; memcpy(combined+pre.n+1,e->path.p,e->path.n); e->path=blob(combined,pre.n+1+e->path.n); }
        }
        if (!number(h+100,8,&e->mode) || !number(h+108,8,&e->uid) || !number(h+116,8,&e->gid) || !number(h+124,12,&e->size) || !number(h+136,12,&e->seconds) || (!v7 && (!number(h+329,8,&e->major) || !number(h+337,8,&e->minor)))) { *error="invalid/overflowing tar number"; break; }
        if (e->mode<0 || e->size<0 || e->major<0 || e->minor<0) { *error="negative tar mode/size/device"; break; }
        int ext=e->type=='x' || e->type=='g' || e->type=='L' || e->type=='K';
        if (ext) {
            if (chain>=r->max_chain || (uint64_t)e->size>r->max_metadata-metadata) { *error="tar extension chain/metadata limit exceeded"; break; }
            chain++; metadata+=(size_t)e->size;
        } else {
            if (e->type<'0' || e->type>'6') { *error="unsupported member type (including sparse)"; break; }
            if (long_path.p) e->path=long_path; if (long_link.p) e->link=long_link;
            if (!attrs_merge(&e->attrs,&r->globals,&local,r->max_metadata)) { *error="effective PAX metadata limit exceeded"; break; }
            if (!apply(e,error)) break;
            if (e->size<0 || e->major<0 || e->minor<0 || (e->type!='0' && e->size)) { *error="invalid nonregular payload or device"; break; }
            if (!string_ok(e->path,r->max_path,0) || !string_ok(e->link,r->max_path,1) || !string_ok(e->uname,r->max_path,1) || !string_ok(e->gname,r->max_path,1)) { *error="tar byte name limit/NUL"; break; }
        }
        size_t offset=at+512;
        if ((uint64_t)e->size>r->length-offset) { *error="truncated tar payload"; break; }
        size_t padding=(512-(size_t)e->size%512)%512;
        if (padding>r->length-offset-(size_t)e->size) { *error="truncated tar payload padding"; break; }
        size_t end=offset+(size_t)e->size+padding;
        if (ext) {
            Blob data=blob(r->source+offset,(size_t)e->size);
            if (e->type=='x' || e->type=='g') {
                if (e->type=='g') { if (!pax_global(data,&r->globals,r->max_metadata,error)) break; }
                else if (!pax_parse(data,&local,r->max_metadata,error)) break;
            }
            else {
                if (data.n && data.p[data.n-1]==0) data.n--;
                if (!string_ok(data,r->max_path,0)) { *error="GNU long name limit/NUL"; break; }
                if (e->type=='L') long_path=data; else long_link=data;
            }
            at=end;
        } else {
            e->start=start; e->header=at; e->offset=offset; e->end=end; r->position=end;
            // combined is stack-local: serialized immediately in caller only
            // after replacing this temporary path with an owned map attribute.
            if (e->path.p==combined) {
                e->owned_path=malloc(e->path.n); if (!e->owned_path) { *error="allocation failure"; break; }
                memcpy(e->owned_path,e->path.p,e->path.n); e->path.p=e->owned_path;
            }
            status=1; break;
        }
    }
    attrs_free(&local); return status;
}
long long minyar_tararchive_openReader(const MinyarBytes *source,long long path,long long metadata,long long chain,long long headers) {
    if (!source || source->byte_length<0 || path<1 || metadata<0 || chain<1 || headers<1 || (uint64_t)source->byte_length>SIZE_MAX || (uint64_t)path>SIZE_MAX || (uint64_t)metadata>SIZE_MAX) return 0;
    Reader *r=calloc(1,sizeof(*r)); if (!r) return 0;
    r->source=source->bytes; r->length=(size_t)source->byte_length; r->max_path=(size_t)path; r->max_metadata=(size_t)metadata; r->max_chain=(size_t)chain; r->max_headers=(size_t)headers;
    return (long long)(intptr_t)r;
}
static MinyarBytes *owned_blob(Blob data) {
    if (data.n >= SIZE_MAX / 2) minyar_native_stop("these tar bytes are too large");
    MinyarBytes *out = minyar_bytes_new((long long)data.n);
    if (data.n) memcpy((void *)out->bytes, data.p, data.n);
    return out;
}
static void record_take(NativeRecord *record, long long field, void *value) {
    minyar_record_set_take(record, field, (long long)(intptr_t)value);
}
static NativeRecord *managed_entry(const Entry *e, const Reader *r) {
    NativeRecord *value = minyar_record_new(22);
    record_take(value, 0, owned_blob(e->path)); record_take(value, 1, owned_blob(e->link));
    int64_t numbers[] = {e->mode, e->uid, e->gid, e->seconds, e->nanos, e->type, e->size, e->major, e->minor};
    for (size_t i = 0; i < 9; i++) minyar_record_set_scalar(value, (long long)i + 2, numbers[i]);
    record_take(value, 11, owned_blob(e->uname)); record_take(value, 12, owned_blob(e->gname));
    NativeList *attrs = minyar_list_new(); minyar_list_references(attrs);
    for (size_t i = 0; i < e->attrs.count; i++) {
        Attr *a = e->attrs.a + i;
        NativeRecord *attribute = minyar_record_new(2);
        record_take(attribute, 0, owned_blob(blob(a->key, a->kn)));
        record_take(attribute, 1, owned_blob(blob(a->value, a->vn)));
        minyar_list_add_take(attrs, (long long)(intptr_t)attribute);
    }
    record_take(value, 13, attrs);
    int64_t spans[] = {(int64_t)e->start, (int64_t)e->header, (int64_t)e->offset, (int64_t)e->end,
                       (int64_t)(intptr_t)r->source, (int64_t)r->length, e->size};
    for (size_t i = 0; i < 7; i++) minyar_record_set_scalar(value, (long long)i + 14, spans[i]);
    return value;
}
NativeRecord *minyar_tararchive_readValue(long long handle) {
    Reader *r = (Reader *)(intptr_t)handle;
    Entry e; const char *error = "invalid tar";
    int status = scan(r, &e, &error);
    r->last_error = status == 0 ? error : NULL;
    if (status != 1) {
        free(e.owned_path); attrs_free(&e.attrs); memset(&e, 0, sizeof(e)); e.type = '0'; e.mode = 420;
        e.start = e.header = e.offset = e.end = SIZE_MAX;
    }
    NativeRecord *out = managed_entry(&e, r);
    minyar_record_set_scalar(out, 21, status);
    free(e.owned_path); attrs_free(&e.attrs);
    return out;
}
MinyarBytes *minyar_tararchive_readerMessage(long long handle) {
    Reader *r = (Reader *)(intptr_t)handle;
    const char *error = r->last_error ? r->last_error : "";
    return owned_blob(blob((const unsigned char *)error, strlen(error)));
}
MinyarBytes *minyar_tararchive_copyRange(const MinyarBytes *source, long long offset, long long length) {
    if (!source || offset < 0 || length < 0 || offset > source->byte_length || length > source->byte_length - offset)
        return minyar_bytes_new(0);
    return owned_blob(blob(source->bytes + offset, (size_t)length));
}
void minyar_tararchive_freeReader(long long handle) {
    Reader *r=(Reader *)(intptr_t)handle; if (!r) return;
    attrs_free(&r->globals); free(r);
}
MinyarText *minyar_tararchive_providerVersion(void) { const char *s=archive_version_string(); return minyar_native_copy_text((const unsigned char *)s,(long long)strlen(s)); }

static la_ssize_t output_callback(struct archive *archive, void *opaque, const void *p, size_t n) {
    (void)archive; Writer *w=opaque;
    if (!w->capturing) {
        if (w->length > w->maximum || n > w->maximum - w->length) { w->error = "tar output limit exceeded"; return -1; }
        if (n) memcpy(minyar_native_bytes_append(w->output, (long long)n), p, n);
        w->length += n;
        return (la_ssize_t)n;
    }
    size_t maximum = 1048576 + 32768;
    if (w->cn > maximum || n > maximum - w->cn || !grow(&w->capture, &w->cc, w->cn + n, maximum)) { w->error = "tar capture limit or allocation failure"; return -1; }
    if (n) memcpy(w->capture + w->cn, p, n); w->cn += n; return (la_ssize_t)n;
}
long long minyar_tararchive_openWriter(long long maximum) {
    if (maximum<1024 || (uint64_t)maximum>SIZE_MAX) return 0;
    Writer *w=calloc(1,sizeof(*w)); if (!w) return 0; w->maximum=(size_t)maximum;
    w->archive=archive_write_new(); if (!w->archive) { free(w); return 0; }
    w->output = minyar_bytes_new(0);
    if (archive_write_set_format_pax_restricted(w->archive)!=ARCHIVE_OK ||
        archive_write_set_format_option(w->archive,"pax","hdrcharset","BINARY")!=ARCHIVE_OK ||
        archive_write_set_bytes_per_block(w->archive,0)!=ARCHIVE_OK ||
        archive_write_open(w->archive,w,NULL,output_callback,NULL)!=ARCHIVE_OK) {
        archive_write_free(w->archive); minyar_rc_release(w->output); free(w); return 0;
    }
    return (long long)(intptr_t)w;
}
static int standard(Blob k) {
    return equal(k,"path") || equal(k,"linkpath") || equal(k,"size") || equal(k,"uid") || equal(k,"gid") || equal(k,"mtime") ||
        equal(k,"uname") || equal(k,"gname") || equal(k,"SCHILY.devmajor") || equal(k,"SCHILY.devminor") || equal(k,"hdrcharset");
}
static const MinyarBytes *entry_bytes(const NativeRecord *value, long long field) {
    return (const MinyarBytes *)(intptr_t)minyar_record_get(value, field);
}
static int decode_value(const NativeRecord *value, const MinyarBytes *data, Entry *e, const char **error) {
    memset(e, 0, sizeof(*e));
    if (!value || !data || data->byte_length < 0) { *error = "invalid tar writer metadata"; return 0; }
    e->type = minyar_record_get(value, 7); e->mode = minyar_record_get(value, 2);
    e->uid = minyar_record_get(value, 3); e->gid = minyar_record_get(value, 4);
    e->seconds = minyar_record_get(value, 5); e->nanos = minyar_record_get(value, 6);
    e->size = data->byte_length; e->major = minyar_record_get(value, 9); e->minor = minyar_record_get(value, 10);
    const MinyarBytes *names[] = {entry_bytes(value, 0), entry_bytes(value, 1), entry_bytes(value, 11), entry_bytes(value, 12)};
    Blob *fields[] = {&e->path, &e->link, &e->uname, &e->gname};
    for (size_t i = 0; i < 4; i++) {
        if (!names[i] || names[i]->byte_length < 0 || names[i]->byte_length > 4096) { *error = "tar writer name limit/NUL"; return 0; }
        *fields[i] = blob(names[i]->bytes, (size_t)names[i]->byte_length);
    }
    if (e->type<'0' || e->type>'6' || e->mode<0 || e->mode>07777777 || e->major<0 || e->minor<0 || e->nanos<0 || e->nanos>=1000000000 || (e->type!='0' && data->byte_length)) { *error="invalid tar writer fields"; return 0; }
    if (!string_ok(e->path,4096,0) || !string_ok(e->link,4096,1) || !string_ok(e->uname,4096,1) || !string_ok(e->gname,4096,1)) { *error="tar writer name limit/NUL"; return 0; }
    NativeList *attrs = (NativeList *)(intptr_t)minyar_record_get(value, 13);
    if (!attrs) { *error = "tar writer attribute count"; return 0; }
    long long count = minyar_list_length(attrs);
    if (count < 0 || count > 4096) { *error = "tar writer attribute count"; return 0; }
    size_t total = 0;
    for (long long i = 0; i < count; i++) {
        NativeRecord *a = (NativeRecord *)(intptr_t)minyar_list_get(attrs, i);
        const MinyarBytes *key = entry_bytes(a, 0), *data_value = entry_bytes(a, 1);
        if (!key || !data_value || key->byte_length < 0 || data_value->byte_length < 0) { *error = "tar writer attribute bounds"; return 0; }
        Blob k = blob(key->bytes, (size_t)key->byte_length), v = blob(data_value->bytes, (size_t)data_value->byte_length);
        if (!k.n || k.n>1048576 || v.n>1048576-k.n || total>1048576-k.n-v.n) { *error="tar writer attribute bounds"; return 0; }
        total += k.n + v.n;
        for (size_t j=0;j<k.n;j++) if (k.p[j]<33 || k.p[j]>126 || k.p[j]=='=') { *error="invalid PAX writer keyword"; return 0; }
        if (sparse(k)) { *error="unsupported sparse tar writer"; return 0; }
        if (equal(k,"SCHILY.filetype") && equal(v,"sparse")) { *error="unsupported sparse tar writer"; return 0; }
        if (!standard(k) && v.n && !attrs_set(&e->attrs,k,v,1048576)) { *error="PAX writer metadata limit"; return 0; }
    }
    return 1;
}
static void octal(unsigned char *p,size_t n,uint64_t value) {
    memset(p,'0',n-1); p[n-1]=0; for (size_t i=n-1;i>0;i--) { p[i-1]=(unsigned char)('0'+value%8); value/=8; }
}
static void checksum(unsigned char *h) {
    memset(h+148,' ',8); uint64_t total=0; for (size_t i=0;i<512;i++) total+=h[i];
    octal(h+148,7,total); h[155]=' ';
}
static int set_text(Attrs *m,const char *key,const char *value) { return attrs_set(m,blob((const unsigned char *)key,strlen(key)),blob((const unsigned char *)value,strlen(value)),1048576); }
static int set_number(Attrs *m,const char *key,int64_t value) { char text[32]; snprintf(text,sizeof(text),"%" PRId64,value); return set_text(m,key,text); }
static int set_time(Attrs *m,int64_t seconds,int64_t nanos) {
    char text[80];
    if (!nanos) snprintf(text,sizeof(text),"%" PRId64,seconds);
    else {
        // Canonical floor-seconds representation; never negate INT64_MIN.
        if (seconds<0) snprintf(text,sizeof(text),"-%" PRIu64 ".%09" PRId64,(uint64_t)(-(seconds+1)),1000000000-nanos);
        else snprintf(text,sizeof(text),"%" PRId64 ".%09" PRId64,seconds,nanos);
        size_t n=strlen(text); while (text[n-1]=='0') text[--n]=0;
    }
    return set_text(m,"mtime",text);
}
static int attr_compare(const void *aa,const void *bb) {
    const Attr *a=aa,*b=bb; size_t n=a->kn<b->kn ? a->kn : b->kn;
    int c=memcmp(a->key,b->key,n); return c ? c : (a->kn>b->kn)-(a->kn<b->kn);
}
static int pax_encode(Attrs *m,unsigned char **output,size_t *length) {
    size_t capacity=0; *output=NULL; *length=0;
    qsort(m->a,m->count,sizeof(Attr),attr_compare);
    for (size_t i=0;i<m->count;i++) {
        Attr *a=m->a+i; size_t size=a->kn+a->vn+4,next; char count[32];
        do { snprintf(count,sizeof(count),"%zu",size); next=strlen(count)+a->kn+a->vn+3; if (next==size) break; size=next; } while (1);
        if (size>1048576-*length || !grow(output,&capacity,*length+size,1048576)) { free(*output); *output=NULL; return 0; }
        unsigned char *p=*output+*length; size_t at=strlen(count); memcpy(p,count,at); p[at++]=' ';
        memcpy(p+at,a->key,a->kn); at+=a->kn; p[at++]='='; if (a->vn) memcpy(p+at,a->value,a->vn); at+=a->vn; p[at]='\n'; *length+=size;
    }
    return 1;
}
static int plain_header(const Entry *e, unsigned char h[512]) {
    if (e->attrs.count || e->path.n > 100 || e->link.n > 100 || e->uname.n > 32 || e->gname.n > 32 ||
        e->uid < 0 || e->uid > 07777777 || e->gid < 0 || e->gid > 07777777 ||
        e->seconds < 0 || e->seconds > 077777777777LL || e->nanos || e->size > 077777777777LL ||
        e->major > 07777777 || e->minor > 07777777 ||
        ((e->type != '3' && e->type != '4') && (e->major || e->minor))) return 0;
    memset(h, 0, 512);
    memcpy(h, e->path.p, e->path.n); if (e->link.n) memcpy(h + 157, e->link.p, e->link.n);
    if (e->uname.n) memcpy(h + 265, e->uname.p, e->uname.n);
    if (e->gname.n) memcpy(h + 297, e->gname.p, e->gname.n);
    octal(h + 100, 8, (uint64_t)e->mode); octal(h + 108, 8, (uint64_t)e->uid);
    octal(h + 116, 8, (uint64_t)e->gid); octal(h + 124, 12, (uint64_t)e->size);
    octal(h + 136, 12, (uint64_t)e->seconds); octal(h + 329, 8, (uint64_t)e->major);
    octal(h + 337, 8, (uint64_t)e->minor); h[156] = (unsigned char)e->type;
    memcpy(h + 257, "ustar\00000", 8); checksum(h);
    return 1;
}
static int writer_header(Writer *w,Entry *e,unsigned char base[512],const char **error) {
    struct archive_entry *a=archive_entry_new(); if (!a) { *error="allocation failure"; return 0; }
    // Blob names are length-delimited; libarchive needs terminated copies.
    char names[4][4097]; Blob fields[]={e->path,e->link,e->uname,e->gname};
    for (size_t i=0;i<4;i++) { if (fields[i].n) memcpy(names[i],fields[i].p,fields[i].n); names[i][fields[i].n]=0; }
    int types[]={AE_IFREG,AE_IFREG,AE_IFLNK,AE_IFCHR,AE_IFBLK,AE_IFDIR,AE_IFIFO};
    archive_entry_set_filetype(a,types[e->type-'0']); archive_entry_set_perm(a,(mode_t)e->mode);
    // Avoid provider-internal decimal formatting overflow at signed extremes.
    // Exact wide/signed fields are emitted below as bounded PAX records.
    archive_entry_set_uid(a,e->uid<0 || e->uid>07777777 ? 0 : e->uid);
    archive_entry_set_gid(a,e->gid<0 || e->gid>07777777 ? 0 : e->gid);
    archive_entry_set_mtime(a,e->seconds<0 || e->seconds>077777777777LL ? 0 : (time_t)e->seconds,0);
    archive_entry_set_size(a,e->size);
    archive_entry_set_rdevmajor(a,e->major>07777777 ? 0 : (dev_t)e->major);
    archive_entry_set_rdevminor(a,e->minor>07777777 ? 0 : (dev_t)e->minor);
    archive_entry_set_pathname(a,names[0]); archive_entry_set_uname(a,names[2]); archive_entry_set_gname(a,names[3]);
    if (e->type=='1') archive_entry_set_hardlink(a,names[1]); if (e->type=='2') archive_entry_set_symlink(a,names[1]);
    w->capturing=1; w->cn=0;
    int code=archive_write_header(w->archive,a);
    archive_entry_free(a);
    if (code<ARCHIVE_WARN || w->error || w->cn<512 || w->cn%512) { *error=w->error ? w->error : archive_error_string(w->archive); if (!*error) *error="libarchive writer header failure"; return 0; }
    // Native library generates base headers. Merge its generated PAX with raw
    // vendor attributes into ONE local extension, since multiple x headers
    // are rejected by newer libarchive versions.
    size_t at=0;
    while (w->cn-at>512) {
        const unsigned char *h=w->capture+at; int64_t n;
        if (h[156]!='x' || !number(h+124,12,&n) || n<0 || (uint64_t)n>w->cn-at-512) { *error="unexpected libarchive extension"; return 0; }
        if (!pax_parse(blob(h+512,(size_t)n),&e->attrs,1048576,error)) return 0;
        size_t span=512+(size_t)n+(512-(size_t)n%512)%512; if (span>w->cn-at) { *error="invalid libarchive extension span"; return 0; } at+=span;
    }
    memcpy(base,w->capture+at,512);
    // Selecting BINARY in libarchive forces a charset extension even for a
    // plain ASCII ustar member. Only retain it when a real PAX record remains.
    attrs_delete(&e->attrs,blob((const unsigned char *)"hdrcharset",10));
    // Current typed fields win over stale attributes, with exact negative
    // fractional time and signed uid/gid semantics even on older providers.
    if (e->uid<0 || e->uid>07777777) { if (!set_number(&e->attrs,"uid",e->uid)) return 0; }
    if (e->gid<0 || e->gid>07777777) { if (!set_number(&e->attrs,"gid",e->gid)) return 0; }
    if (e->seconds<0 || e->seconds>077777777777LL || e->nanos) { if (!set_time(&e->attrs,e->seconds,e->nanos)) return 0; }
    if (e->major>07777777 && !set_number(&e->attrs,"SCHILY.devmajor",e->major)) return 0;
    if (e->minor>07777777 && !set_number(&e->attrs,"SCHILY.devminor",e->minor)) return 0;
    // libarchive may add a trailing directory slash. Preserve exact byte names.
    memset(base,0,100); memset(base+345,0,155);
    if (e->path.n<=100) { memcpy(base,e->path.p,e->path.n); attrs_delete(&e->attrs,blob((const unsigned char *)"path",4)); }
    else {
        size_t split=SIZE_MAX;
        for (size_t i=1;i<e->path.n;i++) if (e->path.p[i]=='/' && i<=155 && e->path.n-i-1>0 && e->path.n-i-1<=100) split=i;
        if (split!=SIZE_MAX) { memcpy(base,e->path.p+split+1,e->path.n-split-1); memcpy(base+345,e->path.p,split); attrs_delete(&e->attrs,blob((const unsigned char *)"path",4)); }
        else { memcpy(base,"PaxEntry",8); if (!attrs_set(&e->attrs,blob((const unsigned char *)"path",4),e->path,1048576)) return 0; }
    }
    if (e->attrs.count && !set_text(&e->attrs,"hdrcharset","BINARY")) return 0;
    // An empty hardlink target is accepted by this byte-level API, but some
    // providers generate a regular header for it. Preserve the requested type.
    base[156]=(unsigned char)e->type;
    octal(base+100,8,(uint64_t)e->mode);
    checksum(base); return 1;
}
long long minyar_tararchive_writeStatus(long long handle,const NativeRecord *value,const MinyarBytes *data) {
    Writer *w=(Writer *)(intptr_t)handle; Entry e; const char *error="tar writer metadata failure";
    if (!decode_value(value,data,&e,&error)) { attrs_free(&e.attrs); w->error = error; return 1; }
    unsigned char base[512],*pax=NULL; size_t pn=0;
    int plain = plain_header(&e, base);
    if (!plain && (!writer_header(w,&e,base,&error) || !pax_encode(&e.attrs,&pax,&pn))) { attrs_free(&e.attrs); free(pax); w->error = error; return 1; }
    size_t padding=(512-(size_t)data->byte_length%512)%512;
    size_t extra=pn ? 512+pn+(512-pn%512)%512 : 0;
    if (w->length>w->maximum-1024 || (uint64_t)data->byte_length>w->maximum-1024-w->length || padding+512+extra>w->maximum-1024-w->length-(size_t)data->byte_length) {
        attrs_free(&e.attrs); free(pax); w->error = "tar writer archive limit exceeded"; return 1;
    }
    w->capturing=0;
    if (pn) {
        unsigned char h[512]={0}; memcpy(h,"PaxHeaders/entry",16); octal(h+100,8,0644); octal(h+108,8,0); octal(h+116,8,0); octal(h+124,12,pn); octal(h+136,12,0); h[156]='x'; memcpy(h+257,"ustar\00000",8); checksum(h);
        unsigned char zeros[512]={0};
        if (output_callback(NULL,w,h,512)<0 || output_callback(NULL,w,pax,pn)<0 || output_callback(NULL,w,zeros,(512-pn%512)%512)<0) w->error="tar writer extension output failure";
    }
    if (!w->error && output_callback(NULL,w,base,512)<0) w->error="tar writer base output failure";
    if (plain) {
        unsigned char zeros[512] = {0};
        if (!w->error && data->byte_length && output_callback(NULL, w, data->bytes, (size_t)data->byte_length) < 0) w->error = "tar writer payload failure";
        if (!w->error && padding && output_callback(NULL, w, zeros, padding) < 0) w->error = "tar writer padding failure";
    } else {
        if (!w->error && data->byte_length && archive_write_data(w->archive,data->bytes,(size_t)data->byte_length)!=data->byte_length) w->error="libarchive writer payload failure";
        if (!w->error && archive_write_finish_entry(w->archive)!=ARCHIVE_OK) w->error="libarchive writer padding failure";
    }
    attrs_free(&e.attrs); free(pax);
    return w->error ? 1 : 0;
}
MinyarBytes *minyar_tararchive_finishData(long long handle) {
    Writer *w = (Writer *)(intptr_t)handle; w->capturing = 0;
    if (archive_write_close(w->archive) != ARCHIVE_OK && !w->error) w->error = "libarchive writer finish failure";
    minyar_rc_retain(w->output);
    return w->output;
}
MinyarBytes *minyar_tararchive_writerStatus(long long handle) {
    Writer *w = (Writer *)(intptr_t)handle;
    return w->error ? result(1, w->error) : result(0, NULL);
}
void minyar_tararchive_freeWriter(long long handle) {
    Writer *w=(Writer *)(intptr_t)handle; if (!w) return;
    // Discard libarchive's close-time footer on explicit early close/error.
    w->capturing=1; w->cn=0; archive_write_free(w->archive); minyar_rc_release(w->output); free(w->capture); free(w);
}
