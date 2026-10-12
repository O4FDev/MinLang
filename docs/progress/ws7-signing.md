# WS7 signing implementation status — 2026-10-12

Source: `/tmp/minyar-ws7-signing`, branch `ws7/test-signing`, frozen starting
commit `bf9c0e9`. Core implementation was `3ed25bd`; independent R1 blocked it
on signer process limits and runner-root validation. This follow-up fixes both
and awaits fresh independent review. Approved registration
`fe66b86995a42f124e33b96d56e6ec61ecbb2b4f` was normally merged onto this branch
in `64cca368c605c7f6bfcf5b13900fe0dbbbaecef5`, without duplicate edits.
Parent owns independent review and qualification scheduling. Only the integrator
merges/pushes `v2`. No subagents, new VM, paid spend, push or `v2` merge performed here.

**OWNER STOP:** NEVER run local sudo (including sudo -n), admin/password/Touch ID
operations, keychain creation or cleanup even temporary, certificate trust
changes, TCC/privacy/login/firewall/profiles or other security mutations on this
laptop. Prior state permits read-only inventory only, never cleanup mutations.
Only local ad-hoc `codesign -s -` structure checks are permitted. Privileged or
trusted credential/signing proof belongs to explicit ephemeral CI or OWN Boat.
The current development release authorizes no new Mac security operations.

Done: explicit TEST release commands; complete tiny-native-artifact, signed
bundle/Ed25519 envelope/independent decode/OS verification harness with mutations;
Mac CI-only automatic credentials and guards before tools/output/certdirs;
OWNER-RUN provisioned identity route without automatic OS mutation; native
Windows/OWN Boat guard; cleanup failures/drift block exclusive atomic TEST
generation publication; public status reports; production keychain/profile
selection without search-list changes; manual artifact-only workflow; complete
[owner credential and update-policy wiring checklist](../release-signing.md).
Make/catalogue registration is now included through the exact approved parent
commit: compiler-free contracts participate in shipping/portable checks; the
native target remains explicit and conveys no signing authorization.

R1 follow-up validation on the preserved worktree: 23 Python signing contracts passed,
including direct API refusal, before-tool/before-directory guards, cleanup
failures/drift, output collision/failure preservation, independent decoding and
production keychain routing. Test-first regressions produced 20 expected
subcase failures before the fix. New controls inject `TimeoutExpired` into all
three Ed25519 operations at initial and first/last policy signing calls, for
mocked Mac and Windows credential contexts. They verify 60-second deadlines,
closed stdin, finally cleanup, no publication, failed reports and passphrase
removal. Missing/file runner roots are refused by CLI and direct context before
tools/mkdir/staging/report. The default production manifest runner retains its
existing subprocess options. The cleanup contract also covers private staging
failure before publication, actual atomic publication failure and accurate
reporting if external evidence fails after publication. Existing shipping
contracts: 12 pass. Catalogue: 508 host sources, 24 invalid controls rejected.
Final logs and commands are in the implementation handoff;
its containing commit is the review source. Python uses existing
3.11 and per-command `DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib`; no install
or OS-setting change. All native tools in these contracts are mocked.

Pending: trusted Mac end-to-end run only after review/merge in ephemeral GitHub
`macos-15`; real native Windows TEST run after owner hands off exclusive
`bx_jbb3dmp3` slot. Current Windows resource/binding abort preceded product
gates and signing; no test/signing admission is established. No local
native certificate test ran in this implementation turn; previous native Mac
attempt remains NONPASS (`CSSMERR_TP_NOT_TRUSTED`/no identity), never a pass from
mocks/ad-hoc signing. Workflow actionlint is pending on the parent's OWN Linux
focused slot; no local lint/parser installation or native probes ran. Parent
incorporates this scoped status into canonical `docs/progress/ws7.md`.
The original failed local diagnostic/cleanup inventory and earlier contract
logs were preserved. No prior security state was modified or cleaned up.
