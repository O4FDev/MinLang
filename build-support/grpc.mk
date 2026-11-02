.PHONY: check-grpc-session check-grpc-interop

# grpc.Connection without sockets: calls, errors, deadlines, cancellation,
# backpressure and a deterministic simulation, at O0 and O2.
check-grpc-session: build/minyarc build/minyar-default-runtime.o
	mkdir -p build/grpc
	MINYAR_CLANG="$(LLVM_CC)" ./minyar --debug tests/grpc-session.min -o build/grpc/session-debug
	$(LIMITED) ./build/grpc/session-debug
	MINYAR_CLANG="$(LLVM_CC)" ./minyar --release tests/grpc-session.min -o build/grpc/session-release
	$(LIMITED) ./build/grpc/session-release

check check-portable: check-grpc-session

# A stock @grpc/grpc-js client (pinned in tests/interop/grpc-js) over h2c and
# TLS with ALPN h2, against servers built at O0 and O2.
check-grpc-interop: build/minyarc build/minyar-default-runtime.o
	MINYAR_CLANG="$(LLVM_CC)" python3 tests/grpc-interop.py "$(CURDIR)/minyar"

check check-portable: check-grpc-interop
