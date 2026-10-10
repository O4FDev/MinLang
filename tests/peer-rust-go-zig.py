#!/usr/bin/env python3
"""Original Minyar adaptations of pinned Rust/Go/Zig audit cases.

Source keys and semantic differences are in docs/research/exhaustive/implementations.jsonl
and the validated rgz-implementation-round3.jsonl handoff in that directory.
No upstream harness or implementation code is copied.
"""
from clang_helpers import clang_command
import json
import os
import sys
import unittest
from regressions import CompilerTestCase, ROOT
from test_evidence import digest


def _rgz_ascii_byte_list(data):
    return '[' + ','.join(str(x) for x in data) + ']'


def _rgz_ascii_output(values):
    return ''.join(('true' if v is True else 'false' if v is False else str(v))+'\n' for v in values)


_RGZ_ASCII_HELPERS = r'''function isAscii(c: Integer): Boolean { return c < 128 }
function isControl(c: Integer): Boolean { return c <= 31 || c == 127 }
function isUpper(c: Integer): Boolean { return c >= 65 && c <= 90 }
function isLower(c: Integer): Boolean { return c >= 97 && c <= 122 }
function isAlphabetic(c: Integer): Boolean { return isUpper(c) || isLower(c) }
function isDigit(c: Integer): Boolean { return c >= 48 && c <= 57 }
function isAlphanumeric(c: Integer): Boolean { return isAlphabetic(c) || isDigit(c) }
function isWhitespace(c: Integer): Boolean { return c == 32 || (c >= 9 && c <= 13) }
function isHex(c: Integer): Boolean { return isDigit(c) || (c >= 65 && c <= 70) || (c >= 97 && c <= 102) }
function isPrint(c: Integer): Boolean { return isAscii(c) && !isControl(c) }
function toLower(c: Integer): Integer { if isUpper(c) { return c + 32 }; return c }
function toUpper(c: Integer): Integer { if isLower(c) { return c - 32 }; return c }
'''


_RGZ_ASCII_CASE_HELPERS = r'''record ByteSpan { values: List<Integer>; count: Integer }
function lowerString(destination: List<Integer>, source: List<Integer>): ByteSpan {
if destination.length < source.length { fail("ASCII output is shorter than input") }
let i = 0
while i < source.length { destination[i] = toLower(source[i]); i = i + 1 }
return ByteSpan { values: destination; count: source.length }
}
function upperString(destination: List<Integer>, source: List<Integer>): ByteSpan {
if destination.length < source.length { fail("ASCII output is shorter than input") }
let i = 0
while i < source.length { destination[i] = toUpper(source[i]); i = i + 1 }
return ByteSpan { values: destination; count: source.length }
}
function allocLowerString(source: List<Integer>): ByteSpan {
let destination: List<Integer> = []; let i = 0
while i < source.length { destination.add(0); i = i + 1 }
return lowerString(destination,source)
}
function allocUpperString(source: List<Integer>): ByteSpan {
let destination: List<Integer> = []; let i = 0
while i < source.length { destination.add(0); i = i + 1 }
return upperString(destination,source)
}
function observe(span: ByteSpan) {
print(span.values.length); print(span.count); let i = 0
while i < span.count { print(span.values[i]); i = i + 1 }
}
'''


_RGZ_ASCII_COMPARE_HELPERS = r'''function equalRange(a: List<Integer>, offset: Integer, b: List<Integer>): Boolean {
let i = 0
while i < b.length { if toLower(a[offset + i]) != toLower(b[i]) { return false }; i = i + 1 }
return true
}
function eqlIgnoreCase(a: List<Integer>, b: List<Integer>): Boolean {
if a.length != b.length { return false }; return equalRange(a,0,b)
}
function startsWithIgnoreCase(a: List<Integer>, b: List<Integer>): Boolean {
if b.length > a.length { return false }; return equalRange(a,0,b)
}
function endsWithIgnoreCase(a: List<Integer>, b: List<Integer>): Boolean {
if b.length > a.length { return false }; return equalRange(a,a.length-b.length,b)
}
'''


_RGZ_ASCII_SEARCH_HELPERS = r'''function preprocess(pattern: List<Integer>, table: List<Integer>) {
let i = 0
while i < table.length { table[i] = pattern.length; i = i + 1 }
i = 0
while i < pattern.length - 1 { table[toLower(pattern[i])] = pattern.length - 1 - i; i = i + 1 }
}
function indexLinear(haystack: List<Integer>, start: Integer, needle: List<Integer>): Integer {
let i = start; let end = haystack.length - needle.length
while i <= end { if equalRange(haystack,i,needle) { return i }; i = i + 1 }
return -1
}
function indexPos(haystack: List<Integer>, start: Integer, needle: List<Integer>, paths: List<Integer>): Integer {
if needle.length > haystack.length { return -1 }
if needle.length == 0 { return start }
if haystack.length < 52 || needle.length <= 4 {
paths[0] = paths[0] + 1; return indexLinear(haystack,start,needle)
}
paths[1] = paths[1] + 1
let table: List<Integer> = []; let j = 0
while j < 256 { table.add(0); j = j + 1 }
preprocess(needle,table)
j = 0
while j < 256 { print(table[j]); j = j + 1 }
let i = start
while i <= haystack.length - needle.length {
if equalRange(haystack,i,needle) { return i }
i = i + table[toLower(haystack[i + needle.length - 1])]
}
return -1
}
function indexOfIgnoreCase(haystack: List<Integer>, needle: List<Integer>, paths: List<Integer>): Integer {
return indexPos(haystack,0,needle,paths)
}
'''


_RGZ_ASCII_ESCAPE_HELPERS = r'''function hexEscape(bytes: List<Integer>, upper: Boolean): Text {
let charset = "0123456789abcdef"
if upper { charset = "0123456789ABCDEF" }
let result = ""; let i = 0
while i < bytes.length {
let c = bytes[i]
if isPrint(c) {
let printable = " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"
result = result + Text(printable[c-32])
} else {
result = result + "\\x" + Text(charset[c / 16]) + Text(charset[c % 16])
}
i = i + 1
}
return result
}
'''


_RGZ_ASCII_CLASS_CASES = [('isControl', 97, False), ('isControl', 122, False), ('isControl', 32, False), ('isControl', 0, True), ('isControl', 12, True), ('isControl', 31, True), ('isControl', 127, True), ('isControl', 128, False), ('isControl', 255, False), ('toUpper', 99, 67), ('toUpper', 58, 58), ('toUpper', 171, 171), ('isUpper', 122, False), ('isUpper', 128, False), ('isUpper', 255, False), ('toLower', 67, 99), ('toLower', 58, 58), ('toLower', 171, 171), ('isLower', 90, False), ('isLower', 128, False), ('isLower', 255, False), ('isAlphanumeric', 90, True), ('isAlphanumeric', 122, True), ('isAlphanumeric', 53, True), ('isAlphanumeric', 97, True), ('isAlphanumeric', 33, False), ('isAlphanumeric', 128, False), ('isAlphanumeric', 255, False), ('isAlphabetic', 53, False), ('isAlphabetic', 99, True), ('isAlphabetic', 64, False), ('isAlphabetic', 90, True), ('isAlphabetic', 128, False), ('isAlphabetic', 255, False), ('isWhitespace', 32, True), ('isWhitespace', 9, True), ('isWhitespace', 13, True), ('isWhitespace', 10, True), ('isWhitespace', 12, True), ('isWhitespace', 46, False), ('isWhitespace', 31, False), ('isWhitespace', 128, False), ('isWhitespace', 255, False), ('isHex', 103, False), ('isHex', 98, True), ('isHex', 70, True), ('isHex', 57, True), ('isHex', 128, False), ('isHex', 255, False), ('isDigit', 126, False), ('isDigit', 48, True), ('isDigit', 57, True), ('isDigit', 128, False), ('isDigit', 255, False), ('isPrint', 32, True), ('isPrint', 64, True), ('isPrint', 126, True), ('isPrint', 27, False), ('isPrint', 128, False), ('isPrint', 255, False)]


_RGZ_ASCII_COMPARISON_CASES = [{'function': 'eqlIgnoreCase', 'left_utf8_hex': '48456cf09f92a94c6f21', 'right_utf8_hex': '68656cf09f92a96c6f21', 'expected': True}, {'function': 'eqlIgnoreCase', 'left_utf8_hex': '68456c4c6f21', 'right_utf8_hex': '68656c6c6f2120', 'expected': False}, {'function': 'eqlIgnoreCase', 'left_utf8_hex': '68456c4c6f21', 'right_utf8_hex': '68656c726f21', 'expected': False}, {'function': 'startsWithIgnoreCase', 'left_utf8_hex': '626f42', 'right_utf8_hex': '426f', 'expected': True}, {'function': 'startsWithIgnoreCase', 'left_utf8_hex': '4e6565646c6520696e20684179537441634b', 'right_utf8_hex': '686179737461636b', 'expected': False}, {'function': 'endsWithIgnoreCase', 'left_utf8_hex': '4e6565646c6520696e20486159735461436b', 'right_utf8_hex': '686179737461636b', 'expected': True}, {'function': 'endsWithIgnoreCase', 'left_utf8_hex': '426f42', 'right_utf8_hex': '426f', 'expected': False}]


_RGZ_ASCII_SEARCH_CASES = [{'haystack_utf8_hex': '6f6e652054776f20546872656520466f7572', 'needle_utf8_hex': '666f5572', 'start': 0, 'expected_index': 14, 'minyar_index': 14, 'algorithm': 'linear-or-length-guard'}, {'haystack_utf8_hex': '6f6e652074776f20746872656520466f7552', 'needle_utf8_hex': '674f7572', 'start': 0, 'expected_index': None, 'minyar_index': -1, 'algorithm': 'linear-or-length-guard'}, {'haystack_utf8_hex': '666f4f', 'needle_utf8_hex': '466f6f', 'start': 0, 'expected_index': 0, 'minyar_index': 0, 'algorithm': 'linear-or-length-guard'}, {'haystack_utf8_hex': '666f6f', 'needle_utf8_hex': '666f6f6c', 'start': 0, 'expected_index': None, 'minyar_index': -1, 'algorithm': 'linear-or-length-guard'}, {'haystack_utf8_hex': '464f4f20666f6f', 'needle_utf8_hex': '664f6f', 'start': 0, 'expected_index': 0, 'minyar_index': 0, 'algorithm': 'linear-or-length-guard'}, {'haystack_utf8_hex': '6f6e652074776f20746872656520666f757220666976652073697820736576656e206569676874206e696e652074656e20656c6576656e', 'needle_utf8_hex': '546852654520664f5572', 'start': 0, 'expected_index': 8, 'minyar_index': 8, 'algorithm': 'boyer-moore-horspool'}, {'haystack_utf8_hex': '6f6e652074776f20746872656520666f757220666976652073697820736576656e206569676874206e696e652074656e20656c6576656e', 'needle_utf8_hex': '54776f2074576f', 'start': 0, 'expected_index': None, 'minyar_index': -1, 'algorithm': 'boyer-moore-horspool'}]


_RGZ_ASCII_ESCAPE_CASES = [{'input_hex': '61626320313233', 'case': 'lower', 'expected_hex': '61626320313233', 'format': '{f}'}, {'input_hex': '6162ff63', 'case': 'lower', 'expected_hex': '61625c78666663', 'format': '{f}'}, {'input_hex': '61626320313233', 'case': 'upper', 'expected_hex': '61626320313233', 'format': '{f}'}, {'input_hex': '6162ff63', 'case': 'upper', 'expected_hex': '61625c78464663', 'format': '{f}'}]


def _rgz_for_output(values):
    return ''.join(('true' if v is True else 'false' if v is False else str(v)) + '\n' for v in values)


def _rgz_unicode_output(values):
    return ''.join(str(value)+'\n' for value in values)


