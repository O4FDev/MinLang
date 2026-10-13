.PHONY: check-feature-declarations
check-feature-declarations: build/minyarc build/minyar-runtime.o build/tooling/tests/feature-declarations
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/feature-declarations

check check-portable: check-feature-declarations
