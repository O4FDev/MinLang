# Independent Python oracles deliberately live outside the self-hosted compiler.
FUZZ_SEED ?= 0x4D494E
FUZZ_PROGRAMS ?= 8
FUZZ_SIZE ?= 12
FUZZ_REGRESSIONS := $(sort $(wildcard tests/differential-fuzz-regressions/*.json))

build/minyarc-fuzz-stage3: build/compiler-stage3.ll build/minyar-compiler-runtime.ll
	$(LIMITED) "$(LLVM_CC)" $(LLVM_FLAGS) $(COMPILER_LTO_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

.PHONY: check-differential-fuzz-harness check-differential-fuzz-regressions check-differential-fuzz
check-differential-fuzz-harness:
	python3 tests/differential-fuzz-harness.py

check-fuzz: check-differential-fuzz-harness

check-differential-fuzz-regressions: check-differential-fuzz-harness build/minyarc build/minyarc-fuzz-stage3
	python3 tests/differential-fuzz.py --compiler-stage2 "$(CURDIR)/build/minyarc" --compiler-stage3 "$(CURDIR)/build/minyarc-fuzz-stage3" --clang "$(LLVM_CC)" $(foreach regression,$(FUZZ_REGRESSIONS),--replay "$(CURDIR)/$(regression)")

check-differential-fuzz: check-differential-fuzz-regressions
	python3 tests/differential-fuzz.py --compiler-stage2 "$(CURDIR)/build/minyarc" --compiler-stage3 "$(CURDIR)/build/minyarc-fuzz-stage3" --clang "$(LLVM_CC)" --seed "$(FUZZ_SEED)" --programs "$(FUZZ_PROGRAMS)" --size "$(FUZZ_SIZE)"
