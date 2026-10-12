# WS7 signing handoff — 2026-10-12

Review source: `/tmp/minyar-ws7-signing`, branch `ws7/test-signing`; the commit
containing this revised report is the corrected implementation for fresh review.
R1 at `/tmp/minyar-ws7-signing-review-r1.md` blocked original core
`3ed25bd2873f9073e5ffc7dd3eb93be63f668a0d` on R1-1/P1 and R1-2/P2. It approved
the separate registration delta without additional findings. Exact registration
`fe66b86995a42f124e33b96d56e6ec61ecbb2b4f` was merged onto this branch via
`64cca368c605c7f6bfcf5b13900fe0dbbbaecef5`; no registration edits were duplicated.
No SHA has landed on `v2` here. Parent obtains fresh independent review and the
integrator alone merges/pushes `v2`.

Changed: `scripts/release.py`, `scripts/update-manifest.py`, `tests/release-signing.py`,
`tests/release-pipeline.py`, `.github/workflows/release-signing.yml`,
`docs/release-signing.md`, a link in `docs/shipping.md` and scoped progress notes.
Preserved existing production notarization/timestamp/acceptance gates and
explicit already-provisioned keychain/profile paths. Registration includes
shipping.mk/catalogue/docs solely through the approved merge. `ci.yml` is untouched.

R1-1: `scripts/update-manifest.py` accepts an optional keyword runner; its default
retains existing production subprocess options. Both actual signing call sites
in the harness inject the shared 60-second, closed-stdin runner into all three
Ed25519 operations. `test_initial_ed25519_timeouts_clean_credentials_and_never_publish`
and `test_signed_policy_ed25519_timeouts_clean_credentials_and_never_publish`
mock timeouts at public derivation/sign/verify for initial and first/last policy
calls, with actual Python Mac/Windows credential context `finally` blocks.
Every external command is mocked. Each case verifies credential cleanup, no
generation publication, private staging/passphrase removal and FAILED reporting.
Admission is mocked in these timeout cases; guard regressions are separate. The
publication cleanup contract now also mocks admission rather than changing
`sys.platform`, so it selects the actual host's file rename implementation.

R1-2: the Mac CI guard resolves `RUNNER_TEMP` strictly and requires an existing
directory before containment checks. Missing/file root regressions exercise
CLI and direct credential entry with no tools, mkdir, stage, output or report.
All explicit flag/hosted-CI checks remain. Owner-provisioned credentials and
production signing gates are unchanged.

The contract suite closes automatic Mac security mutation before authorization,
wrong native host/Boat context, cleanup failure/drift passing as success,
wrong TEST output/identity and failure/collision overwriting a generation.
Native pipeline qualification additionally requires actual wrong certificate,
key/domain/policy and artifact/resource/executable mutation refusals after the
independent decode. The complete commands are in
[release-signing.md](../release-signing.md) and the manual workflow.

Local validation commands, using installed Python/expat only:

```sh
env PYTHONDONTWRITEBYTECODE=1 DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib \
  /opt/homebrew/bin/python3.11 tests/release-signing.py
env PYTHONDONTWRITEBYTECODE=1 DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib \
  /opt/homebrew/bin/python3.11 tests/shipping.py
env PYTHONDONTWRITEBYTECODE=1 DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib \
  /opt/homebrew/bin/python3.11 tests/suite-catalogue.py
git diff --check
```

Test-first RED: 22 tests, 20 expected failing subcases (18 missing process guards,
two invalid roots reaching mocked tools), exit 1. Final GREEN: signing **23 passed**,
shipping **12 passed**, catalogue **508 sources / 24 invalid controls rejected**;
all three commands exited 0. `git diff --check` passed. Logs under
`/tmp/minyar-ws7-signing-evidence/`: `release-signing-r1-red.log`,
`release-signing-r1-green.log`, `shipping-r1-green.log`,
`suite-catalogue-r1-green.log`. Earlier logs remain intact.
The final cleanup contract additionally verifies private staging is removed
before the atomic generation commit, and a staging cleanup or actual commit
failure creates no passing generation. External report failure after a successful
commit exits nonzero and accurately reports that the generation was published.
The original failed local certificate diagnostic and cleanup inventory are
preserved; no prior security-state cleanup was attempted. This is mocked
contract evidence, not native signing evidence. Trusted Mac remains NONPASS until
integrator CI; Windows is not run until the exclusive OWN Boat handoff. Its
current resource/binding abort establishes no product gate or signing result.
Workflow actionlint awaits the parent's OWN Linux focused slot. Broader WS7
strict Windows idle/full portable, measured CI before/after and costed 20k
physical-device <=$10 pilot obligations remain separate; no result is claimed
for them here. Production
Developer ID/notary/hardware-or-cloud Windows credentials and the approved
Ed25519 key/app/target/channel/sequence/origin policy are owner inputs, never TEST
fixtures. No public publication is authorized.

**Owner restriction carries forward:** no local sudo (even sudo -n), admin or
Touch ID operations, keychain/trust/TCC/privacy/login/firewall/profile changes or
cleanup of prior state. Read-only inventory only for prior state; optional local
ad-hoc `codesign -s -` structure checks only. Credential/trusted signing proof only
ephemeral CI or OWN Boat with explicit scope. Development creates no new laptop
security permission. No paid spend, new VM, subagent, push or `v2` merge here.
