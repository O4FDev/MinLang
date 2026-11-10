# This frontend/runtime is selected only by parsed cycle/callback features.
# The historical compiler control is hash-checked, never a mutable baseline.
.PHONY: check-feature-dispatch check-managed-graphs check-managed-graphs-sanitize check-managed-graphs-profiles check-managed-graphs-launcher check-callbacks check-callbacks-sanitize check-callback-domains check-isolated-workers check-isolated-workers-sanitize

check-feature-dispatch: build/minyarc build/minyar-runtime.o build/tooling/tests/feature-dispatch
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/feature-dispatch

build/tooling/tests/managed-graphs: TOOL_NATIVE = tests/sha256-test-native.c
build/tooling/tests/managed-graphs: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/managed-graphs: tests/sha256-test-native.c
build/tooling/tests/managed-graphs-profiles: TOOL_NATIVE = runtime/native/sha256.c
build/tooling/tests/managed-graphs-profiles: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/managed-graphs-profiles: runtime/native/sha256.c
build/tooling/tests/managed-graphs-launcher: TOOL_NATIVE = tests/sha256-test-native.c runtime/native/sha256.c
build/tooling/tests/managed-graphs-launcher: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/managed-graphs-launcher: tests/sha256-test-native.c runtime/native/sha256.c
build/tooling/tests/managed-graphs-profiles.ll build/tooling/tests/managed-graphs-launcher.ll: tests/thread-port-support.min
# One target per named selector group; each piece reuses one runtime object per process.
MANAGED_GRAPH_PARTS = check-managed-graphs-part1 check-managed-graphs-part2 check-managed-graphs-part3 check-managed-graphs-part4
.PHONY: $(MANAGED_GRAPH_PARTS)
check-managed-graphs: $(MANAGED_GRAPH_PARTS)
$(MANAGED_GRAPH_PARTS): build/minyarc build/minyarc-callbacks build/tooling/tests/managed-graphs
check-managed-graphs-part1:
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/managed-graphs ManagedGraphs.test_existing_recursive_programs_preserve_behavior
check-managed-graphs-part2:
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/managed-graphs ManagedGraphs.test_list_edge_can_close_a_self_cycle ManagedGraphs.test_enabling_cycles_preserves_index_contract_failure ManagedGraphs.test_record_edge_can_close_a_self_cycle ManagedGraphs.test_mutually_recursive_aliases_and_replacement ManagedGraphs.test_preserved_record_field_assignment_closes_shared_mutual_cycle
check-managed-graphs-part3:
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/managed-graphs ManagedGraphs.test_preserved_module_aliases_execute_cycle_writes ManagedGraphs.test_preserved_nested_list_helper_and_return_alias_cycles ManagedGraphs.test_preserved_alias_return_and_record_projection_cycles ManagedGraphs.test_unrelated_recursive_types_keep_untraced_allocations ManagedGraphs.test_closure_callback_retains_lexical_capture
check-managed-graphs-part4:
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/managed-graphs ManagedGraphs.test_adapted_graph_churn_temporaries_and_shared_append

check-callbacks: build/minyarc-callbacks build/closure-compiler-stage3.ll build/minyar-runtime.o build/tooling/tests/callbacks build/testing/cycle-runtime.o build/tooling/tests/compiler-behavior
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/compiler-behavior --profile callbacks --ir build/closure-compiler-stage3.ll
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/callbacks

check-managed-graphs-profiles: build/tooling/tests/managed-graphs-profiles
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/managed-graphs-profiles --quick

# Preserve the original allocation-only and continuously growing producer bounds.
# The existing quick matrix covers bounded heaps at K1/K32, native and sanitizer.
.PHONY: check-managed-graphs-bakeoff
CYCLE_BAKEOFF_INPUTS = tests/managed-graphs-bakeoff.c tests/managed-graphs-runtime.c build/tooling/tests/managed-graphs-profiles runtime/minyar_runtime.c $(RUNTIME_HEADERS)
check-managed-graphs-bakeoff: $(CYCLE_BAKEOFF_INPUTS) | build
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/managed-graphs-profiles --quick --fixture managed-graphs-bakeoff.c
check check-portable check-sanitize check-managed-graphs-profiles: check-managed-graphs-bakeoff

check-callback-domains: build/tooling/tests/callback-domains
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/callback-domains

