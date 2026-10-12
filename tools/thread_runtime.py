from pathlib import Path
from cycle_runtime import configured_source


def source(project, runtime, cycles=False):
    project = Path(project)
    runtime = Path(runtime)
    local = runtime.parent / 'runtime.c'
    if runtime.name in ('runtime.o', 'runtime.ll') and local.is_file():
        configuration = local.read_text()
    elif runtime.name.startswith('minyar-default-runtime'):
        configuration = (project / 'runtime/minyar_default_runtime.c').read_text()
    elif runtime.name.startswith('minyar-runtime-eager'):
        configuration = '#include "minyar_runtime.c"\n'
    else:
        raise ValueError('cannot select thread memory policy for ' + str(runtime))
    if any(('#define ' + macro) in configuration for macro in
           ('MINYAR_COMPILER_ARENA', 'MINYAR_BOUNDED_HEAP', 'MINYAR_LAZY_HEAP')):
        raise ValueError('managed threads require system or eager memory profile; pools/arena are unsupported')
    if not (project / 'runtime/minyar_thread_domain.h').is_file():
        raise ValueError('checked thread runtime dependency is missing: minyar_thread_domain.h')
    if cycles:
        configuration = configured_source(project, runtime)
    return '#undef MINYAR_THREADED\n#define MINYAR_THREADED 1\n' + configuration
