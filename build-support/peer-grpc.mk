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

.PHONY: check-http2 check-peer-grpc check-peer-grpc-sanitize
check-http2: build/minyarc check-peer-grpc-python
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "$(PEER_GRPC_PYTHON)" tests/http2.py

check-peer-grpc: build/minyarc check-peer-grpc-python check-http2
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "$(PEER_GRPC_PYTHON)" tests/peer-grpc.py

check-peer-grpc-sanitize: build/minyarc check-peer-grpc-python
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) "$(PEER_GRPC_PYTHON)" tests/http2.py --sanitize
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) "$(PEER_GRPC_PYTHON)" tests/peer-grpc.py --sanitize

check check-portable: check-peer-grpc
check-sanitize: check-peer-grpc-sanitize

.PHONY: check-http2-churn check-http2-churn-sanitize
check-http2-churn: build/minyarc check-peer-grpc-python
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "$(PEER_GRPC_PYTHON)" tests/http2-churn.py

check-http2-churn-sanitize: build/minyarc check-peer-grpc-python
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) "$(PEER_GRPC_PYTHON)" tests/http2-churn.py --sanitize

.PHONY: check-peer-grpc-churn check-peer-grpc-churn-sanitize
check-peer-grpc-churn: build/minyarc check-peer-grpc-python
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "$(PEER_GRPC_PYTHON)" tests/peer-grpc-churn.py

check-peer-grpc-churn-sanitize: build/minyarc check-peer-grpc-python
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) "$(PEER_GRPC_PYTHON)" tests/peer-grpc-churn.py --sanitize

.PHONY: check-peer-grpc-retire check-peer-grpc-retire-sanitize
check-peer-grpc-retire: build/minyarc check-peer-grpc-python
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "$(PEER_GRPC_PYTHON)" tests/peer-grpc-retire.py

check-peer-grpc-retire-sanitize: build/minyarc check-peer-grpc-python
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) "$(PEER_GRPC_PYTHON)" tests/peer-grpc-retire.py --sanitize

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

check-peer-edge-cids-sanitize: build/minyarc check-peer-grpc-python
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) "$(PEER_GRPC_PYTHON)" tests/peer-edge-cids.py --sanitize --evidence "$(CURDIR)/build/peer-edge-cids-sanitize"

check: check-peer-edge-cids
check-sanitize: check-peer-edge-cids-sanitize
