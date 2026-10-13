MINYAR_TOOL_SOURCES = tools/testing.min library/system.min library/files.min
MINYAR_TOOL_NATIVE = runtime/native/system.c runtime/native/files.c

build/tooling/%.ll: %.min $(MINYAR_TOOL_SOURCES) build/minyarc-modules
	mkdir -p $(@D)
	$(LIMITED) ./build/minyarc-modules $< $@ --library library

build/tooling/%: build/tooling/%.ll build/minyar-runtime.o $(MINYAR_TOOL_NATIVE)
	$(LLVM_CC) $(LLVM_FLAGS) $< build/minyar-runtime.o $(MINYAR_TOOL_NATIVE) -pthread -lm -o $@

.PRECIOUS: build/tooling/%.ll
