.PHONY: check-llvm-runtime-contracts check-llvm-runtime-contracts-sanitize

check-llvm-runtime-contracts: build/minyarc build/minyar-runtime.o build/tooling/tests/llvm-runtime-contracts tests/memory-contracts-runtime.c $(RUNTIME_HEADERS)
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/llvm-runtime-contracts

check-llvm-runtime-contracts-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/llvm-runtime-contracts tests/memory-contracts-runtime.c $(RUNTIME_HEADERS)
	ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/llvm-runtime-contracts

check check-portable: check-llvm-runtime-contracts
check-sanitize: check-llvm-runtime-contracts-sanitize
