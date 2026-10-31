.PHONY: check-sequences check-sequences-sanitize
build/tooling/tests/sequences.ll: tests/frontend-fixtures.min

# tests/sequences.min runs four independent selector blocks. A selector gates a
# whole block, because several blocks read the `caseN.ll` their own compile just
# made; with no selector the harness still runs every block.
SEQUENCES_BLOCKS = core boundaries immediate gallery
SEQUENCES_PARTS = $(addprefix check-sequences-part-,$(SEQUENCES_BLOCKS))
SEQUENCES_SANITIZE_PARTS = $(addprefix check-sequences-sanitize-part-,$(SEQUENCES_BLOCKS))
.PHONY: $(SEQUENCES_PARTS) $(SEQUENCES_SANITIZE_PARTS)

check-sequences: $(SEQUENCES_PARTS)

check-sequences-part-core: build/minyarc build/minyar-runtime.o build/tooling/tests/sequences
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/sequences Sequences.core

check-sequences-part-boundaries: build/minyarc build/minyar-runtime.o build/tooling/tests/sequences
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/sequences Sequences.boundaries

check-sequences-part-immediate: build/minyarc build/minyar-runtime.o build/tooling/tests/sequences
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/sequences Sequences.immediate

check-sequences-part-gallery: build/minyarc build/minyar-runtime.o build/tooling/tests/sequences
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/sequences Sequences.gallery

check-sequences-sanitize: $(SEQUENCES_SANITIZE_PARTS)

check-sequences-sanitize-part-core: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/sequences
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/sequences Sequences.core

check-sequences-sanitize-part-boundaries: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/sequences
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/sequences Sequences.boundaries

check-sequences-sanitize-part-immediate: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/sequences
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/sequences Sequences.immediate

check-sequences-sanitize-part-gallery: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/sequences
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/sequences Sequences.gallery

check check-portable: check-sequences
check-sanitize: check-sequences-sanitize
