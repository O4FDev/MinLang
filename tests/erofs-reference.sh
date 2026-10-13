set -eu
test "$(uname -s)" = Linux
clang=${MINYAR_TEST_CLANG:-/usr/lib/llvm-23/bin/clang}
"$clang" --version | head -1 | grep -F '23.1.2'
work=$PWD/build/erofs-utils-1.8.10
mkdir -p "$work"
if ! test -f "$work/VERSION"; then
    curl -fL --retry 2 https://github.com/erofs/erofs-utils/archive/refs/tags/v1.8.10.tar.gz -o "$work/source.tar.gz"
    tar -xzf "$work/source.tar.gz" --strip-components=1 -C "$work"
fi
cd "$work"
mkdir -p objects
: > config.h
flags=(-std=gnu11 -O2 -D_GNU_SOURCE -D_LARGEFILE64_SOURCE -D_FILE_OFFSET_BITS=64 -Iinclude -I. -DHAVE_CONFIG_H
    '-DPACKAGE_VERSION="1.8.10"' '-DPACKAGE_NAME="erofs-utils"'
    -DHAVE_LINUX_TYPES_H -DHAVE_ENDIAN_H -DHAVE_SYS_XATTR_H -DHAVE_LLISTXATTR -DHAVE_LGETXATTR
    -DHAVE_STRUCT_STAT_ST_MTIM -DHAVE_STRUCT_STAT_ST_ATIM -DHAVE_STRNLEN -DHAVE_MEMRCHR -DHAVE_FALLOCATE -DHAVE_FUTIMENS
    -DHAVE_LIBLZ4 -DLZ4_ENABLED=1 -DLZ4HC_ENABLED=1 -DHAVE_LZ4_COMPRESS_DEFAULT -DHAVE_LZ4HC -DHAVE_LZ4_COMPRESS_HC_DESTSIZE
    -DHAVE_LIBZSTD -DHAVE_ZSTD_GETFRAMECONTENTSIZE -DHAVE_SYS_RANDOM_H -DHAVE_GETRANDOM
    -DHAVE_PREAD64 -DHAVE_PWRITE64 -DHAVE_LSETXATTR -DHAVE_UTIMENSAT
    -DHAVE_UNISTD_H -DHAVE_SYSCONF -DHAVE_SYS_SYSMACROS_H -DHAVE_SYS_IOCTL_H
    -DHAVE_LINUX_FALLOC_H -DHAVE_LINUX_FS_H -DHAVE_LINUX_XATTR_H
    -DHAVE_COPY_FILE_RANGE -DHAVE_POSIX_FADVISE -DHAVE_PWRITEV
    -DHAVE_SYS_RESOURCE_H -DHAVE_GETRLIMIT -DHAVE_SYS_SENDFILE_H -DHAVE_SENDFILE
    -DHAVE_SYS_STATFS_H -DHAVE_FSTATFS -DEROFS_MT_ENABLED=1 -DHAVE_PTHREAD_H)
sources=(config io cache super inode xattr exclude namei data compress compressor zmap decompress
    compress_hints hashmap sha256 blobchunk dir fragments dedupe uuid_unparse uuid tar block_list
    rebuild diskbuf bitops dedupe_ext vmdk kite_deflate compressor_deflate xxhash
    compressor_lz4 compressor_lz4hc compressor_libzstd workqueue)
for source in "${sources[@]}"; do
    "$clang" "${flags[@]}" -c "lib/$source.c" -o "objects/$source.o"
done
for tool in fsck mkfs dump; do
    "$clang" "${flags[@]}" "$tool/main.c" objects/*.o -llz4 -lzstd -pthread -o "$tool/$tool.erofs"
done
fsck/fsck.erofs -V
mkfs/mkfs.erofs --help 2>&1 | tail -3
