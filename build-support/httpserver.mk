.PHONY: check-httpserver check-httpserver-sanitize
# Aggregate hooks are POSIX-only until the server is qualified on Windows.
check-httpserver: build/minyarc build/minyar-default-runtime.o
	MINYAR_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/httpserver.py --mode debug
	MINYAR_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/httpserver.py --mode release

ifeq ($(filter Windows_NT,$(OS))$(filter MSYS% MINGW% CYGWIN%,$(shell uname -s)),)
check check-portable: check-httpserver
endif

check-httpserver-sanitize: build/minyarc
	MINYAR_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/httpserver.py --sanitize

ifeq ($(filter Windows_NT,$(OS))$(filter MSYS% MINGW% CYGWIN%,$(shell uname -s)),)
check-sanitize: check-httpserver-sanitize
endif

.PHONY: check-httpserver-front bench-httpserver
check-httpserver-front: build/minyarc build/minyar-default-runtime-release.ll
	MINYAR_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/httpserver-front.py

ifeq ($(filter Windows_NT,$(OS))$(filter MSYS% MINGW% CYGWIN%,$(shell uname -s)),)
check check-portable: check-httpserver-front
endif

# Opt-in heavy qualification. Supply prebuilt binaries and an empty output path.
bench-httpserver:
	python3 benchmarks/httpserver/compare.py --minyar "$(HTTP_FRONT_MINYAR)" --axum "$(HTTP_FRONT_AXUM)" --queries benchmarks/httpserver/inputs/queries.tsv --replay benchmarks/httpserver/inputs/bodies.jsonl.gz --output "$(HTTP_FRONT_RESULTS)"
