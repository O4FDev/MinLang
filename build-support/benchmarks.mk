.PHONY: check-benchmarks check-benchmarks-cli

build/tooling/tests/benchmarks build/tooling/tests/benchmarks-cli build/tooling/tools/project-cli: TOOL_RUNTIME = build/testing/cycle-runtime.o
build/tooling/tests/benchmarks build/tooling/tests/benchmarks-cli build/tooling/tools/project-cli: build/testing/cycle-runtime.o

build/tooling/tests/benchmarks-o0: build/tooling/tests/benchmarks.ll build/tooling/tests/benchmarks build/testing/cycle-runtime.o
	"$(LLVM_CC)" $(filter-out -O%,$(LLVM_FLAGS)) -O0 "$<" build/testing/cycle-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS) -pthread -lm -o "$@"

check-benchmarks: build/tooling/tests/benchmarks build/tooling/tests/benchmarks-o0
	$(LIMITED) ./build/tooling/tests/benchmarks-o0
	$(LIMITED) ./build/tooling/tests/benchmarks

build/tooling/tests/benchmarks-cli.ll: tests/benchmarks/cli.min $(wildcard tools/*.min) $(wildcard library/*.min) build/minyarc-modules
	mkdir -p "$(@D)"
	$(LIMITED) ./build/minyarc-modules "$<" "$@" --library library

build/tooling/tests/benchmarks-cli: TOOL_NATIVE = tools/clang-driver-host.c
build/tooling/tests/benchmarks-cli: tools/clang-driver-host.c runtime/minyar_native.h

check-benchmarks-cli: build/tooling/tests/benchmarks-cli build/tooling/tools/project-cli build/tooling/tools/clang-driver build/minyar-module-build benchmarks/standard-library/src/standard-library.min
	+MINYAR_TEST_CLANG="$(LLVM_CC)" ./build/tooling/tests/benchmarks-cli

check check-portable: check-benchmarks check-benchmarks-cli
