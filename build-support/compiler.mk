build/stage0: bootstrap/stage0.c vendor/stb_ds.h build/.toolchain.json | build
	"$(CC)" $(CPPFLAGS) $(CFLAGS) $< -o $@

build/compiler-stage1.ll: compiler/compiler.min build/stage0
	$(LIMITED) ./build/stage0 $< -o $@

build/compiler-stage1: build/compiler-stage1.ll build/minyar-compiler-runtime.ll
	$(LIMITED) "$(LLVM_CC)" $(LLVM_FLAGS) $(COMPILER_LTO_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/compiler-stage2-sanitize.ll: build/compiler-stage2.ll tests/llvm_sanitizer.py tools/sanitizer_llvm.py
	$(SANITIZER_LIMITED) python3 tests/llvm_sanitizer.py $< $@

build/minyarc-sanitize: build/compiler-stage2-sanitize.ll build/minyar-compiler-runtime-sanitize.o
	$(SANITIZER_LIMITED) "$(LLVM_CC)" $(SANITIZER_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/compiler-stage2.ll: compiler/compiler.min build/compiler-stage1
	$(LIMITED) ./build/compiler-stage1 $< $@

build/minyarc: build/compiler-stage2.ll build/minyar-compiler-runtime.ll
	$(LIMITED) "$(LLVM_CC)" $(LLVM_FLAGS) $(COMPILER_LTO_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/compiler-stage3.ll: compiler/compiler.min build/minyarc
	$(LIMITED) ./build/minyarc $< $@

build/compiler-bootstrap.ll: build/compiler-stage1.ll
	cp $< $@

build/compiler-bootstrap: build/compiler-bootstrap.ll build/minyar-compiler-runtime.ll
	"$(LLVM_CC)" $(LLVM_FLAGS) $(COMPILER_LTO_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

# The module frontend is optional. Its guarded build adapter is applied to the
# current core without changing the ordinary compiler or its fixed budgets.
build/module-compiler.min: compiler/compiler.min compiler/module-compiler.min compiler/module-compiler-adapter.patch scripts/build-module-compiler.py | build
	python3 scripts/build-module-compiler.py $@

build/module-compiler-stage1.ll: build/module-compiler.min build/minyarc
	$(LIMITED) ./build/minyarc $< $@

build/module-compiler-stage1: build/module-compiler-stage1.ll build/minyar-compiler-runtime.ll
	$(LIMITED) "$(LLVM_CC)" $(LLVM_FLAGS) $(COMPILER_LTO_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/module-compiler-stage2.ll: build/module-compiler.min build/module-compiler-stage1
	$(LIMITED) ./build/module-compiler-stage1 $< $@

build/minyarc-modules: build/module-compiler-stage2.ll build/minyar-compiler-runtime.ll
	$(LIMITED) "$(LLVM_CC)" $(LLVM_FLAGS) $(COMPILER_LTO_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/module-compiler-stage3.ll: build/module-compiler.min build/minyarc-modules
	$(LIMITED) ./build/minyarc-modules $< $@

build/minyar-module-build: tools/module-build.c build/.toolchain.json | build
	$(LIMITED) "$(CC)" $(CFLAGS) $< -o $@

build/module-compiler-sanitize.ll: build/module-compiler-stage2.ll tests/llvm_sanitizer.py tools/sanitizer_llvm.py
	$(SANITIZER_LIMITED) python3 tests/llvm_sanitizer.py $< $@

build/minyarc-modules-sanitize: build/module-compiler-sanitize.ll build/minyar-compiler-runtime-sanitize.o
	$(SANITIZER_LIMITED) "$(LLVM_CC)" $(SANITIZER_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/minyar-module-build-sanitize: tools/module-build.c build/.toolchain.json | build
	$(SANITIZER_LIMITED) "$(CC)" -std=c11 -Wall -Wextra -Werror $(SANITIZER_FLAGS) $< -o $@

# Captures and callable types extend the same parser through guarded adapters.
# Only programs whose parsed syntax requests the extension use this frontend.
build/closure-compiler.min: compiler/compiler.min compiler/closure-compiler.min compiler/managed-graphs-adapter.patch scripts/build-closure-compiler.py scripts/build-module-compiler.py | build
	python3 scripts/build-closure-compiler.py $@

build/closure-compiler-stage1.ll: build/closure-compiler.min build/minyarc
	$(LIMITED) ./build/minyarc $< $@

build/closure-compiler-stage1: build/closure-compiler-stage1.ll build/minyar-compiler-runtime.ll
	$(LIMITED) "$(LLVM_CC)" $(LLVM_FLAGS) $(COMPILER_LTO_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/closure-compiler-stage2.ll: build/closure-compiler.min build/closure-compiler-stage1
	$(LIMITED) ./build/closure-compiler-stage1 $< $@

build/minyarc-callbacks: build/closure-compiler-stage2.ll build/minyar-compiler-runtime.ll
	$(LIMITED) "$(LLVM_CC)" $(LLVM_FLAGS) $(COMPILER_LTO_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/closure-compiler-stage3.ll: build/closure-compiler.min build/minyarc-callbacks
	$(LIMITED) ./build/minyarc-callbacks $< $@

build/closure-compiler-sanitize.ll: build/closure-compiler-stage2.ll tests/llvm_sanitizer.py tools/sanitizer_llvm.py
	$(SANITIZER_LIMITED) python3 tests/llvm_sanitizer.py $< $@

build/minyarc-callbacks-sanitize: build/closure-compiler-sanitize.ll build/minyar-compiler-runtime-sanitize.o
	$(SANITIZER_LIMITED) "$(LLVM_CC)" $(SANITIZER_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

# Typed Result is an optional frontend assembled from the same guarded core.
build/errors-compiler.min: compiler/compiler.min compiler/errors-compiler.min compiler/closure-compiler.min compiler/managed-graphs-adapter.patch scripts/build-closure-compiler.py scripts/build-module-compiler.py compiler/build-errors-compiler.py | build
	python3 compiler/build-errors-compiler.py $@

build/errors-compiler-stage1.ll: build/errors-compiler.min build/minyarc
	$(LIMITED) ./build/minyarc $< $@

build/errors-compiler-stage1: build/errors-compiler-stage1.ll build/minyar-compiler-runtime.ll
	$(LIMITED) "$(LLVM_CC)" $(LLVM_FLAGS) $(COMPILER_LTO_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/errors-compiler-stage2.ll: build/errors-compiler.min build/errors-compiler-stage1
	$(LIMITED) ./build/errors-compiler-stage1 $< $@

build/minyarc-errors: build/errors-compiler-stage2.ll build/minyar-compiler-runtime.ll
	$(LIMITED) "$(LLVM_CC)" $(LLVM_FLAGS) $(COMPILER_LTO_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/errors-compiler-stage3.ll: build/errors-compiler.min build/minyarc-errors
	$(LIMITED) ./build/minyarc-errors $< $@

build/errors-compiler-sanitize.ll: build/errors-compiler-stage2.ll tests/llvm_sanitizer.py tools/sanitizer_llvm.py
	$(SANITIZER_LIMITED) python3 tests/llvm_sanitizer.py $< $@

build/minyarc-errors-sanitize: build/errors-compiler-sanitize.ll build/minyar-compiler-runtime-sanitize.o
	$(SANITIZER_LIMITED) "$(LLVM_CC)" $(SANITIZER_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

# The request frontend emits only parser status 87; it is never self-hosted.
build/errors-request.min: compiler/compiler.min compiler/closure-compiler.min compiler/errors-request.min compiler/managed-graphs-adapter.patch scripts/build-closure-compiler.py scripts/build-module-compiler.py compiler/build-errors-request.py | build
	python3 compiler/build-errors-request.py $@

build/errors-request.ll: build/errors-request.min build/minyarc
	$(LIMITED) ./build/minyarc $< $@

build/minyarc-errors-request: build/errors-request.ll build/minyar-compiler-runtime.ll
	$(LIMITED) "$(LLVM_CC)" $(LLVM_FLAGS) $(COMPILER_LTO_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/errors-request-sanitize.ll: build/errors-request.ll tests/llvm_sanitizer.py tools/sanitizer_llvm.py
	$(SANITIZER_LIMITED) python3 tests/llvm_sanitizer.py $< $@

build/minyarc-errors-request-sanitize: build/errors-request-sanitize.ll build/minyar-compiler-runtime-sanitize.o
	$(SANITIZER_LIMITED) "$(LLVM_CC)" $(SANITIZER_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

# The historical comparator has frozen source bytes and an unchanged hash.
# Current compiler and optional frontends continue to use the maintained core.
build/compiler-baseline-control.min: compiler/foundation-baseline.min scripts/build-closure-compiler.py | build
	python3 scripts/build-closure-compiler.py --baseline $@

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
