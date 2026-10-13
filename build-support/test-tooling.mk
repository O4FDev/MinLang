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

