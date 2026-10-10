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
