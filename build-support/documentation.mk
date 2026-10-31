.PHONY: check-doc-comments
check-doc-comments: build/minyarc build/minyar-runtime.o build/tooling/tests/doc-comments
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/doc-comments

build/tooling/tests/doc-comments.ll: tests/frontend-fixtures.min tests/documentation-probe.min
check check-portable: check-doc-comments

.PHONY: check-documentation
build/tooling/tests/documentation-cli: TOOL_NATIVE = tools/clang-driver-host.c
build/tooling/tests/documentation-cli: tools/clang-driver-host.c runtime/minyar_native.h
build/tooling/tests/documentation-cli.ll: tests/documentation-cases/harbour.min
check-documentation: build/tooling/tests/documentation-cli build/tooling/tools/project-cli build/tooling/tools/clang-driver build/minyar-module-build
	MINYAR_TEST_CLANG="$(TEST_CLANG)" ./build/tooling/tests/documentation-cli

check check-portable: check-documentation

.PHONY: check-library-documentation check-library-documentation-part-debug-library \
    check-library-documentation-part-debug-gallery check-library-documentation-part-release-library \
    check-library-documentation-part-release-gallery
LIBRARY_DOCUMENTATION_INPUTS = build/tooling/tests/library-documentation build/tooling/tools/project-cli \
    build/tooling/tools/clang-driver build/minyar-module-build
build/tooling/tests/library-documentation: TOOL_NATIVE = tools/clang-driver-host.c
build/tooling/tests/library-documentation: tools/clang-driver-host.c runtime/minyar_native.h
# One piece per (profile, input): each run writes its own scratch and its own
# <input>/target/<profile> cache, so no two pieces share a directory.
check-library-documentation-part-debug-library: $(LIBRARY_DOCUMENTATION_INPUTS)
	MINYAR_TEST_CLANG="$(TEST_CLANG)" ./build/tooling/tests/library-documentation --profile debug --input library

check-library-documentation-part-debug-gallery: $(LIBRARY_DOCUMENTATION_INPUTS)
	MINYAR_TEST_CLANG="$(TEST_CLANG)" ./build/tooling/tests/library-documentation --profile debug --input examples/gallery

check-library-documentation-part-release-library: $(LIBRARY_DOCUMENTATION_INPUTS)
	MINYAR_TEST_CLANG="$(TEST_CLANG)" ./build/tooling/tests/library-documentation --profile release --input library

check-library-documentation-part-release-gallery: $(LIBRARY_DOCUMENTATION_INPUTS)
	MINYAR_TEST_CLANG="$(TEST_CLANG)" ./build/tooling/tests/library-documentation --profile release --input examples/gallery

check-library-documentation: check-library-documentation-part-debug-library check-library-documentation-part-debug-gallery \
    check-library-documentation-part-release-library check-library-documentation-part-release-gallery $(LIBRARY_DOCUMENTATION_INPUTS)

check check-portable: check-library-documentation