# Incremental fallback uses the POSIX-only module build driver; the native
# Windows launcher still exercises debug/release profiles and callbacks.
MANAGED_GRAPH_LAUNCHER_ARTIFACTS = build/minyarc build/minyarc-callbacks
ifeq ($(filter Windows_NT,$(OS))$(filter MSYS% MINGW% CYGWIN%,$(MINYAR_HOST_SYSTEM)),)
MANAGED_GRAPH_LAUNCHER_ARTIFACTS += build/minyarc-modules build/minyar-module-build
endif

# Three selector pieces plus one piece per bakeoff heap profile; --bakeoff-profiles only
# narrows that case, which without it still runs every profile in both modes.
MANAGED_GRAPH_LAUNCHER_FILTERED = check-managed-graphs-launcher-part4 check-managed-graphs-launcher-part5 check-managed-graphs-launcher-part6 check-managed-graphs-launcher-part7 check-managed-graphs-launcher-part8 check-managed-graphs-launcher-part9 check-managed-graphs-launcher-part10
MANAGED_GRAPH_LAUNCHER_PARTS = check-managed-graphs-launcher-part1 check-managed-graphs-launcher-part2 check-managed-graphs-launcher-part3 $(MANAGED_GRAPH_LAUNCHER_FILTERED)
MANAGED_GRAPH_LAUNCHER_PIECE_DEPENDENCIES = $(MANAGED_GRAPH_LAUNCHER_ARTIFACTS) build/tooling/tests/managed-graphs-launcher
.PHONY: $(MANAGED_GRAPH_LAUNCHER_PARTS)
check-managed-graphs-launcher: $(MANAGED_GRAPH_LAUNCHER_PARTS)
$(MANAGED_GRAPH_LAUNCHER_PARTS): $(MANAGED_GRAPH_LAUNCHER_PIECE_DEPENDENCIES)
check-managed-graphs-launcher-part1:
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/managed-graphs-launcher ManagedGraphLauncher.test_debug_and_release_preserve_selected_heap_and_owner_abi
check-managed-graphs-launcher-part2:
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/managed-graphs-launcher ManagedGraphLauncher.test_debug_and_release_preserve_lazy_heap_policy
check-managed-graphs-launcher-part3:
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/managed-graphs-launcher ManagedGraphLauncher.test_incremental_driver_preserves_parsed_fallback_and_check_mode
check-managed-graphs-launcher-part4:
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/managed-graphs-launcher ManagedGraphLauncher.test_preserved_bakeoff_workload_on_selected_heap_profiles --bakeoff-profiles system --bakeoff-modes native
check-managed-graphs-launcher-part5:
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/managed-graphs-launcher ManagedGraphLauncher.test_preserved_bakeoff_workload_on_selected_heap_profiles --bakeoff-profiles system --bakeoff-modes sanitize
check-managed-graphs-launcher-part6:
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/managed-graphs-launcher ManagedGraphLauncher.test_preserved_bakeoff_workload_on_selected_heap_profiles --bakeoff-profiles fixed --bakeoff-modes native
check-managed-graphs-launcher-part7:
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/managed-graphs-launcher ManagedGraphLauncher.test_preserved_bakeoff_workload_on_selected_heap_profiles --bakeoff-profiles fixed --bakeoff-modes sanitize
check-managed-graphs-launcher-part8:
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/managed-graphs-launcher ManagedGraphLauncher.test_preserved_bakeoff_workload_on_selected_heap_profiles --bakeoff-profiles lazy --bakeoff-modes native
check-managed-graphs-launcher-part9:
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/managed-graphs-launcher ManagedGraphLauncher.test_preserved_bakeoff_workload_on_selected_heap_profiles --bakeoff-profiles lazy --bakeoff-modes sanitize
check-managed-graphs-launcher-part10:
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/managed-graphs-launcher ManagedGraphLauncher.test_preserved_bakeoff_workload_on_selected_heap_profiles --bakeoff-profiles eager

check-isolated-workers: build/minyarc build/minyar-default-runtime.o build/tooling/tests/isolated-workers
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/isolated-workers

build/minyar-default-runtime-sanitize.o: runtime/minyar_default_runtime.c runtime/minyar_runtime.c $(RUNTIME_HEADERS) $(BUILD_RULES) | build
	$(SANITIZER_LIMITED) "$(LLVM_CC)" $(SANITIZER_FLAGS) -c $< -o $@

