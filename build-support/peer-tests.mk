PEER_SUITES ?= tests/peer-regressions.py tests/peer-cpp-java-js.py tests/peer-rust-go-zig.py tests/peer-python-swift-ruby-lua.py
PEER_DRIVER_ARTIFACTS = build/minyarc build/minyarc-modules build/minyar-default-runtime.o
# Only the extended Rust/Go/Zig suite exercises the POSIX incremental driver.
ifneq ($(filter tests/peer-rust-go-zig.py,$(PEER_SUITES)),)
PEER_DRIVER_ARTIFACTS += build/minyar-module-build
endif

.PHONY: check-stateful-lists check-stateful-lists-sanitize check-runtime-size-guards check-compiler-allocation-faults check-peer-ownership check-peer-sanitize check-peer-audit-harness check-evidence-harness check-peer-manifest check-peer-regressions check-peer-optimizations check-allocation-faults check-codegen check-reduction-harness

.PHONY: check-list-literals check-list-literals-sanitize check-list-literal-runtime
check-list-literals: build/minyarc build/minyarc-modules build/minyar-runtime.o
	$(LIMITED) python3 tests/list-literals.py

check-list-literals-sanitize: build/minyarc-sanitize build/minyarc-modules-sanitize build/minyar-runtime-sanitize.o
	ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_MODULE_COMPILER=./build/minyarc-modules-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/list-literals.py

check-list-literal-runtime:
	$(SANITIZER_LIMITED) python3 tests/list-literal-runtime.py --clang "$(LLVM_CC)"

check: check-list-literals check-list-literal-runtime
check-sanitize: check-list-literals-sanitize

check-stateful-lists: build/minyarc build/minyar-runtime.o
	MINYAR_TEST_EXTENDED_OPT=1 $(LIMITED) python3 tests/stateful-lists.py

check-stateful-lists-sanitize: build/minyarc-sanitize build/ownership-runtime.o
	ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/stateful-lists.py

check-sanitize: check-stateful-lists-sanitize
check-peer-audit-harness:
	python3 tests/peer-audit-harness.py
	python3 tests/peer-go-domains.py
	python3 tests/peer-zig-domains.py

.PHONY: check-peer-audit check-peer-audit-complete
check-peer-audit: check-peer-audit-harness
	python3 tools/check-peer-audit.py

check-peer-audit-complete: check-peer-audit
	python3 tools/check-peer-audit.py --require-complete

.PHONY: check-suite-catalogue
check-suite-catalogue:
	python3 tests/suite-catalogue.py

.PHONY: check-linux-snapshot
check-linux-snapshot:
	python3 tests/linux-snapshot.py

check check-portable: check-linux-snapshot

.PHONY: check-scalar-cleanup-probes
check-scalar-cleanup-probes:
	$(SANITIZER_LIMITED) python3 tests/scalar-cleanup-probes.py

check: check-scalar-cleanup-probes

check-peer-manifest: check-peer-audit check-suite-catalogue
	python3 tests/peer-manifest.py

check-evidence-harness: build/minyarc build/minyar-runtime.o
	python3 tests/evidence-harness.py

.PHONY: check-performance-metrics
check-performance-metrics:
	python3 tests/performance-metrics.py

check: check-performance-metrics

check-peer-regressions: check-peer-manifest $(PEER_DRIVER_ARTIFACTS) build/minyar-runtime.o
	@test -n "$(strip $(PEER_SUITES))" || { echo "PEER_SUITES must not be empty" >&2; exit 1; }
	@for suite in $(PEER_SUITES); do MINYAR_PEER_GATE=check-peer-regressions $(LIMITED) python3 "$$suite" || exit $$?; done

check-peer-optimizations: check-peer-manifest $(PEER_DRIVER_ARTIFACTS) build/minyar-runtime.o
	@test -n "$(strip $(PEER_SUITES))" || { echo "PEER_SUITES must not be empty" >&2; exit 1; }
	@for suite in $(PEER_SUITES); do MINYAR_PEER_GATE=check-peer-optimizations MINYAR_TEST_EXTENDED_OPT=1 $(LIMITED) python3 "$$suite" || exit $$?; done

