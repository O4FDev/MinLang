MINYAR_TOOL_NATIVE = runtime/native/system.c runtime/native/files.c tools/testing-host.c
MINYAR_TOOL_NATIVE_OBJECTS = $(addprefix build/tooling/,$(MINYAR_TOOL_NATIVE:.c=.o))
TOOL_RUNTIME = build/minyar-runtime.o
TOOL_CRYPTO := $(shell pkg-config --cflags --libs libcrypto 2>/dev/null || echo -lcrypto)

# All tooling uses the same native services and compiler flags. Compile these
# once, tracking their actual headers and publishing only complete artifacts.
build/tooling/%.o: %.c build/.toolchain.json build-support/test-tooling.mk
	mkdir -p "$(@D)"
	@set -eu; temporary=$$(mktemp "$@.XXXXXXXX"); \
	dependencies=$$(mktemp "$(@:.o=.d).XXXXXXXX"); \
	trap 'rm -f "$$temporary" "$$dependencies"' 0; \
	trap 'exit 1' HUP INT TERM; \
	"$(LLVM_CC)" $(LLVM_FLAGS) -pthread -MMD -MP -MF "$$dependencies" -MQ "$@" -c "$<" -o "$$temporary"; \
	mv -f "$$dependencies" "$(@:.o=.d)"; \
	mv -f "$$temporary" "$@"

-include $(MINYAR_TOOL_NATIVE_OBJECTS:.o=.d)

# Each harness LLVM file depends on exactly the modules its compilation loads,
# recorded in build/tooling/<harness>.ll.d by the scanner (like clang -MMD -MP).
# A new scanner rebuilds every harness, so trees built before it gain a list.
MINYAR_DEPENDENCY_SCANNER = build-support/minyar-dependencies.awk

# `make -s` (the launcher's first-use builds) must print nothing, so the command is echoed only when make is not silent.
MAKE_SILENT = $(findstring s,$(firstword -$(MAKEFLAGS)))
build/tooling/%.ll: %.min build/minyarc-modules $(MINYAR_DEPENDENCY_SCANNER)
	@mkdir -p "$(@D)"
	@$(if $(MAKE_SILENT),:,echo '$(LIMITED) ./build/minyarc-modules $< $@ --library library')
	@set -eu; temporary=$$(mktemp "$@.XXXXXXXX"); \
	dependencies=$$(mktemp "$@.d.XXXXXXXX"); \
	trap 'rm -f "$$temporary" "$$dependencies"' 0; \
	trap 'exit 1' HUP INT TERM; \
	$(LIMITED) ./build/minyarc-modules "$<" "$$temporary" --library library; \
	LC_ALL=C awk -f "$(MINYAR_DEPENDENCY_SCANNER)" "$@" "$<" library > "$$dependencies"; \
	touch "$$temporary"; \
	mv -f "$$dependencies" "$@.d"; \
	mv -f "$$temporary" "$@"

# Included lists need no remaking; this also keeps them out of the link rule.
build/tooling/%.ll.d: ;
-include $(shell find build/tooling -name '*.ll.d' -type f 2>/dev/null)

# Imported test helpers must invalidate LLVM, not only relink an old harness.
MINYAR_NATIVE_EVIDENCE_SOURCES = tests/native-evidence.min tests/compiler-port-support.min \
	tests/sha256-support.min experiments/memory/study-support.min
build/tooling/tests/codegen.ll build/tooling/tests/native-evidence-harness.ll \
build/tooling/tests/regressions.ll: $(MINYAR_NATIVE_EVIDENCE_SOURCES)
build/tooling/tests/regressions.ll: tests/semantic-oracle.min

build/tooling/%: build/tooling/%.ll build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS)
	"$(LLVM_CC)" $(LLVM_FLAGS) $< $(TOOL_RUNTIME) $(MINYAR_TOOL_NATIVE_OBJECTS) $(TOOL_NATIVE) -pthread -lm $(TOOL_LIBS) -o $@

.PRECIOUS: build/tooling/%.ll

build/tooling/scripts/check-linux: build/tooling/tools/test-clang build/tooling/tools/clang-cache build/tooling/tools/rust-cache

