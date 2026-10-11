"""Package regressions use the same parsed feature dispatch and native linker as the launcher."""
import os
from pathlib import Path
import shlex
import sys
from regressions import CompilerTestCase, ROOT, CLANG, LINK_FLAGS
from llvm_sanitizer import address_sanitizer_enabled, prepare_llvm_for_link


class PackageCompilerTestCase(CompilerTestCase):
    def compile(self, source):
        result, llvm = super().compile(source)
        if result.returncode == 86:
            self.assertFalse(llvm.exists(), 'ordinary compiler emitted an unsafe graph')
            sanitized = address_sanitizer_enabled(LINK_FLAGS)
            name = 'minyarc-callbacks-sanitize' if sanitized else 'minyarc-callbacks'
            frontend = Path(os.environ.get('MINYAR_CALLBACK_COMPILER', ROOT / 'build' / name))
            result = self.evidence.run([str(frontend), str(llvm.with_suffix('.min')), str(llvm),
                                       *getattr(self, 'compiler_arguments', ())],
                                      capture_output=True, text=True, timeout=30,
                                      phase='compile-package-feature-dispatch')
            if result.returncode == 0:
                self.assertIn('; minyar-cycle-runtime: 1\n', llvm.read_text())
                prepare_llvm_for_link(llvm, LINK_FLAGS)
        return result, llvm

    def link_program(self, llvm, optimization, exe):
        sanitized = address_sanitizer_enabled(LINK_FLAGS)
        name = 'minyar-default-runtime-sanitize.o' if sanitized else 'minyar-default-runtime.o'
        runtime = ROOT / 'build' / name
        environment = dict(os.environ, MINYAR_CLANG=CLANG,
                           MINYAR_CLANG_FLAGS=shlex.join([optimization, *LINK_FLAGS, '-Wno-override-module']),
                           MINYAR_NATIVE_FLAGS=shlex.join([optimization, *LINK_FLAGS, '-Wno-override-module']),
                           MINYAR_RUNTIME_FLAGS=shlex.join(['-O1' if sanitized else '-O2',
                                                          *LINK_FLAGS, '-Wno-override-module']))
        return self.evidence.run([sys.executable, str(ROOT / 'tools/clang-driver.py'), 'link',
                                  str(ROOT), str(llvm), str(runtime), str(exe), '0'],
                                 env=environment, capture_output=True, text=True, timeout=30,
                                 phase='link-package-native-metadata')
