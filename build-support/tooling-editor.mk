EDITOR_TOOL_NATIVE = tools/editor-host.c tools/clang-driver-host.c
build/tooling/tools/format-cli build/tooling/tests/format: build/tooling/%: build/tooling/%.ll build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS) $(EDITOR_TOOL_NATIVE)
	"$(LLVM_CC)" $(LLVM_FLAGS) $< build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS) $(EDITOR_TOOL_NATIVE) -pthread -lm -o $@

.PHONY: check-minyar-format
check-minyar-format: build/tooling/tools/format-cli build/tooling/tests/format build/minyarc build/minyar-runtime.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" ./build/tooling/tests/format "$(CURDIR)/build/tooling/tools/format-cli"
	python3 tests/editor-files.py "$(CURDIR)/build/tooling/tools/format-cli"
