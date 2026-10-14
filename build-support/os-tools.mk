OS_QEMU_TOOLS = build/tooling/os/tools/qemu-drive build/tooling/os/tools/test-qemu-drive

$(OS_QEMU_TOOLS): TOOL_NATIVE = runtime/native/net.c
$(OS_QEMU_TOOLS): runtime/native/net.c $(wildcard runtime/native/net_*.h)
$(OS_QEMU_TOOLS:=.ll): os/tools/qmp.min
