import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { supportingProjectFor } from '../playground/project-examples.mjs';
import { normalizeProject } from '../playground/project.mjs';

// Pure eligibility/project controls. They neither load a compiler nor execute
// Minyar. Future real execution has independent stdout 42\n: Point(20, 22) is
// passed to the visible companion function which adds exactly those two fields.
const SOURCE_HASH = '7934638fcc04b5e75f2eee0a7815c6dc089560f297e0db2862cd38bd0ed0c770';
const ORIGINAL_SOURCE = 'use "./geometry.min" as geometry\n\nlet point: geometry.Point = geometry.Point { x: 20, y: 22 }\nprint(geometry.answer(point))\n';
const GEOMETRY_SOURCE = 'public record Point { x: Integer; y: Integer }\npublic function answer(point: Point): Integer { return point.x + point.y }\n';
const catalog = JSON.parse(await readFile(new URL('../build/playground/language-examples.json', import.meta.url), 'utf8'));
const matches = catalog.examples.filter(example => example.sourceSha256 === SOURCE_HASH);
assert.equal(matches.length, 1, 'the exact reviewed guide block must still exist once in the catalog');
const example = matches[0];
const checks = [];

function check(name, operation) {
  operation();
  checks.push(name);
  console.log(`PASS project-examples/${name}`);
}

function frozenProject(value) {
  assert.equal(Object.isFrozen(value), true, 'the project record is immutable');
  assert.equal(Object.isFrozen(value.files), true, 'the source file array is immutable');
  for (const file of value.files) assert.equal(Object.isFrozen(file), true, `${file.path} is immutable`);
}

check('the exact catalog fragment gains one explicit visible companion without source changes', () => {
  assert.equal(example.file, 'docs/language.md');
  assert.equal(example.source, ORIGINAL_SOURCE);
  assert.equal(createHash('sha256').update(ORIGINAL_SOURCE).digest('hex'), SOURCE_HASH);
  assert.equal(example.classification, 'fragment');
  assert.equal(example.runnable, false, 'the original single-file catalog excerpt remains contextual');
  const before = JSON.stringify(example);
  const value = supportingProjectFor(example);
  assert.ok(value);
  assert.deepEqual(value, { version: 1, entry: 'main.min', files: [
    { path: 'geometry.min', source: GEOMETRY_SOURCE },
    { path: 'main.min', source: ORIGINAL_SOURCE },
  ] });
  assert.deepEqual(normalizeProject(value), value, 'the result already uses canonical project ordering');
  assert.equal(value.files.find(file => file.path === value.entry).source, example.source,
    'the guide source is neither rewritten nor prefixed/suffixed');
  assert.equal(JSON.stringify(example), before, 'eligibility does not change the catalog entry or its classification');
  assert.deepEqual(Object.keys(value).sort(), ['entry', 'files', 'version']);
  assert.equal(Object.hasOwn(value, 'scaffold'), false);
});

