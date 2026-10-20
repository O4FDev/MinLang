# Keep the protocol definitions as ordinary Minyar source, embedded at build time.
build/capability-builtins.min: compiler/builtin-capabilities.min build-support/capability-prelude.awk | build
	@set -e; temporary=$$(mktemp "$@.tmp.XXXXXXXX"); \
	trap 'rm -f "$$temporary"' 0; \
	awk -f "build-support/capability-prelude.awk" "$<" > "$$temporary"; \
	if ! test -f "$@" || ! cmp -s "$$temporary" "$@"; then mv "$$temporary" "$@"; fi

.PHONY: check-user-capabilities check-user-capabilities-sanitize

check-user-capabilities: build/minyarc build/minyar-runtime.o build/tooling/tests/user-capabilities
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) "./build/tooling/tests/user-capabilities"

check-user-capabilities-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/user-capabilities
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) "./build/tooling/tests/user-capabilities"

build/tooling/tests/user-capabilities.ll: tests/frontend-fixtures.min examples/gallery/capabilities.min

check check-portable: check-user-capabilities
check-sanitize: check-user-capabilities-sanitize
