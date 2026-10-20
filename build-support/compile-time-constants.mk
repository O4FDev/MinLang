.PHONY: check-compile-time-constants check-compile-time-constants-sanitize

check-compile-time-constants: build/minyarc build/minyar-runtime.o build/tooling/tests/compile-time-constants
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/compile-time-constants

check-compile-time-constants-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/compile-time-constants
	MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS="$(SANITIZER_FLAGS)" $(SANITIZER_LIMITED) ./build/tooling/tests/compile-time-constants

check check-portable: check-compile-time-constants
check-sanitize: check-compile-time-constants-sanitize

ifneq ($(OS),Windows_NT)
check-compile-time-constants check-compile-time-constants-sanitize: build/minyar-module-build
endif
