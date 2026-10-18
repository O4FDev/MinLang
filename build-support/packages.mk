build/tooling/tests/package-git: TOOL_NATIVE = tools/clang-driver-host.c

.PHONY: check-package-git
check-package-git: build/tooling/tools/project-cli build/tooling/tests/package-git build/tooling/tools/clang-driver build/minyar-module-build
	./build/tooling/tests/package-git "$(CURDIR)/minyar"

check check-portable: check-package-git
