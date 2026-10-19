.PHONY: check-bootstrap-native
check-bootstrap-native: build/stage0 build/minyar-compiler-runtime.ll build/tooling/tests/bootstrap-native
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/bootstrap-native

check check-portable: check-bootstrap-native

build/tooling/tests/diagnostics.ll: tests/frontend-fixtures.min

check-diagnostics: build/minyar-module-build

build/tooling/tests/bootstrap-native.ll: tests/frontend-fixtures.min tests/diagnostics/recovery-native.min

.PHONY: check-runtime-diagnostics
check-runtime-diagnostics: build/minyarc build/minyar-runtime.o build/minyar-module-build build/tooling/tests/runtime-diagnostics build/testing/cycle-runtime.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/runtime-diagnostics

check check-portable: check-runtime-diagnostics
