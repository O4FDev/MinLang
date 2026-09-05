#!/usr/bin/env python3
"""Build a bounded-reuse experiment in a temporary runtime copy.

At most 32 dead blocks in each eight-byte size class up to 128 bytes are cached:
32 * sum(8,16,...,128) = 34,816 bytes maximum, excluding allocator metadata.
Reference children are destroyed before their block is cached."""
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    directory = Path(tempfile.mkdtemp(prefix='minyar-cache-prototype-'))
    (directory / 'runtime').mkdir()
    (directory / 'tests').mkdir()
    source = (ROOT / 'runtime/minyar_rc.h').read_text()
    source = source.replace('    unsigned kind = object->ownership & 7;\n',
                            '    unsigned kind = object->ownership & 7;\n    size_t total;\n')
    source = source.replace('        MinyarText *text = (MinyarText *)(object + 1);',
                            '        total = sizeof(*object) + sizeof(MinyarText);\n'
                            '        MinyarText *text = (MinyarText *)(object + 1);')
    source = source.replace('        MinyarList *list = (MinyarList *)(object + 1);',
                            '        total = sizeof(*object) + sizeof(MinyarList);\n'
                            '        MinyarList *list = (MinyarList *)(object + 1);')
    source = source.replace('#ifdef MINYAR_RC_TESTING\n        MinyarRecord *record = (MinyarRecord *)(object + 1);\n#endif',
                            '        MinyarRecord *record = (MinyarRecord *)(object + 1);\n'
                            '        total = sizeof(*object) + sizeof(*record) + (size_t)record->length * sizeof(long long);')
    source = source.replace('            MinyarRecord *record = (MinyarRecord *)(object + 1);',
                            '            MinyarRecord *record = (MinyarRecord *)(object + 1);\n'
                            '            total = sizeof(*object) + sizeof(*record) + (size_t)record->length * (sizeof(long long) + 1);')
    source = source.replace('free(object);', 'cache_free(object, total);')
    source = source.replace('RcObject *object = malloc(sizeof(*object) + size);',
                            'RcObject *object = cache_allocate(sizeof(*object) + size);')
    helper = '''
/* Disposable experiment: this code is not in the normal runtime. */
#if defined(__has_feature)
#if __has_feature(address_sanitizer)
#include <sanitizer/asan_interface.h>
#define CACHE_POISON(p, n) __asan_poison_memory_region(p, n)
#define CACHE_UNPOISON(p, n) __asan_unpoison_memory_region(p, n)
#endif
#endif
#ifndef CACHE_POISON
#define CACHE_POISON(p, n) ((void)0)
#define CACHE_UNPOISON(p, n) ((void)0)
#endif
static RcObject *cache_heads[16];
static unsigned cache_counts[16];
static RcObject *cache_allocate(size_t total) {
    if (total <= 128) {
        size_t index = (total + 7) / 8 - 1;
        RcObject *object = cache_heads[index];
        if (object) {
            CACHE_UNPOISON(object, (index + 1) * 8);
            cache_heads[index] = (RcObject *)(uintptr_t)object->ownership;
            cache_counts[index]--;
            return object;
        }
        return malloc((index + 1) * 8);
    }
    return malloc(total);
}
static void cache_free(RcObject *object, size_t total) {
    if (total <= 128) {
        size_t index = (total + 7) / 8 - 1;
        if (cache_counts[index] < 32) {
            object->ownership = (size_t)(uintptr_t)cache_heads[index];
            cache_heads[index] = object;
            cache_counts[index]++;
            CACHE_POISON(object, (index + 1) * 8);
            return;
        }
    }
    free(object);
}
'''
    source = source.replace('static void *rc_allocate_object(size_t size, unsigned kind) {',
                            helper + '\nstatic void *rc_allocate_object(size_t size, unsigned kind) {')
    (directory / 'runtime/minyar_rc.h').write_text(source)
    shutil.copyfile(ROOT / 'runtime/minyar_runtime.c', directory / 'runtime/minyar_runtime.c')
    shutil.copyfile(ROOT / 'tests/runtime-unit.c', directory / 'tests/runtime-unit.c')
    shutil.copy2(ROOT / 'build/minyarc', directory / 'minyarc')
    for name, flags in [('minyar-runtime.o', ['-O2']),
                        ('runtime-sanitize.o', ['-O1', '-g', '-fsanitize=address,undefined'])]:
        subprocess.run(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', *flags,
                        '-c', str(directory / 'runtime/minyar_runtime.c'), '-o', str(directory / name)],
                       check=True, timeout=60)
    print(directory)


if __name__ == '__main__':
    main()
