# This frontend/runtime is selected only by parsed cycle/callback features.
# The historical compiler control is hash-checked, never a mutable baseline.
.PHONY: check-feature-dispatch check-managed-graphs check-managed-graphs-sanitize check-managed-graphs-profiles check-managed-graphs-launcher check-callbacks check-callbacks-sanitize check-callback-domains check-isolated-workers check-isolated-workers-sanitize

check-feature-dispatch: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/feature-dispatch.py

check-managed-graphs: build/minyarc build/minyarc-callbacks build/minyarc-baseline
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/managed-graphs.py

check-callbacks: build/minyarc-callbacks build/closure-compiler-stage3.ll
	cmp build/closure-compiler-stage2.ll build/closure-compiler-stage3.ll
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/callbacks.py

check-managed-graphs-profiles:
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/managed-graphs-profiles.py --quick

check-callback-domains:
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/callback-domains.py

check-managed-graphs-launcher: build/minyarc build/minyarc-callbacks build/minyarc-modules build/minyar-module-build
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/managed-graphs-launcher.py

check-isolated-workers: build/minyarc build/minyar-default-runtime.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/isolated-workers.py

build/minyar-default-runtime-sanitize.o: runtime/minyar_default_runtime.c runtime/minyar_runtime.c $(RUNTIME_HEADERS) $(BUILD_RULES) | build
	$(SANITIZER_LIMITED) "$(LLVM_CC)" $(SANITIZER_FLAGS) -c $< -o $@

check-managed-graphs-sanitize: build/minyarc-sanitize build/minyarc-callbacks-sanitize build/minyarc-baseline
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/managed-graphs.py

check-callbacks-sanitize: build/minyarc-callbacks-sanitize
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/callbacks.py

check-isolated-workers-sanitize: build/minyarc-sanitize build/minyar-default-runtime-sanitize.o
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_WORKER_RUNTIME=./build/minyar-default-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/isolated-workers.py

# The pre-existing type-reachability oracles now require parsed feature
# dispatch for cyclic cases; all acyclic and invalid-type cases are retained.
check-recursive-data check-bounded check-ownership check-adversarial check-peer-regressions check-peer-optimizations check-peer-sanitize check-peer-ownership: build/minyarc-callbacks
check-recursive-data check-bounded check-peer-sanitize check-peer-ownership check-sanitize: build/minyarc-callbacks-sanitize

check-portable check: check-feature-dispatch check-managed-graphs check-managed-graphs-launcher check-callbacks check-callback-domains check-isolated-workers
check-sanitize: check-managed-graphs-sanitize check-callbacks-sanitize check-managed-graphs-profiles check-isolated-workers-sanitize
