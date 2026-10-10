# Portable networking foundations have their own gates so protocol tests can
# grow without mixing native desktop prerequisites into the portable suite.
.PHONY: check-errors-values check-net check-net-loop check-net-connect check-net-connect-sanitize
check-errors-values: build/minyarc build/minyar-runtime.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/errors-values.py

check-net: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/net-native.py

check-net-loop: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/net-loop.py

check-net-connect: build/minyarc
	MINYAR_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/net-connect.py

check-net-connect-sanitize: build/minyarc
	MINYAR_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/net-connect.py --sanitize

check: check-errors-values check-net check-net-loop check-net-connect
check-portable: check-errors-values check-net check-net-loop check-net-connect
check-sanitize: check-net-connect-sanitize
