# Minyar OS for x86-64 PCs and 64-bit Arm, from one source tree.
#
#   make -C os                 build for x86-64 (the default ARCH)
#   make -C os ARCH=arm64      build for 64-bit Arm
#   make -C os release         build both
#   make -C os run [ARCH=...]  boot it in QEMU (serial console on this terminal)
#
# As in Linux, os/arch/$(ARCH) holds what differs (boot code, linker scripts
# and the `arch` package generic code imports) and everything else is shared.
# The package path lists os/arch/$(ARCH) first, so `use "arch" as arch` finds
# that architecture's arch.min; on Arm, library/arch/arm64 comes next, so
# `use "machine"` finds the Arm intrinsics.
#
# x86_64 builds build/os/x86_64/minyar-os.img: a bootable disk with a boot
# record, the stage-two loader, the kernel and its files. arm64 builds
# build/os/arm64/kernel.elf, which QEMU loads directly, and minyar-os.img with
# the same files for a virtio disk.
#
# Needs Homebrew LLVM (clang, ld.lld, llvm-objcopy) and QEMU.

ARCH ?= x86_64
ROOT := $(abspath ..)
OUT := $(ROOT)/build/os/$(ARCH)
LLVM_BIN ?= $(shell brew --prefix llvm 2>/dev/null)/bin
CLANG := $(LLVM_BIN)/clang
LLD := $(firstword $(wildcard $(LLVM_BIN)/ld.lld $(shell brew --prefix lld 2>/dev/null)/bin/ld.lld) ld.lld)
OBJCOPY := $(LLVM_BIN)/llvm-objcopy
MINYARC := $(ROOT)/build/minyarc
MKIMAGE := $(ROOT)/build/os/mkimage
comma := ,

ifeq ($(ARCH),x86_64)
TARGET := --target=x86_64-unknown-none-elf -march=x86-64-v2
CPU_FLAGS := -mno-red-zone
LTO_CPU := -mllvm -mcpu=x86-64-v2
PACKAGES := --library $(ROOT)/os/arch/x86_64 --library $(ROOT)/library
ENTRY := $(OUT)/entry.o
KERNEL_LD := arch/x86_64/boot/kernel.ld
QEMU_SYSTEM := qemu-system-x86_64
else ifeq ($(ARCH),arm64)
TARGET := --target=aarch64-unknown-none-elf
CPU_FLAGS :=
LTO_CPU :=
PACKAGES := --library $(ROOT)/os/arch/arm64 --library $(ROOT)/library/arch/arm64 --library $(ROOT)/library
ENTRY := $(OUT)/head.o
KERNEL_LD := arch/arm64/kernel.ld
QEMU_SYSTEM := qemu-system-aarch64
else
$(error ARCH must be x86_64 or arm64, not $(ARCH))
endif

# QEMU with the Cocoa display patch (tools/build-qemu.sh) if it is built.
QEMU ?= $(firstword $(wildcard $(ROOT)/build/qemu/bin/$(QEMU_SYSTEM)) $(QEMU_SYSTEM))
# The patched build scales whole frames on the GPU, so it can fill the screen;
# stock QEMU scales each update separately and leaves seams, so it stays 1:1.
QEMU_ZOOM ?= $(if $(wildcard $(ROOT)/build/qemu/bin/$(QEMU_SYSTEM)),zoom-to-fit=on$(comma)zoom-interpolation=on,zoom-to-fit=off)

CFLAGS := $(TARGET) -O2 -flto -ffreestanding -fno-builtin -nostdinc \
	-isystem $(shell $(CLANG) -print-resource-dir)/include \
	-isystem $(ROOT)/runtime/freestanding/include \
	$(CPU_FLAGS) -fno-stack-protector -fno-pic -Wall -Wno-unused-function
IRFLAGS := $(TARGET) -O2 -flto -fno-pic -Wno-override-module
LDFLAGS := -static --no-pie -nostdlib --lto-O3 $(LTO_CPU) -z max-page-size=4096 --image-base=0

