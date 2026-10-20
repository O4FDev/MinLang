import assert from 'node:assert/strict';
import {
  ProjectError, MAX_PROJECT_FILES, MAX_PROJECT_BYTES, MAX_PROJECT_PATH_BYTES,
  normalizeProject, projectFromSource, projectCacheKey, projectSourceBytes,
} from '../playground/project.mjs';

let checks = 0;
function check(name, run) {
  run();
  checks++;
  console.log(`PASS project/${name}`);
}
function project(files, entry = files[0]?.path ?? 'main.min') { return { version: 1, entry, files }; }
function failure(code) {
  return error => error instanceof ProjectError && error.name === 'ProjectError'
    && error.code === code && error.message.length > 15;
}
function rejects(value, code) { assert.throws(() => normalizeProject(value), failure(code)); }

check('single-file compatibility and public limits', () => {
  assert.equal(MAX_PROJECT_FILES, 16);
  assert.equal(MAX_PROJECT_BYTES, 65536);
  assert.equal(MAX_PROJECT_PATH_BYTES, 256);
  assert.deepEqual(projectFromSource('print(42)\n'), {
    version: 1, entry: 'main.min', files: [{ path: 'main.min', source: 'print(42)\n' }],
  });
  assert.deepEqual(projectFromSource('', 'input.min'), {
    version: 1, entry: 'input.min', files: [{ path: 'input.min', source: '' }],
  });
  assert.equal(projectSourceBytes(projectFromSource('')), 0);
  assert.throws(() => projectFromSource('source', '../main.min'), failure('invalid_path'));
});

check('canonical paths use exact JavaScript string ordering', () => {
  const paths = ['\ue000.min', '🌙.min', 'ä.min', 'a.min', '𐀀.min', 'Z.min'];
  const result = normalizeProject(project(paths.map(path => ({ path, source: path })), 'a.min'));
  assert.deepEqual(result.files.map(file => file.path), ['Z.min', 'a.min', 'ä.min', '𐀀.min', '🌙.min', '\ue000.min']);
  assert.deepEqual(Object.keys(result), ['version', 'entry', 'files']);
  for (const file of result.files) assert.deepEqual(Object.keys(file), ['path', 'source']);
});

check('source preserves Unicode, BOM, NUL and line endings', () => {
  const texts = ['', 'ASCII\n', '星🌙 café e\u0301 🚀', '\ufeffprint("BOM")\r\n',
    '\0before\0after\0', 'a\r\nb\rc\n', '\ufffd', '\u0080\u07ff\u0800\uffff', '\ud800\udc00\udbff\udfff'];
  const files = texts.map((source, index) => ({ path: `source${index}.min`, source }));
  const result = normalizeProject(project(files));
  assert.deepEqual(result.files.map(file => file.source), texts);
  assert.equal(projectSourceBytes(result), texts.reduce((sum, text) => sum + Buffer.byteLength(text, 'utf8'), 0));
});

check('64 KiB boundary measures UTF-8, not string length', () => {
  for (const source of ['a'.repeat(65536), '🌙'.repeat(16384), '€'.repeat(21845) + 'a']) {
    assert.equal(Buffer.byteLength(source, 'utf8'), 65536);
    assert.equal(projectSourceBytes(projectFromSource(source)), 65536);
    assert.equal(projectFromSource(source).files[0].source, source);
    assert.throws(() => projectFromSource(source + 'a'), failure('too_large'));
  }
  assert.throws(() => projectFromSource('a'.repeat(65537)), failure('too_large'));
  assert.throws(() => projectFromSource('🌙'.repeat(16385)), failure('too_large'));
  const files = [{ path: 'main.min', source: 'é'.repeat(16384) }, { path: 'dep.min', source: 'x'.repeat(32768) }];
  assert.equal(projectSourceBytes(project(files)), 65536);
  rejects(project([...files, { path: 'empty.min', source: '' }, { path: 'extra.min', source: 'x' }]), 'too_large');
  assert.equal(normalizeProject(project([...files, { path: 'empty.min', source: '' }])).files.length, 3);
});

