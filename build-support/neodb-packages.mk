.PHONY: check-net-additions check-net-additions-sanitize check-files-system check-files-system-sanitize
.PHONY: check-neodb-review check-neodb-review-sanitize
check-neodb-review: build/tooling/tests/neodb-review
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/neodb-review

check-neodb-review-sanitize: build/tooling/tests/neodb-review
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/neodb-review --mode sanitize
check-net-additions: build/minyarc build/tooling/tests/neodb-packages
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/neodb-packages --suite net-additions

check-net-additions-sanitize: build/minyarc build/tooling/tests/neodb-packages
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/neodb-packages --suite net-additions --mode sanitize

check-files-system: build/minyarc build/tooling/tests/neodb-packages
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/neodb-packages --suite files-system

check-files-system-sanitize: build/minyarc build/tooling/tests/neodb-packages
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/neodb-packages --suite files-system --mode sanitize

check check-portable: check-net-additions
ifeq ($(filter Windows_NT,$(OS))$(filter MSYS% MINGW% CYGWIN%,$(shell uname -s)),)
check check-portable: check-files-system check-neodb-review
check-sanitize: check-files-system-sanitize check-net-additions-sanitize check-neodb-review-sanitize
endif
