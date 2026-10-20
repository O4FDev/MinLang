import assert from 'node:assert/strict';
import { ProjectError, normalizeProject, projectFromSource } from '../playground/project.mjs';
import { ProjectShareError, MAX_PACKED_PROJECT_BYTES } from '../playground/project-share.mjs';
import {
  ShareLinkError, SHARE_SOURCE_LIMIT, SHARE_PACKED_LIMIT, SHARE_FRAGMENT_LIMIT,
  encodeShareFragment, decodeShareFragment, createShareURL, readShareURL,
} from '../playground/share.mjs';
import { createSharing } from '../playground/share-ui.mjs';

let checks = 0;
async function check(name, run) {
  await run();
  checks++;
  console.log(`PASS project-links/${name}`);
}
function project(files, entry = files[0]?.path ?? 'main.min') { return { version: 1, entry, files }; }
function failure(code, cause) {
  return error => error instanceof ShareLinkError && error.name === 'ShareLinkError'
    && error.code === code && error.message.length > 15
    && (cause === undefined || error.cause instanceof cause);
}
function crc32(bytes) {
  const table = Array.from({ length: 256 }, (_, first) => {
    let value = first;
    for (let bit = 0; bit < 8; bit++) value = value & 1 ? (value >>> 1) ^ 0xedb88320 : value >>> 1;
    return value >>> 0;
  });
  let value = 0xffffffff;
  for (const byte of bytes) value = (value >>> 8) ^ table[(value ^ byte) & 255];
  return ((value ^ 0xffffffff) >>> 0).toString(16).padStart(8, '0');
}
function envelope(bytes, { version = 'v2', mode = 'p', declared = bytes.length, crc = crc32(bytes) } = {}) {
  return `#minyar=${version}.${mode}.${declared}.${crc}.${Buffer.from(bytes).toString('base64url')}`;
}
function u16(value) { const bytes = Buffer.alloc(2); bytes.writeUInt16LE(value); return bytes; }
function u32(value) { const bytes = Buffer.alloc(4); bytes.writeUInt32LE(value); return bytes; }
function wire(entry, files, version = 1) {
  const entryBytes = Buffer.from(entry);
  const chunks = [Buffer.from([version, files.length]), u16(entryBytes.length), entryBytes];
  for (const file of files) {
    const path = Buffer.from(file.path), source = Buffer.from(file.source);
    chunks.push(u16(path.length), u32(source.length), path, source);
  }
  return Uint8Array.from(Buffer.concat(chunks));
}
const source = 'print("Entry 🌙")\r\n';
const value = project([{ path: 'src/main.min', source }, { path: 'src/helpers.min', source: '\ufeff// private dependency\0\r\n' }], 'src/main.min');
const expected = { source, project: normalizeProject(value) };

await check('v2 uses real CRC32 and the exact independent binary fixture', async () => {
  assert.equal(crc32(Buffer.from('123456789')), 'cbf43926');
  const fixture = Buffer.from('010108006d61696e2e6d696e0800010000006d61696e2e6d696e78', 'hex');
  assert.equal(fixture.length, 27);
  assert.equal(await encodeShareFragment('x', { project: projectFromSource('x') }), envelope(fixture));
  assert.deepEqual(await decodeShareFragment(envelope(fixture)), { source: 'x', project: projectFromSource('x') });
  const fragment = await encodeShareFragment(source, { project: value });
  assert.equal(fragment, envelope(wire(value.entry, [...value.files].reverse())));
  assert.deepEqual(await decodeShareFragment(fragment), expected);
});

await check('legacy v1 bytes, shape, Unicode and source boundaries remain compatible', async () => {
  assert.equal(await encodeShareFragment('123456789'), '#minyar=v1.u.9.cbf43926.MTIzNDU2Nzg5');
  assert.equal(await encodeShareFragment('x', { project: undefined }), await encodeShareFragment('x'));
  for (const text of ['', '\ufeffprint("BOM")\r\n\0', '🌙'.repeat(16384)]) {
    const fragment = await encodeShareFragment(text);
    assert(fragment.startsWith('#minyar=v1.u.'));
    assert.deepEqual(await decodeShareFragment(fragment), { source: text });
  }
  assert.equal(SHARE_SOURCE_LIMIT, 65536);
  assert.equal(SHARE_PACKED_LIMIT, MAX_PACKED_PROJECT_BYTES);
  await assert.rejects(encodeShareFragment('a'.repeat(65537)), failure('too_large'));
  await assert.rejects(decodeShareFragment('#minyar=v1.u.65537.00000000.'), failure('too_large'));
  for (const text of ['\ud800', '\udfff', null, 4]) await assert.rejects(encodeShareFragment(text), failure('invalid_source'));
});

