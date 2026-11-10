# Mutation fuzzing of the socket-free protocol parsers (tests/protocol-fuzz.min):
# HTTP/1.1, HTTP/2 and HPACK, gRPC, Connect, protobuf, JSON, RESP, yamux, the
# peer wire, PEM, TLS hellos and QUIC frames. A case that stops the program is a remotely reachable
# crash, so the only passing output is "protocol-fuzz: ok". The default seed is
# fixed, which makes check-portable reproducible; the nightly workflow passes
# the date. See docs/security-review.md.
PROTOCOL_FUZZ_SEED ?= 20261110
PROTOCOL_FUZZ_ITERATIONS ?= 300
PROTOCOL_FUZZ_ARGUMENTS = --seed $(PROTOCOL_FUZZ_SEED) --iterations $(PROTOCOL_FUZZ_ITERATIONS)
.PHONY: check-protocol-fuzz check-protocol-fuzz-sanitize
check-protocol-fuzz: build/minyarc build/minyar-default-runtime.o
	mkdir -p build/protocol-fuzz
	MINYAR_CLANG="$(LLVM_CC)" ./minyar --debug tests/protocol-fuzz.min -o build/protocol-fuzz/debug
	$(LIMITED) ./build/protocol-fuzz/debug $(PROTOCOL_FUZZ_ARGUMENTS)
	MINYAR_CLANG="$(LLVM_CC)" ./minyar --release tests/protocol-fuzz.min -o build/protocol-fuzz/release
	$(LIMITED) ./build/protocol-fuzz/release $(PROTOCOL_FUZZ_ARGUMENTS)

# The same cases with the runtime, the native modules and the program under
# ASan and UBSan: a parser that stays inside Minyar's checks can still drive
# the C runtime's Bytes, Text and collection code somewhere new.
check-protocol-fuzz-sanitize: build/minyarc
	mkdir -p build/protocol-fuzz
	MINYAR_CLANG="$(LLVM_CC)" MINYAR_CLANG_FLAGS="$(SANITIZER_FLAGS)" MINYAR_RUNTIME_FLAGS="$(SANITIZER_FLAGS)" MINYAR_NATIVE_FLAGS="$(SANITIZER_FLAGS)" ./minyar tests/protocol-fuzz.min -o build/protocol-fuzz/sanitize
	$(NATIVE_SANITIZER_ENV) $(SANITIZER_LIMITED) ./build/protocol-fuzz/sanitize $(PROTOCOL_FUZZ_ARGUMENTS)

ifeq ($(filter Windows_NT,$(OS))$(filter MSYS% MINGW% CYGWIN%,$(shell uname -s)),)
check check-portable: check-protocol-fuzz
check-sanitize: check-protocol-fuzz-sanitize
endif
