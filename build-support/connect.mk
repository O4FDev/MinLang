# Connect protocol server and client (library/connect.min) over the shared rpc
# handler API (library/rpc.min). check-connect needs no network.
build/tooling/tests/connect-test.ll: tests/net-fixtures.min
.PHONY: check-connect
check-connect: build/minyarc build/minyar-runtime.o build/tooling/tests/connect-test
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/connect-test

check check-portable: check-connect
