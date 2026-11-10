.PHONY: check-llvm-lint

# LLVM's verifier and Lint pass over the IR the compiler emits for real programs, linked with the release runtime IR,
# as emitted and after O2 (tools/llvm-lint.py). Catches false claims to LLVM: call-site ABI attributes that differ from
# the definition, signature mismatches with the C runtime, misaligned or null accesses the optimizer exposes.
LLVM_LINT_PROGRAMS = $(sort $(wildcard benchmarks/compare/*/main.min) $(wildcard tests/codegen/*.min) \
	$(wildcard tests/miscompiles/*.min) $(wildcard tests/runtime/*.min))

check-llvm-lint: build/minyarc build/minyar-default-runtime-release.ll tools/llvm-lint.py
	$(LIMITED) python3 tools/llvm-lint.py $(LLVM_LINT_PROGRAMS)

check check-portable: check-llvm-lint
