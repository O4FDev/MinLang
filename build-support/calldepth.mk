build/calldepth-compiler.min: compiler/build-calldepth-compiler.py compiler/calldepth-compiler.min compiler/build-errors-compiler.py compiler/compiler.min compiler/closure-compiler.min compiler/errors-compiler.min compiler/managed-graphs-adapter.patch scripts/build-closure-compiler.py scripts/build-module-compiler.py | build
	python3 compiler/build-calldepth-compiler.py $@

build/calldepth-compiler-stage1.ll: build/calldepth-compiler.min build/minyarc
	$(LIMITED) ./build/minyarc $< $@

build/calldepth-compiler-stage1: build/calldepth-compiler-stage1.ll build/minyar-compiler-runtime.ll
	$(LIMITED) "$(LLVM_CC)" $(LLVM_FLAGS) $(COMPILER_LTO_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/calldepth-compiler-stage2.ll: build/calldepth-compiler.min build/calldepth-compiler-stage1
	$(LIMITED) ./build/calldepth-compiler-stage1 $< $@

build/minyarc-calldepth: build/calldepth-compiler-stage2.ll build/minyar-compiler-runtime.ll
	$(LIMITED) "$(LLVM_CC)" $(LLVM_FLAGS) $(COMPILER_LTO_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/calldepth-compiler-stage3.ll: build/calldepth-compiler.min build/minyarc-calldepth
	$(LIMITED) ./build/minyarc-calldepth $< $@

.PHONY: check-calldepth check-calldepth-sanitize check-calldepth-profiles check-calldepth-launcher
check-calldepth: build/minyarc-calldepth build/calldepth-compiler-stage3.ll
	cmp build/calldepth-compiler-stage2.ll build/calldepth-compiler-stage3.ll
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/calldepth.py

check-calldepth-sanitize: build/minyarc-calldepth
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/calldepth.py --sanitize --evidence build/calldepth-sanitize-evidence

# Linux evidence gate: native/LTO, fake-stack ASan/UBSan, exact RC/debt,
# 256KiB native stacks, heap policies and all bounded poll budgets.
check-calldepth-profiles: build/minyarc-calldepth
	@set -e; for profile in system fixed lazy eager; do \
	    for budget in 1 32 1024; do \
	        if test "$$profile" = eager && test "$$budget" != 32; then continue; fi; \
	        MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/calldepth.py --profile $$profile --budget $$budget --lto --small-stack --large-dispatch --evidence build/calldepth-$$profile-k$$budget-evidence; \
	        MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/calldepth.py --profile $$profile --budget $$budget --sanitize --small-stack --evidence build/calldepth-$$profile-k$$budget-sanitize-evidence; \
	    done; \
	done

check-calldepth-launcher: build/minyarc-calldepth build/minyarc-errors-request build/minyarc-errors build/minyarc-callbacks build/minyarc-modules build/minyar-module-build $(MANAGED_GRAPH_LAUNCHER_ARTIFACTS)
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/calldepth-launcher.py

check check-portable: check-calldepth check-calldepth-launcher
check-sanitize: check-calldepth-sanitize
