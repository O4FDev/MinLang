.PHONY: check-result-context check-result-context-sanitize

check-result-context: build/minyarc build/minyar-runtime.o build/tooling/tests/result-context
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/result-context

check-result-context-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/result-context
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/result-context

check check-portable: check-result-context
check-sanitize: check-result-context-sanitize
