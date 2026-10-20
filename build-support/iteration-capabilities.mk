.PHONY: check-iteration-capabilities check-iteration-capabilities-sanitize
check-iteration-capabilities: build/minyarc build/minyar-runtime.o build/tooling/tests/iteration-capabilities
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/iteration-capabilities

check-iteration-capabilities-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/iteration-capabilities
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/iteration-capabilities

check check-portable: check-iteration-capabilities
check-sanitize: check-iteration-capabilities-sanitize
