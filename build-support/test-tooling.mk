MINYAR_TOOL_SOURCES = $(wildcard tools/*.min) library/system.min library/files.min
MINYAR_TOOL_NATIVE = runtime/native/system.c runtime/native/files.c
TOOL_RUNTIME = build/minyar-runtime.o

build/tooling/%.ll: %.min $(MINYAR_TOOL_SOURCES) build/minyarc-modules
	mkdir -p $(@D)
	$(LIMITED) ./build/minyarc-modules $< $@ --library library

build/tooling/%: build/tooling/%.ll build/minyar-runtime.o $(MINYAR_TOOL_NATIVE)
	$(LLVM_CC) $(LLVM_FLAGS) $< $(TOOL_RUNTIME) $(MINYAR_TOOL_NATIVE) $(TOOL_NATIVE) -pthread -lm $(TOOL_LIBS) -o $@

.PRECIOUS: build/tooling/%.ll

build/tooling/scripts/check-linux: build/tooling/tools/test-clang build/tooling/tools/clang-cache build/tooling/tools/rust-cache

build/testing/cycle-runtime.c: runtime/minyar_runtime.c build/tooling/tools/build-test-runtime
	mkdir -p $(@D)
	./build/tooling/tools/build-test-runtime $< $@

build/testing/cycle-runtime.o: build/testing/cycle-runtime.c $(wildcard runtime/minyar_*.h)
	$(LLVM_CC) -O2 -D_GNU_SOURCE -DMINYAR_SYSTEM_HEAP=1 -iquote runtime -c $< -o $@


.PHONY: check-minyar-runner
check-minyar-runner: build/tooling/tests/toolchain-cache build/tooling/tests/runner build/tooling/tests/linux-runner build/tooling/tests/testing-inputs build/tooling/tests/test-clang build/tooling/tests/clang-cache build/tooling/scripts/check-linux build/tooling/tools/test-clang build/tooling/tools/clang-cache
	$(LIMITED) ./build/tooling/tests/runner
	$(LIMITED) ./build/tooling/tests/linux-runner "$(CURDIR)/build/tooling/scripts/check-linux"
	$(LIMITED) ./build/tooling/tests/testing-inputs "$(CURDIR)/build/tooling/tests/testing-inputs"
	$(SANITIZER_LIMITED) ./build/tooling/tests/clang-cache "$(LLVM_CC)" "$(CURDIR)/build/tooling/tools/clang-cache"
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

build/tooling/tools/clang-cache: build/tooling/tools/clang-cache.ll build/minyar-runtime.o $(MINYAR_TOOL_NATIVE) runtime/native/sha256.c
	$(LLVM_CC) $(LLVM_FLAGS) $(shell pkg-config --cflags libcrypto) $< build/minyar-runtime.o $(MINYAR_TOOL_NATIVE) runtime/native/sha256.c -pthread -lm $(shell pkg-config --libs libcrypto) -o $@

build/tooling/tests/mutation-score build/tooling/tests/mutation-score-harness: build/tooling/%: build/tooling/%.ll build/minyar-runtime.o $(MINYAR_TOOL_NATIVE) runtime/native/sha256.c
	$(LLVM_CC) $(LLVM_FLAGS) $(shell pkg-config --cflags libcrypto) $< build/minyar-runtime.o $(MINYAR_TOOL_NATIVE) runtime/native/sha256.c -pthread -lm $(shell pkg-config --libs libcrypto) -o $@

build/tooling/tests/maps-baseline: build/tooling/tests/maps-baseline.ll build/minyar-runtime.o $(MINYAR_TOOL_NATIVE) runtime/native/sha256.c tests/maps-baseline-runtime.c
	$(LLVM_CC) $(LLVM_FLAGS) $(shell pkg-config --cflags libcrypto) $< build/minyar-runtime.o $(MINYAR_TOOL_NATIVE) runtime/native/sha256.c tests/maps-baseline-runtime.c -pthread -lm $(shell pkg-config --libs libcrypto) -o $@
