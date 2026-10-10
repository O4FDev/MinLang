.PHONY: check-peer-wire check-peer-wire-sanitize
check-peer-wire: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/peer-wire.py
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/peer-wire-flow.py

check-peer-wire-sanitize: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/peer-wire.py --sanitize
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/peer-wire-flow.py --sanitize

check check-portable: check-peer-wire
check-sanitize: check-peer-wire-sanitize