check('one through sixteen files and early array bounds', () => {
  const files = Array.from({ length: 16 }, (_, index) => ({ path: `file${index}.min`, source: '' }));
  assert.equal(normalizeProject(project(files)).files.length, 16);
  rejects(project([...files, { path: 'seventeen.min', source: '' }]), 'too_many_files');
  rejects(project([]), 'invalid_files');
  for (const value of [null, {}, 'main.min', new Set(files)]) rejects({ version: 1, entry: 'main.min', files: value }, 'invalid_files');
  const huge = [];
  huge.length = 1_000_000;
  Object.defineProperty(huge, '0', { get() { throw new Error('An oversized file array must reject before reading an item.'); } });
  rejects({ version: 1, entry: 'main.min', files: huge }, 'too_many_files');
});

check('path byte limits preserve valid Unicode and spaces', () => {
  for (const path of ['a'.repeat(252) + '.min', '🌙'.repeat(63) + '.min']) {
    assert.equal(Buffer.byteLength(path, 'utf8'), 256);
    assert.equal(projectFromSource('', path).entry, path);
  }
  for (const path of ['a'.repeat(253) + '.min', '🌙'.repeat(64) + '.min']) {
    assert.throws(() => projectFromSource('', path), failure('path_too_long'));
  }
  for (const path of [' src /nested folder / file.min', '星/🌙.min', 'café.min', 'cafe\u0301.min',
    '.min', ' src /question?and#percent%.min']) {
    const result = projectFromSource('source', path);
    assert.equal(result.entry, path);
    assert.equal(result.files[0].path, path);
  }
});

check('relative paths reject ambiguity and control characters', () => {
  const bad = ['', '.', '..', 'main', 'main.MIN', '/main.min', '//main.min', 'C:/main.min', 'C:main.min',
    'z:main.min', '\\server\\main.min', 'src\\main.min', 'src//main.min', './main.min', 'src/./main.min',
    '../main.min', 'src/../main.min', 'src/main.min/', 'src/\0main.min', '\tmain.min', 'main\n.min',
    'main\r.min', 'main\u007f.min', 'main\u0085.min', 'main\u009f.min', 'main\u2028.min', 'main\u2029.min',
    '\ud800.min', '\udfff.min'];
  for (const path of bad) assert.throws(() => projectFromSource('', path), failure('invalid_path'), JSON.stringify(path));
  for (const path of [null, 4, {}, new String('main.min')]) {
    assert.throws(() => projectFromSource('', path), failure('invalid_path'));
  }
});

check('duplicate and file-parent collisions reject in either order', () => {
  for (const files of [
    [{ path: 'a.min', source: 'a' }, { path: 'a.min', source: 'b' }],
    [{ path: 'a.min', source: 'a' }, { path: 'a.min', source: 'a' }],
  ]) rejects(project(files), 'duplicate_path');
  for (const paths of [['a.min', 'a.min/b.min'], ['src/a.min', 'src/a.min/deep/b.min'],
    ['a.min', 'a.min-other.min', 'a.min/b.min']]) {
    for (const order of [paths, [...paths].reverse()]) {
      rejects(project(order.map(path => ({ path, source: '' }))), 'path_collision');
    }
  }
  const paths = ['a.min', 'a.min-other.min', 'a.min-other/deep.min', 'café.min', 'cafe\u0301.min'];
  assert.equal(normalizeProject(project(paths.map(path => ({ path, source: '' })))).files.length, paths.length);
});

check('standard library root is reserved without prefix rewriting', () => {
  for (const path of ['library/text.min', 'library/nested/main.min']) {
    assert.throws(() => projectFromSource('', path), failure('reserved_path'));
    rejects(project([{ path: 'main.min', source: '' }, { path, source: '' }]), 'reserved_path');
  }
  for (const path of ['library.min', 'libraryish/main.min', 'Library/main.min', 'src/library/main.min']) {
    assert.equal(projectFromSource('', path).entry, path);
  }
});

