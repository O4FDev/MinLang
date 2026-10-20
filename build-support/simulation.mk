.PHONY: check-simulation check-simulation-neodb check-simulation-sanitize

check-simulation: build/minyarc build/minyar-runtime.o build/tooling/tests/simulation
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/simulation

check-simulation-neodb: build/minyarc build/minyar-runtime.o build/tooling/tests/simulation-neodb
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/simulation-neodb

check-simulation-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/simulation build/tooling/tests/simulation-neodb
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/simulation
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/simulation-neodb

check check-portable: check-simulation check-simulation-neodb
check-sanitize: check-simulation-sanitize
