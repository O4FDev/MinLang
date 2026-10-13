MINYAR_TOOL_SOURCES = $(wildcard tools/*.min) library/system.min library/files.min
MINYAR_TOOL_NATIVE = runtime/native/system.c runtime/native/files.c

build/tooling/%.ll: %.min $(MINYAR_TOOL_SOURCES) build/minyarc-modules
	mkdir -p $(@D)
	$(LIMITED) ./build/minyarc-modules $< $@ --library library

build/tooling/%: build/tooling/%.ll build/minyar-runtime.o $(MINYAR_TOOL_NATIVE)
	$(LLVM_CC) $(LLVM_FLAGS) $< build/minyar-runtime.o $(MINYAR_TOOL_NATIVE) -pthread -lm -o $@

.PRECIOUS: build/tooling/%.ll

build/testing/cycle-runtime.c: runtime/minyar_runtime.c build/tooling/tools/build-test-runtime
	mkdir -p $(@D)
	./build/tooling/tools/build-test-runtime $< $@

build/testing/cycle-runtime.o: build/testing/cycle-runtime.c $(wildcard runtime/minyar_*.h)
	$(LLVM_CC) -O2 -D_GNU_SOURCE -DMINYAR_SYSTEM_HEAP=1 -iquote runtime -c $< -o $@


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
