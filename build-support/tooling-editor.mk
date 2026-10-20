EDITOR_TOOL_NATIVE = tools/editor-host.c tools/clang-driver-host.c
build/tooling/tools/format-cli build/tooling/tests/format build/tooling/tools/lsp-cli build/tooling/tests/editor-index build/tooling/tests/editor-verification: build/tooling/%: build/tooling/%.ll build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS) $(EDITOR_TOOL_NATIVE)
	"$(LLVM_CC)" $(LLVM_FLAGS) $< build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS) $(EDITOR_TOOL_NATIVE) -pthread -lm -o $@

.PHONY: check-minyar-format
check-minyar-format: build/tooling/tools/format-cli build/tooling/tests/format build/minyarc build/minyar-runtime.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" ./build/tooling/tests/format "$(CURDIR)/build/tooling/tools/format-cli"
	python3 tests/editor-files.py "$(CURDIR)/build/tooling/tools/format-cli"

.PHONY: check-minyar-lsp check-minyar-tooling-ownership check-minyar-tooling-sanitize
check-minyar-lsp: build/tooling/tools/lsp-cli build/tooling/tests/editor-index build/minyarc
	./build/tooling/tests/editor-index
	MINYAR_TEST_CLANG="$(LLVM_CC)" python3 tests/editor-lsp.py "$(CURDIR)/build/tooling/tools/lsp-cli" "$(CURDIR)/build/minyarc"

check-minyar-tooling-ownership: build/tooling/tests/editor-verification build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" ./build/tooling/tests/editor-verification

check-minyar-tooling-sanitize: build/tooling/tests/editor-verification build/minyarc
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" ./build/tooling/tests/editor-verification --sanitize

.PHONY: check-minyar-editor
check-minyar-editor:
	npm --prefix editors/vscode test
