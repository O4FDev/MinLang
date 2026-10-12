.PHONY: check-thread-ordinary check-thread-runtime-ir check-thread-domain check-thread-buffers check-thread-runtime check-thread-runtime-sanitize check-thread-runtime-tsan
check-thread-domain:
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/thread-runtime.py --domain-only

check-thread-buffers:
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/thread-runtime.py --buffers-only

check-thread-ordinary:
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/thread-ordinary.py --base-root "$(MINYAR_THREAD_BASE_ROOT)"

check-thread-runtime-ir:
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/thread-runtime-ir.py

check-thread-runtime: check-thread-runtime-ir
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/thread-runtime.py

check-thread-runtime-sanitize:
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/thread-runtime.py --sanitize address,undefined

check-thread-runtime-tsan:
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/thread-runtime-ir.py --tsan
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/thread-runtime.py --sanitize thread

# The threaded fixtures have no native Windows qualification yet (WS7 owns that run).
ifeq ($(filter Windows_NT,$(OS))$(filter MSYS% MINGW% CYGWIN%,$(shell uname -s)),)
check check-portable: check-thread-runtime
endif
