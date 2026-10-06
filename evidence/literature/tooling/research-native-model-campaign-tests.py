#!/usr/bin/env python3
"""Source instrumentation/tooling contracts, independent of native execution."""
import importlib.util
from pathlib import Path
import re
import unittest

path = Path(__file__).with_name('research-native-model-campaign.py')
spec = importlib.util.spec_from_file_location('native_campaign', path)
campaign = importlib.util.module_from_spec(spec)
spec.loader.exec_module(campaign)


class Instrumentation(unittest.TestCase):
    def test_exact_observation_points_and_no_input_mutation(self):
        sources = {name: (campaign.ROOT / 'runtime' / name).read_text()
                   for name in ('minyar_bounded_rc.h', 'minyar_rc.h')}
        saved = dict(sources)
        instrumented = campaign.instrument_sources(sources)
        self.assertEqual(sources, saved)
        self.assertEqual(instrumented['minyar_bounded_rc.h'].count('research_on_free(object + 1);'), 1)
        self.assertEqual(instrumented['minyar_rc.h'].count('research_on_free(object + 1);'), 2)
        for name, source in sources.items():
            self.assertEqual(re.sub(r'^ *research_on_free\(object \+ 1\);\n', '', instrumented[name], flags=re.MULTILINE), source)

    def test_changed_observation_anchors_fail_closed(self):
        with self.assertRaises(ValueError):
            campaign.instrument_sources({'minyar_bounded_rc.h': '', 'minyar_rc.h': ''})

    def test_complete_trace_covers_all_public_transitions(self):
        operations = campaign.oracle.generate(39752, 1000)
        self.assertEqual(set(campaign.oracle.OPCODES), {op[0] for op in operations})
        encoded = campaign.oracle.encode(operations)
        self.assertEqual(len(encoded.splitlines()), len(operations))


if __name__ == '__main__':
    unittest.main()
