build/tooling/tests/update-policy: TOOL_NATIVE = runtime/native/sha256.c
build/tooling/tests/update-policy: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/update-policy: runtime/native/sha256.c
RELEASE_TOOLS = build/tooling/scripts/release build/tooling/tests/shipping
$(RELEASE_TOOLS): TOOL_RUNTIME = build/testing/cycle-runtime.o
$(RELEASE_TOOLS): TOOL_NATIVE = scripts/release-native.c
$(RELEASE_TOOLS): TOOL_LIBS = $(TOOL_CRYPTO)
$(RELEASE_TOOLS): build/testing/cycle-runtime.o scripts/release-native.c
build/tooling/tests/shipping.ll: scripts/release.min tests/release-support.min
.PHONY: check-shipping
check-shipping: build/minyarc build/tooling/tests/http-bounded-test build/tooling/tests/update-native build/tooling/tests/update-policy build/tooling/tests/shipping
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/shipping
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/update-manifest.py
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/update-native
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/update-policy
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/http-bounded-test

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
