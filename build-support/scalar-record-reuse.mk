.PHONY: check-scalar-record-reuse check-scalar-record-reuse-sanitize

check-scalar-record-reuse: tests/scalar-record-reuse.c tests/scalar-record-reuse.py runtime/minyar_runtime.c $(RUNTIME_HEADERS)
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/scalar-record-reuse.py --mode native

check-scalar-record-reuse-sanitize: tests/scalar-record-reuse.c tests/scalar-record-reuse.py runtime/minyar_runtime.c $(RUNTIME_HEADERS)
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/scalar-record-reuse.py --mode sanitize

check check-portable: check-scalar-record-reuse
check-sanitize check-ownership: check-scalar-record-reuse-sanitize

