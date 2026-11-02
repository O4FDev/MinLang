# Connect protocol server and client (library/connect.min) over the shared rpc
# handler API (library/rpc.min). check-connect needs no network.
build/tooling/tests/connect-test.ll: tests/net-fixtures.min
.PHONY: check-connect
# Cases link the cycle runtime: open calls and their responders form traced cycles.
# gzip.min links the deflate native, so the launcher builds it at O0 and O2.
check-connect: build/minyarc build/minyar-runtime.o build/minyar-default-runtime.o build/testing/cycle-runtime.o build/tooling/tests/connect-test
	MINYAR_TEST_RUNTIME="./build/testing/cycle-runtime.o" MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/connect-test
	mkdir -p build/connect
	for mode in --debug --release; do \
		MINYAR_CLANG="$(LLVM_CC)" $(LIMITED) ./minyar $$mode tests/connect/gzip.min -o build/connect/gzip >/dev/null && \
		./build/connect/gzip > build/connect/gzip.out && cmp tests/connect/gzip.out build/connect/gzip.out || exit 1; \
	done

check check-portable: check-connect

# A stock connect-node client against a Minyar server over loopback HTTP/1.1.
# connect-node 2.3 needs Node 22 or later, so check-portable includes it only
# where that is installed; the npm packages are pinned by the lockfile.
build/connect-node/.ready: tests/interop/connect-node/package.json tests/interop/connect-node/package-lock.json
	mkdir -p build/connect-node
	cp tests/interop/connect-node/package.json tests/interop/connect-node/package-lock.json build/connect-node/
	npm ci --prefix build/connect-node --ignore-scripts --no-audit --no-fund
	touch "$@"

.PHONY: check-connect-node
check-connect-node: build/minyarc build/minyar-default-runtime.o build/connect-node/.ready
	MINYAR_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/connect-node.py "$(CURDIR)/minyar" "$(CURDIR)/build/connect-node"

ifeq ($(shell node -e 'process.exit(Number(process.versions.node.split(".")[0]) < 22 ? 1 : 0)' 2>/dev/null && echo yes),yes)
check check-portable: check-connect-node
endif