check-peer-sanitize: check-peer-manifest $(PEER_DRIVER_ARTIFACTS) build/minyarc-sanitize build/minyar-runtime-sanitize.o
	@test -n "$(strip $(PEER_SUITES))" || { echo "PEER_SUITES must not be empty" >&2; exit 1; }
	@for suite in $(PEER_SUITES); do MINYAR_PEER_GATE=check-peer-sanitize ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 "$$suite" || exit $$?; done

check-peer-ownership: check-peer-manifest $(PEER_DRIVER_ARTIFACTS) build/minyarc-sanitize build/ownership-runtime.o
	MINYAR_PEER_GATE=check-peer-ownership ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/peer-regressions.py \
		PeerRegressions.test_mixed_width_boundary_views_survive_nonsequential_access \
		PeerRegressions.test_self_join_keeps_old_alias_across_growth \
		PeerRegressions.test_ignored_call_result_preserves_live_argument \
		PeerRegressions.test_nested_branch_keeps_text_live_across_join \
		PeerRegressions.test_fresh_allocation_is_consumed_and_dropped_each_iteration \
		PeerRegressions.test_unicode_composition_vectors_indices_slices_and_files \
		PeerRegressions.test_text_equality_compares_bytes_after_nul \
		PeerRegressions.test_loop_sentinels_nested_state_and_dead_inner_loop \
		PeerRegressions.test_owned_condition_temporaries_include_final_false_check \
		PeerRegressions.test_discarded_owned_results_and_temporary_record_arguments \
		PeerRegressions.test_changing_index_short_circuit_loop_and_blank_output \
		PeerRegressions.test_parameterized_nested_list_dimensions_and_cells \
		PeerRegressions.test_identical_mutable_constructor_calls_remain_independent \
		PeerRegressions.test_alternating_retained_and_discarded_large_allocations \
		PeerRegressions.test_record_returns_recursive_results_and_argument_permutations \
		PeerRegressions.test_unicode_width_compositions_and_cached_append_queries \
		PeerRegressions.test_recursive_hanoi_argument_permutation_trace \
		PeerRegressions.test_decimal_and_boolean_text_conversion_widths \
		PeerRegressions.test_nested_text_record_returns_and_field_permutations \
		PeerRegressions.test_prime_filter_pipeline_with_owned_lists \
		PeerRegressions.test_smooth_number_merge_suppresses_duplicate_candidates \
		PeerRegressions.test_returned_text_observes_alias_mutation_without_clobbering_local \
		PeerRegressions.test_record_initializers_evaluate_in_source_order \
		PeerRegressions.test_text_call_arguments_and_concatenations_keep_evaluation_order \
		PeerRegressions.test_previous_space_scanner_all_positions \
		PeerRegressions.test_repeated_sequential_list_shifts_preserve_alias_reads \
		PeerRegressions.test_iteration_rechecks_list_length_after_append \
		PeerRegressions.test_wide_record_construction_preserves_every_field \
		PeerRegressions.test_earlier_text_argument_survives_later_slot_replacement
	MINYAR_PEER_GATE=check-peer-ownership ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/peer-cpp-java-js.py \
		PeerCppJavaJs.test_five_fill_loops_all_1024_lengths \
		PeerCppJavaJs.test_four_stores_reverse_fill_all_cells \
		PeerCppJavaJs.test_hex_digit_fold_mutates_accumulator_in_order \
		PeerCppJavaJs.test_loop_reset_happens_after_accumulating_call \
		PeerCppJavaJs.test_min32_stride_exits_before_second_list_access \
		PeerCppJavaJs.test_point_orientation_keeps_wide_products \
		PeerCppJavaJs.test_twenty_call_results_stay_live_across_nested_call \
		PeerCppJavaJs.test_fresh_record_temporaries_and_returned_list_fields \
		PeerCppJavaJs.test_return_before_infinite_nest_releases_fresh_empty_records \
		PeerCppJavaJs.test_million_element_maximum_guard_preserves_alias_over_100_calls \
		PeerCppJavaJs.test_previous_allocation_escapes_while_latest_list_is_replaced \
		PeerCppJavaJs.test_self_assignment_and_empty_nests_reach_exact_100000_limit \
		PeerCppJavaJs.test_reverse_copy_distinguishes_self_alias_from_independent_destination \
		PeerCppJavaJs.test_joined_mutable_record_slot_keeps_both_branch_stores \
		PeerCppJavaJs.test_loop_mutable_record_slot_keeps_each_sum_and_readonly_field \
		PeerCppJavaJs.test_nested_mutable_record_slots_keep_all_intermediate_values \
		PeerCppJavaJs.test_nested_record_alias_sees_mutated_inner_list_slot \
		PeerCppJavaJs.test_duplicate_nested_record_aliases_share_only_the_inner_slot \
		PeerCppJavaJs.test_persistent_unswitched_loops_keep_all_five_thousand_rounds \
		PeerCppJavaJs.test_mutable_record_branch_and_loop_helpers_return_stored_values \
		PeerCppJavaJs.test_mutable_text_slots_and_repeated_dead_stores_keep_final_fields \
		PeerCppJavaJs.test_sequential_record_slot_stores_and_forwarded_alias_keep_old_loads \
		PeerCppJavaJs.test_in_place_character_tokenizer_returns_shared_input_views \
		PeerCppJavaJs.test_retargeted_alias_postdecrement_keeps_exact_outer_trace \
		PeerCppJavaJs.test_linked_index_scan_keeps_final_null_iteration_and_out_slot \
		PeerCppJavaJs.test_terminated_character_copy_keeps_both_advanced_positions \
		PeerCppJavaJs.test_all_successful_fixed_tails \
		PeerCppJavaJs.test_full_square_domains \
		PeerCppJavaJs.test_full_boolean_fill_domain \
		PeerCppJavaJs.test_full_signed_byte_fill_domain \
		PeerCppJavaJs.test_complete_bmp_single_comment_domain \
		PeerCppJavaJs.test_complete_bmp_block_comment_domain \
		PeerCppJavaJs.test_all_ten_thousand_scaled_quotients \
		PeerCppJavaJs.test_all_successful_matrix_lengths_preserve_collision_order \
		PeerCppJavaJs.test_all_labelled_loop_iterations_and_postincrements \
		PeerCppJavaJs.test_raw_cr_between_every_declaration_token \
		PeerCppJavaJs.test_complete_representable_width_boundary_quotients \
		PeerCppJavaJs.test_full_seeded_long32_int32_applicable_domain \
		PeerCppJavaJs.test_full_seeded_long64_int32_applicable_domain \
		PeerCppJavaJs.test_full_seeded_longlong64_int32_applicable_domain \
		PeerCppJavaJs.test_seeded_char_fill_generator_and_boundary_supplements \
		PeerCppJavaJs.test_seeded_short_fill_generator_and_boundary_supplements \
		PeerCppJavaJs.test_seeded_int_fill_generator_and_boundary_supplements
	MINYAR_PEER_GATE=check-peer-ownership ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/peer-rust-go-zig.py \
		PeerRustGoZig.test_returned_lists_branch_alias_and_fresh_result \
		PeerRustGoZig.test_record_list_literal_helper_and_direct_elements \
		PeerRustGoZig.test_repeated_record_branch_returns_and_original_copy \
		PeerRustGoZig.test_record_alias_chain_and_returned_text_field \
		PeerRustGoZig.test_local_temporary_lists_and_fresh_factory_results \
		PeerRustGoZig.test_list_odd_count_and_cartesian_product_sum \
		PeerRustGoZig.test_nested_boolean_calls_keep_exact_effect_order \
		PeerRustGoZig.test_sort_nonzero_subrange_preserves_outside_cells \
		PeerRustGoZig.test_positive_byte_reversal_population_and_checked_arithmetic \
		PeerRustGoZig.test_ordered_removal_filter_handles_duplicate_indices \
		PeerRustGoZig.test_integer_divisibility_normalization_stops_at_first_remainder \
		PeerRustGoZig.test_decimal_leading_zero_and_malformed_tokens \
		PeerRustGoZig.test_adler_checksum_streaming_integer_workload \
		PeerRustGoZig.test_constant_multiplication_and_distributive_forms \
		PeerRustGoZig.test_dynamic_text_literal_and_pair_dispatch \
		PeerRustGoZig.test_integer_square_root_and_logarithm_workloads \
		PeerRustGoZig.test_overlapping_character_list_moves_preserve_source \
		PeerRustGoZig.test_calendar_epoch_integer_decomposition \
		PeerRustGoZig.test_record_vector_field_access_and_unused_argument_effects \
		PeerRustGoZig.test_nested_integer_division_grouping \
		PeerRustGoZig.test_integer_expression_pressure_and_negated_call \
		PeerRustGoZig.test_mutual_recursion_accumulates_fibonacci_leaves \
		PeerRustGoZig.test_parameter_shadowing_and_independent_literal_lengths \
		PeerRustGoZig.test_list_builtin_argument_order_across_rebinding \
		PeerRustGoZig.test_same_file_import_record_identity_and_recursive_children \
		PeerRustGoZig.test_escaped_character_and_text_index_assignment \
		PeerRustGoZig.test_record_list_assignment_evaluates_index_once \
		PeerRustGoZig.test_record_list_field_store_order_growth_and_types \
		PeerRustGoZig.test_empty_import_driver_cold_warm_and_declaration_transitions \
		PeerRustGoZig.test_append_record_prefix_suffix_and_input_preservation \
		PeerRustGoZig.test_append_scalar_tables_keep_all_elements \
		PeerRustGoZig.test_conditional_results_and_unreached_failure_branches \
		PeerRustGoZig.test_direct_call_parameters_locals_and_self_comparisons \
		PeerRustGoZig.test_direct_record_argument_and_empty_list_return \
		PeerRustGoZig.test_recursive_even_condition_success \
		PeerRustGoZig.test_boolean_phi_complete_truth_tables \
		PeerRustGoZig.test_constant_comparison_loop_complete_traces \
		PeerRustGoZig.test_scalar_absolute_value_source_cases \
		PeerRustGoZig.test_scalar_minimum_maximum_all_source_operands \
		PeerRustGoZig.test_owned_record_swap_keeps_both_original_values \
		PeerRustGoZig.test_zero_iteration_loops_skip_fatal_and_guarded_bodies \
		PeerRustGoZig.test_constant_true_loop_returns_through_nested_helper \
		PeerRustGoZig.test_module_and_local_names_and_nested_record_construction \
		PeerRustGoZig.test_bom_and_crlf_file_contents_are_preserved \
		PeerRustGoZig.test_two_aggregate_results_keep_independent_elements \
		PeerRustGoZig.test_module_call_retains_ignored_large_aggregate_arguments \
		PeerRustGoZig.test_integer_log2_one_below_and_at_power \
		PeerRustGoZig.test_log_integer_generated_boundary_domain \
		PeerRustGoZig.test_log_integer_generated_specialized_comparison_domains \
		PeerRustGoZig.test_repeated_small_decimal_conversions_keep_length_sink \
		PeerRustGoZig.test_boolean_cell_stores_and_comparisons_preserve_all_values \
		PeerRustGoZig.test_character_conversion_returns_owned_four_byte_text \
		PeerRustGoZig.test_empty_list_returned_through_both_helpers \
		PeerRustGoZig.test_singleton_axis_skips_empty_iterator_advance \
		PeerRustGoZig.test_ordered_insertions_append_and_drain \
		PeerRustGoZig.test_owned_wrapper_reclaims_complete_list \
		PeerRustGoZig.test_writer_alias_advances_between_two_writes \
		PeerRustGoZig.test_twenty_text_self_doublings_preserve_every_character \
		PeerRustGoZig.test_space_equality_and_maximum_scalar_conversion \
		PeerRustGoZig.test_global_and_local_character_list_roundtrips \
		PeerRustGoZig.test_file_byte_roundtrips_preserve_valid_and_invalid_utf8 \
		PeerRustGoZig.test_ascii_classes_and_complete_whitespace_scan \
		PeerRustGoZig.test_case_conversion_preserves_full_byte_prefix_and_ownership \
		PeerRustGoZig.test_ascii_comparisons_keep_all_input_bytes \
		PeerRustGoZig.test_ascii_search_keeps_linear_and_boyer_moore_paths \
		PeerRustGoZig.test_ascii_hex_escape_keeps_raw_ff_and_both_charsets \
		PeerRustGoZig.test_for_control_keeps_nested_exit_and_empty_suffix_order \
		PeerRustGoZig.test_for_six_ordered_traversals_and_same_storage_views \
		PeerRustGoZig.test_for_result_helpers_preserve_tags_returns_and_unreached_fallbacks \
		PeerRustGoZig.test_for_mutation_retains_copied_payload_and_distinct_source \
		PeerRustGoZig.test_for_counters_preserve_fixed_offset_and_runtime_starts \
		PeerRustGoZig.test_for_destination_aliases_keep_all_defined_prefix_stores \
		PeerRustGoZig.test_for_inline_value_specializations_keep_both_helper_call_shapes \
		PeerRustGoZig.test_for_tuple_aliases_and_referenced_counters_preserve_all_values \
		PeerRustGoZig.test_unicode_counts_keep_ascii_accented_and_japanese_domains \
		PeerRustGoZig.test_unicode_encoder_reuses_all_four_defined_prefixes \
		PeerRustGoZig.test_unicode_iterators_keep_independent_slice_and_numeric_cursors \
		PeerRustGoZig.test_unicode_peek_preserves_all_eleven_outputs_without_advancing \
		PeerRustGoZig.test_unicode_raw_ingress_preserves_every_malformed_payload_before_validation \
		PeerRustGoZig.test_unicode_scalar_acceptance_keeps_exact_encoded_bytes \
		PeerRustGoZig.test_unicode_single_scalar_decoder_keeps_all_numeric_boundaries \
		PeerRustGoZig.test_unicode_validators_preserve_all_shared_valid_inputs
	MINYAR_PEER_GATE=check-peer-ownership ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/peer-python-swift-ruby-lua.py \
		PeerPythonSwiftRubyLua.test_three_hundred_positional_parameters_and_values \
		PeerPythonSwiftRubyLua.test_five_module_cycle_shapes_and_acyclic_controls \
		PeerPythonSwiftRubyLua.test_python_literal_payloads_match_independent_utf8_files \
		PeerPythonSwiftRubyLua.test_swift_flag_and_mathematical_scalar_literals \
		PeerPythonSwiftRubyLua.test_ruby_quotient_remainder_operand_placements \
		PeerPythonSwiftRubyLua.test_ruby_negation_at_signed32_transition \
		PeerPythonSwiftRubyLua.test_iterative_fibonacci_uses_previous_pair \
		PeerPythonSwiftRubyLua.test_parenthesized_division_and_mixed_unary_precedence \
		PeerPythonSwiftRubyLua.test_utf8_program_arguments_in_c_and_posix_locales \
		PeerPythonSwiftRubyLua.test_ascii_and_empty_scalar_sequence_assembly \
		PeerPythonSwiftRubyLua.test_extreme_integer_relations_all_operand_placements \
		PeerPythonSwiftRubyLua.test_integer_product_expansions_only_when_every_intermediate_fits \
		PeerPythonSwiftRubyLua.test_signed_integer_corpus_decimal_text_conversion \
		PeerPythonSwiftRubyLua.test_ten_five_hundred_and_thousand_positional_arguments \
		PeerPythonSwiftRubyLua.test_filtered_iteration_preserves_present_payload_order \
		PeerPythonSwiftRubyLua.test_text_suffix_candidates_use_scalar_boundaries \
		PeerPythonSwiftRubyLua.test_lua_comparison_results_and_ordinary_recursion_depths \
		PeerPythonSwiftRubyLua.test_empty_semicolons_sibling_scopes_and_typed_shadowing \
		PeerPythonSwiftRubyLua.test_boolean_false_values_and_dense_lengths_zero_through_forty \
		PeerPythonSwiftRubyLua.test_three_hundred_eighty_character_concatenations \
		PeerPythonSwiftRubyLua.test_five_thousand_transient_empty_lists \
		PeerPythonSwiftRubyLua.test_flat_list_literal_preserves_all_263145_positions \
		PeerPythonSwiftRubyLua.test_documented_whitespace_and_raw_nul_literal \
		PeerPythonSwiftRubyLua.test_four_line_endings_keep_documented_diagnostic_positions \
		PeerPythonSwiftRubyLua.test_supported_syntax_depth_shapes_and_controlled_limits \
		PeerPythonSwiftRubyLua.test_integer_total_order_1001_and_1002 \
		PeerPythonSwiftRubyLua.test_euclidean_gcd_full_signed_one_through_nineteen_domain \
		PeerPythonSwiftRubyLua.test_uppercase_true_is_an_identifier \
		PeerPythonSwiftRubyLua.test_five_ordinary_quote_payloads \
		PeerPythonSwiftRubyLua.test_four_if_chain_shapes \
		PeerPythonSwiftRubyLua.test_six_unparenthesized_boolean_expressions \
		PeerPythonSwiftRubyLua.test_comparison_result_and_all_six_branch_forms \
		PeerPythonSwiftRubyLua.test_all_additive_and_multiplicative_expression_shapes \
		PeerPythonSwiftRubyLua.test_ascii_codepoints_form_complete_numeric_scalar_list \
		PeerPythonSwiftRubyLua.test_binary_enumerator_size_uses_bytes_for_all_three_inputs \
		PeerPythonSwiftRubyLua.test_exact_prefix_removal_values \
		PeerPythonSwiftRubyLua.test_exact_suffix_removal_values \
		PeerPythonSwiftRubyLua.test_ordinary_positional_calls_keep_repetitions_and_trailing_commas \
		PeerPythonSwiftRubyLua.test_one_positional_parameter_declaration_accepts_trailing_comma \
		PeerPythonSwiftRubyLua.test_bare_and_integer_returns_keep_actual_callers \
		PeerPythonSwiftRubyLua.test_parenthesized_integer_and_all_three_plain_list_atoms \
		PeerPythonSwiftRubyLua.test_all_nine_text_selectors_keep_relative_indices_and_omitted_bounds \
		PeerPythonSwiftRubyLua.test_indexed_list_literal_keeps_the_outer_list \
		PeerPythonSwiftRubyLua.test_sliced_list_literal_keeps_both_collection_levels \
		PeerPythonSwiftRubyLua.test_reference_self_assignment_preserves_all_specialized_set_values \
		PeerPythonSwiftRubyLua.test_invalid_a1_and_c2_preserve_raw_ingress_and_complete_byte_roundtrip \
		PeerPythonSwiftRubyLua.test_missing_nonnegative_clipped_substring_matrix \
		PeerPythonSwiftRubyLua.test_utf8_constructor_value_projections_keep_complete_bytes \
		PeerPythonSwiftRubyLua.test_valid_scalar_lengths_and_numeric_character_reads

