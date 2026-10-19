# Portable networking foundations have their own gates so protocol tests can
# grow without mixing native desktop prerequisites into the portable suite.
.PHONY: check-errors-values check-net check-net-loop check-net-connect check-net-connect-sanitize check-os-net-stack check-os-net-stack-sanitize
NET_FIXTURE_TOOLS = http-package-test http-bounded-test httpserver-test httpserver-front-test net-native-test net-loop-test \
    net-udp-offload-test os-tlsverify-test peer-auth-mutants-test peer-auth-device-test peer-auth-test peer-wire-flow-test \
    peer-live-redis-test peer-live-test peer-wire-test redis-pipeline-test redis-protocol-test securecrypto-test \
    tls-handshake-validity-test tls-keyshare-test tls-signing-usage-test tls-local-test tls-resumption-expiry-test \
    yamux-churn-test tls-server-test transport-cancel-test tls-validity-test transport-go-test transport-udp-fallback-test
$(NET_FIXTURE_TOOLS:%=build/tooling/tests/%.ll): tests/net-fixtures.min
build/tooling/tests/net-loop-test.ll build/tooling/tests/net-native-test.ll: tests/net-evidence.min
build/tooling/tests/httpserver-test.ll build/tooling/tests/httpserver-front-test.ll build/tooling/benchmarks/httpserver/compare.ll: tests/net-wire.min tests/net-fixtures.min
build/tooling/tests/httpserver-front-test.ll build/tooling/benchmarks/httpserver/compare.ll: benchmarks/httpserver/front-oracle.min
build/tooling/tests/http-package-test.ll build/tooling/tests/peer-live-redis-test.ll: tests/net-redis.min
build/tooling/tests/peer-auth-test.ll build/tooling/tests/peer-wire-flow-test.ll: tests/peer-grants.min
build/tooling/tests/peer-wire-test.ll build/tooling/tests/redis-protocol-test.ll build/tooling/tests/tls-validity-test.ll: tests/cpython-random.min
SOAK_TOOLS = soak-observer-test net-soak-driver tls-soak-driver quic-soak peer-edge-soak peer-edge-device-scale
$(SOAK_TOOLS:%=build/tooling/tests/%.ll): tests/soak-observer.min tests/net-fixtures.min
build/tooling/tests/soak-observer-test.ll build/tooling/tests/quic-soak.ll: tests/quic-soak-adapter.min
build/tooling/tests/quic-soak.ll: tests/cpython-random.min
build/tooling/tests/peer-edge-soak.ll: tests/peer-edge-lab.min tests/net-redis.min tests/peer-grants.min
build/tooling/tests/peer-edge-device-scale.ll: tests/peer-edge-scale.min tests/net-redis.min
$(SOAK_TOOLS:%=build/tooling/tests/%): TOOL_NATIVE = tests/soak-observer-native.c runtime/native/net.c
$(SOAK_TOOLS:%=build/tooling/tests/%): TOOL_RUNTIME = build/testing/cycle-runtime.o
$(SOAK_TOOLS:%=build/tooling/tests/%): build/testing/cycle-runtime.o tests/soak-observer-native.c runtime/native/net.c

build/tooling/tests/os-net-stack.ll: os/kernel/net/wire.min
check-os-net-stack: build/minyarc build/tooling/tests/os-net-stack
	$(LIMITED) ./build/tooling/tests/os-net-stack

check-os-net-stack-sanitize: build/tooling/tests/os-net-stack.ll build/minyar-runtime-sanitize.o
	$(SANITIZER_LIMITED) "$(LLVM_CC)" $(SANITIZER_FLAGS) "$<" "build/minyar-runtime-sanitize.o" -lm -o "build/os-net-stack-test-sanitize"
	$(SANITIZER_LIMITED) ./build/os-net-stack-test-sanitize

check-errors-values: build/minyarc build/minyar-runtime.o build/tooling/tests/errors-values
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/errors-values

check-net: build/minyarc build/tooling/tests/net-native-test build/tooling/tests/soak-observer-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/soak-observer-test
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

build/tooling/tests/os-providers: TOOL_NATIVE = tests/os-providers-runtime.c
build/tooling/tests/os-providers: tests/os-providers-runtime.c
.PHONY: check-os-providers check-os-providers-sanitize
check-os-providers: build/minyarc build/tooling/tests/os-providers
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/os-providers

check-os-providers-sanitize: build/minyarc build/tooling/tests/os-providers
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/os-providers --sanitize

# The executable vector and inet_pton oracle route is a Linux ELF host gate.
ifeq ($(shell uname -s),Linux)
check check-portable: check-os-providers
check-sanitize: check-os-providers-sanitize
endif
