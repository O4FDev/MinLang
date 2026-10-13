.PHONY: check-system-services check-system-services-sanitize check-system-process check-system-process-sanitize
.PHONY: check-system-process-boundary
build/tooling/tests/system-process-boundary: TOOL_NATIVE = tests/sha256-test-native.c tests/system-test-path-native.c
build/tooling/tests/system-process-boundary: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/system-process-boundary: tests/sha256-test-native.c tests/system-test-path-native.c
check-system-process-boundary: build/tooling/tests/system-process-boundary
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/system-process-boundary

ifeq ($(shell uname -s),Linux)
check-system-process check-system-process-sanitize: check-system-process-boundary
endif
build/tooling/tests/system-services-test: TOOL_NATIVE = tests/system-test-path-native.c tests/sha256-test-native.c
build/tooling/tests/system-services-test: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/system-services-test: tests/system-test-path-native.c tests/sha256-test-native.c
check-system-services: build/minyarc build/tooling/tests/system-services-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/system-services-test --language

check-system-services-sanitize: build/tooling/tests/system-services-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/system-services-test --mode sanitize

build/tooling/tests/system-process-test: TOOL_NATIVE = tests/system-test-path-native.c tests/sha256-test-native.c
build/tooling/tests/system-process-test: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/system-process-test: tests/system-test-path-native.c tests/sha256-test-native.c
check-system-process: build/minyarc build/tooling/tests/system-process-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/system-process-test --language

check-system-process-sanitize: build/tooling/tests/system-process-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/system-process-test --mode sanitize

check check-portable: check-system-services check-system-process
check-sanitize: check-system-services-sanitize check-system-process-sanitize
