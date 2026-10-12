.PHONY: check-httpserver check-httpserver-sanitize
check-httpserver: build/minyarc build/minyar-default-runtime.o
	MINYAR_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/httpserver.py --mode debug
	MINYAR_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/httpserver.py --mode release

check check-portable: check-httpserver

check-httpserver-sanitize: build/minyarc
	MINYAR_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/httpserver.py --sanitize

check-sanitize: check-httpserver-sanitize
