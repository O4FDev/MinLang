.PHONY: check-peer-auth check-peer-auth-sanitize check-peer-auth-mutants
check-peer-auth: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/peer-auth.py
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/peer-auth-device.py

check-peer-auth-sanitize: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/peer-auth.py --sanitize
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/peer-auth-device.py --sanitize

check-peer-auth-mutants: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/peer-auth-mutants.py

check check-portable: check-peer-auth
check-sanitize: check-peer-auth-sanitize
