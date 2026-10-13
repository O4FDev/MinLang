.PHONY: check-peer-auth check-peer-auth-sanitize check-peer-auth-mutants
check-peer-auth: build/minyarc build/tooling/tests/peer-auth-device-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/peer-auth.py
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/peer-auth-device-test

check-peer-auth-sanitize: build/minyarc build/tooling/tests/peer-auth-device-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/peer-auth.py --sanitize
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/peer-auth-device-test --sanitize

check-peer-auth-mutants: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/peer-auth-mutants.py

check check-portable: check-peer-auth
check-sanitize: check-peer-auth-sanitize
