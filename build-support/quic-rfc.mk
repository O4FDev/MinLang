# Public launcher builds every RFC fixture at O0/O2; each author driver runs all cases.
# The gate itself is split into independent pieces: one optimisation level of one
# driver group each, so no piece carries both levels or more than one driver family.
# check-quic-rfc / check-quic-rfc-sanitize stay as recipe-less aggregates of the pieces.
QUIC_RFC_PARTS = o0-migration o0-cipher o0-network o2-migration o2-cipher o2-network
QUIC_RFC_SANITIZE_PARTS = sanitize-o0-migration sanitize-o0-cipher sanitize-o0-network \
    sanitize-o2-migration sanitize-o2-cipher sanitize-o2-network
.PHONY: check-quic-rfc check-quic-rfc-sanitize check-quic-protocol-artifacts \
    $(QUIC_RFC_PARTS:%=check-quic-rfc-%) $(QUIC_RFC_SANITIZE_PARTS:%=check-quic-rfc-%)
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
	@set -e; rm -rf -- build/quic-protocol-artifacts.*; artifacts=$$(mktemp -d "$(abspath build)/quic-protocol-artifacts.XXXXXXXX"); $(LIMITED) ./build/tooling/tests/quic-protocol-artifacts --artifacts "$$artifacts/run"

# Link provenance retains Clang itself; permit files up to 512 MiB here.
check-quic-rfc check-quic-rfc-sanitize $(QUIC_RFC_PARTS:%=check-quic-rfc-%) $(QUIC_RFC_SANITIZE_PARTS:%=check-quic-rfc-%): export MINYAR_MAX_FILE_BLOCKS ?= 1048576

# A piece is one optimisation level of one driver group: it builds only the binaries
# its drivers execute. The local/vn pieces bind MINYAR_QUIC_RFC_PORT, +1 and +2, so
# every network piece owns its own block (44320/44330 native, 44340/44350 sanitized);
# the migration/cipher pieces bind nothing and keep the historical sanitize port 44310.

check-quic-rfc-o0-migration: check-quic-protocol-artifacts $(QUIC_RFC_FRONTENDS) $(QUIC_RFC_INPUTS) | build
	./build/tooling/tests/quic-rfc-harness
	@set -e; rm -rf -- build/quic-rfc-native-o0-migration.*; artifacts=$$(mktemp -d "$(abspath build)/quic-rfc-native-o0-migration.XXXXXXXX"); MINYAR_CLANG="$(LLVM_CC)" MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/quic-rfc --optimization 0 --drivers migration --artifacts "$$artifacts/run"

check-quic-rfc-o0-cipher: check-quic-protocol-artifacts $(QUIC_RFC_FRONTENDS) $(QUIC_RFC_INPUTS) | build
	./build/tooling/tests/quic-rfc-harness
	@set -e; rm -rf -- build/quic-rfc-native-o0-cipher.*; artifacts=$$(mktemp -d "$(abspath build)/quic-rfc-native-o0-cipher.XXXXXXXX"); MINYAR_CLANG="$(LLVM_CC)" MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/quic-rfc --optimization 0 --drivers cipher --artifacts "$$artifacts/run"

check-quic-rfc-o0-network: check-quic-protocol-artifacts $(QUIC_RFC_FRONTENDS) $(QUIC_RFC_INPUTS) | build
	MINYAR_QUIC_RFC_PORT=44320 ./build/tooling/tests/quic-rfc-harness
	@set -e; rm -rf -- build/quic-rfc-native-o0-network.*; artifacts=$$(mktemp -d "$(abspath build)/quic-rfc-native-o0-network.XXXXXXXX"); MINYAR_QUIC_RFC_PORT=44320 MINYAR_CLANG="$(LLVM_CC)" MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/quic-rfc --optimization 0 --drivers local,vn --artifacts "$$artifacts/run"

check-quic-rfc-o2-migration: check-quic-protocol-artifacts $(QUIC_RFC_FRONTENDS) $(QUIC_RFC_INPUTS) | build
	./build/tooling/tests/quic-rfc-harness
	@set -e; rm -rf -- build/quic-rfc-native-o2-migration.*; artifacts=$$(mktemp -d "$(abspath build)/quic-rfc-native-o2-migration.XXXXXXXX"); MINYAR_CLANG="$(LLVM_CC)" MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/quic-rfc --optimization 2 --drivers migration --artifacts "$$artifacts/run"

check-quic-rfc-o2-cipher: check-quic-protocol-artifacts $(QUIC_RFC_FRONTENDS) $(QUIC_RFC_INPUTS) | build
	./build/tooling/tests/quic-rfc-harness
	@set -e; rm -rf -- build/quic-rfc-native-o2-cipher.*; artifacts=$$(mktemp -d "$(abspath build)/quic-rfc-native-o2-cipher.XXXXXXXX"); MINYAR_CLANG="$(LLVM_CC)" MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/quic-rfc --optimization 2 --drivers cipher --artifacts "$$artifacts/run"

check-quic-rfc-o2-network: check-quic-protocol-artifacts $(QUIC_RFC_FRONTENDS) $(QUIC_RFC_INPUTS) | build
	MINYAR_QUIC_RFC_PORT=44330 ./build/tooling/tests/quic-rfc-harness
	@set -e; rm -rf -- build/quic-rfc-native-o2-network.*; artifacts=$$(mktemp -d "$(abspath build)/quic-rfc-native-o2-network.XXXXXXXX"); MINYAR_QUIC_RFC_PORT=44330 MINYAR_CLANG="$(LLVM_CC)" MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/quic-rfc --optimization 2 --drivers local,vn --artifacts "$$artifacts/run"

