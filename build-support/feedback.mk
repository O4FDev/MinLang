# Focused inner-loop entry points; the complete gates retain every case.
FUZZ_STAGES = expressions language semantic hostile regressions seeds modules
FUZZ_STAGE_CHECKS = $(addprefix check-fuzz-,$(FUZZ_STAGES))
.PHONY: $(FUZZ_STAGE_CHECKS) check-regressions-case

$(FUZZ_STAGE_CHECKS): build/minyarc build/minyar-runtime.o build/tooling/tests/fuzz
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/fuzz --stage $(patsubst check-fuzz-%,%,$@)

check-regressions-case: build/minyarc build/minyar-runtime.o build/tooling/tests/regressions
	@test -n "$(CHECK_REGRESSION_CASE)" || { printf '%s\n' 'Set CHECK_REGRESSION_CASE to a case name from tests/regressions.min'; exit 2; }
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/regressions "$(CHECK_REGRESSION_CASE)"
