# Data-format modules are opt-in at link time. Their normal gates exercise the
# standard launcher and the direct custom-link path used by image tooling.
.PHONY: check-formats check-formats-sanitize check-compression check-compression-sanitize
.PHONY: check-sha256 check-sha256-sanitize check-tar check-tar-sanitize
.PHONY: check-format-provider check-formats-wiring
.PHONY: check-formats-pipeline check-formats-pipeline-sanitize
.PHONY: bench-formats bench-compression bench-sha256 bench-tar

build/tooling/tests/compression-codecs: private TOOL_NATIVE = tests/compression-codecs-oracle-runtime.c
build/tooling/tests/compression-codecs: private TOOL_LIBS = -lz -ldl
build/tooling/tests/compression-codecs: tests/compression-codecs-oracle-runtime.c
check-compression: build/minyarc build/tooling/tests/compression-codecs build/tooling/tests/compression-provider
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/compression-provider
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/compression-codecs --mode native

check-sha256: build/minyarc build/minyar-default-runtime.o
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

check-compression-sanitize: build/minyarc build/tooling/tests/compression-codecs
	$(FORMATS_SANITIZER_ENV) $(SANITIZER_LIMITED) ./build/tooling/tests/compression-codecs --mode sanitize

check-sha256-sanitize: build/minyarc
	$(FORMATS_SANITIZER_ENV) $(SANITIZER_LIMITED) python3 tests/sha256.py --sanitize

check-tar-sanitize: build/minyarc
	$(FORMATS_SANITIZER_ENV) $(SANITIZER_LIMITED) python3 tests/tar.py --sanitize

check-format-provider:
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/format-provider.py

check-formats-wiring: build/tooling/tests/formats-wiring
	$(LIMITED) ./build/tooling/tests/formats-wiring

check-formats-pipeline: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/formats.py

check-formats-pipeline-sanitize: build/minyarc
	$(FORMATS_SANITIZER_ENV) $(SANITIZER_LIMITED) python3 tests/formats.py --sanitize

.PHONY: check-erofs check-erofs-reference check-erofs-layers
check-erofs: build/minyarc tests/erofs.min tests/erofs-api.min tests/erofs-thread-main.min tests/erofs-thread-worker.min tests/erofs-thread-helper.min tests/erofs-thread-legacy.min tests/erofs-thread-legacy-helper.min tests/erofs-layers.sh tests/erofs-layers.min tests/erofs-layer-driver.min tests/erofs-tree.c tests/erofs-layers-thread-main.min tests/erofs-layers-thread-worker.min tests/erofs-layers-thread-helper.min tests/erofs-layers-thread-legacy.min tests/erofs-layers-thread-legacy-helper.min library/erofs.min runtime/native/erofs.c runtime/native/erofs_layers.h
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) bash tests/erofs.sh
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) bash tests/erofs-layers.sh

check-erofs-layers: build/minyarc tests/erofs-layers.sh tests/erofs-layers.min tests/erofs-layer-driver.min tests/erofs-tree.c tests/erofs-layers-thread-main.min tests/erofs-layers-thread-worker.min tests/erofs-layers-thread-helper.min tests/erofs-layers-thread-legacy.min tests/erofs-layers-thread-legacy-helper.min library/erofs.min runtime/native/erofs.c runtime/native/erofs_layers.h
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) bash tests/erofs-layers.sh

check-erofs-reference:
	MINYAR_TEST_CLANG="$(LLVM_CC)" bash tests/erofs-reference.sh

check-formats: check-formats-wiring check-format-provider check-compression check-sha256 check-tar check-formats-pipeline
check-formats-sanitize: check-compression-sanitize check-sha256-sanitize check-tar-sanitize check-formats-pipeline-sanitize

bench-compression: build/minyarc build/tooling/benchmarks/compression-bench
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/benchmarks/compression-bench --artifacts build/compression-benchmark --prepare-only --compiler "$(abspath build/minyarc)"
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/benchmarks/compression-bench --artifacts build/compression-benchmark --run-only

bench-sha256: build/minyarc build/minyar-default-runtime.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/sha256-bench.py

bench-tar: build/minyarc build/tooling/benchmarks/tar/run
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/benchmarks/tar/run --prepare
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/benchmarks/tar/run --measure

bench-formats: bench-compression bench-sha256 bench-tar

