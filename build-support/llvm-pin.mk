.PHONY: check-llvm-pin

# The pinned LLVM release lives in one place, the llvm_* lines of tools/toolchain.sh; this fails when any copy
# elsewhere (CI workflows, docs, scripts, test fixtures) names another version or digest (tools/llvm-pin.py).
check-llvm-pin: tools/llvm-pin.py tools/toolchain.sh
	python3 tools/llvm-pin.py

check check-portable: check-llvm-pin
