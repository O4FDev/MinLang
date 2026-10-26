# Native differentials in check-portable run the smallest, default and largest poll budgets (K1, K32, K1024; the empty
# Map check has no K1024, so K1 and K32); the matching *-budgets targets in check-ownership run K2 and K7, so
# `make check` still covers every budget. Sanitizer variants keep the full matrix.
PERFCS_GATE_BUDGETS = 1,32,1024
PERFCS_OTHER_BUDGETS = 2,7

.PHONY: check-owner-queue-batching check-owner-queue-batching-budgets check-owner-queue-batching-sanitize
check-owner-queue-batching: tests/owner-queue-batching.py tests/owner-queue-batching.c $(RUNTIME_HEADERS) | build
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) python3 "tests/owner-queue-batching.py" --modes native --budgets $(PERFCS_GATE_BUDGETS)

check-owner-queue-batching-budgets: tests/owner-queue-batching.py tests/owner-queue-batching.c $(RUNTIME_HEADERS) | build
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) python3 "tests/owner-queue-batching.py" --modes native --budgets $(PERFCS_OTHER_BUDGETS)

check-owner-queue-batching-sanitize: tests/owner-queue-batching.py tests/owner-queue-batching.c $(RUNTIME_HEADERS) | build
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(SANITIZER_LIMITED) python3 "tests/owner-queue-batching.py" --modes sanitize

.PHONY: check-temporary-owner-cache check-temporary-owner-cache-budgets check-temporary-owner-cache-sanitize
check-temporary-owner-cache: tests/temporary-owner-cache.py tests/temporary-owner-cache.c $(RUNTIME_HEADERS) | build
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) python3 "tests/temporary-owner-cache.py" --modes native --budgets $(PERFCS_GATE_BUDGETS)

check-temporary-owner-cache-budgets: tests/temporary-owner-cache.py tests/temporary-owner-cache.c $(RUNTIME_HEADERS) | build
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) python3 "tests/temporary-owner-cache.py" --modes native --budgets $(PERFCS_OTHER_BUDGETS)

check-temporary-owner-cache-sanitize: tests/temporary-owner-cache.py tests/temporary-owner-cache.c $(RUNTIME_HEADERS) | build
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(SANITIZER_LIMITED) python3 "tests/temporary-owner-cache.py" --modes sanitize

.PHONY: check-frame-initialization check-frame-initialization-budgets check-frame-initialization-sanitize
check-frame-initialization: tests/frame-initialization.py tests/frame-initialization.c $(RUNTIME_HEADERS) | build
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) python3 "tests/frame-initialization.py" --modes native --budgets $(PERFCS_GATE_BUDGETS)

check-frame-initialization-budgets: tests/frame-initialization.py tests/frame-initialization.c $(RUNTIME_HEADERS) | build
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) python3 "tests/frame-initialization.py" --modes native --budgets $(PERFCS_OTHER_BUDGETS)

check-frame-initialization-sanitize: tests/frame-initialization.py tests/frame-initialization.c $(RUNTIME_HEADERS) | build
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(SANITIZER_LIMITED) python3 "tests/frame-initialization.py" --modes sanitize --activated-matrix full

.PHONY: check-empty-map-traversal check-empty-map-traversal-budgets check-empty-map-traversal-sanitize
check-empty-map-traversal: tests/empty-map-traversal.py tests/empty-map-traversal.c $(RUNTIME_HEADERS) | build
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) python3 "tests/empty-map-traversal.py" --modes native --budgets 1,32

# Eager and arena profiles take no budget and the mutants run at K1: both are already covered by check-empty-map-traversal.
check-empty-map-traversal-budgets: tests/empty-map-traversal.py tests/empty-map-traversal.c $(RUNTIME_HEADERS) | build
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) python3 "tests/empty-map-traversal.py" --modes native --budgets $(PERFCS_OTHER_BUDGETS) --profiles system,fixed,lazy --skip-mutants

check-empty-map-traversal-sanitize: tests/empty-map-traversal.py tests/empty-map-traversal.c $(RUNTIME_HEADERS) | build
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(SANITIZER_LIMITED) python3 "tests/empty-map-traversal.py" --modes sanitize

check check-portable: check-owner-queue-batching check-temporary-owner-cache check-frame-initialization check-empty-map-traversal
check check-ownership: check-owner-queue-batching-budgets check-temporary-owner-cache-budgets check-frame-initialization-budgets check-empty-map-traversal-budgets
check-ownership check-sanitize: check-owner-queue-batching-sanitize check-temporary-owner-cache-sanitize check-frame-initialization-sanitize check-empty-map-traversal-sanitize
