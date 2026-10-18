.PHONY: check-methods check-methods-sanitize
check-methods: build/minyarc build/minyar-runtime.o build/tooling/tests/methods
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/methods

check-methods-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/methods
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/methods

.PHONY: check-record-capabilities check-record-capabilities-sanitize
check-record-capabilities: build/minyarc build/minyar-runtime.o build/tooling/tests/record-capabilities
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/record-capabilities

check-record-capabilities-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/record-capabilities
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/record-capabilities

check check-portable: check-methods check-record-capabilities
check-sanitize: check-methods-sanitize check-record-capabilities-sanitize

.PHONY: check-record-collections check-record-collections-sanitize
check-record-collections: build/minyarc build/minyar-runtime.o build/tooling/tests/record-collections
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "./build/tooling/tests/record-collections"

check-record-collections-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/record-collections
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) "./build/tooling/tests/record-collections"

check check-portable: check-record-collections
check-sanitize: check-record-collections-sanitize

.PHONY: check-method-library check-method-library-sanitize
check-method-library: build/minyarc build/minyar-runtime.o build/tooling/tests/method-library
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "./build/tooling/tests/method-library"

check-method-library-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/method-library
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) "./build/tooling/tests/method-library"

check check-portable: check-method-library
check-sanitize: check-method-library-sanitize
