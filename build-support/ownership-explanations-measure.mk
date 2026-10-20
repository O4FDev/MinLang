.PHONY: measure-ownership-explanations
measure-ownership-explanations: build/minyarc build/minyar-runtime.o build/tooling/tests/ownership-explanations-measure
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "./build/tooling/tests/ownership-explanations-measure"
