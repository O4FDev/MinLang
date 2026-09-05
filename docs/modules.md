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

Only local file imports are supported. Names that do not begin with `./` or
`../` are reserved for packages and currently produce an error.

## Scalability and rebuilds

Ordinary builds compile the complete reachable source graph. The opt-in
[`--incremental` build mode](incremental-builds.md) reuses checked interfaces and
LLVM code, skipping unchanged dependency bodies.
