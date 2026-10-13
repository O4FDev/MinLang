# Portable networking foundations have their own gates so protocol tests can
# grow without mixing native desktop prerequisites into the portable suite.
.PHONY: check-errors-values check-net check-net-loop check-net-connect check-net-connect-sanitize
check-errors-values: build/minyarc build/minyar-runtime.o build/tooling/tests/errors-values
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/errors-values

check-net: build/minyarc build/tooling/tests/net-native-test
	python3 tests/soak-observer-test.py
	@set -eu; evidence=$$(mktemp -d "$(abspath build)/net-native.XXXXXX"); echo "Network native evidence: $$evidence"; MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/net-native-test --mode native --evidence "$$evidence"
ifeq ($(filter Windows_NT,$(OS))$(filter MSYS% MINGW% CYGWIN%,$(shell uname -s)),)
	@set -eu; evidence=$$(mktemp -d "$(abspath build)/net-native-sanitize.XXXXXX"); echo "Network sanitizer evidence: $$evidence"; MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/net-native-test --mode sanitize --evidence "$$evidence"
endif

check-net-loop: build/minyarc build/tooling/tests/net-loop-test
	@set -eu; evidence=$$(mktemp -d "$(abspath build)/net-loop.XXXXXX"); echo "Event-loop native evidence: $$evidence"; MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/net-loop-test --mode native --evidence "$$evidence"
ifeq ($(filter Windows_NT,$(OS))$(filter MSYS% MINGW% CYGWIN%,$(shell uname -s)),)
	@set -eu; evidence=$$(mktemp -d "$(abspath build)/net-loop-sanitize.XXXXXX"); echo "Event-loop sanitizer evidence: $$evidence"; MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/net-loop-test --mode sanitize --evidence "$$evidence"
endif

check-net-connect: build/minyarc build/tooling/tests/net-connect-test
	MINYAR_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/net-connect-test

check-net-connect-sanitize: build/minyarc tools/toolchain.sh build/tooling/tests/net-connect-test
	PATH="$(NET_SANITIZER_PATH)" MINYAR_CLANG=$(call NET_SANITIZER_QUOTE,$(NET_SANITIZER_CLANG)) $(SANITIZER_LIMITED) ./build/tooling/tests/net-connect-test --sanitize

check: check-errors-values check-net check-net-loop check-net-connect
check-portable: check-errors-values check-net check-net-loop check-net-connect
check-sanitize: check-net-connect-sanitize

# Offload succeeds only on Linux; other OS providers must report unavailable.
.PHONY: check-net-udp-offload check-net-udp-offload-sanitize
# Keep the supported sanitizer override one argument in the caller's namespace.
NET_SANITIZER_QUOTE = '$(subst ','"'"',$(1))'
NET_SANITIZER_CLANG = $(if $(MINYAR_SANITIZER_CLANG),$(shell sh tools/toolchain.sh host-path $(call NET_SANITIZER_QUOTE,$(MINYAR_SANITIZER_CLANG))),$(LLVM_CC))
NET_SANITIZER_PATH = $(if $(MINYAR_SANITIZER_CLANG),$(shell sh tools/toolchain.sh host-directory $(call NET_SANITIZER_QUOTE,$(NET_SANITIZER_CLANG))):$(PATH),$(PATH))

check-net-udp-offload: build/minyarc build/minyar-default-runtime.o build/tooling/tests/net-udp-offload-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/net-udp-offload-test --evidence build/net-udp-offload

check-net-udp-offload-sanitize: build/minyarc build/minyar-default-runtime.o tools/toolchain.sh build/tooling/tests/net-udp-offload-test
	PATH="$(NET_SANITIZER_PATH)" MINYAR_TEST_CLANG=$(call NET_SANITIZER_QUOTE,$(NET_SANITIZER_CLANG)) $(SANITIZER_LIMITED) ./build/tooling/tests/net-udp-offload-test --sanitize --evidence build/net-udp-offload-sanitize

check check-portable check-quic: check-net-udp-offload
check-sanitize check-quic-sanitize: check-net-udp-offload-sanitize

.PHONY: check-os-tlsverify check-os-tlsverify-sanitize
# Keep the supported sanitizer override one argument in the caller's namespace.
OS_TLS_SANITIZER_QUOTE = '$(subst ','"'"',$(1))'
OS_TLS_SANITIZER_CLANG = $(if $(MINYAR_SANITIZER_CLANG),$(shell sh tools/toolchain.sh host-path $(call OS_TLS_SANITIZER_QUOTE,$(MINYAR_SANITIZER_CLANG))),$(LLVM_CC))
OS_TLS_SANITIZER_PATH = $(if $(MINYAR_SANITIZER_CLANG),$(shell sh tools/toolchain.sh host-directory $(call OS_TLS_SANITIZER_QUOTE,$(OS_TLS_SANITIZER_CLANG))):$(PATH),$(PATH))
check-os-tlsverify: build/minyarc build/tooling/tests/os-tlsverify-test
	MINYAR_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/os-tlsverify-test

check-os-tlsverify-sanitize: build/minyarc tools/toolchain.sh build/tooling/tests/os-tlsverify-test
	PATH="$(OS_TLS_SANITIZER_PATH)" MINYAR_CLANG=$(call OS_TLS_SANITIZER_QUOTE,$(OS_TLS_SANITIZER_CLANG)) $(SANITIZER_LIMITED) ./build/tooling/tests/os-tlsverify-test --sanitize

check check-portable: check-os-tlsverify
check-sanitize: check-os-tlsverify-sanitize

.PHONY: check-os-providers check-os-providers-sanitize
check-os-providers: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/os-providers.py

check-os-providers-sanitize: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/os-providers.py --sanitize

# The executable vector and inet_pton oracle route is a Linux ELF host gate.
ifeq ($(shell uname -s),Linux)
check check-portable: check-os-providers
check-sanitize: check-os-providers-sanitize
endif