build/tooling/tools/build-test-runtime: TOOL_RUNTIME = build/minyar-runtime.o
build/tooling/tools/build-test-runtime: TOOL_NATIVE =
build/tooling/tools/build-test-runtime: TOOL_LIBS =

build/tooling/tools/clang-driver: build/tooling/tools/clang-driver.ll build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS) tools/clang-driver-host.c runtime/minyar_native.h
	"$(LLVM_CC)" $(LLVM_FLAGS) $< build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS) tools/clang-driver-host.c -pthread -lm -o $@

build/tooling/tools/project-cli: build/tooling/tools/project-cli.ll build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS) tools/clang-driver-host.c tools/live-watch-host.c runtime/minyar_native.h
	"$(LLVM_CC)" $(LLVM_FLAGS) $< $(TOOL_RUNTIME) $(MINYAR_TOOL_NATIVE_OBJECTS) tools/clang-driver-host.c tools/live-watch-host.c -pthread -lm -o $@

# These explicit frontend rules are included before the shared objects are defined.
build/tooling/tools/install-cli build/tooling/tools/repl-cli: $(MINYAR_TOOL_NATIVE_OBJECTS)

.PHONY: check-project-cli
check-project-cli: build/tooling/tools/project-cli build/tooling/tests/project-cli build/tooling/tools/clang-driver build/minyar-module-build
	./build/tooling/tests/project-cli "$(CURDIR)/minyar"

check check-portable: check-project-cli

build/testing/cycle-runtime.c: runtime/minyar_runtime.c build/tooling/tools/build-test-runtime
	mkdir -p $(@D)
	./build/tooling/tools/build-test-runtime $< $@

build/testing/cycle-runtime.o: build/testing/cycle-runtime.c $(wildcard runtime/minyar_*.h)
	"$(LLVM_CC)" -O2 -D_GNU_SOURCE -DMINYAR_SYSTEM_HEAP=1 -iquote runtime -c $< -o $@


.PHONY: check-minyar-runner
check-minyar-runner: check-clang-cache build/tooling/tests/toolchain-cache build/tooling/tests/runner build/tooling/tests/linux-runner build/tooling/tests/testing-inputs build/tooling/tests/test-clang build/tooling/scripts/check-linux build/tooling/tools/test-clang build/tooling/tools/clang-cache
	$(LIMITED) ./build/tooling/tests/runner
	$(LIMITED) ./build/tooling/tests/linux-runner "$(CURDIR)/build/tooling/scripts/check-linux"
	$(LIMITED) ./build/tooling/tests/testing-inputs "$(CURDIR)/build/tooling/tests/testing-inputs"
	$(SANITIZER_LIMITED) ./build/tooling/tests/test-clang "$(CURDIR)/build/tooling/tools/test-clang" "$(CURDIR)/build/tooling/tools/clang-cache" "$$(command -v "$(LLVM_CC)")" "$$(command -v ld.lld)"
	$(SANITIZER_LIMITED) ./build/tooling/tests/toolchain-cache "$(CURDIR)" "$$(command -v "$(LLVM_CC)")" "$$(command -v clang++)" "$$(command -v ld.lld)"

check: check-minyar-runner

.PHONY: check-minyar-land
check-minyar-land: build/tooling/tests/land build/tooling/tools/land
	$(LIMITED) ./build/tooling/tests/land "$(CURDIR)/build/tooling/tools/land"

check: check-minyar-land

.PHONY: check-portable-process
check-portable-process: build/tooling/tests/portable-process
	$(LIMITED) ./build/tooling/tests/portable-process

check check-portable: check-portable-process

.PHONY: check-clang-cache
check-clang-cache: build/tooling/tests/clang-cache build/tooling/tools/clang-cache
	$(SANITIZER_LIMITED) ./build/tooling/tests/clang-cache "$(LLVM_CC)" "$(CURDIR)/build/tooling/tools/clang-cache"

check: check-clang-cache

build/tooling/tools/clang-cache: build/tooling/tools/clang-cache.ll build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS) runtime/native/sha256.c tools/clang-driver-host.c runtime/minyar_native.h
	"$(LLVM_CC)" $(LLVM_FLAGS) $(shell pkg-config --cflags libcrypto) $< build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS) runtime/native/sha256.c tools/clang-driver-host.c -pthread -lm $(shell pkg-config --libs libcrypto) -o $@

