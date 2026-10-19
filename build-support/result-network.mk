.PHONY: check-result-network check-result-network-sanitize

check-result-network: build/minyarc build/minyar-runtime.o build/tooling/tests/result-network
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "./build/tooling/tests/result-network"

check-result-network-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/result-network
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER="./build/minyarc-sanitize" MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) "./build/tooling/tests/result-network"

check check-portable: check-result-network
check-sanitize: check-result-network-sanitize
