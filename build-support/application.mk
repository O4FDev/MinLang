APPLICATION_SOURCES = tools/application-cli.min scripts/macos-app.min scripts/native-host.min
build/tooling/tools/application-cli.ll: $(APPLICATION_SOURCES)
build/tooling/tools/application-cli: TOOL_NATIVE = tools/clang-driver-host.c
build/tooling/tools/application-cli: tools/clang-driver-host.c runtime/minyar_native.h

.PHONY: check-application-cli check-ui-source check-ui-macos
check-application-cli: build/tooling/tools/application-cli build/tooling/tools/project-cli build/tooling/tools/clang-driver build/minyar-module-build build/tooling/scripts/macos-app build/tooling/tests/macos-packaging
	python3 "tests/application-check.py" cli
	$(LIMITED) ./build/tooling/tests/macos-packaging "$(CURDIR)/build/tooling/scripts/macos-app"

check-ui-macos: check-application-cli build/minyarc build/minyar-default-runtime.o build/tooling/tools/clang-driver
	python3 "tests/application-check.py" ui --clang "$(LLVM_CC)"

check-ui-source: build/minyarc
	$(LIMITED) ./build/minyarc "tests/ui-macos.min" "build/ui-macos-contract.ll" --library library
	$(LIMITED) ./build/minyarc "examples/gallery/desktop.min" "build/harbour-gallery.ll" --library library

check check-portable: check-application-cli check-ui-source
