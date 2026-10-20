import assert from 'node:assert/strict';
import { tour } from '../playground/tour.mjs';
import { guides, restoreTourProgress, visitTourStep, assessTourRun, recordTourRun, summarizeTourProgress } from '../playground/tour-guide.mjs';

const success = output => ({ output, exitCode: 0, diagnostics: [] });
let state = restoreTourProgress(null);
assert.deepEqual(summarizeTourProgress(state), { visited: 0, examples: 0, challenges: 0, total: tour.length });
for (const example of tour) {
  const guide = guides[example.id];
  assert.ok(guide && guide.idea && guide.instruction && guide.hint && guide.expected);
  assert.notEqual(guide.expected, example.expected, 'challenge must change the observed result');
  const previous = JSON.stringify(state);
  const seen = visitTourStep(state, example.id);
  assert.equal(JSON.stringify(state), previous, 'progress updates must not mutate stored state');
  assert.ok(seen.visited.includes(example.id));
  assert.equal(assessTourRun(example.id, 'example', success(example.expected)), true);
  assert.equal(assessTourRun(example.id, 'challenge', success(example.expected)), false);
  assert.equal(assessTourRun(example.id, 'example', { ...success(example.expected), exitCode: 1 }), false);
  assert.equal(assessTourRun(example.id, 'example', { ...success(example.expected), diagnostics: [{}] }), false);
  assert.equal(assessTourRun(example.id, 'example', { output: example.expected, exitCode: 0 }), false);
  assert.equal(assessTourRun(example.id, 'example', success(example.expected.trimEnd())), false);
  state = recordTourRun(state, example.id, 'example', success(example.expected));
  state = recordTourRun(state, example.id, 'challenge', success(guide.expected));
  state = recordTourRun(state, example.id, 'challenge', success(guide.expected));
}
assert.deepEqual(summarizeTourProgress(state), { visited: tour.length, examples: tour.length, challenges: tour.length, total: tour.length });
assert.deepEqual(restoreTourProgress(JSON.stringify(state)), state);
assert.equal(assessTourRun('unknown', 'example', success('')), false);
assert.equal(assessTourRun('hello', 'invalid', success(tour[0].expected)), false);
for (const serialized of ['{', 'null', '42', '[]', '{"version":2}', ' '.repeat(4097)]) {
  assert.deepEqual(restoreTourProgress(serialized), restoreTourProgress(null));
}
const malicious = restoreTourProgress('{"version":1,"visited":["hello","hello","__proto__",null,{}],"examples":42,"challenges":["unknown"]}');
assert.deepEqual(malicious, { version: 1, visited: ['hello'], examples: [], challenges: [] });
console.log(`Tour guide: ${tour.length} example goals, challenges, progress persistence and rejection controls passed`);
