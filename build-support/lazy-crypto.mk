.PHONY: check-lazy-crypto
# Linux programs importing tls/aes load libcrypto on first use; elsewhere the test reports a skip.
check-lazy-crypto: build/minyarc build/tooling/tests/lazy-crypto tests/lazy-crypto/program.min runtime/native/crypto_lazy.c
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/lazy-crypto

check check-portable: check-lazy-crypto
