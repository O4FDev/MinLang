.PHONY: check-constant-tables check-constant-tables-sanitize

check-constant-tables: build/minyarc build/minyar-runtime.o build/tooling/tests/constant-tables
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/constant-tables

check-constant-tables-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/constant-tables
	MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS="$(filter-out -O%,$(SANITIZER_FLAGS))" $(NATIVE_SANITIZER_ENV) $(SANITIZER_LIMITED) ./build/tooling/tests/constant-tables

check check-portable: check-constant-tables
check-sanitize: check-constant-tables-sanitize

ifneq ($(OS),Windows_NT)
check-constant-tables check-constant-tables-sanitize: build/minyar-module-build
endif