await check('complete projects and metadata round trip canonically', async () => {
  for (const compress of ['auto', 'never']) {
    const fragment = await encodeShareFragment(source, { project: value, exampleId: 'custom-2', compress });
    assert.deepEqual(await decodeShareFragment(fragment), { ...expected, exampleId: 'custom-2' });
    const reordered = project([...value.files].reverse(), value.entry);
    assert.equal(await encodeShareFragment(source, { project: reordered, exampleId: 'custom-2', compress }), fragment);
  }
  const decoded = await decodeShareFragment(await encodeShareFragment(source, { project: value }));
  assert(Object.isFrozen(decoded.project) && Object.isFrozen(decoded.project.files) && decoded.project.files.every(Object.isFrozen));
  const before = JSON.stringify(value);
  await encodeShareFragment(source, { project: value });
  assert.equal(JSON.stringify(value), before);
});

await check('source provenance and immutable snapshots are exact', async () => {
  for (const text of ['', source + ' ', source.replace('\r\n', '\n')]) {
    await assert.rejects(encodeShareFragment(text, { project: value }), failure('source_mismatch'));
  }
  const mutable = project([{ path: 'main.min', source: 'entry' }, { path: 'other.min', source: 'before' }]);
  const pending = encodeShareFragment('entry', { project: mutable });
  mutable.files[1].source = 'after';
  const decoded = await decodeShareFragment(await pending);
  assert.equal(decoded.project.files[1].source, 'before');
  await assert.rejects(createShareURL('https://example.test/try', 'wrong', { project: value }), failure('source_mismatch'));
});

await check('invalid projects retain model codes and original causes', async () => {
  for (const [invalid, code] of [
    [null, 'invalid_project'],
    [{ ...value, extra: true }, 'invalid_project'],
    [project([{ path: 'a.min', source }, { path: 'library/overwrite.min', source: '' }]), 'reserved_path'],
    [project([{ path: 'a.min', source }, { path: 'b.min', source: '\ud800' }]), 'invalid_source'],
    [project([{ path: 'a.min', source }, { path: 'b.min', source: 'x'.repeat(65536) }]), 'too_large'],
  ]) await assert.rejects(encodeShareFragment(source, { project: invalid }), failure(code, ProjectError));
  for (const compress of ['always', 'bad']) {
    await assert.rejects(encodeShareFragment(source, { project: value, compress }), failure(compress === 'always' ? 'compression_unavailable' : 'invalid_option'));
  }
  await assert.rejects(encodeShareFragment(source, { project: value, exampleId: '../bad' }), failure('invalid_fragment'));
});

await check('largest project fragment carries all 69,988 packed bytes', async () => {
  const files = Array.from({ length: 16 }, (_, index) => ({
    path: String(index).padStart(2, '0') + 'p'.repeat(250) + '.min', source: index === 0 ? 'x'.repeat(65536) : '',
  }));
  const largest = project(files, files[0].path);
  const packed = wire(largest.entry, files);
  assert.equal(packed.length, 69988);
  const fragment = await encodeShareFragment(files[0].source, { project: largest, exampleId: 'x'.repeat(64) });
  assert(fragment.startsWith('#minyar=v2.p.69988.'));
  assert(fragment.length <= SHARE_FRAGMENT_LIMIT);
  assert.deepEqual(await decodeShareFragment(fragment), { source: files[0].source, project: normalizeProject(largest), exampleId: 'x'.repeat(64) });
  assert.equal(new URLSearchParams(fragment.slice(1)).get('minyar').split('.')[4], Buffer.from(packed).toString('base64url'));
});