check-managed-graphs-sanitize: build/minyarc-sanitize build/minyarc-callbacks-sanitize build/tooling/tests/managed-graphs
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_CLANG="$(TEST_CLANG)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/managed-graphs

check-callbacks-sanitize: build/minyarc-callbacks-sanitize build/tooling/tests/callbacks
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_CLANG="$(TEST_CLANG)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/callbacks

check-isolated-workers-sanitize: build/minyarc-sanitize build/minyar-default-runtime-sanitize.o build/tooling/tests/isolated-workers
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_CLANG="$(TEST_CLANG)" MINYAR_WORKER_RUNTIME=./build/minyar-default-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/isolated-workers

# The pre-existing type-reachability oracles now require parsed feature
# dispatch for cyclic cases; all acyclic and invalid-type cases are retained.
# peer-tests.mk gives these to each per-suite child of the peer gates.
PEER_FEATURE_ARTIFACTS += build/minyarc-callbacks
PEER_FEATURE_SANITIZE_ARTIFACTS += build/minyarc-callbacks-sanitize
check-recursive-data check-bounded check-ownership check-adversarial check-peer-regressions check-peer-optimizations check-peer-sanitize check-peer-ownership: build/minyarc-callbacks
check-recursive-data check-bounded check-peer-sanitize check-peer-ownership check-sanitize: build/minyarc-callbacks-sanitize

check-portable check: check-feature-dispatch check-managed-graphs check-managed-graphs-launcher check-callbacks check-callback-domains check-isolated-workers
check-sanitize: check-managed-graphs-sanitize check-callbacks-sanitize check-managed-graphs-profiles check-isolated-workers-sanitize

# Explicit sanitizer installations may keep their Windows runtime DLLs
# beside the selected compiler rather than the ordinary compiler's directory.
CYCLE_SANITIZER_CLANG = $(or $(MINYAR_SANITIZER_CLANG),$(LLVM_CC))
CYCLE_SANITIZER_PATH = $(if $(MINYAR_SANITIZER_CLANG),$(dir $(MINYAR_SANITIZER_CLANG)):$(PATH),$(PATH))

build/tooling/tests/cycle-witness.ll: tests/cycle-port-support.min tests/thread-port-support.min
build/tooling/tests/cycle-progress.ll: tests/cycle-port-support.min tests/thread-port-support.min
build/tooling/tests/cycle-additive.ll: tests/cycle-port-support.min tests/thread-port-support.min
build/tooling/tests/cycle-registration.ll: tests/cycle-port-support.min tests/thread-port-support.min
build/tooling/tests/cycle-private-retirement.ll: tests/cycle-port-support.min tests/thread-port-support.min
build/tooling/tests/cycle-registration.ll: tests/frontend-fixtures.min
build/tooling/tests/cycle-private-retirement.ll: tests/evidence-support.min
.PHONY: check-cycle-progress check-cycle-progress-sanitize
build/tooling/tests/cycle-progress: TOOL_NATIVE = runtime/native/sha256.c
build/tooling/tests/cycle-progress: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/cycle-progress: runtime/native/sha256.c
check-cycle-progress: build/tooling/tests/cycle-progress
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/cycle-progress --evidence build/cycle-progress-native
check-cycle-progress-sanitize: build/tooling/tests/cycle-progress
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/cycle-progress --sanitize --evidence build/cycle-progress-sanitize
check check-portable: check-cycle-progress
check-sanitize: check-cycle-progress-sanitize

.PHONY: check-cycle-witness check-cycle-witness-sanitize
build/tooling/tests/cycle-witness: TOOL_NATIVE = runtime/native/sha256.c
build/tooling/tests/cycle-witness: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/cycle-witness: runtime/native/sha256.c
check-cycle-witness: build/tooling/tests/cycle-witness
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/cycle-witness --evidence build/cycle-witness-native
check-cycle-witness-sanitize: build/tooling/tests/cycle-witness
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/cycle-witness --sanitize --evidence build/cycle-witness-sanitize
check check-portable: check-cycle-witness check-cycle-witness-sanitize
check-sanitize: check-cycle-witness-sanitize
check-managed-graphs-profiles: check-cycle-witness check-cycle-witness-sanitize

