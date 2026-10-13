.PHONY: check-maps check-maps-sanitize bench-maps bench-maps-baseline
MAP_FRONTENDS = build/minyarc build/minyarc-modules build/minyarc-callbacks build/minyarc-errors
MAP_SANITIZED_FRONTENDS = $(addsuffix -sanitize,$(MAP_FRONTENDS))
# The cache driver is POSIX-only, as in managed-graphs.mk.
ifeq ($(filter Windows_NT,$(OS))$(filter MSYS% MINGW% CYGWIN%,$(shell uname -s)),)
check-maps: build/minyar-module-build
check-maps: map-module-cache
.PHONY: map-module-cache
map-module-cache: build/minyarc-modules build/minyar-module-build build/minyar-runtime.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/maps-incremental.py
endif
check-maps: $(MAP_FRONTENDS) build/minyar-runtime.o build/tooling/tests/maps-frontends
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/maps-matrix.py
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/maps-frontends

check-maps-sanitize: $(MAP_SANITIZED_FRONTENDS) build/tooling/tests/maps-frontends
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/maps-matrix.py --sanitize
	MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/maps-frontends

check check-portable: check-maps
check-sanitize: check-maps-sanitize

# External affinity/serial execution is the owning Boat job's responsibility.
bench-maps: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/maps-bench.py

bench-maps-baseline: build/minyarc build/minyarc-baseline build/tooling/tests/maps-baseline
	$(LIMITED) ./build/tooling/tests/maps-baseline
