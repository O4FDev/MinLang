# Vendored dependencies

- `stb_ds.h` 0.67 provides growable arrays and hash tables. It is copied from
  `nothings/stb` at commit `2c980bb59875b0d32144a71867fbdebb2f77cd20`.
- `STB-LICENSE` contains its public-domain/MIT dual license.

Upstream: <https://github.com/nothings/stb>

- `monocypher/` contains unmodified Monocypher 4.0.3 core and optional SHA-512 /
  RFC8032 Ed25519 sources from <https://github.com/LoupVaillant/Monocypher/tree/4.0.3>,
  tag commit `ab2b16dd619ad5f6979a4fbe69cfa324a6fcc35f`.
  `monocypher/LICENCE.md` carries its BSD-2-Clause / CC0 dual licence.
  `securecrypto` links the core for X25519, ChaCha20 and Poly1305; `update`
  additionally links optional Ed25519. This is the same pinned source used by
  the updater. SHA256 core C:
  `f1f838cdd483bdebe0df0ff5c5ed60535e496f769c6a2f933ac4c0b114207123`;
  optional C: `ce0d2f8e32ca8f66398ba5b3456cc74327c3eff14e7b950ce7d57be9025cc453`.
  The [Cure53 audit](https://monocypher.org/quality-assurance/audit) assessed
  version 3.1.1 in June 2020; it is not an audit of Minyar or version 4.0.3.
  Version 4.0.3 includes a subsequent upstream signing timing leak fix.
