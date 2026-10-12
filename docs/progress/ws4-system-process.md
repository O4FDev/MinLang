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
