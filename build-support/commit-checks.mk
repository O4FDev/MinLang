# Local feedback; exhaustive corpora, profiles and integration matrices remain
# in the existing complete push/PR gates.
.PHONY: check-core check-commit-core check-commit check-commit-plan install-check-hook check-check-selection check-commit-snapshot

check-core: check-commit-core
check-core check-commit-core: export MINYAR_INTERACTIVE_BOOTSTRAP = 1
check-commit-core: check-smoke check-diagnostics check-conformance check-runtime-unit check-modules build/minyarc build/minyar-runtime.o build/tooling/tests/compiler-behavior
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "./build/tooling/tests/compiler-behavior" --compiler "build/minyarc" --profile core

ifneq ($(wildcard tests/core-modules.min),)
check-commit-core: check-core-modules
endif
ifneq ($(wildcard build-support/nitpick-language.mk),)
check-commit-core: check-nitpick-language
endif
ifneq ($(wildcard build-support/language-ergonomics.mk),)
check-commit-core: check-language-ergonomics
endif

check-commit:
	sh "tools/check-commit.sh"

check-commit-plan:
	sh "tools/check-commit.sh" --plan

install-check-hook:
	sh "tools/install-check-hook.sh"

build/tooling/tools/check-commit.ll build/tooling/tests/check-selection.ll: tools/check-selection.min

check-check-selection: build/tooling/tests/check-selection
	$(LIMITED) "./build/tooling/tests/check-selection"

check-commit-snapshot: build/tooling/tests/commit-snapshot
	$(LIMITED) "./build/tooling/tests/commit-snapshot" "$(CURDIR)/tools/check-commit.sh" "$(CURDIR)/tools/install-check-hook.sh"

ifneq ($(wildcard tests/check-selection.min),)
check check-portable: check-check-selection
endif
ifneq ($(wildcard tests/commit-snapshot.min),)
check check-portable: check-commit-snapshot
endif
