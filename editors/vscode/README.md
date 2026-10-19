# Minyar for Visual Studio Code

This extension skeleton supplies TextMate highlighting and starts `minyar lsp`
over stdio. It uses the formatter and language server from the selected Minyar
toolchain. It has not been published to the Marketplace.

Run `npm ci --ignore-scripts` in this directory, open it in VS Code, then press F5 to open
the Extension Development Host. Open a `.min` file there. Run `npm test` to
check the grammar against the real TextMate and Oniguruma engines, plus client
restart/shutdown behavior. The root target is `make check-minyar-editor`.

If Minyar is not on PATH, set `minyar.executablePath` to its absolute path.
Add package source directories with `minyar.libraryPaths`. The normal editor
commands provide hover, definitions, completion, symbols and document formatting.
Choose **Minyar: Restart Language Server** after changing toolchains.

The TextMate grammar handles doc/block/line comments, methods, generics,
choices, aliases, interpolation with nested parentheses and strings, ordinary
and raw multiline text, Character literals and numeric bases. Contextual
`choice`, `type`, `test` and `parallel` receive declaration-aware highlighting.
The formatter keeps the language's canonical four-space style regardless of
the editor's tab-size setting. See [editor tooling](../../docs/editor.md) for
the server's current capabilities and limits.
