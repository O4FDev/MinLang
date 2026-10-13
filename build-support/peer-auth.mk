.PHONY: check-peer-auth check-peer-auth-sanitize check-peer-auth-mutants
check-peer-auth: build/minyarc build/tooling/tests/peer-auth-device-test build/tooling/tests/peer-auth-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/peer-auth-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/peer-auth-device-test

check-peer-auth-sanitize: build/minyarc build/tooling/tests/peer-auth-device-test build/tooling/tests/peer-auth-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/peer-auth-test --sanitize
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/peer-auth-device-test --sanitize

check-peer-auth-mutants: build/minyarc build/tooling/tests/peer-auth-test build/tooling/tests/peer-auth-mutants-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/peer-auth-mutants-test

check check-portable: check-peer-auth
check-sanitize: check-peer-auth-sanitize
