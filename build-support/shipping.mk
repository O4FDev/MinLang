build/tooling/tests/update-policy: TOOL_NATIVE = runtime/native/sha256.c
build/tooling/tests/update-policy: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/update-policy: runtime/native/sha256.c
RELEASE_TOOLS = build/tooling/scripts/release build/tooling/tests/shipping
$(RELEASE_TOOLS): TOOL_RUNTIME = build/testing/cycle-runtime.o
$(RELEASE_TOOLS): TOOL_NATIVE = scripts/release-native.c
$(RELEASE_TOOLS): TOOL_LIBS = $(TOOL_CRYPTO)
$(RELEASE_TOOLS): build/testing/cycle-runtime.o scripts/release-native.c
build/tooling/tests/shipping.ll: scripts/release.min tests/release-support.min
UPDATE_TOOLS = build/tooling/scripts/update-manifest build/tooling/scripts/update-bundle build/tooling/tests/update-manifest build/tooling/tests/update-bundle build/tooling/tests/update-launch
$(UPDATE_TOOLS): TOOL_RUNTIME = build/testing/cycle-runtime.o
$(UPDATE_TOOLS): TOOL_NATIVE = runtime/native/sha256.c scripts/update-support.c
$(UPDATE_TOOLS): TOOL_LIBS = $(TOOL_CRYPTO)
$(UPDATE_TOOLS): build/testing/cycle-runtime.o runtime/native/sha256.c scripts/update-support.c
build/tooling/scripts/update-manifest.ll build/tooling/scripts/update-bundle.ll: scripts/update-support.min
build/tooling/tests/update-manifest.ll: scripts/update-manifest.min scripts/update-support.min
build/tooling/tests/update-bundle.ll: scripts/update-bundle.min scripts/update-support.min tests/release-support.min
build/tooling/tests/update-launch.ll: scripts/update-bundle.min scripts/update-support.min tests/update-launch-support.min tests/release-support.min
build/tooling/tests/update-launch-native: TOOL_NATIVE = runtime/native/sha256.c
build/tooling/tests/update-launch-native: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/update-launch-native: runtime/native/sha256.c
build/tooling/tests/update-launch-native.ll: tests/update-launch-support.min tests/release-support.min
build/tooling/scripts/linux-flatpak: TOOL_NATIVE = runtime/native/sha256.c
build/tooling/scripts/linux-flatpak: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/scripts/linux-flatpak: runtime/native/sha256.c
.PHONY: check-shipping
check-shipping: build/minyarc build/tooling/tests/http-bounded-test build/tooling/tests/update-native build/tooling/tests/update-policy build/tooling/tests/shipping build/tooling/scripts/linux-flatpak build/tooling/tests/update-manifest build/tooling/scripts/update-manifest build/tooling/scripts/update-bundle
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/shipping
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/update-manifest
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/update-native
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/update-policy
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/http-bounded-test

check: check-shipping
check-portable: check-shipping

.PHONY: check-update-bundle check-update-launch check-update-launch-native
check-update-bundle: build/tooling/tests/update-bundle
	$(LIMITED) ./build/tooling/tests/update-bundle
check-update-launch: build/minyarc build/tooling/tests/update-launch
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/update-launch
check-update-launch-native: build/tooling/tests/update-launch-native
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/update-launch-native
check-shipping: check-update-bundle check-update-launch check-update-launch-native
check-sanitize: check-update-launch-native

# Native credential tests are explicit;
# the harness validates platform, credential context and fresh TEST outputs.
RELEASE_TEST_ENV ?=
RELEASE_PIPELINE_ARGS ?=
PIPELINE_TOOLS = build/tooling/tests/release-signing build/tooling/tests/release-pipeline
$(PIPELINE_TOOLS): TOOL_RUNTIME = build/testing/cycle-runtime.o
$(PIPELINE_TOOLS): TOOL_NATIVE = scripts/release-native.c runtime/native/sha256.c scripts/update-support.c
$(PIPELINE_TOOLS): TOOL_LIBS = $(TOOL_CRYPTO)
$(PIPELINE_TOOLS): build/testing/cycle-runtime.o scripts/release-native.c runtime/native/sha256.c scripts/update-support.c
build/tooling/tests/release-pipeline.ll: scripts/release.min scripts/update-bundle.min scripts/update-manifest.min scripts/update-support.min
build/tooling/tests/release-signing.ll: tests/release-pipeline.min scripts/release.min scripts/update-bundle.min scripts/update-manifest.min scripts/update-support.min tests/release-support.min
.PHONY: check-release-signing check-release-pipeline
check-release-signing: build/tooling/tests/release-signing build/tooling/scripts/release
	$(LIMITED) $(RELEASE_TEST_ENV) ./build/tooling/tests/release-signing
check-shipping: check-release-signing
check-release-pipeline: build/tooling/tests/release-pipeline
	$(LIMITED) $(RELEASE_TEST_ENV) ./build/tooling/tests/release-pipeline $(RELEASE_PIPELINE_ARGS)
