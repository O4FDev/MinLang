import re
from pathlib import Path
import subprocess
import sys


def validate_compile_output(result, output, phase='self-compile'):
    if result.returncode != 0:
        raise SystemExit(f'{phase} failed with status {result.returncode}:\n{result.stderr}')
    if not output.is_file():
        raise SystemExit(f'{phase} produced no LLVM output')
    text = output.read_text()
    if not re.search(r'^define (?:fastcc )?i32 @main\(', text, re.M):
        raise SystemExit(f'{phase} produced invalid compiler LLVM output')


def check_compiler_behavior(output):
    script = Path(__file__).with_name('compiler-behavior.py')
    result = subprocess.run([sys.executable, str(script), '--ir', str(output), '--profile', 'errors'],
                            capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        raise SystemExit(f'self-compiled compiler behavior failed:\n{result.stdout}{result.stderr}')
