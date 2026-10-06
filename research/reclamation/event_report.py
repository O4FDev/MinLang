#!/usr/bin/env python3
"""Revalidate continuing-load evidence and report per-process ranges."""
import argparse
import json
import os
from pathlib import Path

from event_study import analyze, oracle, read_csv, sha


def load(directory):
    data = json.loads((directory / 'results.json').read_text())
    if data['status'] != 'passed' or len(data['runs']) != data['planned_runs']:
        raise ValueError(f'incomplete campaign: {directory}')
    for relative, digest in data['source_sha256'].items():
        if sha(directory / 'snapshot' / relative) != digest:
            raise ValueError(f'source changed: {relative}')
    if sha(directory / 'snapshot/minyarc') != data['compiler_sha256']:
        raise ValueError('compiler changed')
    builds = {b['label']: b for b in data['builds']}
    heap_irs = {b['llvm_sha256'] for b in builds.values() if b['ownership'] == 'heap'}
    if len(heap_irs) != 1:
        raise ValueError('scheduler comparison changed generated code')
    for build in builds.values():
        if sha(Path(build['binary'])) != build['binary_sha256'] or sha(Path(build['llvm'])) != build['llvm_sha256']:
            raise ValueError('binary or LLVM changed')
        if sha(directory / build['label'] / 'runtime/minyar_bounded_rc.h') != build['scheduler_sha256']:
            raise ValueError('transformed scheduler changed')
    for run in data['runs']:
        paths = [directory / (run['label'] + suffix) for suffix in ['.events.csv', '.recovery.csv']]
        if sha(paths[0]) != run['events_sha256'] or sha(paths[1]) != run['recovery_sha256']:
            raise ValueError('raw traces changed')
        s = run['summary']; build = builds[run['configuration']]
        metrics = analyze(s, read_csv(paths[0]), read_csv(paths[1]), oracle(s['events'], s['width'], s['seed']),
                          s['spacing_ns'], s['burst'], data['mode'] == 'diagnostic',
                          build['ownership'], s['width'], s['seed'])
        if metrics != run['metrics']:
            raise ValueError('saved metrics differ from recomputation')
    return data


