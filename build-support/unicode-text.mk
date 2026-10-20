.PHONY: check-unicode-text check-unicode-conformance check-unicode-launcher check-unicode-text-sanitize

UNICODE_TEXT_SOURCES = runtime/native/unicode.c $(wildcard vendor/utf8proc/*)
UNICODE_TEXT_CORPUS = $(wildcard tests/fixtures/unicode-18.0.0/*)

check-unicode-text: build/minyarc build/minyar-runtime.o build/tooling/tests/unicode-text $(UNICODE_TEXT_SOURCES) examples/gallery/unicode-text.min
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/unicode-text

build/unicode-conformance-o0: build/tooling/tests/unicode-conformance.ll build/minyar-runtime.o $(UNICODE_TEXT_SOURCES) | build
	$(LIMITED) "$(LLVM_CC)" -O0 -Wno-override-module "$<" build/minyar-runtime.o runtime/native/unicode.c -lm -o "$@"

build/unicode-conformance-o2: build/tooling/tests/unicode-conformance.ll build/minyar-runtime.o $(UNICODE_TEXT_SOURCES) | build
	$(LIMITED) "$(LLVM_CC)" -O2 -Wno-override-module "$<" build/minyar-runtime.o runtime/native/unicode.c -lm -o "$@"

check-unicode-conformance: build/unicode-conformance-o0 build/unicode-conformance-o2 $(UNICODE_TEXT_CORPUS)
	$(LIMITED) ./build/unicode-conformance-o0
	$(LIMITED) ./build/unicode-conformance-o2

check-unicode-launcher: build/minyarc build/tooling/tools/clang-driver $(UNICODE_TEXT_SOURCES) examples/gallery/unicode-text.min tests/unicode-text.stdout
	$(LIMITED) ./minyar examples/gallery/unicode-text.min -o build/unicode-gallery
	$(LIMITED) ./build/unicode-gallery > build/unicode-gallery.stdout
	cmp tests/unicode-text.stdout build/unicode-gallery.stdout
	$(LIMITED) ./minyar --release examples/gallery/unicode-text.min -o build/unicode-gallery-release
	$(LIMITED) ./build/unicode-gallery-release > build/unicode-gallery-release.stdout
	cmp tests/unicode-text.stdout build/unicode-gallery-release.stdout

build/unicode-conformance-sanitize: build/tooling/tests/unicode-conformance.ll build/minyar-runtime-sanitize.o $(UNICODE_TEXT_SOURCES) | build
	$(SANITIZER_LIMITED) "$(LLVM_CC)" $(SANITIZER_FLAGS) "$<" build/minyar-runtime-sanitize.o runtime/native/unicode.c -lm -o "$@"

check-unicode-text-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/unicode-text $(UNICODE_TEXT_SOURCES) build/unicode-conformance-sanitize $(UNICODE_TEXT_CORPUS)
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/unicode-text
	$(NATIVE_SANITIZER_ENV) $(SANITIZER_LIMITED) ./build/unicode-conformance-sanitize

check check-portable: check-unicode-text check-unicode-conformance check-unicode-launcher
check-sanitize: check-unicode-text-sanitize
