# Unicode 18.0.0 conformance data

Unmodified Unicode Character Database files, downloaded from:

- <https://www.unicode.org/Public/18.0.0/ucd/auxiliary/GraphemeBreakTest.txt>
- <https://www.unicode.org/Public/18.0.0/ucd/NormalizationTest.txt>
- <https://www.unicode.org/Public/18.0.0/ucd/CaseFolding.txt>
- <https://www.unicode.org/Public/18.0.0/ucd/SpecialCasing.txt>
- <https://www.unicode.org/Public/18.0.0/ucd/DerivedCoreProperties.txt>
- <https://www.unicode.org/Public/18.0.0/ucd/UnicodeData.txt>

Copyright Unicode, Inc.; the files retain their notices and terms-of-use links.
The Unicode data license is also reproduced in `vendor/utf8proc/LICENSE.md`.
`tests/unicode-conformance.min` requires exactly 853 grapheme vectors, 20,171
normalization vectors and 1,606 C/F default full case-fold vectors. S mappings
are alternatives to full mappings; T mappings are locale-specific Turkic rules.
Neither belongs to default full case folding.

`tools/generate-unicode-case.py` generates the 104 unconditional full-case
overrides and 163 Cased / 468 Case_Ignorable ranges used by the optional native
provider. `tests/unicode-case-conformance.min` checks both case directions for
all 41,297 scalar rows (surrogates and range pseudoentries excluded) and all
104 unconditional SpecialCasing rows. Full-string context cases independently
check Final_Sigma; locale-specific mappings are not part of default casing.

SHA-256 fingerprints:

```text
b0cf047ee94485bbdc846de2b902f5f8a815f6b674f9d04223cddadd91c9df31  GraphemeBreakTest.txt
25a50d816764b04abfb4a646d3eb2b2a803284c3873d9a06757b94fe4513dde3  NormalizationTest.txt
a004797658a457bec4dc11683e39f69249ea3b595b752dbea6721c4c9f587b0d  CaseFolding.txt
8538dea57c184f1ef3783885ea79677b10f6efa06423717157e63712f14d1ad2  SpecialCasing.txt
09c928886a178fcafd93c29e4bd59073a058e5a100b716d425cb563ab50f68c9  DerivedCoreProperties.txt
0736451de439ae7baf1425136617da495e09ee5afbe6e394374db7009ea08950  UnicodeData.txt
```
