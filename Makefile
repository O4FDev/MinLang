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
# TEST_CLANG is the Clang test harnesses compile their own fixtures with (MINYAR_TEST_CLANG in their recipes); it is
# never part of build/.toolchain.json. With MINYAR_TEST_CLANG_CACHE=1 it is build/test-clang/clang, a wrapper that
# caches compiles of LLVM_CC through tools/clang-cache.min under TEST_CLANG_CACHE_DIR, used once `make check-in-parallel`
# (or `make build/test-clang/clang`) has written it for this LLVM_CC. Harnesses that hand a Clang to the launcher or a
# sub-make, or record its identity, take the real one from MINYAR_TEST_REAL_CLANG (tools/testing.min realClang).
TEST_CLANG_WRAPPER = build/test-clang/clang
TEST_CLANG_CACHE_DIR ?= $(HOME)/.cache/minyar/test-clang
ifeq ($(MINYAR_TEST_CLANG_CACHE),1)
TEST_CLANG_WRAPPED := $(shell sed -n 's/^# LLVM_CC=//p' $(TEST_CLANG_WRAPPER) 2>/dev/null)
TEST_CLANG_SAME = $(and $(findstring x$(LLVM_CC)x,x$(TEST_CLANG_WRAPPED)x),$(findstring x$(TEST_CLANG_WRAPPED)x,x$(LLVM_CC)x))
TEST_CLANG ?= $(if $(TEST_CLANG_SAME),$(CURDIR)/$(TEST_CLANG_WRAPPER),$(LLVM_CC))
TEST_CLANG_PREREQUISITES = $(TEST_CLANG_WRAPPER)
export MINYAR_TEST_REAL_CLANG := $(LLVM_CC)
else
TEST_CLANG ?= $(LLVM_CC)
TEST_CLANG_PREREQUISITES =
endif
# Labs that run a real redis-server print a SKIP line instead of failing on hosts without one
# (scripts/needs-command.sh; MINYAR_REQUIRE_LAB_TOOLS=1 makes a missing server a failure).
NEEDS_REDIS = sh scripts/needs-command.sh redis-server $@ "these labs run a real Redis (Debian/Ubuntu: apt-get install redis-server)"
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
