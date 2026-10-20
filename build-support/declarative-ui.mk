.PHONY: check-ui-model

build/tooling/tests/ui.ll: tests/frontend-fixtures.min library/ui.min

check-ui-model: build/minyarc build/minyar-runtime.o build/tooling/tests/ui
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/ui

check check-portable: check-ui-model
