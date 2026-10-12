# WS6 QUIC/TLS interop and soak

Owner RELEASE on 2026-10-12 admits development/testing from bf9c0e9 in dedicated WS6 Boat labs; only the integrator merges/pushes v2. No new paid spend.

PATH_RESPONSE fixes are committed on ws6/quiche-rebinding-20261012: 0d19068 pads response datagrams; 180d6f9 omits responses from loss/PTO retries. Qualified code/test pin: 68b5166e8b1d6c54709c6f9cdcf4da531a22a9a3. Product changes are two executable lines plus one RFC comment.

Sixteen new authenticated cases and the affected response-routes control extend the maintained migration fixture/driver. Exact old-library RED and repaired GREEN passed natively and with ASan/UBSan/LSan at O0/O2 on own Boat bx_3uf7zdcw. All 68 final GREEN case executions exit0 with empty stderr. Pacing/congestion/anti-amplification and reliable STREAM/MAX_DATA/NEW/RETIRE/path-challenge retry controls pass. Exact source/link/raw diagnostic evidence and strict process absence (including zombies) are retained in /home/user/ws6-lab; locally verified export and report are at /Users/luke/overnight/runs/minyar-ws6-20261012/protocol-fixes.md.

Original index72 verdict/panic attribution, official runner/matrix and soak execution remain parent-owned. Prior adaptive CID qualification and thresholds are unchanged. Parent obtains independent review before an integrator merge request. No merge or push occurred.
