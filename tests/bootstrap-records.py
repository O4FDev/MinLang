#!/usr/bin/env python3
"""The bootstrap's typed record subset supports compiler source maps."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
from clang_helpers import clang_command

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = Path(os.environ.get('MINYAR_TEST_BOOTSTRAP', ROOT / 'build/stage0'))
CLANG = os.environ.get('MINYAR_TEST_CLANG', 'clang')
LINK_FLAGS = shlex.split(os.environ.get('MINYAR_TEST_LINK_FLAGS', ''))

with tempfile.TemporaryDirectory(prefix='minyar-bootstrap-records-') as temporary:
    work = Path(temporary)
    source = work / 'records.min'
    llvm = work / 'records.ll'
    source.write_text('''record Coordinates { values: List<Integer>; title: Text; valid: Boolean; letter: Character; counter: Integer }
function make(): Coordinates {
    let values: List<Integer> = [40, 41]
    return Coordinates { letter: 'Q', valid: true, title: "source", values: values, counter: 0 }
}
function read(location: Coordinates): Integer { return location.values[0] + 2 }
function main(): Integer {
    let location = make()
    print(read(location))
    print(location.title)
    print(location.valid)
    print(location.letter)
    location.title = "changed"
    location.valid = false
    location.letter = 'Z'
    location.counter = 42
    print(location.title)
    print(location.valid)
    print(location.letter)
    print(location.counter)
    let bytes = Bytes("Aé🙂")
    print(bytes.length)
    print(bytes[0])
    print(bytes[1])
    print(Bytes(3).length)
    print(Text(Bytes("ABC")))
    let frames = Bytes(0)
    frames.addInt64(-42)
    print(frames.getInt64(0))
    frames.setInt64(0, 42)
    print(frames.getInt64(0))
    print("first
second")
    return 0
}
''')
    result = subprocess.run([BOOTSTRAP, source, '-o', llvm], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    executable = work / 'records'
    linked = subprocess.run(clang_command([CLANG, '-O2', *LINK_FLAGS, '-DMINYAR_COMPILER_ARENA',
                                           '-Wno-override-module', llvm, ROOT / 'runtime/minyar_runtime.c',
                                           '-o', executable]), capture_output=True, text=True)
    assert linked.returncode == 0, linked.stderr
    assert subprocess.check_output([executable], text=True) == '42\nsource\ntrue\nQ\nchanged\nfalse\nZ\n42\n7\n65\n195\n3\nABC\n-42\n42\nfirst\nsecond\n'
    failures = [
        ('function main(): Integer { let text = "first\nsecond"\n    print(missing)\nreturn 0 }\n', 'line 3, column 11'),
        ('function main(): Integer { let bytes = Bytes(0); print(bytes == bytes); return 0 }\n', 'Bytes cannot be compared'),
        ('function main(): Integer { let bytes = Bytes(true); return 0 }\n', 'Bytes expects one Integer or Text value'),
        ('record Pair { value: Integer }\nfunction main(): Integer { let p = Pair { value: 1 }; p.value = \"bad\"; return 0 }\n', 'this field contains'),
        ('record Pair { value: Integer; value: Text }\n', 'more than once'),
        ('record Pair { value: Integer }\nrecord Pair { value: Integer }\n', 'more than once'),
        ('record Pair { value: Integer }\nfunction main(): Integer { let p = Pair { value: "bad" }; return 0 }\n', 'different type'),
        ('record Pair { left: Integer; right: Integer }\nfunction main(): Integer { let p = Pair { left: 1 }; return 0 }\n', 'missing field'),
        ('record Pair { value: Integer }\nfunction main(): Integer { let p = Pair { value: 1, value: 2 }; return 0 }\n', 'more than once'),
        ('record Pair { value: Integer }\nfunction main(): Integer { let p = Pair { other: 1 }; return 0 }\n', 'does not have a field'),
        ('record Pair { value: Integer }\nfunction main(): Integer { let p = Pair { value: 1 }; print(p.other); return 0 }\n', 'does not have a field'),
    ]
    for text, message in failures:
        text = text.replace('; return', '\nreturn').replace('; print', '\nprint')
        source.write_text(text + 'function main(): Integer { return 0 }\n' if 'function main' not in text else text)
        result = subprocess.run([BOOTSTRAP, source, '-o', llvm], capture_output=True, text=True)
        assert result.returncode != 0 and message in result.stderr, (text, result.stderr)

print('bootstrap records: typed construction, reordered fields, field access and invalid declarations verified')
