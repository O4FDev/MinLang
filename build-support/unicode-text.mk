.PHONY: check-unicode-text check-unicode-conformance check-unicode-launcher check-unicode-text-sanitize

UNICODE_TEXT_IMPLEMENTATION = runtime/native/unicode.c runtime/native/unicode_data.c
UNICODE_TEXT_SOURCES = $(UNICODE_TEXT_IMPLEMENTATION) runtime/native/unicode_case_data.h $(wildcard vendor/utf8proc/*)
UNICODE_TEXT_CORPUS = $(wildcard tests/fixtures/unicode-18.0.0/*)

runtime/native/unicode_case_data.h: tools/generate-unicode-case.py tests/fixtures/unicode-18.0.0/SpecialCasing.txt tests/fixtures/unicode-18.0.0/DerivedCoreProperties.txt
	python3 tools/generate-unicode-case.py

.PHONY: check-unicode-case-data check-unicode-case check-unicode-case-sanitize
check-unicode-case-data: runtime/native/unicode_case_data.h
	python3 tools/generate-unicode-case.py --check

build/unicode-case-conformance-o0: build/tooling/tests/unicode-case-conformance.ll build/minyar-runtime.o $(UNICODE_TEXT_SOURCES)
	$(LIMITED) "$(LLVM_CC)" -O0 -Wno-override-module "$<" build/minyar-runtime.o $(UNICODE_TEXT_IMPLEMENTATION) -lm -o "$@"

build/unicode-case-conformance-o2: build/tooling/tests/unicode-case-conformance.ll build/minyar-runtime.o $(UNICODE_TEXT_SOURCES)
	$(LIMITED) "$(LLVM_CC)" -O2 -Wno-override-module "$<" build/minyar-runtime.o $(UNICODE_TEXT_IMPLEMENTATION) -lm -o "$@"

check-unicode-case: build/minyarc build/minyar-runtime.o build/tooling/tests/unicode-case $(UNICODE_TEXT_SOURCES) build/unicode-case-conformance-o0 build/unicode-case-conformance-o2 $(UNICODE_TEXT_CORPUS)
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/unicode-case
	$(LIMITED) ./build/unicode-case-conformance-o0
	$(LIMITED) ./build/unicode-case-conformance-o2

build/unicode-case-conformance-sanitize: build/tooling/tests/unicode-case-conformance.ll build/minyar-runtime-sanitize.o $(UNICODE_TEXT_SOURCES)
	$(SANITIZER_LIMITED) "$(LLVM_CC)" $(SANITIZER_FLAGS) "$<" build/minyar-runtime-sanitize.o $(UNICODE_TEXT_IMPLEMENTATION) -lm -o "$@"

check-unicode-case-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/unicode-case $(UNICODE_TEXT_SOURCES) build/unicode-case-conformance-sanitize $(UNICODE_TEXT_CORPUS)
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/unicode-case
	$(NATIVE_SANITIZER_ENV) $(SANITIZER_LIMITED) ./build/unicode-case-conformance-sanitize

check-unicode-text: build/minyarc build/minyar-runtime.o build/tooling/tests/unicode-text $(UNICODE_TEXT_SOURCES) examples/gallery/unicode-text.min
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/unicode-text

build/unicode-conformance-o0: build/tooling/tests/unicode-conformance.ll build/minyar-runtime.o $(UNICODE_TEXT_SOURCES) | build
	$(LIMITED) "$(LLVM_CC)" -O0 -Wno-override-module "$<" build/minyar-runtime.o $(UNICODE_TEXT_IMPLEMENTATION) -lm -o "$@"

build/unicode-conformance-o2: build/tooling/tests/unicode-conformance.ll build/minyar-runtime.o $(UNICODE_TEXT_SOURCES) | build
	$(LIMITED) "$(LLVM_CC)" -O2 -Wno-override-module "$<" build/minyar-runtime.o $(UNICODE_TEXT_IMPLEMENTATION) -lm -o "$@"

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
	$(SANITIZER_LIMITED) "$(LLVM_CC)" $(SANITIZER_FLAGS) "$<" build/minyar-runtime-sanitize.o $(UNICODE_TEXT_IMPLEMENTATION) -lm -o "$@"

check-unicode-text-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/unicode-text $(UNICODE_TEXT_SOURCES) build/unicode-conformance-sanitize $(UNICODE_TEXT_CORPUS)
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/unicode-text
	$(NATIVE_SANITIZER_ENV) $(SANITIZER_LIMITED) ./build/unicode-conformance-sanitize

.PHONY: check-unicode-normalization check-unicode-normalization-sanitize

build/unicode-normalization-o0: tests/unicode-normalization.c $(UNICODE_TEXT_SOURCES) runtime/minyar_native.h | build
	$(LIMITED) "$(LLVM_CC)" $(CPPFLAGS) $(CFLAGS) -O0 -DMINYAR_UNICODE_NORMALIZATION_TESTING "$<" $(UNICODE_TEXT_IMPLEMENTATION) -lm -o "$@"

build/unicode-normalization-o2: tests/unicode-normalization.c $(UNICODE_TEXT_SOURCES) runtime/minyar_native.h | build
	$(LIMITED) "$(LLVM_CC)" $(CPPFLAGS) $(CFLAGS) -O2 -DMINYAR_UNICODE_NORMALIZATION_TESTING "$<" $(UNICODE_TEXT_IMPLEMENTATION) -lm -o "$@"

check-unicode-normalization: build/unicode-normalization-o0 build/unicode-normalization-o2
	$(LIMITED) ./build/unicode-normalization-o0
	$(LIMITED) ./build/unicode-normalization-o2

build/unicode-normalization-sanitize: tests/unicode-normalization.c $(UNICODE_TEXT_SOURCES) runtime/minyar_native.h | build
	$(SANITIZER_LIMITED) "$(LLVM_CC)" $(CPPFLAGS) $(CFLAGS) $(SANITIZER_FLAGS) -DMINYAR_UNICODE_NORMALIZATION_TESTING "$<" $(UNICODE_TEXT_IMPLEMENTATION) -lm -o "$@"

check-unicode-normalization-sanitize: build/unicode-normalization-sanitize
	$(NATIVE_SANITIZER_ENV) $(SANITIZER_LIMITED) ./build/unicode-normalization-sanitize

.PHONY: check-unicode-installed
build/tooling/tests/unicode-installed.ll: tests/release-support.min
check-unicode-installed: build/tooling/tests/unicode-installed $(MINYAR_INSTALL_FRONTENDS) build/tooling/tools/clang-driver build/minyar-module-build build/minyar-default-runtime.o build/minyar-default-runtime-release.ll $(UNICODE_TEXT_SOURCES)
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/unicode-installed "$(CURDIR)"

check check-portable: check-unicode-text check-unicode-conformance check-unicode-launcher check-unicode-case check-unicode-case-data check-unicode-normalization check-unicode-installed
check-sanitize: check-unicode-text-sanitize check-unicode-case-sanitize check-unicode-normalization-sanitize
