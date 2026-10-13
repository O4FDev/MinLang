.PHONY: check-thread-ordinary check-thread-runtime-ir check-thread-domain check-thread-buffers check-thread-runtime check-thread-runtime-sanitize check-thread-runtime-tsan
build/tooling/tests/thread-runtime: TOOL_NATIVE = runtime/native/sha256.c
build/tooling/tests/thread-runtime: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/thread-runtime: runtime/native/sha256.c
build/tooling/tests/thread-runtime-ir: TOOL_NATIVE = runtime/native/sha256.c
build/tooling/tests/thread-runtime-ir: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/thread-runtime-ir: runtime/native/sha256.c
build/tooling/tests/thread-ordinary: TOOL_NATIVE = runtime/native/sha256.c
build/tooling/tests/thread-ordinary: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/thread-ordinary: runtime/native/sha256.c
check-thread-domain: build/tooling/tests/thread-runtime
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/thread-runtime --domain-only

check-thread-buffers: build/tooling/tests/thread-runtime
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/thread-runtime --buffers-only

check-thread-ordinary: build/tooling/tests/thread-ordinary
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/thread-ordinary --base-root "$(MINYAR_THREAD_BASE_ROOT)"

check-thread-runtime-ir: build/tooling/tests/thread-runtime-ir
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/thread-runtime-ir

check-thread-runtime: check-thread-runtime-ir build/tooling/tests/thread-runtime
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/thread-runtime

check-thread-runtime-sanitize: build/tooling/tests/thread-runtime
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/thread-runtime --sanitize address,undefined

check-thread-runtime-tsan: build/tooling/tests/thread-runtime-ir build/tooling/tests/thread-runtime
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/thread-runtime-ir --tsan
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/thread-runtime --sanitize thread

# The threaded fixtures have no native Windows qualification yet (WS7 owns that run).
ifeq ($(filter Windows_NT,$(OS))$(filter MSYS% MINGW% CYGWIN%,$(shell uname -s)),)
check check-portable: check-thread-runtime
endif
