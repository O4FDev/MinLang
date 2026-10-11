# Portable networking foundations have their own gates so protocol tests can
# grow without mixing native desktop prerequisites into the portable suite.
.PHONY: check-errors-values check-net check-net-loop check-net-connect check-net-connect-sanitize
check-errors-values: build/minyarc build/minyar-runtime.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/errors-values.py

check-net: build/minyarc
	python3 tests/soak-observer-test.py
	@set -eu; evidence=$$(mktemp -d "$(abspath build)/net-native.XXXXXX"); echo "Network native evidence: $$evidence"; MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/net-native.py --mode native --evidence "$$evidence"
ifeq ($(filter Windows_NT,$(OS))$(filter MSYS% MINGW% CYGWIN%,$(shell uname -s)),)
	@set -eu; evidence=$$(mktemp -d "$(abspath build)/net-native-sanitize.XXXXXX"); echo "Network sanitizer evidence: $$evidence"; MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/net-native.py --mode sanitize --evidence "$$evidence"
endif

check-net-loop: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/net-loop.py

check-net-connect: build/minyarc
	MINYAR_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/net-connect.py

check-net-connect-sanitize: build/minyarc
	MINYAR_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/net-connect.py --sanitize

check: check-errors-values check-net check-net-loop check-net-connect
check-portable: check-errors-values check-net check-net-loop check-net-connect
check-sanitize: check-net-connect-sanitize

# Offload succeeds only on Linux; other OS providers must report unavailable.
.PHONY: check-net-udp-offload check-net-udp-offload-sanitize
NET_SANITIZER_CLANG = $(or $(MINYAR_SANITIZER_CLANG),$(LLVM_CC))
NET_SANITIZER_PATH = $(if $(MINYAR_SANITIZER_CLANG),$(dir $(MINYAR_SANITIZER_CLANG)):$(PATH),$(PATH))

check-net-udp-offload: build/minyarc build/minyar-default-runtime.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/net-udp-offload.py --evidence build/net-udp-offload

check-net-udp-offload-sanitize: build/minyarc build/minyar-default-runtime.o
	PATH="$(NET_SANITIZER_PATH)" MINYAR_TEST_CLANG="$(NET_SANITIZER_CLANG)" $(SANITIZER_LIMITED) python3 tests/net-udp-offload.py --sanitize --evidence build/net-udp-offload-sanitize

check check-portable check-quic: check-net-udp-offload
check-sanitize check-quic-sanitize: check-net-udp-offload-sanitize
