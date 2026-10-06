# Adapted three-move case: expectations before corrected replay

The literal review layout could not arise from the chosen actual prefix: its existing free 32-byte nodes make the common header choose 864, before it could choose 64. The failed reporting assertion is preserved. Parent authorized the genuine allocator-created variant, without a callback or injected operation after the header. This derivation follows the declared allocation/free sequence and allocator rules before the corrected replay; it does not promote the failed layout to an executed pass.

Ascending allocation of the complete 4096-byte partition reaches each declared aligned start by splitting the next available block. Source header is 0/32; source backing is 512/128. Other requested blocks are initialized completely to `0x5a`. The freed starts are 800, 864, 896, 128, 640, 256, 2048, 2560, 1024, 3072, 64, 96. Head insertion gives class-0 order `[864,800]` after the final 64/96 buddy pair coalesces; removing 64 to coalesce does not remove either surviving node. The merged class-1 block 64 is inserted before `[128,896]`. Other classes have `[256,640]`, `[2560,2048]`, `[1024]`, `[3072]` respectively. Their allocated buddies prevent further coalescing. Allocated raw blockers total 1376 bytes; source header/backing total 160, so pre-header charge is 1536.

The real common 32-byte result header selects class-0 head 864 without splitting. The comparison boundary therefore has charge 1568 and mask 63, with ordered lists:

| Block size | Expected offsets in order |
| --- | --- |
| 32 | 800 |
| 64 | 64, 128, 896 |
| 128 | 256, 640 |
| 256 | 2560, 2048 |
| 512 | 1024 |
| 1024 | 3072 |

Allocated starts/orders are `0/0,32/0,192/1,384/2,512/2,768/0,832/0,864/0,960/1,1536/4,2304/3,2816/3`. Free starts/orders follow the table. These independently specify every start map byte (allocated `0x80|(order+1)`, free `order+1`) and zero interior byte. Every previous/next link follows the displayed order, with null endpoints.

Original construction requests 32,64,128,256 bytes. It first takes 800. Growth to 64 cannot stay at 800 because that address is the upper 32-byte buddy; it takes 64 and reinserts 800. Growth from 64 to 128 fails lower-half alignment; it takes 256 and reinserts 64 before the still-present tail `[128,896]`. The 128-to-256-byte growth from base 256 fails because its upper 128-byte buddy 384 is occupied; it takes class-3 head 2560 and reinserts 256 before 640. Direct 256-byte reservation takes the same 2560. Thus final lists should equal the boundary lists except class 3 becomes `[2048]`; only map byte at 2560 changes from free order 3 to allocated order 3. Final charge is 1824; requested RC bytes are 448 (source 160, result 288).

There are 23 setup allocations: source header plus 22 partition pieces, including the source backing. The common header adds one; original backing requests add four, direct adds one. Append-completion counts should be 28 versus 25. Both high-water values stay 4096 because setup first filled the whole partition; differing step metrics remain excluded. No telemetry feeds request decisions.

The same valid raw requests 32,64,128,4096 and reverse frees follow. Raw request payload is never read before initialization, no resize copies uninitialized data, and final release/drain/free must recover exactly zero tracked objects, requested bytes and charge. All scheduler roots remain null; the fixture sets matched latent recent-turn 1/next-queue 2 before the public append, explicitly separate from the actual allocator prefix. These are test-only residues, not a claimed public-API trace. Idle allocation service must preserve them. The full-state oracle includes the residues, every ordered link and initialized blocker contents. This is one bounded source-correspondence check, not a proof or literal complete-state equality claim.
