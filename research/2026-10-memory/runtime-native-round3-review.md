# Independent review of the minimal PNG proposal

No blocker found for the proposed five-line repair on the supported ABI: 32-bit
`int`, 64-bit `size_t`. This is a read-only review; no production file was changed.
Reviewed patch SHA256 is
`3b42ed486322cd77f1f502303b19691b4fe63d74fb0948e84b430c43ec126999`.
The isolated results SHA256 is
`905b80b2d8428890d64b6390977905fa2d872eeadaa1317bd6f1ce5e3c49fff1`.

The private chunk guard rejects lengths above 2^31−1 before narrowing or writing.
This matches the [PNG chunk limit](https://www.w3.org/TR/2025/REC-png-3-20250624/#5Chunk-layout);
zero and the inclusive endpoint remain legal. Rejecting oversized single-IDAT
images is an explicit writer limitation; legal PNGs can instead split IDAT data
across chunks. That larger design is outside this repair.

I independently recomputed the maximum dimension endpoint and all seven saved
examples with Python integers. For positive dimensions, raw length R is nonzero,
so `(R-1)/65535+1` gives the exact block count without underflow. The zlib stream
length is R+5*ceil(R/65535)+6. All intermediate row/raw/pixel/allocated/encoded
values fit size_t for dimensions through INT_MAX on the stated ABI. The guard
therefore cannot wrap before deciding. Once admitted, raw length is below the
chunk limit and pixel storage is below 4/3 of raw length, also below PTRDIFF_MAX.
The existing five-byte allocation slack at an exact 65535 multiple is preserved;
it does not justify rejecting the smaller actual encoded length.

Casting x before multiplying removes signed-int overflow in RGB/RGBA offsets.
The other row/source products already cast before multiplication. Positive width
and height make `height-1-y` safe; loop counters stop at INT_MAX without incrementing
past it. The patch adds no state, public signature, allocation or chunk-layout
change. UINT32_C is available through the existing stdint include. This proof is
not 32-bit portability evidence.

Nonpositive dimensions still defer without allocation or clearing the pending
path. Over-limit positive images now report the deliberate `the screenshot is
too large.` diagnostic before allocation/readback/file operations; this changes
the previous OOM-or-invalid-file outcome intentionally. Size-valid allocation,
write and close failure behavior is unchanged by inspection. Fatal traps do not
return a partially created screenshot to the caller.

The retained original header-prefix reds are sufficient to justify the local
chunk serialization guard: they exercise the real first write without giant
allocation or payload access. The 38 isolated checks cover boundary rejection,
small actual PNGs across a stored-block boundary, allocation-order/defer controls
and mesh controls in native and C ASan/UBSan modes. I inspected those recorded
results and source; I did not independently rerun that matrix. Huge real GLFW
framebuffers, successful huge readback and the overflowing old pixel loop remain
unexecuted. These are conditional domain proofs, not observed GPU failures.

Acceptance should preserve the original red and proposed records, then record
focused final-source zero/retry, selective allocation and file-write/close checks.
This proposal does not certify GPU state, driver behavior or whole integration.
