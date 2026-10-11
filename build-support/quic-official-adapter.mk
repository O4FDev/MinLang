# All safe ownership controls run only on Linux/CPython3.12. No Docker call.
# Readiness records bootstrap success; the phony gate verifies all inputs anew.
# Order-only setup sources do not repair a valid cache after source-only edits.
QUIC_OFFICIAL_RUNNER ?= $(abspath build)/quic-interop-runner-740c05a.git
QUIC_OFFICIAL_PYTHON ?= $(abspath build)/quic-official-controls-venv/bin/python
QUIC_OFFICIAL_INPUTS = tests/quic-official-adapter.py tests/interop/qns/owned_adapter.py \
    scripts/check-quic-official-inputs.py tests/interop/qns/controls-requirements.txt \
    tests/quic-simulator-shutdown.py tests/interop/qns/simulator-shutdown.sh \
    tests/quic-qns-endpoint-lifecycle.py tests/interop/qns/endpoint.py
QUIC_OFFICIAL_RUNNER_BOOTSTRAP = $(if $(filter $(abspath build)/quic-interop-runner-740c05a.git,$(QUIC_OFFICIAL_RUNNER)),build/quic-interop-runner-740c05a.git/.ready.json)
QUIC_OFFICIAL_PYTHON_BOOTSTRAP = $(if $(filter $(abspath build)/quic-official-controls-venv/bin/python,$(QUIC_OFFICIAL_PYTHON)),build/quic-official-controls-venv/.ready.json)
QUIC_OFFICIAL_HOST := $(if $(filter Windows_NT,$(OS)),unsupported,$(shell uname -s))
.PHONY: check-quic-official-adapter check-quic-simulator-shutdown check-quic-qns-endpoint-lifecycle

ifeq ($(QUIC_OFFICIAL_HOST),Linux)
build/quic-interop-runner-740c05a.git/.ready.json: | build scripts/check-quic-official-inputs.py tests/interop/qns/owned_adapter.py
	$(LIMITED) python3 -E scripts/check-quic-official-inputs.py prepare-runner --repository "$(QUIC_OFFICIAL_RUNNER)"

build/quic-official-controls-venv/.ready.json: | build scripts/check-quic-official-inputs.py tests/interop/qns/controls-requirements.txt
	$(LIMITED) python3 -E scripts/check-quic-official-inputs.py prepare-python --directory "$(abspath build)/quic-official-controls-venv" --requirements "tests/interop/qns/controls-requirements.txt"

check-quic-simulator-shutdown: tests/quic-simulator-shutdown.py tests/interop/qns/simulator-shutdown.sh $(QUIC_OFFICIAL_PYTHON_BOOTSTRAP) | build
	$(LIMITED) "$(QUIC_OFFICIAL_PYTHON)" -E tests/quic-simulator-shutdown.py

check-quic-qns-endpoint-lifecycle: tests/quic-qns-endpoint-lifecycle.py tests/interop/qns/endpoint.py $(QUIC_OFFICIAL_PYTHON_BOOTSTRAP) | build
	$(LIMITED) "$(QUIC_OFFICIAL_PYTHON)" -E tests/quic-qns-endpoint-lifecycle.py

check-quic-official-adapter: check-quic-simulator-shutdown check-quic-qns-endpoint-lifecycle
check-quic-official-adapter: $(QUIC_OFFICIAL_INPUTS) $(QUIC_OFFICIAL_RUNNER_BOOTSTRAP) $(QUIC_OFFICIAL_PYTHON_BOOTSTRAP) | build
	@set -e; artifacts=$$(mktemp -d "$(abspath build)/quic-official-adapter.XXXXXXXX"); \
	$(LIMITED) "$(QUIC_OFFICIAL_PYTHON)" -E scripts/check-quic-official-inputs.py controls --repository "$(QUIC_OFFICIAL_RUNNER)" --requirements "tests/interop/qns/controls-requirements.txt" --report "$$artifacts/inputs.json" --artifacts "$$artifacts/run"

check check-portable check-quic check-quic-sanitize check-quic-rfc check-quic-rfc-sanitize check-sanitize: check-quic-official-adapter
else
check-quic-official-adapter:
	@echo "Linux adapter controls required" >&2; exit 2
endif
