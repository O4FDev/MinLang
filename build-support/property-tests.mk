.PHONY: check-property-generators check-property-tests check-property-tests-cli

build/tooling/tests/property-generator: TOOL_RUNTIME = build/testing/cycle-runtime.o
build/tooling/tests/property-generator: build/testing/cycle-runtime.o

check-property-generators: build/tooling/tests/property-generator
	$(LIMITED) ./build/tooling/tests/property-generator

build/tooling/tests/property-tests build/tooling/tests/property-cli: TOOL_NATIVE = tools/clang-driver-host.c
build/tooling/tests/property-tests build/tooling/tests/property-cli: tools/clang-driver-host.c runtime/minyar_native.h

check-property-tests: build/minyarc build/minyar-default-runtime.o build/tooling/tests/property-tests
	MINYAR_TEST_RUNTIME="./build/minyar-default-runtime.o" MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/property-tests

check-property-tests-cli: build/tooling/tests/property-cli build/tooling/tools/project-cli build/tooling/tools/clang-driver build/minyar-module-build
	MINYAR_TEST_CLANG="$(LLVM_CC)" ./build/tooling/tests/property-cli

check check-portable: check-property-generators check-property-tests check-property-tests-cli
