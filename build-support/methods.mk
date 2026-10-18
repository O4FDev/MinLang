.PHONY: check-methods check-methods-sanitize
check-methods: build/minyarc build/minyar-runtime.o build/tooling/tests/methods
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/methods

check-methods-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/methods
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/methods

check check-portable: check-methods
check-sanitize: check-methods-sanitize
