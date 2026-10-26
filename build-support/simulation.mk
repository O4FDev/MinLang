.PHONY: check-simulation check-simulation-neodb check-simulation-sanitize check-simulation-cli check-determinism-runtime

check-simulation: build/minyarc build/minyar-runtime.o build/tooling/tests/simulation
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/simulation

check-simulation-neodb: build/minyarc build/minyar-runtime.o build/tooling/tests/simulation-neodb
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/simulation-neodb

check-simulation-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/simulation build/tooling/tests/simulation-neodb
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/simulation
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/simulation-neodb

build/tooling/tests/simulation-cli: TOOL_NATIVE = tools/clang-driver-host.c
build/tooling/tests/simulation-cli: tools/clang-driver-host.c runtime/minyar_native.h

check-simulation-cli: build/tooling/tests/simulation-cli build/tooling/tools/project-cli build/tooling/tools/clang-driver build/minyar-module-build
	+MINYAR_TEST_CLANG="$(TEST_CLANG)" ./build/tooling/tests/simulation-cli

check-determinism-runtime:
	python3 tests/determinism-runtime.py

check check-portable: check-simulation check-simulation-neodb check-simulation-cli check-determinism-runtime
check-sanitize: check-simulation-sanitize
