.PHONY: check-json-metadata-limits
check-json-metadata-limits: build/tooling/tests/json-metadata-limits.ll build/minyar-runtime.o
	@set -eu; for level in 0 2; do \
		$(LIMITED) "$(LLVM_CC)" -O$$level -Wno-override-module "$<" "build/minyar-runtime.o" -lm -o "build/json-metadata-limits-O$$level"; \
		$(LIMITED) "./build/json-metadata-limits-O$$level"; \
	done

check check-portable: check-json-metadata-limits
