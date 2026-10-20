"""Portable projection contracts; run with python3 tools/debugger/test_formatters.py."""

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from minyar_debug_core import (FormatError, MAX_CHILDREN, MAX_MAP_BUCKETS,
                               MAX_TEXT_BYTES, Projection, checked_address,
                               child_index, text_preview)


class Node:
    """Debugger read operations backed by a tiny stopped-memory fixture."""

    def __init__(self, name="Integer", number=0, fields=None, slots=None, data=b""):
        self.name = name
        self.number = number
        self.members = fields or {}
        self.slots = slots or {}
        self.data = data
        self.reads = []
        self.native = self

    def object(self):
        return self

    def type_name(self):
        return self.name

    def fields(self):
        return list(self.members)

    def field(self, name):
        return self.members[name]

    def integer(self):
        return self.number

    def slot(self, index):
        self.reads.append(index)
        return self.slots.get(index, Node())

    def read_bytes(self, amount):
        self.reads.append(amount)
        return self.data[:amount]


def sequence(items=None, length=None, capacity=None, name="List<Integer>"):
    items = items or {}
    if length is None:
        length = max(items, default=-1) + 1
    return Node(name, fields={
        "values": Node("minyar.slot<Integer> *", 4096, slots=items),
        "length": Node(number=length),
        "capacity": Node(number=length if capacity is None else capacity),
    })


def mapped(hashes, keys, values, length):
    return Node("Map<Integer, Text>", fields={
        "hashes": hashes, "keys": keys, "values": values,
        "length": Node(number=length),
    })


class ProjectionTests(unittest.TestCase):
    def test_text_preserves_nul_and_unicode_and_stops_at_byte_limit(self):
        data = "a\0é".encode()
        self.assertEqual(text_preview(data, len(data)), '"a\\u0000é"')
        self.assertEqual(text_preview(b"abc\xc3", 5), '"abc"…')
        self.assertEqual(text_preview(b"\xff", 1), '"�"')
        storage = Node(number=4096, data=b"x" * (MAX_TEXT_BYTES + 10))
        text = Node("Text", fields={"bytes": storage,
                                   "byte_length": Node(number=MAX_TEXT_BYTES + 10)})
        self.assertTrue(Projection(text).summary().endswith('"…'))
        self.assertEqual(storage.reads, [MAX_TEXT_BYTES])

    def test_empty_text_accepts_null_storage_and_short_reads_fail(self):
        storage = Node(number=0)
        text = Node("Text", fields={"bytes": storage, "byte_length": Node()})
        self.assertEqual(Projection(text).summary(), '""')
        self.assertEqual(storage.reads, [])
        text.members["byte_length"].number = 1
        with self.assertRaisesRegex(FormatError, "storage address"):
            Projection(text).summary()
        storage.number = 4096
        with self.assertRaisesRegex(FormatError, "short memory read"):
            Projection(text).summary()

    def test_bytes_use_hex_and_reject_corrupt_capacity(self):
        value = Node("Bytes", fields={"bytes": Node(number=4096, data=b"\0\xff"),
                                    "byte_length": Node(number=2),
                                    "capacity": Node(number=2)})
        self.assertEqual(Projection(value).summary(), "Bytes(length=2) [00 ff]")
        value.members["capacity"].number = 1
        with self.assertRaisesRegex(FormatError, "exceeds capacity"):
            Projection(value).summary()

    def test_list_keeps_typed_slots_and_caps_children(self):
        boolean = Node("Boolean", number=1)
        slot = Node("minyar.slot<Boolean>", fields={"value": boolean})
        value = sequence({1: slot}, length=10000, name="List<Boolean>")
        view = Projection(value)
        self.assertEqual(len(view.names), MAX_CHILDREN)
        self.assertIs(view.child(1), boolean)
        self.assertEqual(value.field("values").reads, [1])
        self.assertIn("showing=64", view.summary())
        self.assertEqual(child_index(view.names, "[1]"), 1)
        self.assertEqual(child_index(view.names, "[10000]"), -1)

    def test_sparse_map_skips_empty_buckets_and_projects_pairs(self):
        hashes = sequence({1: Node(number=-7), 3: Node(number=8)}, length=8)
        key = Node(number=42)
        value = Node("Text")
        view = Projection(mapped(hashes, sequence({3: key}, length=8),
                                 sequence({3: value}, length=8), 2))
        self.assertEqual(view.names, ["[0].key", "[0].value", "[1].key", "[1].value"])
        self.assertIs(view.child(2), key)
        self.assertIs(view.child(3), value)
        self.assertEqual(hashes.field("values").reads, [0, 1, 2, 3])

    def test_sparse_map_scan_is_bounded_and_reports_incomplete_preview(self):
        hashes = sequence({MAX_MAP_BUCKETS + 1: Node(number=8)}, length=1000000)
        view = Projection(mapped(hashes, sequence(length=1000000),
                                 sequence(length=1000000), 1))
        self.assertEqual(view.names, [])
        self.assertEqual(len(hashes.field("values").reads), MAX_MAP_BUCKETS)
        self.assertIn("showing=0, scanned=256/1000000 buckets", view.summary())

    def test_map_limits_pairs_and_rejects_inconsistent_headers(self):
        hashes = sequence({i: Node(number=1) for i in range(100)}, length=128)
        value = mapped(hashes, sequence(length=128), sequence(length=128), 100)
        self.assertEqual(len(Projection(value).names), MAX_CHILDREN)
        value.members["keys"] = sequence(length=64)
        with self.assertRaisesRegex(FormatError, "bucket lengths disagree"):
            Projection(value)
        value = mapped(sequence(length=8), sequence(length=8), sequence(length=8), 1)
        with self.assertRaisesRegex(FormatError, "occupied buckets"):
            Projection(value)

    def test_choice_reads_only_active_payload(self):
        radius = Node("Float")
        value = Node("minyar.choice<Shape>", fields={
            "minyar_record_length": Node(number=3),
            "minyar_choice_tag|Circle|Empty": Node(number=0),
            "minyar_choice_payload|Circle|radius": radius,
            "minyar_choice_payload|Empty|unused": Node(),
        })
        view = Projection(value)
        self.assertEqual(view.summary(), "Shape.Circle")
        self.assertEqual(view.names, ["radius"])
        self.assertIs(view.child(0), radius)
        value.members["minyar_choice_tag|Circle|Empty"].number = 2
        with self.assertRaisesRegex(FormatError, "choice discriminant"):
            Projection(value)

    def test_invalid_sizes_and_address_overflow_are_rejected(self):
        for value in (sequence(length=-1), sequence(length=2, capacity=1),
                      sequence(length=(1 << 63) - 1)):
            with self.subTest(value=value), self.assertRaises(FormatError):
                Projection(value)
        for address, index in ((0, 0), ((1 << 64) - 1, 0), (4096, -1)):
            with self.subTest(address=address), self.assertRaises(FormatError):
                checked_address(address, index)


