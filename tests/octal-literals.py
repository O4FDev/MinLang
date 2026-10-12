#!/usr/bin/env python3
"""GUEST-1: unambiguous octal modes and signed Integer literal boundaries."""
import random
import unittest
from regressions import CompilerTestCase


class OctalLiterals(CompilerTestCase):
    def test_modes_and_signed_limits_match_python(self):
        values = [0, 1, 7, 8, 493, 1023, (1 << 63) - 1, -(1 << 63)]
        rng = random.Random(20261012)
        values += [rng.randrange(-(1 << 63), 1 << 63) for _ in range(32)]
        source = ''.join(f'print({"-" if n < 0 else ""}0o{abs(n):o})\n' for n in values)
        source += 'constant MODE: Integer = 0o755\nprint(MODE)\nprint(0.25)\nprint(0xFF)\n'
        self.executes(source, ''.join(f'{n}\n' for n in values) + '493\n0.25\n255\n')

    def test_leading_zero_decimal_integers_are_rejected(self):
        for literal in ('00', '01', '0755', '-0002', '0009223372036854775808'):
            with self.subTest(literal=literal):
                self.rejects(f'print({literal})\n', 'decimal Integer literals cannot have a leading zero; use 0o for octal')
        self.executes('print(0)\nprint(-0)\nfor i in 0..2 { print(i) }\n', '0\n0\n0\n1\n')

    def test_octal_digits_and_decimal_points_are_rejected(self):
        for literal in ('0o', '0o8', '0o9', '0o78', '0o755x', '0o7_1'):
            with self.subTest(literal=literal):
                self.rejects(f'print({literal})\n', 'an octal Integer literal needs only digits 0 through 7 after 0o')
        self.rejects('print(0o7.5)\n', 'octal literals are Integers and cannot have a decimal point')

    def test_octal_range_checked_even_in_unused_constants(self):
        for literal in ('0o1000000000000000000000', '-0o1000000000000000000001', '0o77777777777777777777777'):
            with self.subTest(literal=literal):
                self.rejects(f'constant UNUSED = {literal}\nprint(1)\n', 'Integer literal is outside the supported range')


if __name__ == '__main__': unittest.main(verbosity=2)
