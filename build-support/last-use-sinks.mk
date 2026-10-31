.PHONY: check-last-use-sinks check-last-use-sinks-mutation \
    check-last-use-sinks-part-native-plain check-last-use-sinks-part-native-scoped \
    check-last-use-sinks-part-sanitize-plain check-last-use-sinks-part-sanitize-scoped

build/tooling/tests/last-use-sinks.ll: tests/frontend-fixtures.min
build/tooling/tests/last-use-sinks: TOOL_NATIVE = tools/clang-driver-host.c
build/tooling/tests/last-use-sinks: tools/clang-driver-host.c runtime/minyar_native.h

# One piece per (compiler, ownership mode). The harness writes its scope wrapper
# and compile outputs into its own test.scratch(), so pieces never share a path.
LAST_USE_SINKS_INPUTS = build/minyarc build/minyarc-sanitize build/minyar-runtime.o build/minyar-runtime-sanitize.o build/tooling/tests/last-use-sinks
LAST_USE_SINKS_SANITIZE = ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined

check-last-use-sinks-part-native-plain: $(LAST_USE_SINKS_INPUTS)
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/last-use-sinks --plain

check-last-use-sinks-part-native-scoped: $(LAST_USE_SINKS_INPUTS)
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/last-use-sinks --scoped

check-last-use-sinks-part-sanitize-plain: $(LAST_USE_SINKS_INPUTS)
	$(LAST_USE_SINKS_SANITIZE) MINYAR_TEST_CLANG="$(TEST_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/last-use-sinks --plain

check-last-use-sinks-part-sanitize-scoped: $(LAST_USE_SINKS_INPUTS)
	$(LAST_USE_SINKS_SANITIZE) MINYAR_TEST_CLANG="$(TEST_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/last-use-sinks --scoped

check-last-use-sinks: check-last-use-sinks-part-native-plain check-last-use-sinks-part-native-scoped \
    check-last-use-sinks-part-sanitize-plain check-last-use-sinks-part-sanitize-scoped $(LAST_USE_SINKS_INPUTS)

check-last-use-sinks-mutation: build/minyarc build/ownership-runtime.o build/tooling/tests/last-use-sinks-mutation
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/last-use-sinks-mutation

check check-portable: check-last-use-sinks check-last-use-sinks-mutation
