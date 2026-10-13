.PHONY: check-c-layout-records
build/tooling/tests/c-layout-records: build/tooling/tools/clang-driver
check-c-layout-records: build/minyarc build/minyar-runtime.o build/tooling/tests/c-layout-records build/tooling/tools/clang-driver
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/c-layout-records

check check-portable: check-c-layout-records

.PHONY: check-c-layout-records-sanitize
check-c-layout-records-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/c-layout-records build/tooling/tools/clang-driver
	MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS="$(SANITIZER_FLAGS)" MINYAR_TEST_CLANG="$(LLVM_CC)" $(NATIVE_SANITIZER_ENV) $(SANITIZER_LIMITED) ./build/tooling/tests/c-layout-records

check-sanitize: check-c-layout-records-sanitize
