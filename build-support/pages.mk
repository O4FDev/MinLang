.PHONY: check-pages check-pages-sanitize

build/tooling/tests/pages: tests/frontend-fixtures.min examples/gallery/page-ledger.min
check-pages: build/minyarc build/minyar-runtime.o build/tooling/tests/pages
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/pages

check-pages-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/pages
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/pages

check check-portable: check-pages
check-sanitize: check-pages-sanitize
