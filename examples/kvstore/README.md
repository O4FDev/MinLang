# kvstore: a crash-safe key-value store, tested by simulation

A write-ahead-logged key-value store in about 200 lines. Its storage code is
written once against `disk.Disk`, so the same functions run:

- on the machine's file system (`disk.host()`) in `src/main.min` and in the
  SIGKILL test `tests/kill.min`, and
- on a simulated disk (`disk.simulated(world)`) in `sim/crash.min`, where every
  run is a seeded universe that loses unsynced writes, tears unsynced sectors
  and crashes, then checks that recovery kept every acknowledged write.

```sh
minyar test                       # replay unit tests and a real SIGKILL crash test
minyar sim crash --seeds 10000    # ten thousand simulated power losses
minyar run -- ./data put harbour light
minyar run -- ./data list
```

The log record is `[length: UInt32][CRC-32C: UInt32][payload]`. A write is
acknowledged after its record is synced; recovery replays complete records
and cuts the log at the first torn or damaged one. Compaction writes a
snapshot, syncs it, renames it into place and syncs the directory before
emptying the log.

Try deleting the line `if created { try storage.syncDirectory(directory) }` in
`src/store.min`: `minyar sim crash` then reports a seed in which a crash loses
the newly created log and every write in it, prints the decisions that
reproduce it, and saves them for `minyar sim crash --replay FILE`. The same bug
passes the SIGKILL test, because killing a process does not lose the page cache.