check('the companion visibly exports the ordinary record and addition function', () => {
  const value = supportingProjectFor(example);
  const companion = value.files.find(file => file.path === 'geometry.min');
  assert.equal(companion.source, GEOMETRY_SOURCE);
  assert.match(companion.source, /^public record Point \{ x: Integer; y: Integer \}\n/);
  assert.match(companion.source, /\npublic function answer\(point: Point\): Integer \{ return point\.x \+ point\.y \}\n$/);
  assert.doesNotMatch(companion.source, /\bnative\b|\bprint\s*\(|\buse\s/,
    'the companion is an ordinary explicit declaration file without hidden host work or output');
});

check('projects are copied and deeply frozen on every eligible request', () => {
  const immutableInput = Object.freeze({ ...example });
  const first = supportingProjectFor(immutableInput);
  const second = supportingProjectFor(immutableInput);
  frozenProject(first);
  frozenProject(second);
  assert.notStrictEqual(first, second);
  assert.notStrictEqual(first.files, second.files);
  for (let index = 0; index < first.files.length; index++) assert.notStrictEqual(first.files[index], second.files[index]);
  assert.throws(() => { first.entry = 'geometry.min'; }, TypeError);
  assert.throws(() => { first.files.push({ path: 'hidden.min', source: '' }); }, TypeError);
  assert.throws(() => { first.files[0].source = 'print("changed")\n'; }, TypeError);
  assert.equal(second.files.find(file => file.path === 'main.min').source, ORIGINAL_SOURCE);
});

check('own data properties allow frozen and null-prototype catalog records', () => {
  const minimal = { file: 'docs/language.md', sourceSha256: SOURCE_HASH, source: ORIGINAL_SOURCE };
  assert.ok(supportingProjectFor(Object.freeze(minimal)));
  assert.ok(supportingProjectFor(Object.assign(Object.create(null), minimal)));
});

check('wrong provenance and every altered source or hash fail closed', () => {
  const changed = ORIGINAL_SOURCE.replace('x: 20', 'x: 21');
  const cases = [
    { ...example, file: 'docs/other.md' },
    { ...example, file: './docs/language.md' },
    { ...example, file: '/docs/language.md' },
    { ...example, file: 'docs\\language.md' },
    { ...example, sourceSha256: SOURCE_HASH.slice(0, 12) },
    { ...example, sourceSha256: SOURCE_HASH.toUpperCase() },
    { ...example, sourceSha256: '0'.repeat(64) },
    { ...example, source: changed },
    { ...example, source: changed, sourceSha256: createHash('sha256').update(changed).digest('hex') },
    { ...example, source: ORIGINAL_SOURCE + '\n' },
    { ...example, source: ORIGINAL_SOURCE.trimEnd() },
    { ...example, source: ORIGINAL_SOURCE.replaceAll('\n', '\r\n') },
    { ...example, source: ORIGINAL_SOURCE.replace('x: 20, y: 22', 'x: 20; y: 22') },
    { ...example, source: ORIGINAL_SOURCE + 'print("an explicit edit")\n' },
  ];
  for (const candidate of cases) assert.equal(supportingProjectFor(candidate), null);
});

check('missing and non-string eligibility fields never coerce or throw', () => {
  for (const key of ['file', 'sourceSha256', 'source']) {
    const absent = { ...example };
    delete absent[key];
    assert.equal(supportingProjectFor(absent), null, `missing ${key}`);
    for (const value of [null, undefined, false, 0, [], new String(example[key]),
      { toString() { throw new Error('must not coerce an eligibility field'); } }]) {
      assert.equal(supportingProjectFor({ ...example, [key]: value }), null, `non-string ${key}`);
    }
  }
});

check('invalid record shapes and accessors do not execute user code', () => {
  const inherited = Object.create(example);
  const array = Object.assign([], example);
  const customPrototype = Object.assign(Object.create({ marker: true }), example);
  const revoked = Proxy.revocable({}, {});
  revoked.revoke();
  for (const candidate of [null, undefined, true, 42, 'example', () => example, [], array,
    new Date(0), new String(ORIGINAL_SOURCE), inherited, customPrototype, revoked.proxy]) {
    assert.equal(supportingProjectFor(candidate), null);
  }
  let accessed = 0;
  for (const key of ['file', 'sourceSha256', 'source']) {
    const candidate = { ...example };
    Object.defineProperty(candidate, key, { enumerable: true,
      get() { accessed++; throw new Error('must not read an eligibility getter'); } });
    assert.equal(supportingProjectFor(candidate), null);
    const hidden = { ...example };
    Object.defineProperty(hidden, key, { value: example[key], enumerable: false });
    assert.equal(supportingProjectFor(hidden), null);
  }
  assert.equal(accessed, 0);
});

check('other guide blocks never gain this companion project', () => {
  for (const candidate of catalog.examples) {
    if (candidate.sourceSha256 !== SOURCE_HASH) assert.equal(supportingProjectFor(candidate), null, candidate.id);
  }
});

console.log(`PASS ${checks.length} pure supporting-project controls; Minyar compilation/execution not performed`);
