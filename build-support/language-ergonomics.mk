.PHONY: check-language-ergonomics check-language-ergonomics-sanitize

check-language-ergonomics: build/minyarc build/minyar-runtime.o build/tooling/tests/language-ergonomics build/tooling/tests/backend-contract
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/language-ergonomics
	$(LIMITED) ./build/tooling/tests/backend-contract

check-language-ergonomics-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/language-ergonomics
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/language-ergonomics

check check-portable: check-language-ergonomics
check-sanitize: check-language-ergonomics-sanitize
