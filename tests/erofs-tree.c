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
    char *extent = join(root,"extent-mixed"), *extent_hard = join(root,"extent-hard");
    unsigned char *mixed = malloc(1048576); require(mixed != NULL, "extent memory");
    int extent_fd = open(extent,O_CREAT | O_EXCL | O_WRONLY,0641); require(extent_fd >= 0, "extent file");
    uint64_t random = 0x1782738eeb29a41full;
    for (unsigned block = 0; block < 4; ++block) {
        for (size_t n = 0; n < 1048576; ++n) {
            random ^= random << 13; random ^= random >> 7; random ^= random << 17;
            mixed[n] = block == 0 ? (unsigned char)random : block == 1 ? 0 : block == 2 ? (unsigned char)(n % 71 + 32) : n % 4096 < 512 ? (unsigned char)random : (unsigned char)(n % 71 + 32);
        }
        require(write(extent_fd,mixed,1048576) == 1048576, "extent content");
    }
    require(write(extent_fd,mixed,4097) == 4097 && !close(extent_fd), "extent tail");
    free(mixed); require(!link(extent,extent_hard), "extent hardlink");
    struct timespec extent_times[2] = {{-2,750000000},{1700000999,123456789}};
    require(!utimensat(AT_FDCWD,extent,extent_times,AT_SYMLINK_NOFOLLOW), "extent time");
    free(extent);free(extent_hard);
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
static void layer_metadata(const char *path, mode_t mode, uid_t uid, gid_t gid) {
    require(!lchown(path,uid,gid), "layer ownership");
    struct stat st; require(!lstat(path,&st), "layer stat");
    if (!S_ISLNK(st.st_mode)) require(!chmod(path,mode), "layer mode");
    struct timespec times[2] = {{-2,750000000},{1700000500,123456789}};
    require(!utimensat(AT_FDCWD,path,times,AT_SYMLINK_NOFOLLOW), "layer time");
}
static void layer_file(const char *root, const char *name, const char *data, mode_t mode) {
    char *path = join(root,name); int fd = open(path,O_CREAT | O_EXCL | O_WRONLY,mode);
    require(fd >= 0 && write(fd,data,strlen(data)) == (ssize_t)strlen(data) && !close(fd), "layer content");
    layer_metadata(path,mode,70000,80000);free(path);
}
static void layer_acl(const char *path, const char *key, int defaults) {
    unsigned char value[44] = {2};
    const unsigned tags[] = {1,2,4,16,32}, access[] = {6,4,4,4,0}, directory[] = {7,7,5,7,1};
    for (unsigned n = 0; n < 5; ++n) {
        value[4 + n * 8] = (unsigned char)tags[n]; value[6 + n * 8] = (unsigned char)(defaults ? directory[n] : access[n]);
        uint32_t id = n == 1 ? 1234 : UINT32_MAX;
        for (unsigned b = 0; b < 4; ++b) value[8 + n * 8 + b] = (unsigned char)(id >> (b * 8));
    }
    require(!lsetxattr(path,key,value,sizeof(value),0), "layer ACL");
}
static void layered(const char *root) {
    char *many = join(root,"many"); struct dirent **entries;
    int count = scandir(many,&entries,visible,order); require(count >= 0, "opaque directory");
    for (int n = 0; n < count; ++n) { char *path = join(many,entries[n]->d_name); require(!unlink(path), "opaque removal"); free(path);free(entries[n]); }
    free(entries);
    layer_file(root,"many/new-first","before",0641); layer_file(root,"many/new-last","after",0641);
    layer_file(root,"dir-to-file","now-file",0641);
    char *switch_dir = join(root,"switch"); require(!mkdir(switch_dir,0751), "replacement directory");
    layer_file(root,"switch/new","new",0641); layer_metadata(switch_dir,0751,70000,80000);free(switch_dir);
    layer_file(root,"new-data","layer-data",0640);
    char *data = join(root,"new-data"); unsigned char binary[] = {0,255,61,10,0};
    require(!lsetxattr(data,"user.layer",binary,sizeof(binary),0) && !lsetxattr(data,"trusted.layer","trusted",7,0), "layer xattrs");
    layer_acl(data,"system.posix_acl_access",0);
    unsigned char capability[20] = {1,0,0,2,0,4};
    require(!lsetxattr(data,"security.capability",capability,sizeof(capability),0), "layer capability");
    const char *aliases[] = {"forward-one","forward-two"};
    for (unsigned n = 0; n < 2; ++n) { char *path = join(root,aliases[n]); require(!link(data,path), "forward hardlink"); free(path); }
    free(data);
    layer_file(root,"Főtanúsítvány.pem","unicode-cert",0640);
    char *unicode = join(root,"Főtanúsítvány.pem"), *unicode_hard = join(root,"unicode-hard"), *unicode_link = join(root,"unicode-link");
    require(!link(unicode,unicode_hard) && !symlink("Főtanúsítvány.pem",unicode_link), "Unicode layer links");
    layer_metadata(unicode_link,0777,70000,80000);free(unicode);free(unicode_hard);free(unicode_link);
    layer_file(root,"epoch","epoch",0641);
    char *epoch = join(root,"epoch"); struct timespec epoch_times[2] = {{-1,750000000},{-1,750000000}};
    require(!utimensat(AT_FDCWD,epoch,epoch_times,AT_SYMLINK_NOFOLLOW), "negative fractional epoch");free(epoch);
    char *hard = join(root,"hard"), *kept = join(root,"kept"); require(!link(hard,kept), "retained lower hardlink");free(hard);free(kept);
    char *sym = join(root,"symlink"); require(!unlink(sym) && !symlink("./hard",sym), "replaced symlink"); layer_metadata(sym,0777,1234,2345);free(sym);
    char *fifo = join(root,"fifo"); require(!unlink(fifo) && !mkfifo(fifo,0640), "replaced fifo"); layer_metadata(fifo,0640,1234,2345);free(fifo);
    const char *devices[] = {"char","block"};
    for (unsigned n = 0; n < 2; ++n) {
        char *path = join(root,devices[n]); mode_t mode = n ? 0640 : 0600;
        require(!mknod(path,(n ? S_IFBLK : S_IFCHR) | mode,makedev(n ? 259 : 4095,1048575)), "layer device");
        layer_metadata(path,mode,1234,2345);free(path);
    }
    require(!lsetxattr(root,"user.root",binary,sizeof(binary),0), "root xattr");layer_acl(root,"system.posix_acl_default",1);
    struct timespec times[2] = {{-2,750000000},{-2,750000000}};
    require(!utimensat(AT_FDCWD,many,times,AT_SYMLINK_NOFOLLOW) && !utimensat(AT_FDCWD,root,times,AT_SYMLINK_NOFOLLOW), "layer directory time");free(many);
}
static int guest(void) {
    require(!mount("proc","/proc","proc",0,NULL) && !mount("sysfs","/sys","sysfs",0,NULL) && !mount("devtmpfs","/dev","devtmpfs",0,NULL), "guest mounts");
    require(!mount("tmpfs","/scratch","tmpfs",0,NULL), "guest scratch");
    unsigned uid = 0, gid = 0; FILE *owner = fopen("/owner","r"); require(owner && fscanf(owner,"%u %u",&uid,&gid) == 2, "guest owner"); fclose(owner);
    create("/scratch/source"); ownership("/scratch/source",uid,gid);
    if (!access("/layers",F_OK)) layered("/scratch/source");
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
