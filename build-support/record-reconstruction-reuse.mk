.PHONY: check-record-reconstruction-reuse

build/tooling/tests/record-reconstruction-reuse.ll: tests/frontend-fixtures.min

check-record-reconstruction-reuse: build/minyarc build/minyarc-sanitize build/tooling/tests/record-reconstruction-reuse
	$(LIMITED) ./build/tooling/tests/record-reconstruction-reuse
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/record-reconstruction-reuse
	printf '%s\n' '#!/bin/sh' 'exec ./build/minyarc "$$@" --scope-owners' > 'build/record-reuse-scope'
	printf '%s\n' '#!/bin/sh' 'exec ./build/minyarc-sanitize "$$@" --scope-owners' > 'build/record-reuse-scope-sanitize'
	chmod +x 'build/record-reuse-scope' 'build/record-reuse-scope-sanitize'
	MINYAR_TEST_COMPILER=./build/record-reuse-scope $(LIMITED) ./build/tooling/tests/record-reconstruction-reuse
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/record-reuse-scope-sanitize MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/record-reconstruction-reuse

check check-portable: check-record-reconstruction-reuse
