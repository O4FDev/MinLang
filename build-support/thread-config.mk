.PHONY: check-thread-config
check-thread-config: tests/thread-config.py runtime/minyar_thread_config.h runtime/minyar_runtime.c $(RUNTIME_HEADERS) tools/cycle_runtime.py
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/thread-config.py

check check-portable: check-thread-config
