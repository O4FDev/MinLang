#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/mount.h>
#include <sys/reboot.h>
#include <sys/sysmacros.h>
#include <sys/xattr.h>
#include <unistd.h>

static void require(int ok, const char *what) { if (!ok) { perror(what); exit(1); } }
static char *join(const char *a, const char *b) { char *p = NULL; require(asprintf(&p, "%s/%s", a, b) >= 0, "path"); return p; }
static int order(const struct dirent **a, const struct dirent **b) { return strcmp((*a)->d_name, (*b)->d_name); }
static int visible(const struct dirent *d) { return strcmp(d->d_name, ".") && strcmp(d->d_name, ".."); }
typedef struct { dev_t ad, bd; ino_t ai, bi; } Pair;
static Pair pairs[20000];
static size_t pair_count;
static void compare(const char *a, const char *b) {
    struct stat x, y;
    require(!lstat(a, &x) && !lstat(b, &y), a);
    if (x.st_mode != y.st_mode || x.st_uid != y.st_uid || x.st_gid != y.st_gid || x.st_nlink != y.st_nlink || x.st_mtim.tv_sec != y.st_mtim.tv_sec || x.st_mtim.tv_nsec != y.st_mtim.tv_nsec || x.st_rdev != y.st_rdev || (!S_ISDIR(x.st_mode) && x.st_size != y.st_size)) {
        fprintf(stderr, "metadata differs: %s %s mode=%o/%o uid=%u/%u gid=%u/%u links=%lu/%lu time=%lld.%ld/%lld.%ld size=%lld/%lld\n", a,b,x.st_mode,y.st_mode,x.st_uid,y.st_uid,x.st_gid,y.st_gid,(unsigned long)x.st_nlink,(unsigned long)y.st_nlink,(long long)x.st_mtim.tv_sec,x.st_mtim.tv_nsec,(long long)y.st_mtim.tv_sec,y.st_mtim.tv_nsec,(long long)x.st_size,(long long)y.st_size); exit(1);
    }
    for (size_t n = 0; n < pair_count; ++n) {
        int left = pairs[n].ad == x.st_dev && pairs[n].ai == x.st_ino;
        int right = pairs[n].bd == y.st_dev && pairs[n].bi == y.st_ino;
        require(left == right, "hardlink identity");
    }
    require(pair_count < 20000, "pair limit"); pairs[pair_count++] = (Pair){x.st_dev,y.st_dev,x.st_ino,y.st_ino};
    ssize_t xn = llistxattr(a, NULL, 0), yn = llistxattr(b, NULL, 0);
    require(xn >= 0 && yn >= 0 && xn == yn, "attribute names");
    char *names = malloc((size_t)xn + 1); require(names != NULL, "attribute memory");
    require(llistxattr(a, names, (size_t)xn) == xn, "attribute list");
    for (size_t n = 0; n < (size_t)xn; n += strlen(names + n) + 1) {
        ssize_t size = lgetxattr(a, names + n, NULL, 0); require(size >= 0 && lgetxattr(b, names + n, NULL, 0) == size, "attribute size");
        void *one = malloc((size_t)size + 1), *two = malloc((size_t)size + 1); require(one && two, "attribute memory");
        require(lgetxattr(a, names + n, one, (size_t)size) == size && lgetxattr(b, names + n, two, (size_t)size) == size && !memcmp(one,two,(size_t)size), "attribute value"); free(one); free(two);
    }
    free(names);
    if (S_ISREG(x.st_mode)) {
        int af = open(a, O_RDONLY), bf = open(b, O_RDONLY); require(af >= 0 && bf >= 0, "open content");
        unsigned char left[65536], right[65536];
        for (;;) { ssize_t n = read(af,left,sizeof(left)); require(n >= 0 && read(bf,right,sizeof(right)) == n, "read content"); require(!memcmp(left,right,(size_t)n), "file content"); if (!n) break; }
        close(af); close(bf);
    } else if (S_ISLNK(x.st_mode)) {
        char left[65536], right[65536]; ssize_t n = readlink(a,left,sizeof(left)); require(n >= 0 && readlink(b,right,sizeof(right)) == n && !memcmp(left,right,(size_t)n), "symlink target");
    } else if (S_ISDIR(x.st_mode)) {
        struct dirent **left, **right;
        int n = scandir(a,&left,visible,order), m = scandir(b,&right,visible,order); require(n >= 0 && n == m, "directory entries");
        for (int i = 0; i < n; ++i) { require(!strcmp(left[i]->d_name,right[i]->d_name), "entry name"); char *ap = join(a,left[i]->d_name), *bp = join(b,right[i]->d_name); compare(ap,bp); free(ap);free(bp);free(left[i]);free(right[i]); }
        free(left);free(right);
    }
}
static void create(const char *root) {
    umask(0022);
    require(!mkdir(root,0751), "create root");
    char *dir = join(root,"many"); require(!mkdir(dir,01775), "create directory");
    unsigned char data[262144]; for (size_t n = 0; n < sizeof(data); ++n) data[n] = (unsigned char)(n * 137 + n / 251);
    const size_t sizes[] = {0,1,31,32,63,64,4095,4096,4097,65535,65536,65537,131071,131072,131073,262143};
    for (size_t n = 0; n < 400; ++n) {
        char name[256]; snprintf(name,sizeof(name),"file-%04zu",n); if (n == 399) { memset(name,'x',255);name[255]=0; }
        char *path = join(dir,name); int fd = open(path,O_CREAT | O_EXCL | O_WRONLY,0641); require(fd >= 0, "create file");
        size_t size = sizes[n % (sizeof(sizes)/sizeof(sizes[0]))]; require(write(fd,data,size) == (ssize_t)size, "fixture content"); close(fd);
        unsigned char attr[] = {0,255,61,10,0}; require(!lsetxattr(path,"user.binary",attr,sizeof(attr),0), "fixture xattr");
        if (n == 10) require(!lsetxattr(path,"user.large",data,3000,0), "large fixture xattr");
        struct timespec times[2] = {{-2,750000000},{1700000000 + (time_t)n,123456789}}; require(!utimensat(AT_FDCWD,path,times,AT_SYMLINK_NOFOLLOW), "fixture time"); free(path);
    }
    char *first = join(dir,"file-0010"), *hard = join(root,"hard"), *sym = join(root,"symlink"), *fifo = join(root,"fifo");
    require(!link(first,hard), "fixture hardlink"); require(!symlink("many/../hard",sym), "fixture symlink"); require(!mkfifo(fifo,0640), "fixture fifo");
    require(!lsetxattr(dir,"user.directory","directory",9,0), "directory attribute");
    struct timespec times[2] = {{-2,750000000},{-2,750000000}};
    require(!utimensat(AT_FDCWD,sym,times,AT_SYMLINK_NOFOLLOW), "symlink time"); require(!utimensat(AT_FDCWD,fifo,times,AT_SYMLINK_NOFOLLOW), "fifo time");
    require(!utimensat(AT_FDCWD,dir,times,AT_SYMLINK_NOFOLLOW), "directory time"); require(!utimensat(AT_FDCWD,root,times,AT_SYMLINK_NOFOLLOW), "root time");
    free(dir);free(first);free(hard);free(sym);free(fifo);
}
static void ownership(const char *path, uid_t uid, gid_t gid) {
    struct stat st; require(!lstat(path,&st), "owner stat");
    require(!lchown(path,uid,gid), "fixture ownership");
    if (!S_ISDIR(st.st_mode)) return;
    struct dirent **entries; int count = scandir(path,&entries,visible,order); require(count >= 0, "owner directory");
    for (int n = 0; n < count; ++n) { char *p = join(path,entries[n]->d_name); ownership(p,uid,gid); free(p);free(entries[n]); }
    free(entries);
}
static int guest(void) {
    require(!mount("proc","/proc","proc",0,NULL) && !mount("sysfs","/sys","sysfs",0,NULL) && !mount("devtmpfs","/dev","devtmpfs",0,NULL), "guest mounts");
    require(!mount("tmpfs","/scratch","tmpfs",0,NULL), "guest scratch");
    unsigned uid = 0, gid = 0; FILE *owner = fopen("/owner","r"); require(owner && fscanf(owner,"%u %u",&uid,&gid) == 2, "guest owner"); fclose(owner);
    create("/scratch/source"); ownership("/scratch/source",uid,gid);
    unsigned ma = 0, mi = 0;
    for (int n = 0; n < 100 && !ma; ++n) { FILE *dev = fopen("/sys/class/block/vdb/dev","r"); if (dev) { require(fscanf(dev,"%u:%u",&ma,&mi) == 2, "block device");fclose(dev); } else usleep(100000); }
    require(ma && !mknod("/dev/erofs-test",S_IFBLK | 0600,makedev(ma,mi)), "guest block node");
    require(!mount("/dev/erofs-test","/mnt","erofs",MS_RDONLY,NULL), "erofs mount");
    compare("/scratch/source","/mnt"); puts("EROFS_KVM_PASS"); fflush(stdout);
    require(!umount("/mnt"), "erofs unmount"); reboot(RB_POWER_OFF); return 0;
}
int main(int argc, char **argv) {
    if (argc == 1) return guest();
    require(argc >= 3, "arguments");
    if (!strcmp(argv[1],"create")) create(argv[2]);
    else { require(argc == 4, "compare arguments"); compare(argv[2],argv[3]); puts("EROFS_TREE_PASS"); }
    return 0;
}
