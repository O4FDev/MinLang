.PHONY: check-osdev-fields check-osdev-fields-sanitize check-osdev-workflow check-osdev-host check-osdev-rtc check-osdev-rtc-sanitize

.PHONY: check-register-layouts check-register-layouts-sanitize
build/tooling/tests/register-layouts.ll: tests/frontend-fixtures.min
check-register-layouts: build/minyarc build/minyar-runtime.o build/tooling/tests/register-layouts
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/register-layouts

check-register-layouts-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/register-layouts
	MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS="$(SANITIZER_FLAGS)" $(SANITIZER_LIMITED) ./build/tooling/tests/register-layouts

build/tooling/tests/device-fields.ll: tests/frontend-fixtures.min
check-osdev-fields: build/minyarc build/minyar-runtime.o build/tooling/tests/device-fields
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/device-fields

check-osdev-fields-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/device-fields
	MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS="$(SANITIZER_FLAGS)" $(SANITIZER_LIMITED) ./build/tooling/tests/device-fields

check-osdev-workflow:
	python3 tests/osdev-workflow.py

.PHONY: check-osdev-runtime check-osdev-callback-domain
check-osdev-runtime:
	python3 tests/osdev-runtime.py

check-osdev-callback-domain: build/.toolchain.json
	MINYAR_TEST_CLANG="$(LLVM_CC)" python3 tests/osdev-callback-domain.py

.PHONY: check-osdev-rtc-log
check-osdev-rtc-log:
	python3 tests/osdev-rtc-log.py

check-osdev-rtc: build/.toolchain.json build/minyarc check-osdev-rtc-log
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/osdev-rtc.py

check-osdev-rtc-sanitize: build/.toolchain.json build/minyarc-sanitize
	MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_LINK_FLAGS="$(SANITIZER_FLAGS)" $(SANITIZER_LIMITED) python3 tests/osdev-rtc.py

check-osdev-host: check-osdev-fields check-security-os-http

.PHONY: check-osdev-interrupts check-osdev-interrupts-sanitize check-osdev-interrupt-assembly
check-osdev-interrupts: build/minyarc build/minyar-runtime.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/osdev-interrupts.py --phase ir
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/osdev-interrupts.py --phase host-flags

check-osdev-interrupts-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/osdev-interrupts.py --phase ir --sanitized-compiler
	MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_RUNTIME=build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS="$(SANITIZER_FLAGS)" $(SANITIZER_LIMITED) python3 tests/osdev-interrupts.py --phase host-flags --sanitized-compiler

# Requires the subsequent hardware entry-ABI implementation; absence fails closed.
check-osdev-interrupt-assembly: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/osdev-interrupts.py --phase assembly --case signal-zero

check check-portable: check-osdev-fields check-osdev-workflow check-osdev-freestanding check-register-layouts check-osdev-rtc check-osdev-interrupts
check-sanitize: check-osdev-fields-sanitize check-register-layouts-sanitize check-osdev-rtc-sanitize check-osdev-interrupts-sanitize

# Optional real hardware-emulation proof, separate from portable fake-tool tests.
.PHONY: check-osdev-qemu
OSDEV_ARCH ?= arm64
check-osdev-qemu: build/minyarc
	python3 tools/osdev.py test --arch "$(OSDEV_ARCH)" --kernel-source os/tests/fields-kernel.min --expect "OSDEV FIELDS PASS" --timeout 30

.PHONY: check-osdev-callback-qemu
check-osdev-callback-qemu: build/minyarc
	python3 tools/osdev.py test --arch "$(OSDEV_ARCH)" --kernel-source os/tests/callback-kernel.min --expect "OSDEV CALLBACK PASS" --timeout 30

.PHONY: check-osdev-freestanding
check-osdev-freestanding: build/.toolchain.json build/minyarc check-osdev-runtime check-osdev-callback-domain
	MINYAR_TEST_CLANG="$(LLVM_CC)" python3 tests/osdev-freestanding.py