_RGZ_UNICODE_CASES = [{'case_id': 'encode-operation/line552', 'group': 'utf8-encode-reused-prefix', 'oracle': {'input_utf8_hex': 'e282ac', 'scalar': 8364, 'length': 3, 'asserted_prefix_bytes': [226, 130, 172], 'ordered_operation': 0, 'shared_buffer_length': 4}}, {'case_id': 'encode-operation/line557', 'group': 'utf8-encode-reused-prefix', 'oracle': {'input_utf8_hex': '24', 'scalar': 36, 'length': 1, 'asserted_prefix_bytes': [36], 'ordered_operation': 1, 'shared_buffer_length': 4}}, {'case_id': 'encode-operation/line560', 'group': 'utf8-encode-reused-prefix', 'oracle': {'input_utf8_hex': 'c2a2', 'scalar': 162, 'length': 2, 'asserted_prefix_bytes': [194, 162], 'ordered_operation': 2, 'shared_buffer_length': 4}}, {'case_id': 'encode-operation/line564', 'group': 'utf8-encode-reused-prefix', 'oracle': {'input_utf8_hex': 'f0908d88', 'scalar': 66376, 'length': 4, 'asserted_prefix_bytes': [240, 144, 141, 136], 'ordered_operation': 3, 'shared_buffer_length': 4}}, {'case_id': 'source-case/line584', 'group': 'utf8-invalid-scalar-encoding', 'oracle': {'scalar': 55296, 'source_error': 'Utf8CannotEncodeSurrogateHalf', 'buffer_capacity': 4}}, {'case_id': 'source-case/line585', 'group': 'utf8-invalid-scalar-encoding', 'oracle': {'scalar': 57343, 'source_error': 'Utf8CannotEncodeSurrogateHalf', 'buffer_capacity': 4}}, {'case_id': 'source-case/line586', 'group': 'utf8-invalid-scalar-encoding', 'oracle': {'scalar': 1114112, 'source_error': 'CodepointTooLarge', 'buffer_capacity': 4}}, {'case_id': 'source-case/line587', 'group': 'utf8-invalid-scalar-encoding', 'oracle': {'scalar': 2097151, 'source_error': 'CodepointTooLarge', 'buffer_capacity': 4}}, {'case_id': 'iterator-sequence/line601', 'group': 'utf8-independent-iterators', 'oracle': {'input_utf8_hex': '616263', 'slice_utf8_hex': ['61', '62', '63'], 'scalars': [97, 98, 99], 'slice_terminal': 'absent', 'scalar_terminal': 'absent', 'independent_initial_cursors': [0, 0]}}, {'case_id': 'iterator-sequence/line631', 'group': 'utf8-independent-iterators', 'oracle': {'input_utf8_hex': 'e69db1e4baace5b882', 'slice_utf8_hex': ['e69db1', 'e4baac', 'e5b882'], 'scalars': [26481, 20140, 24066], 'slice_terminal': 'absent', 'scalar_terminal': 'absent', 'independent_initial_cursors': [0, 0]}}, {'case_id': 'source-case/line621', 'group': 'utf8-invalid-validation', 'oracle': {'input_hex': '68656cad6c6f', 'source_error': 'InvalidUtf8'}}, {'case_id': 'source-case/line656', 'group': 'utf8-valid-validation', 'oracle': {'input_hex': '616263', 'expected_valid': True, 'source_function': 'utf8ValidateSlice', 'scalars': [97, 98, 99]}}, {'case_id': 'source-case/line657', 'group': 'utf8-valid-validation', 'oracle': {'input_hex': '616263dfbf', 'expected_valid': True, 'source_function': 'utf8ValidateSlice', 'scalars': [97, 98, 99, 2047]}}, {'case_id': 'source-case/line658', 'group': 'utf8-valid-validation', 'oracle': {'input_hex': '', 'expected_valid': True, 'source_function': 'utf8ValidateSlice', 'scalars': []}}, {'case_id': 'source-case/line659', 'group': 'utf8-valid-validation', 'oracle': {'input_hex': '61', 'expected_valid': True, 'source_function': 'utf8ValidateSlice', 'scalars': [97]}}, {'case_id': 'source-case/line660', 'group': 'utf8-valid-validation', 'oracle': {'input_hex': '616263', 'expected_valid': True, 'source_function': 'utf8ValidateSlice', 'scalars': [97, 98, 99]}}, {'case_id': 'source-case/line661', 'group': 'utf8-valid-validation', 'oracle': {'input_hex': 'd096', 'expected_valid': True, 'source_function': 'utf8ValidateSlice', 'scalars': [1046]}}, {'case_id': 'source-case/line662', 'group': 'utf8-valid-validation', 'oracle': {'input_hex': 'd096d096', 'expected_valid': True, 'source_function': 'utf8ValidateSlice', 'scalars': [1046, 1046]}}, {'case_id': 'source-case/line663', 'group': 'utf8-valid-validation', 'oracle': {'input_hex': 'd0b1d180d18dd0b42dd09bd093d0a2d09c', 'expected_valid': True, 'source_function': 'utf8ValidateSlice', 'scalars': [1073, 1088, 1101, 1076, 45, 1051, 1043, 1058, 1052]}}, {'case_id': 'source-case/line664', 'group': 'utf8-valid-validation', 'oracle': {'input_hex': 'e298bae298bbe298b9', 'expected_valid': True, 'source_function': 'utf8ValidateSlice', 'scalars': [9786, 9787, 9785]}}, {'case_id': 'source-case/line665', 'group': 'utf8-valid-validation', 'oracle': {'input_hex': '61f3bfbf9b', 'expected_valid': True, 'source_function': 'utf8ValidateSlice', 'scalars': [97, 1048539]}}, {'case_id': 'source-case/line666', 'group': 'utf8-valid-validation', 'oracle': {'input_hex': 'f48fbfbf', 'expected_valid': True, 'source_function': 'utf8ValidateSlice', 'scalars': [1114111]}}, {'case_id': 'source-case/line667', 'group': 'utf8-valid-validation', 'oracle': {'input_hex': '616263dfbf', 'expected_valid': True, 'source_function': 'utf8ValidateSlice', 'scalars': [97, 98, 99, 2047]}}, {'case_id': 'source-case/line669', 'group': 'utf8-invalid-validation', 'oracle': {'input_hex': '616263c0', 'expected_valid': False, 'source_function': 'utf8ValidateSlice'}}, {'case_id': 'source-case/line670', 'group': 'utf8-invalid-validation', 'oracle': {'input_hex': '616263c0616263', 'expected_valid': False, 'source_function': 'utf8ValidateSlice'}}, {'case_id': 'source-case/line671', 'group': 'utf8-invalid-validation', 'oracle': {'input_hex': '6161e2', 'expected_valid': False, 'source_function': 'utf8ValidateSlice'}}, {'case_id': 'source-case/line672', 'group': 'utf8-invalid-validation', 'oracle': {'input_hex': '42fa', 'expected_valid': False, 'source_function': 'utf8ValidateSlice'}}, {'case_id': 'source-case/line673', 'group': 'utf8-invalid-validation', 'oracle': {'input_hex': '42fa43', 'expected_valid': False, 'source_function': 'utf8ValidateSlice'}}, {'case_id': 'source-case/line674', 'group': 'utf8-invalid-validation', 'oracle': {'input_hex': '616263c0', 'expected_valid': False, 'source_function': 'utf8ValidateSlice'}}, {'case_id': 'source-case/line675', 'group': 'utf8-invalid-validation', 'oracle': {'input_hex': '616263c0616263', 'expected_valid': False, 'source_function': 'utf8ValidateSlice'}}, {'case_id': 'source-case/line676', 'group': 'utf8-invalid-validation', 'oracle': {'input_hex': 'f4908080', 'expected_valid': False, 'source_function': 'utf8ValidateSlice'}}, {'case_id': 'source-case/line677', 'group': 'utf8-invalid-validation', 'oracle': {'input_hex': 'f7bfbfbf', 'expected_valid': False, 'source_function': 'utf8ValidateSlice'}}, {'case_id': 'source-case/line678', 'group': 'utf8-invalid-validation', 'oracle': {'input_hex': 'fbbfbfbfbf', 'expected_valid': False, 'source_function': 'utf8ValidateSlice'}}, {'case_id': 'source-case/line679', 'group': 'utf8-invalid-validation', 'oracle': {'input_hex': 'c080', 'expected_valid': False, 'source_function': 'utf8ValidateSlice'}}, {'case_id': 'source-case/line680', 'group': 'utf8-invalid-validation', 'oracle': {'input_hex': 'eda080', 'expected_valid': False, 'source_function': 'utf8ValidateSlice'}}, {'case_id': 'source-case/line681', 'group': 'utf8-invalid-validation', 'oracle': {'input_hex': 'edbfbf', 'expected_valid': False, 'source_function': 'utf8ValidateSlice'}}, {'case_id': 'source-case/line1646', 'group': 'utf8-valid-validation', 'oracle': {'input_hex': '616263', 'expected_valid': True, 'source_function': 'wtf8ValidateSlice', 'scalars': [97, 98, 99]}}, {'case_id': 'source-case/line1647', 'group': 'utf8-valid-validation', 'oracle': {'input_hex': '616263dfbf', 'expected_valid': True, 'source_function': 'wtf8ValidateSlice', 'scalars': [97, 98, 99, 2047]}}, {'case_id': 'source-case/line1648', 'group': 'utf8-valid-validation', 'oracle': {'input_hex': '', 'expected_valid': True, 'source_function': 'wtf8ValidateSlice', 'scalars': []}}, {'case_id': 'source-case/line1649', 'group': 'utf8-valid-validation', 'oracle': {'input_hex': '61', 'expected_valid': True, 'source_function': 'wtf8ValidateSlice', 'scalars': [97]}}, {'case_id': 'source-case/line1650', 'group': 'utf8-valid-validation', 'oracle': {'input_hex': '616263', 'expected_valid': True, 'source_function': 'wtf8ValidateSlice', 'scalars': [97, 98, 99]}}, {'case_id': 'source-case/line1651', 'group': 'utf8-valid-validation', 'oracle': {'input_hex': 'd096', 'expected_valid': True, 'source_function': 'wtf8ValidateSlice', 'scalars': [1046]}}, {'case_id': 'source-case/line1652', 'group': 'utf8-valid-validation', 'oracle': {'input_hex': 'd096d096', 'expected_valid': True, 'source_function': 'wtf8ValidateSlice', 'scalars': [1046, 1046]}}, {'case_id': 'source-case/line1653', 'group': 'utf8-valid-validation', 'oracle': {'input_hex': 'd0b1d180d18dd0b42dd09bd093d0a2d09c', 'expected_valid': True, 'source_function': 'wtf8ValidateSlice', 'scalars': [1073, 1088, 1101, 1076, 45, 1051, 1043, 1058, 1052]}}, {'case_id': 'source-case/line1654', 'group': 'utf8-valid-validation', 'oracle': {'input_hex': 'e298bae298bbe298b9', 'expected_valid': True, 'source_function': 'wtf8ValidateSlice', 'scalars': [9786, 9787, 9785]}}, {'case_id': 'source-case/line1655', 'group': 'utf8-valid-validation', 'oracle': {'input_hex': '61f3bfbf9b', 'expected_valid': True, 'source_function': 'wtf8ValidateSlice', 'scalars': [97, 1048539]}}, {'case_id': 'source-case/line1656', 'group': 'utf8-valid-validation', 'oracle': {'input_hex': 'f48fbfbf', 'expected_valid': True, 'source_function': 'wtf8ValidateSlice', 'scalars': [1114111]}}, {'case_id': 'source-case/line1657', 'group': 'utf8-valid-validation', 'oracle': {'input_hex': '616263dfbf', 'expected_valid': True, 'source_function': 'wtf8ValidateSlice', 'scalars': [97, 98, 99, 2047]}}, {'case_id': 'source-case/line1659', 'group': 'utf8-invalid-validation', 'oracle': {'input_hex': '616263c0', 'expected_valid': False, 'source_function': 'wtf8ValidateSlice'}}, {'case_id': 'source-case/line1660', 'group': 'utf8-invalid-validation', 'oracle': {'input_hex': '616263c0616263', 'expected_valid': False, 'source_function': 'wtf8ValidateSlice'}}, {'case_id': 'source-case/line1661', 'group': 'utf8-invalid-validation', 'oracle': {'input_hex': '6161e2', 'expected_valid': False, 'source_function': 'wtf8ValidateSlice'}}, {'case_id': 'source-case/line1662', 'group': 'utf8-invalid-validation', 'oracle': {'input_hex': '42fa', 'expected_valid': False, 'source_function': 'wtf8ValidateSlice'}}, {'case_id': 'source-case/line1663', 'group': 'utf8-invalid-validation', 'oracle': {'input_hex': '42fa43', 'expected_valid': False, 'source_function': 'wtf8ValidateSlice'}}, {'case_id': 'source-case/line1664', 'group': 'utf8-invalid-validation', 'oracle': {'input_hex': '616263c0', 'expected_valid': False, 'source_function': 'wtf8ValidateSlice'}}, {'case_id': 'source-case/line1665', 'group': 'utf8-invalid-validation', 'oracle': {'input_hex': '616263c0616263', 'expected_valid': False, 'source_function': 'wtf8ValidateSlice'}}, {'case_id': 'source-case/line1666', 'group': 'utf8-invalid-validation', 'oracle': {'input_hex': 'f4908080', 'expected_valid': False, 'source_function': 'wtf8ValidateSlice'}}, {'case_id': 'source-case/line1667', 'group': 'utf8-invalid-validation', 'oracle': {'input_hex': 'f7bfbfbf', 'expected_valid': False, 'source_function': 'wtf8ValidateSlice'}}, {'case_id': 'source-case/line1668', 'group': 'utf8-invalid-validation', 'oracle': {'input_hex': 'fbbfbfbfbf', 'expected_valid': False, 'source_function': 'wtf8ValidateSlice'}}, {'case_id': 'source-case/line1669', 'group': 'utf8-invalid-validation', 'oracle': {'input_hex': 'c080', 'expected_valid': False, 'source_function': 'wtf8ValidateSlice'}}, {'case_id': 'source-case/line689', 'group': 'utf8-single-scalar-decoding', 'oracle': {'input_hex': '00', 'scalar': 0}}, {'case_id': 'source-case/line690', 'group': 'utf8-single-scalar-decoding', 'oracle': {'input_hex': '20', 'scalar': 32}}, {'case_id': 'source-case/line691', 'group': 'utf8-single-scalar-decoding', 'oracle': {'input_hex': '7f', 'scalar': 127}}, {'case_id': 'source-case/line692', 'group': 'utf8-single-scalar-decoding', 'oracle': {'input_hex': 'c280', 'scalar': 128}}, {'case_id': 'source-case/line693', 'group': 'utf8-single-scalar-decoding', 'oracle': {'input_hex': 'dfbf', 'scalar': 2047}}, {'case_id': 'source-case/line694', 'group': 'utf8-single-scalar-decoding', 'oracle': {'input_hex': 'e0a080', 'scalar': 2048}}, {'case_id': 'source-case/line695', 'group': 'utf8-single-scalar-decoding', 'oracle': {'input_hex': 'e18080', 'scalar': 4096}}, {'case_id': 'source-case/line696', 'group': 'utf8-single-scalar-decoding', 'oracle': {'input_hex': 'efbfbf', 'scalar': 65535}}, {'case_id': 'source-case/line697', 'group': 'utf8-single-scalar-decoding', 'oracle': {'input_hex': 'f0908080', 'scalar': 65536}}, {'case_id': 'source-case/line698', 'group': 'utf8-single-scalar-decoding', 'oracle': {'input_hex': 'f1808080', 'scalar': 262144}}, {'case_id': 'source-case/line699', 'group': 'utf8-single-scalar-decoding', 'oracle': {'input_hex': 'f3bfbfbf', 'scalar': 1048575}}, {'case_id': 'source-case/line700', 'group': 'utf8-single-scalar-decoding', 'oracle': {'input_hex': 'f48fbfbf', 'scalar': 1114111}}, {'case_id': 'source-case/line709', 'group': 'utf8-invalid-decoding', 'oracle': {'input_hex': '80', 'source_error': 'Utf8InvalidStartByte'}}, {'case_id': 'source-case/line710', 'group': 'utf8-invalid-decoding', 'oracle': {'input_hex': 'bf', 'source_error': 'Utf8InvalidStartByte'}}, {'case_id': 'source-case/line712', 'group': 'utf8-invalid-decoding', 'oracle': {'input_hex': 'f8', 'source_error': 'Utf8InvalidStartByte'}}, {'case_id': 'source-case/line713', 'group': 'utf8-invalid-decoding', 'oracle': {'input_hex': 'ff', 'source_error': 'Utf8InvalidStartByte'}}, {'case_id': 'source-case/line715', 'group': 'utf8-invalid-decoding', 'oracle': {'input_hex': 'c2', 'source_error': 'UnexpectedEof'}}, {'case_id': 'source-case/line716', 'group': 'utf8-invalid-decoding', 'oracle': {'input_hex': 'c200', 'source_error': 'Utf8ExpectedContinuation'}}, {'case_id': 'source-case/line717', 'group': 'utf8-invalid-decoding', 'oracle': {'input_hex': 'c2c0', 'source_error': 'Utf8ExpectedContinuation'}}, {'case_id': 'source-case/line719', 'group': 'utf8-invalid-decoding', 'oracle': {'input_hex': 'e0', 'source_error': 'UnexpectedEof'}}, {'case_id': 'source-case/line720', 'group': 'utf8-invalid-decoding', 'oracle': {'input_hex': 'e000', 'source_error': 'UnexpectedEof'}}, {'case_id': 'source-case/line721', 'group': 'utf8-invalid-decoding', 'oracle': {'input_hex': 'e0c0', 'source_error': 'UnexpectedEof'}}, {'case_id': 'source-case/line722', 'group': 'utf8-invalid-decoding', 'oracle': {'input_hex': 'e0a0', 'source_error': 'UnexpectedEof'}}, {'case_id': 'source-case/line723', 'group': 'utf8-invalid-decoding', 'oracle': {'input_hex': 'e0a000', 'source_error': 'Utf8ExpectedContinuation'}}, {'case_id': 'source-case/line724', 'group': 'utf8-invalid-decoding', 'oracle': {'input_hex': 'e0a0c0', 'source_error': 'Utf8ExpectedContinuation'}}, {'case_id': 'source-case/line726', 'group': 'utf8-invalid-decoding', 'oracle': {'input_hex': 'f0', 'source_error': 'UnexpectedEof'}}, {'case_id': 'source-case/line727', 'group': 'utf8-invalid-decoding', 'oracle': {'input_hex': 'f000', 'source_error': 'UnexpectedEof'}}, {'case_id': 'source-case/line728', 'group': 'utf8-invalid-decoding', 'oracle': {'input_hex': 'f0c0', 'source_error': 'UnexpectedEof'}}, {'case_id': 'source-case/line729', 'group': 'utf8-invalid-decoding', 'oracle': {'input_hex': 'f09000', 'source_error': 'UnexpectedEof'}}, {'case_id': 'source-case/line730', 'group': 'utf8-invalid-decoding', 'oracle': {'input_hex': 'f090c0', 'source_error': 'UnexpectedEof'}}, {'case_id': 'source-case/line731', 'group': 'utf8-invalid-decoding', 'oracle': {'input_hex': 'f0908000', 'source_error': 'Utf8ExpectedContinuation'}}, {'case_id': 'source-case/line732', 'group': 'utf8-invalid-decoding', 'oracle': {'input_hex': 'f09080c0', 'source_error': 'Utf8ExpectedContinuation'}}, {'case_id': 'source-case/line740', 'group': 'utf8-invalid-decoding', 'oracle': {'input_hex': 'c080', 'source_error': 'Utf8OverlongEncoding'}}, {'case_id': 'source-case/line741', 'group': 'utf8-invalid-decoding', 'oracle': {'input_hex': 'c1bf', 'source_error': 'Utf8OverlongEncoding'}}, {'case_id': 'source-case/line742', 'group': 'utf8-invalid-decoding', 'oracle': {'input_hex': 'e08080', 'source_error': 'Utf8OverlongEncoding'}}, {'case_id': 'source-case/line743', 'group': 'utf8-invalid-decoding', 'oracle': {'input_hex': 'e09fbf', 'source_error': 'Utf8OverlongEncoding'}}, {'case_id': 'source-case/line744', 'group': 'utf8-invalid-decoding', 'oracle': {'input_hex': 'f0808080', 'source_error': 'Utf8OverlongEncoding'}}, {'case_id': 'source-case/line745', 'group': 'utf8-invalid-decoding', 'oracle': {'input_hex': 'f08fbfbf', 'source_error': 'Utf8OverlongEncoding'}}, {'case_id': 'source-case/line754', 'group': 'utf8-invalid-decoding', 'oracle': {'input_hex': 'f4908080', 'source_error': 'Utf8CodepointTooLarge'}}, {'case_id': 'source-case/line755', 'group': 'utf8-invalid-decoding', 'oracle': {'input_hex': 'f7bfbfbf', 'source_error': 'Utf8CodepointTooLarge'}}, {'case_id': 'source-case/line757', 'group': 'utf8-single-scalar-decoding', 'oracle': {'input_hex': 'ed9fbf', 'scalar': 55295}}, {'case_id': 'source-case/line758', 'group': 'utf8-invalid-decoding', 'oracle': {'input_hex': 'eda080', 'source_error': 'Utf8EncodesSurrogateHalf'}}, {'case_id': 'source-case/line759', 'group': 'utf8-invalid-decoding', 'oracle': {'input_hex': 'edbfbf', 'source_error': 'Utf8EncodesSurrogateHalf'}}, {'case_id': 'source-case/line760', 'group': 'utf8-single-scalar-decoding', 'oracle': {'input_hex': 'ee8080', 'scalar': 57344}}, {'case_id': 'iterator-peek-sequence/line772', 'group': 'utf8-peek-restores-cursor', 'oracle': {'input_utf8_hex': '6e6fc3ab6c', 'ordered_operations': [['next', 'n'], ['peek', 1, 'o'], ['peek', 2, 'oë'], ['peek', 3, 'oël'], ['peek', 4, 'oël'], ['peek', 10, 'oël'], ['next', 'o'], ['next', 'ë'], ['next', 'l'], ['next', None], ['peek', 1, '']]}}, {'case_id': 'source-case/line1567', 'group': 'utf8-codepoint-count', 'oracle': {'input_hex': '6162636465666768696a', 'character_count': 10}}, {'case_id': 'source-case/line1568', 'group': 'utf8-codepoint-count', 'oracle': {'input_hex': 'c3a4c3a5c3a9c3abc3bec3bcc3bac3adc3b3c3b6', 'character_count': 10}}, {'case_id': 'source-case/line1569', 'group': 'utf8-codepoint-count', 'oracle': {'input_hex': 'e38193e38293e381abe381a1e381af', 'character_count': 5}}, {'case_id': 'source-case/line1579', 'group': 'utf8-scalar-validity', 'oracle': {'scalar': 101, 'expected_valid': True, 'encoded_hex': '65'}}, {'case_id': 'source-case/line1580', 'group': 'utf8-scalar-validity', 'oracle': {'scalar': 235, 'expected_valid': True, 'encoded_hex': 'c3ab'}}, {'case_id': 'source-case/line1581', 'group': 'utf8-scalar-validity', 'oracle': {'scalar': 12399, 'expected_valid': True, 'encoded_hex': 'e381af'}}, {'case_id': 'source-case/line1582', 'group': 'utf8-scalar-validity', 'oracle': {'scalar': 57344, 'expected_valid': True, 'encoded_hex': 'ee8080'}}, {'case_id': 'source-case/line1583', 'group': 'utf8-scalar-validity', 'oracle': {'scalar': 1114111, 'expected_valid': True, 'encoded_hex': 'f48fbfbf'}}, {'case_id': 'source-case/line1584', 'group': 'utf8-scalar-validity', 'oracle': {'scalar': 55296, 'expected_valid': False}}, {'case_id': 'source-case/line1585', 'group': 'utf8-scalar-validity', 'oracle': {'scalar': 57343, 'expected_valid': False}}, {'case_id': 'source-case/line1586', 'group': 'utf8-scalar-validity', 'oracle': {'scalar': 1114112, 'expected_valid': False}}]


