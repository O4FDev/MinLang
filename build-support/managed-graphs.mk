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

# Incremental fallback uses the POSIX-only module build driver; the native
# Windows launcher still exercises debug/release profiles and callbacks.
MANAGED_GRAPH_LAUNCHER_ARTIFACTS = build/minyarc build/minyarc-callbacks
ifeq ($(filter Windows_NT,$(OS))$(filter MSYS% MINGW% CYGWIN%,$(shell uname -s)),)
MANAGED_GRAPH_LAUNCHER_ARTIFACTS += build/minyarc-modules build/minyar-module-build
endif

check-managed-graphs-launcher: $(MANAGED_GRAPH_LAUNCHER_ARTIFACTS)
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

# Explicit sanitizer installations may keep their Windows runtime DLLs
# beside the selected compiler rather than the ordinary compiler's directory.
CYCLE_SANITIZER_CLANG = $(or $(MINYAR_SANITIZER_CLANG),$(LLVM_CC))
CYCLE_SANITIZER_PATH = $(if $(MINYAR_SANITIZER_CLANG),$(dir $(MINYAR_SANITIZER_CLANG)):$(PATH),$(PATH))

.PHONY: check-cycle-progress check-cycle-progress-sanitize
check-cycle-progress:
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/cycle-progress.py --evidence build/cycle-progress-native
check-cycle-progress-sanitize:
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) python3 tests/cycle-progress.py --sanitize --evidence build/cycle-progress-sanitize
check check-portable: check-cycle-progress
check-sanitize: check-cycle-progress-sanitize

.PHONY: check-cycle-witness check-cycle-witness-sanitize
check-cycle-witness:
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/cycle-witness.py --evidence build/cycle-witness-native
check-cycle-witness-sanitize:
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) python3 tests/cycle-witness.py --sanitize --evidence build/cycle-witness-sanitize
check check-portable: check-cycle-witness check-cycle-witness-sanitize
check-sanitize: check-cycle-witness-sanitize
check-managed-graphs-profiles: check-cycle-witness check-cycle-witness-sanitize

.PHONY: check-cycle-additive check-cycle-additive-sanitize
check-cycle-additive:
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/cycle-additive.py --evidence build/cycle-additive-native
check-cycle-additive-sanitize:
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) python3 tests/cycle-additive.py --sanitize --evidence build/cycle-additive-sanitize
check check-portable: check-cycle-additive check-cycle-additive-sanitize
check-sanitize: check-cycle-additive-sanitize
check-managed-graphs-profiles: check-cycle-additive check-cycle-additive-sanitize

.PHONY: check-cycle-registry-growth check-cycle-registry-growth-sanitize
check-cycle-registry-growth: tests/cycle-registry-growth.c tests/cycle-additive.c tests/cycle-additive.py tools/cycle_runtime.py
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/cycle-additive.py --fixture cycle-registry-growth.c --evidence "$(CURDIR)/build/cycle-registry-growth-native"
check-cycle-registry-growth-sanitize: tests/cycle-registry-growth.c tests/cycle-additive.c tests/cycle-additive.py tools/cycle_runtime.py
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) python3 tests/cycle-additive.py --fixture cycle-registry-growth.c --sanitize --evidence "$(CURDIR)/build/cycle-registry-growth-sanitize"
check check-portable: check-cycle-registry-growth check-cycle-registry-growth-sanitize
check-sanitize: check-cycle-registry-growth-sanitize
check-managed-graphs-profiles: check-cycle-registry-growth check-cycle-registry-growth-sanitize

# Both C mains own their complete schedules; no --nodes arguments apply.
.PHONY: check-cycle-registration-exposure check-cycle-registration-exposure-sanitize
CYCLE_REGISTRATION_INPUTS = tests/cycle-registration.py tests/cycle-registration-exposure.c tests/cycle-late-registration.c tests/cycle-late-registration.min tests/cycle-additive.c tests/cycle-additive.py tests/errors-language.py tests/callbacks.py tests/errors_evidence.py tests/test_evidence.py tools/cycle_runtime.py $(RUNTIME_HEADERS)
check-cycle-registration-exposure: build/minyarc-errors $(CYCLE_REGISTRATION_INPUTS)
	MINYAR_ERRORS_COMPILER=./build/minyarc-errors MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/cycle-registration.py --evidence "$(CURDIR)/build/cycle-registration-exposure-native"
