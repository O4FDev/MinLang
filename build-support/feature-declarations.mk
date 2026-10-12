.PHONY: check-feature-declarations
check-feature-declarations: build/minyarc build/minyar-runtime.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/feature-declarations.py

check check-portable: check-feature-declarations
