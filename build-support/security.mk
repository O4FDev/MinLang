.PHONY: check-security-static check-security-os check-security-os-http check-security-os-http-sanitize

# The native analyzer is intentionally a PR gate, not a commit hook.
check-security-static:
	MINYAR_CLANG="$(LLVM_CC)" sh scripts/security-static-analysis.sh

# Compile each freestanding entry point on PRs after OS parser edits.
# ROOT is passed so os/Makefile names its outputs from the same root spelling as these goals;
# its own $(abspath ..) can differ from $(CURDIR) when the checkout is reached through a symlink or bind mount.
check-security-os: build/minyarc
	$(MAKE) -C os ROOT="$(CURDIR)" "$(CURDIR)/build/os/x86_64/kernel.ll" "$(CURDIR)/build/os/x86_64/loader.ll"
	$(MAKE) -C os ROOT="$(CURDIR)" ARCH=arm64 "$(CURDIR)/build/os/arm64/kernel.ll"
	MINYAR_CLANG="$(LLVM_CC)" sh scripts/security-freestanding-math.sh

# Exercise the pure OS response parser with hostile bytes in a hosted process.
check-security-os-http: build/tooling/tests/os-http-response.ll build/minyar-runtime.o
	$(LIMITED) "$(LLVM_CC)" -O1 -Wno-override-module "$<" "build/minyar-runtime.o" -lm -o "build/os-http-response-test"
	$(LIMITED) ./build/os-http-response-test

check-security-os-http-sanitize: build/tooling/tests/os-http-response.ll build/minyar-runtime-sanitize.o
	$(SANITIZER_LIMITED) "$(LLVM_CC)" $(SANITIZER_FLAGS) "$<" "build/minyar-runtime-sanitize.o" -lm -o "build/os-http-response-test-sanitize"
	$(SANITIZER_LIMITED) ./build/os-http-response-test-sanitize
