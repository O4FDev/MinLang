# Explicit Linux-only qualification. Ordinary check/portable recipes do not opt in.
build/test-memory-budget: tools/test-memory-budget.c | build
	$(LLVM_CC) -std=c11 -O2 -Wall -Wextra -Werror "$<" -o "$@"

build/cgroup-memory-fixture: tests/cgroup-memory-fixture.c | build
	$(LLVM_CC) -std=c11 -O2 -Wall -Wextra -Werror "$<" -o "$@"

.PHONY: check-test-memory
check-test-memory: build/test-memory-budget build/cgroup-memory-fixture
	python3 tests/test-memory-budget.py --helper "$(abspath build/test-memory-budget)" --fixture "$(abspath build/cgroup-memory-fixture)" --evidence-root "$(abspath build/test-memory-results)"
