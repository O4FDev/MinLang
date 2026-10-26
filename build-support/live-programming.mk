build/tooling/tools/live-build-cli build/tooling/tests/live-transform: TOOL_NATIVE = tools/clang-driver-host.c
build/tooling/tools/live-build-cli build/tooling/tests/live-transform: tools/clang-driver-host.c

build/tooling/tools/repl-cli: build/tooling/tools/repl-cli.ll build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS) tools/clang-driver-host.c tools/repl-host.c
	"$(LLVM_CC)" $(LLVM_FLAGS) $< build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS) tools/clang-driver-host.c tools/repl-host.c -pthread -lm $(if $(filter Linux,$(shell uname -s)),-Wl$(comma)--export-dynamic -ldl,-Wl$(comma)-export_dynamic) -o $@

comma := ,

.PHONY: check-minyar-repl
check-minyar-repl: build/tooling/tools/repl-cli build/minyarc
	python3 tests/repl.py "$(CURDIR)/minyar"

.PHONY: check-live-programming check-live-transform check-live-hot check-live-generic-names check-live-patch-load check-incremental-link
check-live-programming: build/tooling/tools/project-cli build/tooling/tools/clang-driver build/minyarc-modules build/minyar-module-build build/minyar-default-runtime.o build/minyar-default-runtime-release.ll
	python3 tests/live-programming.py "$(CURDIR)/minyar"

check-live-transform: build/tooling/tests/live-transform
	./build/tooling/tests/live-transform

check-live-hot: build/tooling/tools/project-cli build/tooling/tools/live-build-cli build/tooling/tools/clang-driver build/minyarc-modules build/minyar-module-build build/minyar-default-runtime.o
	python3 tests/live-hot.py "$(CURDIR)/minyar"

# A patch that reorders first uses of two generic instances keeps a stored closure on its own instance.
check-live-generic-names: build/tooling/tools/project-cli build/tooling/tools/live-build-cli build/tooling/tools/clang-driver build/minyarc-modules build/minyar-module-build build/minyar-default-runtime.o
	python3 tests/live-generic-names.py "$(CURDIR)/minyar"

# A function update under HTTP load: no failed request, counter state continues.
check-live-patch-load: build/tooling/tools/project-cli build/tooling/tools/live-build-cli build/tooling/tools/clang-driver build/minyarc-modules build/minyar-module-build build/minyar-default-runtime.o
	python3 tests/live-patch-load.py "$(CURDIR)/minyar"

# Watch rebuilds link cached partitions: same behaviour, one or two objects per edit.
check-incremental-link: build/tooling/tools/clang-driver build/minyarc-modules build/minyar-module-build build/minyar-default-runtime.o
	python3 tests/incremental-link.py "$(CURDIR)/minyar"

check: check-live-programming check-live-transform check-live-hot check-live-generic-names check-live-patch-load check-incremental-link check-minyar-repl
