#!/usr/bin/env python3
"""Compare already measured artifacts; refuse peer/runtime/input mismatches."""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('control')
parser.add_argument('candidate')
parser.add_argument('--output')
args = parser.parse_args()
control, candidate = [json.loads(Path(p).read_text()) for p in [args.control,args.candidate]]
for key in ['canonical_input_sha256','runtime_tree','library_tree','source_scope_pass_sha256','profile_protocol']:
    if control['inputs'][key] != candidate['inputs'][key]:
        raise RuntimeError('cannot attribute gain: mismatched '+key)
if control['environment'] != candidate['environment']:
    raise RuntimeError('cannot attribute gain: changed measurement environment')
if set(control['profiles']) != set(candidate['profiles']):
    raise RuntimeError('missing measured workloads')
report = {'control':control['label'],'candidate':candidate['label'],'ratios':{}}
for name, before in control['profiles'].items():
    after = candidate['profiles'][name]
    if before.get('iterations') != after.get('iterations'):
        raise RuntimeError('different operation counts for '+name)
    if before.get('output_hashes') != after.get('output_hashes'):
        raise RuntimeError('codec output mismatch for '+name)
    b,a = before['median_instructions'],after['median_instructions']
    report['ratios'][name] = {'control_instructions':b,'candidate_instructions':a,
                             'candidate_over_control':a/b,'reduction_percent':100*(1-a/b)}
report['selfcompile_output_hashes'] = {'control':control['selfcompile_outputs'],
                                      'candidate':candidate['selfcompile_outputs']}
report['interpretation'] = 'Selfcompile IR may intentionally change; semantic qualification is separately required. Product full-child counters include setup and validation. No timing speedup follows automatically.'
text = json.dumps(report,indent=2)+'\n'
if args.output:
    Path(args.output).write_text(text)
print(text,end='')