.PHONY: check-cycle-additive check-cycle-additive-sanitize
build/tooling/tests/cycle-additive: TOOL_NATIVE = runtime/native/sha256.c
build/tooling/tests/cycle-additive: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/cycle-additive: runtime/native/sha256.c
check-cycle-additive: build/tooling/tests/cycle-additive
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/cycle-additive --evidence build/cycle-additive-native
check-cycle-additive-sanitize: build/tooling/tests/cycle-additive
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/cycle-additive --sanitize --evidence build/cycle-additive-sanitize
check check-portable: check-cycle-additive check-cycle-additive-sanitize
check-sanitize: check-cycle-additive-sanitize
check-managed-graphs-profiles: check-cycle-additive check-cycle-additive-sanitize

.PHONY: check-cycle-registry-growth check-cycle-registry-growth-sanitize
check-cycle-registry-growth: tests/cycle-registry-growth.c tests/cycle-additive.c tests/cycle-additive.min build/tooling/tests/cycle-additive
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/cycle-additive --fixture cycle-registry-growth.c --evidence "$(CURDIR)/build/cycle-registry-growth-native"
check-cycle-registry-growth-sanitize: tests/cycle-registry-growth.c tests/cycle-additive.c tests/cycle-additive.min build/tooling/tests/cycle-additive
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/cycle-additive --fixture cycle-registry-growth.c --sanitize --evidence "$(CURDIR)/build/cycle-registry-growth-sanitize"
check check-portable: check-cycle-registry-growth check-cycle-registry-growth-sanitize
check-sanitize: check-cycle-registry-growth-sanitize
check-managed-graphs-profiles: check-cycle-registry-growth check-cycle-registry-growth-sanitize

# Both C mains own their complete schedules; no --nodes arguments apply.
.PHONY: check-cycle-registration-exposure check-cycle-registration-exposure-sanitize
CYCLE_REGISTRATION_INPUTS = build/tooling/tests/cycle-registration build/tooling/tests/errors-language tests/cycle-registration-exposure.c tests/cycle-late-registration.c tests/cycle-late-registration.min tests/cycle-additive.c tests/memory-contracts-runtime.c $(RUNTIME_HEADERS)
build/tooling/tests/cycle-registration: TOOL_NATIVE = runtime/native/sha256.c
build/tooling/tests/cycle-registration: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/cycle-registration: runtime/native/sha256.c
# One target per heap profile and budget group; the eager piece also runs the Result
# callback oracle exactly once, as the unsplit harness did.
CYCLE_REGISTRATION_GROUPS = system-low system-high fixed-low fixed-high lazy-low lazy-high eager
CYCLE_REGISTRATION_PARTS = $(addprefix check-cycle-registration-exposure-part-,$(CYCLE_REGISTRATION_GROUPS))
CYCLE_REGISTRATION_SANITIZE_PARTS = $(addprefix check-cycle-registration-exposure-sanitize-part-,$(CYCLE_REGISTRATION_GROUPS))
.PHONY: $(CYCLE_REGISTRATION_PARTS) $(CYCLE_REGISTRATION_SANITIZE_PARTS)
check-cycle-registration-exposure: $(CYCLE_REGISTRATION_PARTS)
check-cycle-registration-exposure-sanitize: $(CYCLE_REGISTRATION_SANITIZE_PARTS)
$(CYCLE_REGISTRATION_PARTS): build/minyarc-errors $(CYCLE_REGISTRATION_INPUTS)
$(CYCLE_REGISTRATION_SANITIZE_PARTS): build/minyarc-errors-sanitize $(CYCLE_REGISTRATION_INPUTS)
check-cycle-registration-exposure-part-system-low:
	MINYAR_ERRORS_COMPILER=./build/minyarc-errors MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/cycle-registration --profiles system --budgets 1 32 --skip-result-oracle --evidence "$(CURDIR)/build/cycle-registration-exposure-native-system-low"
check-cycle-registration-exposure-part-system-high:
	MINYAR_ERRORS_COMPILER=./build/minyarc-errors MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/cycle-registration --profiles system --budgets 1024 --skip-result-oracle --evidence "$(CURDIR)/build/cycle-registration-exposure-native-system-high"
check-cycle-registration-exposure-part-fixed-low:
	MINYAR_ERRORS_COMPILER=./build/minyarc-errors MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/cycle-registration --profiles fixed --budgets 1 32 --skip-result-oracle --evidence "$(CURDIR)/build/cycle-registration-exposure-native-fixed-low"
