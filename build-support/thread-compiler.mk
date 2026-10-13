.PHONY: check-thread-compiler check-thread-effects check-thread-language check-thread-language-sanitize check-thread-tsan-control
.PHONY: check-thread-scaling-protocol
.PHONY: check-thread-language-tsan
.PHONY: check-thread-generated-recovery check-thread-generated-recovery-sanitize check-thread-generated-recovery-tsan

check-thread-generated-recovery: build/minyarc-threads build/minyar-default-runtime.o build/minyar-runtime-eager.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/thread-generated-recovery.py

check-thread-generated-recovery-sanitize: build/minyarc-threads build/minyar-default-runtime.o build/minyar-runtime-eager.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/thread-generated-recovery.py --sanitizer address

check-thread-generated-recovery-tsan: build/minyarc-threads build/minyar-default-runtime.o build/minyar-runtime-eager.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/thread-generated-recovery.py --sanitizer thread

check-thread-scaling-protocol:
	$(LIMITED) python3 tests/concurrency-scaling.py

check-thread-compiler: build/minyarc-threads
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/thread-compiler.py

check-thread-effects: build/thread-compiler.min build/minyarc build/minyar-compiler-runtime.ll
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/thread-effects.py

check-thread-language: build/minyarc-threads build/minyar-default-runtime.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/thread-language.py

check-thread-language-sanitize: build/minyarc-threads build/minyar-default-runtime.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/thread-language.py --sanitizer address

check-thread-language-tsan: build/minyarc-threads build/minyar-default-runtime.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/thread-language.py --sanitizer thread

check-thread-tsan-control: build/minyarc-threads build/minyar-default-runtime.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/thread-tsan-control.py

check check-portable: check-thread-compiler check-thread-effects check-thread-language check-thread-scaling-protocol check-thread-generated-recovery
check-sanitize: check-thread-language-sanitize check-thread-language-tsan check-thread-tsan-control check-thread-generated-recovery-sanitize check-thread-generated-recovery-tsan
