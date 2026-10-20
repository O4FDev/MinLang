.PHONY: check-debug-info
build/tooling/tests/debug-info.ll: tests/release-support.min
check-debug-info: build/minyarc build/minyar-module-build build/tooling/tools/clang-driver build/tooling/tests/debug-info
	+MINYAR_TEST_CLANG="$(LLVM_CC)" ./build/tooling/tests/debug-info

check check-portable: check-debug-info