class AdapterTests(unittest.TestCase):
    def load(self, name, debugger):
        path = Path(__file__).with_name(name + ".py")
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {debugger.__name__: debugger}):
            spec.loader.exec_module(module)
        return module

    def test_lldb_slot_address_uses_eight_bytes_for_boolean(self):
        debugger = types.ModuleType("lldb")
        debugger.SBError = lambda: types.SimpleNamespace(Fail=lambda: False)
        module = self.load("minyar_lldb", debugger)
        target = types.SimpleNamespace(IsValid=lambda: True, GetByteSize=lambda: 1)
        native = types.SimpleNamespace(
            GetNonSyntheticValue=lambda: native, IsValid=lambda: True,
            GetType=lambda: types.SimpleNamespace(IsPointerType=lambda: True,
                                                 GetPointeeType=lambda: target),
            GetValueAsUnsigned=lambda error, default: 4096,
            CreateValueFromAddress=lambda name, address, value_type: addresses.append(address) or native,
        )
        addresses = []
        module.Value(native).slot(3)
        self.assertEqual(addresses, [4120])
        commands = []
        getattr(module, "__lldb_init_module")(types.SimpleNamespace(HandleCommand=commands.append), {})
        self.assertTrue(any("-w Minyar" in command for command in commands))
        self.assertTrue(all(".+" not in command or "minyar" in command for command in commands))
        native.GetValueAsUnsigned = lambda error, default: 0
        self.assertEqual(module.summary(native, {}), "<Minyar: null>")

    def test_gdb_registration_is_idempotent_and_slot_stride_is_eight(self):
        debugger = types.ModuleType("gdb")
        debugger.pretty_printers = []
        debugger.TYPE_CODE_PTR = 1
        addresses = []
        native = types.SimpleNamespace()
        debugger.Value = lambda address: types.SimpleNamespace(
            cast=lambda value_type: types.SimpleNamespace(dereference=lambda: addresses.append(address) or native))
        module = self.load("minyar_gdb", debugger)
        self.load("minyar_gdb", debugger)
        self.assertEqual(len(debugger.pretty_printers), 1)
        target = types.SimpleNamespace(sizeof=4, pointer=lambda: None)
        native.type = types.SimpleNamespace(strip_typedefs=lambda: types.SimpleNamespace(target=lambda: target))
        value = module.Value(native)
        value.integer = lambda: 4096
        value.slot(3)
        self.assertEqual(addresses, [4120])


if __name__ == "__main__":
    unittest.main()
