build/minyar-runtime.o: runtime/minyar_runtime.c $(RUNTIME_HEADERS) $(BUILD_RULES) | build
	$(LIMITED) "$(LLVM_CC)" $(LLVM_FLAGS) $(PROGRAM_RUNTIME_FLAGS) -c $< -o $@

# Reuse the public launcher's standard configuration, including stack owners.
# Publish complete artifacts atomically when concurrent launchers build them.
build/minyar-default-runtime.o: runtime/minyar_default_runtime.c runtime/minyar_runtime.c runtime/minyar_stack_frames.h $(RUNTIME_HEADERS) $(BUILD_RULES) | build
	@set -eu; temporary=$$(mktemp "$@.XXXXXXXX"); \
	trap 'rm -f "$$temporary"' 0; \
	trap 'exit 1' HUP INT TERM; \
	$(LIMITED) "$(LLVM_CC)" $(LLVM_FLAGS) -c $< -o "$$temporary"; \
	mv -f "$$temporary" "$@"

build/minyar-default-runtime-release.ll: runtime/minyar_default_runtime.c runtime/minyar_runtime.c runtime/minyar_stack_frames.h $(RUNTIME_HEADERS) $(BUILD_RULES) | build
	@set -eu; temporary=$$(mktemp -d "$@.XXXXXXXX"); \
	trap 'rm -rf "$$temporary"' 0; \
	trap 'exit 1' HUP INT TERM; \
	$(LIMITED) "$(LLVM_CC)" $(LLVM_FLAGS) -S -emit-llvm $< -o "$$temporary/raw.ll"; \
	sed -E 's/"(target-cpu|target-features|tune-cpu)"="[^"]*" ?//g' "$$temporary/raw.ll" > "$$temporary/runtime.ll"; \
	mv -f "$$temporary/runtime.ll" "$@"

# Ordinary program runtime, including automatic reclamation. Generic target
# attributes allow its checked hot paths to inline into Minyar's generated IR.
build/minyar-runtime-release.ll: runtime/minyar_runtime.c $(RUNTIME_HEADERS) $(BUILD_RULES) | build
	$(LIMITED) "$(LLVM_CC)" $(LLVM_FLAGS) $(PROGRAM_RUNTIME_FLAGS) -S -emit-llvm $< -o $@.tmp
	sed -E 's/"(target-cpu|target-features|tune-cpu)"="[^"]*" ?//g' $@.tmp > $@
	rm -f $@.tmp

# The compiler links its runtime as LLVM IR. Clang stamps C functions with the
# host's target-cpu and target-features, and LLVM refuses to inline a function
# into a caller whose features differ, so those attributes are stripped to let
# the runtime's small operations inline into generated code.
build/minyar-compiler-runtime.ll: runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(LIMITED) "$(LLVM_CC)" $(LLVM_FLAGS) $(COMPILER_RUNTIME_FLAGS) -S -emit-llvm $< -o $@.tmp
	sed -E 's/"(target-cpu|target-features|tune-cpu)"="[^"]*" ?//g' $@.tmp > $@
	rm -f $@.tmp

build/minyar-compiler-runtime-sanitize.o: runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(SANITIZER_LIMITED) "$(LLVM_CC)" $(SANITIZER_FLAGS) $(COMPILER_RUNTIME_FLAGS) -c $< -o $@

build/runtime-unit: tests/runtime-unit.c runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(LIMITED) "$(LLVM_CC)" $(CFLAGS) $< $(LDLIBS) -o $@

build/minyar-runtime-sanitize.o: runtime/minyar_runtime.c $(RUNTIME_HEADERS) $(BUILD_RULES) | build
	$(SANITIZER_LIMITED) "$(LLVM_CC)" $(SANITIZER_FLAGS) $(PROGRAM_RUNTIME_FLAGS) -c $< -o $@

build/runtime-unit-sanitize: tests/runtime-unit.c runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(SANITIZER_LIMITED) "$(LLVM_CC)" $(SANITIZER_FLAGS) $< $(LDLIBS) -o $@

build/ownership-runtime.o: tests/ownership-runtime.c runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(SANITIZER_LIMITED) "$(LLVM_CC)" $(SANITIZER_FLAGS) -c $< -o $@

# Explicit allocator profile; this does not change the ordinary runtime target.
build/minyar-runtime-system.o: runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(LIMITED) "$(LLVM_CC)" $(LLVM_FLAGS) -DMINYAR_SYSTEM_HEAP=1 -c $< -o $@

build/minyar-runtime-bounded.o: runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(LIMITED) "$(LLVM_CC)" $(LLVM_FLAGS) $(BOUNDED_FLAGS) -c $< -o $@

build/bounded-runtime: tests/bounded-runtime.c runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(LIMITED) "$(LLVM_CC)" $(CFLAGS) $< $(LDLIBS) -o $@

build/bounded-runtime-sanitize: tests/bounded-runtime.c runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(SANITIZER_LIMITED) "$(LLVM_CC)" $(SANITIZER_FLAGS) $< $(LDLIBS) -o $@

build/bounded-ownership-runtime.o: tests/bounded-ownership-runtime.c runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(SANITIZER_LIMITED) "$(LLVM_CC)" $(SANITIZER_FLAGS) -c $< -o $@

build/production-live-oracle: experiments/memory/production-live-oracle.c runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(SANITIZER_LIMITED) "$(LLVM_CC)" $(SANITIZER_FLAGS) $< $(LDLIBS) -o $@

build/production-frame-oracle: experiments/memory/production-frame-oracle.c experiments/memory/production-live-oracle.c runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(SANITIZER_LIMITED) "$(LLVM_CC)" $(SANITIZER_FLAGS) $< $(LDLIBS) -o $@

build/bounded-list-capacity: tests/bounded-list-capacity.c runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(LIMITED) "$(LLVM_CC)" $(CFLAGS) $< $(LDLIBS) -o $@

build/bounded-list-capacity-sanitize: tests/bounded-list-capacity.c runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(SANITIZER_LIMITED) "$(LLVM_CC)" $(SANITIZER_FLAGS) $< $(LDLIBS) -o $@

# Explicit eager opt-out for users who accept graph-sized release work.
build/minyar-runtime-eager.o: runtime/minyar_runtime.c $(RUNTIME_HEADERS) $(BUILD_RULES) | build
	$(LIMITED) "$(LLVM_CC)" $(LLVM_FLAGS) -c $< -o $@

build/minyar-runtime-eager-release.ll: runtime/minyar_runtime.c $(RUNTIME_HEADERS) $(BUILD_RULES) | build
	$(LIMITED) "$(LLVM_CC)" $(LLVM_FLAGS) -S -emit-llvm $< -o $@.tmp
	sed -E 's/"(target-cpu|target-features|tune-cpu)"="[^"]*" ?//g' $@.tmp > $@
	rm -f $@.tmp
