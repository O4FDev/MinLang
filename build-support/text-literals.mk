.PHONY: check-text-literals check-text-literals-sanitize

check-text-literals: build/minyarc build/minyar-runtime.o build/tooling/tests/text-literals
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/text-literals

check-text-literals-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/text-literals
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/text-literals

check check-portable: check-text-literals
check-sanitize: check-text-literals-sanitize
