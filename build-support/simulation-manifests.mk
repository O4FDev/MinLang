.PHONY: check-simulation-manifests check-simulation-manifests-sanitize

SIMULATION_MANIFEST_FIXTURE = $(wildcard tests/fixtures/neodb-simulation/src/storage/*.min) tests/fixtures/neodb-simulation/lib/dbio.min
build/tooling/tests/simulation-manifests.ll: tests/frontend-fixtures.min tests/simulation-manifests-probe.min $(SIMULATION_MANIFEST_FIXTURE)

check-simulation-manifests: build/minyarc build/minyar-runtime.o build/tooling/tests/simulation-manifests
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/simulation-manifests

check-simulation-manifests-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/simulation-manifests
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/simulation-manifests

check check-portable: check-simulation-manifests
check-sanitize: check-simulation-manifests-sanitize
