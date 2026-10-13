.DEFAULT_GOAL := all
CC ?= cc
CPPFLAGS ?= -isystem vendor
CFLAGS ?= -std=c11 -O2 -Wall -Wextra -Werror
LLVM_CC ?= $(if $(filter Darwin,$(shell uname -s)),clang,clang-23)
ifeq ($(origin CC),default)
CC = $(LLVM_CC)
endif
LLVM_FLAGS ?= -O2 -Wno-override-module
LDLIBS ?= -lm
SANITIZER_FLAGS ?= -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module
COMPILER_RUNTIME_FLAGS ?= -DMINYAR_COMPILER_ARENA
COMPILER_LTO_FLAGS ?= -flto=thin $(if $(filter Linux,$(shell uname -s)),$(if $(filter -fuse-ld=% --ld-path=%,$(LLVM_FLAGS)),,-fuse-ld="$(shell "$(LLVM_CC)" -print-prog-name=ld.lld)" -Wl,--threads=1))
PROGRAM_RUNTIME_FLAGS ?= -DMINYAR_SYSTEM_HEAP=1
BOUNDED_FLAGS ?= -DMINYAR_BOUNDED_HEAP=1
RUNTIME_HEADERS = $(wildcard runtime/minyar_*.h) build/.toolchain.json
LIMITED ?= zsh scripts/with-limits.sh
SANITIZER_LIMITED ?= zsh scripts/with-sanitizer-limits.sh
# Native LSan is available on Linux; Windows/macOS retain ASan and UBSan.
NATIVE_SANITIZER_LEAKS = $(if $(filter Windows_NT,$(OS)),0,$(if $(filter Linux,$(shell uname -s)),1,0))
NATIVE_SANITIZER_ENV = ASAN_OPTIONS=detect_leaks=$(NATIVE_SANITIZER_LEAKS) UBSAN_OPTIONS=halt_on_error=1
MIN_COMPILER_EDGE_COVERAGE ?= 79
MIN_RUNTIME_LINE_COVERAGE ?= 72
MIN_RUNTIME_BRANCH_COVERAGE ?= 55
MIN_MUTATION_SCORE ?= 85

.NOTPARALLEL:

all: build/minyarc

build:
	mkdir -p build

doctor:
	@MINYAR_CLANG="$(LLVM_CC)" python3 tools/clang-driver.py doctor

clean:
	rm -rf build

BUILD_RULES := Makefile $(sort $(wildcard build-support/*.mk))
include $(filter-out Makefile,$(BUILD_RULES))
