# First light

This example consumes the external `paint` package through its final GitHub
path. The source, tests, TrueType font and three larger artworks live in their
own repository at `/Users/luke/Projects/minyar-paint`, tagged `v0.1.0`.
That repository has not been published. Its `scripts/publish.sh` is prepared for
Luke to run later; no remote has been configured.

After publication:

```sh
minyar add github.com/O4FDev/paint@v0.1.0
minyar run --locked
minyar run --locked --offline --release
```

Before publication, provide a private bare mirror without changing global Git
configuration:

```sh
mkdir -p /tmp/minyar-mirror/github.com/O4FDev
git clone --bare /Users/luke/Projects/minyar-paint \
  /tmp/minyar-mirror/github.com/O4FDev/paint.git
MINYAR_GIT_MIRROR=/tmp/minyar-mirror minyar add github.com/O4FDev/paint@v0.1.0
minyar run --locked --offline
```

The program writes `first-light.png` and `first-light.svg`, then prints:

```text
first light · paint v0.1.0 · 640 × 480
```

From the Minyar checkout, `make check-paint-package MINYAR_PAINT_SOURCE=/path/to/minyar-paint`
checks this real external package, deletes the mirror before rendering, and
verifies fresh PNG/SVG output at debug and release optimization. This explicit
integration target requires the separate repository and is not part of CI's
self-contained package fixtures.