SOURCES := $(shell find $(ROOT)/os -name "*.min") $(shell find $(ROOT)/library -name "*.min")
RUNTIME := $(OUT)/runtime.o $(OUT)/freestanding.o $(ENTRY)
ATACAMA_HOST ?= 10.0.2.2
ATACAMA_PORT ?= 8080
ATACAMA_KEY ?= minyar-local
FILES ?= config.txt=$(OUT)/config.txt fonts/Archivo-Regular.ttf=assets/fonts/Archivo-Regular.ttf fonts/Archivo-Medium.ttf=assets/fonts/Archivo-Medium.ttf fonts/Archivo-SemiBold.ttf=assets/fonts/Archivo-SemiBold.ttf

.PHONY: all release run clean compiler
all: $(OUT)/minyar-os.img $(OUT)/kernel.elf

release:
	$(MAKE) ARCH=x86_64
	$(MAKE) ARCH=arm64

compiler:
	$(MAKE) -C $(ROOT) build/minyarc

$(MINYARC):
	$(MAKE) -C $(ROOT) build/minyarc

$(OUT):
	mkdir -p $@

# ----- Boot code -----

$(OUT)/mbr.bin: arch/x86_64/boot/mbr.S | $(OUT)
	$(CLANG) $(TARGET) -c $< -o $(OUT)/mbr.o
	$(LLD) --image-base=0 -Ttext=0x7C00 --oformat=binary -e _start $(OUT)/mbr.o -o $@

$(OUT)/entry.o: arch/x86_64/boot/entry.S | $(OUT)
	$(CLANG) $(TARGET) -c $< -o $@

$(OUT)/head.o: arch/arm64/head.S | $(OUT)
	$(CLANG) $(TARGET) -c $< -o $@

# ----- Runtime -----

# The runtime is linked as LLVM bitcode so it inlines into Minyar code. Its
# per-function CPU attributes are stripped (as the hosted build does) because
# the compiler's IR has none, and LLVM never inlines a function that needs
# more CPU features than its caller declares. The CPU is chosen at link time.
# "no-builtins" (implied by -ffreestanding) blocks inlining too; it is removed
# from the language runtime but kept for the C library shim, whose memcpy must
# never be compiled into a call to memcpy.
STRIP_CPU := sed -E 's/"(target-cpu|target-features|tune-cpu)"="[^"]*" ?//g'

