"""Feature-agnostic declaration blocks and shared module assembly contracts."""
import json
import unittest
from regressions import CompilerTestCase, ROOT


def helpers():
    source = (ROOT / 'build/compiler.min').read_text()
    result = []
    for name in ('findText', 'startsDeclaration', 'hasGlobalDeclarations', 'deduplicateGlobalDeclarations'):
        start = source.index('function ' + name + '(')
        end = source.index('\n}\n', start) + 3
        result.append(source[start:end])
    return '\n'.join(result)


class FeatureDeclarations(CompilerTestCase):
    def test_combined_and_individual_blocks_share_program_declarations(self):
        combined = ''.join(f'declare void @feature{i}(ptr)\n' for i in range(4))
        individual = [f'declare void @feature{i}(ptr)\n' for i in range(10)]
        seen = set()
        expected = []
        sources = [combined, *individual, combined]
        program = [helpers(), 'let seen: List<Text> = []']
        for block in sources:
            # Independent Python line-set oracle, preserving first occurrence.
            kept = []
            for line in block.splitlines(keepends=True):
                if line not in seen:
                    seen.add(line)
                    kept.append(line)
            expected.append(''.join(kept) + '\n')
            program.append('print(deduplicateGlobalDeclarations(' + json.dumps(block) + ', seen))')
        self.executes('\n'.join(program), ''.join(expected))

    def test_definition_body_and_ordinary_globals_are_preserved(self):
        declaration = 'declare void @shared(ptr)\n'
        body = 'define void @f() {\n; λ unchanged body\n}\n' + declaration
        self.executes(helpers() + '\nlet seen: List<Text> = []\n'
                      'deduplicateGlobalDeclarations(' + json.dumps(declaration) + ', seen)\n'
                      'print(deduplicateGlobalDeclarations(' + json.dumps(declaration + body, ensure_ascii=False) + ', seen))\n'
                      'print(hasGlobalDeclarations([' + json.dumps('@literal = constant [9 x i8] c"declare "\n') + ']))\n'
                      'print(hasGlobalDeclarations([' + json.dumps(body, ensure_ascii=False) + ']))\n'
                      'print(hasGlobalDeclarations([' + json.dumps('; λ feature header\n' + declaration, ensure_ascii=False) + ']))\n',
                      body + '\nfalse\nfalse\ntrue\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
