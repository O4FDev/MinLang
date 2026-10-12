# Format backend decisions

The preference is unchanged: use pure Minyar when the complete operation takes
at most 1.5 times the maintained C reference's time. These are new-module
measurements, separate from the programme's existing-workload ±1% gate.

| Module | Choice | Reason and evidence |
| --- | --- | --- |
| zstd | Native libzstd | Interoperable maintained codec, bounded full-frame decode, reusable contexts and explicit RAW/by-copy CDict/DDict. Advanced dictionaries require a real matched static archive. No pure candidate was measured; no pure/C ratio is claimed. Binding/C medians at 64 KiB are 0.953–1.085 over 105 paired observations. |
| gzip/zlib/raw DEFLATE | Native zlib | Maintained format/checksum implementation, bounded output, strict trailing-input handling and concatenated gzip. No pure candidate was measured. The same complete-operation benchmark includes allocation, raw and Into paths. |
| Streaming SHA-256 | Native OpenSSL libcrypto | Optimized pure Minyar measured 1.817/1.892 times portable C and 8.468/8.437 times default OpenSSL EVP at 1 MiB. Native measured about 0.99 times direct SHA. The standalone module owns value contexts in Bytes and does not import securecrypto. Small inputs have material wrapper/ownership overhead. |
| tar reader/writer | Native libarchive with bounded wire metadata adapter | Pure measured 3.089–8.479 times C and failed the preference. Native preserves byte metadata, extension spans, vendor attributes and exact timestamps beyond the provider's metadata API. Native measured 2.041–11.048 times C; it is not faster than pure on every workload. Review found correctness fixes still needed before integration. |
| erofs/ext4 writing | Deferred | Optional image writing is separate from the required tar reader/writer and remains open. |

Sources, executable/provider identities, exact commands, quiet process
inventories and raw samples are retained under `docs/evidence/{compression,
sha256,tar}`. Native dictionaries and tar contexts require explicit close and
exclusive use; there are no global/TLS caches. SHA contexts have value storage.
The compression API is whole-buffer bounded to 256 MiB, including raw/Into;
tar is also in memory. Large OCI streams still need an adapter or streaming
API. The neo-vm chunk call fits these bounds.

See [compression contracts](../compression/contract.md), [SHA notes](../sha256.md),
[tar notes](../tar.md), and the [proposed shim deletion](neo-vm-shim-removal.md).
The proposed patch changes no neo-vm files. Owning gap documents will receive
`fixed in v2 <sha>` only after the integrator confirms the relevant merge, and
only for the functionality actually supplied. Windows ABI qualification and
the existing-workload regression gate remain pending.
