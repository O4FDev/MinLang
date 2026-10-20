.PHONY: check-declaration-index
check-declaration-index: build/minyarc build/minyar-runtime.o build/tooling/tests/declaration-index
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/declaration-index

check-portable check: check-declaration-index

.PHONY: check-module-declaration-index
check-module-declaration-index: build/minyarc build/minyar-runtime.o build/tooling/tests/module-declaration-index
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/module-declaration-index

build/tooling/tests/module-declaration-index.ll: tests/module-declaration-index-probe.min

check-portable check: check-module-declaration-index

.PHONY: check-incremental-module-index
check-incremental-module-index: build/minyarc build/minyar-runtime.o build/tooling/tests/incremental-module-index
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/incremental-module-index

build/tooling/tests/incremental-module-index.ll: tests/incremental-module-index-probe.min

check-portable check: check-incremental-module-index

.PHONY: check-declaration-cache
check-declaration-cache: build/minyarc-modules build/minyar-module-build build/minyar-runtime.o build/tooling/tests/incremental-module-delta
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/incremental-module-delta

.PHONY: check-syntax-tree
check-syntax-tree: build/minyarc build/minyar-runtime.o build/tooling/tests/syntax-tree
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/syntax-tree

check-portable check: check-syntax-tree

build/tooling/tests/declaration-index.ll build/tooling/tests/syntax-tree.ll: tests/frontend-fixtures.min
