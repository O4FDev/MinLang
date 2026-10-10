# Portable networking foundations have their own gates so protocol tests can
# grow without mixing native desktop prerequisites into the portable suite.
.PHONY: check-errors-values check-net check-net-loop
check-errors-values: build/minyarc build/minyar-runtime.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/errors-values.py

check-net: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/net-native.py

check-net-loop: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/net-loop.py

check: check-errors-values check-net check-net-loop
check-portable: check-errors-values check-net check-net-loop
