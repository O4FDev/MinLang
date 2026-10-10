#!/usr/bin/env python3
"""Write the Atacama history response that tests/profile/stub-server.py serves.

    python3 benchmarks/json/history.py RUNS > history.json
"""
import json
import sys

WORDS = 'the atacama desert is a plateau in south america covering a strip of land on the pacific coast'.split()


def run(index):
    return {'id': f'run-{index}', 'mode': 'ask', 'created_at': '2026-10-09T12:00:00Z',
            'prompt': f'Question {index}: where is the {WORDS[index % len(WORDS)]} and why is it so dry?',
            'response': {'text': f'Answer {index}. ' + ' '.join(WORDS), 'sources': []}}


runs = int(sys.argv[1]) if len(sys.argv) > 1 else 500
sys.stdout.write(json.dumps({'runs': [run(i) for i in range(runs)], 'hasMore': False}))
