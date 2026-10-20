.PHONY: check-bytes-access check-bytes-access-ir check-bytes-access-sanitize

check-bytes-access: build/minyarc build/minyar-runtime.o build/tooling/tests/bytes-access tests/memory-contracts-runtime.c $(RUNTIME_HEADERS)
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/bytes-access

check-bytes-access-ir: build/minyarc build/tooling/tests/bytes-access
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/bytes-access --ir-only

check-bytes-access-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/bytes-access tests/memory-contracts-runtime.c $(RUNTIME_HEADERS)
	ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/bytes-access

check check-portable: check-bytes-access
check-sanitize: check-bytes-access-sanitize