build/tooling/tests/mutation-score build/tooling/tests/mutation-score-harness: build/tooling/%: build/tooling/%.ll build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS) runtime/native/sha256.c
	"$(LLVM_CC)" $(LLVM_FLAGS) $(shell pkg-config --cflags libcrypto) $< build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS) runtime/native/sha256.c -pthread -lm $(shell pkg-config --libs libcrypto) -o $@

build/tooling/tests/maps-baseline: build/tooling/tests/maps-baseline.ll build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS) runtime/native/sha256.c tests/maps-baseline-runtime.c
	"$(LLVM_CC)" $(LLVM_FLAGS) $(shell pkg-config --cflags libcrypto) $< build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS) runtime/native/sha256.c tests/maps-baseline-runtime.c -pthread -lm $(shell pkg-config --libs libcrypto) -o $@

# Runs CHECKS (default check-portable) through the shared check runner: shared
# builds first, then each phony check as its own `make -j1` process.
CHECKS ?= check-portable
CHECK_JOBS ?= 8
.PHONY: check-in-parallel
check-in-parallel: build/tooling/tools/check-in-parallel $(TEST_CLANG_PREREQUISITES)
	./build/tooling/tools/check-in-parallel --jobs $(CHECK_JOBS) $(CHECKS)

# The fixture Clang for MINYAR_TEST_CLANG_CACHE=1 (TEST_CLANG in the Makefile). Its MINYAR_TOOLCHAIN_KEY covers the
# exact compiler, C++ compiler, linker and sanitizer runtimes and the cache tool, so no other toolchain shares an
# entry; entries unused for 7 days are pruned whenever the wrapper is written.
$(TEST_CLANG_WRAPPER): build/tooling/tools/clang-cache build/.toolchain.json build-support/test-tooling.mk
	@set -eu; real=$$(command -v "$(LLVM_CC)"); directory=$$(dirname "$$(readlink -f "$$real")"); cxx="$$directory/clang++"; \
	linker=$$("$$real" -print-prog-name=ld.lld); case $$linker in /*) ;; *) linker=$$(command -v "$$linker");; esac; \
	cache="$(TEST_CLANG_CACHE_DIR)"; tool="$(CURDIR)/build/tooling/tools/clang-cache"; mkdir -p "$$cache" "$(@D)"; \
	find "$$cache" -maxdepth 1 -type f -mtime +7 -delete; \
	"$$tool" --compiler-identity "$$real" "$$cxx" "$$linker" > "$@.identity"; \
	key=$$("$$tool" --toolchain-key "$$tool" "$$real" "$$cxx" "$$linker" "$@.identity"); \
	{ printf '#!/bin/sh\n# Test fixture Clang: %s through tools/clang-cache.min (MINYAR_TEST_CLANG_CACHE=1)\n' "$$real"; \
	  printf '# LLVM_CC=%s\n' "$(LLVM_CC)"; \
	  printf "export MINYAR_TOOLCHAIN_KEY=%s MINYAR_TOOLCHAIN_LINKER='%s'\n" "$$key" "$$linker"; \
	  printf "exec '%s' '%s' '%s' '%s' \"\$$@\"\n" "$$tool" "$$tool" "$$cache" "$$real"; } > "$@.tmp"; \
	chmod +x "$@.tmp"; mv -f "$@.tmp" "$@"; echo "fixture Clang cache: $@ -> $$cache"

.PHONY: check-in-parallel-tool
check-in-parallel-tool: build/tooling/tools/check-in-parallel build/tooling/tests/check-in-parallel
	$(LIMITED) ./build/tooling/tests/check-in-parallel "$(CURDIR)/build/tooling/tools/check-in-parallel"

check check-portable: check-in-parallel-tool

# The harness LLVM rule above lists exactly the modules a compilation loads.
.PHONY: check-harness-dependencies
check-harness-dependencies: build/tooling/tests/harness-dependencies build/tooling/tests/harness-dependency-fixture/app/main.ll build/minyarc-modules
	$(LIMITED) ./build/tooling/tests/harness-dependencies "$(CURDIR)" "$(CURDIR)/build/minyarc-modules"

check check-portable: check-harness-dependencies
