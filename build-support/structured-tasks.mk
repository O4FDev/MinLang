.PHONY: check-structured-tasks check-structured-tasks-sanitize

ifneq ($(filter Darwin Linux,$(shell uname -s)),)
check-structured-tasks: build/minyarc build/minyar-runtime.o build/tooling/tests/structured-tasks
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "./build/tooling/tests/structured-tasks"

check-structured-tasks-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/structured-tasks
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER="./build/minyarc-sanitize" MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) "./build/tooling/tests/structured-tasks"

check check-portable: check-structured-tasks
check-sanitize: check-structured-tasks-sanitize
endif