check-cycle-registration-exposure-sanitize: build/minyarc-errors-sanitize $(CYCLE_REGISTRATION_INPUTS)
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_ERRORS_COMPILER=./build/minyarc-errors-sanitize MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) python3 tests/cycle-registration.py --sanitize --evidence "$(CURDIR)/build/cycle-registration-exposure-sanitize"
check: check-cycle-registration-exposure check-cycle-registration-exposure-sanitize
check-portable: check-cycle-registration-exposure check-cycle-registration-exposure-sanitize
check-managed-graphs-profiles: check-cycle-registration-exposure check-cycle-registration-exposure-sanitize
check-sanitize: check-cycle-registration-exposure-sanitize

# Every C command takes N OPERATION [ARGS]; these are production-header controls.
.PHONY: check-cycle-private-retirement check-cycle-private-retirement-sanitize
CYCLE_PRIVATE_RETIREMENT_INPUTS = tests/cycle-private-retirement.py tests/cycle-idle-invalidation.c tests/cycle-private-retirement-v5.json tests/cycle-additive.c tests/cycle-additive.py tests/clang_helpers.py tests/test_evidence.py tools/cycle_runtime.py runtime/minyar_runtime.c $(RUNTIME_HEADERS)
check-cycle-private-retirement: $(CYCLE_PRIVATE_RETIREMENT_INPUTS) | build
	@set -e; evidence=$$(mktemp -d "$(abspath build)/cycle-private-retirement-native-XXXXXX"); \
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/cycle-private-retirement.py --evidence "$$evidence/run"
check-cycle-private-retirement-sanitize: $(CYCLE_PRIVATE_RETIREMENT_INPUTS) | build
	@set -e; evidence=$$(mktemp -d "$(abspath build)/cycle-private-retirement-sanitize-XXXXXX"); \
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) python3 tests/cycle-private-retirement.py --sanitize --evidence "$$evidence/run"
check: check-cycle-private-retirement check-cycle-private-retirement-sanitize
check-portable: check-cycle-private-retirement check-cycle-private-retirement-sanitize
check-managed-graphs-profiles: check-cycle-private-retirement check-cycle-private-retirement-sanitize
check-sanitize: check-cycle-private-retirement-sanitize

# Mocked idle observability preserves the historical metric.
# This deterministic API contract does not replay a Windows idle failure.
.PHONY: check-cycle-progress-observability
check-cycle-progress-observability: tests/cycle-progress-observability.py tests/cycle-progress-observability-harness.py tests/cycle-progress.c tests/fixtures/cycle-progress-before-observability.c.txt tests/clang_helpers.py tests/test_evidence.py tests/windows_job_owner.py tools/host_paths.py | build
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/cycle-progress-observability-harness.py
	@set -e; evidence=$$(mktemp -d "$(abspath build)/cycle-progress-observability.XXXXXXXX"); \
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/cycle-progress-observability.py --evidence "$$evidence/run"
check check-cycle-progress check-cycle-progress-sanitize check-managed-graphs-profiles check-portable check-sanitize: check-cycle-progress-observability

# Leaf churn uses the existing rooted-graph driver and its complete C schedule.
.PHONY: check-cycle-leaf-churn check-cycle-leaf-churn-sanitize
check-cycle-leaf-churn: tests/cycle-leaf-churn.c tests/cycle-additive.c tests/cycle-additive.py tools/cycle_runtime.py
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/cycle-additive.py --fixture cycle-leaf-churn.c --evidence "$(CURDIR)/build/cycle-leaf-churn-native"
check-cycle-leaf-churn-sanitize: tests/cycle-leaf-churn.c tests/cycle-additive.c tests/cycle-additive.py tools/cycle_runtime.py
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) python3 tests/cycle-additive.py --fixture cycle-leaf-churn.c --sanitize --evidence "$(CURDIR)/build/cycle-leaf-churn-sanitize"
check check-portable: check-cycle-leaf-churn check-cycle-leaf-churn-sanitize
check-managed-graphs-profiles: check-cycle-leaf-churn check-cycle-leaf-churn-sanitize
check-sanitize: check-cycle-leaf-churn-sanitize

