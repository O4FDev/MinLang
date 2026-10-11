# Optional hosted UDP segmentation and receive offload

Linux UDP offload is an explicit packet API for a scalable QUIC transport.
Ordinary UDP and TCP paths retain their existing socket behavior. Offload
failure is a recoverable result; Minyar does not silently substitute a
successful software send or claim that a NIC performed the work.

## Sending

`net.sendDatagramsOffload(socket, data, segmentSize)` sends one concatenated
payload to a connected UDP peer using a per-message `UDP_SEGMENT` control.
`net.sendDatagramsOffloadTo(socket, source, port, data, segmentSize)` uses a
numeric IPv4/IPv6 destination without DNS or changing the socket's peer.
Both return the number of logical datagrams sent.

The payload is at most 65,507 bytes, the segment size is 1 through 65,507,
and the ceiling of payload length divided by segment size is at most 64.
The last packet may be shorter; exact multiples do not create an extra
empty packet. Empty payload sends one empty datagram. An empty packet in
the middle of a sequence must be sent separately. Invalid lengths/counts
are rejected before any send syscall. Each segment still has to fit the
path MTU; the kernel can reject a send with its original error code.

The Linux sender probes `UDP_SEGMENT` with a read-only socket option, so
older kernels' unsupported-option errors can be distinguished from
`EINVAL` during a supported send. It verifies a datagram socket and sends
an aligned, zero-initialized cmsg with a native-endian `uint16_t` payload.
It leaves the default segmentation socket option unchanged.

## Receiving and readiness

`net.datagramOffload(numericHost, port)` creates and binds its own
nonblocking UDP socket, enabling `UDP_GRO` before binding. Port zero selects
an available port. Check `datagramOffloadOk` and `datagramOffloadError`;
macOS and Windows report `errors.unavailableCode()` with a native OS code.
A Linux kernel that rejects the offload option also reports a recoverable
failure. There is no enable-GRO operation on an ordinary socket.

The record contains a generation-checked opaque negative ID, not an OS
descriptor. Even if a caller obtains that ID, ordinary `read`,
`receiveDatagram`, `receiveDatagrams`, `write` and `close` reject it.
Closed IDs cannot alias a reused registry slot. The socket and registry
belong to one owner thread, like the existing readiness loop.

Use `datagramOffloadPort`, `readyDatagramOffload`, and
`watchDatagramOffload(receiver, loop, interest, token)`. The last returns a
normal eventloop registration; normal update, remove and wait operations
apply. Remove the registration before `closeDatagramOffload`.

After readiness, call `receiveDatagramsOffload(receiver, maximum, limit)`
until its error is would-block. A full batch means there may be more work.
A small maximum can leave segments in userspace after their kernel
aggregate has been consumed; the kernel selector cannot signal those
segments again. `readyDatagramOffload(receiver, 0)` includes this pending
work. The implementation retains it for the next receive call.

The receive maximum is 1 through 64 logical packets, and the per-packet
prefix limit is 1 through 65,507 bytes. Every returned `Datagram` retains
its numeric source address and source port. Ordinary packets without GRO
metadata and zero-byte datagrams remain distinct packets. A short final
segment keeps its actual length. A per-packet prefix shorter than the
original packet has a `TRUNCATED` BytesResult, never a successful packet.

Receive storage is bounded to 65,535 bytes per active receiving socket,
allocated lazily. Original GRO wire lengths are checked before arithmetic,
bounded by 64 times 65,507, and must describe at most 64 segments. Only
copied prefixes are exposed. Missing tail bytes in a kernel-truncated
aggregate produce a batch truncation error after the retained prefixes.
When a maximum splits that prefix across calls, the terminal truncation
error is deferred until the prefix is exhausted. No missing packet is
invented as an empty datagram.

`sendDatagramOffloadTo(receiver, numericSource, port, data, segmentSize)`
replies from this same bound socket with segmentation, without exposing
its descriptor or changing its peer filter.

## Metadata and retained-prefix contract

All received ancillary headers are bounds-checked before aggregate data is
interpreted. `UDP_GRO` must appear at most once with exactly an `int`
payload, positive segment size at most 65,507 and a valid count. Short,
overlong, duplicate, overflowing or control-truncated metadata is rejected.
Well-formed unrelated controls are ignored. `memcpy` reads native values
without assuming data alignment.

A batch may fail after earlier packets were decoded. `datagrams(batch)`
requires success, as before. `datagramBatchPrefix(batch)` permits inspection
of the retained packets even on failure. Malformed metadata contributes no
bytes with unknown boundaries. A truncated aggregate retains complete
packets and the final available packet prefix; each partial packet is
marked truncated. Its missing suffix is discarded with a batch error.

Native envelopes retain the existing LE status/error/count and datagram
layout. Offload status 5 denotes unavailability; public errors use
`unavailableCode`. Prefix count is present on failed offload receives too.
This is an internal native ABI, not a network protocol.

## Evidence and scope

`tests/net-udp-offload.c` uses production networking code with independent
raw POSIX peers. Its Linux feature assertions require successful real
`UDP_SEGMENT` sends and an observed four-byte `UDP_GRO` cmsg on an aggregate
larger than one segment. It exercises 144 parameterized/randomized IPv4
send shapes, empty packets, IPv6 send/receive/reply boundaries, source
ports, opaque ID rejection, pending drain and epoll readiness. A syscall
provider separately supplies malformed and oversized receive states that
unprivileged UDP peers cannot place in kernel-generated ancillary data.
The provider also verifies that invalid send caps are rejected before
the syscall even when the provider would accept them.

Native and ASan/UBSan runs at O0/O2, the typed Minyar fixture, tests-first
red logs and guard mutation failures are recorded outside the source tree
in the existing Boat evidence directory. A Linux build with
`MINYAR_DISABLE_UDP_OFFLOAD=1` tests only the explicit unavailable branch;
it is not evidence of a Windows/macOS execution or of Linux hardware
offload. Loopback feature tests prove kernel offload execution and packet
contracts, not NIC acceleration or a throughput claim. The public cap64
is deliberate even though newer Linux kernels can support more segments.

Primary references:

- [Linux udp(7)](https://man7.org/linux/man-pages/man7/udp.7.html):
  segmentation/receive options, documented limits and MTU constraints.
- [Linux cmsg(3)](https://man7.org/linux/man-pages/man3/cmsg.3.html):
  ancillary alignment, lengths and safe payload copying.
- [Linux recvmsg(2)](https://man7.org/linux/man-pages/man2/recvmsg.2.html):
  original Internet datagram lengths with MSG_TRUNC, and control truncation.
- [Kernel segmentation offloads](https://docs.kernel.org/networking/segmentation-offloads.html):
  software fallback and the separate UDP datagram segmentation model.
- [Linux v6.8 UDP send parser](https://github.com/torvalds/linux/blob/v6.8/net/ipv4/udp.c):
  exact uint16_t UDP_SEGMENT cmsg ABI.
- [Linux v6.8 UDP receive metadata](https://github.com/torvalds/linux/blob/v6.8/include/linux/udp.h):
  int UDP_GRO ABI and the kernel's segment-count limit.
