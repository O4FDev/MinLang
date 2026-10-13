.PHONY: check-c-layout-records
check-c-layout-records: build/minyarc build/minyar-runtime.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/c-layout-records.py

check check-portable: check-c-layout-records

.PHONY: check-c-layout-records-sanitize
check-c-layout-records-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o
	MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS="$(SANITIZER_FLAGS)" MINYAR_TEST_CLANG="$(LLVM_CC)" $(NATIVE_SANITIZER_ENV) $(SANITIZER_LIMITED) python3 tests/c-layout-records.py

check-sanitize: check-c-layout-records-sanitize
