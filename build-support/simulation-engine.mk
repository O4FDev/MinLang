.PHONY: check-simulation-engine-compile check-simulation-engine check-simulation-engine-sanitize

SIMULATION_ENGINE_INPUTS = $(wildcard tests/fixtures/neodb-engine/src/engine/*.min) \
	$(wildcard tests/fixtures/neodb-engine/src/sql/*.min) \
	$(wildcard tests/fixtures/neodb-engine/src/storage/*.min) \
	tests/fixtures/neodb-engine/source-pins.json tests/fixtures/neodb-engine/lib/dbio.min \
	tests/simulation-engine-probe.min
build/tooling/tests/simulation-engine.ll: tests/frontend-fixtures.min
build/tooling/tests/simulation-engine: $(SIMULATION_ENGINE_INPUTS)

# Full production engine is a separate opt-in proof, not a portable smoke test.
check-simulation-engine-compile: build/minyarc build/tooling/tests/simulation-engine
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/simulation-engine compile

check-simulation-engine: build/minyarc build/minyar-runtime.o build/tooling/tests/simulation-engine
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/simulation-engine

check-simulation-engine-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/simulation-engine
	ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/simulation-engine
