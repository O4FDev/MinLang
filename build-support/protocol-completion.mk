.PHONY: check-protocol-completion check-protocol-completion-sanitize

check-protocol-completion: build/minyarc build/minyar-runtime.o build/tooling/tests/protocol-completion
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "./build/tooling/tests/protocol-completion"

check-protocol-completion-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/protocol-completion
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_COMPILER="./build/minyarc-sanitize" MINYAR_TEST_RUNTIME="./build/minyar-runtime-sanitize.o" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) "./build/tooling/tests/protocol-completion"

check check-portable: check-protocol-completion
check-sanitize: check-protocol-completion-sanitize
