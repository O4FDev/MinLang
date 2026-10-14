# Offline encrypted-packet accounting controls; this gate is not an official trace verdict.
.PHONY: check-quic-amplification-ledger
QUIC_LEDGER_INPUTS = tests/quic-amplification-ledger.min tests/quic-ledger-support.min tests/quic-ledger-checker.min tests/quic-ledger-crypto.c
check-quic-amplification-ledger: $(QUIC_LEDGER_INPUTS) build/tooling/tests/quic-amplification-ledger build/tooling/tests/quic-ledger-checker build/tooling/tools/clang-driver | build
	@set -e; artifacts=$$(mktemp -d "$(abspath build)/quic-ledger.XXXXXXXX"); MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/quic-amplification-ledger --artifacts "$$artifacts/run"

QUIC_LEDGER_TOOLS = build/tooling/tests/quic-amplification-ledger build/tooling/tests/quic-ledger-checker
$(QUIC_LEDGER_TOOLS:%=%.ll): tests/quic-ledger-support.min tests/quic-test-support.min tests/quic-json.min
$(QUIC_LEDGER_TOOLS): TOOL_NATIVE = tests/quic-ledger-crypto.c runtime/native/sha256.c
$(QUIC_LEDGER_TOOLS): TOOL_LIBS = $(TOOL_CRYPTO)
$(QUIC_LEDGER_TOOLS): tests/quic-ledger-crypto.c runtime/native/sha256.c

check check-portable check-quic check-quic-sanitize check-quic-rfc check-quic-rfc-sanitize check-sanitize: check-quic-amplification-ledger
