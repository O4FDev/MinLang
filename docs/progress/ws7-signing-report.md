# WS7 signing handoff — 2026-10-12

Review source: `/tmp/minyar-ws7-signing`, branch `ws7/test-signing`; the commit
containing this report is the reviewable implementation chunk. No SHA has landed
on `v2` yet. Parent performs review and the integrator alone merges/pushes.

Changed: `scripts/release.py`, `tests/release-signing.py`,
`tests/release-pipeline.py`, `.github/workflows/release-signing.yml`,
`docs/release-signing.md`, a link in `docs/shipping.md` and scoped progress notes.
Preserved existing production notarization/timestamp/acceptance gates; added
explicit already-provisioned keychain/profile paths. `ci.yml`, shipping.mk and
the suite catalogue are untouched by this implementation.

The contract suite closes automatic Mac security mutation before authorization,
wrong native host/Boat context, cleanup failure/drift passing as success,
wrong TEST output/identity and failure/collision overwriting a generation.
Native pipeline qualification additionally requires actual wrong certificate,
key/domain/policy and artifact/resource/executable mutation refusals after the
independent decode. The complete commands are in
[release-signing.md](../release-signing.md) and the manual workflow.

Local validation commands, using installed Python/expat only:

```sh
env DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib \
  /opt/homebrew/bin/python3.11 tests/release-signing.py
env DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib \
  /opt/homebrew/bin/python3.11 tests/shipping.py
git diff --check
```

Final contract results: signing **19 passed**, shipping **12 passed**; both
commands exited 0. `git diff --check` passed. Final logs are
`/tmp/minyar-ws7-signing-evidence/release-signing-final.log` and
`/tmp/minyar-ws7-signing-evidence/shipping-final.log`; earlier logs remain intact.
The final cleanup contract additionally verifies private staging is removed
before the atomic generation commit, and a staging cleanup or actual commit
failure creates no passing generation. External report failure after a successful
commit exits nonzero and accurately reports that the generation was published.
The original failed local certificate diagnostic and cleanup inventory are
preserved; no prior security-state cleanup was attempted. This is mocked
contract evidence, not native signing evidence. Trusted Mac remains NONPASS until
integrator CI; Windows is not run until the exclusive OWN Boat handoff. Production
Developer ID/notary/hardware-or-cloud Windows credentials and the approved
Ed25519 key/app/target/channel/sequence/origin policy are owner inputs, never TEST
fixtures. No public publication is authorized.

**Owner restriction carries forward:** no local sudo (even sudo -n), admin or
Touch ID operations, keychain/trust/TCC/privacy/login/firewall/profile changes or
cleanup of prior state. Read-only inventory only for prior state; optional local
ad-hoc `codesign -s -` structure checks only. Credential/trusted signing proof only
ephemeral CI or OWN Boat with explicit scope. Development creates no new laptop
security permission. No paid spend, new VM, subagent, push or merge here.
