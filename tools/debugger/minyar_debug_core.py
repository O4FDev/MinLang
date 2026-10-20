"""Bounded, debugger-independent projections of Minyar's DWARF values.

Adapters provide object(), type_name(), fields(), field(), integer(), slot(),
read_bytes(), and the native debugger value. None of these operations run code in
the inferior. Collection slots are always eight bytes, even for Boolean/Character.
"""

import codecs
import json


MAX_TEXT_BYTES = 256
MAX_CHILDREN = 64
MAX_MAP_BUCKETS = 256
MAX_FIELDS = 512
MAX_LENGTH = (1 << 63) - 1
TYPE_PATTERN = r"^(Text|Bytes|List<.+>|Map<.+>|minyar[.]choice<.+>)( ?\*)?$"


class FormatError(ValueError):
    """A malformed, null, unreadable, or unavailable debug value."""


def kind(name):
    if name in ("Text", "Bytes"):
        return name
    for prefix in ("List", "Map", "minyar.choice"):
        if name.startswith(prefix + "<") and name.endswith(">"):
            return prefix
    return None


def count(value, label="length"):
    if value < 0 or value > MAX_LENGTH:
        raise FormatError("invalid " + label)
    return value


def checked_address(address, index=0, stride=8):
    result = address + index * stride
    if address <= 0 or index < 0 or result > (1 << 64) - stride:
        raise FormatError("invalid storage address")
    return result


def text_preview(data, length):
    """Escape NUL/control bytes; do not misreport a truncated UTF-8 scalar."""
    truncated = len(data) < length
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    decoded = decoder.decode(data, final=not truncated)
    return json.dumps(decoded, ensure_ascii=False) + ("…" if truncated else "")


def slot_value(storage, index):
    value = storage.slot(index)
    if value.type_name().startswith("minyar.slot<"):
        return value.field("value")
    return value


class Sequence:
    def __init__(self, value):
        value = value.object()
        self.length = count(value.field("length").integer())
        capacity = count(value.field("capacity").integer(), "capacity")
        if self.length > capacity:
            raise FormatError("length exceeds capacity")
        self.storage = value.field("values")
        if self.length:
            checked_address(self.storage.integer(), self.length - 1)

    def at(self, index):
        if not 0 <= index < self.length:
            raise FormatError("index outside length")
        return slot_value(self.storage, index)


class Projection:
    def __init__(self, value):
        self.value = value.object()
        self.name = self.value.type_name()
        self.kind = kind(self.name)
        self.names = []
        self.indices = []
        if self.kind == "List":
            self.sequence = Sequence(self.value)
            self.length = self.sequence.length
            self.names = ["[{}]".format(i) for i in range(min(self.length, MAX_CHILDREN))]
        elif self.kind == "Map":
            self._map()
        elif self.kind == "minyar.choice":
            self._choice()
        elif self.kind not in ("Text", "Bytes"):
            raise FormatError("unsupported type")

    def _map(self):
        self.length = count(self.value.field("length").integer())
        hashes = Sequence(self.value.field("hashes"))
        self.keys = Sequence(self.value.field("keys"))
        self.values = Sequence(self.value.field("values"))
        if hashes.length != self.keys.length or hashes.length != self.values.length:
            raise FormatError("Map bucket lengths disagree")
        if self.length > hashes.length:
            raise FormatError("Map length exceeds bucket count")
        self.bucket_count = hashes.length
        self.scanned = 0
        if self.length:
            for bucket in range(min(hashes.length, MAX_MAP_BUCKETS)):
                self.scanned = bucket + 1
                if hashes.at(bucket).integer() != 0:
                    self.indices.append(bucket)
                    if len(self.indices) == min(self.length, MAX_CHILDREN // 2):
                        break
        if self.scanned == hashes.length and len(self.indices) != self.length:
            raise FormatError("Map length disagrees with occupied buckets")
        for index in range(len(self.indices)):
            self.names.extend(("[{}].key".format(index), "[{}].value".format(index)))

    def _choice(self):
        fields = self.value.fields()
        tags = [name for name in fields if name.startswith("minyar_choice_tag|")]
        if len(tags) != 1:
            raise FormatError("missing choice discriminant")
        cases = tags[0].split("|")[1:]
        tag = self.value.field(tags[0]).integer()
        if not 0 <= tag < len(cases) or not cases[tag]:
            raise FormatError("invalid choice discriminant")
        self.case = cases[tag]
        self.payload_fields = []
        for name in fields:
            parts = name.split("|")
            if len(parts) == 3 and parts[0] == "minyar_choice_payload" and parts[1] == self.case:
                self.payload_fields.append(name)
                self.names.append(parts[2])
                if len(self.names) == MAX_CHILDREN:
                    break

    def summary(self):
        if self.kind in ("Text", "Bytes"):
            length = count(self.value.field("byte_length").integer(), "byte length")
            if self.kind == "Bytes":
                capacity_name = "capacity" if "capacity" in self.value.fields() else "character_length"
                capacity = count(self.value.field(capacity_name).integer(), "capacity")
                if length > capacity:
                    raise FormatError("byte length exceeds capacity")
            storage = self.value.field("bytes")
            amount = min(length, MAX_TEXT_BYTES)
            if amount:
                checked_address(storage.integer(), amount - 1, 1)
                data = storage.read_bytes(amount)
                if len(data) != amount:
                    raise FormatError("short memory read")
            else:
                data = b""
            if self.kind == "Text":
                return text_preview(data, length)
            return "Bytes(length={}) [{}]{}".format(
                length, " ".join("{:02x}".format(byte) for byte in data),
                "…" if length > amount else "")
        if self.kind == "List":
            suffix = ", showing={}".format(len(self.names)) if self.length > len(self.names) else ""
            return "{}(length={}{})".format(self.name, self.length, suffix)
        if self.kind == "Map":
            suffix = ""
            if len(self.indices) < self.length:
                suffix = ", showing={}, scanned={}/{} buckets".format(
                    len(self.indices), self.scanned, self.bucket_count)
            return "{}(length={}{})".format(self.name, self.length, suffix)
        return "{}.{}".format(self.name[len("minyar.choice<"):-1], self.case)

    def child(self, index):
        if not 0 <= index < len(self.names):
            raise FormatError("invalid child index")
        if self.kind == "List":
            return self.sequence.at(index)
        if self.kind == "Map":
            sequence = self.values if index % 2 else self.keys
            return sequence.at(self.indices[index // 2])
        return self.value.field(self.payload_fields[index])


def child_index(names, name):
    try:
        return names.index(name)
    except ValueError:
        return -1
