.PHONY: check-result-library check-result-library-sanitize

check-result-library: build/minyarc build/minyar-runtime.o build/tooling/tests/result-library
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/result-library

check-result-library-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/result-library
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/result-library

check check-portable: check-result-library
check-sanitize: check-result-library-sanitize
