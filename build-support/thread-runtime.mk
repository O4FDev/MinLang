.PHONY: check-thread-domain check-thread-runtime check-thread-runtime-sanitize check-thread-runtime-tsan
check-thread-domain:
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/thread-runtime.py --domain-only

check-thread-runtime:
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/thread-runtime.py

check-thread-runtime-sanitize:
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/thread-runtime.py --sanitize address,undefined

check-thread-runtime-tsan:
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/thread-runtime.py --sanitize thread

check check-portable: check-thread-domain
