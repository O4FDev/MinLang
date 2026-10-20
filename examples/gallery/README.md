# Three small, complete programs

These programs turn the language features into tools you can use. Each is
self-contained in this checkout, with runnable commands and limits in its
README. None needs a package registry, account or downloaded asset.

- [Daybook](daybook/README.md) adds up time from UTF-8 tab-separated files and
  emits a sorted table or exact-integer JSON. It combines choices, Map, record
  methods, contextual Result propagation and Text interpolation.
- [Tideboard](tideboard/README.md) is a loopback HTTP task board with a browser
  interface and a JSON API. Choices describe task progress, methods own state
  changes, and Results reject invalid input without stopping the service.
- [Lantern Trail](lantern-trail/README.md) is a playable terminal rescue puzzle.
  Choices describe commands and game phases; record methods return fresh game
  states. Fixed replays make wins, losses and controls reproducible.

From the repository root, `make check-showcase` compiles all three at O0 and O2,
checks Daybook against independent totals, sends real HTTP requests to
Tideboard, and compares game replays byte for byte. Focused targets are
`check-showcase-daybook`, `check-showcase-tideboard` and
`check-showcase-lantern-trail`. The check keeps command evidence under
`build/showcase`. The application modules also keep tests beside their code.

The surrounding gallery files explore individual features, from
[choices](choice.min) and [generics](generics.min) to
[parallel image generation](parallel-image.min) and
[contextual errors](results.min).
