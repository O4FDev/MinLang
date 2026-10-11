# Offline encrypted-packet accounting controls; this gate is not an official trace verdict.
.PHONY: check-quic-amplification-ledger
QUIC_LEDGER_INPUTS = tests/quic-amplification-ledger.py tests/quic_amplification_ledger.py
check-quic-amplification-ledger: $(QUIC_LEDGER_INPUTS) | build
	@set -e; artifacts=$$(mktemp -d "$(abspath build)/quic-ledger.XXXXXXXX"); $(LIMITED) python3 -E tests/quic-amplification-ledger.py --artifacts "$$artifacts/run"

check check-portable check-quic check-quic-sanitize check-quic-rfc check-quic-rfc-sanitize check-sanitize: check-quic-amplification-ledger
