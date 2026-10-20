# Cargo's build scripts must see the same Make-exported CC/CFLAGS as the
# bounded harness. Prepare every default debug binary before test runtime.
# FORCE lets Cargo validate its complete config/environment fingerprint.
build/interop-quinn/debug/minyar-quinn-interop: FORCE tests/interop/quinn/Cargo.toml tests/interop/quinn/Cargo.lock | build
	CARGO_BUILD_JOBS=1 cargo build --locked --manifest-path tests/interop/quinn/Cargo.toml --target-dir build/interop-quinn

check-quic-quinn: build/interop-quinn/debug/minyar-quinn-interop
