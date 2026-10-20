# C counterparts for the osdev seeded-mistake study

Plain C11 drivers written the way a Linux/SerenityOS author would write them,
used to compare where seeded mistakes are caught (compile, host test, QEMU only,
undetected) against the Minyar drivers.

| File | Purpose |
| --- | --- |
| `virtio_entropy.h` / `virtio_entropy.c` | One-descriptor split-virtqueue entropy read; mirrors `readOneEntropyByte` in `os/shared/virtio/virtio.min`. Seed markers: `SEED:phys`, `SEED:fence-publish`, `SEED:poll`, `SEED:fence-acquire`, `SEED:read`, `SEED:free`. |
| `model.h` / `model.c` | Deterministic host device model and platform hooks (DMA alloc/free with live tracking, virt->phys with `PHYS_OFFSET`, `platform_relax` driving delayed completion, fault recording). |
| `test_entropy.c` | Host test: counts 1/16/64/4096 x delays 0/3/50, 16-bit index wrap, timeout, bad lengths, over- and short-reported used lengths. Prints `C ENTROPY HOST PASS`. |
| `rtc_irq.c` | Freestanding x86 RTC interrupt handler with `SEED:alloc`, `SEED:lock`, `SEED:print`, `SEED:float`, `SEED:loop` marker lines. |

## Build

Host test (run each; all must print `C ENTROPY HOST PASS` and exit 0):

    clang -std=c11 -Wall -Wextra -O0 model.c virtio_entropy.c test_entropy.c -o test_entropy_O0
    clang -std=c11 -Wall -Wextra -O2 model.c virtio_entropy.c test_entropy.c -o test_entropy_O2
    clang -std=c11 -Wall -Wextra -O0 -g -fsanitize=address,undefined -fno-sanitize-recover=undefined \
          model.c virtio_entropy.c test_entropy.c -o test_entropy_asan
    ASAN_OPTIONS=detect_leaks=1 ./test_entropy_asan

Interrupt handler (object only, nothing links it):

    clang -std=c11 -Wall -Wextra --target=x86_64-unknown-none-elf -ffreestanding \
          -mgeneral-regs-only -mno-red-zone -O2 -c rtc_irq.c -o rtc_irq.o

## Model limits

- The model runs single-threaded inside `platform_relax()`, so removing either
  fence (`SEED:fence-publish`, `SEED:fence-acquire`) is not observable on the host.
- `PHYS_OFFSET` makes a virtual pointer in a descriptor miss every live buffer.
  Minyar-OS on QEMU identity-maps, so the same `SEED:phys` mistake is invisible there.
- On timeout the driver keeps the buffer (the device may still write it); the
  test lets the late completion land, resets the model device, then frees it.
