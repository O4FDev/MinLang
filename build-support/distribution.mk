# Release construction needs Python on the build host, never on the user's Mac.
.PHONY: package-macos check-macos-distribution
package-macos:
	python3 scripts/package-macos.py --llvm "$(MINYAR_LLVM_ROOT)" --version "$(MINYAR_VERSION)" --output "$(CURDIR)/build/releases"

check-macos-distribution:
	python3 tests/macos-distribution.py --distribution "$(MINYAR_DISTRIBUTION)"

.PHONY: package-linux check-linux-distribution check-linux-packager
package-linux:
	python3 scripts/package-linux.py --llvm "$(MINYAR_LLVM_ROOT)" --version "$(MINYAR_VERSION)" --output "$(CURDIR)/build/releases"

check-linux-distribution:
	python3 tests/linux-distribution.py --distribution "$(MINYAR_DISTRIBUTION)"

check-linux-packager:
	python3 tests/linux-packager.py "$(LLVM_CC)"
