COMPILER_SOURCES = compiler/stages/source.min \
	compiler/stages/lexer.min \
	compiler/stages/symbols.min \
	compiler/stages/declarations.min \
	compiler/stages/runtime-abi.min \
	compiler/stages/types.min $(wildcard compiler/stages/c-layout.min) \
	compiler/stages/ownership.min \
	compiler/stages/operators.min \
	compiler/stages/expressions.min \
	compiler/stages/statements.min \
	compiler/stages/literals.min \
	compiler/stages/calls.min \
	compiler/stages/assignment.min \
	compiler/stages/native.min \
	compiler/stages/effects.min \
	compiler/stages/functions.min \
	compiler/stages/pipeline.min \
	compiler/stages/modules.min \
	compiler/stages/incremental.min \
	compiler/closure-compiler.min \
	compiler/errors-compiler.min \
	compiler/calldepth-compiler.min \
	compiler/thread-compiler.min \
	compiler/compiler.min

build/compiler.min: $(COMPILER_SOURCES) build-support/compiler.mk | build
	cat $(COMPILER_SOURCES) > $@.tmp
	awk '/^function [[:alnum:]_]+\(/ { name = $$0; sub(/^function /, "", name); sub(/\(.*/, "", name); if (seen[name]++) { print "duplicate compiler function" > "/dev/stderr"; exit 1 } }' $@.tmp
	mv $@.tmp $@

build/stage0: bootstrap/stage0.c vendor/stb_ds.h build/.toolchain.json | build
	"$(CC)" $(CPPFLAGS) $(CFLAGS) $< -o $@

build/compiler-stage1.ll: build/compiler.min build/stage0
	$(LIMITED) ./build/stage0 $< -o $@

build/compiler-stage1: build/compiler-stage1.ll build/minyar-compiler-runtime.ll
	$(LIMITED) "$(LLVM_CC)" $(LLVM_FLAGS) $(COMPILER_LTO_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/compiler-stage2-sanitize.ll: build/compiler-stage2.ll tests/llvm_sanitizer.py tools/sanitizer_llvm.py
	$(SANITIZER_LIMITED) python3 tests/llvm_sanitizer.py $< $@

build/minyarc-sanitize: build/compiler-stage2-sanitize.ll build/minyar-compiler-runtime-sanitize.o
	$(SANITIZER_LIMITED) "$(LLVM_CC)" $(SANITIZER_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/compiler-stage2.ll: build/compiler.min build/compiler-stage1
	$(LIMITED) ./build/compiler-stage1 $< $@

build/minyarc: build/compiler-stage2.ll build/minyar-compiler-runtime.ll
	$(LIMITED) "$(LLVM_CC)" $(LLVM_FLAGS) $(COMPILER_LTO_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/compiler-stage3.ll: build/compiler.min build/minyarc
	$(LIMITED) ./build/minyarc $< $@

build/compiler-bootstrap.ll: build/compiler-stage1.ll
	cp $< $@

build/compiler-bootstrap: build/compiler-bootstrap.ll build/minyar-compiler-runtime.ll
	"$(LLVM_CC)" $(LLVM_FLAGS) $(COMPILER_LTO_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

COMPILER_COMPAT_NAMES = modules callbacks errors errors-request calldepth threads
COMPILER_COMPAT_FAMILIES = module closure errors calldepth thread

$(addprefix build/minyarc-,$(COMPILER_COMPAT_NAMES)): build/minyarc
	cp $< $@

$(addsuffix -sanitize,$(addprefix build/minyarc-,$(COMPILER_COMPAT_NAMES))): build/minyarc-sanitize
	cp $< $@

$(addsuffix -compiler.min,$(addprefix build/,$(COMPILER_COMPAT_FAMILIES))): build/compiler.min
	cp $< $@

build/errors-request.min: build/compiler.min
	cp $< $@

$(addsuffix -compiler-stage1.ll,$(addprefix build/,$(COMPILER_COMPAT_FAMILIES))): build/compiler-stage1.ll
	cp $< $@

$(addsuffix -compiler-stage1,$(addprefix build/,$(COMPILER_COMPAT_FAMILIES))): build/compiler-stage1
	cp $< $@

$(addsuffix -compiler-stage2.ll,$(addprefix build/,$(COMPILER_COMPAT_FAMILIES))): build/compiler-stage2.ll
	cp $< $@

$(addsuffix -compiler-stage3.ll,$(addprefix build/,$(COMPILER_COMPAT_FAMILIES))): build/compiler-stage3.ll
	cp $< $@

build/minyar-module-build: tools/module-build.c build/.toolchain.json | build
	$(LIMITED) "$(CC)" $(CFLAGS) $< -o $@

build/minyar-module-build-sanitize: tools/module-build.c build/.toolchain.json | build
	$(SANITIZER_LIMITED) "$(CC)" -std=c11 -Wall -Wextra -Werror $(SANITIZER_FLAGS) $< -o $@

FOUNDATION_BASELINE_COMMIT = 4f2d21e541e886bb81f4cd2daee7f11d518fe53b
FOUNDATION_BASELINE_SHA256 = a5f30a7954381231fbe04a712b72bd9663d1bd7082c667fef851b739ec63c3cf

build/compiler-baseline-control.min: build-support/compiler.mk | build
	git show $(FOUNDATION_BASELINE_COMMIT):compiler/foundation-baseline.min > $@.tmp 2>/dev/null || curl --fail --location --retry 3 https://raw.githubusercontent.com/O4FDev/MinLang/$(FOUNDATION_BASELINE_COMMIT)/compiler/foundation-baseline.min -o $@.tmp
	printf '%s  %s\n' '$(FOUNDATION_BASELINE_SHA256)' '$@.tmp' | shasum -a 256 --check
	mv $@.tmp $@

build/compiler-baseline-control.ll: build/compiler-baseline-control.min build/minyarc
	$(LIMITED) ./build/minyarc $< $@

build/minyarc-baseline: build/compiler-baseline-control.ll build/minyar-compiler-runtime.ll
	$(LIMITED) "$(LLVM_CC)" $(LLVM_FLAGS) $(COMPILER_LTO_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

# Metadata probes preserve the stamp mtime on a warm build. Every runtime and
# compiler artifact depends on it, so switching Clang never reuses old LLVM IR.
export CC LLVM_CC CPPFLAGS CFLAGS LLVM_FLAGS LDLIBS SANITIZER_FLAGS
export COMPILER_RUNTIME_FLAGS COMPILER_LTO_FLAGS PROGRAM_RUNTIME_FLAGS BOUNDED_FLAGS
.PHONY: FORCE
FORCE:

build/.toolchain.json: FORCE scripts/toolchain-stamp.py tools/host_paths.py | build
	@python3 scripts/toolchain-stamp.py $@

.PHONY: check-native-records
check-native-records: build/minyarc build/minyarc-errors build/minyar-runtime.o
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/native-records.py

check check-portable: check-native-records
