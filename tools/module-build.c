#define _DARWIN_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#define _XOPEN_SOURCE 700
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

/* Disposable, process-local build artifacts. Compiler identity is compared
 * byte-for-byte (hex encoded), with a versioned ownership-policy suffix when
 * enabled. Compiler snapshots still use only the actual executable bytes.
 * XXH64 is an accidental-corruption checksum,
 * not authentication of artifacts supplied by another party. */
#define CACHE_LIMIT (64u * 1024u * 1024u)
typedef struct { unsigned char *data; size_t size; } Bytes;
static char *cleanup_directory;
static char *cleanup_files[7];
static void cleanup(void) {
    for(size_t i=0;i<7;i++)if(cleanup_files[i])unlink(cleanup_files[i]);
    if(cleanup_directory)rmdir(cleanup_directory);
}
static const uint64_t p1=UINT64_C(11400714785074694791), p2=UINT64_C(14029467366897019727);
static const uint64_t p3=UINT64_C(1609587929392839161), p4=UINT64_C(9650029242287828579), p5=UINT64_C(2870177450012600261);
static uint64_t rol(uint64_t x,unsigned n) { return (x<<n)|(x>>(64-n)); }
static uint64_t little(const unsigned char *s,unsigned n) {
    uint64_t v=0; for(unsigned i=0;i<n;i++) v|=(uint64_t)s[i]<<(8*i); return v;
}
static uint64_t round64(uint64_t a,uint64_t v) { return rol(a+v*p2,31)*p1; }
static uint64_t artifact_hash(const unsigned char *s,size_t n) {
    const unsigned char *end=s+n; uint64_t h;
    if(n>=32) {
        uint64_t a=p1+p2,b=p2,c=0,d=0-p1;
        do { a=round64(a,little(s,8));b=round64(b,little(s+8,8));c=round64(c,little(s+16,8));d=round64(d,little(s+24,8));s+=32; } while((size_t)(end-s)>=32);
        h=rol(a,1)+rol(b,7)+rol(c,12)+rol(d,18);
        uint64_t v[4]={a,b,c,d};
        for(unsigned i=0;i<4;i++) h=(h^round64(0,v[i]))*p1+p4;
    } else h=p5;
    h+=(uint64_t)n;
    while((size_t)(end-s)>=8) { h=rol(h^round64(0,little(s,8)),27)*p1+p4; s+=8; }
    if((size_t)(end-s)>=4) { h=rol(h^(little(s,4)*p1),23)*p2+p3; s+=4; }
    while(s<end) { h=rol(h^((uint64_t)*s++*p5),11)*p1; }
    h^=h>>33;h*=p2;h^=h>>29;h*=p3;h^=h>>32;return h;
}
static void stop(const char *message) { fprintf(stderr,"module build: %s: %s\n",message,strerror(errno));exit(1); }
static void *allocate(size_t n) { void *p=malloc(n?n:1);if(!p) stop("allocation failed");return p; }
static char *join(const char *a,const char *b) {
    size_t n=strlen(a),m=strlen(b);char *s=allocate(n+m+2);memcpy(s,a,n);s[n]='/';memcpy(s+n+1,b,m+1);return s;
}
static int write_all(int fd,const void *data,size_t n) {
    const unsigned char *p=data;
    while(n) { ssize_t k=write(fd,p,n);if(k<0&&errno==EINTR) continue;if(k<=0) return 0;p+=k;n-=(size_t)k; }
    return 1;
}
static Bytes read_fd(int fd,size_t limit) {
    struct stat st; Bytes b={NULL,0};
    if(fstat(fd,&st)<0||!S_ISREG(st.st_mode)||st.st_size<0||(uintmax_t)st.st_size>limit) return b;
    b.size=(size_t)st.st_size;b.data=allocate(b.size+1);
    if(lseek(fd,0,SEEK_SET)<0) { free(b.data);return (Bytes){NULL,0}; }
    size_t at=0;
    while(at<b.size) { ssize_t n=read(fd,b.data+at,b.size-at);if(n<0&&errno==EINTR) continue;if(n<=0) {free(b.data);return (Bytes){NULL,0};}at+=(size_t)n; }
    b.data[b.size]=0;return b;
}
static Bytes read_path(const char *path,size_t limit) {
    int fd=open(path,O_RDONLY);if(fd<0)return (Bytes){NULL,0};Bytes b=read_fd(fd,limit);close(fd);return b;
}
static size_t character_count(const unsigned char *s,size_t n) {
    size_t count=0;for(size_t i=0;i<n;i++) if((s[i]&0xc0)!=0x80)count++;return count;
}
/* Decode a single character-counted UTF-8 field without copying it. */
static int field(Bytes all,size_t *cursor,Bytes *value) {
    size_t i=*cursor,count=0,digits=0;
    while(i<all.size&&all.data[i]>='0'&&all.data[i]<='9') {
        if(count>(CACHE_LIMIT-9)/10) return 0;
        count=count*10+(all.data[i++]-'0');digits++;
    }
    if(!digits||i>=all.size||all.data[i++]!='\n')return 0;
    size_t start=i;
    size_t c=0;
    while(c<count) {
        while(count-c>=16&&all.size-i>=16&&!(little(all.data+i,8)&UINT64_C(0x8080808080808080))&&!(little(all.data+i+8,8)&UINT64_C(0x8080808080808080))) { i+=16;c+=16; }
        if(c==count)break;
        if(i>=all.size)return 0;
        unsigned char lead=all.data[i];size_t width;
        if(lead<0x80)width=1;else if(lead>=0xc2&&lead<=0xdf)width=2;else if(lead>=0xe0&&lead<=0xef)width=3;else if(lead>=0xf0&&lead<=0xf4)width=4;else return 0;
        if(width>all.size-i)return 0;
        for(size_t j=1;j<width;j++)if((all.data[i+j]&0xc0)!=0x80)return 0;
        if(width==3&&((lead==0xe0&&all.data[i+1]<0xa0)||(lead==0xed&&all.data[i+1]>=0xa0)))return 0;
        if(width==4&&((lead==0xf0&&all.data[i+1]<0x90)||(lead==0xf4&&all.data[i+1]>=0x90)))return 0;
        i+=width;c++;
    }
    *value=(Bytes){all.data+start,i-start};*cursor=i;return 1;
}
static int equals(Bytes a,const char *b) { size_t n=strlen(b);return a.size==n&&!memcmp(a.data,b,n); }
static char *hexadecimal(Bytes bytes) {
    static const char digits[]="0123456789abcdef";char *out=allocate(bytes.size*2+1);
    for(size_t i=0;i<bytes.size;i++){out[2*i]=digits[bytes.data[i]>>4];out[2*i+1]=digits[bytes.data[i]&15];}out[2*bytes.size]=0;return out;
}
static int valid_cache(Bytes all,const char *compiler_hex,const char *entry,char identity[17]) {
    Bytes parts[5];size_t at=0;
    for(unsigned i=0;i<5;i++)if(!field(all,&at,&parts[i]))return 0;
    if(at!=all.size||!equals(parts[0],"minyar-local-cache-v1")||!equals(parts[1],compiler_hex)||!equals(parts[2],entry))return 0;
    char expected[17];snprintf(expected,sizeof expected,"%016" PRIx64,artifact_hash(parts[4].data,parts[4].size));
    if(!equals(parts[3],expected))return 0;
    memcpy(identity,expected,17);return 1;
}
static char *absolute_source(const char *source) {
    char *raw;
    if(source[0]=='/') raw=strdup(source);
    else { char *cwd=getcwd(NULL,0);if(!cwd)stop("current directory");raw=join(cwd,source);free(cwd); }
    if(!raw)stop("source path");
    size_t length=strlen(raw),used=1;char *out=allocate(length+2);out[0]='/';
    for(size_t i=0;i<length;) {
        while(i<length&&raw[i]=='/')i++;
        size_t start=i;while(i<length&&raw[i]!='/')i++;
        size_t n=i-start;
        if(!n||(n==1&&raw[start]=='.'))continue;
        if(n==2&&raw[start]=='.'&&raw[start+1]=='.') {
            if(used>1) { while(used>1&&out[used-1]!='/')used--;if(used>1)used--; }
        } else { if(used>1)out[used++]='/';memcpy(out+used,raw+start,n);used+=n; }
    }
    out[used]=0;free(raw);return out;
}
static void ensure_directory(const char *path) {
    char *copy=strdup(path);if(!copy)stop("cache path");
    for(char *p=copy+1;;p++) {
        if(*p=='/'||!*p) { char held=*p;*p=0;if(mkdir(copy,0700)<0&&errno!=EEXIST)stop("cache directory");*p=held;if(!held)break; }
    }
    free(copy);
}
static int compiler_run(const char *compiler,const char *entry,const char *output,int input_fd,const char *state,const char *stats,const char *error,const char *budget) {
    if(lseek(input_fd,0,SEEK_SET)<0)stop("cache seek");
    pid_t child=fork();if(child<0)stop("compiler fork");
    if(!child) {
        int err=open(error,O_WRONLY|O_CREAT|O_TRUNC,0600);if(err<0)_exit(126);
        if(dup2(err,STDERR_FILENO)<0)_exit(126);close(err);
        if(fcntl(input_fd,F_SETFD,0)<0)_exit(126);
        char path[64];snprintf(path,sizeof path,"/dev/fd/%d",input_fd);
        char *const args[]={(char *)compiler,(char *)entry,(char *)output,"--module-state",path,(char *)state,(char *)stats,budget?"--bounded-owners":NULL,(char *)budget,NULL};
        execv(compiler,args);perror("module compiler");_exit(127);
    }
    int status;while(waitpid(child,&status,0)<0){if(errno!=EINTR)stop("compiler wait");}
    return WIFEXITED(status)?WEXITSTATUS(status):1;
}
static void atomic_bytes(const char *path,Bytes bytes) {
    size_t n=strlen(path);char *temporary=allocate(n+16);snprintf(temporary,n+16,"%s.tmp.XXXXXX",path);
    int fd=mkstemp(temporary);if(fd<0)stop("output temporary file");
    if(!write_all(fd,bytes.data,bytes.size)||close(fd)<0){unlink(temporary);stop("output write");}
    if(rename(temporary,path)<0){unlink(temporary);stop("output publish");}free(temporary);
}
static int publish_executable(const char *path,Bytes bytes) {
    size_t n=strlen(path);char *temporary=allocate(n+16);snprintf(temporary,n+16,"%s.tmp.XXXXXX",path);
    int fd=mkstemp(temporary);if(fd<0)stop("compiler image temporary file");
    if(!write_all(fd,bytes.data,bytes.size)||fchmod(fd,0700)<0||close(fd)<0){unlink(temporary);stop("compiler image write");}
    int published=link(temporary,path)==0;
    int saved_errno=errno;unlink(temporary);free(temporary);
    if(!published&&saved_errno!=EEXIST){errno=saved_errno;stop("compiler image publish");}
    return published;
}
static int same_bytes(Bytes a,Bytes b) { return a.data&&b.data&&a.size==b.size&&!memcmp(a.data,b.data,a.size); }
static char *snapshot_compiler(const char *directory,Bytes compiler) {
    /* Published compiler images are never replaced or edited by the driver.
     * The hash selects a filename; exact bytes decide identity. A collision
     * or corrupt image gets another slot. Concurrent publication is exclusive.
     * Executing the persistent inode directly avoids macOS verification work
     * caused by adding/removing an executable hard link on every invocation. */
    char *images=join(directory,"compiler-images");ensure_directory(images);
    uint64_t hash=artifact_hash(compiler.data,compiler.size);
    for(unsigned attempt=0;attempt<16;attempt++) {
        char name[80];snprintf(name,sizeof name,"%016" PRIx64 "-%zu-%u",hash,compiler.size,attempt);
        char *path=join(images,name);Bytes old=read_path(path,16u*1024u*1024u);
        if(same_bytes(old,compiler)&&access(path,X_OK)==0){free(old.data);free(images);return path;}
        if(old.data){free(old.data);free(path);continue;}
        if(publish_executable(path,compiler)){free(images);return path;}
        old=read_path(path,16u*1024u*1024u);int matches=same_bytes(old,compiler);free(old.data);
        if(matches&&access(path,X_OK)==0){free(images);return path;}
        free(path);
    }
    errno=EAGAIN;stop("too many conflicting compiler images");return NULL;
}
static int write_field(int fd,const unsigned char *data,size_t bytes) {
    char prefix[40];int n=snprintf(prefix,sizeof prefix,"%zu\n",character_count(data,bytes));
    return n>0&&write_all(fd,prefix,(size_t)n)&&write_all(fd,data,bytes);
}
static void publish_cache(const char *path,const char *compiler_hex,const char *entry,Bytes state) {
    if(state.size+strlen(compiler_hex)+strlen(entry)+160>CACHE_LIMIT)return;
    size_t n=strlen(path);char *temporary=allocate(n+16);snprintf(temporary,n+16,"%s.tmp.XXXXXX",path);
    int fd=mkstemp(temporary);if(fd<0)stop("cache temporary file");
    const char *magic="minyar-local-cache-v1";char checksum[17];snprintf(checksum,sizeof checksum,"%016" PRIx64,artifact_hash(state.data,state.size));
    int ok=write_field(fd,(const unsigned char *)magic,strlen(magic))
        &&write_field(fd,(const unsigned char *)compiler_hex,strlen(compiler_hex))
        &&write_field(fd,(const unsigned char *)entry,strlen(entry))
        &&write_field(fd,(const unsigned char *)checksum,strlen(checksum))
        &&write_field(fd,state.data,state.size);
    if(close(fd)<0)ok=0;
    if(!ok||rename(temporary,path)<0){unlink(temporary);stop("cache publish");}free(temporary);
}
static void checksum_self_test(void) {
    if(artifact_hash((const unsigned char *)"",0)!=UINT64_C(0xef46db3751d8e999)
       ||artifact_hash((const unsigned char *)"a",1)!=UINT64_C(0xd24ec4f1a98c6e5b)
       ||artifact_hash((const unsigned char *)"abc",3)!=UINT64_C(0x44bc2cf5ad770999)) {
        fputs("module build: checksum self-test failed\n",stderr);exit(1);
    }
}
/* Saturate the useful compiler budget, but validate every ASCII digit. The
 * forwarded spelling is preserved; only the effective owner limit keys code.
 * K1 emits ordinary code and deliberately shares the ordinary cache. */
