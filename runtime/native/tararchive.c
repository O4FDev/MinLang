/* Bounded OCI tar binding. libarchive owns archive validation and header/data
 * writing; the wire scanner adds exact PAX semantics, byte names, attributes,
 * strict limits and physical spans that libarchive's public API cannot expose.
 * Context pointers are private to shared Minyar records, never public handles.
 */
#include "../minyar_native.h"
#include <archive.h>
#include <archive_entry.h>
#include <limits.h>
#include <stdint.h>
#include <inttypes.h>
_Static_assert(sizeof(void *)==8 && sizeof(long long)==8 && sizeof(time_t)==8, "tar binding requires the 64-bit native ABI");

typedef struct { const unsigned char *p; size_t n; } Blob;
typedef struct { unsigned char *key, *value; size_t kn, vn; } Attr;
typedef struct { Attr *a; size_t count, bytes; } Attrs;
typedef struct {
    struct archive *archive;
    const unsigned char *source; size_t length, position;
    size_t max_path, max_metadata, max_chain, max_headers, headers; int normalize;
    Attrs globals;
} Reader;
typedef struct {
    struct archive *archive;
    unsigned char *output, *capture; size_t length, capacity, cn, cc, maximum;
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
    for (size_t i=0;i<global->count;i++) if (!attrs_set(out,blob(global->a[i].key,global->a[i].kn),blob(global->a[i].value,global->a[i].vn),maximum)) return 0;
    for (size_t i=0;i<local->count;i++) {
        Blob k=blob(local->a[i].key,local->a[i].kn),v=blob(local->a[i].value,local->a[i].vn);
        if (!v.n) attrs_delete(out,k); else if (!attrs_set(out,k,v,maximum)) return 0;
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
static int pax_parse(Blob data, Attrs *attrs, size_t maximum, int global, const char **error) {
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
        if (global && !v.n) attrs_delete(attrs,k);
        else if (!attrs_set(attrs,k,v,maximum)) { *error="PAX metadata/count limit exceeded"; return 0; }
        at+=(size_t)size;
    }
    return 1;
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
    size_t at=r->position,start=at,chain=0,metadata=0,local_headers=0; Attrs local={0};
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
        int64_t checksum; int64_t sum=0,signed_sum=0;
        for (size_t i=0;i<512;i++) { int c=i>=148 && i<156 ? ' ' : h[i]; sum+=c; signed_sum+=c<128 ? c : c-256; }
        if (!number(h+148,8,&checksum) || (checksum!=sum && checksum!=signed_sum)) { *error="tar checksum mismatch"; break; }
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
                // Resolve multiple local headers ourselves: provider recursion
                // limits and earlier-header precedence differ from this API.
                if (e->type=='g' || ++local_headers>1) r->normalize=1;
                if (!pax_parse(data,e->type=='g' ? &r->globals : &local,r->max_metadata,e->type=='g',error)) break;
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
static void put_i64(MinyarBytes *b,int64_t v) { memcpy(minyar_bytes_extend(b,8),&v,8); }
static void put_blob(MinyarBytes *b,Blob v) { put_i64(b,(int64_t)v.n); if (v.n) memcpy(minyar_bytes_extend(b,(long long)v.n),v.p,v.n); }
static MinyarBytes *encode(Entry *e) {
    MinyarBytes *b=minyar_bytes_new(0);
    int64_t n[]={1,e->type,e->mode,e->uid,e->gid,e->seconds,e->nanos,e->size,e->major,e->minor,(int64_t)e->start,(int64_t)e->header,(int64_t)e->offset,(int64_t)e->end};
    for (size_t i=0;i<14;i++) put_i64(b,n[i]);
    put_blob(b,e->path); put_blob(b,e->link); put_blob(b,e->uname); put_blob(b,e->gname); put_i64(b,(int64_t)e->attrs.count);
    for (size_t i=0;i<e->attrs.count;i++) { Attr *a=e->attrs.a+i; put_blob(b,blob(a->key,a->kn)); put_blob(b,blob(a->value,a->vn)); }
    return b;
}
long long minyar_tararchive_openReader(const MinyarBytes *source,long long path,long long metadata,long long chain,long long headers) {
    if (!source || source->byte_length<0 || path<1 || metadata<0 || chain<1 || headers<1 || (uint64_t)source->byte_length>SIZE_MAX || (uint64_t)path>SIZE_MAX || (uint64_t)metadata>SIZE_MAX) return 0;
    Reader *r=calloc(1,sizeof(*r)); if (!r) return 0;
    r->source=source->bytes; r->length=(size_t)source->byte_length; r->max_path=(size_t)path; r->max_metadata=(size_t)metadata; r->max_chain=(size_t)chain; r->max_headers=(size_t)headers;
    r->archive=archive_read_new(); if (!r->archive) { free(r); return 0; }
    archive_read_support_filter_none(r->archive); archive_read_support_format_tar(r->archive);
    // Opening can reject a malformed first header. Defer that error until next
    // so EOF/error remain normal recoverable values with a sticky wrapper.
    archive_read_open_memory(r->archive,r->source,r->length);
    return (long long)(intptr_t)r;
}
MinyarBytes *minyar_tararchive_readNext(long long handle) {
    Reader *r=(Reader *)(intptr_t)handle; Entry e; const char *error="invalid tar";
    int status=scan(r,&e,&error); MinyarBytes *out;
    if (status==1) {
        struct archive_entry *library_entry=NULL;
        if (r->normalize) {
            // libarchive ignores global PAX and differs on local chains. The
            // scanner has resolved/validated that layer and cursor movement;
            // validate each physical base header separately through libarchive.
            archive_read_free(r->archive); r->archive=archive_read_new();
            if (!r->archive) { free(e.owned_path); attrs_free(&e.attrs); return result(0,"allocation failure"); }
            archive_read_support_filter_none(r->archive); archive_read_support_format_tar(r->archive);
            archive_read_open_memory(r->archive,r->source+e.header,r->length-e.header);
        }
        int code=archive_read_next_header(r->archive,&library_entry);
        if (code<ARCHIVE_WARN || code==ARCHIVE_EOF) out=result(0,"libarchive rejected tar member");
        else out=encode(&e);

    } else out=result(status,error);
    free(e.owned_path); attrs_free(&e.attrs); return out;
}
void minyar_tararchive_freeReader(long long handle) {
    Reader *r=(Reader *)(intptr_t)handle; if (!r) return;
    archive_read_free(r->archive); attrs_free(&r->globals); free(r);
}
MinyarText *minyar_tararchive_providerVersion(void) { const char *s=archive_version_string(); return minyar_native_copy_text((const unsigned char *)s,(long long)strlen(s)); }

static la_ssize_t output_callback(struct archive *archive, void *opaque, const void *p, size_t n) {
    (void)archive; Writer *w=opaque;
    unsigned char **buffer=w->capturing ? &w->capture : &w->output;
    size_t *length=w->capturing ? &w->cn : &w->length,*capacity=w->capturing ? &w->cc : &w->capacity;
    size_t maximum=w->capturing ? 1048576+32768 : w->maximum;
    if (*length>maximum || n>maximum-*length || !grow(buffer,capacity,*length+n,maximum)) { w->error="tar output/capture limit or allocation failure"; return -1; }
    if (n) memcpy(*buffer+*length,p,n); *length+=n; return (la_ssize_t)n;
}
long long minyar_tararchive_openWriter(long long maximum) {
    if (maximum<1024 || (uint64_t)maximum>SIZE_MAX) return 0;
    Writer *w=calloc(1,sizeof(*w)); if (!w) return 0; w->maximum=(size_t)maximum;
    w->archive=archive_write_new(); if (!w->archive) { free(w); return 0; }
    if (archive_write_set_format_pax_restricted(w->archive)!=ARCHIVE_OK ||
        archive_write_set_format_option(w->archive,"pax","hdrcharset","BINARY")!=ARCHIVE_OK ||
        archive_write_set_bytes_per_block(w->archive,0)!=ARCHIVE_OK ||
        archive_write_open(w->archive,w,NULL,output_callback,NULL)!=ARCHIVE_OK) {
        archive_write_free(w->archive); free(w); return 0;
    }
    return (long long)(intptr_t)w;
}
static int take_i64(const unsigned char *p,size_t length,size_t *at,int64_t *out) {
    if (*at>length || length-*at<8) return 0; memcpy(out,p+*at,8); *at+=8; return 1;
}
static int take_blob(const unsigned char *p,size_t length,size_t *at,Blob *out) {
    int64_t n; if (!take_i64(p,length,at,&n) || n<0 || (uint64_t)n>length-*at) return 0;
    *out=blob(p+*at,(size_t)n); *at+=(size_t)n; return 1;
}
static int standard(Blob k) {
    return equal(k,"path") || equal(k,"linkpath") || equal(k,"size") || equal(k,"uid") || equal(k,"gid") || equal(k,"mtime") ||
        equal(k,"uname") || equal(k,"gname") || equal(k,"SCHILY.devmajor") || equal(k,"SCHILY.devminor") || equal(k,"hdrcharset");
}
static int decode(const MinyarBytes *info,const MinyarBytes *data,Entry *e,const char **error) {
    memset(e,0,sizeof(*e)); size_t at=0;
    if (!info || !data || info->byte_length<0 || data->byte_length<0 || (uint64_t)info->byte_length>1048576+200000) { *error="excessive tar writer metadata"; return 0; }
    const unsigned char *p=info->bytes; size_t n=(size_t)info->byte_length;
    int64_t *fields[]={&e->type,&e->mode,&e->uid,&e->gid,&e->seconds,&e->nanos,&e->size,&e->major,&e->minor};
    for (size_t i=0;i<9;i++) if (!take_i64(p,n,&at,fields[i])) { *error="invalid encoded tar metadata"; return 0; }
    if (!take_blob(p,n,&at,&e->path) || !take_blob(p,n,&at,&e->link) || !take_blob(p,n,&at,&e->uname) || !take_blob(p,n,&at,&e->gname)) { *error="invalid encoded tar names"; return 0; }
    if (e->type<'0' || e->type>'6' || e->mode<0 || e->mode>07777777 || e->major<0 || e->minor<0 || e->nanos<0 || e->nanos>=1000000000 || e->size!=data->byte_length || (e->type!='0' && data->byte_length)) { *error="invalid tar writer fields"; return 0; }
    if (!string_ok(e->path,4096,0) || !string_ok(e->link,4096,1) || !string_ok(e->uname,4096,1) || !string_ok(e->gname,4096,1)) { *error="tar writer name limit/NUL"; return 0; }
    int64_t count;
    if (!take_i64(p,n,&at,&count) || count<0 || count>4096) { *error="tar writer attribute count"; return 0; }
    size_t total=0;
    for (int64_t i=0;i<count;i++) {
        Blob k,v;
        if (!take_blob(p,n,&at,&k) || !take_blob(p,n,&at,&v) || !k.n || k.n>1048576 || v.n>1048576-k.n || total>1048576-k.n-v.n) { *error="tar writer attribute bounds"; return 0; }
        total+=k.n+v.n;
        for (size_t j=0;j<k.n;j++) if (k.p[j]<33 || k.p[j]>126 || k.p[j]=='=') { *error="invalid PAX writer keyword"; return 0; }
        if (sparse(k)) { *error="unsupported sparse tar writer"; return 0; }
        if (equal(k,"SCHILY.filetype") && equal(v,"sparse")) { *error="unsupported sparse tar writer"; return 0; }
        if (!standard(k) && v.n && !attrs_set(&e->attrs,k,v,1048576)) { *error="PAX writer metadata limit"; return 0; }
    }
    if (at!=n) { *error="trailing encoded tar metadata"; return 0; } return 1;
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
static int writer_header(Writer *w,Entry *e,unsigned char base[512],const char **error) {
    struct archive_entry *a=archive_entry_new(); if (!a) { *error="allocation failure"; return 0; }
    // Blob names are length-delimited; libarchive needs terminated copies.
    char *names[4]={0}; Blob fields[]={e->path,e->link,e->uname,e->gname};
    for (size_t i=0;i<4;i++) {
        names[i]=malloc(fields[i].n+1); if (!names[i]) { *error="allocation failure"; for (size_t j=0;j<i;j++) free(names[j]); archive_entry_free(a); return 0; }
        if (fields[i].n) memcpy(names[i],fields[i].p,fields[i].n); names[i][fields[i].n]=0;
    }
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
    archive_entry_free(a); for (size_t i=0;i<4;i++) free(names[i]);
    if (code<ARCHIVE_WARN || w->error || w->cn<512 || w->cn%512) { *error=w->error ? w->error : archive_error_string(w->archive); if (!*error) *error="libarchive writer header failure"; return 0; }
    // Native library generates base headers. Merge its generated PAX with raw
    // vendor attributes into ONE local extension, since multiple x headers
    // are rejected by newer libarchive versions.
    size_t at=0;
    while (w->cn-at>512) {
        const unsigned char *h=w->capture+at; int64_t n;
        if (h[156]!='x' || !number(h+124,12,&n) || n<0 || (uint64_t)n>w->cn-at-512) { *error="unexpected libarchive extension"; return 0; }
        if (!pax_parse(blob(h+512,(size_t)n),&e->attrs,1048576,0,error)) return 0;
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
        for (size_t i=0;i<e->path.n;i++) if (e->path.p[i]=='/' && i<=155 && e->path.n-i-1>0 && e->path.n-i-1<=100) split=i;
        if (split!=SIZE_MAX) { memcpy(base,e->path.p+split+1,e->path.n-split-1); memcpy(base+345,e->path.p,split); attrs_delete(&e->attrs,blob((const unsigned char *)"path",4)); }
        else { memcpy(base,"PaxEntry",8); if (!attrs_set(&e->attrs,blob((const unsigned char *)"path",4),e->path,1048576)) return 0; }
    }
    if (e->attrs.count && !set_text(&e->attrs,"hdrcharset","BINARY")) return 0;
    octal(base+100,8,(uint64_t)e->mode);
    checksum(base); return 1;
}
MinyarBytes *minyar_tararchive_writeEntry(long long handle,const MinyarBytes *info,const MinyarBytes *data) {
    Writer *w=(Writer *)(intptr_t)handle; Entry e; const char *error="tar writer metadata failure";
    if (!decode(info,data,&e,&error)) { attrs_free(&e.attrs); return result(1,error); }
    unsigned char base[512],*pax=NULL; size_t pn=0;
    if (!writer_header(w,&e,base,&error) || !pax_encode(&e.attrs,&pax,&pn)) { attrs_free(&e.attrs); free(pax); return result(1,error); }
    size_t padding=(512-(size_t)data->byte_length%512)%512;
    size_t extra=pn ? 512+pn+(512-pn%512)%512 : 0;
    if (w->length>w->maximum-1024 || (uint64_t)data->byte_length>w->maximum-1024-w->length || padding+512+extra>w->maximum-1024-w->length-(size_t)data->byte_length) {
        attrs_free(&e.attrs); free(pax); return result(1,"tar writer archive limit exceeded");
    }
    w->capturing=0;
    if (pn) {
        unsigned char h[512]={0}; memcpy(h,"PaxHeaders/entry",16); octal(h+100,8,0644); octal(h+108,8,0); octal(h+116,8,0); octal(h+124,12,pn); octal(h+136,12,0); h[156]='x'; memcpy(h+257,"ustar\00000",8); checksum(h);
        unsigned char zeros[512]={0};
        if (output_callback(NULL,w,h,512)<0 || output_callback(NULL,w,pax,pn)<0 || output_callback(NULL,w,zeros,(512-pn%512)%512)<0) w->error="tar writer extension output failure";
    }
    if (!w->error && output_callback(NULL,w,base,512)<0) w->error="tar writer base output failure";
    if (!w->error && data->byte_length && archive_write_data(w->archive,data->bytes,(size_t)data->byte_length)!=data->byte_length) w->error="libarchive writer payload failure";
    if (!w->error && archive_write_finish_entry(w->archive)!=ARCHIVE_OK) w->error="libarchive writer padding failure";
    attrs_free(&e.attrs); free(pax);
    return w->error ? result(1,w->error) : result(0,NULL);
}
MinyarBytes *minyar_tararchive_endWriter(long long handle) {
    Writer *w=(Writer *)(intptr_t)handle; w->capturing=0;
    if (archive_write_close(w->archive)!=ARCHIVE_OK || w->error) return result(1,w->error ? w->error : "libarchive writer finish failure");
    MinyarBytes *out=result(0,NULL); if (w->length) memcpy(minyar_bytes_extend(out,(long long)w->length),w->output,w->length); return out;
}
void minyar_tararchive_freeWriter(long long handle) {
    Writer *w=(Writer *)(intptr_t)handle; if (!w) return;
    // Discard libarchive's close-time footer on explicit early close/error.
    w->capturing=1; w->cn=0; archive_write_free(w->archive); free(w->output); free(w->capture); free(w);
}
