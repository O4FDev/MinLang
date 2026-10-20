.PHONY: check-last-use-sinks check-last-use-sinks-mutation

build/tooling/tests/last-use-sinks.ll: tests/frontend-fixtures.min

check-last-use-sinks: build/minyarc build/minyarc-sanitize build/tooling/tests/last-use-sinks
	$(LIMITED) ./build/tooling/tests/last-use-sinks
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/last-use-sinks

check-last-use-sinks-mutation: build/minyarc build/ownership-runtime.o build/tooling/tests/last-use-sinks-mutation
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/last-use-sinks-mutation

check check-portable: check-last-use-sinks check-last-use-sinks-mutation
