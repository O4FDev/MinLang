.PHONY: check-calldepth check-calldepth-sanitize check-calldepth-profiles check-calldepth-launcher check-calldepth-reporting check-calldepth-reporting-sanitize check-calldepth-hooks check-calldepth-hooks-sanitize
build/tooling/tests/calldepth: TOOL_NATIVE = tests/sha256-test-native.c
build/tooling/tests/calldepth: TOOL_LIBS = -lcrypto
build/tooling/tests/calldepth: tests/sha256-test-native.c
check-calldepth: build/minyarc-calldepth build/calldepth-compiler-stage3.ll build/minyar-runtime.o build/tooling/tests/calldepth
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/compiler-behavior.py --profile calldepth --ir build/calldepth-compiler-stage3.ll
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/calldepth

check-calldepth-sanitize: build/minyarc-calldepth build/tooling/tests/calldepth
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/calldepth --sanitize --evidence build/calldepth-sanitize-evidence

# Linux evidence gate: native/LTO, fake-stack ASan/UBSan, exact RC/debt,
# 256KiB native stacks, heap policies and all bounded poll budgets.
# Each profile/budget/flavour is its own check. The Minyar IR depends only on
# the budget, so it is compiled once per budget; heap profile, optimisation
# mode and sanitizer flags all apply when the cached IR is linked. The C
# fixtures and dispatch control take no profile or budget, so they run once.
CALLDEPTH_PROFILES = system-k1 system-k32 system-k1024 fixed-k1 fixed-k32 fixed-k1024 lazy-k1 lazy-k32 lazy-k1024 eager-k32
CALLDEPTH_PROFILE_CHECKS = check-calldepth-profile-fixtures check-calldepth-profile-fixtures-sanitize \
    $(foreach combination,$(CALLDEPTH_PROFILES),check-calldepth-profile-$(combination) check-calldepth-profile-$(combination)-sanitize)
CALLDEPTH_IR_INPUTS = build/minyarc-calldepth tests/calldepth.min $(wildcard tests/calldepth/*.min) $(wildcard library/*.min)

define calldepth_ir_rule
build/calldepth-ir-k$(1)/manifest.json: $$(CALLDEPTH_IR_INPUTS) build/tooling/tests/calldepth
	$$(LIMITED) ./build/tooling/tests/calldepth --budget $(1) --large-dispatch --emit-ir build/calldepth-ir-k$(1)
endef
$(foreach budget,1 32 1024,$(eval $(call calldepth_ir_rule,$(budget))))

define calldepth_profile_rule
check-calldepth-profile-$(1)-k$(2): build/minyarc-calldepth build/calldepth-ir-k$(2)/manifest.json build/tooling/tests/calldepth
	MINYAR_TEST_CLANG="$$(LLVM_CC)" $$(LIMITED) ./build/tooling/tests/calldepth --profile $(1) --budget $(2) --lto --small-stack --large-dispatch --fixtures skip --ir-cache build/calldepth-ir-k$(2) --evidence build/calldepth-$(1)-k$(2)-evidence
check-calldepth-profile-$(1)-k$(2)-sanitize: build/minyarc-calldepth build/calldepth-ir-k$(2)/manifest.json build/tooling/tests/calldepth
	MINYAR_TEST_CLANG="$$(LLVM_CC)" $$(SANITIZER_LIMITED) ./build/tooling/tests/calldepth --profile $(1) --budget $(2) --sanitize --small-stack --fixtures skip --ir-cache build/calldepth-ir-k$(2) --evidence build/calldepth-$(1)-k$(2)-sanitize-evidence
endef
$(foreach combination,$(CALLDEPTH_PROFILES),$(eval $(call calldepth_profile_rule,$(firstword $(subst -k, ,$(combination))),$(lastword $(subst -k, ,$(combination))))))

check-calldepth-profile-fixtures: build/minyarc build/minyarc-calldepth build/tooling/tests/calldepth
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/calldepth --fixtures only --large-dispatch --evidence build/calldepth-profile-fixtures-evidence
check-calldepth-profile-fixtures-sanitize: build/minyarc-calldepth build/tooling/tests/calldepth
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/calldepth --fixtures only --sanitize --evidence build/calldepth-profile-fixtures-sanitize-evidence

.PHONY: $(CALLDEPTH_PROFILE_CHECKS)
check-calldepth-profiles: $(CALLDEPTH_PROFILE_CHECKS)

check-calldepth-launcher: build/minyarc-calldepth build/minyarc-errors-request build/minyarc-errors build/minyarc-callbacks build/minyarc-modules build/minyar-module-build $(MANAGED_GRAPH_LAUNCHER_ARTIFACTS) build/tooling/tests/calldepth-launcher
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/calldepth-launcher

check-calldepth-reporting: build/minyarc-calldepth build/tooling/tests/calldepth
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/calldepth --case reporting-global --max-depth 2 --evidence build/calldepth-global-evidence
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/calldepth --case reporting-fallback --fallback-depth 16 --evidence build/calldepth-fallback-evidence

check-calldepth-reporting-sanitize: build/minyarc-calldepth build/tooling/tests/calldepth
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/calldepth --case reporting-global --max-depth 2 --sanitize --evidence build/calldepth-global-sanitize-evidence
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/calldepth --case reporting-fallback --fallback-depth 16 --sanitize --evidence build/calldepth-fallback-sanitize-evidence

check-calldepth-hooks: build/minyarc build/minyarc-modules build/minyar-module-build build/minyar-default-runtime.o build/tooling/tests/calldepth-hooks
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/calldepth-hooks

check-calldepth-hooks-sanitize: build/minyarc build/minyarc-modules build/minyar-module-build build/minyar-default-runtime.o build/tooling/tests/calldepth-hooks
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/calldepth-hooks --sanitize --evidence build/calldepth-hook-sanitize-evidence

# Recovery is qualified on Linux and macOS; native Windows linking of the test hooks is not yet.
ifeq ($(filter Windows_NT,$(OS))$(filter MSYS% MINGW% CYGWIN%,$(shell uname -s)),)
check check-portable: check-calldepth check-calldepth-launcher check-calldepth-reporting check-calldepth-hooks
check-sanitize: check-calldepth-sanitize check-calldepth-reporting-sanitize check-calldepth-hooks-sanitize
endif
