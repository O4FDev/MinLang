# Pinned independent peers are test-only. Native modules import no Python stack.
PEER_GRPC_PYTHON ?= build/peergrpc-venv/bin/python
build/peergrpc-venv/.ready: tests/interop/peergrpc/requirements.txt
	python3 -m venv build/peergrpc-venv
	build/peergrpc-venv/bin/pip --disable-pip-version-check install -r tests/interop/peergrpc/requirements.txt
	touch $@

.PHONY: check-http2 check-peer-grpc check-peer-grpc-sanitize
check-http2: build/minyarc build/peergrpc-venv/.ready
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) $(PEER_GRPC_PYTHON) tests/http2.py

check-peer-grpc: build/minyarc build/peergrpc-venv/.ready check-http2
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) $(PEER_GRPC_PYTHON) tests/peer-grpc.py

check-peer-grpc-sanitize: build/minyarc build/peergrpc-venv/.ready
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) $(PEER_GRPC_PYTHON) tests/http2.py --sanitize
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) $(PEER_GRPC_PYTHON) tests/peer-grpc.py --sanitize

check check-portable: check-peer-grpc
check-sanitize: check-peer-grpc-sanitize

.PHONY: check-http2-churn check-http2-churn-sanitize
check-http2-churn: build/minyarc build/peergrpc-venv/.ready
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) $(PEER_GRPC_PYTHON) tests/http2-churn.py

check-http2-churn-sanitize: build/minyarc build/peergrpc-venv/.ready
	ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) $(PEER_GRPC_PYTHON) tests/http2-churn.py --sanitize

.PHONY: check-peer-grpc-churn check-peer-grpc-churn-sanitize
check-peer-grpc-churn: build/minyarc build/peergrpc-venv/.ready
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) $(PEER_GRPC_PYTHON) tests/peer-grpc-churn.py

check-peer-grpc-churn-sanitize: build/minyarc build/peergrpc-venv/.ready
	ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) $(PEER_GRPC_PYTHON) tests/peer-grpc-churn.py --sanitize

.PHONY: check-peer-grpc-retire check-peer-grpc-retire-sanitize
check-peer-grpc-retire: build/minyarc build/peergrpc-venv/.ready
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) $(PEER_GRPC_PYTHON) tests/peer-grpc-retire.py

check-peer-grpc-retire-sanitize: build/minyarc build/peergrpc-venv/.ready
	ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) $(PEER_GRPC_PYTHON) tests/peer-grpc-retire.py --sanitize

.PHONY: check-peer-edge check-peer-edge-sanitize
check-peer-edge: build/minyarc build/peergrpc-venv/.ready
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) $(PEER_GRPC_PYTHON) tests/peer-edge.py

check-peer-edge-sanitize: build/minyarc build/peergrpc-venv/.ready
	ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) $(PEER_GRPC_PYTHON) tests/peer-edge.py --sanitize

check: check-http2-churn check-peer-grpc-churn check-peer-grpc-retire check-peer-edge
check-sanitize: check-http2-churn-sanitize check-peer-grpc-churn-sanitize check-peer-grpc-retire-sanitize check-peer-edge-sanitize
