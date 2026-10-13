.PHONY: check-list-sort check-list-sort-runtime check-list-sort-profiles check-list-sort-sanitize
check-list-sort: build/minyarc build/minyarc-callbacks build/minyar-runtime.o build/tooling/tests/list-sort
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/list-sort

check-list-sort-runtime: build/tooling/tests/list-sort-runtime
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/list-sort-runtime

check-list-sort-profiles: build/minyarc-callbacks build/tooling/tests/list-sort
	@set -e; for profile in '-DMINYAR_COMPILER_ARENA=1' '' '-DMINYAR_SYSTEM_HEAP=1 -DMINYAR_RC_POLL_BUDGET=1' '-DMINYAR_SYSTEM_HEAP=1 -DMINYAR_RC_POLL_BUDGET=32' '-DMINYAR_BOUNDED_HEAP=1 -DMINYAR_BOUNDED_HEAP_BYTES=33554432' '-DMINYAR_BOUNDED_HEAP=1 -DMINYAR_BOUNDED_HEAP_BYTES=33554432 -DMINYAR_LAZY_HEAP=1'; do \
	    case "$$profile" in *MINYAR_LAZY_HEAP*) if [ "$(OS)" = Windows_NT ]; then continue; fi;; esac; \
	    MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_SORT_RUNTIME_FLAGS="$$profile" $(LIMITED) ./build/tooling/tests/list-sort ComparatorSort; \
	done

check-list-sort-sanitize: build/minyarc build/minyarc-callbacks-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/list-sort
	ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined MINYAR_TEST_RUNTIME=build/minyar-runtime-sanitize.o $(SANITIZER_LIMITED) ./build/tooling/tests/list-sort

check check-portable: check-list-sort
check-sanitize: check-list-sort-runtime check-list-sort-sanitize

build/tooling/benchmarks/list-sort/run: TOOL_NATIVE = benchmarks/list-sort/driver-native.c tests/maps-baseline-runtime.c tests/sha256-test-native.c runtime/native/sha256.c
build/tooling/benchmarks/list-sort/run: TOOL_LIBS = -lcrypto
build/tooling/benchmarks/list-sort/run: benchmarks/list-sort/driver-native.c tests/maps-baseline-runtime.c tests/sha256-test-native.c runtime/native/sha256.c
