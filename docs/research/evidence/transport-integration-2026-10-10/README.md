# Remote Linux transport integration

These are completed checks on the dedicated Linux measurement host, not local
laptop runs. `outcomes.tar.gz` contains the original suite reports and logs for
native O0, native O2, and ASan/UBSan with leak detection. All nineteen outcomes
in each configuration exited zero. `manifest.json` records the exact source,
compiler binary, and toolchain hashes; the source was transport commit
`3406074` plus the runtime parent's Linux snapshot repair.

The suite exercises the published QUIC v1/v2 crypto packets, every-byte tamper
and truncation controls, independent packet encoders, bounded CID/timer
dispatch, mutual TLS certificate adversaries, loss/reordering, key updates,
client path migration, resumption, opt-in replay-safe early data, fallback,
congestion/pacing, and real certificate expiry between handshakes. The
archive also retains the actual duplicate-symbol failure that preceded the
shared updater/TLS primitive-object repair.

These results establish Linux correctness for this snapshot. Windows and
macOS native jobs are separate CI gates. This is not a security audit, an
instruction-count result, a completed endurance measurement, or proof of all
remaining RFC lifecycle operations. See `docs/quic.md` and
`docs/quic-evidence.json` for independent peer results and explicit gaps.
