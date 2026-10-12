"""Select the opt-in graph runtime without changing the ordinary engine.

The shared runtime engine is rendered with the two audited ownership header
substitutions. Copying the engine is deliberately a build-time operation:
ordinary program/compiler artifacts keep the original source and no dormant
collector branches, while platform/runtime fixes have one common engine.
"""
import os
from pathlib import Path
import tempfile


def engine_source(project):
    source = (Path(project) / 'runtime/minyar_runtime.c').read_text()
    for ordinary, traced in (('minyar_rc.h', 'minyar_cycle_rc.h'),
                             ('minyar_collections.h', 'minyar_cycle_collections.h')):
        directive = '#include "' + ordinary + '"'
        if source.count(directive) != 1:
            raise ValueError('cycle runtime requires exactly one ' + directive)
        source = source.replace(directive, '#include "' + traced + '"')
    prefix = ('#define MINYAR_MAP_CYCLE_RUNTIME 1\n'
              '#if defined(__GNUC__) || defined(__clang__)\n'
              '#define MINYAR_NOINLINE __attribute__((noinline))\n'
              '#else\n#define MINYAR_NOINLINE\n#endif\n')
    return '#define MINYAR_SORT_GRAPH 1\n' + prefix + source + '\n#include "minyar_callbacks.h"\n'


def publish_engine(project, target=None):
    """Write the engine (default build/managed-graphs-engine.c) atomically, only when it changes.

    Several checks generate the same engine and include it from C fixtures;
    they may run concurrently, so readers must never see a partial file."""
    target = Path(target) if target else Path(project) / 'build/managed-graphs-engine.c'
    target.parent.mkdir(parents=True, exist_ok=True)
    data = engine_source(project).encode()
    if not target.exists() or target.read_bytes() != data:
        descriptor, temporary = tempfile.mkstemp(prefix=target.name + '.', dir=target.parent)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
        os.replace(temporary, target)
    return target


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
