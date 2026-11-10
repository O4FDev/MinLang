# bytecode-vm: a stack machine and its assembler

Four small modules: `opcodes.min` names the instruction set, `asm.min` is a
two-pass assembler (labels are resolved after the first pass), `machine.min`
interprets the encoded `Bytes`, and `main.min` reads a `.asm` file.

```sh
minyar run -- fib.asm     # prints the first ten Fibonacci numbers
minyar test
```

Faults inside the program (stack underflow, a bad jump, division by zero, an
exhausted step budget) are `Err` values the host reports; only a bug in the VM
itself stops the process.
