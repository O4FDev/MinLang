# Lantern Trail

A small terminal rescue puzzle written in Minyar. Carry two lanterns through a
stone maze and light the rescue gate before your energy runs out. The engine
uses choices for commands, directions and game phases, record methods for state
transitions, and Text interpolation for the transcript.

```text
#######
#@..L.#
#.#.#.#
#L..G.#
#######
```

`@` marks you, `#` a wall, `L` an uncollected lantern, and `G` the rescue gate.
Start with ten energy. Each legal step costs one; collecting a lantern for the
first time restores two. Both lanterns must reach the gate together. Collecting
a lantern or opening the gate on your last energy succeeds. Otherwise zero
energy ends the attempt. Walls cost nothing. The map is fixed, so you can plan
a route with `look` and improve it with `restart`.

Enter one lowercase command per line:

- `north`, `south`, `east`, `west`, or `n`, `s`, `e`, `w`: move one square.
- `look`: show the maze and current energy.
- `help`: show the controls.
- `restart`: begin a fresh attempt, including after a win or loss.
- `quit`: leave the game.

Empty and unknown commands cost nothing. Leading/trailing spaces and tabs are
accepted. Commands are limited to 128 ASCII bytes; longer lines and non-ASCII
input are rejected as unknown commands, then the next line is read normally.
Terminal input ends cleanly at EOF, including an unterminated final command.

From the repository root, with the repository's documented LLVM toolchain:

```sh
./minyar --debug \
  --native-source 'trailinput=examples/gallery/lantern-trail/input.c' \
  'examples/gallery/lantern-trail/main.min' -o 'build/lantern-trail'
'./build/lantern-trail'
'./build/lantern-trail' --help
```

The low-level launcher resolves the relative engine/input modules from
`main.min` and the standard library automatically. The library currently has
no stdin line reader: `input.c` supplies only scalar `getchar` and prompt
flushing. Line bounds, command parsing, game rules and rendering are Minyar.
No external package, terminal library, graphics display or network is needed.
Omit `--debug` for the launcher's default O2 build, or use `--release` for LTO.

Replay files contain the same commands and never read stdin. These fixtures
have independently written expected output. The winning route takes eleven
steps and finishes with three energy; the losing route spends all ten energy
without collecting a lantern. The controls fixture checks walls, malformed
commands, help, look, restart, and ignoring commands after quit.

```sh
'./build/lantern-trail' --replay 'examples/gallery/lantern-trail/win.replay' > 'build/trail-win.stdout'
diff -u 'examples/gallery/lantern-trail/win.stdout' 'build/trail-win.stdout'
'./build/lantern-trail' --replay 'examples/gallery/lantern-trail/lose.replay' > 'build/trail-lose.stdout'
# The losing command above returns 1.
diff -u 'examples/gallery/lantern-trail/lose.stdout' 'build/trail-lose.stdout'
'./build/lantern-trail' --replay 'examples/gallery/lantern-trail/controls.replay' > 'build/trail-controls.stdout'
diff -u 'examples/gallery/lantern-trail/controls.stdout' 'build/trail-controls.stdout'
```

Replay files may use LF or CRLF and need no final newline. A replay is limited
to 65536 bytes. Exit statuses are 0 for rescue, help or quit, 1 for exhaustion,
and 2 for invalid arguments, read failures, or a replay ending while the game
is still in progress. Interactive EOF exits 0 unless the current attempt is
exhausted. After rescue or exhaustion, moves leave the state unchanged;
`restart`, `look`, `help` and `quit` still work.

The deterministic engine's module tests exercise legal routes, locked gates,
single lantern collection, wall/malformed input, state preservation, restart,
quit, exhaustion and last-energy rescue:

```sh
./minyar --debug --test-mode 'examples/gallery/lantern-trail/engine.min' \
  -o 'build/lantern-trail-engine-tests'
'./build/lantern-trail-engine-tests'
```
