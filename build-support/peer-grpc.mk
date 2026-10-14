# Pinned independent peers are test-only. Native modules import no Python stack.
PEER_GRPC_PYTHON ?= build/peergrpc-venv/bin/python
# An explicitly selected interpreter must have the same pinned native peers.
# It never builds an unrelated venv with the host's default Python.
PEER_GRPC_BOOTSTRAP = $(if $(filter build/peergrpc-venv/bin/python,$(PEER_GRPC_PYTHON)),build/peergrpc-venv/.ready)
.PHONY: check-peer-grpc-python
check-peer-grpc-python: $(PEER_GRPC_BOOTSTRAP)
	"$(PEER_GRPC_PYTHON)" scripts/check-peer-python.py

build/peergrpc-venv/.ready: tests/interop/peergrpc/requirements.txt scripts/check-peer-python.py
	python3 -m venv build/peergrpc-venv
	GRPC_PYTHON_BUILD_EXT_COMPILER_JOBS=1 CMAKE_BUILD_PARALLEL_LEVEL=1 build/peergrpc-venv/bin/pip --disable-pip-version-check install -r tests/interop/peergrpc/requirements.txt
	build/peergrpc-venv/bin/python scripts/check-peer-python.py
	touch $@

build/peergrpc-peer: tests/interop/peergrpc/main.go tests/interop/peergrpc/go.mod tests/interop/peergrpc/go.sum | build
	cd tests/interop/peergrpc && GOMAXPROCS=2 go build -mod=readonly -trimpath -o "$(abspath $@).tmp" . && "$(abspath $@).tmp" self-test
	mv -f "$@.tmp" "$@"

PEER_GRPC_TOOLS = http2-test http2-churn-test peer-grpc-test peer-grpc-churn-test peer-grpc-retire-test
$(PEER_GRPC_TOOLS:%=build/tooling/tests/%.ll): tests/http2-peer.min tests/net-fixtures.min
$(PEER_GRPC_TOOLS:%=build/tooling/tests/%): TOOL_RUNTIME = build/testing/cycle-runtime.o
$(PEER_GRPC_TOOLS:%=build/tooling/tests/%): build/testing/cycle-runtime.o
build/tooling/tests/http2-test.ll build/tooling/tests/peer-grpc-test.ll: tests/cpython-random.min

.PHONY: check-http2 check-peer-grpc check-peer-grpc-sanitize
check-http2: build/minyarc build/peergrpc-peer build/tooling/tests/http2-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/http2-test

check-peer-grpc: build/minyarc build/peergrpc-peer build/tooling/tests/peer-grpc-test check-http2
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/peer-grpc-test

check-peer-grpc-sanitize: build/minyarc build/peergrpc-peer build/tooling/tests/http2-test build/tooling/tests/peer-grpc-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/http2-test --sanitize
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/peer-grpc-test --sanitize

check check-portable: check-peer-grpc
check-sanitize: check-peer-grpc-sanitize

.PHONY: check-http2-churn check-http2-churn-sanitize
check-http2-churn: build/minyarc build/peergrpc-peer build/tooling/tests/http2-churn-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/http2-churn-test

check-http2-churn-sanitize: build/minyarc build/peergrpc-peer build/tooling/tests/http2-churn-test
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/http2-churn-test --sanitize

.PHONY: check-peer-grpc-churn check-peer-grpc-churn-sanitize
check-peer-grpc-churn: build/minyarc build/peergrpc-peer build/tooling/tests/peer-grpc-churn-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/peer-grpc-churn-test

check-peer-grpc-churn-sanitize: build/minyarc build/peergrpc-peer build/tooling/tests/peer-grpc-churn-test
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/peer-grpc-churn-test --sanitize

.PHONY: check-peer-grpc-retire check-peer-grpc-retire-sanitize
check-peer-grpc-retire: build/minyarc build/peergrpc-peer build/tooling/tests/peer-grpc-retire-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/peer-grpc-retire-test

check-peer-grpc-retire-sanitize: build/minyarc build/peergrpc-peer build/tooling/tests/peer-grpc-retire-test
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/peer-grpc-retire-test --sanitize

.PHONY: check-peer-edge check-peer-edge-sanitize
check-peer-edge: build/minyarc check-peer-grpc-python
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "$(PEER_GRPC_PYTHON)" tests/peer-edge.py

check-peer-edge-sanitize: build/minyarc check-peer-grpc-python
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) "$(PEER_GRPC_PYTHON)" tests/peer-edge.py --sanitize

check: check-http2-churn check-peer-grpc-churn check-peer-grpc-retire check-peer-edge
check-sanitize: check-http2-churn-sanitize check-peer-grpc-churn-sanitize check-peer-grpc-retire-sanitize check-peer-edge-sanitize

.PHONY: check-peer-edge-retry check-peer-edge-retry-sanitize
check-peer-edge-retry: build/minyarc check-peer-grpc-python
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "$(PEER_GRPC_PYTHON)" tests/peer-edge-retry.py

check-peer-edge-retry-sanitize: build/minyarc check-peer-grpc-python
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) "$(PEER_GRPC_PYTHON)" tests/peer-edge-retry.py --sanitize

check: check-peer-edge-retry
check-sanitize: check-peer-edge-retry-sanitize

