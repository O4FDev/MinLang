#!/usr/bin/env python3
"""GREEN self-tests: prove acceptance gates accept controls and reject cheats.

The reference event/idle implementation below exists ONLY in temporary test
snapshots. It is not a production fix or performance evidence.
"""
import copy
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_acceptance import Case, HERE, ROOT, cases, check_result, instrument
from test_acceptance_evidence import checked_artifact, compare, load_external, measurements, validate_phases
from event_study import oracle


CONTROL_STATE = '''
#include <assert.h>
static size_t control_depth, control_remaining[16];
'''
CONTROL_CLAMP = '''
    for (size_t i = 0; i < control_depth; i++)
        if (budget > control_remaining[i]) budget = control_remaining[i];
'''
CONTROL_CHARGE = '''
    for (size_t i = 0; i < control_depth; i++) {
        assert(control_remaining[i] >= work);
        control_remaining[i] -= work;
    }
'''
CONTROL_ADAPTER = '''
#define ACCEPTANCE_HAS_EVENT_SCOPE 1
#define ACCEPTANCE_HAS_IDLE 1
static void acceptance_event_begin(size_t budget) {
    assert(control_depth < 16);
    control_remaining[control_depth++] = budget;
}
static void acceptance_event_end(void) { assert(control_depth); control_depth--; }
static size_t acceptance_idle(size_t budget, int (*ready)(void *), void *context) {
    size_t work = 0;
    if (control_depth) return 0;
    while (work < budget && rc_pending_count && !ready(context)) {
        size_t step = minyar_rc_poll(budget - work);
        assert(step); work += step;
    }
    return work;
}
'''


