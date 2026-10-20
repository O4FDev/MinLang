import { normalizeProject } from './project.mjs';

const NAMESPACE_HASH = '7934638fcc04b5e75f2eee0a7815c6dc089560f297e0db2862cd38bd0ed0c770';
const NAMESPACE_SOURCE = 'use "./geometry.min" as geometry\n\nlet point: geometry.Point = geometry.Point { x: 20, y: 22 }\nprint(geometry.answer(point))\n';
const GEOMETRY_SOURCE = 'public record Point { x: Integer; y: Integer }\npublic function answer(point: Point): Integer { return point.x + point.y }\n';

// The UI offers this companion only after showing the untouched guide excerpt.
// An explicit user action adds both visible files; the catalog stays a fragment.
export function supportingProjectFor(example) {
  let fields;
  try {
    if (example === null || typeof example !== 'object' || Array.isArray(example)
        || ![Object.prototype, null].includes(Object.getPrototypeOf(example))) return null;
    fields = ['file', 'sourceSha256', 'source'].map(key => {
      const property = Object.getOwnPropertyDescriptor(example, key);
      return property?.enumerable && Object.hasOwn(property, 'value') && typeof property.value === 'string'
        ? property.value : null;
    });
  } catch {
    return null;
  }
  const [file, hash, source] = fields;
  if (file !== 'docs/language.md' || hash !== NAMESPACE_HASH || source !== NAMESPACE_SOURCE) return null;
  return normalizeProject({ version: 1, entry: 'main.min', files: [
    { path: 'main.min', source },
    { path: 'geometry.min', source: GEOMETRY_SOURCE },
  ] });
}
