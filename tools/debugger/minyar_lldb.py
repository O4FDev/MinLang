"""Import with: command script import /path/to/tools/debugger/minyar_lldb.py"""

import os
import sys

import lldb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from minyar_debug_core import (FormatError, MAX_FIELDS, Projection, TYPE_PATTERN,
                               checked_address, child_index)


class Value:
    def __init__(self, native):
        self.native = native.GetNonSyntheticValue()
        if not self.native.IsValid():
            raise FormatError("unavailable value")

    def object(self):
        if self.native.GetType().IsPointerType():
            if not self.integer():
                raise FormatError("null")
            return Value(self.native.Dereference())
        return self

    def type_name(self):
        return self.native.GetType().GetName() or ""

    def fields(self):
        value_type = self.native.GetType()
        total = value_type.GetNumberOfFields()
        if total > MAX_FIELDS:
            raise FormatError("too many fields")
        return [value_type.GetFieldAtIndex(i).GetName() or "" for i in range(total)]

    def field(self, name):
        return Value(self.native.GetChildMemberWithName(name))

    def integer(self):
        error = lldb.SBError()
        if self.native.GetType().IsPointerType():
            result = self.native.GetValueAsUnsigned(error, 0)
        else:
            result = self.native.GetValueAsSigned(error, 0)
        if error.Fail():
            raise FormatError("unreadable value")
        return result

    def slot(self, index):
        target_type = self.native.GetType().GetPointeeType()
        if not target_type.IsValid() or not 0 < target_type.GetByteSize() <= 8:
            raise FormatError("invalid slot type")
        address = checked_address(self.integer(), index)
        return Value(self.native.CreateValueFromAddress("[{}]".format(index), address, target_type))

    def read_bytes(self, amount):
        error = lldb.SBError()
        data = self.native.GetProcess().ReadMemory(self.integer(), amount, error)
        if error.Fail():
            raise FormatError("unreadable memory")
        return bytes(data)


def summary(value, internal_dict, options=None):
    try:
        return Projection(Value(value)).summary()
    except Exception as error:
        detail = str(error) if isinstance(error, FormatError) else "unreadable value"
        return "<Minyar: {}>".format(detail)


class Children:
    def __init__(self, value, internal_dict):
        self.value = value
        self.projection = None
        self.update()

    def update(self):
        try:
            self.projection = Projection(Value(self.value))
        except Exception:
            self.projection = None
        return False  # Re-read headers at every stop, including after mutation.

    def num_children(self, max_children=None):
        total = len(self.projection.names) if self.projection else 0
        return total if max_children is None else min(total, max_children)

    def has_children(self):
        return self.num_children() > 0

    def get_child_index(self, name):
        return child_index(self.projection.names, name) if self.projection else -1

    def get_child_at_index(self, index):
        try:
            return self.projection.child(index).native.Clone(self.projection.names[index])
        except Exception:
            return lldb.SBValue()


def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand("type category define Minyar")
    debugger.HandleCommand("type summary add -w Minyar -x '{}' -F {}.summary".format(TYPE_PATTERN, __name__))
    debugger.HandleCommand("type synthetic add -w Minyar -x '{}' -l {}.Children".format(TYPE_PATTERN, __name__))
    debugger.HandleCommand("type category enable Minyar")
