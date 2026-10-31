# Native differentials in check-portable run the smallest, default and largest poll budgets (K1, K32, K1024; the empty
# Map check has no K1024, so K1 and K32); the matching *-budgets targets in check-ownership run K2 and K7, so
# `make check` still covers every budget. Sanitizer variants keep the full matrix.
#
# Every differential here is a product of independent cells (runtime x profile x budget x optimization x mode), so each
# check is a recipe-less aggregate of its pieces: one plain make target per runtime/profile pair (or per profile), each
# running the same harness over its own slice with the harness's own selection options. The pieces together run exactly
# the cells the single check ran. Blocks the harness shares across slices (the frame-initialization frozen-control
# negative, the temporary-owner-cache and empty-Map mutants) stay in their system piece and the sibling pieces ask the
# harness to skip them, so no cell is lost or repeated. Every harness makes its own mkdtemp under build/ or writes into
# its own test.scratch(), so pieces never share a directory, an output file or a port.
PERFCS_GATE_BUDGETS = 1,32,1024
PERFCS_OTHER_BUDGETS = 2,7

PERFCS_RUNTIME_PROFILES = ordinary-system ordinary-fixed ordinary-lazy cycle-system cycle-fixed cycle-lazy
PERFCS_TEMPORARY_CACHE_INPUTS = tests/temporary-owner-cache.py tests/temporary-owner-cache.c $(RUNTIME_HEADERS)
PERFCS_FRAME_INITIALIZATION_INPUTS = tests/frame-initialization.py tests/frame-initialization.c $(RUNTIME_HEADERS)

# $(1) target base, $(2) harness, $(3) inputs, $(4) command prefix, $(5) harness arguments, $(6) runtime-profile pair,
# $(7) argument that drops a shared block (used only when the pair is not a system profile).
define PERFCS_RUNTIME_PROFILE_PIECE
check-$(1)-part-$(6): $(3) | build
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(4) python3 "$(2)" $(5) --runtimes $(firstword $(subst -, ,$(6))) --profiles $(lastword $(subst -, ,$(6))) $(if $(filter system,$(lastword $(subst -, ,$(6)))),,$(7))
endef

.PHONY: check-owner-queue-batching check-owner-queue-batching-budgets check-owner-queue-batching-sanitize
check-owner-queue-batching: tests/owner-queue-batching.py tests/owner-queue-batching.c $(RUNTIME_HEADERS) | build
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) python3 "tests/owner-queue-batching.py" --modes native --budgets $(PERFCS_GATE_BUDGETS)

check-owner-queue-batching-budgets: tests/owner-queue-batching.py tests/owner-queue-batching.c $(RUNTIME_HEADERS) | build
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) python3 "tests/owner-queue-batching.py" --modes native --budgets $(PERFCS_OTHER_BUDGETS)

check-owner-queue-batching-sanitize: tests/owner-queue-batching.py tests/owner-queue-batching.c $(RUNTIME_HEADERS) | build
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(SANITIZER_LIMITED) python3 "tests/owner-queue-batching.py" --modes sanitize

.PHONY: check-temporary-owner-cache check-temporary-owner-cache-budgets check-temporary-owner-cache-sanitize \
	$(addprefix check-temporary-owner-cache-part-,$(PERFCS_RUNTIME_PROFILES)) \
	$(addprefix check-temporary-owner-cache-budgets-part-,$(PERFCS_RUNTIME_PROFILES)) \
	$(addprefix check-temporary-owner-cache-sanitize-part-,$(PERFCS_RUNTIME_PROFILES))
check-temporary-owner-cache: $(addprefix check-temporary-owner-cache-part-,$(PERFCS_RUNTIME_PROFILES))

check-temporary-owner-cache-budgets: $(addprefix check-temporary-owner-cache-budgets-part-,$(PERFCS_RUNTIME_PROFILES))

check-temporary-owner-cache-sanitize: $(addprefix check-temporary-owner-cache-sanitize-part-,$(PERFCS_RUNTIME_PROFILES))

$(foreach pair,$(PERFCS_RUNTIME_PROFILES),$(eval $(call PERFCS_RUNTIME_PROFILE_PIECE,temporary-owner-cache,tests/temporary-owner-cache.py,$(PERFCS_TEMPORARY_CACHE_INPUTS),$(LIMITED),--modes native --budgets $(PERFCS_GATE_BUDGETS),$(pair),--skip-mutants)))
$(foreach pair,$(PERFCS_RUNTIME_PROFILES),$(eval $(call PERFCS_RUNTIME_PROFILE_PIECE,temporary-owner-cache-budgets,tests/temporary-owner-cache.py,$(PERFCS_TEMPORARY_CACHE_INPUTS),$(LIMITED),--modes native --budgets $(PERFCS_OTHER_BUDGETS),$(pair),--skip-mutants)))
$(foreach pair,$(PERFCS_RUNTIME_PROFILES),$(eval $(call PERFCS_RUNTIME_PROFILE_PIECE,temporary-owner-cache-sanitize,tests/temporary-owner-cache.py,$(PERFCS_TEMPORARY_CACHE_INPUTS),$(SANITIZER_LIMITED),--modes sanitize,$(pair),--skip-mutants)))

.PHONY: check-frame-initialization check-frame-initialization-budgets check-frame-initialization-sanitize \
	$(addprefix check-frame-initialization-part-,$(PERFCS_RUNTIME_PROFILES)) \
	$(addprefix check-frame-initialization-budgets-part-,$(PERFCS_RUNTIME_PROFILES)) \
	$(addprefix check-frame-initialization-sanitize-part-,$(PERFCS_RUNTIME_PROFILES))
check-frame-initialization: $(addprefix check-frame-initialization-part-,$(PERFCS_RUNTIME_PROFILES))

check-frame-initialization-budgets: $(addprefix check-frame-initialization-budgets-part-,$(PERFCS_RUNTIME_PROFILES))

check-frame-initialization-sanitize: $(addprefix check-frame-initialization-sanitize-part-,$(PERFCS_RUNTIME_PROFILES))

$(foreach pair,$(PERFCS_RUNTIME_PROFILES),$(eval $(call PERFCS_RUNTIME_PROFILE_PIECE,frame-initialization,tests/frame-initialization.py,$(PERFCS_FRAME_INITIALIZATION_INPUTS),$(LIMITED),--modes native --budgets $(PERFCS_GATE_BUDGETS),$(pair),--skip-negative)))
$(foreach pair,$(PERFCS_RUNTIME_PROFILES),$(eval $(call PERFCS_RUNTIME_PROFILE_PIECE,frame-initialization-budgets,tests/frame-initialization.py,$(PERFCS_FRAME_INITIALIZATION_INPUTS),$(LIMITED),--modes native --budgets $(PERFCS_OTHER_BUDGETS),$(pair),--skip-negative)))
$(foreach pair,$(PERFCS_RUNTIME_PROFILES),$(eval $(call PERFCS_RUNTIME_PROFILE_PIECE,frame-initialization-sanitize,tests/frame-initialization.py,$(PERFCS_FRAME_INITIALIZATION_INPUTS),$(SANITIZER_LIMITED),--modes sanitize --activated-matrix full,$(pair),--skip-negative)))

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
