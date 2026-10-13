.PHONY: check-thread-config
build/tooling/tests/thread-config: TOOL_NATIVE = tests/sha256-test-native.c runtime/native/sha256.c
build/tooling/tests/thread-config: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/thread-config: tests/sha256-test-native.c runtime/native/sha256.c
check-thread-config: build/tooling/tests/thread-config runtime/minyar_thread_config.h runtime/minyar_runtime.c $(RUNTIME_HEADERS)
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/thread-config

check check-portable: check-thread-config
