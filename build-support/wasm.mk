# Optional browser/WASI toolchain; the ordinary portable gate stays offline.
WASM_CC ?= $(LLVM_CC)
WASM_SYSROOT ?= build/wasm/sysroot
WASM_TARGET_FLAGS = --target=wasm32-wasip1 --sysroot="$(WASM_SYSROOT)" -resource-dir="$(WASM_SYSROOT)" -Wno-override-module
WASM_SJLJ_FLAGS = -mllvm -wasm-enable-sjlj -mllvm -wasm-use-legacy-eh=false
WASM_LINK_FLAGS = -Wl,-z,stack-size=8388608 -Wl,--max-memory=536870912 -lm -lsetjmp
WASM_HEADERS = $(wildcard runtime/minyar_*.h)
PLAYGROUND_SOURCES = $(wildcard playground/* playground/licenses/*) tools/build-playground.py tools/wasm-target.mjs
PLAYGROUND_LIBRARY = $(addsuffix .min,$(addprefix library/,maybe errors text math io process random json))

build/wasm/.prepared: tools/prepare-wasm.py | build
	python3 tools/prepare-wasm.py

build/wasm/compiler.ll: build/compiler-stage2.ll tools/wasm-target.mjs build/wasm/.prepared
	node tools/wasm-target.mjs --normalize "$<" "$@"

build/wasm/compiler.wasm: build/wasm/compiler.ll tools/wasm-compiler-runtime.c runtime/minyar_runtime.c $(WASM_HEADERS) build/wasm/.prepared
	"$(WASM_CC)" $(WASM_TARGET_FLAGS) $(WASM_SJLJ_FLAGS) -O2 "$<" tools/wasm-compiler-runtime.c $(WASM_LINK_FLAGS) -o "$@"

build/wasm/runtime.o: tools/wasm-target-runtime.c runtime/minyar_runtime.c $(WASM_HEADERS) build/wasm/.prepared
	"$(WASM_CC)" $(WASM_TARGET_FLAGS) $(WASM_SJLJ_FLAGS) -O2 -c "$<" -o "$@"

build/playground/.built: build/wasm/compiler.wasm build/wasm/runtime.o $(PLAYGROUND_SOURCES) $(PLAYGROUND_LIBRARY)
	python3 tools/build-playground.py

.PHONY: playground prepare-wasm prepare-playground-tests wasm check-wasm check-playground
prepare-wasm: build/wasm/.prepared
playground: build/playground/.built

build/playground-tests/.ready: playground/test-package.json playground/test-package-lock.json
	mkdir -p build/playground-tests
	cp playground/test-package.json build/playground-tests/package.json
	cp playground/test-package-lock.json build/playground-tests/package-lock.json
	npm ci --prefix build/playground-tests --ignore-scripts --no-audit --no-fund
	node build/playground-tests/node_modules/playwright/cli.js install --with-deps chromium
	touch "$@"

prepare-playground-tests: build/playground-tests/.ready

wasm: build/minyarc build/wasm/runtime.o
	@test -n "$(SOURCE)" -a -n "$(OUTPUT)" || { echo 'usage: make wasm SOURCE=program.min OUTPUT=program.wasm'; exit 2; }
	LLVM_CC="$(WASM_CC)" WASM_SYSROOT="$(WASM_SYSROOT)" node tools/wasm-target.mjs "$(SOURCE)" "$(OUTPUT)"

check-wasm: playground build/minyarc
	node tests/wasm.mjs
	node --no-warnings tests/wasm-target.mjs

check-playground: check-wasm build/playground-tests/.ready
	node tests/playground-browser.mjs
