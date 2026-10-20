.PHONY: check-scope-ownership check-scope-ownership-sanitize check-scope-fixed-point

build/tooling/tests/scope-ownership: tests/frontend-fixtures.min tools/test-runtime.min
build/tooling/tests/scope-ownership.ll: tests/choice-composition-cycle.min tests/choice-composition-cycle.expected tests/choice-container-niche.min tests/choice-container-niche.expected
build/tooling/tests/scope-ownership.ll: tests/choice-scalar-niche-bench.min

SCOPE_LAUNCHER_ARTIFACTS = build/minyarc build/minyarc-modules build/minyar-module-build build/tooling/tools/clang-driver build/minyar-runtime-eager.o build/minyar-runtime-eager-release.ll

check-scope-ownership: $(SCOPE_LAUNCHER_ARTIFACTS) build/tooling/tests/scope-ownership
	+MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/scope-ownership

check-scope-ownership-sanitize: $(SCOPE_LAUNCHER_ARTIFACTS) build/minyarc-sanitize build/tooling/tests/scope-ownership
	+MINYAR_TEST_COMPILER="./build/minyarc-sanitize" MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/scope-ownership

build/scope-compiler-stage2.ll: build/compiler.min build/minyarc
	$(LIMITED) ./build/minyarc $< $@ --library library --scope-owners

build/scope-compiler: build/scope-compiler-stage2.ll build/minyar-compiler-runtime.ll
	$(LIMITED) "$(LLVM_CC)" $(LLVM_FLAGS) $(COMPILER_LTO_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/scope-compiler-stage3.ll: build/compiler.min build/scope-compiler
	$(LIMITED) ./build/scope-compiler $< $@ --library library --scope-owners

check-scope-fixed-point: build/scope-compiler-stage2.ll build/scope-compiler-stage3.ll
	cmp build/scope-compiler-stage2.ll build/scope-compiler-stage3.ll

check check-portable: check-scope-ownership check-scope-fixed-point
check-sanitize check-ownership: check-scope-ownership-sanitize
