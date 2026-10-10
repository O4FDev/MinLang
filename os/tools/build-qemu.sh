#!/bin/zsh
# Build QEMU with the Cocoa display patch into build/qemu (show.sh and
# `make -C os run` use it when present).
#
# Stock QEMU draws its window with Core Graphics on the main thread. On a
# wide-gamut Mac display every full 1080p frame costs that thread tens of
# milliseconds, and it also handles input, so the pointer and animations
# judder at 120 Hz, and the window can turn gray after macOS throws its
# contents away. qemu/cocoa-layer.patch hands frames to the window server as
# IOSurfaces instead. x86_64 and aarch64 system emulation are built, for the
# two Minyar OS architectures; aarch64 runs with Apple's hypervisor on Arm Macs.
#
# Needs Xcode's command line tools, ninja, pkg-config, glib, pixman and
# libslirp (brew install ninja pkg-config glib pixman libslirp). Set PYTHON
# if the default python3 cannot create a virtual environment.
set -e
here=${0:A:h}
root=${here:h:h}
version=11.1.2
sha256=731b5681e4bb18be313231579b8efd0296c5b015fa36dc533874b639ba838016
work=$root/build/qemu-src
prefix=$root/build/qemu
mkdir -p $work
tarball=$work/qemu-$version.tar.xz
if [[ ! -f $tarball ]]; then
  curl -fL -o $tarball.part https://download.qemu.org/qemu-$version.tar.xz
  mv $tarball.part $tarball
fi
echo "$sha256  $tarball" | shasum -a 256 -c -
rm -rf $work/qemu-$version
tar -C $work -xf $tarball
cd $work/qemu-$version
patch -p1 < $here/qemu/cocoa-layer.patch
mkdir build
cd build
../configure ${PYTHON:+--python=$PYTHON} --prefix=$prefix --target-list=x86_64-softmmu,aarch64-softmmu \
  --enable-cocoa --enable-slirp --disable-dbus-display --disable-docs --disable-gtk --disable-sdl
make -j$(sysctl -n hw.ncpu)
rm -rf $prefix
make install
cd $root
rm -rf $work/qemu-$version
echo "Built $prefix/bin/qemu-system-x86_64 and qemu-system-aarch64"
