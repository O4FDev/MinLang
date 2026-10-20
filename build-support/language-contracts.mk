.PHONY: check-language-contracts check-language-contracts-sanitize

build/tooling/tests/language-contracts.ll: tests/frontend-fixtures.min examples/gallery/contracts.min tests/memory-contracts-runtime.c tools/test-runtime.min

check-language-contracts: build/minyarc build/minyar-runtime.o build/tooling/tests/language-contracts
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/language-contracts

check-language-contracts-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/language-contracts
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/language-contracts

check check-portable: check-language-contracts
check-sanitize: check-language-contracts-sanitize

ifneq ($(OS),Windows_NT)
check-language-contracts check-language-contracts-sanitize: build/minyar-module-build
endif
