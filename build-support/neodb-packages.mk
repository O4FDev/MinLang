.PHONY: check-net-additions check-net-additions-sanitize check-files-system check-files-system-sanitize
.PHONY: check-neodb-review check-neodb-review-sanitize
check-neodb-review:
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/neodb-review.py

check-neodb-review-sanitize:
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/neodb-review.py --mode sanitize
check-net-additions: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/neodb-packages.py --suite net-additions

check-net-additions-sanitize: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/neodb-packages.py --suite net-additions --mode sanitize

check-files-system: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/neodb-packages.py --suite files-system

check-files-system-sanitize: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/neodb-packages.py --suite files-system --mode sanitize

check check-portable: check-net-additions
ifeq ($(filter Windows_NT,$(OS))$(filter MSYS% MINGW% CYGWIN%,$(shell uname -s)),)
check check-portable: check-files-system check-neodb-review
check-sanitize: check-files-system-sanitize check-net-additions-sanitize check-neodb-review-sanitize
endif
