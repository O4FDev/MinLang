.PHONY: check-builtin-capabilities check-builtin-capabilities-sanitize

check-builtin-capabilities: build/minyarc build/minyar-runtime.o build/tooling/tests/builtin-capabilities
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "./build/tooling/tests/builtin-capabilities"

check-builtin-capabilities-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/builtin-capabilities
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) "./build/tooling/tests/builtin-capabilities"

build/tooling/tests/builtin-capabilities.ll: tests/frontend-fixtures.min examples/gallery/capability-order.min

check check-portable: check-builtin-capabilities
check-sanitize: check-builtin-capabilities-sanitize
