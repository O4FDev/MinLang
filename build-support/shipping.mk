.PHONY: check-shipping
check-shipping: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/shipping.py
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/update-manifest.py
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/update-native.py
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/update-policy.py
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/http-bounded.py

check: check-shipping
check-portable: check-shipping

.PHONY: check-update-bundle check-update-launch check-update-launch-native
check-update-bundle:
	$(LIMITED) python3 tests/update-bundle.py
check-update-launch: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/update-launch.py
check-update-launch-native:
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/update-launch-native.py
check-shipping: check-update-bundle check-update-launch check-update-launch-native
check-sanitize: check-update-launch-native

# Contract checks require Python only. Native credential tests are explicit;
# the harness validates platform, credential context and fresh TEST outputs.
RELEASE_TEST_PYTHON ?= python3
RELEASE_TEST_ENV ?=
RELEASE_PIPELINE_ARGS ?=
.PHONY: check-release-signing check-release-pipeline
check-release-signing:
	$(LIMITED) $(RELEASE_TEST_ENV) "$(RELEASE_TEST_PYTHON)" tests/release-signing.py
check-shipping: check-release-signing
check-release-pipeline:
	$(LIMITED) $(RELEASE_TEST_ENV) "$(RELEASE_TEST_PYTHON)" tests/release-pipeline.py $(RELEASE_PIPELINE_ARGS)