$(OUT)/runtime.o: $(ROOT)/runtime/freestanding/runtime.c $(wildcard $(ROOT)/runtime/*.h $(ROOT)/runtime/*.c) | $(OUT)
	$(CLANG) $(CFLAGS) -S -emit-llvm $< -o $(OUT)/runtime.ll.tmp
	$(STRIP_CPU) $(OUT)/runtime.ll.tmp | sed -E 's/"no-builtins" ?//g' > $(OUT)/runtime.ll
	$(CLANG) $(IRFLAGS) -c $(OUT)/runtime.ll -o $@

$(OUT)/freestanding.o: $(ROOT)/runtime/freestanding/freestanding.c $(wildcard $(ROOT)/runtime/freestanding/include/*.h) | $(OUT)
	$(CLANG) $(CFLAGS) -S -emit-llvm $< -o $(OUT)/freestanding.ll.tmp
	$(STRIP_CPU) $(OUT)/freestanding.ll.tmp > $(OUT)/freestanding.ll
	$(CLANG) $(IRFLAGS) -c $(OUT)/freestanding.ll -o $@

# ----- Minyar programs -----

.PRECIOUS: $(OUT)/%.ll
$(OUT)/kernel.ll: $(SOURCES) $(MINYARC) | $(OUT)
	$(MINYARC) $(ROOT)/os/kernel/main.min $@ $(PACKAGES) --bounded-owners 32 --freestanding

$(OUT)/loader.ll: $(SOURCES) $(MINYARC) | $(OUT)
	$(MINYARC) $(ROOT)/os/arch/x86_64/loader/main.min $@ $(PACKAGES) --bounded-owners 32 --freestanding

$(OUT)/%-program.o: $(OUT)/%.ll
	$(CLANG) $(IRFLAGS) -c $< -o $@

$(OUT)/loader.elf: $(OUT)/loader-program.o $(RUNTIME) arch/x86_64/boot/loader.ld
	$(LLD) $(LDFLAGS) -T arch/x86_64/boot/loader.ld $(ENTRY) $(OUT)/loader-program.o $(OUT)/runtime.o $(OUT)/freestanding.o -o $@

$(OUT)/loader.bin: $(OUT)/loader.elf
	$(OBJCOPY) -O binary $< $@

$(OUT)/kernel.elf: $(OUT)/kernel-program.o $(RUNTIME) $(KERNEL_LD)
	$(LLD) $(LDFLAGS) -T $(KERNEL_LD) $(ENTRY) $(OUT)/kernel-program.o $(OUT)/runtime.o $(OUT)/freestanding.o -o $@

# ----- Disk image -----

$(MKIMAGE): tools/mkimage.min $(MINYARC)
	mkdir -p $(dir $@)
	cd $(ROOT) && ./minyar os/tools/mkimage.min -o $@

# Rewritten only when a setting changes, so the image is not rebuilt needlessly.
$(OUT)/config.txt: FORCE | $(OUT)
	@printf 'ATACAMA_HOST=%s\nATACAMA_PORT=%s\nATACAMA_KEY=%s\n' '$(ATACAMA_HOST)' '$(ATACAMA_PORT)' '$(ATACAMA_KEY)' > $@.new
	@cmp -s $@.new $@ && rm $@.new || mv $@.new $@

.PHONY: FORCE
FORCE:

ifeq ($(ARCH),x86_64)
$(OUT)/minyar-os.img: $(MKIMAGE) $(OUT)/mbr.bin $(OUT)/loader.bin $(OUT)/kernel.elf $(OUT)/config.txt $(wildcard assets/fonts/*.ttf)
	$(MKIMAGE) $@ $(OUT)/mbr.bin $(OUT)/loader.bin kernel.elf=$(OUT)/kernel.elf $(FILES)

QEMU_FLAGS ?= -m 1G -cpu max -smp 4 -accel tcg,thread=multi -vga std -serial stdio -display cocoa,full-screen=on,$(QEMU_ZOOM) \
	-drive file=$(OUT)/minyar-os.img,format=raw,if=ide \
	-netdev user,id=net0 -device e1000,netdev=net0 \
	-device isa-debug-exit,iobase=0xf4,iosize=0x04
else
# No boot record or loader: QEMU loads kernel.elf itself, as firmware hands
# Linux its Image. The disk holds the same files.
$(OUT)/minyar-os.img: $(MKIMAGE) $(OUT)/config.txt $(wildcard assets/fonts/*.ttf)
	$(MKIMAGE) $@ - - $(FILES)

# Hardware virtualization where the host is an Arm Mac or Linux with KVM.
ACCEL ?= $(if $(filter Darwin-arm64,$(shell uname -s)-$(shell uname -m)),hvf,$(if $(wildcard /dev/kvm),kvm,tcg))
CPU ?= $(if $(filter tcg,$(ACCEL)),max,host)
QEMU_FLAGS ?= -M virt -accel $(ACCEL) -cpu $(CPU) -m 1G -smp 4 -serial stdio -display cocoa,full-screen=on,$(QEMU_ZOOM) \
	-kernel $(OUT)/kernel.elf -device bochs-display \
	-drive if=none,id=disk,file=$(OUT)/minyar-os.img,format=raw -device virtio-blk-pci,drive=disk,disable-legacy=on \
	-device virtio-keyboard-pci,disable-legacy=on -device virtio-tablet-pci,disable-legacy=on \
	-device virtio-rng-pci,disable-legacy=on \
	-netdev user,id=net0 -device e1000,netdev=net0
endif

# On macOS, keep App Nap from throttling QEMU while its window is hidden.
run: all
	-if [ "$$(uname)" = Darwin ]; then defaults write $(QEMU_SYSTEM) NSAppSleepDisabled -bool YES; fi
	$(QEMU) $(QEMU_FLAGS)

clean:
	rm -rf $(OUT)
