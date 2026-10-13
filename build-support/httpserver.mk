.PHONY: check-httpserver check-httpserver-sanitize
# Aggregate hooks are POSIX-only until the server is qualified on Windows.
build/tooling/tests/httpserver-test: TOOL_NATIVE = runtime/native/net.c tests/net-wire-native.c
build/tooling/tests/httpserver-test: runtime/native/net.c tests/net-wire-native.c
check-httpserver: build/minyarc build/minyar-default-runtime.o build/tooling/tests/httpserver-test
	MINYAR_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/httpserver-test --mode debug
	MINYAR_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/httpserver-test --mode release

ifeq ($(filter Windows_NT,$(OS))$(filter MSYS% MINGW% CYGWIN%,$(shell uname -s)),)
check check-portable: check-httpserver
endif

check-httpserver-sanitize: build/minyarc build/tooling/tests/httpserver-test
	MINYAR_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/httpserver-test --sanitize

ifeq ($(filter Windows_NT,$(OS))$(filter MSYS% MINGW% CYGWIN%,$(shell uname -s)),)
check-sanitize: check-httpserver-sanitize
endif

.PHONY: check-httpserver-front bench-httpserver
build/tooling/tests/httpserver-front-test: TOOL_NATIVE = runtime/native/net.c tests/net-wire-native.c
build/tooling/tests/httpserver-front-test: runtime/native/net.c tests/net-wire-native.c
check-httpserver-front: build/minyarc build/minyar-default-runtime-release.ll build/tooling/tests/httpserver-front-test
	MINYAR_CLANG="$(LLVM_CC)" MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/httpserver-front-test

ifeq ($(filter Windows_NT,$(OS))$(filter MSYS% MINGW% CYGWIN%,$(shell uname -s)),)
check check-portable: check-httpserver-front
endif

# Opt-in heavy qualification. Supply prebuilt binaries and an empty output path.
build/tooling/benchmarks/httpserver/compare: TOOL_NATIVE = runtime/native/net.c tests/net-wire-native.c
build/tooling/benchmarks/httpserver/compare: runtime/native/net.c tests/net-wire-native.c
bench-httpserver: build/tooling/benchmarks/httpserver/compare
	MINYAR_TEST_CLANG="$(LLVM_CC)" ./build/tooling/benchmarks/httpserver/compare --minyar "$(HTTP_FRONT_MINYAR)" --axum "$(HTTP_FRONT_AXUM)" --queries benchmarks/httpserver/inputs/queries.tsv --replay benchmarks/httpserver/inputs/bodies.jsonl.gz --output "$(HTTP_FRONT_RESULTS)"
