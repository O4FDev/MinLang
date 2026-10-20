.PHONY: measure-research
measure-research: build/minyarc build/minyar-runtime.o build/tooling/tests/research-measurements
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "./build/tooling/tests/research-measurements"
