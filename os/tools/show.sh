#!/bin/zsh
# Boot the current image in a visible QEMU window (full screen, four
# processors), replacing any window this script started before. ARCH=arm64
# boots the Arm build (with Apple's hypervisor on an Arm Mac); the default is
# the x86_64 build. The serial
# console goes to /tmp/minyar-visible-serial.txt and the QEMU monitor listens on
# /tmp/minyar-visible.sock (try: echo "screendump /tmp/s.ppm" | nc -U /tmp/minyar-visible.sock);
# QMP listens on /tmp/minyar-visible-qmp.sock for MOS_ATTACH in qemu-drive.py.
here=${0:A:h}
# zsh starts background jobs at a lower priority; QEMU should not be.
setopt no_bg_nice
# Without this macOS throttles QEMU (App Nap) while its window is hidden or the
# screen is locked, and the guest crawls until the window is seen again.
arch=${ARCH:-x86_64}
case $arch in
  x86_64) system=qemu-system-x86_64 ;;
  arm64) system=qemu-system-aarch64 ;;
  *) echo "ARCH must be x86_64 or arm64" >&2; exit 2 ;;
esac
defaults write $system NSAppSleepDisabled -bool YES
build=$here/../../build/os/$arch
image=$build/minyar-os.img
# QEMU with the Cocoa display patch (os/tools/build-qemu.sh) if it is built:
# stock QEMU draws the window on the CPU, which stalls input at 120 Hz.
# The patched build scales whole frames on the GPU, so it fills the screen;
# stock QEMU scales each update separately and leaves seams, so it stays 1:1.
qemu=${QEMU:-$here/../../build/qemu/bin/$system}
zoom=zoom-to-fit=on,zoom-interpolation=on
[[ -x $qemu ]] || { qemu=$system; zoom=zoom-to-fit=off; }
pkill -f "qemu-system-.*minyar-visible.img" 2>/dev/null
sleep 0.5
cp "$image" /tmp/minyar-visible.img
if [[ $arch == arm64 ]]; then
  cp "$build/kernel.elf" /tmp/minyar-visible.elf
  accel=tcg; cpu=max
  [[ $(uname -s)-$(uname -m) == Darwin-arm64 ]] && { accel=hvf; cpu=host; }
  machine=(-M virt -accel $accel -cpu $cpu -kernel /tmp/minyar-visible.elf -device bochs-display
    -drive if=none,id=disk,file=/tmp/minyar-visible.img,format=raw -device virtio-blk-pci,drive=disk,disable-legacy=on
    -device virtio-keyboard-pci,disable-legacy=on -device virtio-tablet-pci,disable-legacy=on
    -device virtio-rng-pci,disable-legacy=on)
else
  machine=(-cpu max -accel tcg,thread=multi -vga std -drive file=/tmp/minyar-visible.img,format=raw,if=ide)
fi
pid=$(python3 - "$qemu" -name "Minyar OS" -m 1G -smp 4 "${machine[@]}" \
  -display cocoa,full-screen=on,$zoom \
  -serial file:/tmp/minyar-visible-serial.txt -monitor unix:/tmp/minyar-visible.sock,server,nowait -qmp unix:/tmp/minyar-visible-qmp.sock,server,nowait \
  -netdev user,id=net0 -device e1000,netdev=net0 <<'PY'
import subprocess, sys
# A separate session survives terminal/tool process-group cleanup as well as
# SIGHUP. nohup alone still left QEMU attached to the launching tool's group.
with open('/tmp/minyar-visible.log', 'wb') as log:
    process = subprocess.Popen(sys.argv[1:], stdin=subprocess.DEVNULL,
                               stdout=log, stderr=log, start_new_session=True)
print(process.pid)
PY
)
sleep 2
if ! kill -0 "$pid" 2>/dev/null; then
  cat /tmp/minyar-visible.log >&2
  exit 1
fi
osascript -e 'tell application "System Events" to set frontmost of (first process whose name contains "qemu") to true' 2>/dev/null
echo "Minyar OS started (pid $pid, $qemu)"
