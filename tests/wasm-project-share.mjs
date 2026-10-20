import assert from 'node:assert/strict';
import { ProjectError, normalizeProject, projectFromSource, projectSourceBytes } from '../playground/project.mjs';
import { ProjectShareError, MAX_PACKED_PROJECT_BYTES, encodeProject, decodeProject } from '../playground/project-share.mjs';

let checks = 0;
function check(name, run) {
  run();
  checks++;
  console.log(`PASS project-share/${name}`);
}
function project(files, entry = files[0]?.path ?? 'main.min') { return { version: 1, entry, files }; }
function failure(code, cause) {
  return error => error instanceof ProjectShareError && error.name === 'ProjectShareError'
    && error.code === code && error.message.length > 15
    && (cause === undefined || error.cause instanceof cause);
}
function reject(bytes, code, cause) { assert.throws(() => decodeProject(bytes), failure(code, cause)); }
function raw(value) { return typeof value === 'string' ? Buffer.from(value, 'utf8') : Buffer.from(value); }
function u16(value) { const bytes = Buffer.alloc(2); bytes.writeUInt16LE(value); return bytes; }
function u32(value) { const bytes = Buffer.alloc(4); bytes.writeUInt32LE(value); return bytes; }

// Independent wire producer: it deliberately accepts malformed lengths, order,
// text bytes and metadata, without importing any production encoding helper.
function wire(entry, files, { version = 1, count = files.length, entryLength = raw(entry).length } = {}) {
  const chunks = [Buffer.from([version, count]), u16(entryLength), raw(entry)];
  for (const file of files) {
    const path = raw(file.path), source = raw(file.source);
    chunks.push(u16(file.pathLength ?? path.length), u32(file.sourceLength ?? source.length), path, source);
  }
  return Uint8Array.from(Buffer.concat(chunks));
}

check('literal schema fixture fixes byte order and field layout', () => {
  assert.equal(MAX_PACKED_PROJECT_BYTES, 71680);
  const fixture = Uint8Array.from(Buffer.from('010108006d61696e2e6d696e0800010000006d61696e2e6d696e78', 'hex'));
  assert.deepEqual(encodeProject(projectFromSource('x')), fixture);
  assert.deepEqual(decodeProject(fixture), projectFromSource('x'));
  const empty = Uint8Array.from(Buffer.from('01010500612e6d696e050000000000612e6d696e', 'hex'));
  assert.deepEqual(encodeProject(projectFromSource('', 'a.min')), empty);
  assert.deepEqual(decodeProject(empty), projectFromSource('', 'a.min'));
});

check('encoding is deterministic across file and metadata order', () => {
  const files = [{ path: 'z.min', source: 'last' }, { path: 'a.min', source: 'first' }];
  const first = encodeProject(project(files, 'z.min'));
  const expected = wire('z.min', [files[1], files[0]]);
  assert.deepEqual(first, expected);
  assert.deepEqual(encodeProject({ files: [...files].reverse(), entry: 'z.min', version: 1 }), first);
  assert.deepEqual(decodeProject(first), normalizeProject(project(files, 'z.min')));
  assert.notDeepEqual(encodeProject(project(files, 'a.min')), first);
  assert.notDeepEqual(encodeProject(project([files[0], { ...files[1], source: 'other' }], 'z.min')), first);
});

check('UTF-8 source and paths preserve BOM, Unicode, CRLF and NUL', () => {
  for (const source of ['', '星🌙 café e\u0301 🚀', '\ufeffprint("BOM")\r\n', '\0before\0after\0',
    'a\r\nb\rc\n', '\ufffd', '\ud800\udc00\udbff\udfff']) {
    const value = projectFromSource(source, '\ufeff星/ file 🌙.min');
    assert.deepEqual(decodeProject(encodeProject(value)), value);
    assert.deepEqual(decodeProject(wire(value.entry, value.files)), value);
    assert.equal(projectSourceBytes(decodeProject(encodeProject(value))), Buffer.byteLength(source, 'utf8'));
  }
});

