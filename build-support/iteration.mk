.PHONY: check-iteration check-iteration-sanitize
build/tooling/tests/iteration.ll: tests/frontend-fixtures.min

check-iteration: build/minyarc build/minyar-runtime.o build/tooling/tests/iteration
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/iteration

check-iteration-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/iteration
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/iteration

check check-portable: check-iteration
check-sanitize: check-iteration-sanitize