check-cycle-registration-exposure-part-fixed-high:
	MINYAR_ERRORS_COMPILER=./build/minyarc-errors MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/cycle-registration --profiles fixed --budgets 1024 --skip-result-oracle --evidence "$(CURDIR)/build/cycle-registration-exposure-native-fixed-high"
check-cycle-registration-exposure-part-lazy-low:
	MINYAR_ERRORS_COMPILER=./build/minyarc-errors MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/cycle-registration --profiles lazy --budgets 1 32 --skip-result-oracle --evidence "$(CURDIR)/build/cycle-registration-exposure-native-lazy-low"
check-cycle-registration-exposure-part-lazy-high:
	MINYAR_ERRORS_COMPILER=./build/minyarc-errors MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/cycle-registration --profiles lazy --budgets 1024 --skip-result-oracle --evidence "$(CURDIR)/build/cycle-registration-exposure-native-lazy-high"
check-cycle-registration-exposure-part-eager:
	MINYAR_ERRORS_COMPILER=./build/minyarc-errors MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/cycle-registration --profiles eager --evidence "$(CURDIR)/build/cycle-registration-exposure-native-eager"
check-cycle-registration-exposure-sanitize-part-system-low:
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_ERRORS_COMPILER=./build/minyarc-errors-sanitize MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/cycle-registration --sanitize --profiles system --budgets 1 32 --skip-result-oracle --evidence "$(CURDIR)/build/cycle-registration-exposure-sanitize-system-low"
check-cycle-registration-exposure-sanitize-part-system-high:
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_ERRORS_COMPILER=./build/minyarc-errors-sanitize MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/cycle-registration --sanitize --profiles system --budgets 1024 --skip-result-oracle --evidence "$(CURDIR)/build/cycle-registration-exposure-sanitize-system-high"
check-cycle-registration-exposure-sanitize-part-fixed-low:
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_ERRORS_COMPILER=./build/minyarc-errors-sanitize MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/cycle-registration --sanitize --profiles fixed --budgets 1 32 --skip-result-oracle --evidence "$(CURDIR)/build/cycle-registration-exposure-sanitize-fixed-low"
check-cycle-registration-exposure-sanitize-part-fixed-high:
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_ERRORS_COMPILER=./build/minyarc-errors-sanitize MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/cycle-registration --sanitize --profiles fixed --budgets 1024 --skip-result-oracle --evidence "$(CURDIR)/build/cycle-registration-exposure-sanitize-fixed-high"
check-cycle-registration-exposure-sanitize-part-lazy-low:
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_ERRORS_COMPILER=./build/minyarc-errors-sanitize MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/cycle-registration --sanitize --profiles lazy --budgets 1 32 --skip-result-oracle --evidence "$(CURDIR)/build/cycle-registration-exposure-sanitize-lazy-low"
check-cycle-registration-exposure-sanitize-part-lazy-high:
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_ERRORS_COMPILER=./build/minyarc-errors-sanitize MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/cycle-registration --sanitize --profiles lazy --budgets 1024 --skip-result-oracle --evidence "$(CURDIR)/build/cycle-registration-exposure-sanitize-lazy-high"
check-cycle-registration-exposure-sanitize-part-eager:
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_ERRORS_COMPILER=./build/minyarc-errors-sanitize MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/cycle-registration --sanitize --profiles eager --evidence "$(CURDIR)/build/cycle-registration-exposure-sanitize-eager"
check: check-cycle-registration-exposure check-cycle-registration-exposure-sanitize
check-portable: check-cycle-registration-exposure check-cycle-registration-exposure-sanitize
check-managed-graphs-profiles: check-cycle-registration-exposure check-cycle-registration-exposure-sanitize
check-sanitize: check-cycle-registration-exposure-sanitize

