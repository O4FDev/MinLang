set -eu
test "$(uname -s)" = Linux
clang=${MINYAR_TEST_CLANG:-clang-23}
"$clang" --version | head -1 | grep -F '23.1.2'
mkdir -p build
work=$(mktemp -d "$PWD/build/erofs-check.XXXXXXXX")
trap 'rm -rf "$work"' EXIT
MINYAR_CLANG="$clang" ./minyar tests/erofs.min -o "$work/writer"
MINYAR_CLANG="$clang" ./minyar tests/erofs-api.min -o "$work/api"
"$clang" -std=c11 -O2 -Wall -Wextra -Werror -static tests/erofs-tree.c -o "$work/tree"
"$work/tree" create "$work/source"
"$work/api" "$work/source" "$work/api.erofs"
test ! -e "$work/api.erofs"
for kind in worker helper legacy legacy-helper; do
    if ./build/minyarc "tests/erofs-thread-$kind.min" "$work/$kind.ll" --library "$PWD/library" > "$work/$kind.log" 2>&1; then
        cat "$work/$kind.log"
        exit 1
    fi
    grep -F "native 'minyar_erofs_directoryStatus' 8(2,2,1,1,1)" "$work/$kind.log"
    test ! -e "$work/$kind.ll"
done
MINYAR_CLANG="$clang" ./minyar tests/erofs-thread-main.min -o "$work/thread-main"
"$work/thread-main" "$work/source" "$work/thread-main.erofs"
/usr/bin/fsck.erofs --extract "$work/thread-main.erofs"
"$work/writer" "$work/source" "$work/plain.erofs"
/usr/bin/fsck.erofs --extract "$work/plain.erofs"
"$work/writer" "$work/source" "$work/lz4.erofs" 17592186040320 lz4
/usr/bin/fsck.erofs --extract "$work/lz4.erofs"
test "$(stat -c %s "$work/lz4.erofs")" -lt "$(stat -c %s "$work/plain.erofs")"
cp "$work/plain.erofs" "$work/unchanged.erofs"
if "$work/writer" "$work/source" "$work/unchanged.erofs" 8192; then exit 1; fi
cmp "$work/plain.erofs" "$work/unchanged.erofs"
test -z "$(find "$work" -name '*.erofs-??????')"
if "$work/writer" "$work/missing" "$work/plain.erofs"; then exit 1; fi
if "$work/writer" "$work/source/symlink" "$work/plain.erofs"; then exit 1; fi
if test "${MINYAR_EROF_KERNEL:-}" != ''; then
    cp "$MINYAR_EROF_KERNEL" "$work/bzImage"
    mkdir -p "$work/boot/proc" "$work/boot/sys" "$work/boot/dev" "$work/boot/mnt" "$work/boot/scratch"
    cp "$work/tree" "$work/boot/init"
    stat -c '%u %g' "$work/source" > "$work/boot/owner"
    "$work/writer" "$work/boot" "$work/boot.erofs"
    /usr/bin/fsck.erofs --extract "$work/boot.erofs"
    for image in plain lz4; do
        timeout 60 qemu-system-x86_64 -enable-kvm -cpu host -smp 2 -m 512 -nodefaults -no-reboot -nographic -serial stdio -kernel "$work/bzImage" -append 'console=ttyS0 panic=-1 root=/dev/vda rootfstype=erofs ro init=/init' -drive "file=$work/boot.erofs,format=raw,if=virtio,readonly=on" -drive "file=$work/$image.erofs,format=raw,if=virtio,readonly=on" > "$work/guest.log" 2>&1
        tr -d '\r' < "$work/guest.log" > "$work/guest.txt"
        cat "$work/guest.txt"
        grep -Fx EROFS_KVM_PASS "$work/guest.txt"
    done
fi
printf '%s\n' EROFS_CHECK_PASS
