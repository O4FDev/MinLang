set -eu
export LC_ALL=C
test "$(uname -s)" = Linux
clang=${MINYAR_TEST_CLANG:-/usr/lib/llvm-23/bin/clang}
fsck=${MINYAR_EROF_FSCK:-/usr/bin/fsck.erofs}
"$clang" --version | head -1 | grep -F '23.1.3'
mkdir -p 'build'
work=$(mktemp -d "$PWD/build/erofs-layers-check.XXXXXXXX")
fallback=''
trap 'rm -rf "$work"; if test -n "$fallback"; then rm -rf "$fallback"; fi' EXIT
MINYAR_CLANG="$clang" './minyar' 'tests/erofs-layers.min' -o "$work/fixtures"
MINYAR_CLANG="$clang" './minyar' 'tests/erofs-layer-driver.min' -o "$work/writer"
"$clang" -std=c11 -O2 -Wall -Wextra -Werror -static 'tests/erofs-tree.c' -o "$work/tree"
"$work/tree" create "$work/source"
tar --format=pax --xattrs --acls --numeric-owner --owner=70000 --group=80000 -cf "$work/base.tar" -C "$work/source" .
"$work/fixtures" "$work"
test ! -e "$work/invalid.erofs"
"$work/writer" none "$work/unicode.erofs" "$work/unicode.tar"
"$fsck" --extract="$work/unicode" --no-preserve-owner "$work/unicode.erofs"
printf '%s' unicode-cert > "$work/unicode.expected"
cmp "$work/unicode.expected" "$work/unicode/Főtanúsítvány.pem"
test "$(readlink "$work/unicode/unicode-link")" = 'Főtanúsítvány.pem'
test "$(stat -c %i "$work/unicode/Főtanúsítvány.pem")" = "$(stat -c %i "$work/unicode/unicode-hard")"
for kind in worker helper legacy legacy-helper; do
    if './build/minyarc' "tests/erofs-layers-thread-$kind.min" "$work/$kind.ll" --library "$PWD/library" > "$work/$kind.log" 2>&1; then cat "$work/$kind.log"; exit 1; fi
    grep -F "native 'minyar_erofs_layersStatus' 8(8,2,1,1,1)" "$work/$kind.log"
    test ! -e "$work/$kind.ll"
done
MINYAR_CLANG="$clang" './minyar' 'tests/erofs-layers-thread-main.min' -o "$work/thread-main"
"$work/thread-main" "$work" "$work/thread-main.erofs"
"$fsck" --extract "$work/thread-main.erofs"
images='none lz4'
if test "${MINYAR_EROF_ZSTD_KERNEL:-}" != ''; then images="$images zstd"; fi
for mode in $images; do
    "$work/writer" "$mode" "$work/$mode.erofs" "$work/base.tar" "$work/additions.tar" "$work/upper.tar.zstd"
    "$fsck" --extract "$work/$mode.erofs"
done
"$work/writer" none "$work/gzip.erofs" "$work/base.tar" "$work/additions.tar" "$work/upper.tar.gz"
"$work/writer" none "$work/raw.erofs" "$work/base.tar" "$work/additions.tar" "$work/upper.tar"
cmp "$work/none.erofs" "$work/gzip.erofs"
cmp "$work/none.erofs" "$work/raw.erofs"
if test -d '/dev/shm' && test "$(stat -c %d '/dev/shm')" != "$(stat -c %d "$work")"; then
    fallback=$(mktemp -d '/dev/shm/minyar-erofs-layers.XXXXXXXX')
    cp "$work/base.tar" "$fallback/base.tar"
    "$work/writer" none "$work/fallback.erofs" "$fallback/base.tar" "$work/additions.tar" "$work/upper.tar"
    cmp "$work/none.erofs" "$work/fallback.erofs"
    "$fsck" --extract "$work/fallback.erofs"
fi
for kind in 0 1 2 3 4 5 6 7 8 9; do
    cp "$work/none.erofs" "$work/unchanged.erofs"
    if "$work/writer" none "$work/unchanged.erofs" "$work/bad-$kind.tar"; then exit 1; fi
    cmp "$work/none.erofs" "$work/unchanged.erofs"
done
test -z "$(find "$work" -name '*.erofs-??????' -o -name '*.layers-??????')"
if test "${MINYAR_EROF_KERNEL:-}" != ''; then
    cp "$MINYAR_EROF_KERNEL" "$work/bzImage"
    mkdir -p "$work/boot/proc" "$work/boot/sys" "$work/boot/dev" "$work/boot/mnt" "$work/boot/scratch"
    cp "$work/tree" "$work/boot/init"
    printf '70000 80000\n' > "$work/boot/owner"
    : > "$work/boot/layers"
    MINYAR_CLANG="$clang" './minyar' 'tests/erofs.min' -o "$work/directory-writer"
    "$work/directory-writer" "$work/boot" "$work/boot.erofs"
    "$fsck" --extract "$work/boot.erofs"
    for image in $images; do
        kernel=$work/bzImage
        if test "$image" = zstd; then cp "$MINYAR_EROF_ZSTD_KERNEL" "$work/bzImage-zstd"; kernel=$work/bzImage-zstd; fi
        timeout 60 qemu-system-x86_64 -enable-kvm -cpu host -smp 2 -m 512 -nodefaults -no-reboot -nographic -serial stdio -kernel "$kernel" -append 'console=ttyS0 panic=-1 root=/dev/vda rootfstype=erofs ro init=/init' -drive "file=$work/boot.erofs,format=raw,if=virtio,readonly=on" -drive "file=$work/$image.erofs,format=raw,if=virtio,readonly=on" > "$work/guest.log" 2>&1
        tr -d '\r' < "$work/guest.log" > "$work/guest.txt"
        cat "$work/guest.txt"
        grep -Fx EROFS_KVM_PASS "$work/guest.txt"
    done
fi
printf '%s\n' EROFS_LAYERS_CHECK_PASS