class PolicyMutationTests(unittest.TestCase):
    def evidence(self, **values):
        return dict(work=0, visits=0, extra=0, pending=0, event_scope=1, idle=1, final_bytes=0, **values)

    def test_no_duplicate_scenarios(self):
        labels = [c.label for c in cases()]
        self.assertEqual(len(labels), len(set(labels)))

    def test_event_overrun_and_counter_lie(self):
        valid = self.evidence(); valid.update(work=7, visits=7)
        case = Case('operation', 'poll', 7)
        check_result(case, valid, 32)
        for delta in ({'work': 8, 'visits': 8}, {'work': 0}, {'final_bytes': 1}):
            with self.subTest(delta=delta), self.assertRaises(AssertionError):
                check_result(case, dict(valid, **delta), 32)

    def test_disabled_cleanup_cannot_pass_scope_progress(self):
        for kind in ('nested', 'reset', 'outside'):
            with self.subTest(kind=kind), self.assertRaises(AssertionError):
                check_result(Case('scope', kind, 7), self.evidence(), 32)

    def test_nested_budget_reset_and_scope_leak(self):
        valid = self.evidence(); valid.update(work=7, visits=7, extra=7)
        check_result(Case('scope', 'reset', 7), valid, 32)
        for extra in (0, 6, 8, 32):
            with self.subTest(extra=extra), self.assertRaises(AssertionError):
                check_result(Case('scope', 'reset', 7), dict(valid, extra=extra), 32)
        with self.assertRaises(AssertionError):
            check_result(Case('scope', 'outside', 7), dict(valid, extra=0), 32)

    def test_idle_ignoring_readiness_is_rejected(self):
        for case in (Case('idle', 'interrupt', 32, 0), Case('idle', 'inside', 32, 5),
                     Case('idle', 'empty', 32, 5), Case('idle', 'interrupt', 0, 5)):
            with self.subTest(case=case), self.assertRaises(AssertionError):
                check_result(case, dict(self.evidence(), work=1, visits=1, extra=1), 32)

    def test_idle_requires_real_progress_and_callback(self):
        case = Case('idle', 'interrupt', 97, 1)
        for changes in ({}, {'work': 33, 'visits': 33, 'extra': 1},
                        {'work': 1, 'visits': 1, 'extra': 0}, {'idle': 0}):
            with self.subTest(changes=changes), self.assertRaises(AssertionError):
                check_result(case, dict(self.evidence(), **changes), 32)

    def test_sustained_recovery_cannot_hide_work_in_teardown(self):
        case = Case('sustained', 'recovery', 7, 4)
        valid = dict(self.evidence(), work=128 * 4 * 8, extra=4 * (16 + 9 * 7))
        check_result(case, valid, 32)
        for delta in ({'visits': 1}, {'work': valid['work'] - 1}, {'extra': valid['extra'] + 1}):
            with self.subTest(delta=delta), self.assertRaises(AssertionError):
                check_result(case, dict(valid, **delta), 32)

    def test_bad_schema_is_not_a_pass(self):
        for key in self.evidence():
            for value in (-1, None, True, '0'):
                with self.subTest(key=key, value=value), self.assertRaises(AssertionError):
                    check_result(Case('capability', 'idle'), dict(self.evidence(), **{key: value}), 32)
        partial = self.evidence(); partial.pop('work')
        with self.assertRaises(AssertionError): check_result(Case('capability', 'idle'), partial, 32)
        for value in (None, [], 'passed'):
            with self.subTest(value=value), self.assertRaises(AssertionError):
                check_result(Case('capability', 'idle'), value, 32)

    def test_observer_refuses_changed_runtime(self):
        with self.assertRaises(ValueError): instrument('size_t minyar_rc_poll(size_t x) { return 0; }')

    def test_zero_baseline_does_not_divide_or_hide_retention(self):
        self.assertTrue(compare({'bytes': 0}, {'bytes': 0})[0]['passed'])
        self.assertFalse(compare({'bytes': 1}, {'bytes': 0})[0]['passed'])

    def test_no_tradeoff_metric_can_compensate_for_another(self):
        result = compare({'latency': 1, 'memory': 101}, {'latency': 100, 'memory': 100})
        self.assertEqual([r['passed'] for r in result], [True, False])
        with self.assertRaises(AssertionError): compare({'latency': 1}, {'memory': 1})
        with self.assertRaises(AssertionError): compare({}, {})

    def test_nonfinite_comparisons_do_not_pass(self):
        for value in (float('inf'), float('nan'), -1, True):
            with self.subTest(value=value), self.assertRaises(AssertionError):
                compare({'latency': value}, {'latency': value})

    def test_changed_artifacts_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); artifact = base / 'trace'
            artifact.write_bytes(b'original')
            record = {'path': 'trace', 'sha256': hashlib.sha256(b'original').hexdigest()}
            self.assertEqual(checked_artifact(base, record), artifact.resolve())
            artifact.write_bytes(b'edited')
            with self.assertRaises(ValueError): checked_artifact(base, record)

    def test_resource_claim_cannot_undercount_observed_memory(self):
        rows = [{'managed_bytes': 100, 'live_bytes': 80, 'owner_bytes': 32}]
        resources = dict(scope='setup-through-teardown', peak_rss_bytes=4096,
                         peak_managed_bytes=120, peak_owner_bytes=32, allocation_count=3, allocated_bytes=200)
        self.assertEqual(measurements({'resources': resources}, rows, [], True)['dead_managed_peak'], 20)
        for key, value in [('scope', 'events-only'), ('peak_rss_bytes', 0),
                           ('peak_managed_bytes', 99), ('peak_owner_bytes', 31), ('allocation_count', -1)]:
            with self.subTest(key=key, value=value), self.assertRaises(AssertionError):
                measurements({'resources': dict(resources, **{key: value})}, rows, [], True)

    def test_phase_ledger_accounts_for_idle_and_teardown(self):
        phases, summary, rows, recovery = self.phases()
        self.assertEqual(validate_phases(phases, summary, rows, recovery), 15)

    @staticmethod
    def phases():
        phases = [dict(kind='setup', start_ns=-2, end_ns=0),
                  dict(kind='event', event=0, start_ns=0, end_ns=3),
                  dict(kind='idle', start_ns=3, end_ns=7),
                  dict(kind='wait', start_ns=7, end_ns=10),
                  dict(kind='recovery', cycle=0, start_ns=10, end_ns=11),
                  dict(kind='teardown', start_ns=11, end_ns=16)]
        return phases, {'lifecycle_ns': 16}, [{'event': 0, 'start_ns': 0, 'service_ns': 3}], [
            {'cycle': 0, 'start_ns': 10, 'duration_ns': 1}]

    def test_phase_gaps_overlaps_truncation_and_missing_events_fail(self):
        for index, field, value in [(2, 'start_ns', 4), (2, 'start_ns', 2),
                (5, 'end_ns', 15), (0, 'kind', 'wait'), (1, 'event', 1),
                (4, 'cycle', 1), (2, 'kind', 'unknown'), (2, 'end_ns', 2)]:
            args = copy.deepcopy(self.phases()); args[0][index][field] = value
            with self.subTest(index=index, field=field, value=value), self.assertRaises(AssertionError):
                validate_phases(*args)
        for index in range(6):
            args = copy.deepcopy(self.phases()); args[0].pop(index)
            with self.subTest(removed=index), self.assertRaises(AssertionError): validate_phases(*args)


