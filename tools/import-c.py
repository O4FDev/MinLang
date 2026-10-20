#!/usr/bin/env python3
"""Import an explicitly selected, ownership-safe subset of a C header.

Clang parses declarations and evaluates all constants/layout queries. Nothing
from the header is executed. Generated files use Minyar's existing native ABI.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass


class ImportFailure(Exception):
    pass


IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z")
RESERVED = set("function record constant global public private let return if else while for in break continue use as true false Nothing Integer Float Boolean Text Bytes Character List Map Set Callback Result print fail exit abs min max clamp joinText wrappingAdd wrappingSubtract wrappingMultiply parallelEntry".split())
RESERVED.update("sizeOf alignOf offsetOf cView cAt cAddress cBytes FrozenBytes BytesChannel Thread ThreadStartResult ThreadJoinResult FrozenBytesChannel FrozenBytesResult NativeRegion NativeRegions NativeRegionResult nativeThreadSetup mapNativeRegion tryMapNativeRegion shareNativeRegions nativeRegionAddress threadKernelKick threadEventfd threadEventfdRead threadEventfdNotify freezeBytes freezeBytesTake copyFrozenBytes bytesChannel trySendBytes sendBytes tryReceiveBytes receiveBytes closeBytesChannel startThread joinThread startThreadResult joinThreadResult frozenBytesChannel trySendFrozen sendFrozen tryReceiveFrozen receiveFrozen closeFrozenChannel threadKernelRun".split())
INTRINSIC_LIBRARIES = set("machine machine_arm64 runtime diagnostics calldepth integer_overflow".split())


def identifier(name: str) -> str:
    if not IDENTIFIER.fullmatch(name) or name in RESERVED or name.startswith("minyarImport"):
        raise ImportFailure(f"C name '{name}' cannot be used as a Minyar declaration; use a C facade with a different name")
    return name


def walk(node):
    yield node
    for child in node.get("inner", []):
        yield from walk(child)


def value_of(node):
    for child in walk(node):
        if child.get("kind") == "ConstantExpr" and "value" in child:
            return int(child["value"])
    raise ImportFailure("Clang did not supply an integer constant value")


@dataclass
class CType:
    c: str
    minyar: str
    size: int
    alignment: int
    signed: bool = True
    record: str = ""
    floating: bool = False
    boolean: bool = False
    array: int = 0

    @property
    def language(self):
        if self.record:
            return self.record
        if self.c == "void":
            return "Nothing"
        if self.boolean:
            return "Boolean"
        if self.floating:
            return "Float"
        return "Integer"

    @property
    def abi(self):
        if self.record:
            return self.c
        return {"Nothing": "void", "Boolean": "_Bool", "Float": "double"}.get(self.language, "long long")


class Importer:
    def __init__(self, options, flags):
        self.options = options
        self.flags = flags
        self.header = Path(options.header).resolve(strict=True)
        if not self.header.is_file():
            raise ImportFailure("the header must be a regular file")
        if any(c in str(self.header) for c in '\\"\n\r'):
            raise ImportFailure("the header path cannot contain quotes, backslashes or line breaks")
        self.include = f'#include "{self.header}"\n'
        self.temporary = tempfile.TemporaryDirectory(prefix="minyar-import-c-")
        self.directory = Path(self.temporary.name)
        self.nodes = {}
        self.records_by_id = {}
        self.record_spellings = {}
        self.record_types = {}
        self.record_metadata = {}
        self.active_records = set()
        self.enum_types = {}
        self.enums_by_name = {}
        self.enums_by_id = {}
        self.enum_aliases = {}
        self.constants = {}
        self.functions = {}
        self.aliases = {}
        self.macros = {}
        self.exports = set()
        self.assertions = []
        self.min_declarations = []
        self.c_declarations = []

    def clang(self, arguments, source=None):
        command = [self.options.clang, "-x", "c", "-std=c11", *self.flags, *arguments]
        try:
            result = subprocess.run(command, input=source, text=True, encoding="utf-8", capture_output=True, timeout=self.options.timeout)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ImportFailure(f"cannot complete Clang header inspection: {error}") from error
        if result.returncode:
            raise ImportFailure("Clang rejected the selected C interface:\n" + result.stderr.strip())
        return result.stdout

    def ast(self, source):
        path = self.directory / "probe.c"
        path.write_text(source, encoding="utf-8")
        raw = self.clang(["-Xclang", "-ast-dump=json", "-fsyntax-only", str(path)])
        try:
            return json.loads(raw)
        except (ValueError, TypeError) as error:
            raise ImportFailure("Clang did not produce a supported JSON AST") from error

    def query(self, expressions):
        names = list(expressions)
        body = ",\n".join(f"minyar_import_probe_{index} = ({expressions[name]})" for index, name in enumerate(names))
        ast = self.ast(self.include + "\nenum {\n" + body + "\n};\n")
        found = {}
        for node in walk(ast):
            if node.get("kind") == "EnumConstantDecl" and node.get("name", "").startswith("minyar_import_probe_"):
                found[int(node["name"].rsplit("_", 1)[1])] = value_of(node)
        if len(found) != len(names):
            raise ImportFailure("Clang omitted a requested layout or constant query")
        return {name: found[index] for index, name in enumerate(names)}

    def inspect(self):
        ast = self.ast(self.include)
        for node in ast.get("inner", []):
            kind = node.get("kind")
            name = node.get("name")
            if kind == "RecordDecl" and node.get("completeDefinition"):
                self.records_by_id[node["id"]] = node
                if name:
                    self.record_spellings[node.get("tagUsed", "struct") + " " + name] = node["id"]
            if name and kind in {"TypedefDecl", "RecordDecl", "EnumDecl", "FunctionDecl", "VarDecl"}:
                previous = self.nodes.get(name)
                if previous is None or node.get("completeDefinition") or kind == "TypedefDecl" or kind == "FunctionDecl":
                    self.nodes[name] = node
            if kind == "EnumDecl":
                self.enums_by_id[node["id"]] = node
                if name:
                    self.enums_by_name[name] = node
                for child in node.get("inner", []):
                    if child.get("kind") == "EnumConstantDecl":
                        self.nodes[child["name"]] = child
        for name, node in self.nodes.items():
            if node.get("kind") == "TypedefDecl":
                # A PointerType/FunctionProtoType also contains its pointee's
                # EnumType/RecordType. Only direct value aliases can register
                # here; otherwise type() must inspect the canonical wrapper.
                spellings = " ".join(node.get("type", {}).values())
                if any(character in spellings for character in "*()[]") or re.search(r"\b(volatile|_Atomic|__attribute__)\b", spellings):
                    continue
                for child in walk(node):
                    if child.get("kind") == "RecordType":
                        key = child.get("decl", {}).get("id")
                        if key in self.records_by_id:
                            self.record_spellings[name] = key
                    if child.get("kind") == "EnumType":
                        key = child.get("decl", {}).get("id")
                        if key in self.enums_by_id:
                            self.enum_aliases[name] = self.enums_by_id[key]
        raw_macros = self.clang(["-E", "-dM", str(self.header)])
        for line in raw_macros.splitlines():
            match = re.match(r"#define ([A-Za-z_]\w*)(.*)", line)
            if match:
                self.macros[match[1]] = match[2]
        queries = {"pointer": "sizeof(void *)", "charbits": "__CHAR_BIT__", "char_unsigned": "((char)-1 > 0)"}
        for name in ["char", "short", "int", "long", "long long", "float", "double", "_Bool"]:
            queries["size:" + name] = f"sizeof({name})"
            queries["align:" + name] = f"_Alignof({name})"
        self.platform = self.query(queries)
        if self.platform["pointer"] != 8 or self.platform["charbits"] != 8 or self.platform["size:_Bool"] != 1 or self.platform["size:float"] != 4 or self.platform["size:double"] != 8:
            raise ImportFailure("this Minyar C-layout ABI requires 64-bit pointers, 8-bit bytes, 1-byte Boolean and IEEE float/double storage")

    def reserve(self, name):
        identifier(name)
        if name in self.exports:
            raise ImportFailure(f"more than one C declaration would export '{name}'")
        self.exports.add(name)

    def type(self, spelling, context):
        original = spelling
        if re.search(r"\b(volatile|_Atomic|__attribute__)\b", spelling):
            raise ImportFailure(f"{context}: volatile, atomic and attributed types need a hand-written facade")
        spelling = re.sub(r"\bconst\b", "", spelling)
        spelling = " ".join(spelling.split())
        if "*" in spelling or "(" in spelling or ")" in spelling:
            raise ImportFailure(f"{context}: pointer and callback ownership cannot be inferred; provide a C facade")
        array = re.fullmatch(r"(.+?)\s*\[\s*(\d+)\s*\]", spelling)
        if array:
            element = self.type(array[1], context)
            count = int(array[2])
            if element.size != 1 or element.record or element.boolean or element.floating or not 0 < count <= 1073741824:
                raise ImportFailure(f"{context}: only fixed byte arrays are supported")
            return CType(f"{element.c}[{count}]", f"Bytes[{count}]", count, 1, array=count)
        if "[" in spelling:
            raise ImportFailure(f"{context}: flexible or variable arrays cannot have a checked fixed layout")
        if spelling in self.record_spellings:
            return self.record(self.record_spellings[spelling], spelling)
        node = self.nodes.get(spelling)
        if spelling in self.enum_aliases:
            if spelling not in self.enum_types:
                values = self.query({"size": f"sizeof({spelling})", "align": f"_Alignof({spelling})", "signed": f"(({spelling})-1 < ({spelling})0)"})
                self.enum_types[spelling] = self.integer(spelling, values["size"], values["align"], bool(values["signed"]), context)
            return self.enum_types[spelling]
        if node and node.get("kind") == "TypedefDecl":
            target = node["type"].get("desugaredQualType", node["type"]["qualType"])
            if target == spelling:
                raise ImportFailure(f"{context}: recursive or unsupported typedef '{spelling}'")
            return self.type(target, context)
        if spelling.startswith("enum ") or (node and node.get("kind") == "EnumDecl"):
            if spelling not in self.enum_types:
                c = spelling if spelling.startswith("enum ") else "enum " + spelling
                values = self.query({"size": f"sizeof({c})", "align": f"_Alignof({c})", "signed": f"(({c})-1 < ({c})0)"})
                self.enum_types[spelling] = self.integer(c, values["size"], values["align"], bool(values["signed"]), context)
            return self.enum_types[spelling]
        if spelling == "void":
            return CType("void", "Nothing", 0, 1)
        if spelling in {"_Bool", "bool"}:
            return CType("_Bool", "Boolean", 1, 1, boolean=True)
        if spelling in {"float", "double"}:
            size = self.platform["size:" + spelling]
            if self.platform["align:" + spelling] != size:
                raise ImportFailure(f"{context}: floating-point alignment cannot be represented by Minyar")
            return CType(spelling, f"Float{size * 8}", size, self.platform["align:" + spelling], floating=True)
        unsigned = spelling.startswith("unsigned")
        base = re.sub(r"\b(signed|unsigned)\b", "", spelling).strip()
        base = re.sub(r"\s+int$", "", base) or "int"
        if base not in {"char", "short", "int", "long", "long long"}:
            raise ImportFailure(f"{context}: C type '{original}' is not supported")
        if spelling == "char":
            unsigned = bool(self.platform["char_unsigned"])
        return self.integer(original, self.platform["size:" + base], self.platform["align:" + base], not unsigned, context)

    def integer(self, c, size, alignment, signed, context):
        if size not in {1, 2, 4, 8} or alignment != size:
            raise ImportFailure(f"{context}: integer storage does not match Minyar's fixed-width layout")
        assertion = f'_Static_assert(sizeof({c}) == {size} && _Alignof({c}) == {alignment} && ((({c})-1 < ({c})0) == {int(signed)}), "C scalar ABI changed: {c}");'
        if assertion not in self.assertions:
            self.assertions.append(assertion)
        return CType(c, ("Int" if signed else "UInt") + str(size * 8), size, alignment, signed=signed)

    def record(self, key, preferred):
        if key in self.record_types:
            return self.record_types[key]
        if key in self.active_records:
            raise ImportFailure("recursive inline C records cannot have a finite layout")
        self.active_records.add(key)
        node = self.records_by_id[key]
        if node.get("tagUsed") != "struct":
            raise ImportFailure(f"'{preferred}': unions are not supported; provide a tagged C facade")
        name = preferred if IDENTIFIER.fullmatch(preferred) else node.get("name", "")
        self.reserve(name)
        c = preferred
        children = node.get("inner", [])
        packed = any(child.get("kind") == "PackedAttr" for child in children)
        if any(child.get("kind", "").endswith("Attr") and child.get("kind") not in {"PackedAttr", "MaxFieldAlignmentAttr"} for child in children):
            raise ImportFailure(f"'{name}': attributed/aligned structs require a C facade")
        fields = []
        size = 0
        alignment = 1
        queries = {"record:size": f"sizeof({c})", "record:alignment": f"_Alignof({c})"}
        for field in children:
            if field.get("kind") != "FieldDecl":
                continue
            field_name = field.get("name", "")
            if field.get("isBitfield") or not field_name:
                raise ImportFailure(f"'{name}': bitfields and anonymous fields require a C facade")
            identifier(field_name)
            if any(child.get("kind", "").endswith("Attr") for child in field.get("inner", [])):
                raise ImportFailure(f"'{name}.{field_name}': attributed fields require a C facade")
            kind = self.type(field["type"]["qualType"], name + "." + field_name)
            if kind.c == "void":
                raise ImportFailure(f"'{name}.{field_name}': a field cannot have void type")
            field_alignment = 1 if packed else kind.alignment
            size = (size + field_alignment - 1) // field_alignment * field_alignment
            fields.append({"name": field_name, "type": kind.minyar, "offset": size, "size": kind.size})
            self.assertions.append(f'_Static_assert(__builtin_types_compatible_p(__typeof__((({c} *)0)->{field_name}), {kind.c}), "C field type changed: {name}.{field_name}");')
            queries["offset:" + field_name] = f"__builtin_offsetof({c}, {field_name})"
            queries["width:" + field_name] = f"sizeof((({c} *)0)->{field_name})"
            size += kind.size
            alignment = max(alignment, field_alignment)
        if not fields:
            raise ImportFailure(f"'{name}': empty and opaque structs cannot be imported as values")
        size = (size + alignment - 1) // alignment * alignment
        if size > 1073741824:
            raise ImportFailure(f"'{name}': C-layout size exceeds Minyar's limit")
        actual = self.query(queries)
        expected = {"record:size": size, "record:alignment": alignment}
        for field in fields:
            expected["offset:" + field["name"]] = field["offset"]
            expected["width:" + field["name"]] = field["size"]
        if actual != expected:
            raise ImportFailure(f"'{name}': Clang's layout cannot be represented by Minyar (expected {expected}, found {actual}); provide a C facade")
        for label, expression in queries.items():
            self.assertions.append(f'_Static_assert(({expression}) == {actual[label]}, "C layout changed: {name}.{label}");')
        mode = "c_packed" if packed else "c"
        source = [f'public record {name} native "{mode}" {{']
        source.extend(f'    {field["name"]}: {field["type"]}' for field in fields)
        source.append("}")
        self.min_declarations.append("\n".join(source))
        result = CType(c, name, size, alignment, record=name)
        self.record_types[key] = result
        self.record_metadata[name] = {"cType": c, "size": size, "alignment": alignment, "packed": packed, "fields": fields}
        self.active_records.remove(key)
        return result

    def constant(self, name):
        if name in self.constants:
            return
        self.reserve(name)
        macro = self.macros.get(name)
        if macro is not None and macro.startswith("("):
            raise ImportFailure(f"'{name}': function-like macros cannot be imported as constants")
        value = self.query({"value": name})["value"]
        if not -(1 << 63) <= value < (1 << 63):
            raise ImportFailure(f"'{name}': the C constant does not fit in a Minyar Integer")
        self.constants[name] = value
        self.assertions.append(f'_Static_assert(({name}) == ({value if value != -(1 << 63) else "(-9223372036854775807LL - 1)"}), "C constant changed: {name}");')
        self.min_declarations.append(f"public constant {name}: Integer = {value}")

    def function(self, name, node):
        self.reserve(name)
        if node.get("variadic"):
            raise ImportFailure(f"'{name}': variadic functions require a fixed-signature C facade")
        signature = node["type"]["qualType"]
        if signature.endswith("()"):
            raise ImportFailure(f"'{name}': old-style functions without a parameter prototype require a fixed-signature C facade")
        if not re.fullmatch(r"[^()]+ \([^()]*\)", signature):
            raise ImportFailure(f"'{name}': attributed or callback function signatures require a C facade")
        result = self.type(signature.split(" (", 1)[0], name + " result")
        parameters = []
        for index, child in enumerate(n for n in node.get("inner", []) if n.get("kind") == "ParmVarDecl"):
            parameter_name = child.get("name") or "argument" + str(index)
            identifier(parameter_name)
            kind = self.type(child["type"]["qualType"], name + "." + parameter_name)
            if kind.c == "void" or kind.array:
                raise ImportFailure(f"'{name}.{parameter_name}': invalid C parameter")
            parameters.append((parameter_name, kind))
        if len({name for name, _ in parameters}) != len(parameters):
            raise ImportFailure(f"'{name}': duplicate parameter names")
        c_signature = result.c + " (*)(" + (", ".join(kind.c for _, kind in parameters) or "void") + ")"
        self.assertions.append(f'_Static_assert(__builtin_types_compatible_p(__typeof__(&{name}), {c_signature}), "C function signature changed: {name}");')
        raw = "minyarImport" + name
        language_parameters = ", ".join(f"{parameter}: {kind.language}" for parameter, kind in parameters)
        has_record = result.record or any(kind.record for _, kind in parameters)
        suffix = " value" if has_record else ""
        public = [f"public function {name}({language_parameters}): {result.language} {{"]
        for parameter, kind in parameters:
            if kind.language == "Integer" and kind.size < 8:
                low = -(1 << (kind.size * 8 - 1)) if kind.signed else 0
                high = (1 << (kind.size * 8 - int(kind.signed))) - 1
                public.append(f"    if {parameter} < {low} || {parameter} > {high} {{ fail(\"C argument '{name}.{parameter}' is outside its declared range.\") }}")
            if kind.floating and kind.size == 4:
                public.append(f"    if {parameter} < -3.4028234663852886e38 || {parameter} > 3.4028234663852886e38 {{ fail(\"C argument '{name}.{parameter}' is outside its declared range.\") }}")
        call = raw + "(" + ", ".join(parameter for parameter, _ in parameters) + ")"
        public.append("    " + ("return " if result.language != "Nothing" else "") + call)
        public.append("}")
        self.min_declarations.append(f'function {raw}({language_parameters}): {result.language} {{ native "{self.options.library}"{suffix} }}\n' + "\n".join(public))
        c_parameters = ", ".join(f"{kind.abi} minyar_argument_{index}" for index, (_, kind) in enumerate(parameters)) or "void"
        values = []
        for index, (_, kind) in enumerate(parameters):
            value = f"minyar_argument_{index}"
            values.append(value if kind.record else f"({kind.c}){value}")
        invocation = name + "(" + ", ".join(values) + ")"
        if result.language == "Nothing":
            body = invocation + ";"
        elif not result.record and not result.floating and not result.boolean and not result.signed and result.size == 8:
            body = f"{result.c} value = {invocation}; long long bits; __builtin_memcpy(&bits, &value, sizeof(bits)); return bits;"
        else:
            body = "return " + invocation + ";"
        self.c_declarations.append(f"{result.abi} minyar_{self.options.library}_{raw}({c_parameters}) {{ {body} }}")
        self.functions[name] = {"result": result.language, "cResult": result.c, "cSignature": c_signature, "parameters": [{"name": parameter, "type": kind.language, "cType": kind.c} for parameter, kind in parameters], "aggregate": bool(has_record)}

    def select(self, name):
        if name in self.exports:
            return
        node = self.nodes.get(name)
        if node and node.get("kind") == "FunctionDecl":
            self.function(name, node)
        elif name in self.record_spellings:
            kind = self.type(name, name)
            if kind.record != name:
                self.reserve(name)
                self.min_declarations.append(f"public type {name} = {kind.record}")
        elif node and node.get("kind") == "RecordDecl":
            kind = self.record(node["id"], node.get("tagUsed", "struct") + " " + name)
            if kind.record != name:
                self.reserve(name)
                self.min_declarations.append(f"public type {name} = {kind.record}")
        elif node and node.get("kind") == "EnumDecl":
            self.reserve(name)
            self.min_declarations.append(f"public type {name} = Integer")
            for child in node.get("inner", []):
                if child.get("kind") == "EnumConstantDecl":
                    self.constant(child["name"])
        elif node and node.get("kind") == "TypedefDecl":
            kind = self.type(name, name)
            if kind.array:
                raise ImportFailure(f"'{name}': fixed byte arrays can only be imported as struct fields")
            if kind.record and kind.record == name:
                return
            self.reserve(name)
            self.min_declarations.append(f"public type {name} = {kind.language}")
            enum = self.enum_aliases.get(name)
            if enum:
                for child in enum.get("inner", []):
                    if child.get("kind") == "EnumConstantDecl":
                        self.constant(child["name"])
        elif node and node.get("kind") == "VarDecl":
            spelling = node["type"]["qualType"]
            if "const" not in spelling.split() or node.get("storageClass") != "static":
                raise ImportFailure(f"'{name}': mutable or external data cannot be imported as a constant")
            self.constant(name)
        elif (node and node.get("kind") == "EnumConstantDecl") or name in self.macros:
            self.constant(name)
        else:
            raise ImportFailure(f"the C header has no importable declaration named '{name}'")

    def generate(self):
        self.inspect()
        for name in self.options.include:
            identifier(name)
            self.select(name)
        c_source = "/* Generated by tools/import-c.py. Regenerate for each target ABI. */\n" + self.include
        c_source += "\n_Static_assert(sizeof(long long) == 8 && sizeof(void *) == 8 && __CHAR_BIT__ == 8 && sizeof(_Bool) == 1 && _Alignof(_Bool) == 1 && sizeof(float) == 4 && _Alignof(float) == 4 && sizeof(double) == 8 && _Alignof(double) == 8, \"Minyar scalar ABI changed\");\n"
        c_source += "\n".join(self.assertions) + "\n\n" + "\n".join(self.c_declarations) + "\n"
        # Check against the original declarations before replacing any outputs.
        path = self.directory / "adapter.c"
        path.write_text(c_source, encoding="utf-8")
        self.clang(["-fsyntax-only", str(path)])
        source = "// Generated by tools/import-c.py. Regenerate for each target ABI.\n\n" + "\n\n".join(self.min_declarations) + "\n"
        target = self.clang(["-print-target-triple"]).strip()
        metadata = {"version": 1, "header": str(self.header), "headerSha256": hashlib.sha256(self.header.read_bytes()).hexdigest(), "library": self.options.library, "clang": self.options.clang, "clangVersion": self.clang(["--version"]).splitlines()[0], "target": target, "platform": self.platform, "clangFlags": self.flags, "selected": self.options.include, "records": self.record_metadata, "constants": self.constants, "functions": self.functions, "pointerOwnership": "unsupported"}
        return {".min": source, ".c": c_source, ".json": json.dumps(metadata, indent=2, sort_keys=True) + "\n"}


def main(arguments=None):
    arguments = list(sys.argv[1:] if arguments is None else arguments)
    flags = []
    if "--" in arguments:
        separator = arguments.index("--")
        arguments, flags = arguments[:separator], arguments[separator + 1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("header")
    parser.add_argument("--output", required=True, help="output prefix for .min, .c and .json")
    parser.add_argument("--library", required=True, help="unique native package name")
    parser.add_argument("--include", action="append", required=True, help="C declaration to import; repeat to select more")
    parser.add_argument("--clang", default=os.environ.get("MINYAR_CLANG", "clang"))
    parser.add_argument("--timeout", type=int, default=60, help="maximum seconds for each Clang invocation")
    options = parser.parse_args(arguments)
    try:
        if not IDENTIFIER.fullmatch(options.library) or options.library in INTRINSIC_LIBRARIES:
            raise ImportFailure("--library must be an ASCII identifier distinct from compiler intrinsic packages")
        if options.timeout < 1 or options.timeout > 600:
            raise ImportFailure("--timeout must be between 1 and 600 seconds")
        importer = Importer(options, flags)
        try:
            generated = importer.generate()
        finally:
            importer.temporary.cleanup()
        prefix = Path(options.output)
        prefix.parent.mkdir(parents=True, exist_ok=True)
        staged = []
        try:
            for suffix, content in generated.items():
                destination = Path(str(prefix) + suffix)
                descriptor, temporary = tempfile.mkstemp(prefix=destination.name + ".", dir=destination.parent)
                with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                    stream.write(content)
                staged.append((Path(temporary), destination))
            for temporary, destination in staged:
                os.replace(temporary, destination)
        finally:
            for temporary, _ in staged:
                temporary.unlink(missing_ok=True)
    except (ImportFailure, OSError, ValueError, KeyError) as error:
        print(f"import-c: error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
