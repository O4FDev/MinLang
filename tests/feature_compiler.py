"""Validate parsed feature dispatch and the generated ownership frontend."""
import os
from pathlib import Path
from regressions import ROOT
from regressions import LINK_FLAGS
from llvm_sanitizer import address_sanitizer_enabled


def accepts_managed_graph(test, source):
    result, llvm = test.compile(source)
    test.assertEqual(result.returncode, 86, result.stderr)
    test.assertFalse(llvm.exists(), 'ordinary compiler emitted an unsafe graph')
    default = 'minyarc-callbacks-sanitize' if address_sanitizer_enabled(LINK_FLAGS) else 'minyarc-callbacks'
    frontend = Path(os.environ.get('MINYAR_CALLBACK_COMPILER', ROOT / 'build' / default))
    compiled = test.evidence.run([str(frontend), str(llvm.with_suffix('.min')), str(llvm),
                                 *getattr(test, 'compiler_arguments', ())],
                                capture_output=True, text=True, timeout=30,
                                phase='compile-managed-graph-extension')
    test.assertEqual(compiled.returncode, 0, compiled.stderr)
    test.assertIn('; minyar-cycle-runtime: 1\n', llvm.read_text())
    return llvm
