PHASE1_TOOLS = build/tooling/.github/phase1/private-atacama build/tooling/.github/phase1/test-qualification build/tooling/.github/phase1/fake-make
PHASE1_NATIVE = .github/phase1/process.c runtime/native/sha256.c runtime/native/deflate.c

.PHONY: phase1-tools
phase1-tools: $(PHASE1_TOOLS)

$(PHASE1_TOOLS): TOOL_NATIVE = $(PHASE1_NATIVE)
$(PHASE1_TOOLS): TOOL_LIBS = $(TOOL_CRYPTO) -lz
$(PHASE1_TOOLS): $(PHASE1_NATIVE) runtime/native/compression.h
$(PHASE1_TOOLS:=.ll): .github/phase1/process.min .github/phase1/archive.min
