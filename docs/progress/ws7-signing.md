# WS7 signing implementation status — 2026-10-12

Source: `/tmp/minyar-ws7-signing`, branch `ws7/test-signing`, frozen starting
commit `bf9c0e9`. Parent owns independent review, shipping.mk/catalogue integration
and qualification scheduling. Only the integrator merges/pushes
`v2`. No subagents, new VM, paid spend, push or merge performed here.

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

Final validation on the preserved worktree: 19 Python signing contracts passed,
including direct API refusal, before-tool/before-directory guards, cleanup
failures/drift, output collision/failure preservation, independent decoding and
production keychain routing. The cleanup contract also covers private staging
failure before publication, actual atomic publication failure and accurate
reporting if external evidence fails after publication. Existing shipping
contracts: 12 pass. Final logs and commands are in the implementation handoff;
its containing commit is the review source. Python uses existing
3.11 and per-command `DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib`; no install
or OS-setting change. All native tools in these contracts are mocked.

Pending: trusted Mac end-to-end run only after review/merge in ephemeral GitHub
`macos-15`; real native Windows TEST run after owner hands off exclusive
`bx_jbb3dmp3` slot following base/profile transfer and Windows gates. No local
native certificate test ran in this implementation turn; previous native Mac
attempt remains NONPASS (`CSSMERR_TP_NOT_TRUSTED`/no identity), never a pass from
mocks/ad-hoc signing. Workflow actionlint is pending on OWN Boat; local actionlint
and PyYAML are unavailable and were not installed. Parent incorporates this
scoped status into canonical `docs/progress/ws7.md`.
The original failed local diagnostic/cleanup inventory and earlier contract
logs were preserved. No prior security state was modified or cleaned up.
