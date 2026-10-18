# JSON value preservation and HTTP framing/resource limits through public APIs.
ifneq ($(OS),Windows_NT)
.PHONY: check-library-contracts
build/tooling/tests/library-contracts.ll: tests/net-fixtures.min library/json.min
build/tooling/tests/library-contracts: build/tooling/tools/clang-driver tests/library-contracts-client.min tests/library-contracts-peer.c
check-library-contracts: build/minyarc build/minyar-default-runtime.o build/tooling/tests/library-contracts
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/library-contracts

check check-portable: check-library-contracts
endif
