.PHONY: check-choice check-choice-sanitize

check-choice: build/minyarc build/minyar-runtime.o build/tooling/tests/choice
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/choice

check-choice-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/choice
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/choice

check check-portable: check-choice
check-sanitize: check-choice-sanitize
