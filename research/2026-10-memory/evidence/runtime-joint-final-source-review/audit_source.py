"""Read-only source reconstruction; no compiler, native code or timing."""
from pathlib import Path
import datetime
import difflib
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
APP = ROOT / 'research/2026-10-memory/evidence/runtime-joint-final/run-xc_5g2zj'
CORE = ROOT / 'research/2026-10-memory/evidence/runtime/core-production'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def apply(data, patch):
    lines = data.decode().splitlines(True)
    pl = patch.splitlines(True)
    result, cursor, i = [], 0, 0
    while i < len(pl):
        m = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', pl[i])
        if not m:
            i += 1
            continue
        pos = int(m[1]) - 1
        assert pos >= cursor
        result += lines[cursor:pos]
        cursor, i = pos, i + 1
        removed = added = 0
        while i < len(pl) and pl[i][:1] in [' ', '+', '-'] and not pl[i].startswith(('--- ', '+++ ')):
            tag, value = pl[i][0], pl[i][1:]
            if tag in [' ', '-']:
                assert lines[cursor] == value, (cursor, pl[i])
                cursor += 1
                removed += 1
            if tag in [' ', '+']:
                result.append(value)
                added += 1
            i += 1
        assert removed == int(m[2] or 1) and added == int(m[4] or 1)
    result += lines[cursor:]
    return ''.join(result).encode()


def split_patch(patch):
    starts = [m.start() for m in re.finditer(r'^--- a/runtime/', patch, re.M)]
    result = {}
    for begin, end in zip(starts, starts[1:] + [len(patch)]):
        text = patch[begin:end]
        name = text.splitlines()[0].rsplit('/', 1)[1]
        result[name] = text
    return result


def region(data, start, end):
    a = data.index(start)
    b = data.index(end, a)
    return data[:a], data[a:b], data[b:]


def main():
    report = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'files': []}
    app = json.loads((APP / 'application.json').read_text())
    initial = json.loads((CORE / 'index.json').read_text())
    oldpatch = (CORE / 'own-production.patch').read_text()
    assert sha(oldpatch.encode()) == initial['patch_sha256']
    oldparts = split_patch(oldpatch)
    ownparts = []
    for entry in initial['files']:
        name = Path(entry['path']).name
        dirty = (CORE / 'baseline' / name).read_bytes()
        assert sha(dirty) == entry['dirty_baseline_sha256']
        pre = apply(dirty, oldparts[name])
        assert sha(pre) == entry['final_sha256']
        final = (ROOT / entry['path']).read_bytes()
        row = {'name': name, 'dirty_sha256': sha(dirty), 'pre_adoption_sha256': sha(pre), 'final_sha256': sha(final)}
        if name in ['minyar_runtime.c', 'minyar_collections.h']:
            record = next(x for x in app['files'] if x['name'] == name)
            before = (APP / 'before/runtime' / name).read_bytes()
            raw = (APP / 'raw/runtime' / name).read_bytes()
            archived_final = (APP / 'final/runtime' / name).read_bytes()
            patch = (APP / (name + '.raw.patch')).read_text()
            assert before == pre and sha(before) == record['before_sha256']
            assert apply(before, patch) == raw
            assert raw == archived_final == final and sha(raw) == record['raw_sha256'] == record['final_sha256']
            assert not (APP / (name + '.format.patch')).read_bytes()
            assert final == (ROOT / record['source']).read_bytes()
            starts = {'minyar_runtime.c': (b'MinyarText *minyar_join_texts(', b'\nstatic MINYAR_COLD MINYAR_NORETURN void invalid_utf8'),
                      'minyar_collections.h': (b'MinyarList *minyar_list_appended(', b'\n#ifdef MINYAR_BOUNDED_RC\nMINYAR_HOT')}
            before_regions = region(before, *starts[name])
            after_regions = region(final, *starts[name])
            assert before_regions[0] == after_regions[0] and before_regions[2] == after_regions[2]
            row.update(exact_raw_patch_sha256=sha(patch.encode()), reconstruction_matches=True,
                       raw_final_function_byte_equality=True, surrounding_bytes_identical=True,
                       reviewed_pristine_file_equals_live=True)
        else:
            assert final == pre
            row['unchanged_since_pre_adoption'] = True
        own = ''.join(difflib.unified_diff(dirty.decode().splitlines(True), final.decode().splitlines(True),
                                        fromfile='a/' + entry['path'], tofile='b/' + entry['path']))
        assert apply(dirty, own) == final
        ownparts.append(own)
        row['complete_own_patch_reconstruction_matches'] = True
        report['files'].append(row)
    complete = ''.join(ownparts)
    (OUT / 'independent-complete-own-production.patch').write_text(complete)
    report['independent_complete_own_patch_sha256'] = sha(complete.encode())
    others = []
    # Match unchanged companion fragments against the frozen independent review.
    frozen = ROOT / 'research/2026-10-memory/evidence/runtime-scalar-bulk-review/inputs/runtime'
    for p in sorted((APP / 'final/runtime').glob('*')):
        if p.name in ['minyar_runtime.c', 'minyar_collections.h']:
            continue
        assert p.read_bytes() == (ROOT / 'runtime' / p.name).read_bytes()
        before = frozen / p.name
        if before.exists():
            assert before.read_bytes() == p.read_bytes()
        others.append({'name': p.name, 'sha256': sha(p.read_bytes()), 'frozen_review_match': before.exists()})
    report['companion_fragments'] = others
    formatter = Path(app['files'][0]['formatter_command'][0])
    report['formatter_binary_sha256'] = sha(formatter.read_bytes())
    assert report['formatter_binary_sha256'] == app['formatter_sha256']
    report['formatter_version_scope'] = 'Saved application version stdout; executable bytes independently hashed; formatter not executed by reviewer.'
    report['compiler_binary_sha256'] = sha((ROOT / 'build/minyarc').read_bytes())
    report['compiler_source_sha256'] = sha((ROOT / 'compiler/compiler.min').read_bytes())
    report['status'] = 'passed independent source/hash reconstruction only'
    (OUT / 'independent-source-verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
