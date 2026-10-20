"""Import with: source /path/to/tools/debugger/minyar_gdb.py"""

import os
import sys

import gdb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from minyar_debug_core import (FormatError, MAX_FIELDS, Projection,
                               checked_address, kind)


class Value:
    def __init__(self, native):
        self.native = native

    def object(self):
        if self.native.type.strip_typedefs().code == gdb.TYPE_CODE_PTR:
            if not self.integer():
                raise FormatError("null")
            return Value(self.native.dereference())
        return self

    def type_name(self):
        value_type = self.native.type.strip_typedefs()
        return value_type.tag or value_type.name or str(value_type)

    def fields(self):
        fields = self.native.type.strip_typedefs().fields()
        if len(fields) > MAX_FIELDS:
            raise FormatError("too many fields")
        return [field.name or "" for field in fields]

    def field(self, name):
        return Value(self.native[name])

    def integer(self):
        return int(self.native)

    def slot(self, index):
        target_type = self.native.type.strip_typedefs().target()
        if not 0 < target_type.sizeof <= 8:
            raise FormatError("invalid slot type")
        address = checked_address(self.integer(), index)
        return Value(gdb.Value(address).cast(target_type.pointer()).dereference())

    def read_bytes(self, amount):
        return bytes(gdb.selected_inferior().read_memory(self.integer(), amount))


class Printer:
    def __init__(self, value):
        self.projection = None
        self.error = None
        try:
            self.projection = Projection(Value(value))
        except Exception as error:
            self.error = str(error) if isinstance(error, FormatError) else "unreadable value"

    def to_string(self):
        try:
            if self.error:
                return "<Minyar: {}>".format(self.error)
            return self.projection.summary()
        except Exception as error:
            detail = str(error) if isinstance(error, FormatError) else "unreadable value"
            return "<Minyar: {}>".format(detail)

    def children(self):
        if self.projection:
            for index, name in enumerate(self.projection.names):
                try:
                    yield name, self.projection.child(index).native
                except Exception:
                    return


def lookup(value):
    value_type = value.type.strip_typedefs()
    if value_type.code == gdb.TYPE_CODE_PTR:
        value_type = value_type.target().strip_typedefs()
    name = value_type.tag or value_type.name or str(value_type)
    return Printer(value) if kind(name) else None


lookup.name = "Minyar"
lookup.enabled = True
# Loading twice replaces our own registration without duplicating output.
gdb.pretty_printers[:] = [printer for printer in gdb.pretty_printers
                         if getattr(printer, "name", None) != lookup.name]
gdb.pretty_printers.append(lookup)
