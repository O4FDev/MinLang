# JSON numbers

JSON decimal numbers are rounded once to the nearest IEEE 754 binary64 value;
an exact halfway value chooses the even significand. The parser preserves the
original spelling in `Value.text`, including the sign of zero. Finite underflow
may round to signed zero; a result that rounds to infinity is rejected.
For example, `5e-324` is the smallest positive subnormal, `9e-324` is the next
subnormal, and `-0e9999` is negative zero. `1e9999` remains invalid.

The grammar and policy limits stay in `library/json.min`. Its private
`jsonNumber` runtime call converts the validated lexeme using integer arithmetic
in `runtime/minyar_decimal.h`. The helper also rejects malformed lexemes when
called directly. Integral lexemes of at most 18 digits skip the helper: their
digits fit an Integer exactly, so one Integer-to-Float conversion rounds once
with the same nearest-even rule. Longer integral, fractional and exponent
lexemes keep the `jsonNumber` path. The existing borrowed Text ABI remains a
precondition; this is not validation of arbitrary C pointers or forged object
lengths.

## Fixed-space exact rounding

Write the positive decimal as a coefficient times a power of ten. Ignore
leading zeroes, retain its first 800 significant digits, and record whether
any later digit is nonzero. Every discarded digit still contributes to the
decimal exponent, including discarded zeroes.

A midpoint between adjacent binary64 values is `M * 2^e`, where `M < 2^54`
and `e >= -1075`. When `e` is negative, its terminating decimal coefficient is
`M * 5^(-e)`, with at most 768 significant digits; positive exponents need
fewer. Thus every relevant midpoint lies on the finer 800-digit decimal grid.
A discarded suffix cannot cross an interior midpoint. It matters only when
the retained coefficient represents the midpoint exactly: a nonzero suffix
then rounds the magnitude up. An all-zero suffix retains the usual even tie.
The 768-digit bound and nonzero-tail technique also appear in the
[rust-lexical implementation notes](https://raw.githubusercontent.com/Alexhuszagh/rust-lexical/main/lexical-parse-float/docs/Algorithm.md).
This implementation uses a separate quotient/remainder algorithm.

## Short decimals

A lexeme whose retained coefficient has at most 19 digits (any number of
leading zeros, no discarded nonzero tail) fits one 64-bit word `d`, and its
value is `d * 10^p`. The helper first rounds it with Russ Cox's unrounded
scaling ([article](https://research.swtch.com/fp),
[proof](https://research.swtch.com/fp-proof)), shared with Float printing in
`runtime/minyar_float_scale.h`: `d` is left-justified and multiplied by a
128-bit power of ten from `runtime/minyar_pow10_table.h`, keeping the integer
part, a half bit and a sticky bit, and the result rounds to nearest even. Only
integer arithmetic is used. Results that would overflow, scales outside the
table and subnormals more than 63 bits below the significand return to the
exact path below, so infinity and every boundary keep one implementation of
their rounding. This is the same table-based approach as
[Eisel–Lemire](https://arxiv.org/abs/2101.11408), with one multiplication in
most cases.

## Exact division

The decimal magnitude is the number of significant digits plus the decimal
exponent, not the scientific exponent. Magnitudes above 309 overflow; those
below -323 round to zero. The boundary magnitudes require exact conversion.
An all-zero coefficient is handled before these cuts. Exponents saturate only
beyond the input length plus 1200, with checked integer accumulation, so a long
coefficient or fractional prefix can still cancel a large explicit exponent.

The retained coefficient becomes an exact numerator/denominator using powers
of ten. Binary exponent selection uses bit lengths followed by an exact
comparison. Scaling by a power of two makes the quotient the normal
significand, or the subnormal coefficient at exponent -1074. Compare twice
the exact remainder to the denominator, then apply even-tie and nonzero-tail
rules. Carry can produce the smallest normal value or infinity. The sign and
binary fields are assembled as bits; host locale and rounding mode do not
participate.

When the scaled numerator and denominator fit in 64 bits, ordinary unsigned
division supplies the exact quotient and remainder. Comparing the remainder
with the denominator minus the remainder avoids an overflowing doubled value.
This short-number path uses the same final rounding rules.

Each arithmetic work area has 128 limbs of 30 bits. For at most 800 retained
digits, the numerator needs at most 2658 bits and the denominator at most
3731. Scaling and doubled remainders need at most 3732; the 3840-bit storage
has a checked margin. The helper scans the entire input and uses bounded
integer work and about 2.1 KiB of arithmetic storage. It makes no allocation.
The surrounding JSON parser still allocates spelling Text and result trees.
The exact converter is the fallback for long, overflowing and deeply
subnormal lexemes; short ones take the table-based path above.

## Evidence and limits

`make check-json-numbers` generates 1,118 exact-rational oracles and compares
decoded bits, without using a host Float parser to calculate expectations.
The oracle binary-searches ordered binary64 dyadics and compares exact
midpoints; it differs from the implementation's quotient/remainder method.
Cases cover signed zero, subnormals, even/odd ties, the normal boundary,
overflow, 20,001-zero exponent cancellation and 10,000-digit suffixes. Short
coefficients of 1–19 digits cover every third decimal exponent from −345 to
309, and 64 random exact midpoints with 16–19-digit spellings test ties to
even with their neighbours one unit away. Corrupt expected
bits must fail both the C probe and the public-API harness with the expected
diagnostic.

The C probe runs at O0/O2 in four rounding modes. The public program exercises
ten JSON entry points, both `asNumber` forms, spelling preservation and the
numbers gallery at O0/O2 with ownership cleanup checks.
`check-json-numbers-sanitize` instruments the C helper/runtime with ASan/UBSan
and emitted program LLVM with ASan. The helper also compiles to LLVM and objects
for freestanding x86-64 and ARM64. The LLVM declaration check permits only
memory helpers, the ordinary runtime stop and LLVM intrinsics. This does not
claim a linked kernel or execution on those targets. This finite corpus and source proof are not a
machine-checked verification or a complete test of every IEEE 754 operation.
