# Documentation beside the code

Write `///` immediately above a declaration to explain what it offers. Keep
consecutive lines together; an empty `///` line begins a new paragraph. A blank
source line separates the comment from the declaration. Ordinary comments and
text inside strings do not become documentation.

```minyar
/// A named light beside the water.
public record Lantern {
    /// The name someone will look for.
    name: Text
    /// How many windows it can brighten.
    light: Integer
}

/// Share the light equally; the original lantern stays bright.
public function Lantern.share(friends: Integer): Integer {
    return self.light / friends
}
```

Comments can describe functions, methods, records, choices, concrete type
aliases, constants and globals. Fields and choice cases can carry their own
comments. Private declarations and private fields stay out of the public
reference. Original signatures retain generic parameters and constraints.

Run `minyar doc` inside a project. It resolves the project and dependencies,
checks the entry module, verifies the examples and writes `target/doc/index.html`
and `target/doc/api.json`. Open the HTML directly; fonts, styles, highlighting
and search work offline. Search matches names, signatures, members and prose.
Use `/` to focus search and Escape to clear it. `--release`, `--locked` and
`--offline` follow the project CLI's usual meaning.

A source directory without a manifest can use `minyar doc --path library`.
This reads `.min` files recursively and verifies their examples with that
directory on the import path. Output goes to the current directory's
`target/doc`. This route extracts source metadata; it does not type-check every
platform-specific module or instantiate every generic function.

## Examples that stay true

Every fenced `minyar` example is a standalone program. The documented module
is automatically imported as `api`; other modules can be imported normally.
A following `output` fence states exact standard output, including its final
newline. Without an output fence, the program must print nothing.

````text
/// Keep the first thing, or offer something when the list is empty.
///
/// ```minyar
/// print(api.firstOr(["moon", "sea"], "silence"))
/// ```
/// ```output
/// moon
/// ```
public function firstOr<Item>(values: List<Item>, fallback: Item): Item {
    if values.length == 0 { return fallback }
    return values[0]
}
````

Examples may contain named `test` blocks and `expect` calls. These blocks run
in an additional test build, so a passing ordinary program cannot hide a
failed expectation. Each example runs in its own temporary working directory;
relative file writes stay there. Every program must finish successfully and
write no diagnostics. A failed compilation, expectation or output comparison
stops documentation publication and preserves the previous site.

`minyar test` also runs documentation examples from public declarations and
members across the resolved project and dependencies. Its substring filter
matches a module path or an example's declaration name. These results share
the summary with module tests and `tests/*.min` programs.

The small prose format supports paragraphs, backtick code, headings, lists and
fenced code. Other code fences are displayed without execution. Raw HTML is
escaped. See [the living tests gallery](../examples/gallery/living-tests.min)
for code, tests and documentation in one place.

## Source metadata

`minyar --doc-json FILE.min` prints version 1 JSON. Each public declaration has
`name`, `kind`, `signature`, `documentation`, a `span` with file/line/column,
and `members`. Named test spans are recorded separately in `tests`. This mode
always reloads original source and emits no program or runtime code. It is a
syntax metadata interface; use `minyar check` to check a project's types.

`make check-library-documentation` rebuilds the standard-library and gallery
references in both profiles and verifies all their examples. To browse the
library locally, run `minyar doc --path library` and open `target/doc/index.html`.
