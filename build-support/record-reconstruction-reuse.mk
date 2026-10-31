.PHONY: check-record-reconstruction-reuse check-record-reconstruction-reuse-part1 \
    check-record-reconstruction-reuse-part2 check-record-reconstruction-reuse-part3 \
    check-record-reconstruction-reuse-part4

build/tooling/tests/record-reconstruction-reuse.ll: tests/frontend-fixtures.min

# The two --scope-owners wrappers are real file goals so the runner builds each once
# and no two pieces write the same file.
build/record-reuse-scope: build/minyarc | build
	printf '%s\n' '#!/bin/sh' 'exec ./build/minyarc "$$@" --scope-owners' > '$@'
	chmod +x '$@'

build/record-reuse-scope-sanitize: build/minyarc-sanitize | build
	printf '%s\n' '#!/bin/sh' 'exec ./build/minyarc-sanitize "$$@" --scope-owners' > '$@'
	chmod +x '$@'

RECORD_REUSE_INPUTS = build/minyarc build/minyarc-sanitize build/tooling/tests/record-reconstruction-reuse
RECORD_REUSE_SANITIZE = ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined

check-record-reconstruction-reuse-part1: $(RECORD_REUSE_INPUTS)
	$(LIMITED) ./build/tooling/tests/record-reconstruction-reuse

check-record-reconstruction-reuse-part2: $(RECORD_REUSE_INPUTS)
	$(RECORD_REUSE_SANITIZE) MINYAR_TEST_COMPILER=./build/minyarc-sanitize $(SANITIZER_LIMITED) ./build/tooling/tests/record-reconstruction-reuse

check-record-reconstruction-reuse-part3: $(RECORD_REUSE_INPUTS) build/record-reuse-scope
	MINYAR_TEST_COMPILER=./build/record-reuse-scope $(LIMITED) ./build/tooling/tests/record-reconstruction-reuse

check-record-reconstruction-reuse-part4: $(RECORD_REUSE_INPUTS) build/record-reuse-scope-sanitize
	$(RECORD_REUSE_SANITIZE) MINYAR_TEST_COMPILER=./build/record-reuse-scope-sanitize $(SANITIZER_LIMITED) ./build/tooling/tests/record-reconstruction-reuse

check-record-reconstruction-reuse: check-record-reconstruction-reuse-part1 check-record-reconstruction-reuse-part2 \
    check-record-reconstruction-reuse-part3 check-record-reconstruction-reuse-part4 $(RECORD_REUSE_INPUTS)

check check-portable: check-record-reconstruction-reuse
