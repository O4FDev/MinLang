build/hello.ll: examples/hello.min build/minyarc
	./build/minyarc $< $@

build/hello: build/hello.ll build/minyar-runtime.o
	"$(LLVM_CC)" $(LLVM_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/language-tour.ll: examples/language-tour.min build/minyarc
	./build/minyarc $< $@

build/language-tour: build/language-tour.ll build/minyar-runtime.o
	"$(LLVM_CC)" $(LLVM_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/records.ll: examples/records.min build/minyarc
	./build/minyarc $< $@

build/records: build/records.ll build/minyar-runtime.o
	"$(LLVM_CC)" $(LLVM_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/hello-self-hosted.ll: examples/hello.min build/compiler-bootstrap
	./build/compiler-bootstrap $< $@

build/hello-self-hosted: build/hello-self-hosted.ll build/minyar-runtime.o
	"$(LLVM_CC)" $(LLVM_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/integer-overflow.ll: tests/runtime/integer-overflow.min build/minyarc
	./build/minyarc $< $@

build/integer-overflow: build/integer-overflow.ll build/minyar-runtime.o
	"$(LLVM_CC)" $(LLVM_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/divide-by-zero.ll: tests/runtime/divide-by-zero.min build/minyarc
	./build/minyarc $< $@

build/divide-by-zero: build/divide-by-zero.ll build/minyar-runtime.o
	"$(LLVM_CC)" $(LLVM_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/text-and-files.ll: tests/runtime/text-and-files.min build/minyarc
	./build/minyarc $< $@

build/text-and-files: build/text-and-files.ll build/minyar-runtime.o
	"$(LLVM_CC)" $(LLVM_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/lists.ll: tests/runtime/lists.min build/minyarc
	./build/minyarc $< $@

build/lists: build/lists.ll build/minyar-runtime.o
	"$(LLVM_CC)" $(LLVM_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/newlines.ll: tests/runtime/newlines.min build/minyarc
	./build/minyarc $< $@

build/newlines: build/newlines.ll build/minyar-runtime.o
	"$(LLVM_CC)" $(LLVM_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/top-level.ll: tests/runtime/top-level.min build/minyarc
	./build/minyarc $< $@

build/top-level: build/top-level.ll build/minyar-runtime.o
	"$(LLVM_CC)" $(LLVM_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/top-level-exit.ll: tests/runtime/top-level-exit.min build/minyarc
	./build/minyarc $< $@

build/top-level-exit: build/top-level-exit.ll build/minyar-runtime.o
	"$(LLVM_CC)" $(LLVM_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/list-out-of-bounds.ll: tests/runtime/list-out-of-bounds.min build/minyarc
	./build/minyarc $< $@

build/list-out-of-bounds: build/list-out-of-bounds.ll build/minyar-runtime.o
	"$(LLVM_CC)" $(LLVM_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/text-indexing.ll: tests/runtime/text-indexing.min build/minyarc
	./build/minyarc $< $@

build/text-indexing: build/text-indexing.ll build/minyar-runtime.o
	"$(LLVM_CC)" $(LLVM_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

build/text-slice-out-of-bounds.ll: tests/runtime/text-slice-out-of-bounds.min build/minyarc
	./build/minyarc $< $@

build/text-slice-out-of-bounds: build/text-slice-out-of-bounds.ll build/minyar-runtime.o
	"$(LLVM_CC)" $(LLVM_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

emit: build/hello.ll
	@echo "wrote build/hello.ll"

run: build/hello
	./build/hello
