.PHONY: check-system-services check-system-services-sanitize check-system-process check-system-process-sanitize
.PHONY: check-system-process-boundary
check-system-process-boundary: build/tooling/tests/system-process-boundary
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/system-process-boundary

ifeq ($(shell uname -s),Linux)
check-system-process check-system-process-sanitize: check-system-process-boundary
endif
check-system-services: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/system-services.py --language

check-system-services-sanitize:
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/system-services.py --mode sanitize

check-system-process: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/system-process.py --language

check-system-process-sanitize:
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/system-process.py --mode sanitize

check check-portable: check-system-services check-system-process
check-sanitize: check-system-services-sanitize check-system-process-sanitize
