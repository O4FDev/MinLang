.PHONY: check-octal-literals check-octal-literals-sanitize check-reserved-names check-reserved-names-sanitize

check-octal-literals: build/minyarc build/minyar-runtime.o
	$(LIMITED) python3 tests/octal-literals.py

check-octal-literals-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o
	$(SANITIZER_LIMITED) env MINYAR_TEST_COMPILER=build/minyarc-sanitize MINYAR_TEST_RUNTIME=build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS="$(SANITIZER_FLAGS)" python3 tests/octal-literals.py

check-reserved-names: build/minyarc build/minyar-runtime.o
	python3 tools/reserved-names.py --check
	$(LIMITED) python3 tests/reserved-names.py

check-reserved-names-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o
	$(SANITIZER_LIMITED) env MINYAR_TEST_COMPILER=build/minyarc-sanitize MINYAR_TEST_RUNTIME=build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS="$(SANITIZER_FLAGS)" python3 tests/reserved-names.py

.PHONY: check-module-constants check-module-constants-sanitize check-module-constant-graphs check-module-constant-graphs-sanitize
check-module-constants: build/minyarc build/minyar-runtime.o
	$(LIMITED) python3 tests/module-constants.py

check-module-constants-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o
	$(SANITIZER_LIMITED) env MINYAR_TEST_COMPILER=build/minyarc-sanitize MINYAR_TEST_RUNTIME=build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS="$(SANITIZER_FLAGS)" python3 tests/module-constants.py

check-module-constant-graphs: build/minyarc build/minyarc-callbacks
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/module-constant-graphs.py

check-module-constant-graphs-sanitize: build/minyarc-sanitize build/minyarc-callbacks-sanitize
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/module-constant-graphs.py

check check-portable: check-octal-literals check-reserved-names check-module-constants check-module-constant-graphs
check-sanitize: check-octal-literals-sanitize check-reserved-names-sanitize check-module-constants-sanitize check-module-constant-graphs-sanitize
