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

.PHONY: check-frame-initialization check-frame-initialization-sanitize
check-frame-initialization: tests/frame-initialization.py tests/frame-initialization.c $(RUNTIME_HEADERS) | build
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 "tests/frame-initialization.py" --modes native

check-frame-initialization-sanitize: tests/frame-initialization.py tests/frame-initialization.c $(RUNTIME_HEADERS) | build
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 "tests/frame-initialization.py" --modes sanitize --activated-matrix full

.PHONY: check-empty-map-traversal check-empty-map-traversal-sanitize
check-empty-map-traversal: tests/empty-map-traversal.py tests/empty-map-traversal.c $(RUNTIME_HEADERS) | build
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 "tests/empty-map-traversal.py" --modes native

check-empty-map-traversal-sanitize: tests/empty-map-traversal.py tests/empty-map-traversal.c $(RUNTIME_HEADERS) | build
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 "tests/empty-map-traversal.py" --modes sanitize

check check-portable: check-owner-queue-batching check-temporary-owner-cache check-frame-initialization check-empty-map-traversal
check-ownership check-sanitize: check-owner-queue-batching-sanitize check-temporary-owner-cache-sanitize check-frame-initialization-sanitize check-empty-map-traversal-sanitize
