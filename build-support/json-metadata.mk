.PHONY: check-json-metadata-limits
check-json-metadata-limits: build/tooling/tests/json-metadata-limits.ll build/minyar-runtime.o
	@set -eu; for level in 0 2; do \
		$(LIMITED) "$(LLVM_CC)" -O$$level -Wno-override-module "$<" "build/minyar-runtime.o" -lm -o "build/json-metadata-limits-O$$level"; \
		$(LIMITED) "./build/json-metadata-limits-O$$level"; \
	done

check check-portable: check-json-metadata-limits

.PHONY: check-json-numbers check-json-numbers-sanitize
check-json-numbers: build/minyarc build/minyar-runtime.o build/tooling/tests/json-numbers
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 "tests/json-numbers.py"

check-json-numbers-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/json-numbers
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER="./build/minyarc-sanitize" MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 "tests/json-numbers.py" --sanitize

check check-portable: check-json-numbers
check-sanitize: check-json-numbers-sanitize

.PHONY: check-json-values check-json-values-sanitize
check-json-values: build/minyarc build/minyar-runtime.o build/tooling/tests/json-values
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "./build/tooling/tests/json-values"

check-json-values-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/json-values
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER="./build/minyarc-sanitize" MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) "./build/tooling/tests/json-values"

check check-portable: check-json-values
check-sanitize: check-json-values-sanitize
