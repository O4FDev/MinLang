NATIVE_HOST_SOURCES = scripts/native-host.min
NATIVE_SWIFT_SOURCES = $(NATIVE_HOST_SOURCES) scripts/native_project.min scripts/macos-app.min scripts/native-swift.min
MACOS_GATE_SOURCES = $(NATIVE_HOST_SOURCES) tests/macos-native-gate.min
build/tooling/scripts/native-swift.ll build/tooling/scripts/native-frontend.ll build/tooling/tests/swiftui.ll build/tooling/tests/native-swift/compiler.ll: $(NATIVE_SWIFT_SOURCES)
build/tooling/scripts/macos-app.ll build/tooling/tests/macos-packaging.ll: $(NATIVE_HOST_SOURCES) scripts/macos-app.min
build/tooling/tests/native-swift/project.ll: $(NATIVE_HOST_SOURCES) scripts/native_project.min
build/tooling/scripts/native-toolchain.ll: $(NATIVE_HOST_SOURCES)
build/tooling/scripts/native-syntax-check.ll: $(NATIVE_HOST_SOURCES) scripts/native-toolchain.min
build/tooling/tests/macos.ll build/tooling/tests/native-graphics.ll build/tooling/tests/graphics-render.ll build/tooling/tests/native-swift/linux.ll: $(NATIVE_HOST_SOURCES)
build/tooling/tests/macos-network.ll build/tooling/tests/macos-services.ll build/tooling/tests/desktop-native.ll build/tooling/tests/keychain-native.ll: $(MACOS_GATE_SOURCES)

# Native GUI integration needs a logged-in macOS desktop session.
.PHONY: check-macos
check-macos: build/minyarc build/minyar-default-runtime.o build/tooling/tests/macos build/tooling/tests/macos-packaging build/tooling/scripts/macos-app
	./build/tooling/tests/macos "$(CURDIR)/build/tooling/scripts/macos-app" "$(CURDIR)/build/tooling/tests/macos-packaging"

# HTTP requests through NSURLSession against a local server.
.PHONY: check-http
build/tooling/tests/http-package-test: TOOL_NATIVE = runtime/native/net.c
build/tooling/tests/http-package-test: runtime/native/net.c
check-http: build/minyarc build/minyar-default-runtime.o build/tooling/tests/http-package-test
	./build/tooling/tests/http-package-test

.PHONY: check-swiftui
check-swiftui: build/tooling/tests/swiftui build/tooling/scripts/native-swift
	./build/tooling/tests/swiftui

.PHONY: check-native-syntax
check-native-syntax: build/tooling/scripts/native-syntax-check
	./build/tooling/scripts/native-syntax-check

MINYAR_NATIVE_HOST := $(if $(filter Linux,$(shell uname -s)),linux,macosx)
MINYAR_NATIVE_SWIFTC ?= build/native-toolchain/build/Ninja-ReleaseAssert/swift-$(MINYAR_NATIVE_HOST)-$(shell uname -m)/bin/swiftc
.PHONY: check-native-compiler
check-native-compiler: check-native-project build/tooling/tests/native-swift/compiler build/tooling/scripts/native-frontend
	./build/tooling/tests/native-swift/compiler --compiler "$(MINYAR_NATIVE_SWIFTC)"

.PHONY: check-native-project
check-native-project: build/tooling/tests/native-swift/project
	./build/tooling/tests/native-swift/project

.PHONY: check-native-linux
check-native-linux: check-native-project build/tooling/tests/native-swift/linux build/tooling/scripts/native-frontend
	./build/tooling/tests/native-swift/linux --compiler "$(MINYAR_NATIVE_SWIFTC)"

# Real renders through the graphics package (needs a macOS desktop session).
.PHONY: check-graphics-render
check-graphics-render: build/minyarc build/tooling/tests/graphics-render
	./build/tooling/tests/graphics-render

# AppKit with kqueue networking, desktop services, status items and Keychain identities, in native and sanitizer builds.
.PHONY: check-macos-network check-desktop-native check-macos-services check-keychain-native
check-macos-network: build/minyarc build/minyar-default-runtime.o build/tooling/tests/macos-network
	./build/tooling/tests/macos-network

check-desktop-native: build/minyarc build/minyar-default-runtime.o build/tooling/tests/desktop-native
	./build/tooling/tests/desktop-native

check-macos-services: build/minyarc build/minyar-default-runtime.o build/tooling/tests/macos-services
	./build/tooling/tests/macos-services

check-keychain-native: build/tooling/tests/keychain-native
	./build/tooling/tests/keychain-native

.PHONY: check-schannel-framing check-schannel-framing-sanitize

build/schannel-framing: tests/schannel-framing.c runtime/native/schannel_framing.h build/.toolchain.json | build
	$(LIMITED) "$(CC)" $(CFLAGS) $< -o $@

build/schannel-framing-sanitize: tests/schannel-framing.c runtime/native/schannel_framing.h build/.toolchain.json | build
	$(SANITIZER_LIMITED) "$(CC)" $(SANITIZER_FLAGS) -std=c11 -Wall -Wextra -Werror $< -o $@

check-schannel-framing: build/schannel-framing
	$(LIMITED) ./build/schannel-framing

check-schannel-framing-sanitize: build/schannel-framing-sanitize
	$(SANITIZER_LIMITED) ./build/schannel-framing-sanitize

check check-portable: check-schannel-framing
check-sanitize: check-schannel-framing-sanitize
