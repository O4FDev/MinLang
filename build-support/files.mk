.PHONY: check-files check-files-sanitize
FILES_TEST_SOURCES = tests/files-focused.py tests/files-test-path.h tests/files-ranges.c tests/files-prepare.c tests/files-eventloop.min runtime/native/files.c library/files.min
check-files: build/minyarc $(FILES_TEST_SOURCES)
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/files-focused.py

check-files-sanitize: build/minyarc $(FILES_TEST_SOURCES)
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/files-focused.py --sanitize

# The files backend is POSIX-only for now; tests/files-focused.py refuses Windows.
ifeq ($(filter Windows_NT,$(OS))$(filter MSYS% MINGW% CYGWIN%,$(shell uname -s)),)
check check-portable: check-files
check-sanitize: check-files-sanitize
endif
