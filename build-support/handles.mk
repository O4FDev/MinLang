.PHONY: check-handles check-handles-sanitize

check-handles: build/minyarc build/minyar-runtime.o build/tooling/tests/handles
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "./build/tooling/tests/handles"

check-handles-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/handles
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_COMPILER="./build/minyarc-sanitize" MINYAR_TEST_RUNTIME="./build/minyar-runtime-sanitize.o" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) "./build/tooling/tests/handles"

check check-portable: check-handles
check-sanitize: check-handles-sanitize
