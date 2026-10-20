# Tideboard

A small, real HTTP service written in Minyar: give a task a title, see it on
the board, and mark it done. The browser interface and JSON API share the same
bounded in-memory model. Task progress is a `choice`; model operations are
methods returning `Result` or `Maybe`; JSON strings use the library encoder.

From the repository root, with Minyar's pinned LLVM toolchain installed:

```sh
./minyar 'examples/gallery/tideboard/main.min' -o '/tmp/tideboard'
'/tmp/tideboard' 8080
```

Open `http://127.0.0.1:8080/`. The server always binds IPv4 loopback. Omit the
argument to use port 8080; use `0` to ask the operating system for a free port.
The first successful-start line reports the actual address:

```text
TIDEBOARD_READY http://127.0.0.1:8080
```

Stop with Control-C. Invalid arguments exit with status 2; listener and event
loop errors exit with status 1. No files are read or written by the service.

## Try the API

```sh
curl --fail 'http://127.0.0.1:8080/health'
curl --fail -H 'Content-Type: text/plain; charset=utf-8' \
  --data-binary 'Watch the tide' 'http://127.0.0.1:8080/tasks'
curl --fail 'http://127.0.0.1:8080/tasks'
curl --fail -X POST 'http://127.0.0.1:8080/tasks/1/complete'
```

- `GET /` serves the self-contained HTML interface.
- `GET /health` returns `{"ok":true,"service":"tideboard"}`.
- `GET /tasks` returns `{"tasks":[],"capacity":128}`, with tasks in creation
  order. A task has `id`, `title`, and `completed` fields.
- `POST /tasks` takes a plain UTF-8 text body and returns the created task
  with status 201. The Content-Type must be `text/plain` or
  `text/plain; charset=utf-8`. The raw body may contain at most 512 bytes.
  Surrounding ASCII spaces, tabs, CR and LF are trimmed. Empty titles,
  malformed UTF-8, remaining ASCII control characters and DEL return 400.
  Other media types return 415.
- `POST /tasks/<id>/complete` requires an empty body and returns the completed
  task with status 200. Repeating completion is safe. IDs are decimal 1–128
  without signs or leading zeros. Unknown tasks and paths return 404.
- An unsupported method on a known route returns 405 with an `Allow` header.
  Query strings are ignored; paths are case sensitive and not URL decoded.
  Application errors return JSON with an `error` string.

## Bounds and limitations

There are at most 128 tasks, including completed tasks. A full board returns
409; restarting clears it. There is no delete operation, authentication,
persistence, TLS, CORS support or collaboration protocol. Every local client
shares the same board. Use this as a local example, not a hosted task service.
The browser refreshes after its own actions; another client's changes appear
when the page is reloaded. The interface requires modern JavaScript.

The portable HTTP server caps connections at 32, headers at 8 KiB/32 fields,
bodies at 512 bytes, responses at 512 KiB and requests per connection at 100.
Header/body/application deadlines are 3 seconds; idle/write deadlines are 5
seconds. Transport-level rejection (for example a body above 512 bytes) is
handled by `httpserver` and may return its plain-text error body rather than
the application's JSON. Transfer-coded request bodies are unsupported and
return 501. Send an ordinary Content-Length body, as curl does above.

## Model tests

Run the four tests beside the model without starting a listener:

```sh
./minyar --test-mode 'examples/gallery/tideboard/model.min' \
  -o '/tmp/tideboard-model-tests'
'/tmp/tideboard-model-tests'
```

They check state transitions, repeatable completion, invalid titles, Unicode
and JSON escaping, the exact task bound, failed-write IDs and route parsing.
