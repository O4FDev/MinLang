.PHONY: check-thread-compiler check-thread-effects check-thread-language check-thread-language-sanitize check-thread-tsan-control
.PHONY: check-thread-scaling-protocol
.PHONY: check-thread-language-tsan
.PHONY: check-thread-generated-recovery check-thread-generated-recovery-sanitize check-thread-generated-recovery-tsan
.PHONY: check-thread-native-regions check-thread-native-regions-sanitize check-thread-native-regions-tsan

check-thread-native-regions: build/minyarc build/minyar-default-runtime.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/thread-native-regions.py

check-thread-native-regions-sanitize: build/minyarc-sanitize build/minyar-default-runtime.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/thread-native-regions.py --sanitizer address

check-thread-native-regions-tsan: build/minyarc build/minyar-default-runtime.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/thread-native-regions.py --sanitizer thread

check-thread-generated-recovery: build/minyarc-threads build/minyar-default-runtime.o build/minyar-runtime-eager.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/thread-generated-recovery.py

check-thread-generated-recovery-sanitize: build/minyarc-threads build/minyar-default-runtime.o build/minyar-runtime-eager.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/thread-generated-recovery.py --sanitizer address

check-thread-generated-recovery-tsan: build/minyarc-threads build/minyar-default-runtime.o build/minyar-runtime-eager.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/thread-generated-recovery.py --sanitizer thread

build/tooling/tests/concurrency-scaling-test build/tooling/tools/concurrency-scaling: private TOOL_NATIVE = runtime/native/sha256.c tests/performance-resources.c tests/performance-test-runtime.c
build/tooling/tests/concurrency-scaling-test build/tooling/tools/concurrency-scaling: private TOOL_LIBS = -lcrypto
build/tooling/tests/concurrency-scaling-test build/tooling/tools/concurrency-scaling: private TOOL_RUNTIME = build/testing/cycle-runtime.o
build/tooling/tests/concurrency-scaling-test build/tooling/tools/concurrency-scaling: tests/performance-resources.c tests/performance-test-runtime.c build/testing/cycle-runtime.o
check-thread-scaling-protocol: build/tooling/tests/concurrency-scaling-test build/tooling/tools/concurrency-scaling
	$(LIMITED) ./build/tooling/tests/concurrency-scaling-test

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
ifeq ($(shell uname -s),Linux)
check check-portable: check-thread-native-regions
check-sanitize: check-thread-native-regions-sanitize check-thread-native-regions-tsan
endif
