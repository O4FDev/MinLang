# Data-format modules are opt-in at link time. Their normal gates exercise the
# standard launcher and the direct custom-link path used by image tooling.
.PHONY: check-formats check-formats-sanitize check-compression check-compression-sanitize
.PHONY: check-sha256 check-sha256-sanitize check-tar check-tar-sanitize
.PHONY: check-format-provider check-formats-wiring
.PHONY: check-formats-pipeline check-formats-pipeline-sanitize
.PHONY: bench-formats bench-compression bench-sha256 bench-tar

build/tooling/tests/compression-provider build/tooling/tests/compression-codecs build/tooling/tests/tar-test build/tooling/tests/tar-review-test build/tooling/tests/tar-copy-count build/tooling/tests/formats-test build/tooling/benchmarks/compression-bench build/tooling/benchmarks/tar/run: build/tooling/tools/clang-driver
build/tooling/tests/compression-codecs: TOOL_NATIVE = tests/compression-codecs-oracle-runtime.c runtime/native/sha256.c
build/tooling/tests/compression-codecs: TOOL_LIBS = -lz -ldl $(TOOL_CRYPTO)
build/tooling/tests/compression-codecs: tests/compression-codecs-oracle-runtime.c
check-compression: build/minyarc build/tooling/tests/compression-provider build/tooling/tests/compression-codecs
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/compression-provider
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/compression-codecs --mode native

build/tooling/tests/sha256-test: TOOL_NATIVE = tests/sha256-test-native.c
build/tooling/tests/sha256-test: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/sha256-test: tests/sha256-test-native.c
check-sha256: build/minyarc build/minyar-default-runtime.o build/tooling/tests/sha256-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/sha256-test

build/tooling/tests/tar-test: TOOL_NATIVE = tests/sha256-test-native.c
build/tooling/tests/tar-test: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/tar-test: tests/sha256-test-native.c
build/tooling/tests/tar-review-test: TOOL_NATIVE = tests/sha256-test-native.c
build/tooling/tests/tar-review-test: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/tar-review-test: tests/sha256-test-native.c
build/tooling/tests/tar-copy-count: TOOL_NATIVE = tests/sha256-test-native.c
build/tooling/tests/tar-copy-count: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/tar-copy-count: tests/sha256-test-native.c
build/tooling/tests/tar-copy-count: TOOL_RUNTIME = build/testing/cycle-runtime.o
build/tooling/tests/tar-copy-count: build/testing/cycle-runtime.o
check-tar: build/minyarc build/tooling/tests/tar-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/tar-test

# Resolve one compiler path, including spaces/apostrophes and MSYS native
# spellings. Keep selection target-scoped so ordinary portable builds retain
# LLVM_CC. The guest's matching pkg-config configuration selects its providers.
FORMATS_SANITIZER_QUOTE = '$(subst ','"'"',$(1))'
FORMATS_SANITIZER_CLANG = $(if $(MINYAR_SANITIZER_CLANG),$(shell sh tools/toolchain.sh host-path $(call FORMATS_SANITIZER_QUOTE,$(MINYAR_SANITIZER_CLANG))),$(LLVM_CC))
FORMATS_SANITIZER_DIRECTORY = $(if $(MINYAR_SANITIZER_CLANG),$(shell sh tools/toolchain.sh host-directory $(call FORMATS_SANITIZER_QUOTE,$(MINYAR_SANITIZER_CLANG))))
FORMATS_SANITIZER_ENV = PATH=$(call FORMATS_SANITIZER_QUOTE,$(if $(FORMATS_SANITIZER_DIRECTORY),$(FORMATS_SANITIZER_DIRECTORY):)$(PATH)) MINYAR_TEST_CLANG=$(call FORMATS_SANITIZER_QUOTE,$(FORMATS_SANITIZER_CLANG)) UBSAN_OPTIONS=halt_on_error=1

check-compression-sanitize: build/minyarc build/tooling/tests/compression-codecs
	$(FORMATS_SANITIZER_ENV) $(SANITIZER_LIMITED) ./build/tooling/tests/compression-codecs --mode sanitize

check-sha256-sanitize: build/minyarc build/tooling/tests/sha256-test
	$(FORMATS_SANITIZER_ENV) $(SANITIZER_LIMITED) ./build/tooling/tests/sha256-test --sanitize

check-tar-sanitize: build/minyarc build/tooling/tests/tar-test
	$(FORMATS_SANITIZER_ENV) $(SANITIZER_LIMITED) ./build/tooling/tests/tar-test --sanitize

check-format-provider:
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/format-provider.py

check-formats-wiring: build/tooling/tests/formats-wiring
	$(LIMITED) ./build/tooling/tests/formats-wiring

build/tooling/tests/formats-test: TOOL_NATIVE = tests/formats-oracles-runtime.c
build/tooling/tests/formats-test: TOOL_LIBS = $(TOOL_CRYPTO) -lz -lzstd
build/tooling/tests/formats-test: tests/formats-oracles-runtime.c
check-formats-pipeline: build/minyarc build/tooling/tests/formats-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/formats-test

check-formats-pipeline-sanitize: build/minyarc build/tooling/tests/formats-test
	$(FORMATS_SANITIZER_ENV) $(SANITIZER_LIMITED) ./build/tooling/tests/formats-test --sanitize

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

build/tooling/benchmarks/compression-bench: TOOL_NATIVE = tests/compression-codecs-oracle-runtime.c tests/sha256-test-native.c runtime/native/sha256.c
build/tooling/benchmarks/compression-bench: TOOL_LIBS = -lz -ldl $(TOOL_CRYPTO)
build/tooling/benchmarks/compression-bench: tests/compression-codecs-oracle-runtime.c tests/sha256-test-native.c runtime/native/sha256.c
bench-compression: build/minyarc build/tooling/benchmarks/compression-bench
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/benchmarks/compression-bench --artifacts build/compression-benchmark --prepare-only --compiler "$(abspath build/minyarc)"
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/benchmarks/compression-bench --artifacts build/compression-benchmark --run-only

build/tooling/tests/sha256-bench-driver: TOOL_NATIVE = tests/sha256-test-native.c
build/tooling/tests/sha256-bench-driver: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/sha256-bench-driver: tests/sha256-test-native.c
bench-sha256: build/minyarc build/minyar-default-runtime.o build/tooling/tests/sha256-bench-driver
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/sha256-bench-driver

build/tooling/benchmarks/tar/run: TOOL_NATIVE = tests/text-basics-benchmark-runtime.c tests/sha256-test-native.c
build/tooling/benchmarks/tar/run: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/benchmarks/tar/run: tests/text-basics-benchmark-runtime.c tests/sha256-test-native.c
bench-tar: build/minyarc build/tooling/benchmarks/tar/run
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/benchmarks/tar/run --prepare
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/benchmarks/tar/run --measure --output build/tar-native-benchmark/results.json

bench-formats: bench-compression bench-sha256 bench-tar

