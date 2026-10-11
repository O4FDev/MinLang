.PHONY: check-peer-live check-peer-live-sanitize check-peer-live-redis check-peer-live-redis-sanitize
check-peer-live: build/minyarc build/minyarc-callbacks build/minyar-runtime.o build/minyar-default-runtime.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/peer-live.py

check-peer-live-sanitize: build/minyarc-sanitize build/minyarc-callbacks-sanitize build/minyar-runtime-sanitize.o build/minyar-default-runtime-sanitize.o
	UBSAN_OPTIONS=halt_on_error=1 MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/peer-live.py

check-peer-live-redis: build/minyarc build/minyarc-callbacks build/minyar-runtime.o build/minyar-default-runtime.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/peer-live-redis.py

check-peer-live-redis-sanitize: build/minyarc-sanitize build/minyarc-callbacks-sanitize build/minyar-runtime-sanitize.o build/minyar-default-runtime-sanitize.o
	ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/peer-live-redis.py

check check-portable: check-peer-live
check-sanitize: check-peer-live-sanitize
