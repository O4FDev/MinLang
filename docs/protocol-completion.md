# Protocol completion

The `protocol` module provides a completion witness for an application's
commit, rollback or close operation. Every token must be completed or transferred
exactly once on each normal return path. The compiler checks responsibility
separately from reference-counted memory lifetime.

```minyar
use "protocol" as protocol
function commit(done: protocol.Completion) {
    print("committed")
    protocol.complete(done)
}
function rollback(done: protocol.Completion) {
    print("rolled back")
    protocol.complete(done)
}
function finish(success: Boolean) {
    let done = protocol.begin()
    if success { commit(done) } else { rollback(done) }
}
finish(true)
```

`begin` creates one opaque token. Binding it to another local, assigning it or
passing it to an ordinary helper moves the responsibility; the old binding
becomes unavailable. Returning a token transfers responsibility to the caller.
`complete` consumes it. A helper must itself complete or transfer its argument;
its name and return type cannot discharge the obligation.

Place the application's successful commit, rollback or close action before
`complete` in a consuming helper. The witness does not implement transactions or
prove that an arbitrary application action succeeded. A process stop, native
failure or fatal cancellation does not promise automatic rollback.

The initial checker supports straight-line code, lexical scopes, if/else and
normal returns. Continuing branches must agree about responsibility. A live token
cannot cross a loop, and token operations inside loops are rejected. Ordinary
scalar loops before acquisition or after completion remain available.

Tokens cannot be stored in records, containers, choices, Results, globals or
callback signatures, captured in closures, compared automatically, or passed
through an unclassified native boundary. Calls accept at most one token argument,
as a bare local name. Bind returned tokens before passing them onward. Recursive
consuming helper graphs, token operations reachable from thread/parallel/callback
execution, and exceptional `try`/recovery edges are rejected in this first subset.
Aliases and generic specializations preserve these rules. Imported helpers use
whole-source checking even when module caching is requested.

`Completion` uses the existing opaque native-record marker form. `begin` allocates
one empty managed record; normal reference ownership still manages that record.
The source proof adds no runtime protocol-state table, flag or external provider.
This is a deliberately restricted completion witness, not a general linear type
system or a cancellation-safety guarantee.

The [transaction gallery](../examples/gallery/protocol-completion.min) connects
the witness to a concrete balance update and rollback decision.

Protocol ownership errors use `E0801`; `minyar explain E0801` describes the
rules and shows a complete commit-or-rollback example.
