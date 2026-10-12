# Plan for 20,000 physical QUIC/mTLS devices

Cost references checked 2026-10-12. This is a test and procurement plan, not a
capacity result or authorization to spend. The programme's shared paid cap is
$10; the integrator controls that cap. Included Boat credit is admitted for
development. No device purchase, cloud purchase or fleet contract is approved.

Start with four borrowed physical Linux devices and an admitted Boat target,
then borrow an existing managed fleet if possible. An owned wired lab is the
repeatable alternative, with a planning budget of about **$2.43 million before
tax**. A borrowed fleet has an illustrative **$218,400** staffing/incentive
budget plus an unquoted fleet-access charge. Neither route has a supplier or
fleet-availability commitment.

## What counts and what runs

The final run requires 20,000 simultaneously connected physical endpoints,
one test agent and one enrolled identity per device. Virtual machines, multiple
processes on one board, gateway counts and 20,000 certificates alone do not
establish 20,000 physical devices. Record an operator-verified inventory of
board/device serials, hardware models, agent/binary hashes and public certificate
fingerprints. Challenge each inventory entry over its authenticated session;
reject duplicate active identities. A software CSR is not hardware attestation
and does not establish nonexportability or prevent a dishonest inventory.

Use a pinned ARM64 Linux image on Raspberry Pi 4 Model B 1 GB for the owned
fleet: four ARM cores and onboard Gigabit Ethernet, with headless operation,
microSD boot, case and a 5.1 V/3 A USB-C supply. Its hardware and supply
requirements are documented by [Raspberry Pi](https://www.raspberrypi.com/products/raspberry-pi-4-model-b/).
The observed US reseller board price is $38.50, currently out of stock, rather
than assuming a volume discount from the manufacturer's $35 base price.
[Reseller reference](https://www.adafruit.com/product/4295),
[manufacturer's current price notice](https://www.raspberrypi.com/news/price-increases-for-2gb-raspberry-pi-4-and-raspberry-pi-5/).

The target is one Minyar peer-edge process, initially on an isolated 8-core,
32-GiB Linux server. Put Redis, the independent observer and the controller on
separate allocated machines for the final run, with a 10-GbE or faster backbone.
Record target core/CPU model, kernel, tools, source SHA and binary hash; do not
substitute several sharded targets for the single-target capacity claim. These
server sizes are starting allocations, not measured capacity requirements.
Compilation and long target measurements run on admitted Boat infrastructure;
physical clients necessarily run on the supplied devices. Any Windows work
remains on Boat. Default pilot and purchased endpoints are Linux.

The existing `tests/peer-edge-device-scale.py` and
`tests/interop/quinn/src/bin/peer-edge-scale.rs` are synthetic lab fixtures.
They share a lab leaf key, assume `localhost`, start device indices at zero for
each invocation and validate fixed lab IP/ASN/country fields. Before deployment,
coordinate a separately tested adapter with WS6: one device ID per process,
the actual server name, local per-device key/CSR enrollment and an exact expected
inventory. Keep identity and heartbeat validation; do not disable checks to
accept real network metadata. Never distribute the CA private key or the shared
lab leaf key to devices.

Generate a distinct P-256 private key on each device and submit only its CSR.
Use a private test CA, unique serial and URI SAN bound to the enrolled device,
`clientAuth` usage, bounded validity, explicit revocation and no duplicate active
ID. The server has its own `serverAuth` certificate with the tested DNS name or
IP SAN. Preserve untrusted-root, wrong-name, wrong-identity, wrong-EKU, expired
and revoked controls. This test PKI is separate from OS release-signing
certificates and the updater's Ed25519 key. Ordinary Pi software key storage
does not imply TPM/HSM protection.

## Pilot: at most $10, with no hardware purchase

Borrow two ARM64 boards and two x86-64 Linux computers with their existing
power, storage and network. Device loans are a prerequisite and are not yet
confirmed. If loans are unavailable, the real-device pilot is unavailable;
simulated clients can prepare it but cannot replace it.

Prefer an already admitted owned Boat Linux target, controller/observer and
existing network on included credit: **$0 additional paid spend**. First verify
actual client-to-target UDP and TCP reachability; an HTTPS exposure or a TCP
forward alone does not prove QUIC UDP access. Do not create another paid service
merely to work around a failed reachability probe.

If the integrator allocates part of the shared $10 cap to a paid fallback, a
conditional EU dedicated CCX33 target for at most eight hours costs $2.0896 at
the published $0.2612/hour reference. Budget a whole $0.60 IPv4 month, $1 traffic
reserve, $0.10 estimated device electricity and $2 tax/rounding reserve: **$5.79**
plus up to **$4.21 contingency**, hard total **$10**. Recheck the checkout price,
tax and remaining programme cap before ordering; reduce duration or do not order
if the all-in limit cannot be met. The [provider's price list](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/)
and [IPv4 reference](https://docs.hetzner.com/cloud/servers/primary-ips/overview/)
support these unit rates, not a booked service or availability guarantee.

Create no backups, paid volumes or snapshots. Prearrange deletion by eight hours
and verify deletion of both server and separately allocated IPv4; a stopped
server or unassigned IP remains billable. Traffic alerts are not a spending cap.
[Billing and deletion rules](https://docs.hetzner.com/cloud/billing/faq/).
The fallback server route needs separate integrator admission under the Boat
execution rule; it is not permission for an agent to run outside Boat.

Enroll all four devices before issuing one fresh common future start within
30 seconds. Observe two hours of connected heartbeats with independent Redis
validation. Then run separately labeled disconnect/reconnect, one-device reboot,
wrong/revoked identity and UDP-blocked TCP fallback cases. Preserve normal
shutdown, zero live entries and released peer/relay state. Record source/tools,
inventory, public key fingerprints, admission, CPU/RSS, UDP drops, heartbeats,
faults and teardown. The pilot establishes enrollment and measurement mechanics,
not 20,000-device capacity.

## Owned lab bill of materials

Purchase 21,000 devices for 20,000 active endpoints and 1,000 replacement spares.
Use 425 access switches with 48 endpoint ports and separate SFP uplinks: 20,400
active ports. The additional 1,000 spares need not be connected simultaneously.
Group access switches behind aggregation/core switches; physically separate
device wiring, power and the observer/control plane. Obtain an electrical and
cooling design before booking a facility.

All amounts below are USD before tax. Retail observations and planning
allowances are labeled separately. Supplier stock and 21,000-unit lead times
must be quoted; a web listing is not a reservation.

| Item | Quantity × unit allowance | Cost | Basis |
| --- | ---: | ---: | --- |
| Pi 4 Model B 1 GB boards | 21,000 × $38.50 | $808,500 | Observed reseller price; out of stock |
| Official 5.1 V/3 A USB-C supplies | 21,000 × $8.74 | $183,540 | [Retail reference](https://www.adafruit.com/product/4298); no bulk discount assumed |
| Boot microSD cards, 16/32 GB | 21,000 × $20 | $420,000 | Planning allowance; obtain a current matched card quote |
| Cases | 21,000 × $5 | $105,000 | Planning allowance |
| Ethernet patch leads | 21,000 × $2 | $42,000 | Planning allowance |
| 48-port access switches | 425 × $439 | $186,575 | [USW-48 surcharge-inclusive reference](https://store.ui.com/us/en/category/cloud-gateways-wifi-integrated/products/usw-48) |
| Aggregation/core switches | 20 × $990 | $19,800 | [USW-Pro-Aggregation surcharge-inclusive reference](https://store.ui.com/us/en/category/switching-aggregation/products/usw-pro-aggregation); sold out at lookup |
| Optics, racks, PDUs, imaging fixtures and cooling setup | Fixed allowance | $120,000 | Site-dependent engineering quote required |
| Imaging, inventory, enrollment and operators | 3,000 hours × $35 | $105,000 | Staffing assumption, including spare handling |
| Target/Redis/observer/control hosting, two weeks | Fixed allowance | $2,000 | Sizing and provider quote required |
| Facility and electricity, two weeks | Fixed allowance | $30,000 | Site and energy assumptions below |
| **Subtotal** | | **$2,022,415** | |
| **20% contingency** | | **$404,483** | Shipping, failures and price uncertainty; obtain actual quotes |
| **Planning total before tax** | | **$2,426,898** | Approximately **$2.43 million** |

The microSD allowance is not the discontinued [16-GB product](https://www.adafruit.com/product/2693)
offered as a purchase recommendation; that listing is only a historical retail
price reference. Source an available, qualified card and image before volume
ordering. The cheaper Zero 2 W has no onboard Ethernet; adapter, power and driver
qualification costs erase much of its board-price advantage. Its observed
[board reference](https://www.adafruit.com/product/5291) and
[Ethernet adapter listing](https://www.adafruit.com/product/2992) are both out of
stock, and the adapter page records an OS compatibility warning.

For facility planning, assume 6 W per active board and 20 W per access switch:
about 128.5 kW before server/core overhead. At assumed PUE 1.5 and $0.20/kWh,
two weeks uses about $12,953 in electricity; the $30,000 line also allows facility
cost. These are assumptions to replace with pilot power measurements and a
facility quote. Local tax is additional. Contingency is not a guaranteed tax,
shipping or electrical-installation quote.

## Borrowed fleet alternative

Prefer an operator with an existing consenting physical fleet and an enforceable
test window. Enroll 22,000 devices for a 10% attendance margin, then require
20,000 present at the common start. Hardware capital is $0 only if the operator
already owns and supplies the devices; no fleet has been committed.

Illustrative budget: 22,000 enrollment incentives × $5 = $110,000; 1,200
engineering/operator hours × $50 = $60,000; hosting $2,000; network/logistics
$10,000. Subtotal $182,000 plus 20% contingency is **$218,400 before tax**, plus
the separately quoted fleet rental/access fee. These are commercial assumptions,
not supplier prices. Incentives do not guarantee recruitment or simultaneity.
Record the network and hardware distribution; an existing Wi-Fi/NAT fleet is a
different experiment from the owned wired lab.

## Admission, measurement and stop decisions

Do not order volume hardware before the four-device pilot, synthetic admission
regression and a 512-physical-device stage pass. The recorded 4,096 synthetic
cohort stopped during setup at 2,063 authenticated clients, before a steady-state
window, with the original 20-second handshake timeout. That unresolved failure
must be diagnosed and repaired rather than increasing the timeout.

Run physical stages 4, 32, 128, 512, 2,048, 4,096, 10,000 and 20,000, stopping on
the first failure. A planned 20 admissions/second takes 1,000 seconds for 20,000
devices, within the existing 1,800-second setup ceiling; pilot measurements must
establish whether that rate is safe. Keep the original per-device handshake
limit. A simultaneous reconnect storm is a separate fault test, not evidence
that a staggered ramp can be relabeled as a storm.

Preserve the existing capacity fixture's gates:

- Exact expected device set, Redis keys and stable owner epochs; all requested
  devices admitted before a common start. Heartbeats every 15 seconds, fresh
  within 30 seconds, and every device advances after the common start.
- Target connected CPU at most 0.02 of one CPU; do not divide by the host core
  count. For each two-hour run, target RSS span at most 16,384 KiB and slope at
  most 0.2 KiB/second, after the existing warm-up. Retain raw samples and math.
- Normal shutdown and retirement, zero active peers/retained relays and equal
  opened/released calls. Forced cleanup records failure, never a pass.

Keep active traffic, network churn, connected idle, UDP-blocked fallback and
sanitizer cohorts separate with their original or explicitly approved contracts.
The final primary run is two hours; an optional 23-hour endurance run fits the
current 82,800-second bound and needs a separate credit/resource allocation.
At assumed 1-KiB heartbeats per 15 seconds, 20,000 devices send about 1.37 MB/s
of payload before protocol overhead; an assumed 1-KiB/second active phase is
about 20.48 MB/s. These are sizing arithmetic, not measured throughput.

Before execution, the owner supplies device loans/fleet access, an approved
budget or procurement quote, inventory/enrollment authority, reachable target
networking and a scheduled test window. WS6 owns the transport adapter and
regression tests; WS7 owns this cost and execution design. Review the software,
pilot evidence and exact hardware/server allocation before each scale increase.
