.PHONY: check-crc32c

ifneq ($(OS),Windows_NT)
build/crc32c: tests/crc32c.c runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	"$(LLVM_CC)" $(CPPFLAGS) $(CFLAGS) -pthread $< -lm -o $@

check-crc32c: build/crc32c
	$(LIMITED) ./build/crc32c

check check-portable: check-crc32c
endif