class PeerRustGoZig(CompilerTestCase):
    def executes(self, source, expected, status=0, stderr='', arguments=()):
        variants = ('-O0', '-O2', '-O3', '-Os') if os.environ.get('MINYAR_TEST_EXTENDED_OPT') == '1' else ('-O0', '-O2')
        return super().executes(source, expected, status, stderr, optimizations=variants, arguments=arguments)

    def test_conditional_results_and_unreached_failure_branches(self):
        # Each helper preserves the source branch tree; explicit returns replace
        # Rust's value-producing if expressions. Oracles are the twelve explicit
        # upstream assertions, not results calculated by the Minyar program.
        self.executes('''function first(): Boolean { if true { return true } else { return false } }
function second(): Boolean { if false { return false } else { return true } }
function third(): Boolean { if true { return true } else { if true { return false } else { return false } } }
function fourth(): Boolean { if false { return false } else { if true { return true } else { return false } } }
function fifth(): Boolean { if false { return false } else { if false { return false } else { return true } } }
function inferred(): Boolean { let result = true; if true { result = true } else { result = false }; return result }
function innerFalse(): Boolean { if false { return false } else { return true } }
function innerTrue(): Boolean { if true { return false } else { return true } }
function nestedConditionOne(): Boolean { if innerFalse() { return true } else { return false } }
function nestedConditionTwo(): Boolean { if innerTrue() { return false } else { return true } }
function nestedBranch(): Boolean { if true { if false { return false } else { return true } } else { return false } }
function panicThen(): Integer { if false { fail("explicit panic") } else { return 10 } }
function panicElse(): Integer { if true { return 10 } else { fail("explicit panic") } }
function panicElseIf(): Integer { if false { return 0 } else { if false { fail("explicit panic") } else { return 10 } } }
print(first()); print(second()); print(third()); print(fourth()); print(fifth()); print(inferred())
print(nestedConditionOne()); print(nestedConditionTwo()); print(nestedBranch())
print(panicThen()); print(panicElse()); print(panicElseIf())
''', 'true\n' * 9 + '10\n' * 3)

    def test_recursive_even_condition_success(self):
        self.executes('''function even(x: Integer): Boolean {
if x < 2 { return false } else { if x == 2 { return true } else { return even(x - 2) } }
}
function foo(x: Integer) { if even(x) { print(x) } else { fail("explicit panic") } }
foo(2)
''', '2\n')

    def test_fatal_conditional_calls_preserve_terminal_effects(self):
        cases = [
            ('''function f(): Integer { fail("explicit panic") }
function g(): Integer { if true { return f() } else { return 10 } }
g()
''', '', 'explicit panic'),
            ('''if false { print(0) } else { if true { fail("explicit panic") } else { print(10) } }
''', '', 'explicit panic'),
            ('''function even(x: Integer): Boolean {
if x < 2 { return false } else { if x == 2 { return true } else { return even(x - 2) } }
}
function foo(x: Integer) { if even(x) { print(x) } else { fail("Number is odd") } }
foo(3)
''', '', 'Number is odd'),
            ('''function myError(s: Text): Boolean { print(s); fail("quux") }
if myError("b" + "ye") { print("unreachable") }
''', 'bye\n', 'quux'),
        ]
        for source, stdout, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic, source=source):
                self.executes(source, stdout, status=1, stderr=f'Minyar stopped: {diagnostic}\n')

    def test_partial_integer_return_is_rejected(self):
        result, llvm = self.compile('''function foo(bar: Integer): Integer {
if bar % 5 == 0 { return 3 }
}
print(foo(1))
''')
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (1, '', "Minyar stopped: function 'foo' must return a value on every path\n"))
        self.assertFalse(llvm.exists())

    def test_append_scalar_tables_keep_all_elements(self):
        # These explicit inputs/expected lists were transcribed from append.go.
        # Width-only Go integer variants share Integer here; no narrowing claim.
        numeric = [([], [], []), ([], [0], [0]), ([], [0, 1, 2, 3], [0, 1, 2, 3]),
                   ([0, 1, 2], [], [0, 1, 2]), ([0, 1, 2], [3], [0, 1, 2, 3]),
                   ([0, 1, 2], [3, 4, 5], [0, 1, 2, 3, 4, 5]),
                   ([], [0], [0]), ([], [0, 1, 2, 3], [0, 1, 2, 3]),
                   ([0, 1, 2], [3], [0, 1, 2, 3]), ([0, 1, 2], [3, 4, 5], [0, 1, 2, 3, 4, 5])]
        boolean = [([], [], []), ([], [True], [True]), ([], [True, False, True, True], [True, False, True, True]),
                   ([True, False, True], [], [True, False, True]),
                   ([True, False, True], [False], [True, False, True, False]),
                   ([True, False, True], [False, False, False], [True, False, True, False, False, False]),
                   ([], [True], [True]), ([], [True, False, True, False], [True, False, True, False]),
                   ([True, False, True], [True], [True, False, True, True]),
                   ([True, False, True], [True, True, True], [True, False, True, True, True, True])]
        text = [(list(map(str, a)), list(map(str, b)), list(map(str, c))) for a, b, c in numeric]
        source, expected = '', []
        serial = 0
        for kind, cases in [('Boolean', boolean), ('Integer', numeric * 3), ('Text', text),
                            ('Integer', [([0, 1], [], [0, 1]), ([0, 1], [0, 0], [0, 1, 0, 0])]),
                            ('Text', [([], [], [])])]:
            for case_index, (initial, additions, result) in enumerate(cases):
                name = f'values{serial}'
                serial += 1
                literal = lambda values: '[' + ', '.join(json.dumps(value) for value in values) + ']'
                source += f'let {name}: List<{kind}> = {literal(initial)}\n'
                if case_index % 10 >= 6 or len(cases) < 3:
                    source += f'let extra{serial}: List<{kind}> = {literal(additions)}\nlet a{serial} = 0\n'
                    source += f'while a{serial} < extra{serial}.length {{ {name}.add(extra{serial}[a{serial}]); a{serial} = a{serial} + 1 }}\n'
                else:
                    for value in additions:
                        source += f'{name}.add({json.dumps(value)})\n'
                source += f'print({name}.length)\nlet p{serial} = 0\nwhile p{serial} < {name}.length {{ print({name}[p{serial}]); p{serial} = p{serial} + 1 }}\n'
                expected.extend([str(len(result)), *[str(value).lower() if isinstance(value, bool) else str(value) for value in result]])
        self.assertEqual(serial, 53)
        self.executes(source, '\n'.join(expected) + '\n')

    def test_append_record_prefix_suffix_and_input_preservation(self):
        # A fresh List models the result when Go append outgrows its slice.
        # Copying the prefix explicitly preserves the input's observed length;
        # this does not assert Go slice-capacity/backing-address behavior.
        source = '''record Entry { a: Text; b: Text; c: Text }
function prefix(values: List<Entry>, end: Integer): List<Entry> {
let result: List<Entry> = []; let i = 0
while i < end { result.add(values[i]); i = i + 1 }
return result
}
function appendTail(input: List<Entry>, values: List<Entry>, start: Integer): List<Entry> {
let result = prefix(input, input.length); let i = start
while i < values.length { result.add(values[i]); i = i + 1 }
return result
}
function show(values: List<Entry>) {
print(values.length); let i = 0
while i < values.length { print(values[i].a); print(values[i].b); print(values[i].c); i = i + 1 }
}
let entries: List<Entry> = []; let n = 0
while n < 100 { entries.add(Entry { a: "foo"; b: Text(n); c: "bar" }); n = n + 1 }
'''
        expected = []
        def oracle(indices):
            expected.append(str(len(indices)))
            for index in indices:
                expected.extend(('', '', '') if index is None else ('foo', str(index), 'bar'))
        for serial, (start, added) in enumerate([(0, []), (0, [0]), (0, [0, 1, 2]), (1, []),
                                               (1, [1]), (1, [1, 2, 3]), (3, []), (3, [3]), (3, [3, 4, 5, 6])]):
            source += f'let fixed{serial} = prefix(entries, {start})\n'
            for index in added:
                source += f'fixed{serial}.add(entries[{index}])\n'
            source += f'show(fixed{serial})\n'
            oracle(list(range(start)) + added)
        source += '''let i = 0
while i < 100 {
show(prefix(entries, i))
let input = prefix(entries, i)
show(appendTail(input, entries, i))
show(input)
i = i + 1
}
let blanks: List<Entry> = []; let j = 0
while j < 10 { blanks.add(Entry { a: ""; b: ""; c: "" }); j = j + 1 }
show(blanks)
let result = appendTail(blanks, entries, 0)
show(result)
'''
        for count in range(100):
            oracle(list(range(count)))
            oracle(list(range(100)))
            oracle(list(range(count)))
        oracle([None] * 10)
        oracle([None] * 10 + list(range(100)))
        self.executes(source, '\n'.join(expected) + '\n')

    def test_direct_call_parameters_locals_and_self_comparisons(self):
        self.executes('''function add(a: Integer, b: Integer): Integer { return a + b }
function local(b: Integer) { let a = 1; if a + b != 3 { fail("unreachable") } }
function equal(x: Integer): Boolean { return x == x }
function notEqual(x: Integer): Boolean { return x != x }
function less(x: Integer): Boolean { return x < x }
function lessEqual(x: Integer): Boolean { return x <= x }
function greater(x: Integer): Boolean { return x > x }
function greaterEqual(x: Integer): Boolean { return x >= x }
function acceptsString(value: Text) { }
print(add(22, 11)); local(2)
let zero = 0; print(zero)
let i = 0; while i != 3 { i = i + 1 }; print(i)
if true { let noConflict = 5; print(noConflict) }
if true { let noConflict = 10; print(noConflict) }
acceptsString("")
print(equal(42)); print(notEqual(42)); print(less(42)); print(lessEqual(42)); print(greater(42)); print(greaterEqual(42))
''', '33\n0\n3\n5\n10\ntrue\nfalse\nfalse\ntrue\nfalse\ntrue\n')

    def test_direct_record_argument_and_empty_list_return(self):
        (self.directory / 'empty.min').write_text('''public function get(): List<Integer> {
let result: List<Integer> = []; return result
}
''')
        self.executes('''use "./empty.min" as empty
record Point { x: Integer; y: Integer }
function addPointCoords(point: Point): Integer { return point.x + point.y }
print(addPointCoords(Point { x: 1; y: 2 }))
let values = empty.get(); print(values.length)
''', '3\n0\n')

    def test_nominal_record_and_collection_comparison_diagnostics(self):
        prefix = '''record S { X: Integer }
record Other { X: Integer }
let s = S { X: 0 }
let other = Other { X: 0 }
'''
        cases = [(prefix + 's = other\n', "an assignment to 's' has the wrong type"),
                 (prefix + 'other = s\n', "an assignment to 'other' has the wrong type"),
                 ('record Box { values: List<Integer> }\nlet values: List<Integer> = []\nlet value = Box { values: values }\nprint(value == value)\n',
                  'line 4, column 13: records, Lists, and Bytes do not yet support equality'),
                 ('let value: List<Integer> = []\nprint(value == value)\n',
                  'line 2, column 13: records, Lists, and Bytes do not yet support equality')]
        for source, diagnostic in cases:
            with self.subTest(source=source):
                result, llvm = self.compile(source)
                self.assertEqual((result.returncode, result.stdout, result.stderr),
                                 (1, '', 'Minyar stopped: ' + diagnostic + '\n'))
                self.assertFalse(llvm.exists())

    def test_boolean_phi_complete_truth_tables(self):
        self.executes('''function conjunction(a: Boolean, b: Boolean): Boolean {
let x = false
if a { x = b } else { x = a }
return x
}
function disjunction(a: Boolean, b: Boolean): Boolean {
let x = false
if a { x = a } else { x = b }
return x
}
print(conjunction(false, false)); print(conjunction(false, true))
print(conjunction(true, false)); print(conjunction(true, true))
print(disjunction(false, false)); print(disjunction(false, true))
print(disjunction(true, false)); print(disjunction(true, true))
''', 'false\nfalse\nfalse\ntrue\nfalse\ntrue\ntrue\ntrue\n')

    def test_boolean_cell_stores_and_comparisons_preserve_all_values(self):
        # Boolean pointers become shared one-cell Lists. Exercise all four
        # argument/initial-cell pairs, every ordered comparison pair, and both
        # same-cell comparison aliases. The source's exact returns are 5 and 7.
        self.executes('''function constantWrite(b: Boolean, p: List<Boolean>) {
if b { p[0] = b }
}
function boolCompare1(p: List<Boolean>, q: List<Boolean>): Integer {
if p[0] == q[0] { return 5 }; return 7
}
function boolCompare2(p: List<Boolean>, q: List<Boolean>): Integer {
if p[0] != q[0] { return 5 }; return 7
}
let cell0 = [false]; let alias0 = cell0; constantWrite(false, alias0); print(cell0[0])
let cell1 = [true]; let alias1 = cell1; constantWrite(false, alias1); print(cell1[0])
let cell2 = [false]; let alias2 = cell2; constantWrite(true, alias2); print(cell2[0])
let cell3 = [true]; let alias3 = cell3; constantWrite(true, alias3); print(cell3[0])
let p0 = [false]; let q0 = [false]; print(boolCompare1(p0, q0)); print(boolCompare2(p0, q0))
let p1 = [false]; let q1 = [true]; print(boolCompare1(p1, q1)); print(boolCompare2(p1, q1))
let p2 = [true]; let q2 = [false]; print(boolCompare1(p2, q2)); print(boolCompare2(p2, q2))
let p3 = [true]; let q3 = [true]; print(boolCompare1(p3, q3)); print(boolCompare2(p3, q3))
let same0 = [false]; print(boolCompare1(same0, same0)); print(boolCompare2(same0, same0))
let same1 = [true]; print(boolCompare1(same1, same1)); print(boolCompare2(same1, same1))
''', 'false\ntrue\ntrue\ntrue\n5\n7\n7\n5\n7\n5\n5\n7\n5\n7\n5\n7\n')

    def test_constant_comparison_loop_complete_traces(self):
        source = '''function observe(value: Integer) { print(value) }
function loops() {
let i = 0
while i < 128 { observe(i); i = i + 1 }
i = 0
while i < 256 { observe(i); i = i + 1 }
i = 257
while i >= 256 { observe(i); i = i - 1 }
i = 1024
while i > 0 { observe(i); i = i - 1 }
}
loops()
loops()
'''
        # Two upstream unsigned-width variants have identical concrete domains;
        # no value approaches a width boundary. Every iteration is observed.
        one = [*range(128), *range(256), 257, 256, *range(1024, 0, -1)]
        self.executes(source, ''.join(f'{value}\n' for value in one * 2))

    def test_scalar_absolute_value_source_cases(self):
        inputs = [-1000, 0, 1000, -1, -5, 1000, 0, 1000, 1, 5]
        expected = [1000, 0, 1000, 1, 5, 1000, 0, 1000, 1, 5]
        source = '''function absolute(value: Integer): Integer {
if value < 0 { return -value }
return value
}
''' + ''.join(f'print(absolute({value}))\n' for value in inputs)
        self.executes(source, ''.join(f'{value}\n' for value in expected))

    def test_scalar_minimum_maximum_all_source_operands(self):
        source = '''function minimum(a: Integer, b: Integer): Integer { if a < b { return a }; return b }
function maximum(a: Integer, b: Integer): Integer { if a > b { return a }; return b }
function minThree(a: Integer, b: Integer, c: Integer): Integer { return minimum(minimum(a, b), c) }
function maxThree(a: Integer, b: Integer, c: Integer): Integer { return maximum(maximum(a, b), c) }
function minFour(a: Integer, b: Integer, c: Integer, d: Integer): Integer { return minimum(minThree(a, b, c), d) }
function maxFour(a: Integer, b: Integer, c: Integer, d: Integer): Integer { return maximum(maxThree(a, b, c), d) }
print(maximum(-3, 10)); print(minimum(-3, 10))
print(minThree(30, 10, 20)); print(maxThree(30, 10, 20))
print(minThree(20, 30, 100)); print(maxThree(20, 30, 100))
print(minFour(1, 2, -2, -1)); print(maxFour(1, 2, -2, -1))
print(minThree(123, 456, 10)); print(maxThree(123, 456, 10))
print(minimum(-1, 1)); print(maximum(-1, 1))
print(minimum(-2147483648, 4294967295)); print(maximum(-2147483648, 4294967295))
'''
        expected = [10, -3, 10, 30, 20, 100, -2, 2, 10, 456, -1, 1, -2147483648, 4294967295]
        self.executes(source, ''.join(f'{value}\n' for value in expected))

    def test_deferred_primary_name_type_and_token_diagnostics(self):
        # Preserve each failing operand/field and the compiler's first-error
        # contract. Rust regions, Zig reflection and ZON import syntax are not
        # claimed: their primary missing-name/type errors are ordinary source.
        cases = [
            ('let x: Iter = 0\n', "line 1, column 8: unknown type 'Iter'"),
            ('while false {} else {}\n', "line 1, column 16: unexpected 'else'; start the next statement on a new line"),
            ('record Foo { a: Integer }\nfunction lol(b: Foo) { b.c }\n', "record 'Foo' has no field named 'c'"),
            ('function main() { asdf }\n', "line 1, column 19: I can't find a value named 'asdf'"),
            ('\n\ufeff //BOM\n', "line 2, column 1: names must use ASCII letters, digits, and '_'; found non-ASCII character '\ufeff'"),
            ("let foo: Character = '\\U1234'\n", 'line 1, column 22: Character literal must contain exactly one character and a closing quote'),
            ('function foo(): boid {}\n', "line 1, column 17: unknown type 'boid'"),
            ('return 1\n', 'line 1, column 1: use exit(status) to finish a top-level program'),
            ('function a() { b() }\n', "line 1, column 16: I can't find a function named 'b'"),
            ("print(-'a')\n", 'line 1, column 11: negation needs an Integer or Float'),
            ('record Value { boolean: Boolean; number: Integer }\nlet value: Boolean = Value { boolean: true; number: 123 }\n', "line 2, column 5: the value for 'value' does not match its declared type"),
            ('record Value { value: Boolean }\nlet value = Value { value: truefalse }\n', "line 2, column 28: I can't find a value named 'truefalse'"),
            ('let A = B\n', "line 1, column 9: I can't find a value named 'B'"),
            ('let derp = 1234\nprint(derp + "foo")\n', "line 2, column 12: the two sides of '+' have different types (Integer and Text)"),
            ('function dummy(value: Integer) {}\ndummy([1, 2])\n', 'line 2, column 14: an argument passed to dummy has the wrong type'),
            ('let cstr = "Hat"\ncstr[0] = \'W\'\n', 'line 2, column 5: indexed assignment needs a List or Bytes, not Text'),
            ('let x = 0\nx = \x00Q\n', "line 2, column 5: expected an expression, found '\x00'"),
        ]
        for source, diagnostic in cases:
            with self.subTest(source=source):
                result, llvm = self.compile(source)
                self.assertEqual((result.returncode, result.stdout, result.stderr),
                                 (1, '', 'Minyar stopped: ' + diagnostic + '\n'))
                self.assertFalse(llvm.exists())

    def test_invalid_utf8_prefix_before_function_is_rejected(self):
        from regressions import COMPILER, COMPILE_TIMEOUT
        path = self.directory / 'invalid-prefix.min'
        path.write_bytes(b'\xff\xfefunction foo(): Boolean { return true }\n')
        llvm = path.with_suffix('.ll')
        result = self.evidence.run([COMPILER, path, llvm], timeout=COMPILE_TIMEOUT, phase='compile')
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (1, b'', b'Minyar stopped: Text contained invalid UTF-8.\n'))
        self.assertFalse(llvm.exists())

    def test_owned_record_swap_keeps_both_original_values(self):
        self.executes('''record Box { value: Integer }
function run() {
let i = Box { value: 100 }; let j = Box { value: 200 }
let temporary = i; i = j; j = temporary
print(i.value); print(j.value)
}
run()
''', '200\n100\n')

    def test_zero_iteration_loops_skip_fatal_and_guarded_bodies(self):
        self.executes('''let values: List<Integer> = []; let index = 0
while index < values.length { fail("moop"); index = index + 1 }
let x = 10
while x == 10 && x == 11 { let y = 3840; print(y) }
''', '')

    def test_constant_true_loop_returns_through_nested_helper(self):
        self.executes('''function whileLoop2(): Integer { while true { return 1 } }
function whileLoop1(): Integer { return whileLoop2() }
print(whileLoop1())
''', '1\n')

    def test_module_and_local_names_and_nested_record_construction(self):
        module = self.directory / 'rgz-names.min'
        module.write_text('''public record TreeLeaf { value: Integer }
public record BTree { node: TreeLeaf }
public function leaf(value: Integer): TreeLeaf { return TreeLeaf { value: value } }
public function g(): Integer { return 14 }
''')
        self.evidence.inputs[str(module)] = digest(module)
        self.executes('''use "./rgz-names.min" as x
use "./rgz-names.min" as std
let std = "std"; print(std)
let x = 9; x + 3; print(x.g())
let tree = x.BTree { node: x.leaf(1) }; print(tree.node.value)
record A { a: Integer }
function a(a: A): Integer { return a.a }
let value: A = A { a: 1 }; print(a(value))
let print: Integer = 0; print(print)
''', 'std\n14\n1\n1\n0\n')

    def test_repeated_small_decimal_conversions_keep_length_sink(self):
        # Go's b.N becomes an explicit 1000 repetitions for each original input.
        # Every decimal result and the cumulative length sink are observable;
        # this is a semantic workload, without a timing/benchmark claim.
        self.executes('''let values = [7, 42]
let sink = 0; let input = 0
while input < values.length {
let iteration = 0
while iteration < 1000 {
let text = Text(values[input]); print(text)
sink = sink + text.length; iteration = iteration + 1
}
print(sink); input = input + 1
}
''', '7\n' * 1000 + '1000\n' + '42\n' * 1000 + '3000\n')

    def test_bom_and_crlf_file_contents_are_preserved(self):
        # Compile-time include_bytes/include_str become runtime UTF-8 file I/O.
        # Both observe the complete original byte sequence, including the BOM,
        # CRLF separators and the literal backslashes in the second line.
        payload = b'\xef\xbb\xbfThis file starts with BOM.\r\nLines are separated by \\r\\n.\r\n'
        path = self.directory / 'rgz-bom-crlf.bin'
        output = self.directory / 'rgz-bom-crlf-copy.bin'
        path.write_bytes(payload)
        self.evidence.inputs[str(path)] = digest(path)
        CompilerTestCase.executes(self, '''let contents = readTextFile(argument(0))
print(contents.byteLength); print(contents.length); print(contents)
writeTextFile(argument(1), contents)
print(readTextFile(argument(1)))
''', str(len(payload)) + '\n' + str(len(payload.decode('utf-8'))) + '\n' + (payload.decode('utf-8') + '\n') * 2,
                      arguments=(str(path), str(output)),
                      optimizations=('-O0','-O2','-O3','-Os') if os.environ.get('MINYAR_TEST_EXTENDED_OPT')=='1' else ('-O0','-O2'),
                      file_outputs=((output, payload),))

    def test_two_aggregate_results_keep_independent_elements(self):
        self.executes('''record Pair { first: Integer; second: Integer }
function F(value: Pair): Pair { return Pair { first: value.first; second: value.second } }
let a = F(Pair { first: 1; second: 2 })
let b = F(Pair { first: 3; second: 4 })
print(Text(a.first) + " " + Text(a.second) + " " + Text(b.first) + " " + Text(b.second))
''', '1 2 3 4\n')

    def test_module_call_retains_ignored_large_aggregate_arguments(self):
        module = self.directory / 'rgz-large-args.min'
        module.write_text('''public record Large { x: List<Integer> }
public function F(x: Integer, unusedInteger: Integer, unusedBoolean: Boolean, unusedLarge: Large): Integer { return x }
''')
        self.evidence.inputs[str(module)] = digest(module)
        zeros = ', '.join(['0'] * 256)
        # The upstream importer leaves x symbolic; these explicit values cover
        # both signs and extremes while preserving its 256 initialized cells.
        self.executes('use "./rgz-large-args.min" as a\n' +
                      'function G(x: Integer): Integer { return a.F(x, 1, false, a.Large { x: [' + zeros + '] }) }\n' +
                      'print(G(0)); print(G(1)); print(G(-1)); print(G(9223372036854775807)); print(G(-9223372036854775808))\n',
                      '0\n1\n-1\n9223372036854775807\n-9223372036854775808\n')

    def test_integer_log2_one_below_and_at_power(self):
        self.executes('''function log2(value: Integer): Integer {
let n = value; let exponent = 0
while n >= 2 { n = n / 2; exponent = exponent + 1 }
return exponent
}
print(log2(1)); print(log2(15)); print(log2(16))
''', '0\n3\n4\n')

    def test_log_integer_generated_boundary_domain(self):
        import sys
        sys.path.insert(0, str(ROOT / 'tools'))
        from peer_zig_domains import instances, validate_domain
        artifact = ROOT / 'docs/research/exhaustive/zig/log-int-generated-domain.json'
        schema = ROOT / 'tools/peer_zig_domains.py'
        self.evidence.inputs[str(artifact)] = digest(artifact)
        self.evidence.inputs[str(schema)] = digest(schema)
        domain = json.loads(artifact.read_text())
        cohorts = validate_domain(domain)
        expected = []
        for cohort, identity, base, value, result in instances():
            if cohort != 'boundary-representable':
                continue
            parts = identity.split('/')
            bits = int(parts[0].removeprefix('bits'))
            exponent = 0 if parts[-1] == 'one' else int(parts[2].removeprefix('power'))
            branch = {'one': 0, 'below': 1, 'at': 2}[parts[-1]]
            expected.append(f'{bits}\n{base}\n{exponent}\n{branch}\n{value}\n{result}\n')
        self.assertEqual(len(expected), 514804)
        self.evidence.controls['source_domain'] = dict(domain_id=domain['domain_id'],
                                                       cohort='boundary-representable',
                                                       instances_per_configuration=len(expected),
                                                       oracle_sha256=cohorts['boundary-representable']['oracle_sha256'])
        self.evidence.controls['source_domain']['separately_rejected_cohorts'] = [{
            'domain': 'boundary-outside-integer', 'instances_per_configuration': 210,
            'reason': 'Pinned unsigned64 source inputs exceed signed64 Integer; separately rejected cohort with exact input/oracle hashes'}]
        # The local helper divides the input repeatedly; the external boundary
        # oracle enumerates exact integer powers. Printing identity and input
        # alongside every result prevents an omitted/repeated case passing.
        self.executes('''function logarithm(base: Integer, value: Integer): Integer {
let n = value; let exponent = 0
while n >= base { n = n / base; exponent = exponent + 1 }
return exponent
}
function observe(bits: Integer, base: Integer, exponent: Integer, branch: Integer, value: Integer) {
print(bits); print(base); print(exponent); print(branch); print(value); print(logarithm(base, value))
}
let bits = 2; let maximum = 3
while bits <= 64 {
let base = 2
while base <= maximum && base <= 1025 {
observe(bits, base, 0, 0, 1)
let power = 1; let exponent = 0
while power <= maximum / base {
power = power * base; exponent = exponent + 1
observe(bits, base, exponent, 1, power - 1); observe(bits, base, exponent, 2, power)
}
// Four source powers equal 2^63. Their predecessors remain representable;
// their at-power cases belong to the explicit 210-case rejected cohort.
if bits == 64 && (base == 2 || base == 8 || base == 128 || base == 512) {
observe(bits, base, exponent + 1, 1, 9223372036854775807)
}
base = base + 1
}
if bits < 63 { maximum = maximum * 2 + 1 }
bits = bits + 1
}
''', ''.join(expected))

    def test_log_integer_generated_specialized_comparison_domains(self):
        import sys
        sys.path.insert(0, str(ROOT / 'tools'))
        from peer_zig_domains import instances, validate_domain
        artifact = ROOT / 'docs/research/exhaustive/zig/log-int-generated-domain.json'
        schema = ROOT / 'tools/peer_zig_domains.py'
        self.evidence.inputs[str(artifact)] = digest(artifact)
        self.evidence.inputs[str(schema)] = digest(schema)
        domain = json.loads(artifact.read_text()); cohorts = validate_domain(domain)
        expected = []
        for cohort, identity, base, value, result in instances():
            if cohort not in ('log2-comparison', 'log10-comparison'):
                continue
            bits = int(identity.split('/')[0].removeprefix('bits'))
            expected.append(f'{bits}\n{base}\n{value}\n{result}\n{result}\n')
        self.assertEqual(len(expected), 65815 + 65899)
        self.evidence.controls['source_domain'] = dict(domain_id=domain['domain_id'], cohorts={
            name: {key: cohorts[name][key] for key in ('instances', 'input_sha256', 'oracle_sha256')}
            for name in ('log2-comparison', 'log10-comparison')})
        self.executes('''function logarithm(base: Integer, value: Integer): Integer {
let n = value; let exponent = 0
while n >= base { n = n / base; exponent = exponent + 1 }
return exponent
}
function log2(value: Integer): Integer {
let threshold = 2; let result = 0
while threshold <= value { threshold = threshold * 2; result = result + 1 }
return result
}
function compare(bits: Integer, base: Integer) {
let maximum = 1; let bit = 0
while bit < bits { maximum = maximum * 2; bit = bit + 1 }
let value = 1
while value < maximum {
let specialized = 0
if base == 2 { specialized = log2(value) } else { specialized = Text(value).length - 1 }
print(bits); print(base); print(value); print(specialized); print(logarithm(base, value))
value = value + 1
}
}
let log2Widths = [2, 3, 4, 8, 16]; let index = 0
while index < log2Widths.length { compare(log2Widths[index], 2); index = index + 1 }
let log10Widths = [4, 5, 6, 8, 16]; index = 0
while index < log10Widths.length { compare(log10Widths[index], 10); index = index + 1 }
''', ''.join(expected))

    def test_data_allocator_zero_shrink_regrow_and_supported_alignment(self):
        from regressions import CLANG, LINK_FLAGS
        fixture = ROOT / 'tests/peer-rgz-data-resize.c'
        for dependency in (fixture, *sorted((ROOT / 'runtime').glob('minyar_*.h')),
                           ROOT / 'runtime/minyar_runtime.c'):
            self.evidence.inputs[str(dependency)] = digest(dependency)
        variants = ('-O0', '-O2', '-O3', '-Os') if os.environ.get('MINYAR_TEST_EXTENDED_OPT') == '1' else ('-O0', '-O2')
        profiles = [('eager', []), ('system', ['-DMINYAR_SYSTEM_HEAP=1']),
                    ('fixed', ['-DMINYAR_BOUNDED_HEAP=1']),
                    ('lazy', ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_LAZY_HEAP=1'])]
        self.evidence.controls['allocator_profiles'] = [profile for profile, _ in profiles]
        for optimization in variants:
            for profile, flags in profiles:
                with self.subTest(optimization=optimization, profile=profile):
                    executable = self.directory / ('data-resize-' + profile + optimization)
                    linked = self.evidence.run(clang_command([CLANG, '-std=c11', optimization, *LINK_FLAGS, *flags,
                                                '-DMINYAR_BOUNDED_HEAP_BYTES=1048576', fixture, '-o', executable]),
                                               timeout=30, phase='link-data-allocator')
                    self.assertEqual(linked.returncode, 0, linked.stderr)
                    run = self.evidence.run([executable], timeout=30, phase='execute-data-allocator')
                    self.assertEqual((run.returncode, run.stdout, run.stderr),
                                     (0, b'resize-zero-regrow; empty; align1,2,4,8; page-plus-one-shrink; zero-live-bytes\n', b''))

    @unittest.skipUnless(sys.platform.startswith('linux'), 'ELF -z text linker contract requires Linux')
    def test_empty_program_links_without_elf_text_relocations(self):
        from regressions import CLANG, LINK_FLAGS, RUNTIME
        compiled, llvm = self.compile('')
        self.assertEqual((compiled.returncode, compiled.stdout, compiled.stderr), (0, '', ''))
        variants = ('-O0', '-O2', '-O3', '-Os') if os.environ.get('MINYAR_TEST_EXTENDED_OPT') == '1' else ('-O0', '-O2')
        for optimization in variants:
            with self.subTest(optimization=optimization):
                executable = llvm.with_suffix('.' + optimization[1:])
                linked = self.evidence.run(clang_command([CLANG, optimization, *LINK_FLAGS, '-Wno-override-module',
                                            '-Wl,-z,text', llvm, RUNTIME, '-o', executable]),
                                           timeout=30, phase='link-elf-z-text')
                self.assertEqual(linked.returncode, 0, linked.stderr)
                run = self.evidence.run([executable], timeout=30, phase='execute-elf-z-text')
                self.assertEqual((run.returncode, run.stdout, run.stderr), (0, b'', b''))

    def test_returned_lists_branch_alias_and_fresh_result(self):
        source = '''function zeros(): List<Integer> {
let result: List<Integer> = []
let i = 0
while i < 16 { result.add(0); i = i + 1 }
return result
}
function set(values: List<Integer>, index: Integer, value: Integer) { values[index] = value }
function single(x: Integer): List<Integer> {
let ret = zeros()
set(ret, 0, x)
set(ret, 8, x + 1)
return ret
}
function addrTaken(x: Integer): List<Integer> {
let ret = zeros()
let alias = ret
alias[1] = x
return ret
}
function captured(x: Integer): List<Integer> {
let ret = zeros()
set(ret, 2, x)
return ret
}
function multi(x: Integer, c: Boolean): List<Integer> {
let ret = zeros()
ret[4] = x
if c { return ret }
ret[5] = x + 1
return ret
}
function escaped(x: Integer, c: Boolean, sink: List<List<Integer>>): List<Integer> {
let ret = zeros()
ret[3] = x
sink[0] = ret
if c { return ret }
let other = zeros()
other[4] = 99
return other
}
function partial(x: Integer, c: Boolean): List<Integer> {
let ret = zeros()
ret[6] = x
if c { return ret }
let other = zeros()
other[7] = 77
return other
}
function partialOther(x: Integer, c: Boolean): List<Integer> {
let ret = zeros()
ret[8] = x
if c { return ret }
let other = zeros()
other[9] = 88
return other
}
function show(values: List<Integer>) {
print(values.length)
let i = 0
while i < 16 { print(values[i]); i = i + 1 }
}
let sink: List<List<Integer>> = [zeros()]
'''
        cases = [('single(10)', {0: 10, 8: 11}), ('addrTaken(12)', {1: 12}),
                 ('captured(13)', {2: 13}), ('multi(15, true)', {4: 15}),
                 ('multi(15, false)', {4: 15, 5: 16}), ('escaped(14, true, sink)', {3: 14}),
                 ('sink[0]', {3: 14}), ('escaped(14, false, sink)', {4: 99}),
                 ('partial(17, true)', {6: 17}), ('partial(17, false)', {7: 77}),
                 ('partialOther(18, true)', {8: 18}), ('partialOther(18, false)', {9: 88})]
        expected = []
        for expression, fields in cases:
            source += f'show({expression})\n'
            expected += [16, *[fields.get(i, 0) for i in range(16)]]
        # The original sink must also survive when a fresh result was returned.
        source += 'show(sink[0])\n'
        expected += [16, *[14 if i == 3 else 0 for i in range(16)]]
        self.executes(source, ''.join(f'{n}\n' for n in expected))

    def test_record_list_literal_helper_and_direct_elements(self):
        source = '''record Item { num: Integer; text: Text }
function item(n: Integer): Item { return Item { num: n; text: "item-" + Text(n) } }
function show(values: List<Item>) {
let i = 0
while i < values.length { print(values[i].num); print(values[i].text); i = i + 1 }
}
let helpers = [item(0), item(1), item(2), item(3), item(4), item(5)]
let direct = [''' + ', '.join(f'Item {{ num: {n}; text: "item-" + Text({n}) }}' for n in range(6)) + ''']
show(helpers)
show(direct)
'''
        self.executes(source, ''.join(f'{n}\nitem-{n}\n' for _ in range(2) for n in range(6)))

    def test_repeated_record_branch_returns_and_original_copy(self):
        self.executes('''record Triple { x: Integer; y: Integer; z: Integer }
function choose(flag: Boolean, value: Triple): Integer {
let alias = value
let chosen = alias
if flag { chosen = alias } else { chosen = Triple { x: 4; y: 5; z: 6 } }
return chosen.y
}
let value = Triple { x: 1; y: 2; z: 3 }
let copy = value
print(copy.x)
print(value.x)
let i = 0
let sum = 0
while i < 10000 { let answer = choose(true, value); if answer != 2 { fail("bad branch result") }; sum = sum + answer; i = i + 1 }
print(sum)
print(choose(false, value))
''', '1\n1\n20000\n5\n')

    def test_record_alias_chain_and_returned_text_field(self):
        self.executes('''record Triple { a: Integer; b: Integer; c: Integer; text: Text }
function transfer(input: Triple): Triple {
let first = input
let second = first
let third = second
let fourth = third
return fourth
}
function make(): Triple { return transfer(Triple { a: 1; b: 2; c: 3; text: "Hello, " + "World!" }) }
function field(value: Triple): Text { return value.text }
let result = make()
print(result.c)
let text = field(result)
result = Triple { a: 4; b: 5; c: 6; text: "replacement" + Text(1) }
print(text)
print(text.length)
''', '3\nHello, World!\n13\n')

    def test_local_temporary_lists_and_fresh_factory_results(self):
        self.executes('''function inspect(values: List<Integer>) { print(values[0]) }
function factory(): List<Integer> { let values = [1, 2, 3]; values.add(4); return values }
let local = [10]
inspect(local)
inspect([10])
let first = factory()
let second = factory()
print(first.length)
print(second.length)
let i = 0
while i < 4 { print(first[i]); print(second[i]); i = i + 1 }
first[0] = 99
print(first[0])
print(second[0])
''', '10\n10\n4\n4\n1\n1\n2\n2\n3\n3\n4\n4\n99\n1\n')

    def test_nested_boolean_calls_keep_exact_effect_order(self):
        source = '''function step(trace: List<Text>, name: Text, position: Integer) {
if trace.length != position { fail("wrong evaluation order") }
trace.add(name)
}
'''
        for name, position, kind, result in [('A', 1, 'Boolean', 'true'), ('B', 2, 'Boolean', 'true'),
                                             ('C', 5, 'Boolean', 'false'), ('E', 3, 'Integer', '0'),
                                             ('F', 0, 'Integer', '0'), ('J', 4, 'Integer', '0'),
                                             ('K', 6, 'Integer', '0'), ('L', 10, 'Integer', '0')]:
            source += f'function {name}(trace: List<Text>): {kind} {{ step(trace, "{name}", {position}); return {result} }}\n'
        source += '''function D(trace: List<Text>): Boolean { fail("D must not run") }
function G(trace: List<Text>, flag: Boolean): Integer { step(trace, "G", 9); print(flag); return 0 }
function H(trace: List<Text>, a: Integer, flag: Boolean, b: Integer): Integer { step(trace, "H", 7); print(flag); return a + b }
function I(trace: List<Text>, a: Integer): Boolean { step(trace, "I", 8); return a == 0 }
let trace: List<Text> = []
let result = F(trace) + G(trace, A(trace) && B(trace) && I(trace, E(trace) + H(trace, J(trace), C(trace) && D(trace), K(trace)))) + L(trace)
print(result)
print(trace.length)
print(joinText(trace))
'''
        self.executes(source, 'false\ntrue\n0\n11\nFABEJCKHIGL\n')

    def test_sort_nonzero_subrange_preserves_outside_cells(self):
        self.executes('''function get(values: List<Integer>, i: Integer, start: Integer, end: Integer): Integer {
if i < start || i >= end { fail("sort read escaped range") }
return values[i]
}
function put(values: List<Integer>, i: Integer, value: Integer, start: Integer, end: Integer) {
if i < start || i >= end { fail("sort write escaped range") }
values[i] = value
}
function sort(values: List<Integer>, start: Integer, end: Integer) {
let i = start + 1
while i < end {
let value = get(values, i, start, end)
let j = i
while j > start && get(values, j - 1, start, end) > value {
put(values, j, get(values, j - 1, start, end), start, end)
j = j - 1
}
put(values, j, value, start, end)
i = i + 1
}
}
let values: List<Integer> = []
let i = 0
while i < 2000 { values.add((i * 7) % 100); i = i + 1 }
sort(values, 1118, 1764)
i = 0
while i < values.length { print(values[i]); i = i + 1 }
''', ''.join(f'{n}\n' for n in self.sorted_subrange_oracle()))

    @staticmethod
    def sorted_subrange_oracle():
        values = [(i * 7) % 100 for i in range(2000)]
        values[1118:1764] = sorted(values[1118:1764])
        return values

    def test_list_odd_count_and_cartesian_product_sum(self):
        self.executes('''function odds(values: List<Integer>): Integer {
let count = 0
let i = 0
while i < values.length { if values[i] % 2 == 1 { count = count + 1 }; i = i + 1 }
return count
}
function products(values: List<Integer>): Integer {
let sum = 0
let i = 0
while i < values.length {
let j = 0
while j < values.length { sum = sum + values[i] * values[j]; j = j + 1 }
i = i + 1
}
return sum
}
print(odds([1, 2, 3, 4, 5, 6, 7]))
print(products([1, 2, 3, 4, 5]))
''', '4\n225\n')

    def test_integer_divisibility_normalization_stops_at_first_remainder(self):
        source = '''function normalize(input: Integer): Text {
let factors = [1000000, 60, 60, 24, 7]
let units = ["s", "m", "h", "d", "w"]
let value = input
let unit = "u"
let index = 0
let active = true
while index < factors.length && active {
if value % factors[index] != 0 { active = false } else {
value = value / factors[index]
unit = units[index]
index = index + 1
}
}
return Text(value) + unit
}
'''
        inputs = [1, 1000000, 60000000, 3600000000, 86400000000, 604800000000, 1000001, 0]
        source += ''.join(f'print(normalize({n}))\n' for n in inputs)
        self.executes(source, '1u\n1s\n1m\n1h\n1d\n1w\n1000001u\n0w\n')

    def test_positive_byte_reversal_population_and_checked_arithmetic(self):
        fixture = ROOT / 'tests/peer-rgz-integer-vectors.json'
        self.evidence.inputs[str(fixture.resolve())] = digest(fixture)
        groups = json.loads(fixture.read_text())
        self.assertEqual(len(groups), 3)
        self.assertEqual([group['target'] for group in groups], [
            'test/behavior/byteswap.zig', 'test/behavior/popcount.zig',
            'test/behavior/wrapping_arithmetic.zig'])
        self.assertEqual([len(group['vectors']) for group in groups], [6, 5, 25])
        source = '''function reverse(value: Integer, width: Integer): Integer {
let remaining = value
let result = 0
let i = 0
while i < width { result = result * 256 + remaining % 256; remaining = remaining / 256; i = i + 1 }
return result
}
function population(value: Integer): Integer {
let n = value
let count = 0
while n > 0 { count = count + n % 2; n = n / 2 }
return count
}
function add(a: Integer, b: Integer): Integer { return a + b }
function subtract(a: Integer, b: Integer): Integer { return a - b }
function multiply(a: Integer, b: Integer): Integer { return a * b }
'''
        expected = []
        for vector in groups[0]['vectors']:
            oracle = int.from_bytes(vector['value'].to_bytes(vector['bytes'], 'little'), 'big')
            self.assertEqual(oracle, vector['expected'])
            source += f'print(reverse({vector["value"]}, {vector["bytes"]}))\n'
            expected.append(oracle)
        for vector in groups[1]['vectors']:
            oracle = vector['value'].bit_count()
            self.assertEqual(oracle, vector['expected'])
            source += f'print(population({vector["value"]}))\n'
            expected.append(oracle)
        for index, vector in enumerate(groups[2]['vectors']):
            a, b, op = vector['left'], vector['right'], vector['operator']
            oracle = {'+': lambda: a + b, '-': lambda: a - b, '*': lambda: a * b}[op]()
            self.assertEqual(oracle, vector['expected'])
            function = {'+': 'add', '-': 'subtract', '*': 'multiply'}[op]
            source += f'print({function}({a}, {b}))\nlet v{index} = {a}\nv{index} = v{index} {op} ({b})\nprint(v{index})\n'
            expected += [oracle, oracle]
        self.executes(source, ''.join(f'{n}\n' for n in expected))

    def test_ordered_removal_filter_handles_duplicate_indices(self):
        self.executes('''function remove(values: List<Integer>, indices: List<Integer>): List<Integer> {
let result: List<Integer> = []
let i = 0
while i < values.length {
let j = 0
let removed = false
while j < indices.length { if indices[j] == i { removed = true }; j = j + 1 }
if !removed { result.add(values[i]) }
i = i + 1
}
return result
}
function show(values: List<Integer>) { print(values.length); let i = 0; while i < values.length { print(values[i]); i = i + 1 } }
let values = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
values = remove(values, [1, 5, 5, 7, 9])
show(values)
values = remove(values, [0])
show(values)
values = remove(values, [])
show(values)
values = remove(values, [1, 2, 3, 4])
show(values)
values = remove(values, [0])
show(values)
''', '6\n0\n2\n3\n4\n6\n8\n5\n2\n3\n4\n6\n8\n5\n2\n3\n4\n6\n8\n1\n2\n0\n')

    def test_record_return_and_initializer_types_reject(self):
        self.rejects('record A { a: Integer }\nrecord B { a: Integer }\nfunction other(): B { return B { a: 1 } }\nfunction wrong(): A { return other() }\n', 'a returned value has the wrong type')
        for expression, missing in (('A { z: 4; y: 2; foo: 42 }', 'foo'), ('A { abc: 1 }', 'abc')):
            self.rejects('record A { x: Integer; y: Integer; z: Integer }\nlet value = ' + expression + '\n', f"record 'A' has no field named '{missing}'")
        self.rejects('record Object { field_1: Integer; field_2: Integer }\nfunction dump(value: Object) {}\ndump(Object { field_1: 123; field_3: 456 })\n', "record 'Object' has no field named 'field_3'")
        for source in ('let values = [9223372036854775808]\n', 'record Box { value: Integer }\nlet box = Box { value: 9223372036854775808 }\n'):
            self.rejects(source, 'Integer literal is outside the supported range')

    def test_decimal_leading_zero_and_malformed_tokens(self):
        self.executes("print(000123)\nprint(01)\nprint(''')\n", "123\n1\n'\n")
        for token in ('0e.0', '0E.0', '12e.0', '12E.0', '0xp0', '0xP0'):
            self.rejects('let value = ' + token + '\n', 'Minyar stopped:')


    def test_constant_multiplication_and_distributive_forms(self):
        source = 'function strength(n: Integer) {\n'
        expected = []
        want = 0
        for multiplier in range(200):
            source += f'print(n * {multiplier})\n'
            expected.append(want)
            want += 131
        source += '}\nfunction merge(n: Integer) {\n'
        axes = [(3, 5, 0), (17, 33, 0), (80, 45, 0), (32, 64, 0),
                (7, 11, 1), (9, 13, 2), (11, 16, -1), (17, 9, -2)]
        for a, b, offset in axes:
            for operator in ('+', '-'):
                source += f'print({a} * n {operator} {b} * (n + ({offset})))\n'
                source += f'print(({a} {operator} {b}) * n {operator} ({b} * ({offset})))\n'
                value = a * 42 + (1 if operator == '+' else -1) * b * (42 + offset)
                expected.extend([value, value])
        self.assertEqual(len(expected), 232)
        source += '}\nstrength(131)\nmerge(42)\n'
        self.executes(source, ''.join(f'{n}\n' for n in expected))

    def test_dynamic_text_literal_and_pair_dispatch(self):
        source = '''function fresh(value: Text): Text { return ("x" + value).slice(1, value.length + 1) }
function one(value: Text, capture: Boolean): Text {
if value == "a" { return "found a" }
if value == "b" { return "found b" }
if capture { return "not found (" + value + ")" }
return "not found"
}
function pair(first: Text, second: Text, capture: Boolean): Text {
if first == "a" && second == "b" { return "found a,b" }
if first == "b" && second == "c" { return "found b,c" }
if capture { return "not found (" + first + ", " + second + ")" }
return "not found"
}
'''
        expected = []
        for capture in (False, True):
            for value in ('b', 'c', 'd'):
                source += f'print(one(fresh("{value}"), {str(capture).lower()}))\n'
                expected.append('found b' if value == 'b' else f'not found ({value})' if capture else 'not found')
        for capture in (False, True):
            for first, second in [('b', 'c'), ('c', 'd'), ('d', 'e')]:
                source += f'print(pair(fresh("{first}"), fresh("{second}"), {str(capture).lower()}))\n'
                expected.append('found b,c' if first == 'b' else f'not found ({first}, {second})' if capture else 'not found')
        self.assertEqual(len(expected), 12)
        self.executes(source, '\n'.join(expected) + '\n')

    def test_integer_square_root_and_logarithm_workloads(self):
        import math
        roots = [3, 4, 5, 8, 9, 10, 0, 1, 3, 4, 8, 9]
        logarithms = [(2, n) for n in (1, 2, 0x72, 0xFFFFFF, 0x7FF0123456789ABC)] + [(9, 59049)]
        source = '''function root(value: Integer): Integer {
let low = 0
let high = value
let answer = 0
while low <= high {
let middle = low + (high - low) / 2
if middle == 0 { answer = 0; low = 1 } else {
if middle <= value / middle { answer = middle; low = middle + 1 } else { high = middle - 1 }
}
}
return answer
}
function logarithm(base: Integer, value: Integer): Integer {
let remaining = value
let result = 0
while remaining >= base { remaining = remaining / base; result = result + 1 }
return result
}
'''
        expected = [math.isqrt(n) for n in roots]
        source += ''.join(f'print(root({n}))\n' for n in roots)
        for base, value in logarithms:
            source += f'print(logarithm({base}, {value}))\n'
            power, exponent = 1, 0
            while power * base <= value:
                power *= base
                exponent += 1
            expected.append(exponent)
        self.executes(source, ''.join(f'{n}\n' for n in expected))

    def test_adler_checksum_streaming_integer_workload(self):
        import zlib
        vectors = [b'a', b'example', bytes([1]) * 1024, bytes([1]) * 1025,
                   bytes([1]) * 5553, bytes(i % 256 for i in range(6000))]
        source = '''function checksum(values: List<Integer>): Integer {
let low = 1
let high = 0
let i = 0
while i < values.length {
low = (low + values[i]) % 65521
high = (high + low) % 65521
 i = i + 1
}
return high * 65536 + low
}
function repeat(count: Integer, varied: Boolean): List<Integer> {
let values: List<Integer> = []
let i = 0
while i < count {
if varied { values.add(i % 256) } else { values.add(1) }
i = i + 1
}
return values
}
print(checksum([97]))
print(checksum([101, 120, 97, 109, 112, 108, 101]))
print(checksum(repeat(1024, false)))
print(checksum(repeat(1025, false)))
print(checksum(repeat(5553, false)))
print(checksum(repeat(6000, true)))
'''
        expected = [zlib.adler32(data) for data in vectors]
        self.assertEqual(expected, [0x620062, 0xbc002ed, 0x06780401, 0x0a7a0402, 0x707f15b2, 0x5af38d6e])
        self.executes(source, ''.join(f'{n}\n' for n in expected))


    def test_overlapping_character_list_moves_preserve_source(self):
        source = '''function move(values: List<Character>, destination: Integer, origin: Integer, count: Integer) {
if destination > origin {
let i = count
while i > 0 { i = i - 1; values[destination + i] = values[origin + i] }
} else {
let i = 0
while i < count { values[destination + i] = values[origin + i]; i = i + 1 }
}
}
function show(values: List<Character>) {
let i = 0
while i < values.length { print(values[i]); i = i + 1 }
}
function buffer(count: Integer): List<Character> {
let values: List<Character> = []
let i = 0
while i < count { values.add('.'); i = i + 1 }
return values
}
let first = buffer(20)
let i = 0
while i < 20 { if i < 10 { first[i] = 'A' } else { first[i] = 'B' }; i = i + 1 }
show(first)
move(first, 10, 0, 10)
show(first)
let suffix = buffer(100)
suffix[95] = 'h'; suffix[96] = 'e'; suffix[97] = 'l'; suffix[98] = 'l'; suffix[99] = 'o'
show(suffix)
move(suffix, 92, 95, 5)
show(suffix)
move(suffix, 94, 92, 5)
show(suffix)
let small = buffer(8)
small[0] = 'h'; small[1] = 'e'; small[2] = 'l'; small[3] = 'l'; small[4] = 'o'
show(small)
move(small, 3, 0, 5)
show(small)
move(small, 2, 3, 5)
show(small)
'''
        states = ['A' * 10 + 'B' * 10, 'A' * 20, '.' * 95 + 'hello',
                  '.' * 92 + 'hellollo', '.' * 92 + 'hehelloo',
                  'hello...', 'helhello', 'hehelloo']
        self.executes(source, ''.join(character + '\n' for state in states for character in state))


    def test_checked_integer_power_source_vectors(self):
        fixture = ROOT / 'tests/peer-rgz-power-vectors.json'
        self.evidence.inputs[str(fixture.resolve())] = digest(fixture)
        vectors = json.loads(fixture.read_text())
        self.assertEqual(len(vectors), 71)
        self.assertEqual(len({item['case_id'] for item in vectors}), 71)
        helper = '''function power(base: Integer, exponent: Integer): Integer {
let result = 1
let factor = base
let remaining = exponent
while remaining > 0 {
if remaining % 2 == 1 { result = result * factor }
remaining = remaining / 2
if remaining > 0 { factor = factor * factor }
}
return result
}
'''
        source, expected, overflows = helper, [], set()
        for item in vectors:
            _, kind, base_text, exponent_text = item['case_id'].split('/')
            base, exponent = item['base'], item['exponent']
            self.assertEqual((base, exponent), (int(base_text), int(exponent_text)))
            self.assertGreaterEqual(exponent, 0)
            value = pow(base, exponent)
            if -(1 << 63) <= value < (1 << 63):
                source += f'print(power({base}, {exponent}))\n'
                expected.append(value)
            else:
                overflows.add((base, exponent))
        self.assertEqual(len(expected), 56)
        self.assertEqual(len(overflows), 15)
        self.executes(source, ''.join(f'{n}\n' for n in expected))
        for base, exponent in sorted(overflows):
            with self.subTest(base=base, exponent=exponent):
                self.executes(helper + f'print(power({base}, {exponent}))\n', '', status=1,
                              stderr='Minyar stopped: this Integer calculation is outside the supported range.\n')


    def test_calendar_epoch_integer_decomposition(self):
        import calendar
        import datetime
        source = '''record DateParts { year: Integer; yearDay: Integer; month: Integer; day: Integer; hour: Integer; minute: Integer; second: Integer }
function leap(year: Integer): Boolean { return year % 4 == 0 && (year % 100 != 0 || year % 400 == 0) }
function yearDays(year: Integer): Integer { if leap(year) { return 366 }; return 365 }
function monthDays(year: Integer, month: Integer): Integer {
if month == 2 { if leap(year) { return 29 }; return 28 }
if month == 4 || month == 6 || month == 9 || month == 11 { return 30 }
return 31
}
function decode(seconds: Integer): DateParts {
let days = seconds / 86400
let year = 1970
while days >= yearDays(year) { days = days - yearDays(year); year = year + 1 }
let yearDay = days
let month = 1
while days >= monthDays(year, month) { days = days - monthDays(year, month); month = month + 1 }
let time = seconds % 86400
return DateParts { year: year; yearDay: yearDay; month: month; day: days; hour: time / 3600; minute: (time % 3600) / 60; second: time % 60 }
}
function show(parts: DateParts) {
print(parts.year); print(parts.yearDay); print(parts.month); print(parts.day)
print(parts.hour); print(parts.minute); print(parts.second)
}
'''
        expected = []
        for year in [2095, 2096, 2100, 2400]:
            source += f'print(leap({year}))\n'
            expected.append(str(calendar.isleap(year)).lower())
        for seconds in [0, 31535999, 1622924906, 1625159473]:
            source += f'show(decode({seconds}))\n'
            value = datetime.datetime(1970, 1, 1) + datetime.timedelta(seconds=seconds)
            expected += [str(n) for n in (value.year, value.timetuple().tm_yday - 1, value.month,
                                          value.day - 1, value.hour, value.minute, value.second)]
        self.executes(source, '\n'.join(expected) + '\n')

    def test_record_vector_field_access_and_unused_argument_effects(self):
        source = '''record Item { value: Integer }
function at(values: List<Item>, index: Integer): Item { return values[index] }
function side(counter: List<Integer>): Integer { counter[0] = counter[0] + 1; return 1 }
function ignored(value: Integer) {}
function ignoredPair(first: Integer, second: Integer) {}
function ignoredReceiver(receiver: Integer) {}
function receiverWithIgnored(receiver: Integer, argument: Integer) {}
let values = [Item { value: 44444 }, Item { value: 3333 }, Item { value: 222 }, Item { value: 11 }, Item { value: 0 }]
let output = "hi" + Text('\n')
let i = 0
while i < values.length {
let item = at(values, i)
output = output + Text(i) + " " + Text(item.value) + Text('\n')
i = i + 1
}
i = 0
while i < values.length {
output = output + Text(i) + " " + Text(at(values, i).value) + Text('\n')
i = i + 1
}
print(output)
let counter = [0]
ignored(side(counter)); print(counter[0])
ignoredPair(side(counter), side(counter)); print(counter[0])
ignoredPair(side(counter), side(counter)); print(counter[0])
ignoredReceiver(side(counter)); print(counter[0])
receiverWithIgnored(1, side(counter)); print(counter[0])
'''
        lines = 'hi\n' + ''.join(f'{i} {n}\n' for _ in range(2) for i, n in enumerate([44444, 3333, 222, 11, 0]))
        self.executes(source, lines + '\n1\n3\n5\n6\n7\n')

    def test_nested_integer_division_grouping(self):
        source = '''function divide(a: Integer, b: Integer): Integer { return a / (a / b) }
print(5 / (5 / 3))
print(5 / (5 / 3))
print(divide(5, 3))
let values = [2, 3, 5]
print(values[2] / (values[2] / values[1]))
let tail = [values[1], values[2]]
print(tail[1] / (tail[1] / tail[0]))
'''
        self.executes(source, '5\n' * 5)


    def test_integer_expression_pressure_and_negated_call(self):
        names = [f'v{i}' for i in range(33)]
        terms = ' + '.join(f'{name} + {i % 10 + 1}' for i, name in enumerate(names))
        source = 'function sum(values: List<Integer>): Integer {\n'
        source += ''.join(f'let {name} = values[{i}]\n' for i, name in enumerate(names))
        source += 'return ' + terms + '\n}\n'
        source += '''function grouped(w: Integer, x: Integer, y: Integer, z: Integer): Integer { return (w + (x + 3) + 3) * (y + 3 + z * 3) }
function computed(n: Integer): Integer {
let total = 0
let i = 0
while i < n { total = total + i / 2; i = i + 1 }
return total
}
function formula(values: List<Integer>): Integer {
'''
        source += ''.join(f'let d{i} = values[0]\n' for i in range(1, 13))
        source += 'return d1 + d2 * d3 + d4 * d5 + d6 * d7 + d8 * d9 + d10 * d11 + d12\n}\n'
        factors = list('abcd') * 4
        nested = factors[-1]
        for name in reversed(factors[:-1]):
            nested = f'{name} * ({nested})'
        source += 'function nested(a: Integer, b: Integer, c: Integer, d: Integer): Integer { return ' + nested + ' }\n'
        source += 'print(sum([' + ', '.join(['0'] * 33) + ']))\n'
        source += 'print(sum([' + ', '.join(str(i) for i in range(33)) + ']))\n'
        source += '''print(grouped(0, 0, 0, 0))
print(grouped(1, 2, 3, 4))
print(formula([1]))
print(nested(1, 1, 1, 1))
print(-computed(100))
let denominators = [48, 46]
print(7 / denominators[0]); print(1 / denominators[1]); print(0 / denominators[0])
print(48 / denominators[0]); print((5 * 48) / denominators[0])
'''
        self.executes(source, '171\n699\n18\n162\n7\n1\n-2450\n0\n0\n0\n1\n5\n')

    def test_record_list_assignment_evaluates_index_once(self):
        self.executes('''record Container { values: List<Integer> }
function index(counter: List<Integer>): Integer { counter[0] = counter[0] + 1; return 0 }
let counter = [0]
let container = Container { values: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0] }
container.values[index(counter)] = 1
print(counter[0])
print(container.values[0])
print(container.values.length)
''', '1\n1\n10\n')

    def test_record_list_field_store_order_growth_and_types(self):
        source = '''record Inner { values: List<Text> }
record Outer { child: Inner }
function index(trace: List<Text>): Integer { trace.add("I"); return 1 }
function replacement(values: List<Text>, trace: List<Text>): Text {
trace.add("R")
values[1] = "temporary" + Text(trace.length)
let i = 0
while i < 256 { values.add("item-" + Text(i)); i = i + 1 }
return "replacement-" + Text(trace.length)
}
let outer = Outer { child: Inner { values: ["left", "old-" + Text(0)] } }
let alias = outer.child.values
let trace: List<Text> = []
outer.child.values[index(trace)] = replacement(alias, trace)
print(joinText(trace))
print(alias.length)
print(outer.child.values.length)
let i = 0
while i < alias.length { print(alias[i]); print(outer.child.values[i]); i = i + 1 }
'''
        values = ['left', 'replacement-2', *[f'item-{i}' for i in range(256)]]
        self.executes(source, 'IR\n258\n258\n' + ''.join(value + '\n' + value + '\n' for value in values))
        prefix = 'record Box { values: List<Text> }\nlet box = Box { values: ["text"] }\n'
        for source, diagnostic in [
            (prefix + 'box.values[0] = 1\n', 'an indexed assignment needs Text, not Integer'),
            (prefix + 'box.values[true] = "text"\n', 'a position must be an Integer'),
            ('record Box { value: Integer }\nlet box = Box { value: 1 }\nbox.value[0] = 2\n', 'indexed assignment needs a List'),
            ('record Node { children: List<Node> }\nlet empty: List<Node> = []\nlet node = Node { children: empty }\nnode.children[0] = node\n',
             'List position 0'),
        ]:
            with self.subTest(source=source):
                if diagnostic == 'List position 0':
                    from feature_compiler import accepts_managed_graph
                    accepts_managed_graph(self, source)
                else:
                    self.rejects(source, diagnostic)

    def test_mutual_recursion_accumulates_fibonacci_leaves(self):
        source = ''
        # Read-only pointer parameters become Integers; four distinct call orders remain.
        branches = {'f': [('g', 'xm1', 'xm2', 'next'), ('h', 'xm2', 'next', 'older')],
                    'g': [('k', 'xm2', 'next', 'older'), ('h', 'xm1', 'xm2', 'next')],
                    'h': [('k', 'xm1', 'xm2', 'next'), ('f', 'xm2', 'next', 'older')],
                    'k': [('f', 'xm2', 'next', 'older'), ('g', 'xm1', 'xm2', 'next')]}
        for name, calls in branches.items():
            source += f'function {name}(x: Integer, xm1: Integer, xm2: Integer, total: List<Integer>) {{\n'
            source += 'let older = x - 4\nif x < 2 { total[0] = total[0] + x; return }\nlet next = x - 3\n'
            source += ''.join(f'{callee}({a}, {b}, {c}, total)\n' for callee, a, b, c in calls) + '}\n'
        expected = []
        for n in (12, 20):
            source += f'let sum{n} = [0]\nf({n}, {n - 1}, {n - 2}, sum{n})\nprint(sum{n}[0])\n'
            a, b = 0, 1
            for _ in range(n):
                a, b = b, a + b
            expected.append(a)
        self.executes(source, ''.join(f'{n}\n' for n in expected))

    def test_empty_dynamic_text_slice_then_large_index_rejects(self):
        for trace in (False, True):
            # The checked-add sibling prints this reachable diagnostic before
            # failing; the SCEV sibling does not. Minyar has no nonfatal stderr
            # API, so the complete four-value trace is asserted on stdout.
            source = '''function inspect(x: Integer) {
let roots = ["abc"]
'''
            source += 'let z: List<Integer> = []\n' if trace else 'let z = [0]\n'
            source += '''
let row = 0
while row < roots.length {
let y = 0
while y < x {
let inner = 0
while inner < 1 {
let count = 0
'''
            source += ('while count < x { z.add(0); count = count + 1 }\n' if trace else
                       'while count < x { z[0] = 0; count = count + 1 }\n')
            source += '''
let start = y * x
let end = (y + 1) * x - 1
let view = roots[row].slice(start, end)
'''
            if trace:
                source += 'print(Text(start) + " " + Text(end) + " " + Text(roots[row].length) + " " + Text(view.length))\n'
            source += '''
print(view[16777216])
inner = inner + 1
}
y = y + 1
}
row = row + 1
}
}
inspect(1)
inspect(2)
'''
            with self.subTest(source_variant='checked-add-trace' if trace else 'SCEV'):
                self.executes(source, '0 0 3 0\n' if trace else '', status=1,
                              stderr='Minyar stopped: a Text position was outside the Text.\n')


    def test_failure_text_values_and_full_large_message(self):
        for expression, value in [('Text(8)', '8'), ('Text(true)', 'true'), ('"test"', 'test')]:
            self.executes(f'fail({expression})\n', '', status=1, stderr=f'Minyar stopped: {value}\n')
        self.executes('''function chunk(value: Text): Text {
let result = ""
let i = 0
while i < 1024 { result = result + value; i = i + 1 }
return result
}
let first = chunk("0")
let second = chunk("1")
let third = chunk("2")
let fourth = chunk("3")
fail(first + second + third + fourth)
''', '', status=1, stderr='Minyar stopped: ' + ''.join(str(i) * 1024 for i in range(4)) + '\n')

    def test_large_index_displacements_remain_signed64(self):
        self.executes('''record Position { index: Integer }
function get(position: Position): Integer { let values = [3, 4]; return values[position.index] }
print(get(Position { index: 4294967297 }))
''', '', status=1, stderr='Minyar stopped: List position 4294967297 is outside its length of 2.\n')
        for offset in (1073741824, 2147483648):
            helper = f'function get(values: List<Integer>, i: Integer): Integer {{ return values[i + {offset}] }}\n'
            self.executes(helper + f'print(get([42], -{offset}))\nprint(get([42], 0))\n', '42\n', status=1,
                          stderr=f'Minyar stopped: List position {offset} is outside its length of 1.\n')
        for offset in (1610612736, 1610612746, 1610612726):
            helper = f'''function get(values: List<Text>, i: Integer): Text {{
if i > {offset} {{ return values[i - {offset}] }}
return ""
}}
let values = ["zero", "one"]
'''
            source = helper + ''.join(f'print(get(values, {i}))\n' for i in (offset - 1, offset, offset + 1, offset + 2))
            self.executes(source, '\n\none\n', status=1,
                          stderr='Minyar stopped: List position 2 is outside its length of 2.\n')


    def test_frontend_binding_and_expression_diagnostics(self):
        fixture = ROOT / 'tests/peer-rgz-frontend-vectors.json'
        self.evidence.inputs[str(fixture.resolve())] = digest(fixture)
        vectors = json.loads(fixture.read_text())
        self.assertEqual(len(vectors), 24)
        self.assertEqual(len({row['id'] for row in vectors}), 24)
        for row in vectors:
            with self.subTest(case=row['id']):
                result, llvm = self.compile(row['source'])
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, '')
                self.assertEqual(result.stderr, row['diagnostic'])
                self.assertFalse(llvm.exists())

    def test_grouped_discard_and_empty_list_runtime_bounds(self):
        self.executes('((1 + 1))\nprint(42)\n', '42\n')
        self.executes('''function get(index: Integer): Integer { let values: List<Integer> = []; return values[index] }
print(get(0))
''', '', status=1, stderr='Minyar stopped: List position 0 is outside its length of 0.\n')
        self.executes('''function inspect(start: Integer) {
let text = "abcde"
text.slice(start, 5).slice(0, 10)
}
inspect(6)
''', '', status=1, stderr='Minyar stopped: a Text slice must stay within the Text and end after it starts.\n')


    def test_parameter_shadowing_and_independent_literal_lengths(self):
        self.executes('''function parameters(i: Integer, f: Integer) { i = 8; f = 8; print(i); print(f) }
function shadow(x: Integer) { print(x); let x = 7; print(x) }
function first() { let x = 0; print(x) }
function second() { let x = 0; print(x) }
function local() { let a = 5; print(a) }
function parameter(a: Integer) { a = 0; print(a) }
let a = 0
parameters(3, 5)
shadow(3)
first(); second(); local(); parameter(9); print(a)
let one = [0]
let two = [0, 1]
print(one.length); print(one[0]); print(two.length); print(two[0]); print(two[1]); print(one.length)
''', '8\n8\n3\n7\n0\n0\n5\n0\n0\n1\n0\n2\n0\n1\n1\n')

    def test_list_builtin_argument_order_across_rebinding(self):
        self.executes('''function replace(slot: List<List<Integer>>, count: Integer): Integer {
let fresh: List<Integer> = []
let i = 0
while i < count { fresh.add(0); i = i + 1 }
slot[0] = fresh
return 2
}
function lists(first: List<Integer>, middle: Integer, last: List<Integer>) { print(first.length); print(middle); print(last.length) }
function numbers(first: Integer, middle: Integer, last: Integer) { print(first); print(middle); print(last) }
function make(count: Integer): List<Integer> {
let fresh: List<Integer> = []
let i = 0
while i < count { fresh.add(0); i = i + 1 }
return fresh
}
let empty: List<Integer> = []
let appendSlot = [empty]
lists(appendSlot[0].appended(1), replace(appendSlot, 2), appendSlot[0].appended(1))
let lengthSlot = [[0]]
numbers(lengthSlot[0].length, replace(lengthSlot, 3), lengthSlot[0].length)
let makeSlot = [[0]]
lists(make(makeSlot[0].length), replace(makeSlot, 3), make(makeSlot[0].length))
''', '1\n2\n3\n' * 3)

    def test_same_file_import_record_identity_and_recursive_children(self):
        (self.directory / 'rgz-library.min').write_text('''public record Item { value: Integer }
public function accept(value: Item): Integer { return value.value }
public function foo(): Integer { return 1234 }
''')
        self.executes('''use "./rgz-library.min" as first
use "././rgz-library.min" as second
record Node { value: Integer; children: List<Node> }
function node(value: Integer, children: List<Node>): Node { return Node { value: value; children: children } }
let item = first.Item { value: 42 }
print(second.accept(item))
print(first.foo())
let empty: List<Node> = []
let root = node(1, [node(42, empty)])
print(root.children.length)
print(root.children[0].value)
print(root.children[0].children.length)
''', '42\n1234\n1\n42\n0\n')
        self.rejects('use "./rgz-library.min" as library\nlibrary(0)\n', "I can't find a function named 'library'")


    def test_five_thousand_text_fields_and_accessors_compile(self):
        names = [f'H{i:06X}' for i in range(5000)]
        self.assertEqual(len(set(names)), 5000)
        source = 'record Wide {\n' + ''.join(f'{name}: Text\n' for name in names) + '}\n'
        source += ''.join(f'function get{name}(value: Wide): Text {{ return value.{name} }}\n' for name in names)
        # Upstream is a build-only stress test. Nullability/getter methods become Text fields/functions.
        result, llvm = self.compile(source)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')
        self.assertTrue(llvm.exists())
        emitted = llvm.read_text()
        for name in names:
            self.assertIn('get' + name, emitted)
        # The upstream generator invokes `go build`, so successful textual IR
        # emission alone is insufficient. Validate and link every selected
        # backend configuration; the source does not execute the built program.
        from regressions import CLANG, LINK_FLAGS, RUNTIME
        variants = ('-O0', '-O2', '-O3', '-Os') if os.environ.get('MINYAR_TEST_EXTENDED_OPT') == '1' else ('-O0', '-O2')
        for optimization in variants:
            with self.subTest(optimization=optimization):
                executable = llvm.with_suffix('.' + optimization[1:])
                linked = self.evidence.run(clang_command([CLANG, optimization, *LINK_FLAGS, '-Wno-override-module',
                                            llvm, RUNTIME, '-o', executable]), timeout=30,
                                           phase='link-wide-record-build')
                self.assertEqual(linked.returncode, 0, linked.stderr)
                self.assertTrue(executable.is_file())

    def test_empty_import_driver_cold_warm_and_declaration_transitions(self):
        import sys
        module = self.directory / 'rgz-empty.min'
        entry = self.directory / 'rgz-empty-main.min'
        entry.write_text('use "./rgz-empty.min" as empty\nprint(42)\n')
        shim_directory = self.directory / 'rgz-empty-tools'
        shim_directory.mkdir()
        shim = shim_directory / 'make'
        shim.write_text('#!' + sys.executable + '\n' +
                        'import pathlib, sys\n' +
                        'assert sys.argv[1:3] == ["-s", "-C"]\n' +
                        'root = pathlib.Path(sys.argv[3])\n' +
                        'assert root == pathlib.Path(' + repr(str(ROOT)) + ')\n' +
                        'assert sys.argv[4:]\n' +
                        'assert all((root / target).is_file() for target in sys.argv[4:])\n')
        shim.chmod(0o755)
        for dependency in [shim, ROOT / 'minyar', ROOT / 'build/minyarc',
                           ROOT / 'build/minyarc-modules', ROOT / 'build/minyar-module-build',
                           ROOT / 'build/minyar-default-runtime.o']:
            self.evidence.inputs[str(dependency)] = digest(dependency)
        # The direct path uses the selected native/sanitized compiler and runtime.
        # The public driver uses existing production artifacts, with its own cache;
        # the shim verifies targets and prevents rebuilding shared artifacts.
        env = {**os.environ, 'PATH': str(shim_directory) + os.pathsep + os.environ['PATH'],
               'MINYAR_MODULE_CACHE': str(self.directory / 'rgz-empty-cache'),
               'MINYAR_CLANG_FLAGS': '-O2 -Wno-override-module'}
        for key in ('MINYAR_CLANG', 'MINYAR_RUNTIME_FLAGS'):
            env.pop(key, None)
        for stage, contents in [('empty', ''), ('comments', '// no declarations\n'),
                                ('declaration', 'public function value(): Integer { return 7 }\n'),
                                ('removed', '')]:
            module.write_text(contents)
            expression = 'empty.value()' if stage == 'declaration' else '42'
            expected = '7\n' if stage == 'declaration' else '42\n'
            entry.write_text('use "./rgz-empty.min" as empty\nprint(' + expression + ')\n')
            with self.subTest(stage=stage):
                self.executes(entry.read_text(), expected)
                for mode in ('direct', 'incremental-first', 'incremental-warm'):
                    executable = self.directory / f'rgz-empty-{stage}-{mode}'
                    command = [ROOT / 'minyar']
                    if mode != 'direct':
                        command.append('--incremental')
                    command += [entry, '-o', executable]
                    built = self.evidence.run(command, env=env, timeout=30, phase='driver-empty-import-' + mode)
                    self.assertEqual((built.returncode, built.stdout, built.stderr),
                                     (0, f'built {executable}\n'.encode(), b''))
                    result = self.evidence.run([executable], timeout=30, phase='execute-empty-import-' + mode)
                    self.assertEqual((result.returncode, result.stdout, result.stderr), (0, expected.encode(), b''))
        # Removing the declaration must also invalidate a former use of it.
        entry.write_text('use "./rgz-empty.min" as empty\nprint(empty.value())\n')
        missing = self.directory / 'rgz-empty-missing'
        result = self.evidence.run([ROOT / 'minyar', '--incremental', entry, '-o', missing],
                                   env=env, timeout=30, phase='driver-empty-import-removed-declaration')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b'')
        self.assertEqual(result.stderr,
                         f"Minyar stopped: {entry}:2, column 7: module 'empty' has no function named 'value'\n".encode())
        self.assertFalse(missing.exists())


    def test_full_signed64_constant_and_parameter_matrix(self):
        fixture = ROOT / 'tests/peer-rgz-signed64-values.json'
        self.evidence.inputs[str(fixture.resolve())] = digest(fixture)
        values = json.loads(fixture.read_text())
        self.assertEqual(len(values), 33)
        self.assertEqual(len(set(values)), 33)
        minimum, maximum = -(1 << 63), (1 << 63) - 1
        symbols = ('+', '-', '*', '/', '%')
        overflow = 'Minyar stopped: this Integer calculation is outside the supported range.\n'
        source = 'function value(index: Integer): Integer {\n'
        source += ''.join(f'if index == {i} {{ return {n} }}\n' for i, n in enumerate(values))
        source += 'fail("invalid operand index")\n}\n'
        source += 'function index(text: Text): Integer {\n'
        source += ''.join(f'if text == "{i}" {{ return {i} }}\n' for i in range(33))
        source += 'fail("invalid matrix index")\n}\n'
        for operation, symbol in enumerate(symbols):
            source += f'function dynamic{operation}(a: Integer, b: Integer): Integer {{ return a {symbol} b }}\n'
            for placement in ('left', 'right'):
                source += f'function {placement}{operation}(fixed: Integer, variable: Integer): Integer {{\n'
                for i, n in enumerate(values):
                    # Source excludes division by zero and MIN/-1. A zero constant denominator
                    # remains absent, matching the original generator's binaryConstR0 branch.
                    if placement == 'right' and symbol in ('/', '%') and n == 0:
                        continue
                    expression = f'({n}) {symbol} variable' if placement == 'left' else f'variable {symbol} ({n})'
                    source += f'if fixed == {i} {{ return {expression} }}\n'
                source += 'fail("excluded matrix operation")\n}\n'
        source += 'function evaluate(op: Integer, placement: Integer, ai: Integer, bi: Integer): Integer {\n'
        for operation in range(5):
            source += f'''if op == {operation} {{
if placement == 0 {{ return dynamic{operation}(value(ai), value(bi)) }}
if placement == 1 {{ return left{operation}(ai, value(bi)) }}
return right{operation}(bi, value(ai))
}}
'''
        source += 'fail("invalid matrix operation")\n}\n'
        expected, failures, masks = [], [], []
        for op, symbol in enumerate(symbols):
            mask = []
            for ai, a in enumerate(values):
                for bi, b in enumerate(values):
                    if symbol in ('/', '%') and (b == 0 or (a == minimum and b == -1)):
                        mask.append('0')
                        continue
                    if symbol == '+': result = a + b
                    elif symbol == '-': result = a - b
                    elif symbol == '*': result = a * b
                    else:
                        quotient = abs(a) // abs(b)
                        if (a < 0) != (b < 0): quotient = -quotient
                        result = quotient if symbol == '/' else a - quotient * b
                    fits = minimum <= result <= maximum
                    mask.append('1' if fits else '0')
                    for placement in range(3):
                        if fits:
                            expected.append(result)
                        else:
                            failures.append(([str(op), str(placement), str(ai), str(bi)], overflow))
            masks.append(''.join(mask))
        self.assertEqual(len(failures), 2310)
        self.assertEqual(len(expected), 13821)
        source += 'let mode = argument(0)\nif mode == "success" {\n'
        for op, mask in enumerate(masks):
            source += f'let mask{op} = "{mask}"\nlet ai{op} = 0\nwhile ai{op} < 33 {{\nlet bi{op} = 0\nwhile bi{op} < 33 {{\n'
            source += f"if mask{op}[ai{op} * 33 + bi{op}] == '1' {{\n"
            source += ''.join(f'print(evaluate({op}, {p}, ai{op}, bi{op}))\n' for p in range(3))
            source += f'}}\nbi{op} = bi{op} + 1\n}}\nai{op} = ai{op} + 1\n}}\n'
        source += '} else { print(evaluate(index(argument(0)), index(argument(1)), index(argument(2)), index(argument(3)))) }\n'
        llvm = self.executes(source, ''.join(f'{n}\n' for n in expected), arguments=['success'])
        self.evidence.controls['signed64_matrix'] = {'values': values, 'success_instances': len(expected),
            'overflow_instances': len(failures), 'placements': ['var-var', 'const-var', 'var-const'],
            'excluded_divmod': 'denominator0 and MIN/-1 exactly as upstream; no other exclusion',
            'overflow_cases': [arguments for arguments, _ in failures]}
        variants = ('-O0', '-O2', '-O3', '-Os') if os.environ.get('MINYAR_TEST_EXTENDED_OPT') == '1' else ('-O0', '-O2')
        normal_only = os.environ.get('MINYAR_RGZ_MATRIX_NORMAL_ONLY') == '1'
        self.evidence.controls['signed64_matrix']['normal_exit_only'] = normal_only
        coverage = {'safe_cells_per_configuration': len(expected),
                    'overflow_cells_per_configuration': len(failures),
                    'overflow_processes_executed': 0, 'configurations': list(variants)}
        self.evidence.controls['domain_coverage'] = {'signed64_matrix': coverage}
        if normal_only:
            self.evidence.controls['domain_exclusions'] = [{
                'domain': 'signed64 overflow and minimum-value negation',
                'instances_per_configuration': len(failures) + 1,
                'reason': 'MINYAR_RGZ_MATRIX_NORMAL_ONLY selects normal-exit ownership cases'}]
        for optimization in variants:
            exe = llvm.with_suffix('.' + optimization[1:])
            for arguments, diagnostic in ([] if normal_only else failures):
                with self.subTest(optimization=optimization, arguments=arguments):
                    result = self.evidence.run([exe, *arguments], timeout=30, phase='execute-matrix-overflow')
                    coverage['overflow_processes_executed'] += 1
                    self.assertEqual((result.returncode, result.stdout, result.stderr), (1, b'', diagnostic.encode()))
        # Unary source domain is separate from the binary generator.
        unary = 'function negate(value: Integer): Integer { return -value }\n'
        self.executes(unary + ''.join(f'print(negate({n}))\n' for n in values if n != minimum),
                      ''.join(f'{-n}\n' for n in values if n != minimum))
        if not normal_only:
            self.executes(unary + f'print(negate({minimum}))\n', '', status=1, stderr=overflow)


    def test_go_frontend_supported_shape_diagnostics(self):
        fixture = ROOT / 'tests/peer-rgz-go-frontend-vectors.json'
        self.evidence.inputs[str(fixture.resolve())] = digest(fixture)
        vectors = json.loads(fixture.read_text())
        self.assertEqual(len(vectors), 21)
        self.assertEqual(len({row['id'] for row in vectors}), 21)
        for row in vectors:
            with self.subTest(case=row['id']):
                result, llvm = self.compile(row['source'])
                self.assertEqual((result.returncode, result.stdout, result.stderr), (1, '', row['diagnostic']))
                self.assertFalse(llvm.exists())

    def test_escaped_character_and_text_index_assignment(self):
        self.executes(r'''let controls = "\n\r\t"
print(controls)
print(controls.length)
print('\'')
print('\\')
print("\"")
function put(buffer: List<Character>, index: Integer, value: Integer, digits: Text) { buffer[index] = digits[value] }
let buffer: List<Character> = ['.', '.', '.']
put(buffer, 1, 2, "0123456789")
print(buffer[0]); print(buffer[1]); print(buffer[2])
''', '\n\r\t\n3\n\'\n\\\n"\n.\n2\n.\n')


    def test_truncated_utf8_source_and_invalid_import_paths(self):
        from regressions import COMPILER, COMPILE_TIMEOUT
        malformed = self.directory / 'rgz-invalid-utf8.min'
        malformed.write_bytes(b'function f() {\xef\xef')
        output = malformed.with_suffix('.ll')
        result = self.evidence.run([COMPILER, malformed, output], capture_output=True, timeout=COMPILE_TIMEOUT, phase='compile-invalid-utf8')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b'')
        self.assertIn(b'invalid UTF-8', result.stderr)
        self.assertFalse(output.exists())
        (self.directory / 'rgz-valid.min').write_text('public function get(): Integer { return 42 }\n')
        for name, source, diagnostic in [
            ('empty', 'use "" as empty\n', "Minyar stopped: package module '' is not available yet; local modules begin with './' or '../'\n"),
            ('nul', 'use "./rgz-valid.min\0suffix" as valid\nprint(valid.get())\n', 'Minyar stopped: a file path cannot contain a zero byte.\n'),
        ]:
            with self.subTest(import_path=name):
                result, llvm = self.compile(source)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (1, '', diagnostic))
                self.assertFalse(llvm.exists())


        # Exercise the real driver with a make shim that verifies existing artifacts.
        # No build tool or shared artifact rebuild is performed by this fixture.
        import sys
        tools = self.directory / 'rgz-driver-tools'
        tools.mkdir()
        shim = tools / 'make'
        shim.write_text('#!' + sys.executable + '\n' +
                        'import pathlib, sys\n' +
                        'assert sys.argv[1:3] == ["-s", "-C"]\n' +
                        'root = pathlib.Path(sys.argv[3])\n' +
                        'assert root == pathlib.Path(' + repr(str(ROOT)) + ')\n' +
                        'assert sys.argv[4:]\n' +
                        'assert all((root / target).is_file() for target in sys.argv[4:])\n')
        shim.chmod(0o755)
        self.evidence.inputs[str(shim)] = digest(shim)
        self.evidence.inputs[str(ROOT / 'minyar')] = digest(ROOT / 'minyar')
        env = {**os.environ, 'PATH': str(tools) + os.pathsep + os.environ['PATH']}
        for name, source, diagnostic in [
            ('empty', 'use "" as empty\n', f"Minyar stopped: the file '{ROOT / 'library/.min'}' could not be opened.\n"),
            ('nul', 'use "./rgz-valid.min\0suffix" as valid\nprint(valid.get())\n', 'Minyar stopped: a file path cannot contain a zero byte.\n'),
        ]:
            path = self.directory / ('rgz-driver-' + name + '.min')
            path.write_text(source)
            executable = self.directory / ('rgz-driver-' + name)
            result = self.evidence.run([ROOT / 'minyar', path, '-o', executable], env=env,
                                       timeout=30, phase='driver-invalid-import-existing-artifacts')
            self.assertEqual((result.returncode, result.stdout, result.stderr), (1, b'', diagnostic.encode()))
            self.assertFalse(executable.exists())

    def test_guarded_page_end_bounds_precede_later_loads(self):
        from regressions import CLANG, LINK_FLAGS, RUNTIME
        fixture = ROOT / 'tests/peer-rgz-guarded-end.c'
        self.evidence.inputs[str(fixture.resolve())] = digest(fixture)
        variants = ('-O0', '-O2', '-O3', '-Os') if os.environ.get('MINYAR_TEST_EXTENDED_OPT') == '1' else ('-O0', '-O2')
        for optimization in variants:
            exe = self.directory / ('guarded-end-' + optimization[1:])
            linked = self.evidence.run(clang_command([CLANG, '-std=c11', optimization, *LINK_FLAGS, fixture, RUNTIME, '-o', exe]), timeout=30, phase='link-guarded-end')
            self.assertEqual(linked.returncode, 0, linked.stderr)
            for kind, diagnostic in [('list', 'List position 1 is outside its length of 1.'), ('text', 'a Text position was outside the Text.')]:
                for count in (2, 4, 8):
                    for placement in ('constant', 'dynamic'):
                        with self.subTest(optimization=optimization, kind=kind, count=count, placement=placement):
                            result = self.evidence.run([exe, kind, str(count), placement], timeout=30, phase='execute-guarded-end')
                            self.assertEqual((result.returncode, result.stdout, result.stderr),
                                             (1, b'', ('Minyar stopped: ' + diagnostic + '\n').encode()))


    def test_allocator_fail_ordinals_and_nonlast_move_accounting(self):
        from regressions import CLANG, LINK_FLAGS
        fixture = ROOT / 'tests/peer-rgz-allocator-probe.c'
        for dependency in [fixture, ROOT / 'tests/allocation-fault-runtime.c', ROOT / 'runtime/minyar_runtime.c', *sorted((ROOT / 'runtime').glob('*.h'))]:
            self.evidence.inputs[str(dependency.resolve())] = digest(dependency)
        variants = ('-O0', '-O2', '-O3', '-Os') if os.environ.get('MINYAR_TEST_EXTENDED_OPT') == '1' else ('-O0', '-O2')
        env = {k: v for k, v in os.environ.items() if not k.startswith('MINYAR_FAIL_') and not k.startswith('MINYAR_FAULT_')}
        source = '''let first = [1, 2]
let second = [3, 4]
let alias = first
let next = 3
while next <= 40 { first.add(next); next = next + 1 }
print(first.length); print(alias.length)
let i = 0
while i < first.length { print(first[i]); print(alias[i]); i = i + 1 }
print(second[0]); print(second[1])
alias[0] = 99
print(first[0]); print(second[0])
'''
        compiled, llvm = self.compile(source)
        self.assertEqual((compiled.returncode, compiled.stdout, compiled.stderr), (0, '', ''))
        expected = [40, 40, *[n for n in range(1, 41) for _ in range(2)], 3, 4, 99, 3]
        for optimization in variants:
            exe = self.directory / ('allocator-' + optimization[1:])
            linked = self.evidence.run(clang_command([CLANG, '-std=c11', optimization, *LINK_FLAGS, fixture, '-o', exe]), timeout=30, phase='link-allocator-probe')
            self.assertEqual(linked.returncode, 0, linked.stderr)
            for mode, extra, allocations, resizes, moved, fired in [
                ('allocate', {'MINYAR_FAIL_ALLOCATION': '3'}, 3, 0, 0, 1),
                ('resize', {'MINYAR_FAIL_RESIZE': '2'}, 2, 3, 1, 2),
                ('move', {}, 2, 1, 1, 0),
            ]:
                report_path = self.directory / f'{mode}-{optimization[1:]}.json'
                run = self.evidence.run([exe, mode], env={**env, **extra, 'MINYAR_ALLOCATION_REPORT': str(report_path)}, timeout=30, phase='execute-allocator-probe')
                self.assertEqual((run.returncode, run.stdout, run.stderr), (0, b'', b''))
                report = json.loads(report_path.read_text())
                self.assertEqual((report['allocations'], report['resizes'], report['moved'], report['fired'], report['live_bytes']),
                                 (allocations, resizes, moved, fired, 0))
            # The same forced-moving wrapper now executes generated language code,
            # with a second live List and an alias spanning each storage resize.
            # Disable its optional frame cache so the final raw-byte accounting
            # observes complete reclamation, including the finished owner frame.
            executable = self.directory / ('moving-list-' + optimization[1:])
            linked = self.evidence.run(clang_command([CLANG, '-std=c11', optimization, *LINK_FLAGS, '-Wno-override-module',
                                        '-DMINYAR_FRAME_CACHE_BYTES=0',
                                        llvm, ROOT / 'tests/allocation-fault-runtime.c', '-o', executable]),
                                       timeout=30, phase='link-forced-moving-list')
            self.assertEqual(linked.returncode, 0, linked.stderr)
            report_path = self.directory / ('moving-list-' + optimization[1:] + '.json')
            run = self.evidence.run([executable], env={**env, 'MINYAR_ALLOCATION_REPORT': str(report_path)},
                                   timeout=30, phase='execute-forced-moving-list')
            self.assertEqual((run.returncode, run.stdout, run.stderr),
                             (0, ''.join(f'{value}\n' for value in expected).encode(), b''))
            report = json.loads(report_path.read_text())
            self.assertGreater(report['resizes'], 0)
            self.assertEqual(report['moved'], report['resizes'])
            self.assertEqual((report['fired'], report['live_bytes']), (0, 0))


    def _executes_rgz_binary_file_roundtrip(self, source, expected, arguments, output, payload):
        import base64
        from regressions import CLANG, LINK_FLAGS, RUNTIME, RUN_TIMEOUT
        self.evidence.controls.setdefault('binary_oracles',[]).append({'stdout_base64':base64.b64encode(expected).decode(),'written_base64':base64.b64encode(payload).decode(),'status':0,'stderr':''})
        result, llvm=self.compile(source)
        self.assertEqual((result.returncode,result.stdout,result.stderr),(0,'',''))
        variants = ('-O0', '-O2', '-O3', '-Os') if os.environ.get('MINYAR_TEST_EXTENDED_OPT') == '1' else ('-O0', '-O2')
        for optimization in variants:
            executable=llvm.with_suffix('.'+optimization[1:])
            result=self.evidence.run(clang_command([CLANG,optimization,*LINK_FLAGS,'-Wno-override-module',llvm,RUNTIME,'-o',executable]),timeout=30,phase='link')
            self.assertEqual(result.returncode,0,result.stderr)
            output.unlink(missing_ok=True)
            run=self.evidence.run([executable,*arguments],timeout=RUN_TIMEOUT,phase='execute')
            self.assertEqual((run.returncode,run.stdout,run.stderr),(0,expected,b''))
            self.assertEqual(output.read_bytes(),payload)


    def test_character_conversion_returns_owned_four_byte_text(self):
        self.executes('''function makeString(ch: Character): Text { return Text(ch) }
let ch = '😃'; print(ch)
let text = makeString(ch); print(text); print(text.byteLength); print(text.length)
''','😃\n😃\n4\n1\n')


    def test_empty_list_returned_through_both_helpers(self):
        self.executes('''function indirectGet(): List<Integer> { return [] }
function get(): List<Integer> { let ret = indirectGet(); return ret }
let output = get().length; print(output)
''','0\n')


    def test_singleton_axis_skips_empty_iterator_advance(self):
        self.executes('''record Iterator { values: List<Integer>; position: List<Integer>; calls: List<Integer> }
function next(iterator: Iterator) {
iterator.calls[0] = iterator.calls[0] + 1
if iterator.position[0] < iterator.values.length { iterator.position[0] = iterator.position[0] + 1 }
}
function removeAxis(values: List<Integer>, axis: Integer) {
let iterator = Iterator { values: []; position: [0]; calls: [0] }
let index = 0
while index < values.length {
print(values[index])
if index != axis { next(iterator) }
index = index + 1
}
print(index); print(iterator.calls[0]); print(iterator.position[0])
}
removeAxis([3], 0)
''','3\n1\n0\n0\n')


    def test_ordered_insertions_append_and_drain(self):
        self.executes('''function insert(values: List<Integer>, position: Integer, value: Integer) {
values.add(0); let index = values.length - 1
while index > position { values[index] = values[index - 1]; index = index - 1 }
values[position] = value
}
let receiver: List<Integer> = []; let donor = [0]
insert(donor, 0, 30); insert(donor, 1, 31); insert(donor, 2, 32)
insert(donor, 3, 33); insert(donor, 4, 34); insert(donor, 5, 35)
let index = 0
while index < donor.length { receiver.add(donor[index]); index = index + 1 }
donor = []
print(receiver.length); index = 0
while index < receiver.length { print(receiver[index]); index = index + 1 }
print(donor.length)
''','7\n30\n31\n32\n33\n34\n35\n0\n0\n')


    def test_owned_wrapper_reclaims_complete_list(self):
        self.executes('''record Wrapper { wrapped: List<Integer> }
function scoped() {
let wrapper = Wrapper { wrapped: [1, 2, 3, 4, 5] }
let index = 0
while index < wrapper.wrapped.length { print(wrapper.wrapped[index]); index = index + 1 }
}
scoped()
''','1\n2\n3\n4\n5\n')


    def test_writer_alias_advances_between_two_writes(self):
        self.executes('''record Writer { buffer: List<Integer>; offset: List<Integer>; remaining: List<Integer> }
function write(writer: Writer, input: List<Integer>) {
let amount = writer.remaining[0]
if input.length < amount { amount = input.length }
let index = 0
while index < amount { writer.buffer[writer.offset[0] + index] = input[index]; index = index + 1 }
writer.offset[0] = writer.offset[0] + input.length
writer.remaining[0] = writer.remaining[0] - input.length
}
let buffer = [0, 0, 0, 0, 0, 0]
let writer = Writer { buffer: buffer; offset: [0]; remaining: [6] }
let alias = writer
write(alias, [0, 1, 2]); write(alias, [3, 4, 5])
let index = 0
while index < buffer.length { print(buffer[index]); index = index + 1 }
print(writer.offset[0]); print(writer.remaining[0])
''','0\n1\n2\n3\n4\n5\n6\n0\n')


    def test_terminal_failure_prevents_later_list_append(self):
        self.executes('''let x: List<Integer> = []; let y = [3]
fail("so long")
let index = 0
while index < y.length { x.add(y[index]); index = index + 1 }
print("unreachable")
''','',status=1,stderr='Minyar stopped: so long\n')


    def test_twenty_text_self_doublings_preserve_every_character(self):
        self.executes('''let a = "A"; let i = 20; let expectedLength = 1
while i > 0 {
print(a.length)
if a.length != expectedLength { fail("wrong intermediate length") }
a = a + a; i = i - 1; expectedLength = expectedLength * 2
}
print(a.length); print(a.byteLength)
let index = 0
while index < a.length { if a[index] != 'A' { fail("wrong character") }; index = index + 1 }
print(index)
''',''.join(str(1<<i)+'\n' for i in range(20))+'1048576\n'*3)


    def test_space_equality_and_maximum_scalar_conversion(self):
        self.executes('''print(" " == " "); print(" ".length); print(" ".byteLength)
function encode(value: Character): Text { return Text(value) }
let variable = '􏿿'; let first = encode(variable)
print(first); print(first.byteLength); print(first.length)
let second = Text('􏿿')
print(second); print(second.byteLength); print(second.length)
''','true\n1\n1\n'+'\U0010ffff\n4\n1\n'*2)


    def test_global_and_local_character_list_roundtrips(self):
        self.executes('''function characters(text: Text): List<Character> {
let result: List<Character> = []; let index = 0
while index < text.length { result.add(text[index]); index = index + 1 }
return result
}
function reconstruct(values: List<Character>): Text {
let parts: List<Text> = []; let index = 0
while index < values.length { print(values[index]); parts.add(Text(values[index])); index = index + 1 }
return joinText(parts)
}
function local() { let input = "aä本☺"; let values = characters(input); input = "released"; print(reconstruct(values)) }
let input = "aä本☺"; let global = characters(input); input = "released"
print(reconstruct(global)); local()
''','a\nä\n本\n☺\naä本☺\n'*2)


    def test_file_byte_roundtrips_preserve_valid_and_invalid_utf8(self):
        for payload in ('aä本☺'.encode(),b'a\xc3\xa4\xff\xff\xe6\x9c\xac\xe2\x98\xba'):
            for scope in ('global','local'):
                with self.subTest(payload=payload,scope=scope):
                    path=self.directory/'input.bytes';output=self.directory/'output.bytes'
                    path.write_bytes(payload);self.evidence.inputs[str(path)]=digest(path)
                    body='''print(contents.byteLength); print(contents)
writeTextFile(argument(1), contents)
let copied = readTextFile(argument(1)); print(copied == contents); print(copied)
'''
                    source='let contents = readTextFile(argument(0))\n'+body
                    if scope=='local':source='function run() {\n'+source+'}\nrun()\n'
                    expected=str(len(payload)).encode()+b'\n'+payload+b'\ntrue\n'+payload+b'\n'
                    self._executes_rgz_binary_file_roundtrip(source,expected,(str(path),str(output)),output,payload)


    def test_invalid_byte_text_rejects_character_operations_lazily(self):
        path=self.directory/'invalid.bytes';payload=b'a\xc3\xa4\xff\xff\xe6\x9c\xac\xe2\x98\xba'
        path.write_bytes(payload);self.evidence.inputs[str(path)]=digest(path)
        for operation in ('text.length','text[0]'):
            self.executes('let text = readTextFile(argument(0))\nprint(text.byteLength)\nprint('+operation+')\nprint("after")\n',
                          '11\n',status=1,stderr='Minyar stopped: Text contained invalid UTF-8.\n',arguments=(str(path),))


    def test_ascii_classes_and_complete_whitespace_scan(self):
        source = _RGZ_ASCII_HELPERS + '''let whitespace = [32,9,10,13,11,12]
let w = 0
while w < whitespace.length { print(isWhitespace(whitespace[w])); w = w + 1 }
let i = 0
while isAscii(i) {
print(isAscii(i)); let classified = isWhitespace(i); print(classified)
let found = -1
if classified {
let j = 0
while j < whitespace.length { if whitespace[j] == i { found = j }; j = j + 1 }
if found < 0 { fail("classified byte missing from whitespace") }
}
print(found); i = i + 1
}
print(i); print(isAscii(i))
'''
        expected = [True]*6
        whitelist = (32,9,10,13,11,12)
        for c in range(128):
            expected += [True,c in whitelist,whitelist.index(c) if c in whitelist else -1]
        expected += [128,False]
        for fn,c,result in _RGZ_ASCII_CLASS_CASES:
            source += f'print({fn}({c}))\n'
            expected.append(result)
        self.executes(source,_rgz_ascii_output(expected))


    def test_case_conversion_preserves_full_byte_prefix_and_ownership(self):
        value = 'aBcDeFgHiJkLmNOPqrst0234+💩!'.encode('utf-8')
        lower = 'abcdefghijklmnopqrst0234+💩!'.encode('utf-8')
        upper = 'ABCDEFGHIJKLMNOPQRST0234+💩!'.encode('utf-8')
        source = _RGZ_ASCII_HELPERS + _RGZ_ASCII_CASE_HELPERS + 'let input = '+_rgz_ascii_byte_list(value)+'\n'
        source += '''let lowerBuffer: List<Integer> = []; let upperBuffer: List<Integer> = []
let i = 0
while i < 1024 { lowerBuffer.add(0); upperBuffer.add(0); i = i + 1 }
let lowerSpan = lowerString(lowerBuffer,input)
observe(lowerSpan)
observe(allocLowerString(input))
let upperSpan = upperString(upperBuffer,input)
observe(upperSpan)
observe(allocUpperString(input))
i = 0
while i < input.length { print(lowerBuffer[i]); print(upperBuffer[i]); print(input[i]); i = i + 1 }
lowerBuffer[0] = 88; upperBuffer[0] = 89
print(lowerSpan.values[0]); print(upperSpan.values[0])
'''
        expected = [1024,len(value),*lower,len(value),len(value),*lower,1024,len(value),*upper,len(value),len(value),*upper]
        for lower_byte,upper_byte,input_byte in zip(lower,upper,value):
            expected += [lower_byte,upper_byte,input_byte]
        expected += [88,89]
        self.executes(source,_rgz_ascii_output(expected))


    def test_case_conversion_capacity_precedes_all_writes(self):
        # Trace each attempted store before it mutates the caller's buffer.
        instrumented = _RGZ_ASCII_CASE_HELPERS
        for conversion in ('toLower','toUpper'):
            instrumented = instrumented.replace(f'destination[i] = {conversion}(source[i])',f'storeByte(destination,i,{conversion}(source[i]))')
        instrumented = 'function storeByte(destination: List<Integer>, i: Integer, value: Integer) { print(i); destination[i] = value }\n' + instrumented
        for fn in ('lowerString','upperString'):
            with self.subTest(function=fn):
                self.executes(_RGZ_ASCII_HELPERS+instrumented+f'let span = {fn}([99],[65,66])\nobserve(span)\n','',status=1,stderr='Minyar stopped: ASCII output is shorter than input\n')
                self.executes(_RGZ_ASCII_HELPERS+instrumented+f'let empty: List<Integer> = []; observe({fn}(empty,empty))\n','0\n0\n')
                expected = [0,1,2,2] + ([97,98] if fn=='lowerString' else [65,66])
                self.executes(_RGZ_ASCII_HELPERS+instrumented+f'observe({fn}([99,99],[65,66]))\n',_rgz_ascii_output(expected))


    def test_ascii_comparisons_keep_all_input_bytes(self):
        source = _RGZ_ASCII_HELPERS + _RGZ_ASCII_COMPARE_HELPERS
        expected = []
        for row in _RGZ_ASCII_COMPARISON_CASES:
            a,b = bytes.fromhex(row['left_utf8_hex']),bytes.fromhex(row['right_utf8_hex'])
            source += f'print({row["function"]}({_rgz_ascii_byte_list(a)},{_rgz_ascii_byte_list(b)}))\n'
            expected.append(row['expected'])
        self.executes(source,_rgz_ascii_output(expected))


    def test_ascii_search_keeps_linear_and_boyer_moore_paths(self):
        source = _RGZ_ASCII_HELPERS + _RGZ_ASCII_COMPARE_HELPERS + _RGZ_ASCII_SEARCH_HELPERS + 'let paths = [0,0]\n'
        expected = []
        for row in _RGZ_ASCII_SEARCH_CASES:
            haystack,needle = bytes.fromhex(row['haystack_utf8_hex']),bytes.fromhex(row['needle_utf8_hex'])
            source += f'print(indexOfIgnoreCase({_rgz_ascii_byte_list(haystack)},{_rgz_ascii_byte_list(needle)},paths))\n'
            if row['algorithm']=='boyer-moore-horspool':
                # Independent last-occurrence formula, excluding the final byte.
                prefix = needle[:-1].lower()
                expected += [len(needle) if prefix.rfind(bytes([c])) < 0 else len(needle)-1-prefix.rfind(bytes([c])) for c in range(256)]
            expected.append(row['minyar_index'])
        source += 'print(paths[0]); print(paths[1])\n'
        expected += [4,2]
        self.executes(source,_rgz_ascii_output(expected))


    def test_ascii_hex_escape_keeps_raw_ff_and_both_charsets(self):
        source = _RGZ_ASCII_HELPERS + _RGZ_ASCII_ESCAPE_HELPERS
        expected = b''
        for row in _RGZ_ASCII_ESCAPE_CASES:
            raw = bytes.fromhex(row['input_hex'])
            source += f'print(hexEscape({_rgz_ascii_byte_list(raw)},{"true" if row["case"]=="upper" else "false"}))\n'
            expected += bytes.fromhex(row['expected_hex'])+b'\n'
        self.executes(source,expected.decode('ascii'))


    def test_for_control_keeps_nested_exit_and_empty_suffix_order(self):
        # for.zig: continue, labelled break, labelled continue, and empty suffix else.
        source = '''function continueUntilThree() {
let array = [1,2,3,4,5]; let sum = 0; let i = 0; let active = true
while i < array.length && active {
  let x = array[i]; print(x); sum = sum + x
  if x < 3 { i = i + 1 } else { active = false }
}
if sum != 6 { fail("continue sum") }; print(sum)
}
function testBreakOuter() {
let array = [97,111,101,117]; let count = 0; let i = 0; let outerActive = true
while i < array.length && outerActive {
  let j = 0
  while j < array.length && outerActive {
    print(i); print(j); count = count + 1; outerActive = false
  }
  i = i + 1
}
if count != 1 { fail("outer break count") }; print(count)
}
function testContinueOuter() {
let array = [97,111,101,117]; let counter = 0; let i = 0
while i < array.length {
  let j = 0; let innerActive = true
  while j < array.length && innerActive {
    print(i); print(j); counter = counter + 1; innerActive = false
  }
  i = i + 1
}
if counter != array.length { fail("outer continue count") }; print(counter)
}
function elseContinueOuter() {
let i = 6; let buffer = [0,0,0,0,0]
while true {
  i = i - 1; print(i)
  let element = i
  while element < buffer.length { print(1); return }
}
}
continueUntilThree(); testBreakOuter(); testContinueOuter(); elseContinueOuter()
'''
        self.executes(source, _rgz_for_output([1,2,3,6,0,0,1,0,0,1,0,2,0,3,0,4,5,4,1]))


    def test_for_six_ordered_traversals_and_same_storage_views(self):
        # Complete24-cell oracle, then both nonnull source-value/reference traversals.
        source = '''record ByteView { values: List<Integer>; start: Integer; count: Integer }
function basicFor() {
let buffer = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
let write = 0; let array = [9,8,7,6]; let i = 0
while i < array.length { buffer[write] = array[i]; write = write + 1; i = i + 1 }
i = 0
while i < array.length { buffer[write] = i; write = write + 1; i = i + 1 }
let arrayAlias = array; i = 0
while i < arrayAlias.length { buffer[write] = arrayAlias[i]; write = write + 1; i = i + 1 }
i = 0
while i < arrayAlias.length { buffer[write] = i; write = write + 1; i = i + 1 }
let view = ByteView { values: array; start: 0; count: array.length }; i = 0
while i < view.count { buffer[write] = view.values[view.start + i]; write = write + 1; i = i + 1 }
i = 0
while i < view.count { buffer[write] = i; write = write + 1; i = i + 1 }
print(write); i = 0
while i < write { print(buffer[i]); i = i + 1 }
}
function testNonnullSlice(slice: List<Integer>) {
let view = ByteView { values: slice; start: 0; count: slice.length }; let i = 0
while i < view.count {
  let x = view.values[view.start + i]
  if x != i + 1 { fail("value traversal") }; print(x); i = i + 1
}
i = 0
while i < view.count {
  let referenced = view.values
  if referenced[view.start + i] != i + 1 { fail("reference traversal") }
  print(referenced[view.start + i]); i = i + 1
}
}
basicFor(); testNonnullSlice([1,2,3,4])
'''
        self.executes(source, _rgz_for_output([24] + [9,8,7,6,0,1,2,3]*3 + [1,2,3,4]*2))


    def test_for_result_helpers_preserve_tags_returns_and_unreached_fallbacks(self):
        # The two even-yield variants both return4. Fallback1/fail stay unexecuted.
        # The absent optional payload is never read or included in the oracle.
        source = '''record OptionalInteger { present: Boolean; value: Integer }
record OptionalBoolean { present: Boolean; value: Boolean }
function findTen(slice: List<Integer>): OptionalInteger {
let i = 0
while i < slice.length {
  let item = slice[i]; print(item)
  if item == 10 { return OptionalInteger { present: true; value: item } }
  i = i + 1
}
return OptionalInteger { present: false; value: 0 }
}
function doTheTest(slice: List<Integer>) {
let result = findTen(slice)
if result.present { fail("fail") }; print(result.present)
}
function entry(t: Boolean, f: Boolean): Boolean {
let buffer = [0,0,0,0,0,0,0,0,0,0]; let i = 0
while i < buffer.length {
  print(i)
  if f { return false }
  if t { return true }
  i = i + 1
}
return false
}
function evenOrOne(x: List<Integer>): Integer {
let i = 0
while i < x.length {
  let y = x[i]; print(y)
  if y % 2 != 0 { i = i + 1 } else { return y * 2 }
}
return 1
}
function evenOrFail(x: List<Integer>): Integer {
let i = 0
while i < x.length {
  let y = x[i]; print(y)
  if y % 2 != 0 { i = i + 1 } else { return y * 2 }
}
fail("")
}
function optionalCondition(cond: Boolean): OptionalBoolean {
let i = 0
while i < 1 {
  if cond { return OptionalBoolean { present: true; value: cond } }
  i = i + 1
}
return OptionalBoolean { present: false; value: false }
}
function zeroYieldsTrue(values: List<Integer>): Boolean {
let i = 0
while i < values.length {
  let x = values[i]; print(x)
  if x == 0 { return true }; i = i + 1
}
return false
}
function returnFromSingleton(): Boolean {
let values = ["a"]; let i = 0
while i < values.length {
  print(values[i]); if true { return false }; i = i + 1
}
return true
}
function emptyRange() {
let map: List<Integer> = []; let i = 0; let j = 0; let count = 0
while i < map.length && j < map.length {
  count = count + 1; fail("empty body entered")
}
print(count)
}
doTheTest([1,2])
let ok = entry(true,false); if !ok { fail("entry") }; print(ok)
let q1 = evenOrOne([1,2]); if q1 != 4 { fail("first result") }; print(q1)
let q2 = evenOrFail([1,2]); if q2 != 4 { fail("second result") }; print(q2)
let cond = false; let absent = optionalCondition(cond)
if absent.present { fail("expected absent") }; print(absent.present)
cond = true; let present = optionalCondition(cond)
if !present.present { fail("expected present") }; print(present.present)
if !present.value { fail("expected true") }; print(present.value)
print(zeroYieldsTrue([0])); print(returnFromSingleton()); emptyRange()
'''
        self.executes(source, _rgz_for_output([1,2,False,0,True,1,2,4,1,2,4,False,True,True,0,True,'a',False,0]))


    def test_for_mutation_retains_copied_payload_and_distinct_source(self):
        source = '''function mangleString(values: List<Integer>) {
let i = 0
while i < values.length { values[i] = values[i] + 1; i = i + 1 }
}
function copiedPayload() {
let x = [1,2,3]; let i = 0
while i < x.length {
  let value = x[i]; x[i] = x[i] + 99
  if value != i + 1 { fail("payload changed") }; print(value); print(x[i]); i = i + 1
}
i = 0; while i < x.length { print(x[i]); i = i + 1 }
}
let source = [97,98,99,100,101,102,103]; let target: List<Integer> = []; let i = 0
while i < source.length { target.add(source[i]); i = i + 1 }
mangleString(target); i = 0
while i < target.length { print(target[i]); i = i + 1 }
i = 0; while i < source.length { print(source[i]); i = i + 1 }
copiedPayload()
'''
        self.executes(source, _rgz_for_output(list(b'bcdefgh') + list(b'abcdefg') + [1,100,2,101,3,102,100,101,102]))


    def test_for_counters_preserve_fixed_offset_and_runtime_starts(self):
        source = '''function fixedRange() {
let sum = 0; let i = 0
while i < 6 { print(i); sum = sum + i; i = i + 1 }
if sum != 15 { fail("range sum") }; print(sum)
}
function twoCounters() {
let sum = 0; let i = 0; let j = 10
while i < 10 && j < 20 {
  sum = sum + 1; if i + 10 != j { fail("counter pair") }
  print(i); print(j); i = i + 1; j = j + 1
}
if sum != 10 { fail("counter count") }; print(sum)
}
function oneBased() {
let bytes = [104,101,108,108,111]; let i = 1; let ok = 0
while i < 6 && i - 1 < bytes.length {
  let b = bytes[i - 1]; print(i); print(b)
  if i == 1 { if b != 104 { fail("h") }; ok = ok + 1 }
  if i == 2 { if b != 101 { fail("e") }; ok = ok + 1 }
  if i == 3 { if b != 108 { fail("l1") }; ok = ok + 1 }
  if i == 4 { if b != 108 { fail("l2") }; ok = ok + 1 }
  if i == 5 { if b != 111 { fail("o") }; ok = ok + 1 }
  i = i + 1
}
if ok != 5 { fail("one-based count") }; print(ok)
}
function runtimeStart() {
let slice = [98,108,97,104]; let start = 0; let aIndex = 0; let b = start; let c = 1
while aIndex < slice.length && b < 4 && c < 5 {
  let a = slice[aIndex]; print(a); print(b); print(c)
  if a == 98 { if b != 0 { fail("b0") }; if c != 1 { fail("c1") } }
  if a == 108 { if b != 1 { fail("b1") }; if c != 2 { fail("c2") } }
  if a == 97 { if b != 2 { fail("b2") }; if c != 3 { fail("c3") } }
  if a == 104 { if b != 3 { fail("b3") }; if c != 4 { fail("c4") } }
  aIndex = aIndex + 1; b = b + 1; c = c + 1
}
}
fixedRange(); twoCounters(); oneBased(); runtimeStart()
'''
        expected = list(range(6)) + [15]
        expected += [item for pair in zip(range(10),range(10,20)) for item in pair] + [10]
        expected += [item for pair in zip(range(1,6),b'hello') for item in pair] + [5]
        expected += [item for triple in zip(b'blah',range(4),range(1,5)) for item in triple]
        self.executes(source, _rgz_for_output(expected))


    def test_for_destination_aliases_keep_all_defined_prefix_stores(self):
        source = '''record ByteView { values: List<Integer>; start: Integer; count: Integer }
function twoSlices() {
let buffer = [0,0,0,0,0,0,0,0,0,0]; let slice1 = [98,108,97,104]
let slice2 = ByteView { values: buffer; start: 0; count: 4 }; let i = 0
while i < slice1.length && i < slice2.count {
  slice2.values[slice2.start + i] = slice1[i]; i = i + 1
}
i = 0; while i < slice2.count { print(slice2.values[slice2.start + i]); i = i + 1 }
}
function pointerAndSlice() {
let buffer = [0,0,0,0,0,0,0,0,0,0]; let slice = [98,108,97,104]; let alias = buffer; let i = 0
while i < slice.length { alias[i] = slice[i]; i = i + 1 }
i = 0; while i < 4 { print(buffer[i]); i = i + 1 }
}
function pointerAndCounter() {
let buffer = [0,0,0,0,0,0,0,0,0,0]; let alias = buffer; let b = 0
while b < 4 { alias[b] = 65 + b; b = b + 1 }
b = 0; while b < 4 { print(buffer[b]); b = b + 1 }
}
twoSlices(); pointerAndSlice(); pointerAndCounter()
'''
        # Undefined original buffer tails are initialized solely for safety and never observed.
        self.executes(source, _rgz_for_output(list(b'blahblahABCD')))


    def test_for_inline_value_specializations_keep_both_helper_call_shapes(self):
        source = '''function checkSliceValue(a: Integer, b: Integer, ok: List<Integer>) {
print(a); print(b)
if a == 108 { if b != 3 { fail("slice index3") }; ok[0] = ok[0] + 1 } else {
if a == 111 { if b != 4 { fail("slice index4") }; ok[0] = ok[0] + 1 } else { fail("unsupported slice byte") } }
}
function checkCounterValue(a: Integer, b: Integer, ok: List<Integer>) {
print(a); print(b)
if b == 3 { if a != 108 { fail("counter l") }; ok[0] = ok[0] + 1 } else {
if b == 4 { if a != 111 { fail("counter o") }; ok[0] = ok[0] + 1 } else { fail("unsupported counter") } }
}
function sliceKnown() {
let fixedSlice = [104,101,108,108,111]; let runtimeIndex = 3; let sliceIndex = 3; let ok = [0]
while sliceIndex < 5 && runtimeIndex < 5 {
  checkSliceValue(fixedSlice[sliceIndex],runtimeIndex,ok)
  sliceIndex = sliceIndex + 1; runtimeIndex = runtimeIndex + 1
}
if ok[0] != 2 { fail("slice ok") }; print(ok[0])
}
function counterKnown() {
let runtimeSlice = [104,101,108,108,111]; let runtimeIndex = 3; let fixedCounter = 3; let ok = [0]
while runtimeIndex < 5 && fixedCounter < 5 {
  checkCounterValue(runtimeSlice[runtimeIndex],fixedCounter,ok)
  runtimeIndex = runtimeIndex + 1; fixedCounter = fixedCounter + 1
}
if ok[0] != 2 { fail("counter ok") }; print(ok[0])
}
sliceKnown(); counterKnown()
'''
        self.executes(source, _rgz_for_output([108,3,111,4,2]*2))


    def test_for_tuple_aliases_and_referenced_counters_preserve_all_values(self):
        source = '''function tupleWrites() {
let fields = [100,200,300]; let alias = fields; let i = 0
while i < alias.length { print(alias[i]); alias[i] = i; i = i + 1 }
i = 0; while i < fields.length { print(fields[i]); i = i + 1 }
}
function referencedCounters(values: List<Integer>) {
let j = 0
while j < values.length {
  let i = values[j]; let iCell = [i]; let jCell = [j]
  if i != j { fail("scalar counter mismatch") }; print(i == j)
  if iCell[0] != jCell[0] { fail("referenced counter mismatch") }; print(iCell[0] == jCell[0])
  print(i); print(j); print(iCell[0]); print(jCell[0]); j = j + 1
}
}
tupleWrites(); referencedCounters([0,1,2]); referencedCounters([0,1,2])
'''
        expected = [100,200,300,0,1,2]
        expected += [x for _ in range(2) for i in range(3) for x in [True,True,i,i,i,i]]
        self.executes(source, _rgz_for_output(expected))


    def _rgz_unicode_run_cases(self, cases):
        import hashlib
        from pathlib import Path
        from regressions import CLANG, LINK_FLAGS, RUNTIME
        fixture=Path(__file__).with_name('peer-rgz-unicode-probe.c')
        self.evidence.inputs[str(fixture.resolve())]=hashlib.sha256(fixture.read_bytes()).hexdigest()
        variants=('-O0','-O2','-O3','-Os') if os.environ.get('MINYAR_TEST_EXTENDED_OPT')=='1' else ('-O0','-O2')
        prepared=[]
        for index,(label,mode,payload,expected,status,diagnostic) in enumerate(cases):
            arguments=[mode]
            inputs=[]
            if isinstance(payload,bytes):
                path=self.directory/f'unicode-input-{index}.bin';path.write_bytes(payload)
                arguments.append(str(path));inputs.append((path,payload))
            elif mode=='encode-sequence':
                for part,data in enumerate(payload):
                    path=self.directory/f'unicode-input-{index}-{part}.bin';path.write_bytes(data)
                    arguments.append(str(path));inputs.append((path,data))
            else:
                arguments.append(str(payload))
            prepared.append((label,arguments,inputs,expected.encode(),status,diagnostic.encode()))
        coverage={'source_cases_per_configuration':len(cases),'processes_attempted':{},'processes_passing_exact_oracle':{},'case_ids':[case[0]for case in cases]}
        self.evidence.controls['domain_coverage']={'unicode':coverage}
        for optimization in variants:
            object_file=self.directory/('unicode-'+optimization[1:]+'.o')
            executable=self.directory/('unicode-'+optimization[1:])
            compile_result=self.evidence.run(clang_command([CLANG,'-std=c11',optimization,*LINK_FLAGS,'-Wall','-Wextra','-Werror','-c',fixture,'-o',object_file]),timeout=30,phase='compile-c-runtime-probe')
            self.assertEqual(compile_result.returncode,0,compile_result.stderr)
            linked=self.evidence.run(clang_command([CLANG,optimization,*LINK_FLAGS,object_file,RUNTIME,'-o',executable]),timeout=30,phase='link')
            self.assertEqual(linked.returncode,0,linked.stderr)
            coverage['processes_attempted'][optimization]=0
            coverage['processes_passing_exact_oracle'][optimization]=0
            for label,arguments,inputs,expected,status,diagnostic in prepared:
                with self.subTest(optimization=optimization,source_case=label):
                    for path,payload in inputs:self.assertEqual(path.read_bytes(),payload)
                    coverage['processes_attempted'][optimization]+=1
                    result=self.evidence.run([executable,*arguments],timeout=30,phase='execute')
                    self.assertEqual((result.returncode,result.stdout,result.stderr),(status,expected,diagnostic))
                    coverage['processes_passing_exact_oracle'][optimization]+=1


    def test_unicode_encoder_reuses_all_four_defined_prefixes(self):
        selected=[r for r in _RGZ_UNICODE_CASES if r['group']=='utf8-encode-reused-prefix']
        self.assertEqual(len(selected),4)
        payload=[bytes.fromhex(r['oracle']['input_utf8_hex'])for r in selected]
        expected=[v for r in selected for v in [r['oracle']['length'],*r['oracle']['asserted_prefix_bytes']]]
        self._rgz_unicode_run_cases([('four ordered encode operations','encode-sequence',payload,_rgz_unicode_output(expected),0,'')])


    def test_unicode_single_scalar_decoder_keeps_all_numeric_boundaries(self):
        cases=[]
        for row in _RGZ_UNICODE_CASES:
            if row['group']!='utf8-single-scalar-decoding':continue
            data=bytes.fromhex(row['oracle']['input_hex'])
            cases.append((row['case_id'],'decode',data,_rgz_unicode_output([len(data),1,row['oracle']['scalar']]),0,''))
        self.assertEqual(len(cases),14);self._rgz_unicode_run_cases(cases)


    def test_unicode_validators_preserve_all_shared_valid_inputs(self):
        cases=[]
        for row in _RGZ_UNICODE_CASES:
            if row['group']!='utf8-valid-validation':continue
            data=bytes.fromhex(row['oracle']['input_hex']);scalars=row['oracle']['scalars']
            cases.append((row['case_id'],'decode',data,_rgz_unicode_output([len(data),len(scalars),*scalars]),0,''))
        self.assertEqual(len(cases),24);self._rgz_unicode_run_cases(cases)


    def test_unicode_counts_keep_ascii_accented_and_japanese_domains(self):
        cases=[]
        for row in _RGZ_UNICODE_CASES:
            if row['group']!='utf8-codepoint-count':continue
            data=bytes.fromhex(row['oracle']['input_hex']);scalars=list(map(ord,data.decode('utf-8')))
            self.assertEqual(len(scalars),row['oracle']['character_count'])
            cases.append((row['case_id'],'decode',data,_rgz_unicode_output([len(data),row['oracle']['character_count'],*scalars]),0,''))
        self.assertEqual(len(cases),3);self._rgz_unicode_run_cases(cases)


    def test_unicode_scalar_acceptance_keeps_exact_encoded_bytes(self):
        cases=[]
        for row in _RGZ_UNICODE_CASES:
            if row['group']!='utf8-scalar-validity' or not row['oracle']['expected_valid']:continue
            data=bytes.fromhex(row['oracle']['encoded_hex']);scalar=row['oracle']['scalar']
            cases.append((row['case_id'],'encode',scalar,_rgz_unicode_output([len(data),*data,1,scalar]),0,''))
        self.assertEqual(len(cases),5);self._rgz_unicode_run_cases(cases)


    def test_unicode_encoder_rejects_every_invalid_scalar_in_fresh_process(self):
        cases=[]
        for row in _RGZ_UNICODE_CASES:
            if row['group']=='utf8-invalid-scalar-encoding' or (row['group']=='utf8-scalar-validity' and not row['oracle']['expected_valid']):
                cases.append((row['case_id'],'encode',row['oracle']['scalar'],'',1,'Minyar stopped: this Character is not valid Unicode.\n'))
        self.assertEqual(len(cases),7);self._rgz_unicode_run_cases(cases)


    def test_unicode_decoder_rejects_all_truncation_overlong_surrogate_and_range_inputs(self):
        cases=[(r['case_id'],'invalid',bytes.fromhex(r['oracle']['input_hex']),'',1,'Minyar stopped: Text contained invalid UTF-8.\n')for r in _RGZ_UNICODE_CASES if r['group']=='utf8-invalid-decoding']
        self.assertEqual(len(cases),30);self._rgz_unicode_run_cases(cases)


    def test_unicode_validators_reject_every_shared_invalid_input(self):
        cases=[(r['case_id'],'invalid',bytes.fromhex(r['oracle']['input_hex']),'',1,'Minyar stopped: Text contained invalid UTF-8.\n')for r in _RGZ_UNICODE_CASES if r['group']=='utf8-invalid-validation']
        self.assertEqual(len(cases),25);self._rgz_unicode_run_cases(cases)


    def test_unicode_raw_ingress_preserves_every_malformed_payload_before_validation(self):
        cases=[]
        for row in _RGZ_UNICODE_CASES:
            if row['group'] not in ('utf8-invalid-decoding','utf8-invalid-validation'):continue
            data=bytes.fromhex(row['oracle']['input_hex'])
            cases.append((row['case_id'],'raw',data,_rgz_unicode_output([len(data),*data]),0,''))
        self.assertEqual(len(cases),55);self._rgz_unicode_run_cases(cases)


    def test_unicode_utf8_ascii_prefix_tail_checks_every_backing_offset(self):
        # Exact source range0..str.len-3, str='a'*550+C0:548 distinct offsets.
        cases=[(f'generated-case/line652/start{i}','suffix',i,'',1,'Minyar stopped: Text contained invalid UTF-8.\n')for i in range(548)]
        self._rgz_unicode_run_cases(cases)


    def test_unicode_wtf8_shared_ascii_prefix_tail_checks_every_backing_offset(self):
        # Separate WTF8-root invocation; these exact malformed inputs share UTF8 policy.
        cases=[(f'generated-case/line1641/start{i}','suffix',i,'',1,'Minyar stopped: Text contained invalid UTF-8.\n')for i in range(548)]
        self._rgz_unicode_run_cases(cases)


    def test_unicode_iterators_keep_independent_slice_and_numeric_cursors(self):
        cases=[]
        for row in _RGZ_UNICODE_CASES:
            if row['group']!='utf8-independent-iterators':continue
            oracle=row['oracle'];data=bytes.fromhex(oracle['input_utf8_hex']);slices=[bytes.fromhex(value)for value in oracle['slice_utf8_hex']]
            expected=[];position=0
            for index,part in enumerate(slices,1):
                position+=len(part);expected += [1,len(part),*part,index,position]
            expected += [0,3,len(data)];position=0
            for index,(part,scalar)in enumerate(zip(slices,oracle['scalars']),1):
                position+=len(part);expected += [1,scalar,index,position]
            expected += [0,3,len(data)]
            cases.append((row['case_id'],'iterators',data,_rgz_unicode_output(expected),0,''))
        self.assertEqual(len(cases),2);self._rgz_unicode_run_cases(cases)


    def test_unicode_peek_preserves_all_eleven_outputs_without_advancing(self):
        rows=[r for r in _RGZ_UNICODE_CASES if r['group']=='utf8-peek-restores-cursor'];self.assertEqual(len(rows),1)
        row=rows[0];oracle=row['oracle'];expected=[];character=byte=0
        self.assertEqual(len(oracle['ordered_operations']),11)
        for operation in oracle['ordered_operations']:
            if operation[0]=='next':
                value=operation[1]
                if value is None:expected += [0,character,byte]
                else:
                    data=value.encode();character+=1;byte+=len(data);expected += [1,len(data),*data,character,byte]
            else:
                data=operation[2].encode();expected += [len(data),*data,character,byte]
        self._rgz_unicode_run_cases([(row['case_id'],'peek',bytes.fromhex(oracle['input_utf8_hex']),_rgz_unicode_output(expected),0,'')])


if __name__ == '__main__':
    from peer_runner import main
    main()
