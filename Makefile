.DEFAULT_GOAL := all
CC ?= cc
CPPFLAGS ?= -isystem vendor
CFLAGS ?= -std=c11 -O2 -Wall -Wextra -Werror
LLVM_CC ?= $(shell sh tools/toolchain.sh default-clang)
ifeq ($(shell uname -s),Darwin)
SDKROOT ?= $(shell sh tools/toolchain.sh sdkroot)
export SDKROOT
endif
ifeq ($(origin CC),default)
CC = $(LLVM_CC)
endif
LLVM_FLAGS ?= -O2 -Wno-override-module
LDLIBS ?= -lm
SANITIZER_FLAGS ?= -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module
COMPILER_RUNTIME_FLAGS ?= -DMINYAR_COMPILER_ARENA
COMPILER_LTO_CACHE_DIR ?= build/thinlto-cache
COMPILER_LTO_CACHE_POLICY ?= cache_size=10%:cache_size_bytes=1g:cache_size_files=10000:prune_after=168h:prune_interval=0s
TOOLCHAIN_QUOTE = '$(subst ','"'"',$(1))'
# Make exports this value even for clean. Keep ThinLTO enabled on discovery
# failure so the mandatory toolchain stamp rejects the bad linker before any
# build; an empty shell result would silently bypass that validation.
COMPILER_LTO_FLAGS ?= $(if $(filter Linux,$(shell uname -s)),$(shell LLVM_CC=$(call TOOLCHAIN_QUOTE,$(LLVM_CC)) LLVM_FLAGS=$(call TOOLCHAIN_QUOTE,$(LLVM_FLAGS)) COMPILER_LTO_CACHE_DIR=$(call TOOLCHAIN_QUOTE,$(COMPILER_LTO_CACHE_DIR)) COMPILER_LTO_CACHE_POLICY=$(call TOOLCHAIN_QUOTE,$(COMPILER_LTO_CACHE_POLICY)) sh tools/toolchain.sh compiler-lto-flags || printf '%s\n' '-flto=thin'),-flto=thin)
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
	@MINYAR_CLANG="$(LLVM_CC)" sh tools/toolchain.sh doctor

clean:
	rm -rf build

BUILD_RULES := Makefile $(sort $(wildcard build-support/*.mk))
include $(filter-out Makefile,$(BUILD_RULES))
