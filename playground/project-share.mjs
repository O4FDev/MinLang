import {
  ProjectError, MAX_PROJECT_FILES, MAX_PROJECT_BYTES, MAX_PROJECT_PATH_BYTES, normalizeProject,
} from './project.mjs';

export const MAX_PACKED_PROJECT_BYTES = 70 * 1024;
const encoder = new TextEncoder();
const decoder = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true });

export class ProjectShareError extends Error {
  constructor(code, message, options) {
    super(message, options);
    this.name = 'ProjectShareError';
    this.code = code;
  }
}

function fail(code, message, cause) {
  throw new ProjectShareError(code, message, cause === undefined ? undefined : { cause });
}

function normalized(value) {
  try { return normalizeProject(value); }
  catch (error) {
    if (error instanceof ProjectError) fail(error.code, error.message, error);
    throw error;
  }
}

// Schema 1: u8 schema, u8 file count, u16 entry bytes, entry UTF-8;
// then each canonical file: u16 path bytes, u32 source bytes, path, source.
// All integers are unsigned little-endian. This layer adds no URL or checksum.
export function encodeProject(value) {
  const project = normalized(value); // Validate bounds and Unicode before encoding.
  const entry = encoder.encode(project.entry);
  const files = project.files.map(file => ({ path: encoder.encode(file.path), source: encoder.encode(file.source) }));
  const length = 4 + entry.length + files.reduce((total, file) => total + 6 + file.path.length + file.source.length, 0);
  if (length > MAX_PACKED_PROJECT_BYTES) fail('too_large', 'This shared project exceeds the packed size limit.');
  const bytes = new Uint8Array(length);
  const view = new DataView(bytes.buffer);
  bytes[0] = 1;
  bytes[1] = files.length;
  view.setUint16(2, entry.length, true);
  let offset = 4;
  bytes.set(entry, offset);
  offset += entry.length;
  for (const file of files) {
    view.setUint16(offset, file.path.length, true);
    view.setUint32(offset + 2, file.source.length, true);
    offset += 6;
    bytes.set(file.path, offset);
    offset += file.path.length;
    bytes.set(file.source, offset);
    offset += file.source.length;
  }
  return bytes;
}

export function decodeProject(bytes) {
  if (!(bytes instanceof Uint8Array)) fail('invalid_bytes', 'A shared project must contain a Uint8Array payload.');
  if (bytes.byteLength > MAX_PACKED_PROJECT_BYTES) fail('too_large', 'This shared project exceeds the packed size limit.');
  let offset = 0;
  function need(length) {
    if (length > bytes.byteLength - offset) fail('truncated', 'This shared project is damaged or incomplete.');
  }
  need(4);
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  if (view.getUint8(0) !== 1) fail('unsupported_version', 'This shared project uses an unsupported format version.');
  const count = view.getUint8(1);
  if (count < 1 || count > MAX_PROJECT_FILES) fail('invalid_count', 'A shared project must contain between 1 and 16 source files.');
  const entryLength = view.getUint16(2, true);
  offset = 4;
  function pathLimit(length) {
    if (length > MAX_PROJECT_PATH_BYTES) fail('path_too_long', 'A shared project path exceeds the 256-byte limit.');
  }
  pathLimit(entryLength);
  need(entryLength);
  const entryOffset = offset;
  offset += entryLength;
  const records = [];
  let sourceBytes = 0;
  for (let index = 0; index < count; index++) {
    need(6);
    const pathLength = view.getUint16(offset, true);
    const sourceLength = view.getUint32(offset + 2, true);
    offset += 6;
    pathLimit(pathLength);
    if (sourceLength > MAX_PROJECT_BYTES - sourceBytes) {
      fail('too_large', 'Shared project sources must fit within 64 KiB of UTF-8 text.');
    }
    need(pathLength + sourceLength);
    records.push({ pathOffset: offset, pathLength, sourceOffset: offset + pathLength, sourceLength });
    offset += pathLength + sourceLength;
    sourceBytes += sourceLength;
  }
  if (offset !== bytes.byteLength) fail('trailing_data', 'This shared project contains unexpected trailing data.');
  // Preflight every header, bound and byte range before creating any text view.
  function text(start, length) {
    try { return decoder.decode(bytes.subarray(start, start + length)); }
    catch (error) { fail('invalid_utf8', 'This shared project contains invalid UTF-8 text.', error); }
  }
  const entry = text(entryOffset, entryLength);
  const files = records.map(record => ({
    path: text(record.pathOffset, record.pathLength),
    source: text(record.sourceOffset, record.sourceLength),
  }));
  const project = normalized({ version: 1, entry, files });
  if (files.some((file, index) => file.path !== project.files[index].path)) {
    fail('noncanonical', 'Shared project files must be stored in canonical path order.');
  }
  return project;
}
