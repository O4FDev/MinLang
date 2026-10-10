build/stage0: bootstrap/stage0.c vendor/stb_ds.h build/.toolchain.json | build
	"$(CC)" $(CPPFLAGS) $(CFLAGS) $< -o $@

build/compiler-stage1.ll: compiler/compiler.min build/stage0
	$(LIMITED) ./build/stage0 $< -o $@

build/compiler-stage1: build/compiler-stage1.ll build/minyar-compiler-runtime.ll
	$(LIMITED) "$(LLVM_CC)" $(LLVM_FLAGS) $(COMPILER_LTO_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/compiler-stage1-sanitize.ll: build/compiler-stage1.ll tests/llvm_sanitizer.py
	$(SANITIZER_LIMITED) python3 tests/llvm_sanitizer.py $< $@

build/minyarc-sanitize: build/compiler-stage1-sanitize.ll build/minyar-compiler-runtime-sanitize.o
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

build/module-compiler-sanitize.ll: build/module-compiler-stage2.ll tests/llvm_sanitizer.py
	$(SANITIZER_LIMITED) python3 tests/llvm_sanitizer.py $< $@

build/minyarc-modules-sanitize: build/module-compiler-sanitize.ll build/minyar-compiler-runtime-sanitize.o
	$(SANITIZER_LIMITED) "$(LLVM_CC)" $(SANITIZER_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/minyar-module-build-sanitize: tools/module-build.c build/.toolchain.json | build
	$(SANITIZER_LIMITED) "$(CC)" -std=c11 -Wall -Wextra -Werror $(SANITIZER_FLAGS) $< -o $@

# Metadata probes preserve the stamp mtime on a warm build. Every runtime and
# compiler artifact depends on it, so switching Clang never reuses old LLVM IR.
export CC LLVM_CC CPPFLAGS CFLAGS LLVM_FLAGS LDLIBS SANITIZER_FLAGS
export COMPILER_RUNTIME_FLAGS COMPILER_LTO_FLAGS PROGRAM_RUNTIME_FLAGS BOUNDED_FLAGS
.PHONY: FORCE
FORCE:

build/.toolchain.json: FORCE scripts/toolchain-stamp.py | build
	@python3 scripts/toolchain-stamp.py $@
