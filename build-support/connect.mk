# Connect protocol server and client (library/connect.min) over the shared rpc
# handler API (library/rpc.min). check-connect needs no network.
build/tooling/tests/connect-test.ll: tests/net-fixtures.min
.PHONY: check-connect
# Cases link the cycle runtime: open calls and their responders form traced cycles.
# gzip.min links the deflate native, so the launcher builds it at O0 and O2.
check-connect: build/minyarc build/minyar-runtime.o build/minyar-default-runtime.o build/testing/cycle-runtime.o build/tooling/tests/connect-test
	MINYAR_TEST_RUNTIME="./build/testing/cycle-runtime.o" MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/connect-test
	mkdir -p build/connect
	for mode in --debug --release; do \
		MINYAR_CLANG="$(LLVM_CC)" $(LIMITED) ./minyar $$mode tests/connect/gzip.min -o build/connect/gzip >/dev/null && \
		./build/connect/gzip > build/connect/gzip.out && cmp tests/connect/gzip.out build/connect/gzip.out || exit 1; \
	done

check check-portable: check-connect
