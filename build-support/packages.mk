build/tooling/tests/package-git: TOOL_NATIVE = tools/clang-driver-host.c
build/tooling/tests/package-git: tools/clang-driver-host.c
build/tooling/tools/registry-cli: TOOL_NATIVE = tools/clang-driver-host.c runtime/native/net.c
build/tooling/tools/registry-cli: tools/clang-driver-host.c runtime/native/net.c runtime/minyar_native.h

.PHONY: check-package-git
check-package-git: build/tooling/tools/project-cli build/tooling/tests/package-git build/tooling/tools/clang-driver build/minyar-module-build
	"./build/tooling/tests/package-git" "$(CURDIR)/minyar"

.PHONY: check-registry
check-registry: build/tooling/tools/project-cli build/tooling/tools/registry-cli build/tooling/tools/clang-driver build/minyar-module-build
	python3 "tests/registry.py" "$(CURDIR)/minyar" "$(CURDIR)/build/tooling/tools/registry-cli" "$(CURDIR)"

.PHONY: check-toolchain-install
check-toolchain-install: build/tooling/tools/registry-cli
	python3 "tests/toolchain-install.py" "$(CURDIR)/install" "$(CURDIR)/build/tooling/tools/registry-cli"

ifeq ($(filter Windows_NT,$(OS))$(filter MSYS% MINGW% CYGWIN%,$(shell uname -s)),)
check check-portable: check-package-git check-registry check-toolchain-install
endif

.PHONY: check-paint-package
check-paint-package: build/tooling/tools/project-cli build/tooling/tools/clang-driver build/minyar-module-build
	@test -n "$(MINYAR_PAINT_SOURCE)" || { echo 'set MINYAR_PAINT_SOURCE to the separate minyar-paint repository'; exit 1; }
	python3 "tests/paint-package.py" "$(CURDIR)/minyar" "$(MINYAR_PAINT_SOURCE)" "$(CURDIR)/examples/gallery/paint"