check('input types and total packed cap reject before parsing', () => {
  for (const bytes of [undefined, null, '', [], {}, new ArrayBuffer(8), new DataView(new ArrayBuffer(8)), new Uint16Array(8)]) {
    reject(bytes, 'invalid_bytes');
  }
  reject(new Uint8Array(71681), 'too_large');
  const padded = new Uint8Array(71680);
  padded.set(encodeProject(projectFromSource('')));
  reject(padded, 'trailing_data');
  reject(new Uint8Array(), 'truncated');
});

check('bounded offset views and frozen output do not alias input', () => {
  const value = projectFromSource('private source');
  const packed = encodeProject(value);
  const backing = new Uint8Array(MAX_PACKED_PROJECT_BYTES * 2);
  backing.fill(0xa5);
  const view = new Uint8Array(backing.buffer, 4096, packed.length);
  view.set(packed);
  const before = Uint8Array.from(view);
  const result = decodeProject(view);
  assert.deepEqual(result, value);
  assert.deepEqual(view, before);
  assert.equal(backing[4095], 0xa5);
  assert.equal(backing[4096 + packed.length], 0xa5);
  assert(Object.isFrozen(result) && Object.isFrozen(result.files) && result.files.every(Object.isFrozen));
  view.fill(0);
  assert.equal(result.files[0].source, 'private source');
  assert.throws(() => { result.files[0].source = 'changed'; }, TypeError);
  assert.deepEqual(decodeProject(Buffer.from(packed)), value);
  const again = encodeProject(value);
  packed.fill(0);
  assert.deepEqual(decodeProject(again), value);
});

check('schema and file count are strict', () => {
  const files = [{ path: 'a.min', source: '' }];
  for (const version of [0, 2, 255]) reject(wire('a.min', files, { version }), 'unsupported_version');
  for (const count of [0, 17, 255]) reject(wire('a.min', files, { count }), 'invalid_count');
  const sixteen = Array.from({ length: 16 }, (_, index) => ({ path: `${String(index).padStart(2, '0')}.min`, source: '' }));
  assert.equal(decodeProject(wire(sixteen[0].path, sixteen)).files.length, 16);
  reject(wire('a.min', files, { count: 2 }), 'truncated');
});

check('every truncated prefix of a valid record rejects', () => {
  const bytes = wire('🌙.min', [{ path: '🌙.min', source: '\ufeffé\0\r\n🌙' }]);
  for (let length = 0; length < bytes.length; length++) reject(bytes.slice(0, length), 'truncated');
  assert.equal(decodeProject(bytes).files[0].source, '\ufeffé\0\r\n🌙');
  reject(wire('a.min', [{ path: 'a.min', source: 'x', sourceLength: 2 }]), 'truncated');
  reject(wire('a.min', [{ path: 'a.min', source: '', pathLength: 6 }]), 'truncated');
});

check('trailing bytes and uncounted records are rejected', () => {
  const valid = wire('a.min', [{ path: 'a.min', source: '' }]);
  for (const extra of [[0], [255], [0, 0, 0, 0]]) reject(Uint8Array.from([...valid, ...extra]), 'trailing_data');
  reject(wire('a.min', [{ path: 'a.min', source: '' }, { path: 'b.min', source: '' }], { count: 1 }), 'trailing_data');
  reject(wire('a.min', [{ path: 'a.min', source: 'x', sourceLength: 0 }]), 'trailing_data');
});

