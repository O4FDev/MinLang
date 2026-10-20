// Project paths are exact virtual filesystem names, never URL or OS paths.
export const MAX_PROJECT_FILES = 16;
export const MAX_PROJECT_BYTES = 64 * 1024;
export const MAX_PROJECT_PATH_BYTES = 256;

export class ProjectError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'ProjectError';
    this.code = code;
  }
}

function fail(code, message) { throw new ProjectError(code, message); }

function record(value, keys, code, message) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)
      || ![Object.prototype, null].includes(Object.getPrototypeOf(value))) fail(code, message);
  const own = Reflect.ownKeys(value);
  if (own.length !== keys.length || own.some(key => !keys.includes(key))) fail(code, message);
  const copy = Object.create(null);
  for (const key of keys) {
    const property = Object.getOwnPropertyDescriptor(value, key);
    if (!property || !Object.hasOwn(property, 'value') || !property.enumerable) fail(code, message);
    copy[key] = property.value;
  }
  return copy;
}

// Count without encoding buffers. UTF-16 length is an early lower bound; the
// scan rejects isolated surrogates and stops at the first excess UTF-8 byte.
function utf8Bytes(text, limit, invalidCode, largeCode, label) {
  if (typeof text !== 'string') fail(invalidCode, `${label} must be text.`);
  const tooLarge = () => fail(largeCode, `${label} exceeds its UTF-8 byte limit.`);
  if (text.length > limit) tooLarge();
  let bytes = 0;
  for (let index = 0; index < text.length; index++) {
    const unit = text.charCodeAt(index);
    if (unit < 0x80) bytes++;
    else if (unit < 0x800) bytes += 2;
    else if (unit >= 0xd800 && unit <= 0xdbff) {
      const next = text.charCodeAt(index + 1);
      if (!(next >= 0xdc00 && next <= 0xdfff)) {
        fail(invalidCode, `${label} contains an incomplete Unicode character.`);
      }
      index++;
      bytes += 4;
    } else if (unit >= 0xdc00 && unit <= 0xdfff) {
      fail(invalidCode, `${label} contains an incomplete Unicode character.`);
    } else bytes += 3;
    if (bytes > limit) tooLarge();
  }
  return bytes;
}

function projectPath(path) {
  utf8Bytes(path, MAX_PROJECT_PATH_BYTES, 'invalid_path', 'path_too_long', 'Each project path');
  if (!path.endsWith('.min') || path.startsWith('/') || /^[A-Za-z]:/.test(path)
      || path.includes('\\') || /[\u0000-\u001f\u007f-\u009f\u2028\u2029]/u.test(path)) {
    fail('invalid_path', 'Use a relative .min path with forward slashes and no control characters.');
  }
  const segments = path.split('/');
  if (segments.some(segment => segment === '' || segment === '.' || segment === '..')) {
    fail('invalid_path', 'Project paths cannot contain empty, dot or parent directory segments.');
  }
  if (segments[0] === 'library') {
    fail('reserved_path', 'The library directory is reserved for the standard library.');
  }
  return path;
}

function sourceFiles(value) {
  if (!Array.isArray(value) || value.length < 1) {
    fail('invalid_files', 'A project needs an array containing at least one source file.');
  }
  if (value.length > MAX_PROJECT_FILES) fail('too_many_files', 'A project can contain at most 16 source files.');
  const keys = Reflect.ownKeys(value);
  if (keys.length !== value.length + 1
      || keys.some(key => key !== 'length' && (typeof key !== 'string' || !/^(0|[1-9][0-9]*)$/.test(key)
        || Number(key) >= value.length))) {
    fail('invalid_files', 'Project files must be a complete array without extra metadata.');
  }
  const files = [];
  for (let index = 0; index < value.length; index++) {
    const property = Object.getOwnPropertyDescriptor(value, String(index));
    if (!property || !Object.hasOwn(property, 'value') || !property.enumerable) {
      fail('invalid_files', 'Project files must be a complete array of source file records.');
    }
    files.push(property.value);
  }
  return files;
}

function normalized(value) {
  const project = record(value, ['version', 'entry', 'files'], 'invalid_project',
    'A project must contain exactly version, entry and files.');
  if (!Number.isSafeInteger(project.version) || project.version < 1) {
    fail('invalid_version', 'A project version must be a positive whole number.');
  }
  if (project.version !== 1) fail('unsupported_version', 'This project uses an unsupported format version.');
  const input = sourceFiles(project.files);
  const entry = projectPath(project.entry);
  const paths = new Set();
  let bytes = 0;
  const files = input.map(value => {
    const file = record(value, ['path', 'source'], 'invalid_file',
      'Each project file must contain exactly path and source.');
    const path = projectPath(file.path);
    if (paths.has(path)) fail('duplicate_path', 'Each source file needs a distinct project path.');
    paths.add(path);
    bytes += utf8Bytes(file.source, MAX_PROJECT_BYTES - bytes, 'invalid_source', 'too_large', 'Project source');
    return Object.freeze({ path, source: file.source });
  });
  for (const path of paths) {
    for (let slash = path.indexOf('/'); slash !== -1; slash = path.indexOf('/', slash + 1)) {
      if (paths.has(path.slice(0, slash))) {
        fail('path_collision', 'A source file cannot also be another source file’s parent directory.');
      }
    }
  }
  if (!paths.has(entry)) fail('missing_entry', 'The project entry must name one of its source files.');
  files.sort((left, right) => left.path < right.path ? -1 : left.path > right.path ? 1 : 0);
  return { project: Object.freeze({ version: 1, entry, files: Object.freeze(files) }), bytes };
}

export function normalizeProject(value) { return normalized(value).project; }

export function projectFromSource(source, entry = 'main.min') {
  return normalizeProject({ version: 1, entry, files: [{ path: entry, source }] });
}

export function projectCacheKey(project) { return JSON.stringify(normalizeProject(project)); }

export function projectSourceBytes(project) { return normalized(project).bytes; }
