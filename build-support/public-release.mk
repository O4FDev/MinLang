.PHONY: check-public-release check-public-release-sanitize

check-public-release: tests/public-release-runtime.c tests/public-release.py tools/test-runtime.min runtime/minyar_runtime.c $(RUNTIME_HEADERS)
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/public-release.py --mode native

check-public-release-sanitize: tests/public-release-runtime.c tests/public-release.py tools/test-runtime.min runtime/minyar_runtime.c $(RUNTIME_HEADERS)
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/public-release.py --mode sanitize

check check-portable: check-public-release
check-sanitize check-ownership: check-public-release-sanitize