# Every C command takes N OPERATION [ARGS]; these are production-header controls.
.PHONY: check-cycle-private-retirement check-cycle-private-retirement-sanitize
CYCLE_PRIVATE_RETIREMENT_INPUTS = build/tooling/tests/cycle-private-retirement tests/cycle-idle-invalidation.c tests/cycle-private-retirement-v5.json tests/fixtures/cycle-private-retirement-v5-collector.h tests/cycle-additive.c runtime/minyar_runtime.c $(RUNTIME_HEADERS)
build/tooling/tests/cycle-private-retirement: TOOL_NATIVE = tests/evidence-support-native.c runtime/native/sha256.c
build/tooling/tests/cycle-private-retirement: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/cycle-private-retirement: tests/evidence-support-native.c runtime/native/sha256.c
# Evidence retains Clang itself; permit files up to 512 MiB for these checks.
# One target per heap profile; each piece keeps its own mktemp evidence tree and only
# removes its own stale evidence directories.
CYCLE_PRIVATE_RETIREMENT_PARTS = check-cycle-private-retirement-part-system check-cycle-private-retirement-part-fixed check-cycle-private-retirement-part-lazy check-cycle-private-retirement-part-eager
CYCLE_PRIVATE_RETIREMENT_SANITIZE_PARTS = check-cycle-private-retirement-sanitize-part-system check-cycle-private-retirement-sanitize-part-fixed check-cycle-private-retirement-sanitize-part-lazy check-cycle-private-retirement-sanitize-part-eager
.PHONY: $(CYCLE_PRIVATE_RETIREMENT_PARTS) $(CYCLE_PRIVATE_RETIREMENT_SANITIZE_PARTS)
check-cycle-private-retirement check-cycle-private-retirement-sanitize $(CYCLE_PRIVATE_RETIREMENT_PARTS) $(CYCLE_PRIVATE_RETIREMENT_SANITIZE_PARTS): export MINYAR_MAX_FILE_BLOCKS ?= 1048576
check-cycle-private-retirement: $(CYCLE_PRIVATE_RETIREMENT_PARTS)
check-cycle-private-retirement-sanitize: $(CYCLE_PRIVATE_RETIREMENT_SANITIZE_PARTS)
$(CYCLE_PRIVATE_RETIREMENT_PARTS) $(CYCLE_PRIVATE_RETIREMENT_SANITIZE_PARTS): $(CYCLE_PRIVATE_RETIREMENT_INPUTS) | build
check-cycle-private-retirement-part-system:
	@set -e; rm -rf -- build/cycle-private-retirement-native-system-*; evidence=$$(mktemp -d "$(abspath build)/cycle-private-retirement-native-system-XXXXXX"); \
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/cycle-private-retirement --profiles system --evidence "$$evidence/run"
check-cycle-private-retirement-part-fixed:
	@set -e; rm -rf -- build/cycle-private-retirement-native-fixed-*; evidence=$$(mktemp -d "$(abspath build)/cycle-private-retirement-native-fixed-XXXXXX"); \
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/cycle-private-retirement --profiles fixed --evidence "$$evidence/run"
check-cycle-private-retirement-part-lazy:
	@set -e; rm -rf -- build/cycle-private-retirement-native-lazy-*; evidence=$$(mktemp -d "$(abspath build)/cycle-private-retirement-native-lazy-XXXXXX"); \
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/cycle-private-retirement --profiles lazy --evidence "$$evidence/run"
check-cycle-private-retirement-part-eager:
	@set -e; rm -rf -- build/cycle-private-retirement-native-eager-*; evidence=$$(mktemp -d "$(abspath build)/cycle-private-retirement-native-eager-XXXXXX"); \
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/cycle-private-retirement --profiles eager --evidence "$$evidence/run"
check-cycle-private-retirement-sanitize-part-system:
	@set -e; rm -rf -- build/cycle-private-retirement-sanitize-system-*; evidence=$$(mktemp -d "$(abspath build)/cycle-private-retirement-sanitize-system-XXXXXX"); \
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/cycle-private-retirement --sanitize --profiles system --evidence "$$evidence/run"
check-cycle-private-retirement-sanitize-part-fixed:
	@set -e; rm -rf -- build/cycle-private-retirement-sanitize-fixed-*; evidence=$$(mktemp -d "$(abspath build)/cycle-private-retirement-sanitize-fixed-XXXXXX"); \
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/cycle-private-retirement --sanitize --profiles fixed --evidence "$$evidence/run"
check-cycle-private-retirement-sanitize-part-lazy:
	@set -e; rm -rf -- build/cycle-private-retirement-sanitize-lazy-*; evidence=$$(mktemp -d "$(abspath build)/cycle-private-retirement-sanitize-lazy-XXXXXX"); \
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/cycle-private-retirement --sanitize --profiles lazy --evidence "$$evidence/run"
check-cycle-private-retirement-sanitize-part-eager:
	@set -e; rm -rf -- build/cycle-private-retirement-sanitize-eager-*; evidence=$$(mktemp -d "$(abspath build)/cycle-private-retirement-sanitize-eager-XXXXXX"); \
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/cycle-private-retirement --sanitize --profiles eager --evidence "$$evidence/run"
check: check-cycle-private-retirement check-cycle-private-retirement-sanitize
check-portable: check-cycle-private-retirement check-cycle-private-retirement-sanitize
check-managed-graphs-profiles: check-cycle-private-retirement check-cycle-private-retirement-sanitize
check-sanitize: check-cycle-private-retirement-sanitize

