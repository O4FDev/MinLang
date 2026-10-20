.PHONY: check-ownership-explanations check-ownership-explanations-sanitize
check-ownership-explanations: build/minyarc build/minyar-runtime.o build/tooling/tests/ownership-explanations
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "./build/tooling/tests/ownership-explanations"

check-ownership-explanations-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/ownership-explanations
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_COMPILER="./build/minyarc-sanitize" MINYAR_TEST_RUNTIME="./build/minyar-runtime-sanitize.o" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) "./build/tooling/tests/ownership-explanations"

check check-portable: check-ownership-explanations
check-sanitize: check-ownership-explanations-sanitize
