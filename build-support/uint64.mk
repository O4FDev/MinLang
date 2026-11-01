.PHONY: check-uint64

# library/uint64.min against C uint64_t at O0 and O2 over the same IR.
build/tooling/tests/uint64: TOOL_NATIVE = tests/uint64-reference.c
build/tooling/tests/uint64: tests/uint64-reference.c
build/tooling/tests/uint64-o0: build/tooling/tests/uint64.ll build/minyar-runtime.o tests/uint64-reference.c
	"$(LLVM_CC)" -O0 -Wno-override-module $< $(TOOL_RUNTIME) tests/uint64-reference.c -pthread -lm -o $@
check-uint64: build/tooling/tests/uint64 build/tooling/tests/uint64-o0
	$(LIMITED) ./build/tooling/tests/uint64-o0
	$(LIMITED) ./build/tooling/tests/uint64

check check-portable: check-uint64
