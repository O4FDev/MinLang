build/tooling/tools/live-build-cli build/tooling/tests/live-transform: TOOL_NATIVE = tools/clang-driver-host.c
build/tooling/tools/live-build-cli build/tooling/tests/live-transform: tools/clang-driver-host.c

build/tooling/tools/repl-cli: build/tooling/tools/repl-cli.ll build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS) tools/clang-driver-host.c tools/repl-host.c
	"$(LLVM_CC)" $(LLVM_FLAGS) $< build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS) tools/clang-driver-host.c tools/repl-host.c -pthread -lm $(if $(filter Linux,$(shell uname -s)),-Wl$(comma)--export-dynamic -ldl,-Wl$(comma)-export_dynamic) -o $@

comma := ,

.PHONY: check-minyar-repl
check-minyar-repl: build/tooling/tools/repl-cli build/minyarc
	python3 tests/repl.py "$(CURDIR)/minyar"

.PHONY: check-live-programming check-live-transform check-live-hot
check-live-programming: build/tooling/tools/project-cli build/tooling/tools/clang-driver build/minyarc-modules build/minyar-module-build build/minyar-default-runtime.o build/minyar-default-runtime-release.ll
	python3 tests/live-programming.py "$(CURDIR)/minyar"

check-live-transform: build/tooling/tests/live-transform
	./build/tooling/tests/live-transform

check-live-hot: build/tooling/tools/project-cli build/tooling/tools/live-build-cli build/tooling/tools/clang-driver build/minyarc-modules build/minyar-module-build build/minyar-default-runtime.o
	python3 tests/live-hot.py "$(CURDIR)/minyar"

check: check-live-programming check-live-transform check-live-hot check-minyar-repl
