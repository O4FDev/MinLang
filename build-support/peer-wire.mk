.PHONY: check-peer-wire check-peer-wire-sanitize
check-peer-wire: build/minyarc build/tooling/tests/peer-wire-test build/tooling/tests/peer-wire-flow-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/peer-wire-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/peer-wire-flow-test

check-peer-wire-sanitize: build/minyarc build/tooling/tests/peer-wire-test build/tooling/tests/peer-wire-flow-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/peer-wire-test --sanitize
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/peer-wire-flow-test --sanitize

check check-portable: check-peer-wire
check-sanitize: check-peer-wire-sanitize
