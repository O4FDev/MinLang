# Minyar

A small, statically typed language that compiles to native code through LLVM.

## Get started

Requires Clang, a C compiler, Make, Python 3, zsh, and system C development
headers. The compiler and runtime build on first use.

```sh
./minyar examples/hello.min -o hello
./hello
```

Add `--release` for optimized builds:

```sh
./minyar --release examples/hello.min -o hello
```

Run the tests with `make check`, or `make check-smoke` for a quick check.

## Documentation

- [Language guide](docs/language.md)
- [Modules](docs/modules.md) and [incremental builds](docs/incremental-builds.md)
- [Examples](examples/)
- [Runtime ownership](docs/runtime-memory.md) and [runtime profiles](docs/bounded-runtime-contract.md)
- [Performance testing](docs/performance.md)
- [Linux testing](experiments/linux/README.md)

## A note from the developer 

Hey, Luke here - I made this language as a small joke to a friend as a poke for using PHP and Laravel, I'm trying to get it into an acceptable state for them and me to use in a few projects for funsies and it's also helping me to do some learning and security research, also to push the limits of what AI agents are capable of doing. I've got some really super fun things planned so feel free to drop an issue if you have any ideas or feedback! 