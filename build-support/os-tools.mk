OS_QEMU_TOOLS = build/tooling/os/tools/qemu-drive build/tooling/os/tools/test-qemu-drive

$(OS_QEMU_TOOLS): TOOL_NATIVE = runtime/native/net.c
$(OS_QEMU_TOOLS): runtime/native/net.c $(wildcard runtime/native/net_*.h)
$(OS_QEMU_TOOLS:=.ll): os/tools/qmp.min

build/tooling/tests/virtio-used-ring.ll: os/shared/virtio/used.min

.PHONY: check-virtio-used-ring
check-virtio-used-ring: build/tooling/tests/virtio-used-ring
	$(LIMITED) ./build/tooling/tests/virtio-used-ring

check check-portable: check-virtio-used-ring
