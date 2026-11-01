.PHONY: check-sys-native check-sys-native-sanitize check-sys-files check-sys-files-sanitize
.PHONY: check-checksums-encoding check-checksums-encoding-sanitize check-time-civil check-time-civil-sanitize
.PHONY: check-io-lines check-io-lines-sanitize

# SYS-3..SYS-6 and SYS-8. The native test compiles the runtime itself so the
# sanitizer build sees every allocation in the new paths; the Minyar tests
# exercise the typed library API through the compiler.
SYS_TEST_SOURCES = runtime/native/files.c $(RUNTIME_HEADERS)

build/sys-native: tests/sys-native.c runtime/minyar_runtime.c $(SYS_TEST_SOURCES) | build
	$(LIMITED) "$(LLVM_CC)" $(CFLAGS) -DMINYAR_SYSTEM_HEAP=1 tests/sys-native.c runtime/native/files.c $(LDLIBS) -o $@

build/sys-native-sanitize: tests/sys-native.c runtime/minyar_runtime.c $(SYS_TEST_SOURCES) | build
	$(SANITIZER_LIMITED) "$(LLVM_CC)" $(SANITIZER_FLAGS) -DMINYAR_SYSTEM_HEAP=1 tests/sys-native.c runtime/native/files.c $(LDLIBS) -o $@

check-sys-native: build/sys-native
	$(LIMITED) ./build/sys-native

check-sys-native-sanitize: build/sys-native-sanitize
	ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 $(SANITIZER_LIMITED) ./build/sys-native-sanitize

check-sys-files: build/minyarc build/minyar-runtime.o build/tooling/tests/sys-files tests/sys-files.min library/files.min
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/sys-files

check-sys-files-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/sys-files tests/sys-files.min library/files.min
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_CLANG="$(TEST_CLANG)" MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/sys-files

check-checksums-encoding: build/minyarc build/minyar-runtime.o build/tooling/tests/checksums-encoding tests/checksums-encoding.min library/checksum.min library/digest.min library/encoding.min
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/checksums-encoding

check-checksums-encoding-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/checksums-encoding
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_CLANG="$(TEST_CLANG)" MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/checksums-encoding

check-time-civil: build/minyarc build/minyar-runtime.o build/tooling/tests/time-civil tests/time-civil.min library/time.min
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/time-civil

check-time-civil-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/time-civil
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_CLANG="$(TEST_CLANG)" MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/time-civil

# The reader's input is a pipe the runner writes, so the fixture is a filter
# script rather than a source file: CRLF, LF, an empty line, an over-long line,
# a final line without a newline and an invalid UTF-8 line.
check-io-lines: build/minyarc build/minyar-runtime.o build/tooling/tests/io-lines tests/io-lines.min
	printf 'alpha\r\nbeta\n\nomega\n' > build/io-lines-input.bin
	python3 -c 'import sys; sys.stdout.buffer.write(b"x" * (1048576 + 1) + b"\nafter\n\xff\xfe\n")' >> build/io-lines-input.bin
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) sh -c './build/tooling/tests/io-lines < build/io-lines-input.bin'

check-io-lines-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/io-lines
	printf 'alpha\r\nbeta\n\nomega\n' > build/io-lines-input.bin
	python3 -c 'import sys; sys.stdout.buffer.write(b"x" * (1048576 + 1) + b"\nafter\n\xff\xfe\n")' >> build/io-lines-input.bin
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_CLANG="$(TEST_CLANG)" MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) sh -c './build/tooling/tests/io-lines < build/io-lines-input.bin'

# The files backend and these calls are POSIX-only, like check-files.
ifeq ($(filter Windows_NT,$(OS))$(filter MSYS% MINGW% CYGWIN%,$(shell uname -s)),)
check check-portable: check-sys-native check-sys-files check-checksums-encoding check-time-civil check-io-lines
check-sanitize: check-sys-native-sanitize check-sys-files-sanitize check-checksums-encoding-sanitize check-time-civil-sanitize check-io-lines-sanitize
endif