check('all declared bounds preflight before any slice or text decode', () => {
  const files = [{ path: 'a.min', source: '' }];
  const cases = [
    [new Uint8Array(71681), 'too_large'],
    [wire('a.min', files, { count: 17 }), 'invalid_count'],
    [wire('a.min', files, { entryLength: 257 }), 'path_too_long'],
    [wire('a.min', [{ path: 'a.min', source: '', pathLength: 257 }]), 'path_too_long'],
    [wire('a.min', [{ path: 'a.min', source: '', sourceLength: 65537 }]), 'too_large'],
    [wire('a.min', [{ path: 'a.min', source: '', sourceLength: 0xffffffff }]), 'too_large'],
    [wire('a.min', [{ path: 'a.min', source: 'x', sourceLength: 2 }]), 'truncated'],
    [wire('a.min', [{ path: 'a.min', source: 'a'.repeat(32768) }, { path: 'b.min', source: 'b'.repeat(32769) }]), 'too_large'],
  ];
  const originalDecode = TextDecoder.prototype.decode;
  const originalSubarray = Uint8Array.prototype.subarray;
  let decodes = 0, slices = 0;
  TextDecoder.prototype.decode = function () { decodes++; throw new Error('Invalid declared bounds must reject before decoding.'); };
  Uint8Array.prototype.subarray = function (...args) { slices++; return originalSubarray.apply(this, args); };
  try {
    for (const [bytes, code] of cases) reject(bytes, code);
    assert.equal(decodes, 0);
    assert.equal(slices, 0);
  } finally {
    TextDecoder.prototype.decode = originalDecode;
    Uint8Array.prototype.subarray = originalSubarray;
  }
});

check('fatal UTF-8 rejects bad bytes in entry, path and source', () => {
  for (const bad of [[255], [0x80], [0xc0, 0x80], [0xe2, 0x82], [0xed, 0xa0, 0x80], [0xf4, 0x90, 0x80, 0x80]]) {
    reject(wire(bad, [{ path: 'a.min', source: '' }]), 'invalid_utf8', TypeError);
    reject(wire('a.min', [{ path: bad, source: '' }]), 'invalid_utf8', TypeError);
    reject(wire('a.min', [{ path: 'a.min', source: bad }]), 'invalid_utf8', TypeError);
  }
  assert.equal(decodeProject(wire('a.min', [{ path: 'a.min', source: [0xef, 0xbb, 0xbf, 0x61] }])).files[0].source, '\ufeffa');
});

check('encoding wraps model failures and retains the original cause', () => {
  const original = TextEncoder.prototype.encode;
  TextEncoder.prototype.encode = () => { throw new Error('An invalid model must reject before encoding.'); };
  try {
    for (const [value, code] of [
      [null, 'invalid_project'],
      [{ version: 2, entry: 'a.min', files: [{ path: 'a.min', source: '' }] }, 'unsupported_version'],
      [project([{ path: 'a.min', source: '\ud800' }]), 'invalid_source'],
      [project([{ path: '../a.min', source: '' }]), 'invalid_path'],
      [project([{ path: 'a.min', source: 'x'.repeat(65537) }]), 'too_large'],
    ]) {
      assert.throws(() => encodeProject(value), error => failure(code, ProjectError)(error) && error.cause.code === code);
    }
  } finally { TextEncoder.prototype.encode = original; }
});

check('decoded projects apply entry, path, duplicate and collision validation', () => {
  for (const [entry, files, code] of [
    ['missing.min', [{ path: 'a.min', source: '' }], 'missing_entry'],
    ['../a.min', [{ path: 'a.min', source: '' }], 'invalid_path'],
    ['a.min', [{ path: '../a.min', source: '' }], 'invalid_path'],
    ['library/a.min', [{ path: 'library/a.min', source: '' }], 'reserved_path'],
    ['a.min', [{ path: 'a.min', source: '' }, { path: 'a.min', source: '' }], 'duplicate_path'],
    ['a.min', [{ path: 'a.min', source: '' }, { path: 'a.min/b.min', source: '' }], 'path_collision'],
    ['', [{ path: 'a.min', source: '' }], 'invalid_path'],
    ['a.min', [{ path: '', source: '' }], 'invalid_path'],
    ['a.min', [{ path: 'a\0.min', source: '' }], 'invalid_path'],
  ]) reject(wire(entry, files), code, ProjectError);
  const names = ['__proto__.min', 'constructor.min', 'toString.min'];
  assert.deepEqual(decodeProject(wire('toString.min', names.map(path => ({ path, source: path })))).files.map(file => file.path), names);
});

