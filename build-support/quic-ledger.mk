# Offline encrypted-packet accounting controls; this gate is not an official trace verdict.
.PHONY: check-quic-amplification-ledger
QUIC_LEDGER_INPUTS = tests/quic-amplification-ledger.py tests/quic_amplification_ledger.py
# The independent packet protection comes from a pinned test-only venv, so hosts
# without a system `cryptography` (e.g. CI's setup-python) run the same controls.
QUIC_LEDGER_VENV = $(abspath build)/quic-ledger-venv
# MSYS2's Python has no cryptography wheels, so CI installs its packaged module there;
# the venv inherits an installed module and pins one only when none is importable.
build/quic-ledger-venv/.ready: tests/quic-ledger-requirements.txt | build
	python3 -m venv --system-site-packages "$(QUIC_LEDGER_VENV)"
	"$(QUIC_LEDGER_VENV)/bin/python" -c 'import cryptography' 2>/dev/null || \
	"$(QUIC_LEDGER_VENV)/bin/python" -m pip --disable-pip-version-check install -q -r tests/quic-ledger-requirements.txt
	touch $@
check-quic-amplification-ledger: $(QUIC_LEDGER_INPUTS) build/quic-ledger-venv/.ready | build
	@set -e; artifacts=$$(mktemp -d "$(abspath build)/quic-ledger.XXXXXXXX"); PATH="$(QUIC_LEDGER_VENV)/bin:$$PATH" $(LIMITED) python3 -E tests/quic-amplification-ledger.py --artifacts "$$artifacts/run"

check check-portable check-quic check-quic-sanitize check-quic-rfc check-quic-rfc-sanitize check-sanitize: check-quic-amplification-ledger