# Mocked idle observability preserves the historical metric.
# This deterministic API contract does not replay a Windows idle failure.
.PHONY: check-cycle-progress-observability
IDLE_OBSERVABILITY_TOOLS = build/tooling/tests/cycle-progress-observability build/tooling/tests/cycle-progress-observability-harness
build/tooling/tests/cycle-progress-observability.ll: tests/evidence-support.min
build/tooling/tests/cycle-progress-observability-harness.ll: tests/cycle-progress-observability.min tests/evidence-support.min
$(IDLE_OBSERVABILITY_TOOLS): TOOL_RUNTIME = build/testing/cycle-runtime.o
$(IDLE_OBSERVABILITY_TOOLS): TOOL_NATIVE = tests/cycle-progress-observability-native.c tests/evidence-support-native.c runtime/native/sha256.c
$(IDLE_OBSERVABILITY_TOOLS): TOOL_LIBS = $(TOOL_CRYPTO)
$(IDLE_OBSERVABILITY_TOOLS): build/testing/cycle-runtime.o tests/cycle-progress-observability-native.c tests/evidence-support-native.c runtime/native/sha256.c
check-cycle-progress-observability: build/tooling/tests/cycle-progress-observability build/tooling/tests/cycle-progress-observability-harness tests/cycle-progress.c tests/fixtures/cycle-progress-before-observability.c.txt | build
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/cycle-progress-observability-harness
	@set -e; rm -rf -- build/cycle-progress-observability.*; evidence=$$(mktemp -d "$(abspath build)/cycle-progress-observability.XXXXXXXX"); \
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/cycle-progress-observability --evidence "$$evidence/run"
check check-cycle-progress check-cycle-progress-sanitize check-managed-graphs-profiles check-portable check-sanitize: check-cycle-progress-observability

# Leaf churn uses the existing rooted-graph driver and its complete C schedule.
.PHONY: check-cycle-leaf-churn check-cycle-leaf-churn-sanitize
check-cycle-leaf-churn: tests/cycle-leaf-churn.c tests/cycle-additive.c tests/cycle-additive.min build/tooling/tests/cycle-additive
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/cycle-additive --fixture cycle-leaf-churn.c --evidence "$(CURDIR)/build/cycle-leaf-churn-native"
check-cycle-leaf-churn-sanitize: tests/cycle-leaf-churn.c tests/cycle-additive.c tests/cycle-additive.min build/tooling/tests/cycle-additive
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/cycle-additive --fixture cycle-leaf-churn.c --sanitize --evidence "$(CURDIR)/build/cycle-leaf-churn-sanitize"
check check-portable: check-cycle-leaf-churn check-cycle-leaf-churn-sanitize
check-managed-graphs-profiles: check-cycle-leaf-churn check-cycle-leaf-churn-sanitize
check-sanitize: check-cycle-leaf-churn-sanitize

# Captured-zero locality uses the existing driver and only bounded profiles.
.PHONY: check-cycle-captured-retirement check-cycle-captured-retirement-sanitize
CYCLE_CAPTURED_RETIREMENT_INPUTS = tests/cycle-captured-retirement.c tests/cycle-leaf-churn.c tests/cycle-additive.c tests/cycle-additive.min runtime/minyar_runtime.c $(RUNTIME_HEADERS)
check-cycle-captured-retirement: $(CYCLE_CAPTURED_RETIREMENT_INPUTS) build/tooling/tests/cycle-additive | build
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/cycle-additive --fixture cycle-captured-retirement.c --evidence "$(CURDIR)/build/cycle-captured-retirement-native"
check-cycle-captured-retirement-sanitize: $(CYCLE_CAPTURED_RETIREMENT_INPUTS) build/tooling/tests/cycle-additive | build
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/cycle-additive --fixture cycle-captured-retirement.c --sanitize --evidence "$(CURDIR)/build/cycle-captured-retirement-sanitize"
check-managed-graphs-profiles: check-cycle-captured-retirement check-cycle-captured-retirement-sanitize

