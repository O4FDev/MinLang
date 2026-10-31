.PHONY: check-benchmarks check-benchmarks-cli check-benchmarks-compare check-benchmarks-bothmodes

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
	+MINYAR_TEST_CLANG="$(TEST_CLANG)" ./build/tooling/tests/benchmarks-cli

check check-portable: check-benchmarks check-benchmarks-cli

# Four-language comparison suite (benchmarks/compare): correctness only. Each
# Minyar program is built at O0 and release and must print exactly what its C
# peer prints on the small workload. Timing lives in benchmarks/compare/run.py.
check-benchmarks-compare: build/minyarc build/tooling/tools/clang-driver
	$(LIMITED) env CC="$(LLVM_CC)" python3 benchmarks/compare/run.py --check

# One source, both modes (benchmarks/bothmodes): correctness only. Each Minyar
# program is built at O0 and release and run at 1 and 4 threads; every run must
# print exactly what its serial C peer prints on the small workload. Timing
# (serial Ir ratio, parallel wall ratio against std-only Rust) lives in
# benchmarks/bothmodes/run.py.
check-benchmarks-bothmodes: build/minyarc build/tooling/tools/clang-driver
	$(LIMITED) env CC="$(LLVM_CC)" python3 benchmarks/bothmodes/run.py --check

# Experimental ablation switches (tools/ablation.sh): measurement tools only.
.PHONY: check-ablation-switches
check-ablation-switches: build/minyarc build/tooling/tools/clang-driver
	$(LIMITED) env MINYAR_CLANG="$(LLVM_CC)" sh tests/ablation/switches.sh