check('entry must match an existing source file exactly', () => {
  const files = [{ path: 'src/main.min', source: '' }, { path: 'src/other.min', source: '' }];
  for (const entry of ['main.min', 'src/Main.min', 'src/absent.min']) rejects(project(files, entry), 'missing_entry');
  for (const entry of ['', '../src/main.min', 'src\\main.min']) rejects(project(files, entry), 'invalid_path');
  rejects(project(files, 'library/main.min'), 'reserved_path');
  assert.equal(normalizeProject(project(files, 'src/other.min')).entry, 'src/other.min');
});

check('source values must be strict Unicode text', () => {
  for (const source of [undefined, null, 42, true, {}, [], new String('source'), new Uint8Array([97]),
    '\ud800', '\udfff', 'a\ud800b', '\ud800\ud800', '\udc00\ud800']) {
    rejects(project([{ path: 'main.min', source }]), 'invalid_source');
  }
  assert.equal(projectFromSource('\ufffd').files[0].source, '\ufffd');
});

check('malformed shapes and versions reject extra metadata', () => {
  const valid = projectFromSource('source');
  for (const value of [undefined, null, 4, 'source', [], new Date(), {}, { entry: 'main.min', files: [] },
    { ...valid, extra: 1 }, { ...valid, [Symbol('extra')]: true }, Object.create(valid)]) rejects(value, 'invalid_project');
  for (const version of [undefined, null, '1', 0, -1, 1.5, NaN, Infinity, 2 ** 53]) {
    rejects({ ...valid, version }, 'invalid_version');
  }
  for (const version of [2, 99]) rejects({ ...valid, version }, 'unsupported_version');
  for (const file of [null, [], {}, { path: 'main.min' }, { source: '' }, { path: 'main.min', source: '', extra: true },
    { path: 'main.min', source: '', [Symbol('extra')]: 1 }, Object.create({ path: 'main.min', source: '' })]) {
    rejects({ version: 1, entry: 'main.min', files: [file] }, 'invalid_file');
  }
  for (const files of [Array(1), Object.assign([{ path: 'main.min', source: '' }], { extra: true }),
    Object.assign([{ path: 'main.min', source: '' }], { [Symbol('extra')]: true })]) {
    rejects({ version: 1, entry: 'main.min', files }, 'invalid_files');
  }
});

check('accessors and prototype metadata are never consumed', () => {
  const trap = () => { throw new Error('Project validation must not invoke input accessors.'); };
  const root = { version: 1, files: [{ path: 'main.min', source: '' }] };
  Object.defineProperty(root, 'entry', { enumerable: true, get: trap });
  rejects(root, 'invalid_project');
  const file = { path: 'main.min' };
  Object.defineProperty(file, 'source', { enumerable: true, get: trap });
  rejects({ version: 1, entry: 'main.min', files: [file] }, 'invalid_file');
  const files = [null];
  Object.defineProperty(files, '0', { enumerable: true, get: trap });
  rejects({ version: 1, entry: 'main.min', files }, 'invalid_files');
  const hidden = { version: 1, files: [{ path: 'main.min', source: '' }] };
  Object.defineProperty(hidden, 'entry', { value: 'main.min' });
  rejects(hidden, 'invalid_project');
  const names = ['__proto__.min', 'constructor.min', 'toString.min', 'hasOwnProperty.min'];
  const clean = normalizeProject(Object.assign(Object.create(null), {
    version: 1, entry: 'toString.min', files: names.map(path => Object.assign(Object.create(null), { path, source: path })),
  }));
  assert.equal(clean.files.length, 4);
  assert.equal(clean.entry, 'toString.min');
  assert.deepEqual(clean.files.map(value => value.path), [...names].sort());
  rejects(JSON.parse('{"version":1,"entry":"main.min","files":[{"path":"main.min","source":""}],"__proto__":{}}'), 'invalid_project');
});