class ExternalEvidenceMutationTests(unittest.TestCase):
    def test_external_admission_replays_outputs_and_rejects_corruptions(self):
        # Synthetic timestamps/artifacts test the validator, not language speed.
        with tempfile.TemporaryDirectory(prefix='minyar-external-evidence-control-') as directory:
            base = Path(directory)
            count, width, seed, spacing = 2048, 4, 7, 10000
            expected = oracle(count, width, seed); rows = []
            for i in range(count):
                cycle, j = divmod(i, count // 4)
                arrival = cycle * ((count // 4) * spacing + 10000000) + j * spacing
                rows.append(dict(event=i, cycle=cycle, kind='rebuild' if i % 256 == 0 else 'ordinary',
                    result=expected[i], arrival_ns=arrival, start_ns=arrival + 10,
                    service_ns=100, response_ns=110, pending=0,
                    managed_bytes=-1, live_bytes=-1, owner_bytes=-1))
            recovery = [dict(cycle=i, pending_before=0, pending_after=0, polls=0,
                start_ns=(i + 1) * (count // 4) * spacing + i * 10000000,
                duration_ns=0, overrun_ns=0, managed_bytes=-1, live_bytes=-1, owner_bytes=-1)
                for i in range(4)]
            summary = dict(events=count, width=width, seed=seed, spacing_ns=spacing, burst=1,
                total_service_ns=count * 100, lifecycle_ns=count * spacing + 40000000 + 100,
                pending_before_teardown=0, final_bytes=-1, stack_admissions=-1)

            def artifact(name, data):
                (base / name).write_bytes(data)
                return {'path': name, 'sha256': hashlib.sha256(data).hexdigest()}

            def trace(name, values):
                with (base / name).open('w') as output:
                    writer = csv.DictWriter(output, fieldnames=list(values[0])); writer.writeheader(); writer.writerows(values)
                return {'path': name, 'sha256': hashlib.sha256((base / name).read_bytes()).hexdigest()}

            run = dict(implementation='rust', mode='timing', toolchain='synthetic test fixture',
                build_command=['fixture-compiler'], run_command=['fixture-binary'],
                binary=artifact('binary', b'not performance evidence'),
                sources=[artifact('source', b'validator positive control')], summary=summary,
                events=trace('events.csv', rows), recovery=trace('recovery.csv', recovery))
            data = dict(schema=1, workload='event_workload_v1', host='fixture', hardware='fixture',
                        allocator='system', lto=False, runs=[run])
            native = {'host': 'fixture', 'hardware': 'fixture'}
            path = base / 'external.json'

            def admit(value):
                path.write_text(json.dumps(value))
                return load_external(path, native)

            self.assertEqual(len(admit(data)), 1)
            for field, value in [('schema', 2), ('workload', 'different'), ('host', 'other'),
                                 ('hardware', 'other'), ('allocator', 'arena'), ('lto', True)]:
                with self.subTest(field=field), self.assertRaises(ValueError): admit(dict(data, **{field: value}))
            for field, value in [('mode', 'sanitized-timing'), ('sources', []), ('build_command', 'shell string')]:
                bad = copy.deepcopy(data); bad['runs'][0][field] = value
                with self.subTest(field=field), self.assertRaises(ValueError): admit(bad)
            duplicate = copy.deepcopy(data); duplicate['runs'].append(copy.deepcopy(run))
            with self.assertRaises(ValueError): admit(duplicate)
            for field, value in [('result', -1), ('arrival_ns', 123), ('response_ns', 0)]:
                bad_rows = copy.deepcopy(rows); bad_rows[0][field] = value
                bad = copy.deepcopy(data); bad['runs'][0]['events'] = trace('changed.csv', bad_rows)
                with self.subTest(field=field), self.assertRaises(ValueError): admit(bad)
            bad = copy.deepcopy(data); bad['runs'][0]['events'] = trace('short.csv', rows[:-1])
            with self.assertRaises(ValueError): admit(bad)
            (base / 'binary').write_bytes(b'changed binary')
            with self.assertRaises(ValueError): admit(data)


class NativePositiveControls(unittest.TestCase):
    def test_reference_control_satisfies_every_deterministic_scenario(self):
        with tempfile.TemporaryDirectory(prefix='minyar-acceptance-control-') as directory:
            root = Path(directory); runtime = root / 'runtime'; runtime.mkdir()
            fixture = root / 'research/reclamation'; fixture.mkdir(parents=True)
            for source in (ROOT / 'runtime').glob('*.[ch]'): shutil.copy2(source, runtime / source.name)
            for name in ('acceptance_runtime.c', 'acceptance_adapter.h'): shutil.copy2(HERE / name, fixture / name)
            header = runtime / 'minyar_bounded_rc.h'
            source = instrument(header.read_text())
            source = source.replace('static size_t acceptance_queued_work;', CONTROL_STATE + '\nstatic size_t acceptance_queued_work;')
            source = source.replace('size_t minyar_rc_poll(size_t budget) {', 'size_t minyar_rc_poll(size_t budget) {' + CONTROL_CLAMP)
            source = source.replace('    acceptance_queued_work += work;', CONTROL_CHARGE + '\n    acceptance_queued_work += work;')
            adapter = fixture / 'control.h'

            def compile_binary(name, budget, runtime_source, adapter_source):
                header.write_text(runtime_source); adapter.write_text(adapter_source)
                binary = root / name
                compiled = subprocess.run(['clang', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                    '-DMINYAR_SYSTEM_HEAP=1', f'-DMINYAR_RC_POLL_BUDGET={budget}',
                    f'-DACCEPTANCE_ADAPTER="{adapter}"', str(fixture / 'acceptance_runtime.c'),
                    '-o', str(binary)], capture_output=True, text=True, timeout=90)
                self.assertEqual(compiled.returncode, 0, compiled.stderr)
                return binary

            for budget in (1, 8, 32):
                binary = compile_binary(f'control-k{budget}', budget, source, CONTROL_ADAPTER)
                for case in cases():
                    with self.subTest(budget=budget, case=case.label):
                        run = subprocess.run([str(binary), case.group, case.name, str(case.budget), str(case.extra)],
                                             capture_output=True, text=True, timeout=15)
                        self.assertEqual(run.returncode, 0, run.stderr)
                        check_result(case, json.loads(run.stdout), budget)
            mutants = [
                ('no-event-charge', source.replace('control_remaining[i] -= work;', '(void)work;'),
                 CONTROL_ADAPTER, Case('operation', 'poll', 7)),
                ('lying-work-counter', source.replace('acceptance_queued_work += work;', 'acceptance_queued_work += 0;'),
                 CONTROL_ADAPTER, Case('operation', 'poll', 7)),
                ('ignores-readiness', source, CONTROL_ADAPTER.replace('!ready(context)', '((void)ready, (void)context, 1)'),
                 Case('idle', 'interrupt', 32, 0)),
                ('leaks-event-scope', source, CONTROL_ADAPTER.replace('control_depth--;', '(void)control_depth;'),
                 Case('scope', 'outside', 7)),
                ('stalled-idle', source, CONTROL_ADAPTER.replace('size_t work = 0;', 'size_t work = 0; budget = 0;'),
                 Case('idle', 'interrupt', 32, 5)),
            ]
            for name, runtime_source, adapter_source, case in mutants:
                with self.subTest(mutant=name):
                    binary = compile_binary(name, 32, runtime_source, adapter_source)
                    run = subprocess.run([str(binary), case.group, case.name, str(case.budget), str(case.extra)],
                                         capture_output=True, text=True, timeout=15)
                    if run.returncode == 0:
                        with self.assertRaises(AssertionError, msg=f'mutant survived: {name}'):
                            check_result(case, json.loads(run.stdout), 32)


if __name__ == '__main__':
    unittest.main(verbosity=2)
