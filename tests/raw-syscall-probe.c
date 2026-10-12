/* No libc includes: usable with bare cross targets and -ffreestanding. */
#include "../runtime/minyar_machine.h"
long long probe(void) { return minyar_machine_syscall(39, 1, 2, 3, 4, 5, 6); }
