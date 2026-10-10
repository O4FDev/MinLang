"""Select the opt-in graph runtime without changing the ordinary engine.

The shared runtime engine is rendered with the two audited ownership header
substitutions. Copying the engine is deliberately a build-time operation:
ordinary program/compiler artifacts keep the original source and no dormant
collector branches, while platform/runtime fixes have one common engine.
"""
from pathlib import Path


def engine_source(project):
    source = (Path(project) / 'runtime/minyar_runtime.c').read_text()
    for ordinary, traced in (('minyar_rc.h', 'minyar_cycle_rc.h'),
                             ('minyar_collections.h', 'minyar_cycle_collections.h')):
        directive = '#include "' + ordinary + '"'
        if source.count(directive) != 1:
            raise ValueError('cycle runtime requires exactly one ' + directive)
        source = source.replace(directive, '#include "' + traced + '"')
    prefix = ('#if defined(__GNUC__) || defined(__clang__)\n'
              '#define MINYAR_NOINLINE __attribute__((noinline))\n'
              '#else\n#define MINYAR_NOINLINE\n#endif\n')
    return prefix + source + '\n#include "minyar_callbacks.h"\n'


def configured_source(project, runtime):
    project = Path(project)
    runtime = Path(runtime)
    local_configuration = runtime.parent / 'runtime.c'
    if runtime.name in ('runtime.o', 'runtime.ll') and local_configuration.is_file():
        # The launcher wrote the exact selected heap, byte cap and poll budget.
        configuration = local_configuration.read_text()
    elif runtime.name.startswith('minyar-default-runtime'):
        configuration = (project / 'runtime/minyar_default_runtime.c').read_text()
    elif runtime.name.startswith('minyar-runtime-eager'):
        configuration = '#include "minyar_runtime.c"\n'
    else:
        raise ValueError('cannot select cycle runtime policy for ' + str(runtime))
    directive = '#include "minyar_runtime.c"'
    if configuration.count(directive) != 1:
        raise ValueError('cycle runtime configuration must include the engine once')
    return configuration.replace(directive, engine_source(project))
