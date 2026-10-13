#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static void require(int ok, const char *reason) { if (!ok) { perror(reason); exit(1); } }
static uint64_t now(void) { struct timespec t; require(!clock_gettime(CLOCK_MONOTONIC,&t),"clock"); return (uint64_t)t.tv_sec * 1000000000 + (uint64_t)t.tv_nsec; }
static void prepare(const char *directory) {
    require(!mkdir(directory,0755),"benchmark directory");
    unsigned char *data = malloc(1048576); require(data != NULL,"benchmark memory");
    uint64_t random = 0x1782738eeb29a41full;
    for (size_t n = 0; n < 1048576; ++n) {
        random ^= random << 13; random ^= random >> 7; random ^= random << 17;
        data[n] = n % 4096 < 512 ? (unsigned char)random : (unsigned char)(n % 71 + 32);
    }
    for (int n = 0; n < 128; ++n) {
        char *path = NULL; require(asprintf(&path,"%s/file-%03d",directory,n) >= 0,"benchmark path");
        int fd = open(path,O_CREAT | O_EXCL | O_WRONLY,0644); require(fd >= 0,"benchmark file");
        for (int block = 0; block < 8; ++block) require(write(fd,data,1048576) == 1048576,"benchmark write");
        require(!close(fd),"benchmark close"); free(path);
    }
    free(data);
}
static uint64_t run(char **arguments, const char *output, uint64_t *bytes) {
    unlink(output);
    uint64_t start = now(); pid_t child = fork(); require(child >= 0,"benchmark fork");
    if (!child) { int null = open("/dev/null",O_WRONLY); require(null >= 0 && dup2(null,STDOUT_FILENO) >= 0,"benchmark stdout"); execv(arguments[0],arguments); perror(arguments[0]); _exit(127); }
    int status = 0; while (waitpid(child,&status,0) < 0) require(errno == EINTR,"benchmark wait");
    uint64_t elapsed = now() - start; require(WIFEXITED(status) && !WEXITSTATUS(status),"benchmark process");
    struct stat st; require(!stat(output,&st) && st.st_size > 0,"benchmark output"); *bytes = (uint64_t)st.st_size; unlink(output); return elapsed;
}
int main(int argc, char **argv) {
    require(argc >= 3,"benchmark arguments");
    if (!strcmp(argv[1],"prepare")) { prepare(argv[2]); return 0; }
    require(argc == 6 || argc == 7,"benchmark compare arguments");
    int layers = !strcmp(argv[1],"compare-layers");
    const char *mode = argc == 7 ? argv[6] : "none";
    require(!strcmp(mode,"none") || !strcmp(mode,"lz4") || !strcmp(mode,"zstd"),"benchmark mode");
    char *writer[] = {argv[2],argv[4],argv[5],"17592186040320",(char *)mode,NULL};
    char *mkfs[] = {argv[3],"--quiet","--preserve-mtime","--workers=1","-C65536",argv[5],argv[4],NULL,NULL,NULL};
    if (strcmp(mode,"none")) { mkfs[5] = !strcmp(mode,"lz4") ? "-zlz4" : "-zzstd,3"; mkfs[6] = argv[5]; mkfs[7] = argv[4]; }
    if (layers) {
        writer[1] = (char *)mode; writer[2] = argv[5]; writer[3] = argv[4]; writer[4] = NULL;
        size_t at = strcmp(mode,"none") ? 8 : 7; mkfs[at] = "--tar=f";
    }
    uint64_t a_bytes, b_bytes;
    printf("entry=%s mode=%s level=%s max_physical_cluster_bytes=%u workers=1 input_bytes=1073741824\n",layers ? "layers" : "directory",mode,!strcmp(mode,"zstd") ? "3" : !strcmp(mode,"lz4") ? "default-fast" : "none",strcmp(mode,"none") ? 65536u : 4096u); fflush(stdout);
    run(writer,argv[5],&a_bytes); run(mkfs,argv[5],&b_bytes);
    for (int n = 0; n < 5; ++n) {
        uint64_t a, b;
        if (n & 1) { b = run(mkfs,argv[5],&b_bytes); a = run(writer,argv[5],&a_bytes); }
        else { a = run(writer,argv[5],&a_bytes); b = run(mkfs,argv[5],&b_bytes); }
        printf("%s repeat=%d minyar_ns=%llu mkfs_ns=%llu ratio=%.4f minyar_bytes=%llu mkfs_bytes=%llu size_ratio=%.6f bar=%s\n",mode,n+1,(unsigned long long)a,(unsigned long long)b,(double)a/(double)b,(unsigned long long)a_bytes,(unsigned long long)b_bytes,(double)a_bytes/(double)b_bytes,a_bytes <= b_bytes + b_bytes / 100 && a < b ? "PASS" : "FAIL");fflush(stdout);
    }
    return 0;
}