check-quic-rfc-sanitize-o0-migration: check-quic-protocol-artifacts $(QUIC_RFC_FRONTENDS) $(QUIC_RFC_INPUTS) | build
	MINYAR_QUIC_RFC_PORT=44310 ./build/tooling/tests/quic-rfc-harness
	@set -e; rm -rf -- build/quic-rfc-sanitize-o0-migration.*; artifacts=$$(mktemp -d "$(abspath build)/quic-rfc-sanitize-o0-migration.XXXXXXXX"); MINYAR_QUIC_RFC_PORT=44310 $(NATIVE_SANITIZER_ENV) MINYAR_CLANG="$(LLVM_CC)" MINYAR_TEST_CLANG="$(TEST_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/quic-rfc --optimization 0 --drivers migration --sanitize --artifacts "$$artifacts/run"

check-quic-rfc-sanitize-o0-cipher: check-quic-protocol-artifacts $(QUIC_RFC_FRONTENDS) $(QUIC_RFC_INPUTS) | build
	MINYAR_QUIC_RFC_PORT=44310 ./build/tooling/tests/quic-rfc-harness
	@set -e; rm -rf -- build/quic-rfc-sanitize-o0-cipher.*; artifacts=$$(mktemp -d "$(abspath build)/quic-rfc-sanitize-o0-cipher.XXXXXXXX"); MINYAR_QUIC_RFC_PORT=44310 $(NATIVE_SANITIZER_ENV) MINYAR_CLANG="$(LLVM_CC)" MINYAR_TEST_CLANG="$(TEST_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/quic-rfc --optimization 0 --drivers cipher --sanitize --artifacts "$$artifacts/run"

check-quic-rfc-sanitize-o0-network: check-quic-protocol-artifacts $(QUIC_RFC_FRONTENDS) $(QUIC_RFC_INPUTS) | build
	MINYAR_QUIC_RFC_PORT=44310 ./build/tooling/tests/quic-rfc-harness
	@set -e; rm -rf -- build/quic-rfc-sanitize-o0-network.*; artifacts=$$(mktemp -d "$(abspath build)/quic-rfc-sanitize-o0-network.XXXXXXXX"); MINYAR_QUIC_RFC_PORT=44340 $(NATIVE_SANITIZER_ENV) MINYAR_CLANG="$(LLVM_CC)" MINYAR_TEST_CLANG="$(TEST_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/quic-rfc --optimization 0 --drivers local,vn --sanitize --artifacts "$$artifacts/run"

check-quic-rfc-sanitize-o2-migration: check-quic-protocol-artifacts $(QUIC_RFC_FRONTENDS) $(QUIC_RFC_INPUTS) | build
	MINYAR_QUIC_RFC_PORT=44310 ./build/tooling/tests/quic-rfc-harness
	@set -e; rm -rf -- build/quic-rfc-sanitize-o2-migration.*; artifacts=$$(mktemp -d "$(abspath build)/quic-rfc-sanitize-o2-migration.XXXXXXXX"); MINYAR_QUIC_RFC_PORT=44310 $(NATIVE_SANITIZER_ENV) MINYAR_CLANG="$(LLVM_CC)" MINYAR_TEST_CLANG="$(TEST_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/quic-rfc --optimization 2 --drivers migration --sanitize --artifacts "$$artifacts/run"

check-quic-rfc-sanitize-o2-cipher: check-quic-protocol-artifacts $(QUIC_RFC_FRONTENDS) $(QUIC_RFC_INPUTS) | build
	MINYAR_QUIC_RFC_PORT=44310 ./build/tooling/tests/quic-rfc-harness
	@set -e; rm -rf -- build/quic-rfc-sanitize-o2-cipher.*; artifacts=$$(mktemp -d "$(abspath build)/quic-rfc-sanitize-o2-cipher.XXXXXXXX"); MINYAR_QUIC_RFC_PORT=44310 $(NATIVE_SANITIZER_ENV) MINYAR_CLANG="$(LLVM_CC)" MINYAR_TEST_CLANG="$(TEST_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/quic-rfc --optimization 2 --drivers cipher --sanitize --artifacts "$$artifacts/run"

check-quic-rfc-sanitize-o2-network: check-quic-protocol-artifacts $(QUIC_RFC_FRONTENDS) $(QUIC_RFC_INPUTS) | build
	MINYAR_QUIC_RFC_PORT=44310 ./build/tooling/tests/quic-rfc-harness
	@set -e; rm -rf -- build/quic-rfc-sanitize-o2-network.*; artifacts=$$(mktemp -d "$(abspath build)/quic-rfc-sanitize-o2-network.XXXXXXXX"); MINYAR_QUIC_RFC_PORT=44350 $(NATIVE_SANITIZER_ENV) MINYAR_CLANG="$(LLVM_CC)" MINYAR_TEST_CLANG="$(TEST_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/quic-rfc --optimization 2 --drivers local,vn --sanitize --artifacts "$$artifacts/run"

check-quic-rfc: $(QUIC_RFC_PARTS:%=check-quic-rfc-%) check-quic-protocol-artifacts $(QUIC_RFC_FRONTENDS) $(QUIC_RFC_INPUTS)

check-quic-rfc-sanitize: $(QUIC_RFC_SANITIZE_PARTS:%=check-quic-rfc-%) check-quic-protocol-artifacts $(QUIC_RFC_FRONTENDS) $(QUIC_RFC_INPUTS)

check check-portable check-quic: check-quic-rfc
check-sanitize check-quic-sanitize: check-quic-rfc-sanitize
