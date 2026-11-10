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

# One piece per independent invocation group of tests/simulation-cli.min. Every
# piece is its own process, so its `test.scratch()` project (and its target/
# cache) is private; replay groups stay with the run whose output they replay.
SIMULATION_CLI_PARTS = check-simulation-cli-lanterns check-simulation-cli-vault check-simulation-cli-beacons check-simulation-cli-options check-simulation-cli-durable check-simulation-cli-early
.PHONY: $(SIMULATION_CLI_PARTS)
check-simulation-cli: $(SIMULATION_CLI_PARTS)

check-simulation-cli-lanterns: build/tooling/tests/simulation-cli build/tooling/tools/project-cli build/tooling/tools/clang-driver build/minyar-module-build
	+MINYAR_TEST_CLANG="$(TEST_CLANG)" ./build/tooling/tests/simulation-cli --cases lanterns

check-simulation-cli-vault: build/tooling/tests/simulation-cli build/tooling/tools/project-cli build/tooling/tools/clang-driver build/minyar-module-build
	+MINYAR_TEST_CLANG="$(TEST_CLANG)" ./build/tooling/tests/simulation-cli --cases vault

check-simulation-cli-beacons: build/tooling/tests/simulation-cli build/tooling/tools/project-cli build/tooling/tools/clang-driver build/minyar-module-build
	+MINYAR_TEST_CLANG="$(TEST_CLANG)" ./build/tooling/tests/simulation-cli --cases beacons

check-simulation-cli-durable: build/tooling/tests/simulation-cli build/tooling/tools/project-cli build/tooling/tools/clang-driver build/minyar-module-build
	+MINYAR_TEST_CLANG="$(TEST_CLANG)" ./build/tooling/tests/simulation-cli --cases durable

check-simulation-cli-early: build/tooling/tests/simulation-cli build/tooling/tools/project-cli build/tooling/tools/clang-driver build/minyar-module-build
	+MINYAR_TEST_CLANG="$(TEST_CLANG)" ./build/tooling/tests/simulation-cli --cases early

check-simulation-cli-options: build/tooling/tests/simulation-cli build/tooling/tools/project-cli build/tooling/tools/clang-driver build/minyar-module-build
	+MINYAR_TEST_CLANG="$(TEST_CLANG)" ./build/tooling/tests/simulation-cli --cases options

check-determinism-runtime:
	python3 tests/determinism-runtime.py

check check-portable: check-simulation check-simulation-neodb check-simulation-cli check-determinism-runtime
check-sanitize: check-simulation-sanitize

.PHONY: check-example-kvstore
check-example-kvstore: build/minyarc build/minyar-default-runtime.o build/minyar-default-runtime-release.ll build/tooling/tools/project-cli build/tooling/tools/clang-driver build/minyar-module-build
	MINYAR_CLANG="$(LLVM_CC)" python3 "tests/example-kvstore.py"

check check-portable: check-example-kvstore
