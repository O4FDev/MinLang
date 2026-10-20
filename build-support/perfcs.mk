.PHONY: check-owner-queue-batching check-owner-queue-batching-sanitize
check-owner-queue-batching: tests/owner-queue-batching.py tests/owner-queue-batching.c $(RUNTIME_HEADERS) | build
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 "tests/owner-queue-batching.py" --modes native

check-owner-queue-batching-sanitize: tests/owner-queue-batching.py tests/owner-queue-batching.c $(RUNTIME_HEADERS) | build
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 "tests/owner-queue-batching.py" --modes sanitize

.PHONY: check-temporary-owner-cache check-temporary-owner-cache-sanitize
check-temporary-owner-cache: tests/temporary-owner-cache.py tests/temporary-owner-cache.c $(RUNTIME_HEADERS) | build
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 "tests/temporary-owner-cache.py" --modes native

check-temporary-owner-cache-sanitize: tests/temporary-owner-cache.py tests/temporary-owner-cache.c $(RUNTIME_HEADERS) | build
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 "tests/temporary-owner-cache.py" --modes sanitize

check check-portable: check-owner-queue-batching check-temporary-owner-cache
check-ownership check-sanitize: check-owner-queue-batching-sanitize check-temporary-owner-cache-sanitize
