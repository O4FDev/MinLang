.PHONY: completionio-neodb-linux check-completionio-neodb-kernel check-completionio-neodb-sanitize

NEODB_COMPLETION_MODULES = tests/fixtures/neodb-simulation/src/storage/wal.min \
	tests/fixtures/neodb-simulation/src/storage/crc32c.min \
	tests/fixtures/neodb-simulation/src/storage/util.min \
	tests/fixtures/neodb-simulation/src/storage/snapshot.min
NEODB_COMPLETION_SOURCES = tests/completionio-neodb-probe.min tests/neodb-completion/dbio.min \
	$(NEODB_COMPLETION_MODULES) library/completionio.min library/files.min library/system.min \
	runtime/native/completionio.c runtime/native/files.c runtime/native/system.c

build/tooling/tests/completionio-neodb.ll: tests/frontend-fixtures.min
build/tooling/tests/completionio-neodb: $(NEODB_COMPLETION_SOURCES)

# Reuse the dedicated unmodified C strict kernel probe under sanitizers too.
build/completionio/neodb-kernel-sanitize: tests/completionio-kernel.c runtime/native/completionio.c runtime/minyar_native.h | build
	@mkdir -p "$(@D)"
	$(SANITIZER_LIMITED) "$(LLVM_CC)" $(SANITIZER_FLAGS) -std=c11 -Wall -Wextra -Werror "$<" -o "$@"

completionio-neodb-linux:
	@test "$(shell uname -s)" = Linux || { echo 'NeoDB completion proof requires Linux; unsupported is failure' >&2; exit 1; }

# Both targets intentionally stay outside check/check-portable/check-sanitize.
# First require the existing strict C provider + public API/gallery kernel proof.
# Exit 77, unsupported rings, setup/restriction errors and timeouts all fail.
check-completionio-neodb-kernel: completionio-neodb-linux check-completionio-kernel build/tooling/tests/completionio-neodb
	MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_NEODB_COMPLETION_KEEP=1 $(LIMITED) "./build/tooling/tests/completionio-neodb"

check-completionio-neodb-sanitize: completionio-neodb-linux check-completionio-kernel build/completionio/neodb-kernel-sanitize build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/completionio-neodb
	$(NATIVE_SANITIZER_ENV) $(SANITIZER_LIMITED) "./build/completionio/neodb-kernel-sanitize"
	ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 MINYAR_TEST_COMPILER="./build/minyarc-sanitize" MINYAR_TEST_RUNTIME="./build/minyar-runtime-sanitize.o" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_NEODB_COMPLETION_KEEP=1 $(SANITIZER_LIMITED) "./build/tooling/tests/completionio-neodb"
