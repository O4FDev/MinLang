# Minyar for Cursor and Visual Studio Code

This extension supplies TextMate highlighting and starts `minyar lsp`
over stdio. It uses the formatter and language server from the selected Minyar
toolchain. It has not been published to the Marketplace.

To install locally, run these commands from this directory:

```sh
npm ci --ignore-scripts
npx --yes @vscode/vsce package --baseContentUrl 'https://github.com/O4FDev/MinLang/blob/v2/editors/vscode/'
cursor --install-extension './minyar-0.1.1.vsix' --force
```

For VS Code, replace `cursor` with `code`. You can also choose **Extensions:
Install from VSIX...** in the Command Palette and select the generated file.
Open a `.min` file; its language mode should read **Minyar**. If an existing
window does not pick up the extension, run **Developer: Reload Window**.
Suggestions appear while typing and after `.`; use **Trigger Suggest** to open
the completion list manually. Highlighting works without the language server.

If Minyar is not on PATH, set `minyar.executablePath` to its absolute path.
Add package source directories with `minyar.libraryPaths`. The normal editor
commands provide hover, definitions, completion, symbols and document formatting.
Choose **Minyar: Restart Language Server** after changing toolchains.
Creating, changing or deleting `Minyar.toml` or `Minyar.lock` automatically
restarts the server so packages added with `minyar add` become available to
diagnostics, completion and navigation without reloading the editor.
If the server cannot start in a GUI-launched editor, set `minyar.executablePath`
in user settings to the full path printed by `command -v minyar`.

For extension development, open this directory in VS Code and press F5 to open
the Extension Development Host. Run `npm test` to check the grammar against
the real TextMate and Oniguruma engines, plus client restart/shutdown behavior.
The root target is `make check-minyar-editor`.

The TextMate grammar handles doc/block/line comments, methods, generics,
choices, aliases, interpolation with nested parentheses and strings, ordinary
and raw multiline text, Character literals and numeric bases. Contextual
`choice`, `type`, `test` and `parallel` receive declaration-aware highlighting.
The formatter keeps the language's canonical four-space style regardless of
the editor's tab-size setting. See [editor tooling](../../docs/editor.md) for
the server's current capabilities and limits.
