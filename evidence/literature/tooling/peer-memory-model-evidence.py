#!/usr/bin/env python3
"""Regenerate only this lane's pure-model evidence, without repinning sources."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys


root = Path(__file__).resolve().parent.parent
path = root / 'tests/peer-memory-model-accounting.py'
base = root / 'research/2026-10-memory'
result = subprocess.run([sys.executable, str(path)], cwd=root,
                        capture_output=True, text=True)
source_map = json.loads((base / 'literature-accounting-source-map.json').read_text())
paths = list(source_map['sources']) + ['tests/peer-memory-model-accounting.py',
                                     'tests/peer-memory-model-evidence.py']
evidence = {'status': 'passed' if result.returncode == 0 else 'failed',
            'scope': 'Pure Python model only; no compiled-C execution or universal theorem.',
            'command': [sys.executable, 'tests/peer-memory-model-accounting.py'],
            'exit_code': result.returncode,
            'sources': {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths},
            'stdout': result.stdout, 'stderr': result.stderr}
(base / 'literature-accounting-model-green.json').write_text(json.dumps(evidence, indent=2) + '\n')
if result.returncode:
    print(result.stderr, file=sys.stderr)
    raise SystemExit(result.returncode)

spec = importlib.util.spec_from_file_location('accounting_model', path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
capture = module.capture_trace_state
traces = []

model = module.Model(1)
model.enter(0)
model.new('root', 'text')
model.new('view', 'text', backing='root')
model.release('root')
model.keep('view')
model.step()
steps = [capture(model, 'detached single view owner')]
while model.pending:
    work = model.poll(1)
    steps.append(dict(capture(model, 'poll(1)'), work=work))
traces.append({'name': 'view-root-from-partial-chunk-K1', 'steps': steps})

model = module.Model(5, optimized=True)
model.new('leaf', 'text')
child = 'leaf'
for i in range(4):
    parent = model.new('unary' + str(i), fields=[child])
    model.release(child)
    child = parent
model.release(child)
steps = [capture(model, 'one unary chain task')]
work = model.poll(5)
steps.append(dict(capture(model, 'odd-budget fused poll(5)'), work=work))
model.enter(1)
model.keep(model.new('temporary', 'text'))
model.local(0, model.new('local', 'text'), take=True)
model.leave()
steps.append(capture(model, 'frame and chunk arrival'))
while model.pending:
    work = model.poll(1)
    steps.append(dict(capture(model, 'poll(1)'), work=work))
traces.append({'name': 'odd-unary-fusion-then-other-queues', 'steps': steps})

model = module.Model(1)
model.new('root', 'text')
model.new('view', 'text', backing='root')
steps = [capture(model, 'objects prepared while no cleanup is pending')]
operations = [('minyar_rc_enter(0)', lambda: model.public_enter(0)),
              ('minyar_rc_release(root)', lambda: model.release('root', service=True)),
              ('minyar_rc_keep(view)', lambda: model.public_keep('view')),
              ('minyar_rc_step()', model.public_step),
              ('minyar_rc_poll(1)', lambda: model.poll(1)),
              ('minyar_rc_poll(1)', lambda: model.poll(1)),
              ('minyar_rc_leave()', model.public_leave)]
for label, operation in operations:
    work = operation()
    steps.append(dict(capture(model, label), work=work))
traces.append({'name': 'public-RC-view-chunk-K1',
               'boundary': 'Actual public RC pre/post service placement is modeled. '
                           'Text/view construction is abstract setup during an empty queue; '
                           'allocation failure/cost and compiler insertion are excluded.',
               'steps': steps})

report = {'scope': 'Predictions of finite model; native fixtures not run.',
          'boundary': 'First two traces are ownership/scheduler kernel: enter/new/local/keep/step/leave omit '
                      'automatic public service. Exact replay requires preallocated protected '
                      'objects and private detachment plus explicit polls, or a separate '
                      'public-operation model with all service hooks. The third trace '
                      'explicitly uses public RC wrappers and includes their service hooks.',
          'generator': 'tests/peer-memory-model-evidence.py',
          'snapshot_note': 'Copied snapshots. Earlier transient generator aliased recent list; '
                           'independent review caught the artifact error and a permanent test now rejects it.',
          'traces': traces}
(base / 'literature-accounting-traces.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'status': 'passed', 'traces': len(traces), 'source_hashes': len(paths)}))
