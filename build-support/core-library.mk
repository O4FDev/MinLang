.PHONY: check-octal-literals check-octal-literals-sanitize check-reserved-names check-reserved-names-sanitize

check-octal-literals: build/minyarc build/minyar-runtime.o build/tooling/tests/octal-literals
	$(LIMITED) ./build/tooling/tests/octal-literals

check-octal-literals-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/octal-literals
	$(SANITIZER_LIMITED) env MINYAR_TEST_COMPILER=build/minyarc-sanitize MINYAR_TEST_RUNTIME=build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS="$(SANITIZER_FLAGS)" ./build/tooling/tests/octal-literals

check-reserved-names: build/minyarc build/minyar-runtime.o build/tooling/tests/reserved-names
	$(LIMITED) ./build/tooling/tests/reserved-names

check-reserved-names-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/reserved-names
	$(SANITIZER_LIMITED) env MINYAR_TEST_COMPILER=build/minyarc-sanitize MINYAR_TEST_RUNTIME=build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS="$(SANITIZER_FLAGS)" ./build/tooling/tests/reserved-names

.PHONY: check-module-constants check-module-constants-sanitize check-module-constant-graphs check-module-constant-graphs-sanitize
check-module-constants: build/minyarc build/minyar-runtime.o build/tooling/tests/module-constants
	$(LIMITED) ./build/tooling/tests/module-constants

check-module-constants-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/module-constants
	$(SANITIZER_LIMITED) env MINYAR_TEST_COMPILER=build/minyarc-sanitize MINYAR_TEST_RUNTIME=build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS="$(SANITIZER_FLAGS)" ./build/tooling/tests/module-constants

check-module-constant-graphs: build/minyarc build/minyarc-callbacks build/tooling/tests/module-constant-graphs
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/module-constant-graphs

check-module-constant-graphs-sanitize: build/minyarc-sanitize build/minyarc-callbacks-sanitize build/tooling/tests/module-constant-graphs
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/module-constant-graphs

check check-portable: check-octal-literals check-reserved-names check-module-constants check-module-constant-graphs
check-sanitize: check-octal-literals-sanitize check-reserved-names-sanitize check-module-constants-sanitize check-module-constant-graphs-sanitize

.PHONY: check-collections-integration check-collections-integration-sanitize
check-collections-integration: build/minyarc build/minyarc-callbacks build/minyar-runtime.o build/tooling/tests/collections-integration
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/collections-integration
check-collections-integration-sanitize: build/minyarc-sanitize build/minyarc-callbacks-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/collections-integration
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/collections-integration
check check-portable: check-collections-integration
check-sanitize: check-collections-integration-sanitize

ifeq ($(filter Windows_NT,$(OS))$(filter MSYS% MINGW% CYGWIN%,$(shell uname -s)),)
.PHONY: check-feature-declarations-incremental check-feature-declarations-incremental-sanitize
check-feature-declarations-incremental: build/minyarc-modules build/minyar-module-build build/minyar-runtime.o build/tooling/tests/feature-declarations-incremental
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/feature-declarations-incremental
check-feature-declarations-incremental-sanitize: build/minyarc-modules-sanitize build/minyar-module-build-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/feature-declarations-incremental
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/feature-declarations-incremental
check check-portable: check-feature-declarations-incremental
check-sanitize: check-feature-declarations-incremental-sanitize
endif