def span(values, scale=1):
    values = [v / scale for v in values]
    return f'{min(values):.3f}–{max(values):.3f}'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['diagnostic', 'sanitize', 'timing', 'output']:
        p.add_argument('--' + name, type=Path, required=True)
    args = p.parse_args()
    manifests = {k: load(getattr(args, k).resolve()) for k in ['diagnostic', 'sanitize', 'timing']}
    diagnostic, sanitized, timing = [manifests[k] for k in ['diagnostic', 'sanitize', 'timing']]
    if diagnostic['mode'] != 'diagnostic' or diagnostic['sanitize'] or sanitized['mode'] != 'diagnostic' or not sanitized['sanitize']:
        raise ValueError('wrong diagnostic campaign types')
    if timing['mode'] != 'timing' or timing['sanitize']:
        raise ValueError('timing contains diagnostic instrumentation')
    # Notes and analysis code may evolve; the measured implementation must match.
    relevant = [s for s in timing['source_sha256'] if s.startswith('runtime/') or s in [
        'compiler/compiler.min', 'research/reclamation/event_driver.c', 'research/reclamation/event_workload.min',
        'research/reclamation/variants.py']]
    for data in [diagnostic, sanitized]:
        if data['compiler_sha256'] != timing['compiler_sha256'] or any(
                data['source_sha256'][s] != timing['source_sha256'][s] for s in relevant):
            raise ValueError('campaigns measured different implementations')
    key = lambda r: (r['configuration'], r['summary']['seed'])
    native_runs, sanitized_runs = [{key(r): r for r in m['runs']} for m in [diagnostic, sanitized]]
    if native_runs.keys() != sanitized_runs.keys():
        raise ValueError('native/sanitized matrix differs')
    for k in native_runs:
        if native_runs[k]['summary'] != sanitized_runs[k]['summary'] or native_runs[k]['metrics'] != sanitized_runs[k]['metrics']:
            raise ValueError('sanitized accounting differs')
        for metric in ['events_sha256', 'recovery_sha256']:
            if native_runs[k][metric] != sanitized_runs[k][metric]:
                raise ValueError('sanitized boundary traces differ')
    fair_pairs = 0
    for (config, seed), run in native_runs.items():
        if config.startswith('current-') and config.endswith('-heap'):
            fair = native_runs.get((config.replace('current-', 'fair-unit-'), seed))
            if fair is None: continue
            if any(run[x] != fair[x] for x in ['events_sha256', 'recovery_sha256']):
                raise ValueError('current/fair-unit boundary traces differ')
            fair_pairs += 1
    def selected(configuration, spacing=None, burst=None, data=timing):
        return [r for r in data['runs'] if r['configuration'] == configuration and
                (spacing is None or r['summary']['spacing_ns'] == spacing) and
                (burst is None or r['summary']['burst'] == burst)]
    configurations = [b['label'] for b in timing['builds']]
    arrivals = sorted({(r['summary']['spacing_ns'], r['summary']['burst']) for r in timing['runs']})
    sizes = lambda data: sorted({(r['summary']['events'], r['summary']['width']) for r in data['runs']})
    lines = ['# Compiled continuing-load measurements', '',
        'Generated by `event_report.py`; source/binary/LLVM/raw-trace hashes checked, event',
        'oracles and metrics recomputed. Ranges are minimum–maximum across per-process',
        'measurements; percentiles are never pooled across seeds.', '',
        f"Host: {timing['host']}; Clang `-O2`, system allocator, no LTO, integer-Text cache disabled.", '',
        'Hardware: ' + timing.get('hardware', 'not separately recorded').replace('\n', '; ') + '.', '',
        f"- Native diagnostic runs: {len(diagnostic['runs'])}; ASan/UBSan: {len(sanitized['runs'])}; exact summary/accounting agreement.",
        f"- Timing runs: {len(timing['runs'])}; all event results and trace checks passed.",
        f'- Exact current/fair-unit event/recovery trace pairs: {fair_pairs} per diagnostic mode.',
        f'- Diagnostic (events, width): {sizes(diagnostic)}; timing: {sizes(timing)}.',
        '- All scheduler variants use the same heap-only LLVM; stack variants use separately checked compiler output.',
        '- Diagnostic peaks are between-event requested bytes, excluding transient peaks, allocator metadata and RSS.', '',
        '## Scheduler comparison at K32', '',
        'Arrival spacing is the prescribed mean; a burst releases that many events at once.',
        'Rebuild max is the maximum service duration within each process (32 rebuilds in the default run).',
        'Service totals exclude waits and quiet-window cleanup; lifecycle includes those and final teardown.', '',
        '| Spacing, µs / burst | Policy | Ordinary service p99, µs | Ordinary response p99, µs | Rebuild service max, µs | Event service total, ms | Lifecycle, ms | Failed quiet windows |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for spacing, burst in arrivals:
        for config in ['current-k32-heap', 'fair-unit-k32-heap', 'fifo-k32-heap', 'lifo-k32-heap', 'eager-k0-heap']:
            runs = selected(config, spacing, burst)
            if not runs: continue
            m = [r['metrics'] for r in runs]
            lines.append(f'| {spacing / 1000:g} / {burst} | {config} | ' + ' | '.join([
                span([x['ordinary']['service_ns']['p99'] for x in m], 1000),
                span([x['ordinary']['response_ns']['p99'] for x in m], 1000),
                span([x['rebuild']['service_ns']['max'] for x in m], 1000),
                span([r['summary']['total_service_ns'] for r in runs], 1000000),
                span([r['summary']['lifecycle_ns'] for r in runs], 1000000),
                f"{sum(x['recovery_failed_cycles'] for x in m)}/{4 * len(m)}"]) + ' |')
    lines += ['', '## Budget and recovery comparison', '',
        'Heap-only current/FIFO comparisons keep every arrival pattern separate.',
        'Recovery duration measures polling during the fixed quiet window, excluding',
        'waiting for its end. A window fails if debt remains or processing overruns it.', '',
        '| Spacing, µs / burst | Configuration | Ordinary service p99, µs | Ordinary response p99, µs | Peak pending tasks | Longest recovery, µs | Failed quiet windows |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for spacing, burst in arrivals:
        for budget in [1, 8, 32]:
            for policy in ['current', 'fifo']:
                config = f'{policy}-k{budget}-heap'
                runs = selected(config, spacing, burst)
                if not runs: continue
                m = [r['metrics'] for r in runs]
                lines.append(f'| {spacing / 1000:g} / {burst} | {config} | ' + ' | '.join([
                    span([x['ordinary']['service_ns']['p99'] for x in m], 1000),
                    span([x['ordinary']['response_ns']['p99'] for x in m], 1000),
                    span([x['max_pending'] for x in m]), span([x['max_recovery_ns'] for x in m], 1000),
                    f"{sum(x['recovery_failed_cycles'] for x in m)}/{4 * len(m)}"]) + ' |')
    lines += ['', '## Stack-ownership policy ablation', '',
        'Each ratio is budget-stack divided by heap-only for the same K, seed and arrival',
        'schedule. Below 1 means lower. Different processes ran in randomized order;',
        'ratios do not remove host noise. Stack lowering also requires `noinline` on',
        'admitted functions, so this compares the actual compiler policies.', '',
        '| K | Spacing, µs / burst | Ordinary service p99 ratio | Ordinary response p99 ratio | Event service total ratio |',
        '| ---: | --- | ---: | ---: | ---: |']
    for budget in [8, 32]:
        for spacing, burst in arrivals:
            heaps = {r['summary']['seed']: r for r in selected(f'current-k{budget}-heap', spacing, burst)}
            stacks = selected(f'current-k{budget}-budget', spacing, burst)
            if not stacks: continue
            ratios = [[], [], []]
            for r in stacks:
                h = heaps[r['summary']['seed']]
                for i, metric in enumerate(['service_ns', 'response_ns']):
                    ratios[i].append(r['metrics']['ordinary'][metric]['p99'] / h['metrics']['ordinary'][metric]['p99'])
                ratios[2].append(r['summary']['total_service_ns'] / h['summary']['total_service_ns'])
            lines.append(f'| {budget} | {spacing / 1000:g} / {burst} | ' + ' | '.join(span(x) for x in ratios) + ' |')
    lines += ['', '## Diagnostic retention and ownership storage', '',
        'These smaller, unpaced runs use complete drains between cycles. Their memory',
        'figures cannot establish timed-window recovery or timing-size memory consumption.',
        'Each column reports its own maximum; separate maxima need not coincide.',
        'Owner storage here means retained heap frames/chunks/caches, excluding active stack storage.', '',
        '| Configuration | Dead managed peak, KiB | Heap owner peak, KiB | Managed + heap owner peak, KiB | Peak pending tasks | Actual stack entries |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for config in configurations:
        runs = selected(config, data=diagnostic)
        if not runs: continue
        m = [r['metrics'] for r in runs]
        lines.append(f'| {config} | ' + ' | '.join([
            span([x['max_boundary_dead_managed_bytes'] for x in m], 1024),
            span([x['max_boundary_owner_bytes'] for x in m], 1024),
            span([x['max_boundary_managed_plus_owner_bytes'] for x in m], 1024),
            span([x['max_pending'] for x in m]), span([r['summary']['stack_admissions'] for r in runs])]) + ' |')
    failed = sum(r['metrics']['recovery_failed_cycles'] for r in timing['runs'])
    entries = [n for r in timing['runs'] for n in r['metrics']['cycle_end_pending']]
    lines += ['', '## Recovery and limits', '',
        f"Across all timing configurations, {failed}/{len(timing['runs']) * 4} quiet windows ended with debt or overrun.",
        f'{sum(n > 0 for n in entries)}/{len(entries)} windows began with debt; the largest entry backlog was only {max(entries)} tasks.',
        'This workload therefore does not stress recovery from a large boundary backlog.',
        'This is finite recovery with 10 ms service windows, not a proof of stable backlog',
        'under unlimited arrivals. Rebuilds, allocation and frame initialization remain',
        'outside any claim that every event has constant total cost.', '',
        'Minimum positive empty-clock differences, ns: ' + span([r['summary']['clock_positive_min_ns'] for r in timing['runs']]) + '.', '',
        'Application-shaped synthetic workload; one host, three seeds, no CPU isolation,',
        'no rare-tail guarantee, no comparison with an external language/runtime.', '',
        '## Evidence', '']
    for name in manifests:
        path = getattr(args, name).resolve() / 'results.json'
        relative = os.path.relpath(path, args.output.resolve().parent)
        lines.append(f'- [{name} manifest]({relative}): SHA-256 `{sha(path)}`.')
    args.output.write_text('\n'.join(lines) + '\n')
    print(args.output)


if __name__ == '__main__':
    main()
