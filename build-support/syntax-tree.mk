.PHONY: check-declaration-index
check-declaration-index: build/minyarc build/minyar-runtime.o build/tooling/tests/declaration-index
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/declaration-index

check-portable check: check-declaration-index

.PHONY: check-declaration-cache
check-declaration-cache: build/minyarc-modules build/minyar-module-build build/minyar-runtime.o build/tooling/tests/incremental-module-delta
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/incremental-module-delta

.PHONY: check-syntax-tree
check-syntax-tree: build/minyarc build/minyar-runtime.o build/tooling/tests/syntax-tree
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/syntax-tree

check-portable check: check-syntax-tree

build/tooling/tests/declaration-index.ll build/tooling/tests/syntax-tree.ll: tests/frontend-fixtures.min
