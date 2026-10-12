# System/process track

Frozen base: bf9c0e9; no rebase, v2 merge, push or Boat provisioning by this child.

Environment/resource-limit chunk: copied getenv/environment, missing/empty distinction,
named portable resources with soft/hard setters, Windows clocks/RSS/stderr and explicit
unsupported POSIX operations. Test-first `python3 tests/system-services.py` failed on
missing APIs, then passed all four native macOS cases. Language, Linux and Windows
validation remains pending parent-owned Boat execution. No gap is marked landed in v2.

Process API implementation and privilege tests are next. macOS credential setters are
private SPI and must be dynamically discovered with exact signatures. XNU requires root
for these spawn attributes; groups setter needs a non-NULL array even for zero groups.

First implementation commit: d3f7b966937b4d5496e623d2d7cb45779e44ddbb.
Assigned Linux box bx_ppv9fjr7, namespace `/home/user/ws4/system-r2`: immutable
bf9c0e9 baseline copied with compiler SHA f4f589328d1b53b8cf92c9aa8b0da1f5168bca1b4e8cf9198ff1b542cc59212b.
`python3 tests/system-services.py --language` and `--mode sanitize` passed (exit 0).

Process regressions first failed on missing native functions, then
`python3 tests/system-process.py` passed on native macOS: argv/envp/empty env,
Unicode executable/cwd, NUL/malformed input, synchronous ENOENT, stale handles,
pending poll, child exit 127, SIGPIPE disposition AND mask, FD_CLOEXEC, and actual
macOS credential SPI privilege denial with parent credentials/mask preserved.
Linux clone-vfork, root credential ordering, language integration and Windows
process execution remain pending remote qualification at this commit boundary.

Apple primary source design evidence:
- [SPI exact prototypes](https://github.com/apple-oss-distributions/xnu/blob/main/libsyscall/wrappers/spawn/spawn_private.h): uid/gid setters accept `const posix_spawnattr_t *`; groups adds `int`, `gid_t *`, `uid_t gmuid`.
- [Parent-side wrappers](https://github.com/apple-oss-distributions/xnu/blob/main/libsyscall/wrappers/spawn/posix_spawn.c): credential attributes allocate in the caller and validate groups including a non-NULL pointer at zero count.
- [Kernel spawn](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_exec.c): credential attributes require root; kernel applies gid, groups, then uid.
- [Group semantics](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_prot.c): zero groups installs group zero. Package prepends the requested/inherited effective gid to the supplementary list.
- [Credential model](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_credential.c): gmuid KAUTH_UID_NONE disables memberd expansion, keeping the explicit group list authoritative.

Linux shared-VM child has a guarded independent stack and only inline kernel
syscalls, with no-sanitize/no-stack-protector/no-instrument annotations. All
signals (including reserved NPTL signals) are blocked across clone. Child resets
caught dispositions before restoring its inherited mask minus SIGPIPE. Child
does not share the parent's descriptor table, cwd, or signal dispositions.
