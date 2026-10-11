# Public launcher builds every RFC fixture at O0/O2; each author driver runs all cases.
.PHONY: check-quic-rfc check-quic-rfc-sanitize
QUIC_RFC_FRONTENDS = build/minyarc build/minyarc-callbacks build/minyarc-errors-request build/minyarc-errors
QUIC_RFC_INPUTS = minyar tools/clang-driver.py tools/sanitizer_llvm.py \
    tests/quic-rfc.py tests/quic-rfc-harness.py tests/test_evidence.py tests/clang_helpers.py \
    tests/tls-local.py tests/quic_protocol_artifacts.py tests/interop/qns/endpoint.py library/quic.min library/tls.min library/tlsserver.min \
    tests/quic-migration-cids.py tests/quic-migration-cids.min \
    tests/quic-cipher-policy.py tests/quic-cipher-policy.min \
    tests/quic-qns-local.py tests/quic-vn-probe.py \
    tests/interop/qns/client.min tests/interop/qns/server.min \
    $(wildcard compiler/*.patch scripts/*compiler*.py runtime/*.h runtime/native/*.h)

check-quic-rfc: $(QUIC_RFC_FRONTENDS) $(QUIC_RFC_INPUTS) | build
	python3 tests/quic-rfc-harness.py
	@set -e; artifacts=$$(mktemp -d "$(abspath build)/quic-rfc-native.XXXXXXXX"); MINYAR_CLANG="$(LLVM_CC)" MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/quic-rfc.py --optimization both --artifacts "$$artifacts/run"

check-quic-rfc-sanitize: $(QUIC_RFC_FRONTENDS) $(QUIC_RFC_INPUTS) | build
	python3 tests/quic-rfc-harness.py
	@set -e; artifacts=$$(mktemp -d "$(abspath build)/quic-rfc-sanitize.XXXXXXXX"); $(NATIVE_SANITIZER_ENV) MINYAR_CLANG="$(LLVM_CC)" MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/quic-rfc.py --optimization both --sanitize --artifacts "$$artifacts/run"

check check-portable check-quic: check-quic-rfc
check-sanitize check-quic-sanitize: check-quic-rfc-sanitize
