check check-portable: check-patterns
check-sanitize: check-patterns-sanitize

# The core declaration remains ordinary Minyar source; embedding avoids a runtime
# dependency on the compiler's working directory or a particular library path.
build/choice-builtins.min: library/maybe.min build-support/choice-prelude.awk | build
	@set -e; temporary=$$(mktemp "$@.tmp.XXXXXXXX"); \
	trap 'rm -f "$$temporary"' 0; \
	awk -f "build-support/choice-prelude.awk" "$<" > "$$temporary"; \
	if ! test -f "$@" || ! cmp -s "$$temporary" "$@"; then mv "$$temporary" "$@"; fi

.PHONY: check-choice-identifiers check-choice-smoke check-choice check-choice-sanitize check-choice-library check-choice-library-sanitize

.PHONY: check-patterns check-patterns-sanitize

check-patterns: build/minyarc build/minyar-runtime.o build/tooling/tests/patterns
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "./build/tooling/tests/patterns"

check-patterns-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/patterns
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER="./build/minyarc-sanitize" MINYAR_TEST_RUNTIME="./build/minyar-runtime-sanitize.o" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) "./build/tooling/tests/patterns"

check-choice-identifiers: build/minyarc build/minyar-runtime.o build/tooling/tests/choice-identifiers
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "./build/tooling/tests/choice-identifiers"


check-choice-smoke: build/minyarc build/minyar-runtime.o build/testing/cycle-runtime.o build/tooling/tests/choice-smoke
	MINYAR_TEST_RUNTIME="./build/testing/cycle-runtime.o" MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "./build/tooling/tests/choice-smoke"


check-choice: build/minyarc build/minyar-runtime.o build/tooling/tests/choice
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "./build/tooling/tests/choice"

check-choice-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/choice
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER="./build/minyarc-sanitize" MINYAR_TEST_RUNTIME="./build/minyar-runtime-sanitize.o" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) "./build/tooling/tests/choice"

check-choice-library: build/minyarc build/minyar-runtime.o build/tooling/tests/choice-library
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "./build/tooling/tests/choice-library"

check-choice-library-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/choice-library
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER="./build/minyarc-sanitize" MINYAR_TEST_RUNTIME="./build/minyar-runtime-sanitize.o" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) "./build/tooling/tests/choice-library"

.PHONY: check-choice-layout check-choice-layout-sanitize
check-choice-layout: build/minyarc build/minyar-runtime.o build/tooling/tests/choice-layout-check
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "./build/tooling/tests/choice-layout-check"

check-choice-layout-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/choice-layout-check
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER="./build/minyarc-sanitize" MINYAR_TEST_RUNTIME="./build/minyar-runtime-sanitize.o" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) "./build/tooling/tests/choice-layout-check"

.PHONY: check-choice-niche check-choice-niche-sanitize
check-choice-niche: build/minyarc build/minyar-runtime.o build/tooling/tests/choice-niche-check
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "./build/tooling/tests/choice-niche-check"

check-choice-niche-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/choice-niche-check
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER="./build/minyarc-sanitize" MINYAR_TEST_RUNTIME="./build/minyar-runtime-sanitize.o" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) "./build/tooling/tests/choice-niche-check"

.PHONY: check-choice-propagation check-choice-propagation-sanitize
check-choice-propagation: build/minyarc build/minyar-runtime.o build/tooling/tests/choice-propagation-check
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "./build/tooling/tests/choice-propagation-check"

check-choice-propagation-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/choice-propagation-check
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER="./build/minyarc-sanitize" MINYAR_TEST_RUNTIME="./build/minyar-runtime-sanitize.o" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) "./build/tooling/tests/choice-propagation-check"

.PHONY: check-choice-enums check-choice-enums-sanitize
check-choice-enums: build/minyarc build/minyar-runtime.o build/tooling/tests/choice-enums
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "./build/tooling/tests/choice-enums"

check-choice-enums-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/choice-enums
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER="./build/minyarc-sanitize" MINYAR_TEST_RUNTIME="./build/minyar-runtime-sanitize.o" MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) "./build/tooling/tests/choice-enums"

.PHONY: check-choice-text-niche check-choice-text-niche-sanitize
check-choice-text-niche: build/minyarc build/minyar-runtime.o build/tooling/tests/choice-text-niche-check
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "./build/tooling/tests/choice-text-niche-check"

check-choice-text-niche-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/choice-text-niche-check
	ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 MINYAR_TEST_COMPILER="./build/minyarc-sanitize" MINYAR_TEST_RUNTIME="./build/minyar-runtime-sanitize.o" MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) "./build/tooling/tests/choice-text-niche-check"

check check-portable: check-choice check-choice-library check-choice-layout check-choice-niche check-choice-propagation check-choice-enums check-choice-text-niche
check-sanitize: check-choice-sanitize check-choice-library-sanitize check-choice-layout-sanitize check-choice-niche-sanitize check-choice-propagation-sanitize check-choice-enums-sanitize check-choice-text-niche-sanitize
