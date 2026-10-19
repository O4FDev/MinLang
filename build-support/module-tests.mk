.PHONY: check-module-tests check-module-tests-cli
build/tooling/tests/module-tests build/tooling/tests/module-tests-cli: TOOL_NATIVE = tools/clang-driver-host.c
build/tooling/tests/module-tests build/tooling/tests/module-tests-cli: tools/clang-driver-host.c runtime/minyar_native.h

check-module-tests: build/minyarc build/minyar-runtime.o build/minyar-default-runtime.o build/tooling/tests/module-tests
	MINYAR_TEST_RUNTIME="./build/minyar-default-runtime.o" MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/module-tests

check-module-tests-cli: build/tooling/tests/module-tests-cli build/tooling/tools/project-cli build/tooling/tools/clang-driver build/minyar-module-build
	MINYAR_TEST_CLANG="$(LLVM_CC)" ./build/tooling/tests/module-tests-cli

check check-portable: check-module-tests check-module-tests-cli
