.PHONY: check-last-use-sinks check-last-use-sinks-mutation

build/tooling/tests/last-use-sinks.ll: tests/frontend-fixtures.min
build/tooling/tests/last-use-sinks: TOOL_NATIVE = tools/clang-driver-host.c
build/tooling/tests/last-use-sinks: tools/clang-driver-host.c runtime/minyar_native.h

check-last-use-sinks: build/minyarc build/minyarc-sanitize build/minyar-runtime.o build/minyar-runtime-sanitize.o build/tooling/tests/last-use-sinks
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/last-use-sinks
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/last-use-sinks

check-last-use-sinks-mutation: build/minyarc build/ownership-runtime.o build/tooling/tests/last-use-sinks-mutation
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/last-use-sinks-mutation

check check-portable: check-last-use-sinks check-last-use-sinks-mutation
