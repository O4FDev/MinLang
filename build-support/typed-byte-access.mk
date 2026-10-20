.PHONY: check-typed-byte-access check-typed-byte-access-ir check-typed-byte-access-sanitize
check-typed-byte-access: build/minyarc build/minyar-runtime.o build/tooling/tests/typed-byte-access tests/memory-contracts-runtime.c $(RUNTIME_HEADERS)
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/typed-byte-access
check-typed-byte-access-ir: build/minyarc build/tooling/tests/typed-byte-access
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/typed-byte-access --ir-only
check-typed-byte-access-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/typed-byte-access tests/memory-contracts-runtime.c $(RUNTIME_HEADERS)
	ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/typed-byte-access
check check-portable: check-typed-byte-access
check-sanitize: check-typed-byte-access-sanitize
