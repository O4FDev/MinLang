.PHONY: check-result-methods check-result-methods-sanitize

check-result-methods: build/minyarc build/minyar-runtime.o build/tooling/tests/result-methods
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/result-methods

check-result-methods-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/result-methods
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/result-methods

check check-portable: check-result-methods
check-sanitize: check-result-methods-sanitize
