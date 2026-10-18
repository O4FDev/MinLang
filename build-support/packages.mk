build/tooling/tests/package-git: TOOL_NATIVE = tools/clang-driver-host.c

.PHONY: check-package-git
check-package-git: build/tooling/tools/project-cli build/tooling/tests/package-git build/tooling/tools/clang-driver build/minyar-module-build
	./build/tooling/tests/package-git "$(CURDIR)/minyar"

check check-portable: check-package-git

.PHONY: check-paint-package
check-paint-package: build/tooling/tools/project-cli build/tooling/tools/clang-driver build/minyar-module-build
	@test -n "$(MINYAR_PAINT_SOURCE)" || { echo 'set MINYAR_PAINT_SOURCE to the separate minyar-paint repository'; exit 1; }
	python3 tests/paint-package.py "$(CURDIR)/minyar" "$(MINYAR_PAINT_SOURCE)" "$(CURDIR)/examples/gallery/paint"
