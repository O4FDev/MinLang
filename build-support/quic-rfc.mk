# Public launcher builds every RFC fixture at O0/O2; each author driver runs all cases.
.PHONY: check-quic-rfc check-quic-rfc-sanitize check-quic-protocol-artifacts
QUIC_RFC_FRONTENDS = build/minyarc build/minyarc-callbacks build/minyarc-errors-request build/minyarc-errors
QUIC_RFC_INPUTS = minyar build/tooling/tools/clang-driver tools/llvm-sanitizer.min \
    build/tooling/tests/quic-rfc tests/quic-rfc.min build/tooling/tests/quic-rfc-harness tests/quic-rfc-harness.min \
    tests/quic-protocol-artifacts.min tests/interop/qns/endpoint.min library/quic.min library/tls.min library/tlsserver.min \
    build/tooling/tests/quic-migration-cids-test tests/quic-migration-cids-test.min tests/quic-migration-cids.min \
    build/tooling/tests/quic-cipher-policy-test tests/quic-cipher-policy-test.min tests/quic-cipher-policy.min \
    tests/quic-protocol-support.min tests/quic-test-support.min tests/quic-json.min tools/testing.min \
    build/tooling/tests/quic-qns-local tests/quic-qns-local.min build/tooling/tests/quic-vn-probe tests/quic-vn-probe.min \
    tests/interop/qns/client.min tests/interop/qns/server.min \
    $(wildcard compiler/*.patch scripts/*compiler*.py runtime/*.h runtime/native/*.h)
QUIC_PROTOCOL_DRIVERS = build/tooling/tests/quic-qns-local build/tooling/tests/quic-vn-probe
$(QUIC_PROTOCOL_DRIVERS:%=%.ll) build/tooling/tests/quic-protocol-artifacts.ll build/tooling/tests/quic-rfc-harness.ll: tests/quic-protocol-support.min tests/quic-test-support.min tests/quic-json.min
build/tooling/tests/quic-rfc.ll build/tooling/tests/quic-rfc-harness.ll: tests/quic-rfc.min tests/quic-test-support.min tests/quic-json.min
$(QUIC_PROTOCOL_DRIVERS): TOOL_NATIVE = runtime/native/net.c runtime/native/sha256.c
$(QUIC_PROTOCOL_DRIVERS): TOOL_LIBS = $(TOOL_CRYPTO)
$(QUIC_PROTOCOL_DRIVERS): runtime/native/net.c runtime/native/sha256.c

check-quic-protocol-artifacts: build/tooling/tests/quic-protocol-artifacts build/tooling/tests/quic-qns-local build/tooling/tests/quic-vn-probe tests/quic-protocol-artifacts.min tests/quic-protocol-support.min tests/quic-qns-local.min tests/quic-vn-probe.min tests/interop/qns/endpoint.min | build
	@set -e; artifacts=$$(mktemp -d "$(abspath build)/quic-protocol-artifacts.XXXXXXXX"); $(LIMITED) ./build/tooling/tests/quic-protocol-artifacts --artifacts "$$artifacts/run"

# Link provenance retains Clang itself; permit files up to 512 MiB here.
check-quic-rfc check-quic-rfc-sanitize: export MINYAR_MAX_FILE_BLOCKS ?= 1048576
check-quic-rfc: check-quic-protocol-artifacts $(QUIC_RFC_FRONTENDS) $(QUIC_RFC_INPUTS) | build
	./build/tooling/tests/quic-rfc-harness
	@set -e; artifacts=$$(mktemp -d "$(abspath build)/quic-rfc-native.XXXXXXXX"); MINYAR_CLANG="$(LLVM_CC)" MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/quic-rfc --optimization both --artifacts "$$artifacts/run"

check-quic-rfc-sanitize: check-quic-protocol-artifacts $(QUIC_RFC_FRONTENDS) $(QUIC_RFC_INPUTS) | build
	MINYAR_QUIC_RFC_PORT=44310 ./build/tooling/tests/quic-rfc-harness
	@set -e; artifacts=$$(mktemp -d "$(abspath build)/quic-rfc-sanitize.XXXXXXXX"); MINYAR_QUIC_RFC_PORT=44310 $(NATIVE_SANITIZER_ENV) MINYAR_CLANG="$(LLVM_CC)" MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/quic-rfc --optimization both --sanitize --artifacts "$$artifacts/run"

check check-portable check-quic: check-quic-rfc
check-sanitize check-quic-sanitize: check-quic-rfc-sanitize