# Captured-zero locality uses the existing driver and only bounded profiles.
.PHONY: check-cycle-captured-retirement check-cycle-captured-retirement-sanitize
CYCLE_CAPTURED_RETIREMENT_INPUTS = tests/cycle-captured-retirement.c tests/cycle-leaf-churn.c tests/cycle-additive.c tests/cycle-additive.py tools/cycle_runtime.py runtime/minyar_runtime.c $(RUNTIME_HEADERS)
check-cycle-captured-retirement: $(CYCLE_CAPTURED_RETIREMENT_INPUTS) | build
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/cycle-additive.py --fixture cycle-captured-retirement.c --evidence "$(CURDIR)/build/cycle-captured-retirement-native"
check-cycle-captured-retirement-sanitize: $(CYCLE_CAPTURED_RETIREMENT_INPUTS) | build
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) python3 tests/cycle-additive.py --fixture cycle-captured-retirement.c --sanitize --evidence "$(CURDIR)/build/cycle-captured-retirement-sanitize"
check-managed-graphs-profiles: check-cycle-captured-retirement check-cycle-captured-retirement-sanitize

# Fresh local-MARK zero retirement and issued-marker expiry, bounded profiles only.
.PHONY: check-cycle-fresh-mark-retirement check-cycle-fresh-mark-retirement-sanitize
CYCLE_FRESH_MARK_RETIREMENT_INPUTS = tests/cycle-fresh-mark-retirement.c tests/cycle-leaf-churn.c tests/cycle-additive.c tests/cycle-additive.py tools/cycle_runtime.py runtime/minyar_runtime.c $(RUNTIME_HEADERS)
check-cycle-fresh-mark-retirement: $(CYCLE_FRESH_MARK_RETIREMENT_INPUTS) | build
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/cycle-additive.py --fixture cycle-fresh-mark-retirement.c --evidence "$(CURDIR)/build/cycle-fresh-mark-retirement-native"
check-cycle-fresh-mark-retirement-sanitize: $(CYCLE_FRESH_MARK_RETIREMENT_INPUTS) | build
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) python3 tests/cycle-additive.py --fixture cycle-fresh-mark-retirement.c --sanitize --evidence "$(CURDIR)/build/cycle-fresh-mark-retirement-sanitize"
check-managed-graphs-profiles: check-cycle-fresh-mark-retirement check-cycle-fresh-mark-retirement-sanitize

.PHONY: check-cycle-detached-first-insertion check-cycle-detached-first-insertion-sanitize
CYCLE_DETACHED_FIRST_INSERTION_INPUTS = tests/cycle-detached-first-insertion.c tests/cycle-leaf-churn.c tests/cycle-additive.c tests/cycle-additive.py tools/cycle_runtime.py runtime/minyar_runtime.c $(RUNTIME_HEADERS)
check-cycle-detached-first-insertion: $(CYCLE_DETACHED_FIRST_INSERTION_INPUTS) | build
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/cycle-additive.py --fixture cycle-detached-first-insertion.c --budgets 1 32 --nodes 512 2048 --evidence "$(CURDIR)/build/cycle-detached-first-insertion-native"
check-cycle-detached-first-insertion-sanitize: $(CYCLE_DETACHED_FIRST_INSERTION_INPUTS) | build
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) python3 tests/cycle-additive.py --fixture cycle-detached-first-insertion.c --budgets 1 32 --nodes 512 2048 --sanitize --evidence "$(CURDIR)/build/cycle-detached-first-insertion-sanitize"
check-managed-graphs-profiles: check-cycle-detached-first-insertion check-cycle-detached-first-insertion-sanitize

# Scanned full-MARK actual-zero retirement and issued-job expiry, bounded profiles only.
.PHONY: check-cycle-full-mark-retirement check-cycle-full-mark-retirement-sanitize
CYCLE_FULL_MARK_RETIREMENT_INPUTS = tests/cycle-full-mark-zero.c tests/cycle-detached-first-insertion.c tests/cycle-leaf-churn.c tests/cycle-additive.c tests/cycle-additive.py tools/cycle_runtime.py runtime/minyar_runtime.c $(RUNTIME_HEADERS)
check-cycle-full-mark-retirement: $(CYCLE_FULL_MARK_RETIREMENT_INPUTS) | build
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/cycle-additive.py --fixture cycle-full-mark-zero.c --budgets 1 32 --nodes 512 2048 --evidence "$(CURDIR)/build/cycle-full-mark-retirement-native"
check-cycle-full-mark-retirement-sanitize: $(CYCLE_FULL_MARK_RETIREMENT_INPUTS) | build
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) python3 tests/cycle-additive.py --fixture cycle-full-mark-zero.c --budgets 1 32 --nodes 512 2048 --sanitize --evidence "$(CURDIR)/build/cycle-full-mark-retirement-sanitize"
check-managed-graphs-profiles: check-cycle-full-mark-retirement check-cycle-full-mark-retirement-sanitize
