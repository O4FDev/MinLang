.PHONY: check-book check-book-cli

check-book: build/minyarc build/minyar-runtime.o build/tooling/tests/book
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/book

build/tooling/tests/book-cli: TOOL_NATIVE = tools/clang-driver-host.c
build/tooling/tests/book-cli: tools/clang-driver-host.c runtime/minyar_native.h
check-book-cli: build/tooling/tests/book-cli build/tooling/tools/project-cli build/tooling/tools/clang-driver build/minyar-module-build
	MINYAR_TEST_CLANG="$(LLVM_CC)" ./build/tooling/tests/book-cli

check check-portable: check-book check-book-cli
