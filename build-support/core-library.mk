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

check check-portable: check-octal-literals check-reserved-names
check-sanitize: check-octal-literals-sanitize check-reserved-names-sanitize
