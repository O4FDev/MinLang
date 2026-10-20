.PHONY: check-bootstrap-native
check-bootstrap-native: build/stage0 build/minyar-compiler-runtime.ll build/tooling/tests/bootstrap-native
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/bootstrap-native

check check-portable: check-bootstrap-native

build/tooling/tests/diagnostics.ll: tests/frontend-fixtures.min

check-diagnostics: build/minyar-module-build

.PHONY: check-explain
check-explain: build/minyarc
	python3 "tests/explain.py" "$(CURDIR)/build/minyarc" "$(CURDIR)/minyar"

check check-portable: check-explain

build/tooling/tests/bootstrap-native.ll: tests/frontend-fixtures.min tests/diagnostics/recovery-native.min

build/tooling/tests/runtime-diagnostics.ll: tests/release-support.min

.PHONY: check-runtime-diagnostics
check-runtime-diagnostics: build/minyarc build/minyar-runtime.o build/minyar-module-build build/tooling/tests/runtime-diagnostics build/testing/cycle-runtime.o
	MINYAR_TEST_LTO_FLAGS='$(subst ','"'"',$(COMPILER_LTO_FLAGS))' MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/runtime-diagnostics

check check-portable: check-runtime-diagnostics
