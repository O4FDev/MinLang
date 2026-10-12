# Prior qualification findings

These are summaries of earlier tool output, not reconstructed raw receipts.
The final-68948fb directory contains the current exact source-bound receipts.

- Test-first services compilation failed on missing getenv/environment and
  get/set limit natives before d3f7b96 implementation.
- Test-first process compilation failed on missing spawn/PID/wait natives before
  055ada5 implementation.
- Initial launcher language run passed behavior but regenerated the namespace's
  compiler from supplied f4f589328d1b53b8cf92c9aa8b0da1f5168bca1b4e8cf9198ff1b542cc59212b
  to 0b8bd2f48c5f6dbce09fa4a7fc69db168102ce5c9c14eafa591dc8f966aa0d49
  through its bootstrap/toolchain stamp. The immutable parent baseline was not
  modified. Qualification rejected this mismatch, restored copied baseline
  bytes in the child namespace and now uses --prebuilt direct compilation/linking.
- Initial sanitized language helper compiled bare minyar_runtime.c and failed
  linking minyar_rc_enter_stack_v1/minyar_rc_leave_stack_v1. The helper now compiles
  canonical minyar_default_runtime.c, including the expected stack-frame ABI.
- Initial positive root fixture dropped to nobody (65534), which could not
  traverse /home/user mode 0750. Exec correctly returned -EACCES. The fixture
  now drops to its unprivileged executable owner while still proving saved-ID
  removal, inability to regain root, explicit/empty groups and parent isolation.
  No home permissions or host security settings were changed.
- The parent-turn interruption did not complete qualification of 68948fb.
  Resumption verified no live job and preserved earlier a086d75 receipts before
  creating a distinct final-68948fb run. All six final suites and the child audit
  passed; Windows and privileged macOS remain unqualified platform work.
