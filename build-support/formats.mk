# Data-format modules are opt-in at link time. Their normal gates exercise the
# standard launcher and the direct custom-link path used by image tooling.
.PHONY: check-formats check-formats-sanitize check-compression check-compression-sanitize
.PHONY: check-sha256 check-sha256-sanitize check-tar check-tar-sanitize
.PHONY: check-format-provider check-formats-wiring
.PHONY: check-formats-pipeline check-formats-pipeline-sanitize
.PHONY: bench-formats bench-compression bench-sha256 bench-tar

check-compression: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/compression-provider.py
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/compression.py --mode native

check-sha256: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/sha256.py

check-tar: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/tar.py

# Resolve one compiler path, including spaces/apostrophes and MSYS native
# spellings. Keep selection target-scoped so ordinary portable builds retain
# LLVM_CC. The guest's matching pkg-config configuration selects its providers.
FORMATS_SANITIZER_QUOTE = '$(subst ','"'"',$(1))'
FORMATS_SANITIZER_CLANG = $(if $(MINYAR_SANITIZER_CLANG),$(shell python3 -c 'import sys; sys.path.insert(0, "tools"); from host_paths import host_path; print(host_path(sys.argv[1]))' $(call FORMATS_SANITIZER_QUOTE,$(MINYAR_SANITIZER_CLANG))),$(LLVM_CC))
FORMATS_SANITIZER_DIRECTORY = $(if $(MINYAR_SANITIZER_CLANG),$(shell python3 -c 'import sys; sys.path.insert(0, "tools"); from host_paths import host_path; print(host_path(sys.argv[1]).parent)' $(call FORMATS_SANITIZER_QUOTE,$(MINYAR_SANITIZER_CLANG))))
FORMATS_SANITIZER_ENV = PATH=$(call FORMATS_SANITIZER_QUOTE,$(if $(FORMATS_SANITIZER_DIRECTORY),$(FORMATS_SANITIZER_DIRECTORY):)$(PATH)) MINYAR_TEST_CLANG=$(call FORMATS_SANITIZER_QUOTE,$(FORMATS_SANITIZER_CLANG)) UBSAN_OPTIONS=halt_on_error=1

check-compression-sanitize: build/minyarc
	$(FORMATS_SANITIZER_ENV) $(SANITIZER_LIMITED) python3 tests/compression.py --mode sanitize

check-sha256-sanitize: build/minyarc
	$(FORMATS_SANITIZER_ENV) $(SANITIZER_LIMITED) python3 tests/sha256.py --sanitize

check-tar-sanitize: build/minyarc
	$(FORMATS_SANITIZER_ENV) $(SANITIZER_LIMITED) python3 tests/tar.py --sanitize

check-format-provider:
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/format-provider.py

check-formats-wiring:
	$(LIMITED) python3 tests/formats-wiring.py

check-formats-pipeline: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/formats.py

check-formats-pipeline-sanitize: build/minyarc
	$(FORMATS_SANITIZER_ENV) $(SANITIZER_LIMITED) python3 tests/formats.py --sanitize

check-formats: check-formats-wiring check-format-provider check-compression check-sha256 check-tar check-formats-pipeline
check-formats-sanitize: check-compression-sanitize check-sha256-sanitize check-tar-sanitize check-formats-pipeline-sanitize

bench-compression: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 benchmarks/compression.py --artifacts build/compression-benchmark --prepare-only --compiler "$(abspath build/minyarc)"
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 benchmarks/compression.py --artifacts build/compression-benchmark --run-only

bench-sha256: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/sha256-bench.py

bench-tar: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 benchmarks/tar/run.py --prepare
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 benchmarks/tar/run.py --measure

bench-formats: bench-compression bench-sha256 bench-tar

# Opt-in until CI installs static libzstd, zlib, libcrypto and libarchive providers:
# run `make check-formats check-formats-sanitize` on a host that has them.
