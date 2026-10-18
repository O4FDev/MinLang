.PHONY: check-nitpick-language check-nitpick-language-sanitize

check-nitpick-language: build/minyarc build/minyarc-modules build/minyar-runtime.o build/tooling/tests/nitpick-language
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/nitpick-language

check-nitpick-language-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/nitpick-language
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/nitpick-language

check check-portable: check-nitpick-language
check-sanitize: check-nitpick-language-sanitize
