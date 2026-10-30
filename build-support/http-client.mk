.PHONY: check-http-client
# The portable http Client: keep-alive and streaming bodies against a local fixture server.
build/tooling/tests/http-client-test.ll: tests/net-fixtures.min
check-http-client: build/minyarc build/tooling/tests/http-client-test tests/http-client/server.min tests/http-client/client.min library/http.min
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/http-client-test

ifneq ($(OS),Windows_NT)
check check-portable: check-http-client
endif
