.PHONY: check-peer-live check-peer-live-sanitize check-peer-live-redis check-peer-live-redis-sanitize
check-peer-live: build/minyarc build/minyarc-callbacks build/minyar-runtime.o build/minyar-default-runtime.o build/tooling/tests/peer-live-test build/tooling/tools/clang-driver
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/peer-live-test

check-peer-live-sanitize: build/minyarc-sanitize build/minyarc-callbacks-sanitize build/minyar-runtime-sanitize.o build/minyar-default-runtime-sanitize.o build/tooling/tests/peer-live-test build/tooling/tools/clang-driver
	UBSAN_OPTIONS=halt_on_error=1 MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/peer-live-test

build/tooling/tests/peer-live-redis-test: TOOL_NATIVE = runtime/native/net.c
build/tooling/tests/peer-live-redis-test: runtime/native/net.c
check-peer-live-redis: build/minyarc build/minyarc-callbacks build/minyar-runtime.o build/minyar-default-runtime.o build/tooling/tests/peer-live-redis-test build/tooling/tools/clang-driver
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/peer-live-redis-test

check-peer-live-redis-sanitize: build/minyarc-sanitize build/minyarc-callbacks-sanitize build/minyar-runtime-sanitize.o build/minyar-default-runtime-sanitize.o build/tooling/tests/peer-live-redis-test build/tooling/tools/clang-driver
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/peer-live-redis-test

check check-portable: check-peer-live
check-sanitize: check-peer-live-sanitize
