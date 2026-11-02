# Protocol Buffers: the runtime's wire format, protoc-gen-minyar run under
# protoc against its own bindings and the generated-code fixtures, and Google's
# conformance suite against the generated code.
.PHONY: check-protobuf check-protoc-gen-minyar check-protobuf-conformance

check-protobuf: build/minyarc build/tooling/tests/protobuf-test
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/protobuf-test

# Generated messages can refer to each other, so programs link the runtime that
# collects cycles.
build/tooling/tools/protoc-gen-minyar/main: TOOL_RUNTIME = build/testing/cycle-runtime.o
build/tooling/tools/protoc-gen-minyar/main: build/testing/cycle-runtime.o

check-protoc-gen-minyar: build/minyarc-modules build/testing/cycle-runtime.o build/tooling/tools/protoc-gen-minyar/main build/tooling/tests/protoc-gen-minyar-test
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) sh scripts/needs-command.sh protoc check-protoc-gen-minyar "it runs the plugin under protoc" ./build/tooling/tests/protoc-gen-minyar-test

# The runner is built from pinned sources against the installed libprotobuf
# 36.2; this downloads them once. Without a runner the check reports SKIP. The
# suite makes about 2,800 pipe round trips to the testee, which background
# priority (LIMITED) stretches from seconds to tens of minutes on macOS, so the
# check runs at normal priority; the runner times out each test itself.
PROTOBUF_CONFORMANCE_RUNNER ?= build/protobuf-conformance/conformance_test_runner
build/protobuf-conformance/conformance_test_runner: tools/protoc-gen-minyar/conformance-runner.sh
	sh tools/protoc-gen-minyar/conformance-runner.sh $@

check-protobuf-conformance: build/minyarc-modules build/testing/cycle-runtime.o build/tooling/runtime/native/system.o build/tooling/runtime/native/files.o build/tooling/tools/protoc-gen-minyar/main build/tooling/tests/protobuf-conformance-test
	MINYAR_TEST_CLANG="$(TEST_CLANG)" sh scripts/needs-command.sh protoc check-protobuf-conformance "it generates the conformance testee" ./build/tooling/tests/protobuf-conformance-test "$(PROTOBUF_CONFORMANCE_RUNNER)"

check check-portable: check-protobuf check-protoc-gen-minyar check-protobuf-conformance