# CID routing is an actual Redis-backed mTLS/Retry integration on Linux.
.PHONY: check-peer-edge-cids check-peer-edge-cids-sanitize
check-peer-edge-cids: build/minyarc check-peer-grpc-python
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "$(PEER_GRPC_PYTHON)" tests/peer-edge-cids.py --evidence "$(CURDIR)/build/peer-edge-cids-native"
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "$(PEER_GRPC_PYTHON)" tests/peer-edge-cid-stock.py --evidence "$(CURDIR)/build/peer-edge-cid-stock-native"

check-peer-edge-cids-sanitize: build/minyarc check-peer-grpc-python
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) "$(PEER_GRPC_PYTHON)" tests/peer-edge-cids.py --sanitize --evidence "$(CURDIR)/build/peer-edge-cids-sanitize"
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) "$(PEER_GRPC_PYTHON)" tests/peer-edge-cid-stock.py --sanitize --evidence "$(CURDIR)/build/peer-edge-cid-stock-sanitize"

check: check-peer-edge-cids
check-sanitize: check-peer-edge-cids-sanitize

# Signed relay and independently malformed/abrupt gateway lifetime checks are Linux labs.
.PHONY: check-peer-edge-relay check-peer-edge-relay-sanitize check-peer-edge-relay-lifetime check-peer-edge-relay-lifetime-sanitize
check-peer-edge-relay: build/minyarc check-peer-grpc-python tests/peer-edge-relay.py tests/peer_edge_support.py | build
	@set -e; artifacts=$$(mktemp -d "$(abspath build)/peer-edge-relay-native.XXXXXXXX"); MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "$(PEER_GRPC_PYTHON)" tests/peer-edge-relay.py --evidence "$$artifacts"

check-peer-edge-relay-sanitize: build/minyarc check-peer-grpc-python tests/peer-edge-relay.py tests/peer_edge_support.py | build
	@set -e; artifacts=$$(mktemp -d "$(abspath build)/peer-edge-relay-sanitize.XXXXXXXX"); $(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) "$(PEER_GRPC_PYTHON)" tests/peer-edge-relay.py --sanitize --evidence "$$artifacts"

check-peer-edge-relay-lifetime: build/minyarc check-peer-grpc-python tests/peer-edge-relay-lifetime.py tests/peer-edge-relay.py tests/peer_edge_support.py | build
	@set -e; cache=$$(mktemp -d "$(abspath build)/peer-edge-relay-lifetime-native-programs.XXXXXXXX"); trap 'rm -rf "$$cache"' EXIT; export MINYAR_TEST_PROGRAM_CACHE="$$cache"; \
	artifacts=$$(mktemp -d "$(abspath build)/peer-edge-relay-lifetime-native-malformed.XXXXXXXX"); MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "$(PEER_GRPC_PYTHON)" tests/peer-edge-relay-lifetime.py --mode malformed --evidence "$$artifacts"; \
	artifacts=$$(mktemp -d "$(abspath build)/peer-edge-relay-lifetime-native-abrupt.XXXXXXXX"); MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "$(PEER_GRPC_PYTHON)" tests/peer-edge-relay-lifetime.py --mode abrupt --evidence "$$artifacts"

check-peer-edge-relay-lifetime-sanitize: build/minyarc check-peer-grpc-python tests/peer-edge-relay-lifetime.py tests/peer-edge-relay.py tests/peer_edge_support.py | build
	@set -e; cache=$$(mktemp -d "$(abspath build)/peer-edge-relay-lifetime-sanitize-programs.XXXXXXXX"); trap 'rm -rf "$$cache"' EXIT; export MINYAR_TEST_PROGRAM_CACHE="$$cache"; \
	artifacts=$$(mktemp -d "$(abspath build)/peer-edge-relay-lifetime-sanitize-malformed.XXXXXXXX"); $(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) "$(PEER_GRPC_PYTHON)" tests/peer-edge-relay-lifetime.py --mode malformed --sanitize --evidence "$$artifacts"; \
	artifacts=$$(mktemp -d "$(abspath build)/peer-edge-relay-lifetime-sanitize-abrupt.XXXXXXXX"); $(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) "$(PEER_GRPC_PYTHON)" tests/peer-edge-relay-lifetime.py --mode abrupt --sanitize --evidence "$$artifacts"

check: check-peer-edge-relay check-peer-edge-relay-lifetime
check-sanitize: check-peer-edge-relay-sanitize check-peer-edge-relay-lifetime-sanitize


# Real server chain presentation and independently trusted device/gateway CA overlap.
.PHONY: check-peer-edge-pki check-peer-edge-pki-sanitize
check-peer-edge-pki: build/minyarc check-peer-grpc-python
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "$(PEER_GRPC_PYTHON)" tests/peer-edge-pki.py
check-peer-edge-pki-sanitize: build/minyarc check-peer-grpc-python
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) "$(PEER_GRPC_PYTHON)" tests/peer-edge-pki.py --sanitize
check: check-peer-edge-pki
check-sanitize: check-peer-edge-pki-sanitize

# The independent device peer stays outside default CI and sustained-load runs.
PEER_EDGE_SCALE_PYTHON ?= python3
.PHONY: check-peer-edge-device-scale-controls check-peer-edge-device-scale-peer
check-peer-edge-device-scale-controls:
	"$(PEER_EDGE_SCALE_PYTHON)" -B tests/peer-edge-device-scale-controls.py

check-peer-edge-device-scale-peer:
	CARGO_BUILD_JOBS=1 cargo test --release --locked --manifest-path tests/interop/quinn/Cargo.toml --bin peer-edge-scale -j1
