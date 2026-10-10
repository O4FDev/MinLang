# Native GUI integration needs a logged-in macOS desktop session.
.PHONY: check-macos
check-macos: build/minyarc build/minyar-default-runtime.o
	$${MINYAR_PYTHON:-/usr/bin/python3} tests/macos.py

# HTTP requests through NSURLSession against a local server.
.PHONY: check-http
check-http: build/minyarc build/minyar-default-runtime.o
	$${MINYAR_PYTHON:-python3} tests/http-package.py

.PHONY: check-swiftui
check-swiftui:
	$${MINYAR_PYTHON:-/usr/bin/python3} tests/swiftui.py

.PHONY: check-native-syntax
check-native-syntax:
	$${MINYAR_PYTHON:-/usr/bin/python3} scripts/native-syntax-check.py

MINYAR_NATIVE_HOST := $(if $(filter Linux,$(shell uname -s)),linux,macosx)
MINYAR_NATIVE_SWIFTC ?= build/native-toolchain/build/Ninja-ReleaseAssert/swift-$(MINYAR_NATIVE_HOST)-$(shell uname -m)/bin/swiftc
.PHONY: check-native-compiler
check-native-compiler: check-native-project
	$${MINYAR_PYTHON:-/usr/bin/python3} tests/native-swift/compiler.py --compiler "$(MINYAR_NATIVE_SWIFTC)"

.PHONY: check-native-project
check-native-project:
	$${MINYAR_PYTHON:-/usr/bin/python3} tests/native-swift/project.py

.PHONY: check-native-linux
check-native-linux: check-native-project
	$${MINYAR_PYTHON:-/usr/bin/python3} tests/native-swift/linux.py --compiler "$(MINYAR_NATIVE_SWIFTC)"

# Real renders through the graphics package (needs a macOS desktop session).
.PHONY: check-graphics-render
check-graphics-render: build/minyarc
	$${MINYAR_PYTHON:-/usr/bin/python3} tests/graphics-render.py
