.DEFAULT_GOAL := all
CC ?= cc
CPPFLAGS ?= -isystem vendor
CFLAGS ?= -std=c11 -O2 -Wall -Wextra -Werror
LLVM_CC ?= clang
LLVM_FLAGS ?= -O2 -Wno-override-module
LDLIBS ?= -lm
SANITIZER_FLAGS ?= -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module
COMPILER_RUNTIME_FLAGS ?= -DMINYAR_COMPILER_ARENA
COMPILER_LTO_FLAGS ?= -flto=thin
PROGRAM_RUNTIME_FLAGS ?= -DMINYAR_SYSTEM_HEAP=1
BOUNDED_FLAGS ?= -DMINYAR_BOUNDED_HEAP=1
RUNTIME_HEADERS = $(wildcard runtime/minyar_*.h) build/.toolchain.json
LIMITED ?= zsh scripts/with-limits.sh
SANITIZER_LIMITED ?= zsh scripts/with-sanitizer-limits.sh
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
