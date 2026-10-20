# Pinned independent peers are test-only. Native modules import no Python stack.
# Their Go-only protocol and fixture TLS code needs no host C runtime.
build/peergrpc-peer: tests/interop/peergrpc/main.go tests/interop/peergrpc/edge.go tests/interop/peergrpc/go.mod tests/interop/peergrpc/go.sum $(lastword $(MAKEFILE_LIST)) | build
	cd tests/interop/peergrpc && CGO_ENABLED=0 GOMAXPROCS=2 go build -mod=readonly -trimpath -o "$(abspath $@).tmp" . && "$(abspath $@).tmp" self-test
	mv -f "$@.tmp" "$@"

PEER_GRPC_TOOLS = http2-test http2-churn-test peer-grpc-test peer-grpc-churn-test peer-grpc-retire-test
$(PEER_GRPC_TOOLS:%=build/tooling/tests/%.ll): tests/http2-peer.min tests/net-fixtures.min
$(PEER_GRPC_TOOLS:%=build/tooling/tests/%): TOOL_RUNTIME = build/testing/cycle-runtime.o
$(PEER_GRPC_TOOLS:%=build/tooling/tests/%): build/testing/cycle-runtime.o
build/tooling/tests/http2-test.ll build/tooling/tests/peer-grpc-test.ll: tests/cpython-random.min

.PHONY: check-http2 check-peer-grpc check-peer-grpc-sanitize
check-http2: build/minyarc build/peergrpc-peer build/tooling/tests/http2-test
	MINYAR_MAX_MEMORY_MIB=2048 GOMAXPROCS=2 MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/http2-test

check-peer-grpc: build/minyarc build/peergrpc-peer build/tooling/tests/peer-grpc-test check-http2
	MINYAR_MAX_MEMORY_MIB=2048 GOMAXPROCS=2 MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/peer-grpc-test

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

PEER_EDGE_TOOLS = peer-edge-test peer-edge-retry-test peer-edge-cids-test peer-edge-cid-stock-test peer-edge-relay-test \
    peer-edge-relay-lifetime-test peer-edge-pki-test
$(PEER_EDGE_TOOLS:%=build/tooling/tests/%.ll): tests/peer-edge-lab.min tests/net-fixtures.min tests/net-redis.min tests/peer-grants.min
build/tooling/tests/peer-edge-relay-lifetime-test.ll: tests/http2-peer.min
$(PEER_EDGE_TOOLS:%=build/tooling/tests/%): TOOL_RUNTIME = build/testing/cycle-runtime.o
$(PEER_EDGE_TOOLS:%=build/tooling/tests/%): TOOL_NATIVE = runtime/native/net.c
$(PEER_EDGE_TOOLS:%=build/tooling/tests/%): build/testing/cycle-runtime.o runtime/native/net.c

.PHONY: check-peer-edge check-peer-edge-sanitize
check-peer-edge: build/minyarc build/peergrpc-peer build/tooling/tests/peer-edge-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/peer-edge-test

check-peer-edge-sanitize: build/minyarc build/peergrpc-peer build/tooling/tests/peer-edge-test
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/peer-edge-test --sanitize

check: check-http2-churn check-peer-grpc-churn check-peer-grpc-retire check-peer-edge
check-sanitize: check-http2-churn-sanitize check-peer-grpc-churn-sanitize check-peer-grpc-retire-sanitize check-peer-edge-sanitize

.PHONY: check-peer-edge-retry check-peer-edge-retry-sanitize
check-peer-edge-retry: build/minyarc build/peergrpc-peer build/tooling/tests/peer-edge-retry-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/peer-edge-retry-test

check-peer-edge-retry-sanitize: build/minyarc build/peergrpc-peer build/tooling/tests/peer-edge-retry-test
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/peer-edge-retry-test --sanitize

check: check-peer-edge-retry
check-sanitize: check-peer-edge-retry-sanitize

# CID routing is an actual Redis-backed mTLS/Retry integration on Linux.
.PHONY: check-peer-edge-cids check-peer-edge-cids-sanitize
# Stock CID link receipts retain Clang itself; permit files up to 512 MiB here.
check-peer-edge-cids check-peer-edge-cids-sanitize: export MINYAR_MAX_FILE_BLOCKS ?= 1048576
check-peer-edge-cids: build/minyarc build/peergrpc-peer build/tooling/tests/peer-edge-cids-test build/tooling/tests/peer-edge-cid-stock-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/peer-edge-cids-test --evidence "$(CURDIR)/build/peer-edge-cids-native"
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/peer-edge-cid-stock-test --evidence "$(CURDIR)/build/peer-edge-cid-stock-native"

