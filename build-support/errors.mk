.PHONY: check-errors-language check-errors-language-sanitize check-errors-language-bounded

check-errors-language: build/minyarc-errors build/errors-compiler-stage3.ll
	cmp build/errors-compiler-stage2.ll build/errors-compiler-stage3.ll
	MINYAR_ERRORS_COMPILER=./build/minyarc-errors MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/errors-language.py

check-errors-language-sanitize: build/minyarc-errors-sanitize
	ASAN_OPTIONS=detect_leaks=0 MINYAR_ERRORS_COMPILER=./build/minyarc-errors-sanitize MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/errors-language.py

check check-portable: check-errors-language
check-sanitize: check-errors-language-sanitize

check-errors-language-bounded: build/minyarc-errors
	@set -e; for budget in 1 32 1024; do \
	    echo "typed Result bounded 1MiB cleanup budget $$budget"; \
	    MINYAR_ERRORS_RUNTIME_FLAGS="-DMINYAR_BOUNDED_HEAP=1 -DMINYAR_BOUNDED_HEAP_BYTES=1048576 -DMINYAR_RC_POLL_BUDGET=$$budget" MINYAR_ERRORS_COMPILER=./build/minyarc-errors MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/errors-language.py; \
	done

check check-portable: check-errors-language-bounded

.PHONY: check-errors-launcher

check-errors-launcher: build/minyarc-errors-request build/minyarc-errors build/minyarc-callbacks build/minyar-runtime.o $(MANAGED_GRAPH_LAUNCHER_ARTIFACTS)
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/errors-launcher.py

check check-portable: check-errors-launcher

.PHONY: check-errors-review check-errors-review-sanitize check-errors-review-bounded check-errors-review-bounded-sanitize

check-errors-review: build/minyarc-errors build/errors-compiler-stage3.ll
	cmp build/errors-compiler-stage2.ll build/errors-compiler-stage3.ll
	MINYAR_ERRORS_COMPILER=./build/minyarc-errors MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/errors-review.py

check-errors-review-sanitize: build/minyarc-errors-sanitize
	ASAN_OPTIONS=detect_leaks=0 MINYAR_ERRORS_COMPILER=./build/minyarc-errors-sanitize MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/errors-review.py

check-errors-review-bounded: build/minyarc-errors
	@set -e; for budget in 1 32 1024; do \
	    echo "typed Result review bounded 1MiB cleanup budget $$budget"; \
	    MINYAR_ERRORS_RUNTIME_FLAGS="-DMINYAR_BOUNDED_HEAP=1 -DMINYAR_BOUNDED_HEAP_BYTES=1048576 -DMINYAR_RC_POLL_BUDGET=$$budget" MINYAR_ERRORS_COMPILER=./build/minyarc-errors MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/errors-review.py; \
	done

check-errors-review-bounded-sanitize: build/minyarc-errors-sanitize
	ASAN_OPTIONS=detect_leaks=0 MINYAR_ERRORS_RUNTIME_FLAGS="-DMINYAR_BOUNDED_HEAP=1 -DMINYAR_BOUNDED_HEAP_BYTES=1048576 -DMINYAR_RC_POLL_BUDGET=1" MINYAR_ERRORS_COMPILER=./build/minyarc-errors-sanitize MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/errors-review.py

check check-portable: check-errors-review check-errors-review-bounded
check-sanitize: check-errors-review-sanitize check-errors-review-bounded-sanitize
