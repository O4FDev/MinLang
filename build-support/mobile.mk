.PHONY: check-mobile check-mobile-tools check-mobile-bridge check-mobile-gallery check-mobile-sanitize check-mobile-ios check-mobile-ios-provider check-mobile-android

check-mobile-tools:
	python3 tests/mobile-tools.py

check-mobile-bridge: build/minyarc build/testing/cycle-runtime.c
	MINYAR_TEST_CLANG="$(LLVM_CC)" python3 tests/check-mobile-bridge.py

check-mobile-sanitize: build/minyarc build/testing/cycle-runtime.c
	MINYAR_TEST_CLANG="$(LLVM_CC)" python3 tests/check-mobile-bridge.py --sanitize

check-mobile-gallery: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" python3 tests/check-mobile-gallery.py

check-mobile: check-mobile-tools check-mobile-bridge check-mobile-gallery
check check-portable: check-mobile
check-sanitize: check-mobile-sanitize

check-mobile-android: build/minyarc build/testing/cycle-runtime.c
	python3 tests/check-mobile-android.py

# SDK work only; run through the coordination lx wrapper on shared machines.
# This target never boots a Simulator or installs an application.
ifeq ($(shell uname -s),Darwin)
check-mobile-ios-provider:
	"$(LLVM_CC)" -target arm64-apple-ios16.0-simulator -isysroot "$$(xcrun --sdk iphonesimulator --show-sdk-path)" -fobjc-arc -fsyntax-only runtime/native/mobileios.m
	"$(LLVM_CC)" -target arm64-apple-ios16.0 -isysroot "$$(xcrun --sdk iphoneos --show-sdk-path)" -fobjc-arc -fsyntax-only runtime/native/mobileios.m

check-mobile-ios: build/minyarc build/testing/cycle-runtime.c
	python3 tools/mobile.py examples/mobile-hello/main.min --target ios-simulator --no-bootstrap
	python3 tools/mobile.py examples/mobile-hello/main.min --target ios-device --no-bootstrap
else
check-mobile-ios check-mobile-ios-provider:
	@echo 'SKIP check-mobile-ios: Xcode SDKs require macOS'
endif