# Fresh local-MARK zero retirement and issued-marker expiry, bounded profiles only.
.PHONY: check-cycle-fresh-mark-retirement check-cycle-fresh-mark-retirement-sanitize
CYCLE_FRESH_MARK_RETIREMENT_INPUTS = tests/cycle-fresh-mark-retirement.c tests/cycle-leaf-churn.c tests/cycle-additive.c tests/cycle-additive.min runtime/minyar_runtime.c $(RUNTIME_HEADERS)
check-cycle-fresh-mark-retirement: $(CYCLE_FRESH_MARK_RETIREMENT_INPUTS) build/tooling/tests/cycle-additive | build
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/cycle-additive --fixture cycle-fresh-mark-retirement.c --evidence "$(CURDIR)/build/cycle-fresh-mark-retirement-native"
check-cycle-fresh-mark-retirement-sanitize: $(CYCLE_FRESH_MARK_RETIREMENT_INPUTS) build/tooling/tests/cycle-additive | build
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/cycle-additive --fixture cycle-fresh-mark-retirement.c --sanitize --evidence "$(CURDIR)/build/cycle-fresh-mark-retirement-sanitize"
check-managed-graphs-profiles: check-cycle-fresh-mark-retirement check-cycle-fresh-mark-retirement-sanitize

.PHONY: check-cycle-detached-first-insertion check-cycle-detached-first-insertion-sanitize
CYCLE_DETACHED_FIRST_INSERTION_INPUTS = tests/cycle-detached-first-insertion.c tests/cycle-leaf-churn.c tests/cycle-additive.c tests/cycle-additive.min runtime/minyar_runtime.c $(RUNTIME_HEADERS)
check-cycle-detached-first-insertion: $(CYCLE_DETACHED_FIRST_INSERTION_INPUTS) build/tooling/tests/cycle-additive | build
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/cycle-additive --fixture cycle-detached-first-insertion.c --budgets 1 32 --nodes 512 2048 --evidence "$(CURDIR)/build/cycle-detached-first-insertion-native"
check-cycle-detached-first-insertion-sanitize: $(CYCLE_DETACHED_FIRST_INSERTION_INPUTS) build/tooling/tests/cycle-additive | build
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/cycle-additive --fixture cycle-detached-first-insertion.c --budgets 1 32 --nodes 512 2048 --sanitize --evidence "$(CURDIR)/build/cycle-detached-first-insertion-sanitize"
check-managed-graphs-profiles: check-cycle-detached-first-insertion check-cycle-detached-first-insertion-sanitize

# Scanned full-MARK actual-zero retirement and issued-job expiry, bounded profiles only.
.PHONY: check-cycle-full-mark-zero check-cycle-full-mark-zero-sanitize
CYCLE_FULL_MARK_ZERO_INPUTS = tests/cycle-full-mark-zero.c tests/cycle-detached-first-insertion.c tests/cycle-leaf-churn.c tests/cycle-additive.c tests/cycle-additive.min runtime/minyar_runtime.c $(RUNTIME_HEADERS)
check-cycle-full-mark-zero: $(CYCLE_FULL_MARK_ZERO_INPUTS) build/tooling/tests/cycle-additive | build
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/cycle-additive --fixture cycle-full-mark-zero.c --budgets 1 32 --nodes 512 2048 --evidence "$(CURDIR)/build/cycle-full-mark-zero-native"
check-cycle-full-mark-zero-sanitize: $(CYCLE_FULL_MARK_ZERO_INPUTS) build/tooling/tests/cycle-additive | build
	PATH="$(CYCLE_SANITIZER_PATH)" MINYAR_TEST_CLANG="$(CYCLE_SANITIZER_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/cycle-additive --fixture cycle-full-mark-zero.c --budgets 1 32 --nodes 512 2048 --sanitize --evidence "$(CURDIR)/build/cycle-full-mark-zero-sanitize"
check-managed-graphs-profiles: check-cycle-full-mark-zero check-cycle-full-mark-zero-sanitize

check-sanitize: check-cycle-full-mark-zero-sanitize

# Keep the original standalone names as aliases without repeating either recipe.
.PHONY: check-cycle-full-mark-retirement check-cycle-full-mark-retirement-sanitize
check-cycle-full-mark-retirement: check-cycle-full-mark-zero
check-cycle-full-mark-retirement-sanitize: check-cycle-full-mark-zero-sanitize
