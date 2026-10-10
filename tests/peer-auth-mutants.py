#!/usr/bin/env python3
"""Deliberate weakened policy must be killed by a named hostile-input case."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MUTANTS = [
    ('signature', 'peerauth.min', '!verify(token.slice(0, dots[1]), signature, key)', 'false', 'signature bit mutation'),
    ('exit', 'peerauth.min', 'field(claims, "exit_id") != authenticatedExitID', 'false', "claim exit_id 'exit-b'"),
    ('connection', 'peerauth.min', 'field(claims, "conn_id") != requestConnID', 'false', 'wrong connection'),
    ('deadline', 'peerauth.min', 'establishmentDeadlineSeconds > expiry', 'false', 'deadline after expiry'),
    ('lifetime', 'peerauth.min', 'expiry - issued > 60', 'false', 'claim exp 1061'),
    ('pad-bits', 'peerauth.min', 'if value != 0 { return Bytes() }', 'if false { return Bytes() }', 'noncanonical signature pad bits'),
    ('duplicates', 'json.min', 'return parseUnique(Text(source))', 'return parseText(Text(source), true)', 'duplicate decoded header key'),
]


def main():
    for name, filename, before, after, expected in MUTANTS:
        with tempfile.TemporaryDirectory(prefix='minyar-auth-mutant-') as directory:
            directory = Path(directory)
            source = (ROOT / 'library' / filename).read_text()
            assert source.count(before) == 1, (name, 'mutation site drift')
            (directory / filename).write_text(source.replace(before, after))
            result = subprocess.run([sys.executable, str(ROOT / 'tests/peer-auth.py'), '--library', str(directory)],
                                    env=os.environ.copy(), capture_output=True, text=True, timeout=300)
            assert result.returncode != 0 and expected in result.stderr and 'AssertionError' in result.stderr, (name, result.returncode, result.stdout, result.stderr)
            print(f'Killed {name}: {expected}', flush=True)
    print(f'Peer auth: all {len(MUTANTS)} deliberate policy mutations killed')


if __name__ == '__main__':
    main()
