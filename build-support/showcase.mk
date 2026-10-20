.PHONY: check-showcase check-showcase-daybook check-showcase-tideboard check-showcase-lantern-trail

SHOWCASE_DEPS = build/minyarc build/minyar-default-runtime.o build/minyar-default-runtime-release.ll build/tooling/tools/clang-driver

check-showcase: $(SHOWCASE_DEPS)
	MINYAR_CLANG="$(LLVM_CC)" python3 "tests/showcase.py"

check-showcase-daybook: $(SHOWCASE_DEPS)
	MINYAR_CLANG="$(LLVM_CC)" python3 "tests/showcase.py" --only daybook

check-showcase-tideboard: $(SHOWCASE_DEPS)
	MINYAR_CLANG="$(LLVM_CC)" python3 "tests/showcase.py" --only tideboard

check-showcase-lantern-trail: $(SHOWCASE_DEPS)
	MINYAR_CLANG="$(LLVM_CC)" python3 "tests/showcase.py" --only lantern-trail

ifeq ($(filter Windows_NT,$(OS))$(filter MSYS% MINGW% CYGWIN%,$(shell uname -s)),)
check check-portable: check-showcase
endif
