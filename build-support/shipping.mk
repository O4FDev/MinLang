.PHONY: check-shipping
check-shipping: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/shipping.py
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/update-manifest.py
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/update-native.py
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/update-policy.py
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/http-bounded.py

check: check-shipping
check-portable: check-shipping
