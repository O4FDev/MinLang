.PHONY: check-ownership-name-proofs

build/tooling/tests/ownership-name-proofs.ll: tests/frontend-fixtures.min

check-ownership-name-proofs: build/minyarc build/minyarc-sanitize build/tooling/tests/ownership-name-proofs
	$(LIMITED) ./build/tooling/tests/ownership-name-proofs
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/ownership-name-proofs
	printf '%s\n' '#!/bin/sh' 'exec ./build/minyarc "$$@" --scope-owners' > 'build/ownership-names-scope'
	printf '%s\n' '#!/bin/sh' 'exec ./build/minyarc-sanitize "$$@" --scope-owners' > 'build/ownership-names-scope-sanitize'
	chmod +x 'build/ownership-names-scope' 'build/ownership-names-scope-sanitize'
	MINYAR_TEST_COMPILER=./build/ownership-names-scope $(LIMITED) ./build/tooling/tests/ownership-name-proofs
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/ownership-names-scope-sanitize MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/ownership-name-proofs

check check-portable: check-ownership-name-proofs