static int owner_limit_for_budget(const char *text,unsigned *limit) {
    unsigned value=0;
    if(!*text)return 0;
    for(const unsigned char *p=(const unsigned char *)text;*p;p++) {
        if(*p<'0'||*p>'9')return 0;
        if(value<9) { value=value*10+(*p-'0');if(value>9)value=9; }
    }
    if(!value)return 0;
    *limit=value-1;return 1;
}
int main(int argc,char **argv) {
    checksum_self_test();
    if(argc==2&&!strcmp(argv[1],"--checksum-self-test"))return 0;
    int positional=argc;const char *budget=NULL;unsigned owner_limit=0;
    if(argc>=7&&!strcmp(argv[argc-2],"--bounded-owners")) {
        budget=argv[argc-1];positional-=2;
        if(!owner_limit_for_budget(budget,&owner_limit)) {
            fputs("module build: ownership budget must be a positive ASCII decimal integer\n",stderr);return 2;
        }
    }
    if((positional!=5&&positional!=6)||(positional==6&&!strcmp(argv[5],"--bounded-owners"))) {
        fputs("usage: module-build COMPILER SOURCE LLVM CACHE_DIRECTORY [STATS] [--bounded-owners BUDGET]\n",stderr);return 2;
    }
    umask(077);
    char *compiler=realpath(argv[1],NULL);if(!compiler)stop("compiler path");
    Bytes compiler_bytes=read_path(compiler,16u*1024u*1024u);if(!compiler_bytes.data)stop("compiler identity");
    char *compiler_hex=hexadecimal(compiler_bytes);
    if(owner_limit) {
        size_t length=strlen(compiler_hex);char *identity=allocate(length+40);
        snprintf(identity,length+40,"%s:stack-owners-v1:%u",compiler_hex,owner_limit);
        free(compiler_hex);compiler_hex=identity;
    }
    char *entry=absolute_source(argv[2]);ensure_directory(argv[4]);
    char key[80];uint64_t entry_hash=artifact_hash((const unsigned char *)entry,strlen(entry));
    if(owner_limit)snprintf(key,sizeof key,"%016" PRIx64 "-stack-owners-v1-%u.cache",entry_hash,owner_limit);
    else snprintf(key,sizeof key,"%016" PRIx64 ".cache",entry_hash);
    char *cache=join(argv[4],key);
    size_t cache_length=strlen(cache);char *delta=allocate(cache_length+7);snprintf(delta,cache_length+7,"%s.delta",cache);
    char *work=join(argv[4],"invocation.XXXXXX");if(!mkdtemp(work))stop("invocation directory");
    cleanup_directory=work;if(atexit(cleanup)!=0)stop("cleanup registration");
    char *snapshot=snapshot_compiler(argv[4],compiler_bytes);
    free(compiler_bytes.data);
    char *empty=join(work,"empty"),*output=join(work,"program.ll"),*state=join(work,"next.state"),*stats=join(work,"stats"),*error=join(work,"stderr");
    cleanup_files[0]=empty;cleanup_files[1]=output;cleanup_files[2]=state;cleanup_files[3]=stats;cleanup_files[4]=error;
    int empty_fd=open(empty,O_RDWR|O_CREAT|O_EXCL,0600);if(empty_fd<0)stop("empty cache input");
    int base_fd=open(cache,O_RDONLY|O_CLOEXEC);int cache_valid=0;
    char base_identity[17];
    if(base_fd>=0) { Bytes old=read_fd(base_fd,CACHE_LIMIT);if(old.data){cache_valid=valid_cache(old,compiler_hex,entry,base_identity);free(old.data);}if(!cache_valid){close(base_fd);base_fd=-1;} }
    int input_fd=empty_fd,delta_fd=-1,plan_fd=-1;
    char *plan_path=join(work,"plan");cleanup_files[6]=plan_path;
    if(cache_valid) {
        delta_fd=open(delta,O_RDONLY|O_CLOEXEC);
        if(delta_fd>=0) {
            Bytes saved=read_fd(delta_fd,CACHE_LIMIT);char identity[17];
            int valid=saved.data&&valid_cache(saved,compiler_hex,entry,identity);
            free(saved.data);if(!valid){close(delta_fd);delta_fd=-1;}
        }
        plan_fd=open(plan_path,O_RDWR|O_CREAT|O_EXCL,0600);if(plan_fd<0)stop("cache plan");
        char base_path[64],delta_path[64];
        snprintf(base_path,sizeof base_path,"/dev/fd/%d",base_fd);
        snprintf(delta_path,sizeof delta_path,"/dev/fd/%d",delta_fd>=0?delta_fd:empty_fd);
        const char *magic="minyar-module-plan-v1";
        if(!write_field(plan_fd,(const unsigned char *)magic,strlen(magic))
            ||!write_field(plan_fd,(const unsigned char *)base_path,strlen(base_path))
            ||!write_field(plan_fd,(const unsigned char *)delta_path,strlen(delta_path))
            ||!write_field(plan_fd,(const unsigned char *)base_identity,strlen(base_identity)))stop("cache plan write");
        if(fcntl(base_fd,F_SETFD,0)<0||(delta_fd>=0&&fcntl(delta_fd,F_SETFD,0)<0))stop("cache plan descriptors");
        input_fd=plan_fd;
    }
    int result=compiler_run(snapshot,entry,output,input_fd,state,stats,error,budget);
    if(result&&cache_valid)result=compiler_run(snapshot,entry,output,empty_fd,state,stats,error,budget);
    if(!result) {
        Bytes diagnostic=read_path(stats,4096);struct stat state_stat;
        unsigned long long counters[6];char reused_table[6],extra;
        int parsed=diagnostic.data?sscanf((const char *)diagnostic.data,"%llu %llu %llu %llu %llu %llu %5s %c",&counters[0],&counters[1],&counters[2],&counters[3],&counters[4],&counters[5],reused_table,&extra):0;
        if(parsed!=7||(strcmp(reused_table,"true")&&strcmp(reused_table,"false"))||stat(state,&state_stat)<0||!S_ISREG(state_stat.st_mode)) {
            errno=EPROTO;stop("compiler did not produce module artifacts");
        }
        if(rename(output,argv[3])<0) {
            if(errno!=EXDEV)stop("compiler output publish");
            Bytes llvm=read_path(output,SIZE_MAX-1);if(!llvm.data)stop("compiler output");atomic_bytes(argv[3],llvm);free(llvm.data);
        }
        if(positional==6)atomic_bytes(argv[5],diagnostic);
        free(diagnostic.data);
        Bytes fresh=read_path(state,CACHE_LIMIT);
        if(fresh.data&&fresh.size) {
            size_t cursor=0;Bytes schema;
            if(!field(fresh,&cursor,&schema)){errno=EPROTO;stop("invalid compiler state");}
            if(equals(schema,"minyar-module-delta-v2"))publish_cache(delta,compiler_hex,entry,fresh);
            else if(equals(schema,"minyar-module-interface-v4"))publish_cache(cache,compiler_hex,entry,fresh);
            else {errno=EPROTO;stop("unsupported compiler state");}
        }
        free(fresh.data);
    } else { Bytes message=read_path(error,1024u*1024u);if(message.data){(void)write_all(STDERR_FILENO,message.data,message.size);free(message.data);} }
    if(plan_fd>=0)close(plan_fd);if(base_fd>=0)close(base_fd);if(delta_fd>=0)close(delta_fd);close(empty_fd);
    cleanup();
    cleanup_directory=NULL;for(size_t i=0;i<7;i++)cleanup_files[i]=NULL;
    free(compiler);free(compiler_hex);free(entry);free(cache);free(work);free(empty);free(output);free(state);free(stats);free(error);free(snapshot);free(delta);free(plan_path);
    return result;
}