await check('malformed envelopes and unsupported modes remain typed', async () => {
  const valid = await encodeShareFragment(source, { project: value });
  const prefix = '#minyar=v2.p.0.00000000.';
  for (const fragment of [valid.slice(0, -1), valid + 'A', valid + '=', valid.replace('.p.', '.p.0.'),
    '#minyar=v2.p.01.00000000.AA', '#minyar=v2.p.-1.00000000.AA', '#minyar=v2.p.NaN.00000000.AA',
    '#minyar=v2.p.0.FFFFFFFF.', '#minyar=v2.p.0.00000000', prefix + '%GG', prefix + 'A+', prefix + 'A/',
    '#minyar=v02.p.0.00000000.', valid + '&minyar=v2.p.0.00000000.', valid + '&example=a&example=b', valid + '&unknown=true']) {
    await assert.rejects(decodeShareFragment(fragment), failure('corrupt'), fragment.slice(0, 100));
  }
  for (const [version, mode] of [['v2', 'u'], ['v2', 'g'], ['v2', 'P'], ['v1', 'p']]) {
    await assert.rejects(decodeShareFragment(`#minyar=${version}.${mode}.0.00000000.`), failure('unsupported_encoding'));
  }
  for (const version of ['v3', 'v999']) await assert.rejects(decodeShareFragment(`#minyar=${version}.p.0.00000000.`), failure('unsupported_version'));
  await assert.rejects(decodeShareFragment(prefix), failure('truncated', ProjectShareError));
});

await check('CRC corruption rejects before binary project decode', async () => {
  const valid = await encodeShareFragment(source, { project: value });
  const broken = valid.replace(/\.[0-9a-f]{8}\./, '.00000000.');
  assert.notEqual(broken, valid);
  const original = TextDecoder.prototype.decode;
  let decodes = 0;
  TextDecoder.prototype.decode = () => { decodes++; throw new Error('The project must not decode until CRC passes.'); };
  try {
    await assert.rejects(decodeShareFragment(broken), failure('corrupt'));
    assert.equal(decodes, 0);
  } finally { TextDecoder.prototype.decode = original; }
});

await check('global and version-specific bounds reject before base64 allocation', async () => {
  const original = globalThis.atob;
  let decodes = 0;
  globalThis.atob = () => { decodes++; throw new Error('Oversized encoded input must reject before base64 decode.'); };
  try {
    for (const fragment of ['#' + 'A'.repeat(SHARE_FRAGMENT_LIMIT), '#minyar=v2.p.71681.00000000.',
      '#minyar=v1.u.65537.00000000.', '#minyar=v2.p.0.00000000.' + 'A'.repeat(4 * Math.ceil(SHARE_PACKED_LIMIT / 3) + 1)]) {
      await assert.rejects(decodeShareFragment(fragment), failure('too_large'));
    }
    assert.equal(decodes, 0);
  } finally { globalThis.atob = original; }
});

await check('valid CRC cannot bypass binary model validation', async () => {
  const good = wire('a.min', [{ path: 'a.min', source: '' }]);
  for (const [packed, code] of [
    [Uint8Array.from([...good, 0]), 'trailing_data'],
    [good.slice(0, -1), 'truncated'],
    [wire('a.min', [{ path: 'a.min', source: '' }, { path: 'a.min', source: '' }]), 'duplicate_path'],
    [wire('a.min', [{ path: 'b.min', source: '' }, { path: 'a.min', source: '' }]), 'noncanonical'],
    [wire('missing.min', [{ path: 'a.min', source: '' }]), 'missing_entry'],
    [wire('a.min', [{ path: 'a.min', source: [255] }]), 'invalid_utf8'],
    [wire('a.min', [{ path: 'a.min', source: '' }], 2), 'unsupported_version'],
  ]) await assert.rejects(decodeShareFragment(envelope(packed)), failure(code, ProjectShareError));
  await assert.rejects(decodeShareFragment(envelope(wire('a.min', [{ path: 'a.min', source: '' }, { path: 'a.min', source: '' }]))),
    error => failure('duplicate_path', ProjectShareError)(error) && error.cause.cause instanceof ProjectError);
});

