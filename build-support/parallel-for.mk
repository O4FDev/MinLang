.PHONY: check-parallel-for check-parallel-for-sanitize check-parallel-pool check-parallel-pool-tsan

ifneq ($(OS),Windows_NT)
build/parallel-pool: tests/parallel-pool.c runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	"$(LLVM_CC)" $(CPPFLAGS) $(CFLAGS) -pthread $< -lm -o $@

check-parallel-pool: build/parallel-pool
	MINYAR_PARALLEL_THREADS=1 $(LIMITED) ./build/parallel-pool
	MINYAR_PARALLEL_THREADS=4 $(LIMITED) ./build/parallel-pool

build/parallel-pool-tsan: tests/parallel-pool.c runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	"$(LLVM_CC)" -std=c11 -O1 -g -fsanitize=thread -pthread $< -lm -o $@

check-parallel-pool-tsan: build/parallel-pool-tsan
	MINYAR_PARALLEL_THREADS=1 ./build/parallel-pool-tsan
	MINYAR_PARALLEL_THREADS=4 ./build/parallel-pool-tsan

check-parallel-for: check-parallel-pool
else
check-parallel-pool check-parallel-pool-tsan:
	@echo "The pthread pool checks require macOS or Linux." >&2
	@exit 1
endif

check-parallel-for: build/minyarc build/minyar-runtime.o build/tooling/tests/parallel-for
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/parallel-for
	MINYAR_PARALLEL_MODULES=1 MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/parallel-for
	MINYAR_PARALLEL_THREADS=1 MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/parallel-for

check-parallel-for-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/parallel-for
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/parallel-for
	ASAN_OPTIONS=detect_leaks=0 MINYAR_PARALLEL_MODULES=1 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/parallel-for

check check-portable: check-parallel-for
check-sanitize: check-parallel-for-sanitize
