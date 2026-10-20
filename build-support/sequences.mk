.PHONY: check-sequences check-sequences-sanitize
build/tooling/tests/sequences.ll: tests/frontend-fixtures.min

check-sequences: build/minyarc build/minyar-runtime.o build/tooling/tests/sequences
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/sequences

check-sequences-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/sequences
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/sequences

check check-portable: check-sequences
check-sanitize: check-sequences-sanitize
