import { tour } from './tour.mjs';

// Progress means an observed output matched a goal, not a proof of learning.
export const guides = Object.freeze({
  hello: {
    idea: 'Text is a value. Put another value inside it with \\(name).',
    instruction: 'Change the name from Ada to Grace, then run the program.',
    hint: 'Keep the quotation marks around the name. The sentence reads the value from name.',
    expected: 'Hello, Grace.\nMake yourself at home.\n',
  },
  functions: {
    idea: 'A function names a calculation. Integer describes the value it accepts and returns.',
    instruction: 'Keep double unchanged. Make the answer 84 by changing its argument.',
    hint: 'double multiplies its argument by two. Which argument would produce 84?',
    expected: 'A small thought: 84.\n',
  },
  lists: {
    idea: 'A List holds values of one type. A for loop visits each value in order.',
    instruction: 'Add a green lantern after blue. Let the program count the four lights.',
    hint: 'Add another quoted Text value to colours, separated by a comma.',
    expected: 'One amber lantern.\nOne silver lantern.\nOne blue lantern.\nOne green lantern.\n4 lights, one harbour.\n',
  },
  records: {
    idea: 'A record gives related values a checked shape. Every field is required.',
    instruction: 'Give the harbour one more light. Make the sentence report 43 lights.',
    hint: 'Change the lights field in the Lantern value; keep its Integer type.',
    expected: 'The harbour keeps 43 lights.\n',
  },
  choices: {
    idea: 'A choice names the possibilities. A match must handle every one.',
    instruction: 'Change the weather to Clear, without removing either match arm.',
    hint: 'Clear has no payload. Construct it as Weather.Clear.',
    expected: 'Room for stars.\n',
  },
  lanterns: {
    idea: 'Small ideas compose: a List of records, a function, a loop and a running total.',
    instruction: 'Give The harbour five lights. Keep the other two places unchanged and report eight lights altogether.',
    hint: 'Change the first Lantern value from light: 3 to light: 5. The loop computes the total.',
    expected: 'The harbour: 5 small promises.\nThe hill: 2 small promises.\nHome: one small promise.\n8 lights. Someone will come home.\n',
  },
});

const examples = new Map(tour.map(example => [example.id, example]));
const validIds = new Set(examples.keys());
const empty = () => ({ version: 1, visited: [], examples: [], challenges: [] });
const selected = values => Array.isArray(values)
  ? [...new Set(values.filter(value => typeof value === 'string' && validIds.has(value)))] : [];

export function restoreTourProgress(serialized) {
  if (typeof serialized !== 'string' || serialized.length > 4096) return empty();
  try {
    const parsed = JSON.parse(serialized);
    if (!parsed || parsed.version !== 1) return empty();
    return { version: 1, visited: selected(parsed.visited), examples: selected(parsed.examples), challenges: selected(parsed.challenges) };
  } catch { return empty(); }
}

export function visitTourStep(progress, id) {
  const state = restoreTourProgress(JSON.stringify(progress));
  if (validIds.has(id) && !state.visited.includes(id)) state.visited.push(id);
  return state;
}

export function assessTourRun(id, mode, result) {
  const example = examples.get(id);
  if (!example || (mode !== 'example' && mode !== 'challenge')) return false;
  const expected = mode === 'challenge' ? guides[id]?.expected : example.expected;
  return typeof expected === 'string' && result?.exitCode === 0
    && Array.isArray(result.diagnostics) && result.diagnostics.length === 0
    && result.output === expected;
}

export function recordTourRun(progress, id, mode, result) {
  const state = visitTourStep(progress, id);
  if (!assessTourRun(id, mode, result)) return state;
  const column = mode === 'challenge' ? 'challenges' : 'examples';
  if (!state[column].includes(id)) state[column].push(id);
  return state;
}

export function summarizeTourProgress(progress) {
  const state = restoreTourProgress(JSON.stringify(progress));
  return { visited: state.visited.length, examples: state.examples.length, challenges: state.challenges.length, total: tour.length };
}
