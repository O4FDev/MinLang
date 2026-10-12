/* Maintained C codec full operations, same corpus/cap/levels and lifetimes. */
#define _POSIX_C_SOURCE 200809L
#define ZSTD_STATIC_LINKING_ONLY
#include <zstd.h>
#include <zlib.h>
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
static uint64_t clock_ns(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t); return (uint64_t)t.tv_sec*1000000000+(uint64_t)t.tv_nsec; }
static unsigned char *read_all(const char *path,size_t *n) {
    FILE *f=fopen(path,"rb"); assert(f); assert(!fseek(f,0,SEEK_END)); long size=ftell(f); assert(size>=0); rewind(f);
    *n=(size_t)size; unsigned char *p=malloc(*n+1); assert(p); assert(fread(p,1,*n,f)==*n); fclose(f); return p;
}
static size_t deflate_op(int compress,int format,const void *in,size_t n,void *out,size_t cap) {
    assert(n<=UINT32_MAX && cap<=UINT32_MAX);
    z_stream z={0}; int w=format==0 ? 31 : format==1 ? 15 : -15;
    int r=compress ? deflateInit2(&z,6,Z_DEFLATED,w,8,Z_DEFAULT_STRATEGY) : inflateInit2(&z,w); assert(r==Z_OK);
    z.next_in=(Bytef *)in; z.avail_in=(uInt)n; z.next_out=out; z.avail_out=(uInt)cap;
    r=compress ? deflate(&z,Z_FINISH) : inflate(&z,Z_FINISH); assert(r==Z_STREAM_END && z.avail_in==0);
    size_t count=cap-z.avail_out;
    if(compress) deflateEnd(&z); else inflateEnd(&z);
    return count;
}
int main(int argc,char **argv) {
    assert(argc==8);
    const char *codec=argv[1], *operation=argv[2], *style=argv[3]; size_t n,dn;
    unsigned char *in=read_all(argv[4],&n), *dict=read_all(argv[5],&dn);
    size_t cap=(size_t)strtoull(argv[6],NULL,10), rounds=(size_t)strtoull(argv[7],NULL,10);
    unsigned char *out=calloc(cap+1,1); assert(out);
    ZSTD_CCtx *c=ZSTD_createCCtx(); ZSTD_DCtx *d=ZSTD_createDCtx(); assert(c&&d);
    ZSTD_CDict *cd=ZSTD_createCDict_advanced(dict,dn,ZSTD_dlm_byCopy,ZSTD_dct_rawContent,ZSTD_getCParams(3,0,dn),ZSTD_defaultCMem);
    ZSTD_DDict *dd=ZSTD_createDDict_advanced(dict,dn,ZSTD_dlm_byCopy,ZSTD_dct_rawContent,ZSTD_defaultCMem); assert(cd&&dd);
    uint64_t started=0,total=0;
    for(size_t i=0;i<rounds+8;i++) {
        if(i==8) started=clock_ns();
        unsigned char *destination=!strcmp(style,"buffer") ? calloc(cap+1,1) : out; assert(destination);
        size_t count=0;
        if(!strcmp(operation,"build")) {
            ZSTD_CDict *tc=ZSTD_createCDict_advanced(dict,dn,ZSTD_dlm_byCopy,ZSTD_dct_rawContent,ZSTD_getCParams(3,0,dn),ZSTD_defaultCMem);
            ZSTD_DDict *td=ZSTD_createDDict_advanced(dict,dn,ZSTD_dlm_byCopy,ZSTD_dct_rawContent,ZSTD_defaultCMem); assert(tc&&td);
            ZSTD_freeCDict(tc); ZSTD_freeDDict(td); count=dn;
        } else if(!strcmp(codec,"dict")) {
            count=!strcmp(operation,"compress") ? ZSTD_compress_usingCDict(c,destination,cap,in,n,cd) : ZSTD_decompress_usingDDict(d,destination,cap,in,n,dd);
            assert(!ZSTD_isError(count));
        } else if(!strcmp(codec,"zstd")) {
            count=!strcmp(operation,"compress") ? ZSTD_compressCCtx(c,destination,cap,in,n,3) : ZSTD_decompressDCtx(d,destination,cap,in,n);
            assert(!ZSTD_isError(count));
        } else {
            count=deflate_op(!strcmp(operation,"compress"),!strcmp(codec,"gzip") ? 0 : !strcmp(codec,"zlib") ? 1 : 2,in,n,destination,cap);
        }
        if(destination!=out) free(destination);
        if(i>=8) total+=count;
    }
    uint64_t elapsed=clock_ns()-started;
    printf("%llu\n%llu\n",(unsigned long long)elapsed,(unsigned long long)total);
    ZSTD_freeCCtx(c); ZSTD_freeDCtx(d); ZSTD_freeCDict(cd); ZSTD_freeDDict(dd); free(out); free(in); free(dict);
}
