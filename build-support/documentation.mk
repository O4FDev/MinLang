.PHONY: check-doc-comments
check-doc-comments: build/minyarc build/minyar-runtime.o build/tooling/tests/doc-comments
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/doc-comments

build/tooling/tests/doc-comments.ll: tests/frontend-fixtures.min tests/documentation-probe.min
check check-portable: check-doc-comments

.PHONY: check-documentation
build/tooling/tests/documentation-cli: TOOL_NATIVE = tools/clang-driver-host.c
build/tooling/tests/documentation-cli: tools/clang-driver-host.c runtime/minyar_native.h
build/tooling/tests/documentation-cli.ll: tests/documentation-cases/harbour.min
check-documentation: build/tooling/tests/documentation-cli build/tooling/tools/project-cli build/tooling/tools/clang-driver build/minyar-module-build
	MINYAR_TEST_CLANG="$(LLVM_CC)" ./build/tooling/tests/documentation-cli

check check-portable: check-documentation

.PHONY: check-library-documentation
build/tooling/tests/library-documentation: TOOL_NATIVE = tools/clang-driver-host.c
build/tooling/tests/library-documentation: tools/clang-driver-host.c runtime/minyar_native.h
check-library-documentation: build/tooling/tests/library-documentation build/tooling/tools/project-cli build/tooling/tools/clang-driver build/minyar-module-build
	MINYAR_TEST_CLANG="$(LLVM_CC)" ./build/tooling/tests/library-documentation

check check-portable: check-library-documentation
