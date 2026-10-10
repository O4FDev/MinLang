# Modules

## Local modules

An entry file gives each imported module an explicit local name:

```minyar
use "./geometry.min" as geometry

let origin = geometry.Point { x: 0, y: 0 }
print(geometry.distance(origin))
```

The imported file chooses its interface with `public`:

```minyar
public record Point {
    x: Integer
    y: Integer
}

public function distance(point: Point): Integer {
    return point.x + point.y
}

function implementationDetail(): Integer {
    return 42
}
```

Paths beginning with `./` or `../` are local and resolve relative to the file
that contains the `use`, never relative to whichever terminal launched the
compiler. Forward slashes are the canonical spelling on every platform;
backslashes in local paths are accepted for Windows interoperability. `.` and
`..` components are normalized before a module is identified, so the same file
is compiled once even when reached through different paths.

Imported modules contain declarations only. Executable top-level statements
belong to the entry file, preventing imports from causing hidden runtime side
effects. Cycles are rejected before type checking. Functions and records with
the same private source name may safely exist in different modules because the
declarations belong to separate module namespaces.

## Packages

Names that do not begin with `./` or `../` are standard library packages,
bundled with the compiler in [`library/`](../library/):

```minyar
use "graphics" as graphics

graphics.openWindow(1280, 720, "Hello")
while graphics.nextFrame() {
    graphics.clear(0.5, 0.7, 1.0)
}
```

`json` parses and writes JSON, `net` opens TCP connections and `http` makes
HTTP/1.1 requests over them, for `https://` URLs through `tls`, a TLS 1.3
client built on `crypto` (SHA-256, HMAC, HKDF, ChaCha20-Poly1305, X25519). The
TLS client encrypts and verifies the handshake but does not validate
certificates. [`examples/atacama`](../examples/atacama/main.min) and
[`examples/fetch`](../examples/fetch/main.min) use them. `machine` gives [freestanding programs](freestanding.md) direct
access to the hardware, and `device` gives them typed, checked registers, ports
and DMA memory on top of it.
`graphics` provides a window, keyboard and mouse input, textured 3D meshes
with fog and lighting, lines, a 2D overlay with text, and screenshots; its
module documents each function. The [`macos`](macos.md) package provides native
AppKit desktop applications and needs no third-party library. Some library
functions are implemented in C or Objective-C: their body is, for example,
`native "graphics"` or `native "macos"`, and `./minyar` builds and links the
needed native code automatically. Packages from other sources are not yet supported, and
`--incremental` builds do not resolve packages yet.

The compiler finds packages through `--library DIRECTORY`, which may be given
more than once; each directory is searched in order and the first with the
package wins. A build for another processor or platform can so replace one
package without copying the rest: Minyar OS's Arm build lists
`library/arch/arm64`, whose `machine.min` holds the Arm intrinsics, before
`library`, and its own `os/arch/arm64` before both for its `arch` package.

## Scalability and rebuilds

Ordinary builds compile the complete reachable source graph. The opt-in
[`--incremental` build mode](incremental-builds.md) reuses checked interfaces and
LLVM code, skipping unchanged dependency bodies.
