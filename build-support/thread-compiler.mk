.PHONY: check-thread-compiler check-thread-effects check-thread-language check-thread-language-sanitize check-thread-tsan-control
.PHONY: check-thread-scaling-protocol
.PHONY: check-thread-language-tsan
.PHONY: check-thread-generated-recovery check-thread-generated-recovery-sanitize check-thread-generated-recovery-tsan
.PHONY: check-thread-native-regions check-thread-native-regions-sanitize check-thread-native-regions-tsan

build/tooling/tests/thread-native-regions.ll: tests/thread-port-support.min
build/tooling/tests/thread-generated-recovery.ll: tests/thread-port-support.min
build/tooling/tests/thread-effects.ll: tests/thread-port-support.min
build/tooling/tests/thread-language.ll: tests/thread-port-support.min
build/tooling/tests/thread-tsan-control.ll: tests/thread-port-support.min
build/tooling/tests/thread-compiler.ll: tests/thread-port-support.min tests/compiler-port-support.min tests/sha256-support.min
build/tooling/tests/thread-native-regions: TOOL_NATIVE = runtime/native/sha256.c
build/tooling/tests/thread-native-regions: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/thread-native-regions: runtime/native/sha256.c
build/tooling/tests/thread-generated-recovery: TOOL_NATIVE = runtime/native/sha256.c
build/tooling/tests/thread-generated-recovery: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/thread-generated-recovery: runtime/native/sha256.c
build/tooling/tests/thread-effects: TOOL_NATIVE = runtime/native/sha256.c
build/tooling/tests/thread-effects: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/thread-effects: runtime/native/sha256.c
build/tooling/tests/thread-language: TOOL_NATIVE = runtime/native/sha256.c
build/tooling/tests/thread-language: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/thread-language: runtime/native/sha256.c
build/tooling/tests/thread-tsan-control: TOOL_NATIVE = runtime/native/sha256.c
build/tooling/tests/thread-tsan-control: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/thread-tsan-control: runtime/native/sha256.c
check-thread-native-regions: build/minyarc build/minyar-default-runtime.o build/tooling/tests/thread-native-regions build/tooling/tools/clang-driver
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/thread-native-regions

check-thread-native-regions-sanitize: build/minyarc-sanitize build/minyar-default-runtime.o build/tooling/tests/thread-native-regions build/tooling/tools/clang-driver
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/thread-native-regions --sanitizer address

check-thread-native-regions-tsan: build/minyarc build/minyar-default-runtime.o build/tooling/tests/thread-native-regions build/tooling/tools/clang-driver
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/thread-native-regions --sanitizer thread

check-thread-generated-recovery: build/minyarc-threads build/minyar-default-runtime.o build/minyar-runtime-eager.o build/tooling/tests/thread-generated-recovery build/tooling/tools/clang-driver
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/thread-generated-recovery

check-thread-generated-recovery-sanitize: build/minyarc-threads build/minyar-default-runtime.o build/minyar-runtime-eager.o build/tooling/tests/thread-generated-recovery build/tooling/tools/clang-driver
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/thread-generated-recovery --sanitizer address

check-thread-generated-recovery-tsan: build/minyarc-threads build/minyar-default-runtime.o build/minyar-runtime-eager.o build/tooling/tests/thread-generated-recovery build/tooling/tools/clang-driver
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/thread-generated-recovery --sanitizer thread

build/tooling/tests/concurrency-scaling-test build/tooling/tools/concurrency-scaling: TOOL_NATIVE = runtime/native/sha256.c tests/performance-resources.c
build/tooling/tests/concurrency-scaling-test build/tooling/tools/concurrency-scaling: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/concurrency-scaling-test build/tooling/tools/concurrency-scaling: TOOL_RUNTIME = build/testing/cycle-runtime.o
build/tooling/tests/concurrency-scaling-test build/tooling/tools/concurrency-scaling: tests/performance-resources.c build/testing/cycle-runtime.o
check-thread-scaling-protocol: build/tooling/tests/concurrency-scaling-test build/tooling/tools/concurrency-scaling
	$(LIMITED) ./build/tooling/tests/concurrency-scaling-test

build/tooling/tests/thread-compiler: TOOL_NATIVE = tests/sha256-test-native.c runtime/native/sha256.c
build/tooling/tests/thread-compiler: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/thread-compiler: tests/sha256-test-native.c runtime/native/sha256.c
check-thread-compiler: build/minyarc-threads build/tooling/tests/thread-compiler
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/thread-compiler

check-thread-effects: build/thread-compiler.min build/minyarc build/minyar-compiler-runtime.ll build/tooling/tests/thread-effects
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/thread-effects

check-thread-language: build/minyarc-threads build/minyar-default-runtime.o build/tooling/tests/thread-language
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/thread-language

check-thread-language-sanitize: build/minyarc-threads build/minyar-default-runtime.o build/tooling/tests/thread-language
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/thread-language --sanitizer address

check-thread-language-tsan: build/minyarc-threads build/minyar-default-runtime.o build/tooling/tests/thread-language
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/thread-language --sanitizer thread

check-thread-tsan-control: build/minyarc-threads build/minyar-default-runtime.o build/tooling/tests/thread-tsan-control build/tooling/tools/clang-driver
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/thread-tsan-control

check check-portable: check-thread-compiler check-thread-effects check-thread-language check-thread-scaling-protocol check-thread-generated-recovery
check-sanitize: check-thread-language-sanitize check-thread-language-tsan check-thread-tsan-control check-thread-generated-recovery-sanitize check-thread-generated-recovery-tsan
ifeq ($(shell uname -s),Linux)
check check-portable: check-thread-native-regions
check-sanitize: check-thread-native-regions-sanitize check-thread-native-regions-tsan
endif
