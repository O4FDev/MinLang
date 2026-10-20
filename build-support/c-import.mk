.PHONY: check-c-import check-c-import-smoke
check-c-import: build/minyarc build/minyar-runtime.o build/tooling/tools/clang-driver
	MINYAR_TEST_CLANG="$(LLVM_CC)" python3 tests/c-import.py

check-c-import-smoke: build/minyarc build/minyar-runtime.o build/tooling/tools/clang-driver
	MINYAR_TEST_CLANG="$(LLVM_CC)" python3 tests/c-import.py --case constants --case scalars --case records --case rejections

check check-portable: check-c-import
