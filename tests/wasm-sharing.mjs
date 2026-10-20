import assert from 'node:assert/strict';
import {
  ShareLinkError, SHARE_SOURCE_LIMIT, SHARE_PACKED_LIMIT, SHARE_FRAGMENT_LIMIT,
  encodeShareFragment, decodeShareFragment, createShareURL, readShareURL,
} from '../playground/share.mjs';

let checks = 0;
async function check(name, run) {
  await run();
  checks++;
  console.log(`PASS sharing/${name}`);
}
function failure(code) {
  return error => error instanceof ShareLinkError && error.name === 'ShareLinkError'
    && error.code === code && error.message.length > 15;
}
function envelope(bytes, { declared = bytes.length, version = 'v1', mode = 'u', crc = crc32(bytes) } = {}) {
  return `#minyar=${version}.${mode}.${declared}.${crc}.${Buffer.from(bytes).toString('base64url')}`;
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

await check('known checksum and canonical base64url', async () => {
  assert.equal(await encodeShareFragment('123456789'), '#minyar=v1.u.9.cbf43926.MTIzNDU2Nzg5');
  assert.equal(await encodeShareFragment(''), '#minyar=v1.u.0.00000000.');
  assert.equal(await encodeShareFragment('a'), '#minyar=v1.u.1.e8b7be43.YQ');
  assert.equal(crc32(Buffer.from('123456789')), 'cbf43926');
});

await check('UTF-8 source preserves exact characters', async () => {
  for (const source of ['', 'print("Hello")\n', '星🌙 café e\u0301 🚀', '\0\0before\0after\0', '\ufeffprint("BOM")\r\n', 'a\r\nb\rc\n', '#?&=+%/ \\"<>', '\ufffd']) {
    const fragment = await encodeShareFragment(source, { compress: 'never' });
    assert.deepEqual(await decodeShareFragment(fragment), { source });
    const payload = new URLSearchParams(fragment.slice(1)).get('minyar').split('.').at(-1);
    assert.equal(payload, Buffer.from(source).toString('base64url'));
  }
});

await check('optional example metadata and independent round trips', async () => {
  for (const exampleId of ['hello', 'records-2', 'A_B', 'x'.repeat(64)]) {
    const fragment = await encodeShareFragment('print(42)', { exampleId });
    assert.deepEqual(await decodeShareFragment(fragment), { source: 'print(42)', exampleId });
  }
  const first = await encodeShareFragment('first', { exampleId: 'hello' });
  const second = await encodeShareFragment('second');
  assert.deepEqual(await decodeShareFragment(second), { source: 'second' });
  assert.deepEqual(await decodeShareFragment(first), { source: 'first', exampleId: 'hello' });
  for (const exampleId of ['', 'a b', '../hello', '🌙', null, 3, 'x'.repeat(65)]) {
    await assert.rejects(encodeShareFragment('', { exampleId }), failure('invalid_fragment'));
  }
});

await check('64 KiB byte boundary for ASCII and astral text', async () => {
  for (const source of ['a'.repeat(SHARE_SOURCE_LIMIT - 1), 'a'.repeat(SHARE_SOURCE_LIMIT), '🌙'.repeat(SHARE_SOURCE_LIMIT / 4)]) {
    const fragment = await encodeShareFragment(source);
    assert(fragment.length <= SHARE_FRAGMENT_LIMIT);
    assert.deepEqual(await decodeShareFragment(fragment), { source });
  }
  await assert.rejects(encodeShareFragment('a'.repeat(SHARE_SOURCE_LIMIT + 1)), failure('too_large'));
  await assert.rejects(encodeShareFragment('🌙'.repeat(SHARE_SOURCE_LIMIT / 4 + 1)), failure('too_large'));
  await assert.rejects(decodeShareFragment('#minyar=v1.u.65537.00000000.'), failure('too_large'));
});

await check('invalid source and strict UTF-8', async () => {
  for (const source of [null, 4, {}, new Uint8Array([97]), '\ud800', '\udfff', 'a\ud800b']) {
    await assert.rejects(encodeShareFragment(source), failure('invalid_source'));
  }
  for (const bytes of [[255], [0xc0, 0x80], [0xe2, 0x82], [0xed, 0xa0, 0x80], [0xf4, 0x90, 0x80, 0x80]]) {
    await assert.rejects(decodeShareFragment(envelope(bytes)), failure('corrupt'));
  }
});

await check('damaged and noncanonical payloads', async () => {
  const valid = await encodeShareFragment('print("moon")\n');
  for (const fragment of [valid.slice(0, -1), valid + 'A', valid.replace('.u.14.', '.u.13.'), valid.replace(/\.[0-9a-f]{8}\./, '.00000000.'),
    '#minyar=v1.u.1.e8b7be43.YR', '#minyar=v1.u.1.e8b7be43.YQ==', '#minyar=v1.u.1.e8b7be43.Y+',
    '#minyar=v1.u.1.e8b7be43.Y/', '#minyar=v1.u.1.e8b7be43.%', '#minyar=v1.u.1.e8b7be43.%GG',
    '#minyar=v1.u.01.e8b7be43.YQ', '#minyar=v1.u.-1.e8b7be43.YQ', '#minyar=v1.u.NaN.e8b7be43.YQ',
    '#minyar=v1.u.1.E8B7BE43.YQ', '#minyar=v1.u.1.e8b7be43', '#minyar=v1.u.1.e8b7be43.YQ.extra',
    '#minyar', '#minyar=', '#minyar=v01.u.1.e8b7be43.YQ', '#minyar=v1.u.0.00000000.A']) {
    await assert.rejects(decodeShareFragment(fragment), failure('corrupt'), fragment);
  }
  await assert.rejects(decodeShareFragment(valid + '&minyar=v1.u.0.00000000.'), failure('corrupt'));
  await assert.rejects(decodeShareFragment(valid + '&example=a&example=b'), failure('corrupt'));
  await assert.rejects(decodeShareFragment(valid + '&unexpected=yes'), failure('corrupt'));
});

await check('versions and compression remain explicit and bounded', async () => {
  await assert.rejects(decodeShareFragment('#minyar=v2.u.0.00000000.'), failure('unsupported_version'));
  await assert.rejects(decodeShareFragment('#minyar=v999.u.0.00000000.'), failure('unsupported_version'));
  for (const mode of ['g', 'z', 'U']) {
    await assert.rejects(decodeShareFragment(`#minyar=v1.${mode}.0.00000000.`), failure('unsupported_encoding'));
  }
  await assert.rejects(encodeShareFragment('program', { compress: 'always' }), failure('compression_unavailable'));
  await assert.rejects(encodeShareFragment('', { compress: 'invalid' }), failure('invalid_option'));
  const compression = Object.getOwnPropertyDescriptor(globalThis, 'DecompressionStream');
  const originalAtob = globalThis.atob;
  let nativeDecoders = 0, base64Decodes = 0;
  Object.defineProperty(globalThis, 'DecompressionStream', { configurable: true, value: class {
    constructor() { nativeDecoders++; throw new Error('A compressed payload must not reach this decoder.'); }
  } });
  globalThis.atob = (...args) => { base64Decodes++; return originalAtob(...args); };
  try {
    await assert.rejects(decodeShareFragment('#minyar=v1.g.1.00000000.H4sIAAAAAAAA'), failure('unsupported_encoding'));
    await assert.rejects(decodeShareFragment('#minyar=v1.u.1.00000000.' + 'A'.repeat(4 * Math.ceil(SHARE_PACKED_LIMIT / 3) + 1)), failure('too_large'));
    await assert.rejects(decodeShareFragment('#' + 'A'.repeat(SHARE_FRAGMENT_LIMIT)), failure('too_large'));
    assert.equal(nativeDecoders, 0);
    assert.equal(base64Decodes, 0, 'length caps reject before decoding');
  } finally {
    globalThis.atob = originalAtob;
    if (compression) Object.defineProperty(globalThis, 'DecompressionStream', compression);
    else delete globalThis.DecompressionStream;
  }
});

await check('URL fragment is private and replaces stale navigation state', async () => {
  const source = 'print("PRIVATE # ? & 🌙")\r\n\0';
  const base = new URL('https://example.test/try%20minyar/?old=PRIVATE&source=stale#old-anchor');
  const original = base.href;
  const result = new URL(await createShareURL(base, source, { exampleId: 'hello' }));
  assert.equal(result.origin, base.origin);
  assert.equal(result.pathname, base.pathname);
  assert.equal(result.search, '');
  assert.equal(result.href.split('#')[0], 'https://example.test/try%20minyar/');
  assert.equal(base.href, original, 'caller-owned URL must remain unchanged');
  assert.deepEqual(await readShareURL(result), { source, exampleId: 'hello' });
  const replacement = await createShareURL(result, 'new source');
  assert.deepEqual(await readShareURL(replacement), { source: 'new source' });
  for (const address of ['https://example.test/', 'https://example.test/?minyar=v1.u.0.00000000.',
    'https://example.test/#section', 'https://example.test/#example=hello', 'https://example.test/#']) {
    assert.equal(await readShareURL(address), null);
  }
  for (const fragment of ['', '#', '#section', '#other=hello']) assert.equal(await decodeShareFragment(fragment), null);
  for (const address of ['not a URL', '../relative', 'file:///tmp/site.html', 'javascript:alert(1)',
    'data:text/html,hello', 'https://user:password@example.test/', null, 42]) {
    await assert.rejects(createShareURL(address, ''), failure('invalid_url'));
    await assert.rejects(readShareURL(address), failure('invalid_url'));
  }
  await assert.rejects(decodeShareFragment('minyar=v1.u.0.00000000.'), failure('invalid_fragment'));
  await assert.rejects(decodeShareFragment(null), failure('invalid_fragment'));
});

await check('sharing performs no network calls and handles varied Unicode', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = () => { throw new Error('Sharing must never make a network request.'); };
  try {
    let state = 0x20261020;
    for (let sample = 0; sample < 48; sample++) {
      let source = '';
      for (let item = 0; item < 80; item++) {
        state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
        let scalar = state % 0x110000;
        if (scalar >= 0xd800 && scalar <= 0xdfff) scalar = 32;
        source += String.fromCodePoint(scalar);
      }
      const url = await createShareURL('https://example.test/try?source=old#stale', source);
      assert.deepEqual(await readShareURL(url), { source });
    }
  } finally { globalThis.fetch = originalFetch; }
});

console.log(`PASS ${checks} sharing groups: private URL fragments, strict UTF-8/CRC, limits and corruption`);
