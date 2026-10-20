.PHONY: check-completionio check-completionio-native check-completionio-kernel check-completionio-sanitize

COMPLETIONIO_INPUTS = runtime/native/completionio.c runtime/minyar_native.h
COMPLETIONIO_MOCK = $(if $(filter Linux,$(shell uname -s)),1,0)

build/completionio/unit: tests/completionio-unit.c $(COMPLETIONIO_INPUTS) | build
	@mkdir -p "$(@D)"
	$(LIMITED) "$(LLVM_CC)" $(CPPFLAGS) $(CFLAGS) "$<" -pthread -o "$@"

build/completionio/unsupported: tests/completionio-unit.c $(COMPLETIONIO_INPUTS) | build
	@mkdir -p "$(@D)"
	$(LIMITED) "$(LLVM_CC)" $(CPPFLAGS) $(CFLAGS) -DCOMPLETIONIO_FORCE_UNSUPPORTED "$<" -o "$@"

build/completionio/kernel: tests/completionio-kernel.c $(COMPLETIONIO_INPUTS) | build
	@mkdir -p "$(@D)"
	$(LIMITED) "$(LLVM_CC)" $(CPPFLAGS) $(CFLAGS) "$<" -o "$@"

build/completionio/unit-sanitize: tests/completionio-unit.c $(COMPLETIONIO_INPUTS) | build
	@mkdir -p "$(@D)"
	$(SANITIZER_LIMITED) "$(LLVM_CC)" $(SANITIZER_FLAGS) -std=c11 -Wall -Wextra -Werror "$<" -pthread -o "$@"

build/completionio/unsupported-sanitize: tests/completionio-unit.c $(COMPLETIONIO_INPUTS) | build
	@mkdir -p "$(@D)"
	$(SANITIZER_LIMITED) "$(LLVM_CC)" $(SANITIZER_FLAGS) -std=c11 -Wall -Wextra -Werror -DCOMPLETIONIO_FORCE_UNSUPPORTED "$<" -o "$@"

build/tooling/tests/completionio.ll: tests/frontend-fixtures.min
build/tooling/tests/completionio: $(COMPLETIONIO_INPUTS) tests/completionio-unit.c library/completionio.min examples/gallery/durable-batch.min

check-completionio-native: build/completionio/unit build/completionio/unsupported
	$(LIMITED) "./build/completionio/unit"
	$(LIMITED) "./build/completionio/unsupported"

check-completionio: check-completionio-native build/minyarc build/minyar-runtime.o build/tooling/tests/completionio
	MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_COMPLETIONIO_MOCK=$(COMPLETIONIO_MOCK) $(LIMITED) "./build/tooling/tests/completionio"

# Strict: exit 77 / unsupported is a failure of this proof target. Never part of
# portable checks; a container's seccomp policy may legitimately forbid setup.
check-completionio-kernel: build/completionio/kernel build/minyarc build/minyar-runtime.o build/tooling/tests/completionio
	$(LIMITED) "./build/completionio/kernel"
	MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_COMPLETIONIO_KERNEL=1 $(LIMITED) "./build/tooling/tests/completionio"

check-completionio-sanitize: build/completionio/unit-sanitize build/completionio/unsupported-sanitize build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/completionio
	$(NATIVE_SANITIZER_ENV) $(SANITIZER_LIMITED) "./build/completionio/unit-sanitize"
	$(NATIVE_SANITIZER_ENV) $(SANITIZER_LIMITED) "./build/completionio/unsupported-sanitize"
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER="./build/minyarc-sanitize" MINYAR_TEST_RUNTIME="./build/minyar-runtime-sanitize.o" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_COMPLETIONIO_MOCK=$(COMPLETIONIO_MOCK) $(SANITIZER_LIMITED) "./build/tooling/tests/completionio"

check check-portable: check-completionio
check-sanitize: check-completionio-sanitize
