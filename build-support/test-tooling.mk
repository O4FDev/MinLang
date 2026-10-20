MINYAR_TOOL_SOURCES = $(wildcard tools/*.min) $(wildcard library/*.min)
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

build/tooling/%.ll: %.min $(MINYAR_TOOL_SOURCES) build/minyarc-modules
	mkdir -p $(@D)
	$(LIMITED) ./build/minyarc-modules $< $@ --library library

# Imported test helpers must invalidate LLVM, not only relink an old harness.
MINYAR_NATIVE_EVIDENCE_SOURCES = tests/native-evidence.min tests/compiler-port-support.min \
	tests/sha256-support.min experiments/memory/study-support.min
build/tooling/tests/codegen.ll build/tooling/tests/native-evidence-harness.ll \
build/tooling/tests/regressions.ll: $(MINYAR_NATIVE_EVIDENCE_SOURCES)
build/tooling/tests/regressions.ll: tests/semantic-oracle.min

build/tooling/%: build/tooling/%.ll build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS)
	$(LLVM_CC) $(LLVM_FLAGS) $< $(TOOL_RUNTIME) $(MINYAR_TOOL_NATIVE_OBJECTS) $(TOOL_NATIVE) -pthread -lm $(TOOL_LIBS) -o $@

.PRECIOUS: build/tooling/%.ll

build/tooling/scripts/check-linux: build/tooling/tools/test-clang build/tooling/tools/clang-cache build/tooling/tools/rust-cache

build/tooling/tools/build-test-runtime: TOOL_RUNTIME = build/minyar-runtime.o
build/tooling/tools/build-test-runtime: TOOL_NATIVE =
build/tooling/tools/build-test-runtime: TOOL_LIBS =

build/tooling/tools/clang-driver: build/tooling/tools/clang-driver.ll build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS) tools/clang-driver-host.c runtime/minyar_native.h
	"$(LLVM_CC)" $(LLVM_FLAGS) $< build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS) tools/clang-driver-host.c -pthread -lm -o $@

build/tooling/tools/project-cli: build/tooling/tools/project-cli.ll build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS) tools/clang-driver-host.c tools/live-watch-host.c runtime/minyar_native.h
	"$(LLVM_CC)" $(LLVM_FLAGS) $< build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS) tools/clang-driver-host.c tools/live-watch-host.c -pthread -lm -o $@

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
	$(LLVM_CC) -O2 -D_GNU_SOURCE -DMINYAR_SYSTEM_HEAP=1 -iquote runtime -c $< -o $@


.PHONY: check-minyar-runner
check-minyar-runner: check-clang-cache build/tooling/tests/toolchain-cache build/tooling/tests/runner build/tooling/tests/linux-runner build/tooling/tests/testing-inputs build/tooling/tests/test-clang build/tooling/scripts/check-linux build/tooling/tools/test-clang build/tooling/tools/clang-cache
	$(LIMITED) ./build/tooling/tests/runner
	$(LIMITED) ./build/tooling/tests/linux-runner "$(CURDIR)/build/tooling/scripts/check-linux"
	$(LIMITED) ./build/tooling/tests/testing-inputs "$(CURDIR)/build/tooling/tests/testing-inputs"
	$(SANITIZER_LIMITED) ./build/tooling/tests/test-clang "$(CURDIR)/build/tooling/tools/test-clang" "$(CURDIR)/build/tooling/tools/clang-cache" "$$(command -v $(LLVM_CC))" "$$(command -v ld.lld)"
	$(SANITIZER_LIMITED) ./build/tooling/tests/toolchain-cache "$(CURDIR)" "$$(command -v $(LLVM_CC))" "$$(command -v clang++)" "$$(command -v ld.lld)"

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

build/tooling/tools/clang-cache: build/tooling/tools/clang-cache.ll build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS) runtime/native/sha256.c
	$(LLVM_CC) $(LLVM_FLAGS) $(shell pkg-config --cflags libcrypto) $< build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS) runtime/native/sha256.c -pthread -lm $(shell pkg-config --libs libcrypto) -o $@

build/tooling/tests/mutation-score build/tooling/tests/mutation-score-harness: build/tooling/%: build/tooling/%.ll build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS) runtime/native/sha256.c
	$(LLVM_CC) $(LLVM_FLAGS) $(shell pkg-config --cflags libcrypto) $< build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS) runtime/native/sha256.c -pthread -lm $(shell pkg-config --libs libcrypto) -o $@

build/tooling/tests/maps-baseline: build/tooling/tests/maps-baseline.ll build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS) runtime/native/sha256.c tests/maps-baseline-runtime.c
	$(LLVM_CC) $(LLVM_FLAGS) $(shell pkg-config --cflags libcrypto) $< build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS) runtime/native/sha256.c tests/maps-baseline-runtime.c -pthread -lm $(shell pkg-config --libs libcrypto) -o $@