check-peer-edge-cids-sanitize: build/minyarc build/peergrpc-peer build/tooling/tests/peer-edge-cids-test build/tooling/tests/peer-edge-cid-stock-test
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/peer-edge-cids-test --sanitize --evidence "$(CURDIR)/build/peer-edge-cids-sanitize"
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/peer-edge-cid-stock-test --sanitize --evidence "$(CURDIR)/build/peer-edge-cid-stock-sanitize"

check: check-peer-edge-cids
check-sanitize: check-peer-edge-cids-sanitize

# Signed relay and independently malformed/abrupt gateway lifetime checks are Linux labs.
.PHONY: check-peer-edge-relay check-peer-edge-relay-sanitize check-peer-edge-relay-lifetime check-peer-edge-relay-lifetime-sanitize
check-peer-edge-relay: build/minyarc build/peergrpc-peer build/tooling/tests/peer-edge-relay-test | build
	@set -e; artifacts=$$(mktemp -d "$(abspath build)/peer-edge-relay-native.XXXXXXXX"); MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/peer-edge-relay-test --evidence "$$artifacts"

check-peer-edge-relay-sanitize: build/minyarc build/peergrpc-peer build/tooling/tests/peer-edge-relay-test | build
	@set -e; artifacts=$$(mktemp -d "$(abspath build)/peer-edge-relay-sanitize.XXXXXXXX"); $(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/peer-edge-relay-test --sanitize --evidence "$$artifacts"

check-peer-edge-relay-lifetime: build/minyarc build/peergrpc-peer build/tooling/tests/peer-edge-relay-lifetime-test | build
	@set -e; cache=$$(mktemp -d "$(abspath build)/peer-edge-relay-lifetime-native-programs.XXXXXXXX"); trap 'rm -rf "$$cache"' EXIT; export MINYAR_TEST_PROGRAM_CACHE="$$cache"; \
	artifacts=$$(mktemp -d "$(abspath build)/peer-edge-relay-lifetime-native-malformed.XXXXXXXX"); MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/peer-edge-relay-lifetime-test --mode malformed --evidence "$$artifacts"; \
	artifacts=$$(mktemp -d "$(abspath build)/peer-edge-relay-lifetime-native-abrupt.XXXXXXXX"); MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/peer-edge-relay-lifetime-test --mode abrupt --evidence "$$artifacts"

check-peer-edge-relay-lifetime-sanitize: build/minyarc build/peergrpc-peer build/tooling/tests/peer-edge-relay-lifetime-test | build
	@set -e; cache=$$(mktemp -d "$(abspath build)/peer-edge-relay-lifetime-sanitize-programs.XXXXXXXX"); trap 'rm -rf "$$cache"' EXIT; export MINYAR_TEST_PROGRAM_CACHE="$$cache"; \
	artifacts=$$(mktemp -d "$(abspath build)/peer-edge-relay-lifetime-sanitize-malformed.XXXXXXXX"); $(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/peer-edge-relay-lifetime-test --mode malformed --sanitize --evidence "$$artifacts"; \
	artifacts=$$(mktemp -d "$(abspath build)/peer-edge-relay-lifetime-sanitize-abrupt.XXXXXXXX"); $(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/peer-edge-relay-lifetime-test --mode abrupt --sanitize --evidence "$$artifacts"

check: check-peer-edge-relay check-peer-edge-relay-lifetime
check-sanitize: check-peer-edge-relay-sanitize check-peer-edge-relay-lifetime-sanitize


# Real server chain presentation and independently trusted device/gateway CA overlap.
.PHONY: check-peer-edge-pki check-peer-edge-pki-sanitize
check-peer-edge-pki: build/minyarc build/peergrpc-peer build/tooling/tests/peer-edge-pki-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/peer-edge-pki-test
check-peer-edge-pki-sanitize: build/minyarc build/peergrpc-peer build/tooling/tests/peer-edge-pki-test
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/peer-edge-pki-test --sanitize
check: check-peer-edge-pki
check-sanitize: check-peer-edge-pki-sanitize

# The independent device peer stays outside default CI and sustained-load runs.
.PHONY: check-peer-edge-device-scale-controls check-peer-edge-device-scale-peer
build/tooling/tests/peer-edge-device-scale-controls-test.ll: tests/peer-edge-scale.min tests/net-fixtures.min tests/cpython-random.min
build/tooling/tests/peer-edge-device-scale-controls-test: TOOL_RUNTIME = build/testing/cycle-runtime.o
build/tooling/tests/peer-edge-device-scale-controls-test: build/testing/cycle-runtime.o
check-peer-edge-device-scale-controls: build/peergrpc-peer build/tooling/tests/peer-edge-device-scale-controls-test
	./build/tooling/tests/peer-edge-device-scale-controls-test

check-peer-edge-device-scale-peer:
	CARGO_BUILD_JOBS=1 cargo test --release --locked --manifest-path tests/interop/quinn/Cargo.toml --bin peer-edge-scale -j1