check-allocation-faults: build/minyarc
	$(SANITIZER_LIMITED) python3 tests/allocation-faults.py

check-runtime-size-guards:
	$(SANITIZER_LIMITED) python3 tests/runtime-size-guards.py

check-compiler-allocation-faults: build/minyarc build/compiler-stage2.ll build/minyar-runtime.o
	$(SANITIZER_LIMITED) python3 tests/allocation-faults.py --scope compiler --output build/compiler-allocation-faults.json

check-codegen: build/minyarc
	$(LIMITED) python3 tests/codegen.py

check-reduction-harness: build/minyarc build/minyar-runtime.o
	$(LIMITED) python3 tests/reduction-harness.py

check: check-evidence-harness check-peer-regressions check-allocation-faults check-compiler-allocation-faults check-runtime-size-guards check-reduction-harness

.PHONY: check-statement-nesting check-statement-nesting-sanitize check-statement-nesting-ownership
check-statement-nesting: build/minyarc build/minyarc-modules build/minyar-runtime.o
	$(LIMITED) python3 tests/statement-nesting.py

check-statement-nesting-sanitize: build/minyarc-sanitize build/minyarc-modules-sanitize build/minyar-runtime-sanitize.o
	ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_MODULE_COMPILER=./build/minyarc-modules-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/statement-nesting.py

check-statement-nesting-ownership: build/minyarc-sanitize build/minyarc-modules-sanitize build/ownership-runtime.o
	ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_MODULE_COMPILER=./build/minyarc-modules-sanitize MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/statement-nesting.py StatementNesting.test_moderate_scopes_loops_and_owned_results StatementNesting.test_imported_nested_scopes_and_owned_returns

check-portable: check-statement-nesting
check-sanitize: check-statement-nesting-sanitize
check-ownership: check-statement-nesting-ownership


check-fuzz: check-stateful-lists
check-portable: check-evidence-harness check-peer-regressions
check-ownership: check-peer-ownership
