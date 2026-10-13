# Linux correctness validation

Use `build/tooling/scripts/check-linux` on Linux aarch64 or x86_64 to build from source
and run compiler, runtime, and sanitizer checks. It excludes performance tests.

## Run on a Linux host

Install Clang, its sanitizer runtime, lld, make, Python 3, zsh and the system C/C++
development headers. The Dockerfile below records the Ubuntu 24.04 package set
used for these checks. From the project root:

```sh
make build/tooling/scripts/check-linux && ./build/tooling/scripts/check-linux --source "$PWD" --output-dir "$PWD/build/linux-validation/native"
```

The runner requires an aarch64 or x86_64 Linux host, selects lld for linking, and
builds its compiler/runtime artifacts in the checkout's own `build/` directory.
Use `--clang` and `--cxx` to select alternative compiler paths,
or `--timeout 3600` to increase the timeout for each top-level check.
`--dry-run` prints the planned checks without building anything.

## Run in a container

Build the image and keep its ID alongside the results:

```sh
mkdir -p build/linux-validation/arm64
docker build --platform linux/arm64 -f experiments/linux/Dockerfile -t minyar-linux-arm64 .
docker image inspect minyar-linux-arm64 --format '{{.Id}}' > build/linux-validation/arm64/image-id.txt
docker run --rm --platform linux/arm64 -v "$PWD:/work" -w /work minyar-linux-arm64 \
  sh -c 'make build/tooling/scripts/check-linux && ./build/tooling/scripts/check-linux --source /work --output-dir /work/build/linux-validation/arm64'
```

For x86_64, build a separate image using `--platform linux/amd64`, tag it
`minyar-linux-amd64`, and use a separate output directory such as
`build/linux-validation/amd64`. Use the same platform flag when running it.
Docker needs an appropriate native host or configured architecture emulation.
Retain the image ID and Clang version when comparing runs.

## Resume and inspect evidence

Each execution prints its retained `minyar-tests-linux-...` directory. It contains
`results.json`, per-check logs with CPU and peak RSS, the scratch of failed checks
and the CI artifacts under `source/build`. The native runner has no resume; rerun
a corrected check inside the same image with `--only`:

```sh
docker run --rm --platform linux/arm64 -v "$PWD:/work" -w /work minyar-linux-arm64 \
  sh -c 'make build/tooling/scripts/check-linux && ./build/tooling/scripts/check-linux --source /work --only check-maps'
```

On a native Linux host, run the same command directly. Measured check
durations are kept in `build/tooling/check-durations` and order the next run.

## Optional runtime leak checks

The `leaks` group replays normal-exit runtime fixtures with LeakSanitizer
enabled once the checks it replays have passed:

```sh
./build/tooling/scripts/check-linux --group leaks --output-dir "$PWD/build/linux-validation/native"
```

For containers, run that command inside the matching image as above. A
deliberately leaked allocation must first trigger the detector; then the
eager-runtime and completed system-allocator fixtures must exit without leaks.
Compiler processes are excluded because their arena intentionally lasts until
process exit. The replay's log is retained with the run's other check logs.
