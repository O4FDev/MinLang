#!/usr/bin/env python3
"""Plot every retained aggregate CPU pair with its preregistered interval."""
import hashlib
import json
from pathlib import Path
import random
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'evidence/runtime-aggregate-timing/run-rrkuiyad/results.json'
data = json.loads(SOURCE.read_text())
assert data['status'] == 'passed'
rows = data['measurements']
labels = {'known': 'Known ASCII, 4,096 bytes', 'short': 'Known ASCII, 15 bytes',
          'unknown': 'Unknown ASCII, 4,096 bytes', 'unicode': 'Unicode, 4,096 UTF-8 bytes',
          'no-query': 'No character query, 4,096 bytes'}
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                     'svg.fonttype': 'none', 'pdf.fonttype': 42})
figure, axes = plt.subplots(1, 2, figsize=(11.5, 4), sharey=True,
                            gridspec_kw={'width_ratios': [1, 1.3]})
generator = random.Random(681492)
for index, row in enumerate(rows):
    summary = row['cpu_ns_before_over_candidate']
    color = '#2369a1' if summary['geometric_mean'] >= 1 else '#bb4d30'
    y = [index + generator.uniform(-.065, .065) for _ in summary['individual_ratios']]
    for axis in axes:
        axis.scatter(summary['individual_ratios'], y, color=color, alpha=.35, s=17)
        center = summary['geometric_mean']
        axis.errorbar(center, index, xerr=[[center - summary['lower']], [summary['upper'] - center]],
                      fmt='o', color=color, capsize=4, markersize=5)
        axis.axvline(1, color='#666666', linestyle='--', linewidth=.8)
        axis.grid(axis='x', alpha=.16)
        axis.set_xlabel('Baseline / candidate process CPU ratio')
        axis.set_ylim(4.5, -.5)
axes[0].set_xlim(.95, 2.65)
axes[1].set_xlim(.96, 1.115)
axes[0].set_yticks(range(len(rows)), [labels[row['mode']] for row in rows])
axes[0].set_title('All five modes')
axes[1].set_title('Controls enlarged; known-large outside view')
figure.suptitle('Aggregate ASCII certificate experiment: all 12 pairs per mode')
figure.text(.5, .015,
            'Points: individual pairs. Bars: 95% paired-bootstrap intervals. Above 1 favors candidate.\n'
            'System/K32/O2; construction/cleanup/output included. Paced soak and shared host load; test-only candidate.',
            ha='center', fontsize=8)
figure.tight_layout(rect=(0, .115, 1, .93))
outputs = []
for suffix in ['svg', 'pdf', 'png']:
    path = HERE / ('runtime-aggregate-timing.' + suffix)
    figure.savefig(path, dpi=180)
    outputs.append({'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
provenance = {'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'input': str(SOURCE.relative_to(HERE)), 'input_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              'matplotlib_version': matplotlib.__version__, 'outputs': outputs,
              'scope': 'All 60 retained CPU pairs and preregistered geometric-mean intervals; no additional measurements.',
              'render_environment': 'Cached matplotlib environment with DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib; default Python pyexpat/libexpat version mismatch prevented its first render.'}
(HERE / 'runtime-aggregate-figure.json').write_text(json.dumps(provenance, indent=2) + '\n')
print(json.dumps(provenance, indent=2))
