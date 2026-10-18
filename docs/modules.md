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
belong to the entry file. Explicit runtime
[`global` initializers](language.md#constants) run before the entry point,
including in imported modules, and can perform I/O or fail. Imports therefore
can have initialization side effects when they declare globals. Literal
module constants cannot execute initialization code. Import cycles are rejected before type
checking. Functions and records with
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
TLS client validates certificate chains against OS roots, checks names and
validity, and verifies the server's handshake signature. It supports custom
trust anchors and mutual authentication; see the TLS API.
[`examples/atacama`](../examples/atacama/main.min) and
[`examples/fetch`](../examples/fetch/main.min) use them. `machine` gives freestanding programs direct
access to the hardware, and `device` gives them typed, checked registers, ports
and DMA memory on top of it.
`graphics` provides a window, keyboard and mouse input, textured 3D meshes
(triangles, or quads with `updateQuads`) with fog and lighting, lines, a 2D overlay with text, and screenshots; its
module documents each function. The `macos` package provides native
AppKit desktop applications and needs no third-party library. On macOS,
`./minyar` searches [`library/platform/macos`](../library/platform/macos/http.min)
before `library`, so `use "http"` there gets an `http` with the same
`Response`, `get`, `post` and `request` that goes through NSURLSession: it
validates certificates, follows redirects, decodes chunked bodies, and can
also stream (`start`, `read`, `finished`). The portable one does none of those.
`./minyar --library library` picks the portable one on macOS too.
[`json`](../library/json.min) parses and quotes JSON in Minyar itself. Some library functions are implemented
in C or Objective-C: their body is, for example, `native "graphics"` or
`native "macos"`, and `./minyar` builds and links the needed native code
automatically. Packages from other sources are not yet supported.

The compiler finds packages through `--library DIRECTORY`, which may be given
more than once (`./minyar` accepts it too, ahead of its standard directories); each directory is searched in order and the first with the
package wins. A build for another processor or platform can so replace one
package without copying the rest: Minyar OS's Arm build lists
`library/arch/arm64`, whose `machine.min` holds the Arm intrinsics, before
`library`, and its own `os/arch/arm64` before both for its `arch` package.

## Core and standard modules

Text methods (including trimming and splitting), collection operations, byte
encoding, basic numeric helpers, printing and checked termination are core
conveniences. File and process services, secure randomness and advanced Float
mathematics have explicit module APIs:

```minyar
use "io" as io
use "process" as process
use "random" as random
use "math" as math

let path = process.argument(0)
let source = io.readTextFile(path)
io.writeTextFile(path + ".copy", source)
let nonce = random.bytes(32)
print(math.sqrt(81.0))
```

`io.writeTextParts(path, pieces)` streams a `List<Text>`; use
`io.readBytesFile` and `io.writeBytesFile` for packed Bytes.
`process.processId`, `process.sleepNanoseconds`, and `io.sync` are pointer-free
OS operations safe in ordinary functions and managed threads; they replace
`threadProcessId`, `threadSleepNanoseconds`, and `threadFsync`. File failures stop
with a diagnostic. The `files` package provides recoverable descriptor APIs
and explicit durability. These APIs no longer reserve unqualified function
names: a module may declare its own `sin`, `argument`, or `readTextFile`.

The `pixels` module contains parallel software blending and coverage algorithms.
It uses the `machine` module's memory operations; rendering policy is ordinary
library code. Thread-domain, ownership and channel checks remain compiler
responsibilities. Native-backed module functions use the shared runtime ABI. Streaming text
parts is ordinary library iteration over private buffered-writer operations.

## Scalability and rebuilds

Ordinary builds compile the complete reachable source graph. The opt-in
[`--incremental` build mode](incremental-builds.md) reuses checked interfaces and
LLVM code, skipping unchanged dependency bodies.