check('noncanonical wire order rejects instead of silently sorting', () => {
  const paths = ['Z.min', 'a.min', 'ä.min', '𐀀.min', '🌙.min', '\ue000.min'];
  const files = paths.map(path => ({ path, source: path }));
  assert.deepEqual(decodeProject(wire('a.min', files)).files.map(file => file.path), paths);
  reject(wire('a.min', [...files].reverse()), 'noncanonical');
  reject(wire('a.min', [files[1], files[0], ...files.slice(2)]), 'noncanonical');
  assert.deepEqual(encodeProject(project([...files].reverse(), 'a.min')), wire('a.min', files));
});

check('256-byte entry and path limits count actual UTF-8 bytes', () => {
  for (const path of ['a'.repeat(252) + '.min', '🌙'.repeat(63) + '.min']) {
    assert.equal(Buffer.byteLength(path, 'utf8'), 256);
    assert.deepEqual(decodeProject(wire(path, [{ path, source: '' }])), projectFromSource('', path));
  }
  for (const path of ['a'.repeat(253) + '.min', '🌙'.repeat(64) + '.min']) {
    reject(wire(path, [{ path: 'a.min', source: '' }]), 'path_too_long');
    reject(wire('a.min', [{ path, source: '' }]), 'path_too_long');
  }
});

check('64 KiB source and cumulative source budget are exact', () => {
  for (const source of ['a'.repeat(65536), '🌙'.repeat(16384), '€'.repeat(21845) + 'a']) {
    const value = projectFromSource(source);
    assert.equal(Buffer.byteLength(source, 'utf8'), 65536);
    assert.deepEqual(decodeProject(wire(value.entry, value.files)), value);
    assert.deepEqual(decodeProject(encodeProject(value)), value);
  }
  const files = [{ path: 'a.min', source: 'é'.repeat(16384) }, { path: 'b.min', source: 'x'.repeat(32768) }, { path: 'c.min', source: '' }];
  assert.equal(projectSourceBytes(decodeProject(wire('c.min', files))), 65536);
  reject(wire('a.min', [{ path: 'a.min', source: 'a'.repeat(65537) }]), 'too_large');
  reject(wire('a.min', [files[0], { ...files[1], source: files[1].source + 'x' }]), 'too_large');
  reject(wire('a.min', [{ path: 'a.min', source: '', sourceLength: 0xffffffff }]), 'too_large');
});

check('largest valid project uses the exact bounded wire size', () => {
  const files = Array.from({ length: 16 }, (_, index) => ({
    path: String(index).padStart(2, '0') + 'p'.repeat(250) + '.min',
    source: index === 0 ? 'x'.repeat(65536) : '',
  }));
  assert(files.every(file => Buffer.byteLength(file.path, 'utf8') === 256));
  const value = project(files, files[15].path);
  const packed = encodeProject(value);
  assert.equal(packed.byteLength, 69988);
  assert(packed.byteLength <= MAX_PACKED_PROJECT_BYTES);
  assert.deepEqual(packed, wire(value.entry, files));
  assert.deepEqual(decodeProject(packed), normalizeProject(value));
  const fields = Buffer.from(packed);
  assert.equal(fields.readUInt16LE(2), 256);
  assert.equal(fields.readUInt16LE(260), 256);
  assert.equal(fields.readUInt32LE(262), 65536);
});

console.log(`PASS ${checks} project sharing groups: deterministic binary format, bounded parsing, strict UTF-8 and project validation`);
