# All safe ownership controls run only on Linux. No Docker call.
# Readiness records bootstrap success; the phony gate verifies all inputs anew.
# Order-only setup sources do not repair a valid cache after source-only edits.
QUIC_OFFICIAL_RUNNER ?= $(abspath build)/quic-interop-runner-740c05a.git
QUIC_OFFICIAL_TOOLS = build/tooling/scripts/check-quic-official-inputs build/tooling/tests/quic-official-inputs \
    build/tooling/tests/quic-official-adapter build/tooling/tests/interop/qns/owned-adapter
QUIC_OFFICIAL_MODULES = tests/interop/qns/owned-common.min tests/interop/qns/owned-process.min tests/interop/qns/owned-daemon.min \
    tests/interop/qns/owned-derive.min tests/quic-json.min
QUIC_OFFICIAL_INPUTS = tests/quic-official-adapter.min tests/quic-official-support.min tests/quic-official-inputs.min \
    scripts/check-quic-official-inputs.min tests/interop/qns/owned-adapter.min tests/interop/qns/owned-adapter.c $(QUIC_OFFICIAL_MODULES) \
    tests/quic-simulator-shutdown.min tests/interop/qns/simulator-shutdown.sh \
    tests/quic-qns-endpoint-lifecycle.min tests/interop/qns/endpoint.min
QUIC_OFFICIAL_RUNNER_BOOTSTRAP = $(if $(filter $(abspath build)/quic-interop-runner-740c05a.git,$(QUIC_OFFICIAL_RUNNER)),build/quic-interop-runner-740c05a.git/.ready.json)
QUIC_OFFICIAL_HOST := $(if $(filter Windows_NT,$(OS)),unsupported,$(shell uname -s))
.PHONY: check-quic-official-adapter check-quic-simulator-shutdown check-quic-qns-endpoint-lifecycle

$(QUIC_OFFICIAL_TOOLS:%=%.ll): $(QUIC_OFFICIAL_MODULES)
build/tooling/tests/quic-official-adapter.ll: tests/quic-official-support.min
build/tooling/tests/quic-official-inputs.ll: scripts/check-quic-official-inputs.min
$(QUIC_OFFICIAL_TOOLS): TOOL_NATIVE = tests/interop/qns/owned-adapter.c runtime/native/sha256.c
$(QUIC_OFFICIAL_TOOLS): TOOL_LIBS = $(TOOL_CRYPTO)
$(QUIC_OFFICIAL_TOOLS): TOOL_RUNTIME = build/testing/cycle-runtime.o
$(QUIC_OFFICIAL_TOOLS): tests/interop/qns/owned-adapter.c runtime/native/sha256.c build/testing/cycle-runtime.o

ifeq ($(QUIC_OFFICIAL_HOST),Linux)
build/quic-interop-runner-740c05a.git/.ready.json: | build build/tooling/scripts/check-quic-official-inputs
	$(LIMITED) ./build/tooling/scripts/check-quic-official-inputs prepare-runner --repository "$(QUIC_OFFICIAL_RUNNER)"

build/tooling/tests/quic-simulator-shutdown.ll: tests/quic-test-support.min
check-quic-simulator-shutdown: build/tooling/tests/quic-simulator-shutdown tests/quic-simulator-shutdown.min tests/interop/qns/simulator-shutdown.sh | build
	$(LIMITED) ./build/tooling/tests/quic-simulator-shutdown

build/tooling/tests/quic-qns-endpoint-lifecycle.ll: tests/quic-test-support.min
check-quic-qns-endpoint-lifecycle: build/tooling/tests/quic-qns-endpoint-lifecycle build/minyarc tests/quic-qns-endpoint-lifecycle.min tests/interop/qns/endpoint.min | build
	$(LIMITED) ./build/tooling/tests/quic-qns-endpoint-lifecycle

check-quic-official-adapter: check-quic-simulator-shutdown check-quic-qns-endpoint-lifecycle
check-quic-official-adapter: $(QUIC_OFFICIAL_INPUTS) $(QUIC_OFFICIAL_TOOLS) $(QUIC_OFFICIAL_RUNNER_BOOTSTRAP) | build
	@set -e; artifacts=$$(mktemp -d "$(abspath build)/quic-official-adapter.XXXXXXXX"); \
	$(LIMITED) ./build/tooling/tests/quic-official-inputs; \
	$(LIMITED) ./build/tooling/scripts/check-quic-official-inputs controls --repository "$(QUIC_OFFICIAL_RUNNER)" --controls "$(abspath build/tooling/tests/quic-official-adapter)" --adapter "$(abspath build/tooling/tests/interop/qns/owned-adapter)" --report "$$artifacts/inputs.json" --artifacts "$$artifacts/run"

check check-portable check-quic check-quic-sanitize check-quic-rfc check-quic-rfc-sanitize check-sanitize: check-quic-official-adapter
else
check-quic-official-adapter:
	@echo "Linux adapter controls required" >&2; exit 2
endif