check('canonical result is deeply frozen and copied', () => {
  const input = project([{ path: 'z.min', source: 'z' }, { path: 'a.min', source: 'a' }], 'a.min');
  const before = JSON.stringify(input);
  const result = normalizeProject(input);
  assert.equal(JSON.stringify(input), before, 'normalization must not sort or mutate caller input');
  assert.notEqual(result, input);
  assert.notEqual(result.files, input.files);
  assert.notEqual(result.files[0], input.files[1]);
  assert(Object.isFrozen(result));
  assert(Object.isFrozen(result.files));
  assert(result.files.every(Object.isFrozen));
  const key = projectCacheKey(result);
  input.entry = 'z.min';
  input.files[0].source = 'changed';
  input.files[1].path = 'renamed.min';
  input.files.push({ path: 'extra.min', source: '' });
  assert.equal(projectCacheKey(result), key);
  assert.throws(() => { result.entry = 'z.min'; }, TypeError);
  assert.throws(() => { result.files[0].source = 'changed'; }, TypeError);
  assert.throws(() => { result.files.push({ path: 'extra.min', source: '' }); }, TypeError);
  assert.deepEqual(normalizeProject(result), result);
  assert.notEqual(normalizeProject(result), result);
});

check('cache key includes entry, every path and every dependency source', () => {
  const base = project([{ path: 'main.min', source: 'main' }, { path: 'dep.min', source: 'dependency' }], 'main.min');
  const key = projectCacheKey(base);
  assert.equal(key, '{"version":1,"entry":"main.min","files":[{"path":"dep.min","source":"dependency"},{"path":"main.min","source":"main"}]}');
  assert.equal(projectCacheKey(project([...base.files].reverse(), 'main.min')), key);
  assert.equal(projectCacheKey({ files: base.files, entry: 'main.min', version: 1 }), key);
  assert.notEqual(projectCacheKey({ ...base, entry: 'dep.min' }), key);
  for (const files of [
    [{ path: 'main.min', source: 'MAIN' }, base.files[1]],
    [base.files[0], { path: 'dep.min', source: 'DEPENDENCY' }],
    [base.files[0], { path: 'other.min', source: 'dependency' }],
    [...base.files, { path: 'empty.min', source: '' }],
    [base.files[0]],
  ]) assert.notEqual(projectCacheKey(project(files, 'main.min')), key);
  assert.notEqual(projectCacheKey(projectFromSource('a\r\n')), projectCacheKey(projectFromSource('a\n')));
  assert.notEqual(projectCacheKey(projectFromSource('\ufeffa')), projectCacheKey(projectFromSource('a')));
  assert.notEqual(projectCacheKey(projectFromSource('a\0')), projectCacheKey(projectFromSource('a')));
});

check('oversized strings reject before encoding or scanning their contents', () => {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, 'TextEncoder');
  const original = String.prototype.charCodeAt;
  const giantSource = 'x'.repeat(65537);
  const giantPath = 'p'.repeat(257);
  Object.defineProperty(globalThis, 'TextEncoder', { configurable: true, value: class {
    constructor() { throw new Error('Project validation must not allocate an encoder.'); }
  } });
  String.prototype.charCodeAt = function (...args) {
    if (String(this) === giantSource || String(this) === giantPath) {
      throw new Error('Oversized UTF-16 strings must reject before a character scan.');
    }
    return original.apply(this, args);
  };
  try {
    assert.throws(() => projectFromSource(giantSource), failure('too_large'));
    assert.throws(() => projectFromSource('', giantPath), failure('path_too_long'));
    assert.equal(projectSourceBytes(projectFromSource('🌙')), 4);
  } finally {
    String.prototype.charCodeAt = original;
    if (descriptor) Object.defineProperty(globalThis, 'TextEncoder', descriptor);
    else delete globalThis.TextEncoder;
  }
});

console.log(`PASS ${checks} project model groups: strict UTF-8, path isolation, frozen copies and complete cache identity`);
