#!/usr/bin/env python3
"""Export vector and raster figures from retained paired timing observations."""
import hashlib
import json
from pathlib import Path
import random

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
LIST = ROOT / 'build/memory-research-list-reserve-bench/run-9t0lgm8s/results.json'
ASCII = ROOT / 'build/memory-research-ascii-join-bench/run-603xbkqt/results.json'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                     'svg.fonttype': 'none', 'pdf.fonttype': 42})
provenance = {'generator': str(Path(__file__).relative_to(ROOT)),
              'matplotlib_version': matplotlib.__version__, 'inputs': [], 'outputs': []}


def read(path):
    provenance['inputs'].append({'path': str(path.relative_to(ROOT)),
                                 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    data = json.loads(path.read_text())
    assert data['status'] == 'passed'
    return data


def draw(axis, rows, colors, logarithmic=False, limits=None):
    generator = random.Random(20261004)
    for index, row in enumerate(rows):
        for series, (summary, color) in enumerate(zip(row['series'], colors)):
            center = index + (series - (len(row['series']) - 1) / 2) * .24
            interval = summary['confidence_interval']
            axis.scatter(summary['ratios'],
                         [center + generator.uniform(-.035, .035) for _ in summary['ratios']],
                         color=color, alpha=.23, s=15, zorder=2)
            axis.errorbar(summary['median'], center,
                          xerr=[[summary['median'] - interval['lower']],
                                [interval['upper'] - summary['median']]],
                          fmt='o', capsize=4, color=color, markersize=5, zorder=3)
    axis.axvline(1, color='#555555', linestyle='--', linewidth=1, zorder=1)
    axis.set_yticks(range(len(rows)), [row['label'] for row in rows])
    axis.invert_yaxis()
    axis.spines[['top', 'right', 'left']].set_visible(False)
    axis.tick_params(axis='y', length=0)
    axis.grid(axis='x', color='#dddddd', linewidth=.6)
    axis.set_xlabel('Baseline / candidate process CPU time')
    if logarithmic:
        axis.set_xscale('log')
    if limits:
        axis.set_xlim(*limits)


def save(figure, stem):
    for suffix in ('svg', 'pdf', 'png'):
        path = HERE / f'{stem}.{suffix}'
        figure.savefig(path, dpi=250, bbox_inches='tight', facecolor='white')
        provenance['outputs'].append({'path': str(path.relative_to(ROOT)),
                                      'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    plt.close(figure)


lists = read(LIST)
rows = []
for mode, length in [('append', 31), ('append', 1024), ('append', 8193), ('grow', 31)]:
    series = []
    for profile in ('system', 'fixed'):
        case = next(case for case in lists['measurements']
                    if (case['profile'], case['mode'], case['length']) == (profile, mode, length))
        series.append(case['cpu_before_over_after'])
    rows.append({'label': f'Append {length:,}' if mode == 'append' else 'Ordinary growth 31 (control)',
                 'series': series})
figure, axis = plt.subplots(figsize=(9, 4.7))
draw(axis, rows, ['#2474a2', '#bf6329'], limits=(.92, 2.48))
axis.set_title('Guarded List reservation: no-debt append batches', loc='left', fontweight='bold')
axis.legend([Line2D([0], [0], marker='o', color=color, linestyle='-')
             for color in ('#2474a2', '#bf6329')], ['System heap', 'Fixed pool'],
            loc='lower right', frameon=False)
figure.text(.02, -.03,
            '12 adjacent randomized pairs per case. Faint points: every pair; bars: 95% paired bootstrap interval.\n'
            'Ratios >1 favor reservation. Fixed ordinary growth is about 1.6% slower. No wall-clock latency bound.',
            fontsize=9)
save(figure, 'runtime-list-timing')

ascii_data = read(ASCII)
labels = {'known': 'Known long ASCII / length', 'unknown': 'Unknown long ASCII',
          'no-query': 'Known long ASCII / byte length', 'short': 'Known short ASCII / length',
          'unicode': 'Accented + non-BMP Unicode'}
rows = [{'label': labels[case['mode']], 'series': [case['cpu_before_over_candidate']]}
        for case in ascii_data['measurements']]
figure, axes = plt.subplots(1, 2, figsize=(12, 5), gridspec_kw={'width_ratios': [1.15, 1]})
draw(axes[0], rows, ['#2474a2'], limits=(.90, 2.48))
draw(axes[1], rows[1:], ['#2474a2'], limits=(.90, 1.08))
axes[0].set_title('ASCII metadata: generated workloads', loc='left', fontweight='bold')
axes[1].set_title('Controls: expanded scale', loc='left', fontweight='bold')
figure.tight_layout(w_pad=2)
figure.text(.01, -.04,
            '12 randomized blocks; adjacent baseline/candidate runs. Points: all observed CPU ratios; bars: 95% paired bootstrap interval.\n'
            'Byte-length-only control is about 0.9% slower. Counts establish avoided index work; these timings do not establish an OS latency bound.',
            fontsize=9)
save(figure, 'runtime-ascii-timing')
provenance['generator_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
(HERE / 'runtime-timing-figures.json').write_text(json.dumps(provenance, indent=2) + '\n')
print('Exported List and ASCII figures as SVG, PDF and PNG.')