await check('CRC detects damage and does not authenticate source authorship', async () => {
  const replacement = projectFromSource('a different valid program');
  const forged = envelope(wire(replacement.entry, replacement.files));
  assert.deepEqual(await decodeShareFragment(forged), { source: replacement.files[0].source, project: replacement });
  const original = await encodeShareFragment(source, { project: value });
  assert.notEqual(forged, original, 'any author can create a different valid CRC and payload');
});

await check('URL APIs keep all project data in the fragment without network calls', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = () => { throw new Error('Project sharing must make no network calls.'); };
  try {
    const base = new URL('https://example.test/nested/try%20minyar/?source=OLD&track=1#old');
    const before = base.href;
    const address = new URL(await createShareURL(base, source, { project: value, exampleId: 'hello' }));
    assert.equal(base.href, before);
    assert.equal(address.href.split('#')[0], 'https://example.test/nested/try%20minyar/');
    assert.equal(address.search, '');
    assert.equal(address.pathname, base.pathname);
    assert.deepEqual(await readShareURL(address), { ...expected, exampleId: 'hello' });
    const legacy = await createShareURL(address, 'legacy');
    assert.deepEqual(await readShareURL(legacy), { source: 'legacy' });
    assert.equal(await readShareURL('https://example.test/?minyar=v2.p.0.00000000.'), null);
  } finally { globalThis.fetch = originalFetch; }
});

async function withSharingUI(run) {
  const handlers = new Map();
  const button = { disabled: false, addEventListener(name, handler) { handlers.set(name, handler); } };
  const field = { hidden: true, value: '', addEventListener() {}, select() {} };
  const message = { textContent: '' };
  const elements = new Map([['share', button], ['share-url', field], ['share-message', message]]);
  const values = {
    document: { getElementById(id) { return elements.get(id); } },
    window: { addEventListener() {} }, navigator: {}, location: new URL('https://example.test/nested/try/?old=1#old'),
  };
  const previous = new Map(Object.keys(values).map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
  for (const [key, value] of Object.entries(values)) Object.defineProperty(globalThis, key, { configurable: true, value });
  try { await run({ button, field, message, click: () => handlers.get('click')() }); }
  finally {
    for (const [key, descriptor] of previous) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else delete globalThis[key];
    }
  }
}

await check('sharing UI snapshots the complete project and defaults to v1', async () => {
  await withSharingUI(async ui => {
    let snapshots = 0;
    createSharing({ getSource: () => source, getRevision: () => 1, getExampleId: () => 'hello',
      getProject: () => { snapshots++; return value; }, loadShared() {} });
    await ui.click();
    assert.equal(snapshots, 1);
    assert.equal(ui.button.disabled, false);
    assert.equal(ui.field.hidden, false);
    assert.deepEqual(await readShareURL(ui.field.value), { ...expected, exampleId: 'hello' });
  });
  await withSharingUI(async ui => {
    createSharing({ getSource: () => 'legacy', getRevision: () => 1, getExampleId: () => 'hello', loadShared() {} });
    await ui.click();
    assert.deepEqual(await readShareURL(ui.field.value), { source: 'legacy', exampleId: 'hello' });
  });
});

await check('snapshot failures restore the button and stale snapshots stay hidden', async () => {
  await withSharingUI(async ui => {
    createSharing({ getSource: () => source, getRevision: () => 1, getExampleId: () => undefined,
      getProject: () => { throw new ProjectError('invalid_project', 'The draft project is incomplete.'); }, loadShared() {} });
    await ui.click();
    assert.equal(ui.button.disabled, false);
    assert.equal(ui.field.hidden, true);
    assert.equal(ui.message.textContent, 'The draft project is incomplete.');
  });
  await withSharingUI(async ui => {
    let revision = 1;
    createSharing({ getSource: () => source, getRevision: () => revision, getExampleId: () => undefined,
      getProject: () => { revision++; return value; }, loadShared() {} });
    await ui.click();
    assert.equal(ui.button.disabled, false);
    assert.equal(ui.field.hidden, true);
    assert.match(ui.message.textContent, /changed/);
  });
});

console.log(`PASS ${checks} project link groups: v2 CRC/base64 envelope, legacy v1, source provenance and guarded UI snapshots`);
