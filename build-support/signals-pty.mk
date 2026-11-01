.PHONY: check-signals-pty check-signals-pty-sanitize
SIGNALS_PTY_SOURCES = tests/signals-pty.min tests/signals-pty-program.min library/system.min \
	runtime/native/system.c runtime/native/system_process.h runtime/native/system_terminal.h
check-signals-pty: build/minyarc $(SIGNALS_PTY_SOURCES) build/tooling/tests/signals-pty
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/signals-pty

check-signals-pty-sanitize: build/minyarc $(SIGNALS_PTY_SOURCES) build/tooling/tests/signals-pty
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(SANITIZER_LIMITED) ./build/tooling/tests/signals-pty --sanitize

# Signals and PTYs are POSIX services; the Windows backend reports -ENOTSUP.
ifeq ($(filter Windows_NT,$(OS))$(filter MSYS% MINGW% CYGWIN%,$(shell uname -s)),)
check check-portable: check-signals-pty
check-sanitize: check-signals-pty-sanitize
endif
