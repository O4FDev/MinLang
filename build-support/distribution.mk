# Release construction needs Python on the build host, never on the user's Mac.
.PHONY: package-macos check-macos-distribution
package-macos:
	python3 scripts/package-macos.py --llvm "$(MINYAR_LLVM_ROOT)" --version "$(MINYAR_VERSION)" --output "$(CURDIR)/build/releases"

check-macos-distribution:
	python3 tests/macos-distribution.py --distribution "$(MINYAR_DISTRIBUTION)"
