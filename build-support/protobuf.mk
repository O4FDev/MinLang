# Protocol Buffers: the runtime's wire format, and protoc-gen-minyar run under
# protoc against its own bindings and the generated-code fixtures.
.PHONY: check-protobuf check-protoc-gen-minyar

check-protobuf: build/minyarc build/tooling/tests/protobuf-test
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/protobuf-test

# Generated messages can refer to each other, so programs link the runtime that
# collects cycles.
build/tooling/tools/protoc-gen-minyar/main: TOOL_RUNTIME = build/testing/cycle-runtime.o
build/tooling/tools/protoc-gen-minyar/main: build/testing/cycle-runtime.o

check-protoc-gen-minyar: build/minyarc-modules build/testing/cycle-runtime.o build/tooling/tools/protoc-gen-minyar/main build/tooling/tests/protoc-gen-minyar-test
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) sh scripts/needs-command.sh protoc check-protoc-gen-minyar "it runs the plugin under protoc" ./build/tooling/tests/protoc-gen-minyar-test

check check-portable: check-protobuf check-protoc-gen-minyar
