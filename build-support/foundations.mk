PYTHON ?= python3
LAKE ?= lake

.PHONY: check-foundations-proofs
check-foundations-proofs:
	@command -v "$(LAKE)" >/dev/null 2>&1 || { echo 'check-foundations-proofs: install the Lean toolchain selected by proofs/lean-toolchain' >&2; exit 1; }
	"$(PYTHON)" tools/check-foundations.py --lake "$(LAKE)" --output build/foundations-proof-evidence
