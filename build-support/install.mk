PREFIX ?= $(HOME)/.local
MINYAR_INSTALL_FRONTENDS = $(patsubst %.min,build/tooling/%,$(wildcard tools/*-cli.min))

build/tooling/tools/install-cli: build/tooling/tools/install-cli.ll build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS) tools/clang-driver-host.c runtime/minyar_native.h
	"$(LLVM_CC)" $(LLVM_FLAGS) $< build/minyar-runtime.o $(MINYAR_TOOL_NATIVE_OBJECTS) tools/clang-driver-host.c -pthread -lm -o $@

.PHONY: install install-cli check-installed-cli
install install-cli: $(MINYAR_INSTALL_FRONTENDS) build/tooling/tools/clang-driver build/minyar-module-build build/minyar-default-runtime.o build/minyar-default-runtime-release.ll
	./build/tooling/tools/install-cli --source "$(CURDIR)" --prefix "$(PREFIX)"

check-installed-cli: build/tooling/tests/installed-cli $(MINYAR_INSTALL_FRONTENDS) build/tooling/tools/clang-driver build/minyar-module-build build/minyar-default-runtime.o build/minyar-default-runtime-release.ll
	./build/tooling/tests/installed-cli "$(CURDIR)"

check check-portable: check-installed-cli
