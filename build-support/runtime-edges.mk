# Memory-safety checks of the C runtime paths that hand-written vector code and
# the small-object heap add: tests/text-vector-edges.c (UTF-8 validation and
# Text search at unreadable page boundaries, against scalar oracles) and
# tests/small-heap-stress.c (random allocate/free/resize with content checks).
# The sanitizer form forces the small heap on, which sanitizer builds otherwise
# compile out. See docs/security-review.md.
RUNTIME_EDGE_TESTS = text-vector-edges small-heap-stress
.PHONY: check-runtime-edges check-runtime-edges-sanitize
build/runtime-edges/%: tests/%.c runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	mkdir -p build/runtime-edges
	$(LIMITED) "$(LLVM_CC)" -std=c11 -O2 -isystem vendor $< $(LDLIBS) -o $@
build/runtime-edges/%-sanitize: tests/%.c runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	mkdir -p build/runtime-edges
	$(SANITIZER_LIMITED) "$(LLVM_CC)" -std=c11 $(SANITIZER_FLAGS) -DMINYAR_SYSTEM_SMALL_HEAP=1 -isystem vendor $< $(LDLIBS) -o $@
check-runtime-edges: $(RUNTIME_EDGE_TESTS:%=build/runtime-edges/%)
	$(LIMITED) ./build/runtime-edges/text-vector-edges
	$(LIMITED) ./build/runtime-edges/small-heap-stress
check-runtime-edges-sanitize: $(RUNTIME_EDGE_TESTS:%=build/runtime-edges/%-sanitize)
	$(NATIVE_SANITIZER_ENV) $(SANITIZER_LIMITED) ./build/runtime-edges/text-vector-edges-sanitize
	$(NATIVE_SANITIZER_ENV) $(SANITIZER_LIMITED) ./build/runtime-edges/small-heap-stress-sanitize

ifeq ($(filter Windows_NT,$(OS))$(filter MSYS% MINGW% CYGWIN%,$(shell uname -s)),)
check check-portable: check-runtime-edges
check-sanitize: check-runtime-edges-sanitize
endif
