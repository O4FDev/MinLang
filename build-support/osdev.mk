.PHONY: check-osdev-fields check-osdev-fields-sanitize check-osdev-workflow check-osdev-host

build/tooling/tests/device-fields.ll: tests/frontend-fixtures.min
check-osdev-fields: build/minyarc build/minyar-runtime.o build/tooling/tests/device-fields
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/device-fields

check-osdev-fields-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/device-fields
	MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS="$(SANITIZER_FLAGS)" $(SANITIZER_LIMITED) ./build/tooling/tests/device-fields

check-osdev-workflow:
	python3 tests/osdev-workflow.py

check-osdev-host: check-osdev-fields check-security-os-http

check check-portable: check-osdev-fields check-osdev-workflow check-osdev-freestanding
check-sanitize: check-osdev-fields-sanitize

# Optional real hardware-emulation proof, separate from portable fake-tool tests.
.PHONY: check-osdev-qemu
OSDEV_ARCH ?= arm64
check-osdev-qemu: build/minyarc
	python3 tools/osdev.py test --arch "$(OSDEV_ARCH)" --kernel-source os/tests/fields-kernel.min --expect "OSDEV FIELDS PASS" --timeout 30

.PHONY: check-osdev-freestanding
check-osdev-freestanding: build/.toolchain.json
	MINYAR_TEST_CLANG="$(LLVM_CC)" python3 tests/osdev-freestanding.py
