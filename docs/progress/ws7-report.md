# WS7 interim release report

Updated 2026-10-12. The full release objective is incomplete. No WS7 change is
confirmed merged into `v2`; only the integrator merges and pushes. All paid spend
is $0. Owned Windows sender/receiver and Linux CI boxes are stopped.

| Requirement | Established evidence | Still required |
| --- | --- | --- |
| Windows sanitizer idle CPU <= .02, original one-second system-k1024/n2048 | Exact immutable bf9 source retained; approved sanitizer-path prerequisite merged only onto own branch e563c578 | Resource/source admission, real product RED, narrow measured fix, original gates green |
| Full Windows portable/native suite | No product suite ran in WS7's guest | All portable and separately required native gates on the qualified v2 source |
| CI correctness and speed | Stamp-only 0150ba5 independently reviewed and queued; d8dc0c2 CI stack passes 22 focused Boat tests plus lint; fresh R3 pending | Successful matched full runs, actual before/after wall time, completed green v2 Actions |
| Test-certificate signed pipeline | 21fd4e7 code R2 approved; 23 mocked signing, 12 shipping and five public Ed25519 publisher tests pass on Boat; catalogue and workflow lint pass | Real macOS CI and admitted Windows OS signing, updater roundtrip, mutation refusals and cleanup |
| Owner credentials checklist | [Exact signing checklist](../release-signing.md) written with owner-run provisioning and key/policy locations | Owner provides production identities/keys when production signing is authorized |
| 20,000-real-device plan | [Costed physical-device plan](../device-test-20000.md), independently approved; focused b55b235 queued | Loans/fleet, tested WS6 adapter, synthetic admission repair and separate execution/procurement admission |

The unchanged bf9 Linux baseline failed at toolchain-stamp after **229.593s**
(runner **224.694s**). There is no qualifying after wall time. Historical Actions
3,071s uses 111 targets rather than the frozen 135 and cannot serve as the speed
baseline. Both future timing sides need the same reviewed stamp prerequisite
and complete source/tool/host/gate bindings, without replayed successful rows.

Windows infrastructure failures remain separate NONPASS records. The original
host guardian sampled 77.5% CPU against its unchanged 75% ceiling during source
binding; no receipt or NT Job closure was established. The later relay-only
verifier read returned but failed a metadata assertion before saving SHA,
ending after 521.94s with zero resource excursions. Its actual 10,800-second
configuration differs from later 1,200-second prose. No byte relay or product
test occurred. Owned process absence and normal snapshot-preserving stops are
recorded; hydration metadata is not proof of restored input bytes.

Evidence is under `~/overnight/runs/minyar-unify-20261012/ws7-windows-idle/`
(`closeout.json`, `relay-closeout.json`, public evidence) and
`/tmp/minyar-ws7-ci-evidence/` (source-bound Boat receipts). New source-admission
preparation uses ordinary synthetic files only; another remote run needs fresh
integrator admission with an explicit 1,200-second bound. Guest/testing/signing
admission remains separate. No retry, threshold, duration or budget relaxation
is a substitute for qualification.

The owner's local restriction remains absolute: no sudo, password/Touch ID,
keychain/trust/TCC/privacy/login/firewall/profile changes or cleanup. Trusted
signing belongs on admitted CI/owned Boat; local ad-hoc signing can check only
structure. The prior local test identity result remains NONPASS. Private image,
profile and transfer-key bytes stay remote; production signing and publication
have not been performed.
