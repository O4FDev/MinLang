.PHONY: check-doc-comments
check-doc-comments: build/minyarc build/minyar-runtime.o build/tooling/tests/doc-comments
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/doc-comments

build/tooling/tests/doc-comments.ll: tests/frontend-fixtures.min tests/documentation-probe.min
check check-portable: check-doc-comments
