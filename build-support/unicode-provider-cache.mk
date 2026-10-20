.PHONY: check-unicode-provider-cache

UNICODE_PROVIDER_CACHE_INPUTS = runtime/native/unicode.c runtime/native/unicode_data.c runtime/minyar_native.h runtime/native/unicode_case_data.h $(wildcard vendor/utf8proc/*)

build/tooling/tests/unicode-provider-cache: TOOL_NATIVE = tests/toolchain-files.c
build/tooling/tests/unicode-provider-cache: tests/toolchain-files.c
build/tooling/tests/unicode-provider-cache.ll: tests/toolchain-files.min tests/release-support.min

check-unicode-provider-cache: build/tooling/tools/clang-driver build/tooling/tests/unicode-provider-cache $(UNICODE_PROVIDER_CACHE_INPUTS)
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/unicode-provider-cache

check check-portable: check-unicode-provider-cache
