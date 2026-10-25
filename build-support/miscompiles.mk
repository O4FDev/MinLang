.PHONY: check-miscompiles

# tests/miscompiles/*.min must print their .stdout at -O0, -O1 and -O2; the harness also checks the
# Boolean return ABI (zeroext call sites reach zeroext definitions) in each fixture and in the compiler's own IR.
check-miscompiles: build/minyarc build/minyar-runtime.o build/compiler-stage2.ll build/tooling/tests/miscompiles $(wildcard tests/miscompiles/*)
	MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_MISCOMPILE_SELF_IR=build/compiler-stage2.ll $(LIMITED) ./build/tooling/tests/miscompiles

check check-portable: check-miscompiles
