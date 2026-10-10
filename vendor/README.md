# Vendored dependencies

- `stb_ds.h` 0.67 provides growable arrays and hash tables. It is copied from
  `nothings/stb` at commit `2c980bb59875b0d32144a71867fbdebb2f77cd20`.
- `STB-LICENSE` contains its public-domain/MIT dual license.

Upstream: <https://github.com/nothings/stb>

- `monocypher/` contains unmodified Monocypher 4.0.3 core and optional SHA-512 /
  RFC8032 Ed25519 sources from <https://github.com/LoupVaillant/Monocypher/tree/4.0.3>.
  `monocypher/LICENCE.md` carries its BSD-2-Clause / CC0 dual licence. Only programs
  importing `update` link it. Version 4.0.3 includes the upstream signing timing
  leak fix; verification does not use our own curve arithmetic.
  SHA256 of core C: `f1f838cdd483bdebe0df0ff5c5ed60535e496f769c6a2f933ac4c0b114207123`;
  optional C: `ce0d2f8e32ca8f66398ba5b3456cc74327c3eff14e7b950ce7d57be9025cc453`.
