import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

SCALARS = {1: 'int8_t', 2: 'uint8_t', 3: 'int16_t', 4: 'uint16_t',
           5: 'int32_t', 6: 'uint32_t', 7: 'int64_t', 8: 'uint64_t',
           9: 'float', 10: 'double', 11: 'bool', 12: 'uint32_t'}
VALUES = {'1': 'long long', '3': 'uint32_t', '4': 'bool', '5': 'void',
          '7': 'double', 'p': 'void *'}


def read_metadata(lines):
    layouts = {}
    calls = {}
    for line in lines:
        if line.startswith('; minyar-c-layout: '):
            parts = line.removeprefix('; minyar-c-layout: ').strip().split('|')
            if len(parts) < 5 or any(not re.fullmatch(r'[0-9,]+', part) for part in parts):
                raise ValueError('invalid C-layout ABI metadata')
            key, mode, size, alignment = map(int, parts[:4])
            fields = tuple(tuple(map(int, field.split(','))) for field in parts[4:])
            if mode not in (1, 2) or size <= 0 or alignment not in (1, 2, 4, 8) or any(
                    len(field) != 3 or field[1] + field[2] > size or field[2] <= 0 for field in fields):
                raise ValueError('invalid C-layout ABI fields')
            value = (mode, size, alignment, fields)
            if key in layouts and layouts[key] != value:
                raise ValueError('conflicting C-layout ABI metadata')
            layouts[key] = value
        elif line.startswith('; minyar-c-value: '):
            parts = line.removeprefix('; minyar-c-value: ').strip().split('|')
            if len(parts) < 2 or not re.fullmatch(r'minyar_[A-Za-z0-9_]+', parts[0]) or any(
                    not re.fullmatch(r'C[0-9]+|[13457p]', part) for part in parts[1:]):
                raise ValueError('invalid C-layout native ABI signature')
            if '5' in parts[2:]:
                raise ValueError('Nothing cannot be a C-layout ABI parameter')
            value = tuple(parts[1:])
            if parts[0] in calls and calls[parts[0]] != value:
                raise ValueError('conflicting C-layout native ABI signatures')
            calls[parts[0]] = value
    return layouts, calls


def source(lines):
    layouts, calls = read_metadata(lines)
    if not calls:
        return ''
    pieces = ['#include <stdint.h>\n#include <stddef.h>\n#include <stdbool.h>\n#include <string.h>\n',
              'extern void *minyar_c_record_copy(const void *, long long);\n']
    completed = set()
    active = set()

    def record(key):
        if key in completed:
            return
        if key in active or key not in layouts:
            raise ValueError('invalid inline C-layout record dependency')
        active.add(key)
        mode, size, alignment, fields = layouts[key]
        for kind, _, _ in fields:
            if kind >= 1000:
                record(kind - 1000)
        suffix = ' __attribute__((packed))' if mode == 2 else ''
        name = 'minyar_c_record_' + str(key)
        pieces.append('struct' + suffix + ' ' + name + ' {\n')
        for index, (kind, _, width) in enumerate(fields):
            if kind == 0:
                declaration = f'unsigned char field{index}[{width}]'
            elif kind >= 1000:
                declaration = f'struct minyar_c_record_{kind - 1000} field{index}'
            elif kind in SCALARS:
                declaration = f'{SCALARS[kind]} field{index}'
            else:
                raise ValueError('invalid C-layout scalar representation')
            pieces.append(declaration + ';\n')
        pieces.append('};\n')
        pieces.append(f'_Static_assert(sizeof(struct {name}) == {size}, "C-layout size mismatch");\n')
        pieces.append(f'_Static_assert(_Alignof(struct {name}) == {alignment}, "C-layout alignment mismatch");\n')
        for index, (_, offset, _) in enumerate(fields):
            pieces.append(f'_Static_assert(offsetof(struct {name}, field{index}) == {offset}, "C-layout offset mismatch");\n')
        active.remove(key)
        completed.add(key)

    def value_type(kind):
        if kind.startswith('C'):
            key = int(kind[1:])
            record(key)
            return 'struct minyar_c_record_' + str(key)
        return VALUES[kind]

    for callee, signature in sorted(calls.items()):
        result, *parameters = signature
        return_type = value_type(result)
        parameter_types = [value_type(kind) for kind in parameters]
        pieces.append(f'extern {return_type} {callee}(' + (', '.join(parameter_types) or 'void') + ');\n')
        bridge_return = 'void *' if result.startswith('C') else return_type
        arguments = [f'const void *argument{index}' if kind.startswith('C') else
                     f'{type_name} argument{index}' for index, (kind, type_name) in
                     enumerate(zip(parameters, parameter_types))]
        pieces.append(f'{bridge_return} minyar_c_value_{callee}(' + (', '.join(arguments) or 'void') + ') {\n')
        for index, (kind, type_name) in enumerate(zip(parameters, parameter_types)):
            if kind.startswith('C'):
                pieces.append(f'{type_name} value{index};\nmemcpy(&value{index}, argument{index}, sizeof(value{index}));\n')
        values = ', '.join(f'value{index}' if kind.startswith('C') else f'argument{index}'
                           for index, kind in enumerate(parameters))
        invocation = callee + '(' + values + ')'
        if result.startswith('C'):
            pieces.append(f'{return_type} value = {invocation};\nreturn minyar_c_record_copy(&value, sizeof(value));\n')
        elif result == '5':
            pieces.append(invocation + ';\n')
        else:
            pieces.append('return ' + invocation + ';\n')
        pieces.append('}\n')
    return ''.join(pieces)


def native_object(project, clang, flags, lines, identity, run):
    generated = source(lines)
    if not generated:
        return None
    digest = hashlib.sha256()
    digest.update(identity.digest())
    digest.update(json.dumps(flags).encode())
    digest.update(generated.encode())
    directory = Path(project) / 'build/native'
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / ('c-layout-abi-' + digest.hexdigest() + '.o')
    if not output.is_file():
        with tempfile.TemporaryDirectory(prefix='c-layout-abi-', dir=directory) as temporary:
            temporary = Path(temporary)
            input_path = temporary / 'abi.c'
            staged = temporary / 'abi.o'
            input_path.write_text(generated)
            run([clang, *flags, '-c', str(input_path), '-o', str(staged)])
            os.replace(staged, output)
    return str(output)
