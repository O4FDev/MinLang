.PHONY: check-thread-compiler check-thread-effects check-thread-language check-thread-language-sanitize check-thread-tsan-control

check-thread-compiler: build/minyarc-threads
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/thread-compiler.py

check-thread-effects: build/thread-compiler.min build/minyarc build/minyar-compiler-runtime.ll
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/thread-effects.py

check-thread-language: build/minyarc-threads build/minyar-default-runtime.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/thread-language.py

check-thread-language-sanitize: build/minyarc-threads build/minyar-default-runtime.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/thread-language.py --sanitizer address

check-thread-tsan-control: build/minyarc-threads build/minyar-default-runtime.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/thread-tsan-control.py

check check-portable: check-thread-compiler check-thread-effects check-thread-language
check-sanitize: check-thread-language-sanitize check-thread-tsan-control
