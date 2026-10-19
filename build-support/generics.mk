.PHONY: check-generics check-generics-sanitize check-generics-smoke

check-generics-smoke: build/minyarc build/minyar-runtime.o build/tooling/tests/generics-smoke
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/generics-smoke

check-generics: build/minyarc build/minyar-runtime.o build/tooling/tests/generics build/tooling/tests/generics-records build/tooling/tests/generic-literals
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/generics
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/generics-records
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/generic-literals

check-generics-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/generics build/tooling/tests/generics-records build/tooling/tests/generic-literals
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/generics
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/generics-records
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/generic-literals

check check-portable: check-generics
check-sanitize: check-generics-sanitize

.PHONY: check-generic-aliases check-generic-aliases-sanitize
check-generic-aliases: build/minyarc build/minyar-runtime.o build/tooling/tests/generic-aliases
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/generic-aliases

check-generic-aliases-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/generic-aliases
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/generic-aliases

check check-portable: check-generic-aliases
check-sanitize: check-generic-aliases-sanitize
