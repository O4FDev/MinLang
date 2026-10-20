.PHONY: check-debug-info check-debugger-values
build/tooling/tests/debug-info.ll: tests/release-support.min
check-debug-info: build/minyarc build/minyar-module-build build/tooling/tools/clang-driver build/tooling/tests/debug-info
	+MINYAR_TEST_CLANG="$(LLVM_CC)" ./build/tooling/tests/debug-info

build/tooling/tests/debugger-values.ll: tests/release-support.min
check-debugger-values: build/minyarc build/minyar-module-build build/tooling/tools/clang-driver build/tooling/tests/debugger-values
	+MINYAR_TEST_CLANG="$(LLVM_CC)" ./build/tooling/tests/debugger-values

check check-portable: check-debug-info check-debugger-values
