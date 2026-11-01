.PHONY: check-scope-ownership check-scope-ownership-sanitize check-scope-fixed-point

build/tooling/tests/scope-ownership.ll: tests/frontend-fixtures.min tools/test-runtime.min
build/tooling/tests/scope-ownership.ll: tests/choice-composition-cycle.min tests/choice-composition-cycle.expected tests/choice-container-niche.min tests/choice-container-niche.expected
build/tooling/tests/scope-ownership.ll: tests/choice-scalar-niche-bench.min

SCOPE_LAUNCHER_ARTIFACTS = build/minyarc build/minyarc-modules build/minyar-module-build build/tooling/tools/clang-driver build/minyar-runtime-eager.o build/minyar-runtime-eager-release.ll

# The 26 harness tests are independent `fixtures.selected` blocks, so four pieces
# name disjoint groups of ScopeOwnership tests on the command line. The lone
# launcher test and the two heaviest fixtures get their own piece.
SCOPE_OWNERSHIP_LAUNCHER = test_eager_launcher_selects_scope_owners
SCOPE_OWNERSHIP_RECOVERY = test_empty_scopes_finish_recovery_without_losing_roots
SCOPE_OWNERSHIP_UNWIND = test_module_state_replay_lowers_cached_owners test_temporary_cells_reuse_only_disjoint_cfg_ranges test_projected_borrows_publish_one_lasting_owner test_bounded_scope_cleanup_points_fit_the_budget
SCOPE_OWNERSHIP_CORE = test_direct_owners_and_borrowed_parameter_moves test_condition_owners_on_both_branches test_loop_false_exit_break_continue_and_nested_loops test_early_return_and_try_cleanup test_aliases_survive_later_argument_mutation test_escaping_closure_and_cycle_owners test_repeated_and_nested_diagnostic_unwind test_large_function_keeps_legacy_fallback test_scope_modes_and_private_symbols test_mixed_scoped_and_legacy_diagnostic_unwind test_recoverable_call_depth_cleans_scope_owners test_large_cycle_drains_at_final_scope test_plain_borrows_share_local_and_return_owners test_comparison_borrows_have_no_later_uses test_comparison_borrow_ssa_boundaries test_allocating_text_read_borrows_keep_parent_owners test_choice_composition_cycle_scope_owners test_choice_container_niche_scope_owners test_choice_scalar_niche_scope_owners test_stable_field_paths_borrow_without_cells
SCOPE_OWNERSHIP_PARTS = check-scope-ownership-launcher check-scope-ownership-recovery check-scope-ownership-unwind check-scope-ownership-core
.PHONY: $(SCOPE_OWNERSHIP_PARTS)
check-scope-ownership: $(SCOPE_OWNERSHIP_PARTS)

check-scope-ownership-launcher: $(SCOPE_LAUNCHER_ARTIFACTS) build/tooling/tests/scope-ownership
	+MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/scope-ownership $(addprefix ScopeOwnership.,$(SCOPE_OWNERSHIP_LAUNCHER))

check-scope-ownership-recovery: $(SCOPE_LAUNCHER_ARTIFACTS) build/tooling/tests/scope-ownership
	+MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/scope-ownership $(addprefix ScopeOwnership.,$(SCOPE_OWNERSHIP_RECOVERY))

check-scope-ownership-unwind: $(SCOPE_LAUNCHER_ARTIFACTS) build/tooling/tests/scope-ownership
	+MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/scope-ownership $(addprefix ScopeOwnership.,$(SCOPE_OWNERSHIP_UNWIND))

check-scope-ownership-core: $(SCOPE_LAUNCHER_ARTIFACTS) build/tooling/tests/scope-ownership
	+MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/scope-ownership $(addprefix ScopeOwnership.,$(SCOPE_OWNERSHIP_CORE))

check-scope-ownership-sanitize: $(SCOPE_LAUNCHER_ARTIFACTS) build/minyarc-sanitize build/tooling/tests/scope-ownership
	+MINYAR_TEST_COMPILER="./build/minyarc-sanitize" MINYAR_TEST_CLANG="$(TEST_CLANG)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/scope-ownership

build/scope-compiler-stage2.ll: build/compiler.min build/minyarc
	$(LIMITED) ./build/minyarc $< $@ --library library --scope-owners

build/scope-compiler: build/scope-compiler-stage2.ll build/minyar-compiler-runtime.ll tools/compiler-link.sh
	$(LIMITED) sh tools/compiler-link.sh "$(LLVM_CC)" $(LLVM_FLAGS) $(COMPILER_LTO_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/scope-compiler-stage3.ll: build/compiler.min build/scope-compiler
	$(LIMITED) ./build/scope-compiler $< $@ --library library --scope-owners

check-scope-fixed-point: build/scope-compiler-stage2.ll build/scope-compiler-stage3.ll
	cmp build/scope-compiler-stage2.ll build/scope-compiler-stage3.ll

check check-portable: check-scope-ownership check-scope-fixed-point
check-sanitize check-ownership: check-scope-ownership-sanitize
