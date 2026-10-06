"""Extract source and saved machine-code evidence for test accounting."""
from pathlib import Path
import json
import re

OUT = Path(__file__).resolve().parent
ROOT = OUT / 'inputs'
FINAL = ROOT / 'research/2026-10-memory/evidence/runtime-list-bulk-cpu/run-ws0ma9zu'
observations = []
for variant in ['baseline', 'candidate']:
    for profile in ['system', 'fixed']:
        assembly = FINAL / f'fixture-assembly-{variant}-{profile}.s'
        text = assembly.read_text()
        names = ['rc_object_count', 'rc_bytes', 'rc_bounded_last_work']
        if profile == 'system':
            names.append('rc_heap_allocation_count')
        fields = {}
        for name in names:
            references = [{'line': i, 'instruction': line} for i, line in enumerate(text.splitlines(), 1)
                          if '_' + name + '@PAGE' in line]
            assert references, (variant, profile, name)
            fields[name] = references
        linked = (FINAL / f'linked-machine-code-{variant}-{profile}.s').read_text()
        excerpts = []
        for name in ['minyar_list_add', 'rc_drop', 'minyar_rc_poll']:
            match = re.search(r'^_' + name + r':\n(.*?)(?=^_[^\s:]+:|\Z)', linked, re.M | re.S)
            assert match
            excerpts.append(match.group(0))
        filename = f'accounting-linked-{variant}-{profile}.s'
        (OUT / filename).write_text('\n'.join(excerpts))
        observations.append({'variant': variant, 'profile': profile,
                             'named_compiler_assembly_references': fields, 'linked_excerpt': filename})
result = {'timing_fixture_define': '#define MINYAR_RC_TESTING 1',
          'source_definitions': ['runtime/minyar_rc.h:78 (RC_ACCOUNT)', 'runtime/minyar_rc.h:97 (idle last-work)',
                                 'runtime/minyar_heap.h:5 (system allocation count)',
                                 'runtime/minyar_bounded_rc.h:370 (poll last-work)',
                                 'runtime/minyar_bounded_rc.h:380 (release last-work)'],
          'observations': observations,
          'measured_scope': 'Common result header/backing alloc and release; debt alloc/detach and poll/drain; last-work telemetry',
          'removed_scalar_prefix': 'Capacity-sufficient scalar minyar_list_add path has no RC_ACCOUNT or test-work updates',
          'eligibility': 'bulk_scalar uses references and ordinary rc_pending_count; test accounting fields do not feed eligibility',
          'inference_limit': 'Equal logical bookkeeping does not imply equal machine cost, permit subtraction, or identify an accounting-free ratio'}
(OUT / 'accounting-scope.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'four_builds': len(observations), 'accounting_enabled': True, 'native_execution': False}))
