import { ProjectError, normalizeProject } from './project.mjs';
import { ProjectShareError, MAX_PACKED_PROJECT_BYTES, encodeProject, decodeProject } from './project-share.mjs';

// Source belongs in a URL fragment: it is never sent as an HTTP request target.
// CRC32 detects damaged links; it does not authenticate their author.
export const SHARE_SOURCE_LIMIT = 64 * 1024;
export const SHARE_PACKED_LIMIT = MAX_PACKED_PROJECT_BYTES;
export const SHARE_FRAGMENT_LIMIT = 4 * Math.ceil(SHARE_PACKED_LIMIT / 3) + 256;
const URL_LIMIT = SHARE_FRAGMENT_LIMIT + 16 * 1024;
const encoder = new TextEncoder();
const decoder = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true });

export class ShareLinkError extends Error {
  constructor(code, message, options) {
    super(message, options);
    this.name = 'ShareLinkError';
    this.code = code;
  }
}

function fail(code, message, cause) { throw new ShareLinkError(code, message, cause === undefined ? undefined : { cause }); }
function damaged() { fail('corrupt', 'This shared program is damaged or incomplete. Ask for a new link.'); }
function tooLarge() { fail('too_large', 'Shared programs must fit within 64 KiB of UTF-8 source.'); }
function projectOperation(run) {
  try { return run(); }
  catch (error) {
    if (error instanceof ProjectShareError || error instanceof ProjectError) fail(error.code, error.message, error);
    throw error;
  }
}

function checksum(bytes) {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function hex(value) { return value.toString(16).padStart(8, '0'); }

function base64url(bytes) {
  let binary = '';
  for (let index = 0; index < bytes.length; index += 8192) {
    binary += String.fromCharCode(...bytes.subarray(index, index + 8192));
  }
  return btoa(binary).replaceAll('+', '-').replaceAll('/', '_').replace(/=+$/, '');
}

function unbase64url(text, declared) {
  if (text.length > 4 * Math.ceil(SHARE_PACKED_LIMIT / 3)) tooLarge();
  if (text.length !== Math.ceil(declared * 4 / 3)) damaged();
  if (!/^[A-Za-z0-9_-]*$/.test(text) || text.length % 4 === 1) damaged();
  let binary;
  try { binary = atob(text.replaceAll('-', '+').replaceAll('_', '/') + '='.repeat((4 - text.length % 4) % 4)); }
  catch { damaged(); }
  const bytes = Uint8Array.from(binary, character => character.charCodeAt(0));
  if (bytes.length > SHARE_PACKED_LIMIT) tooLarge();
  if (base64url(bytes) !== text) damaged(); // Reject nonzero unused padding bits.
  return bytes;
}

function sourceBytes(source) {
  if (typeof source !== 'string') fail('invalid_source', 'Choose a text program to share.');
  if (source.length > SHARE_SOURCE_LIMIT) tooLarge();
  const bytes = encoder.encode(source);
  if (bytes.length > SHARE_SOURCE_LIMIT) tooLarge();
  if (decoder.decode(bytes) !== source) fail('invalid_source', 'The program contains an incomplete Unicode character.');
  return bytes;
}

function exampleSlug(exampleId) {
  if (exampleId === undefined) return;
  if (typeof exampleId !== 'string' || !/^[A-Za-z0-9_-]{1,64}$/.test(exampleId)) {
    fail('invalid_fragment', 'This shared link has an invalid example name.');
  }
  return exampleId;
}

// Both formats remain uncompressed and work without optional compression APIs.
// v1.u stores one source; v2.p stores the complete canonical binary project.
export async function encodeShareFragment(source, { exampleId, compress = 'auto', project } = {}) {
  let bytes = sourceBytes(source);
  exampleSlug(exampleId);
  if (!['auto', 'never', 'always'].includes(compress)) fail('invalid_option', 'Choose automatic or uncompressed sharing.');
  if (compress === 'always') fail('compression_unavailable', 'Compressed sharing is not supported yet. Use an uncompressed link.');
  let format = 'v1.u';
  if (project !== undefined) {
    const normalized = projectOperation(() => normalizeProject(project));
    if (source !== normalized.files.find(file => file.path === normalized.entry).source) {
      fail('source_mismatch', 'The shared source must match the project entry file exactly.');
    }
    bytes = projectOperation(() => encodeProject(normalized));
    format = 'v2.p';
  }
  const params = new URLSearchParams({ minyar: `${format}.${bytes.length}.${hex(checksum(bytes))}.${base64url(bytes)}` });
  if (exampleId !== undefined) params.set('example', exampleId);
  return `#${params}`;
}

export async function decodeShareFragment(fragment) {
  if (typeof fragment !== 'string') fail('invalid_fragment', 'This shared link has no readable fragment.');
  if (fragment.length > SHARE_FRAGMENT_LIMIT) tooLarge();
  if (!fragment) return null;
  if (!fragment.startsWith('#')) fail('invalid_fragment', 'This shared link has an invalid fragment.');
  const params = new URLSearchParams(fragment.slice(1));
  if (!params.has('minyar')) return null;
  if (params.getAll('minyar').length !== 1 || params.getAll('example').length > 1
      || [...params.keys()].some(key => key !== 'minyar' && key !== 'example')) damaged();
  const exampleId = params.has('example') ? exampleSlug(params.get('example')) : undefined;
  const fields = params.get('minyar').split('.');
  if (!/^v[1-9][0-9]{0,3}$/.test(fields[0])) damaged();
  if (!['v1', 'v2'].includes(fields[0])) fail('unsupported_version', 'This shared link uses a newer format. Open it in an updated playground.');
  if (fields.length !== 5) damaged();
  const [version, mode, length, crc, payload] = fields;
  if (mode !== (version === 'v1' ? 'u' : 'p')) fail('unsupported_encoding', 'This shared link uses an unsupported encoding. Ask for an uncompressed link.');
  if (!/^(0|[1-9][0-9]{0,4})$/.test(length) || !/^[0-9a-f]{8}$/.test(crc)) damaged();
  const declared = Number(length);
  if (declared > (version === 'v1' ? SHARE_SOURCE_LIMIT : SHARE_PACKED_LIMIT)) tooLarge();
  const expectedCRC = Number.parseInt(crc, 16);
  const bytes = unbase64url(payload, declared);
  if (bytes.length !== declared || checksum(bytes) !== expectedCRC) damaged();
  const metadata = exampleId === undefined ? {} : { exampleId };
  if (version === 'v2') {
    const project = projectOperation(() => decodeProject(bytes));
    const source = project.files.find(file => file.path === project.entry).source;
    return { source, project, ...metadata };
  }
  let source;
  try { source = decoder.decode(bytes); } catch { damaged(); }
  return { source, ...metadata };
}

function shareURL(value) {
  if (!(value instanceof URL) && typeof value !== 'string') fail('invalid_url', 'Choose the playground’s web address to share.');
  if (String(value).length > URL_LIMIT) tooLarge();
  let url;
  try { url = new URL(value); } catch { fail('invalid_url', 'This shared link has an invalid web address.'); }
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) {
    fail('invalid_url', 'Share from a normal HTTP or HTTPS playground address.');
  }
  return url;
}

export async function createShareURL(baseURL, source, options) {
  const url = shareURL(baseURL);
  url.search = '';
  url.hash = await encodeShareFragment(source, options);
  return url.href;
}

export async function readShareURL(value) {
  return decodeShareFragment(shareURL(value).hash);
}
