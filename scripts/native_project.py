"""Project discovery for the direct native frontend; never rewrites source."""
from pathlib import Path
import os


PLATFORMS = ('mac', 'ios', 'windows', 'linux', 'android', 'web')
IGNORED_DIRECTORIES = {'build', 'dist', 'target', 'node_modules', '__pycache__'}


def source_identity(path):
    """Return the shared logical path and optional target suffix."""
    stem = path.stem
    base, separator, platform = stem.rpartition('.')
    if separator and platform in PLATFORMS:
        return path.with_name(base + path.suffix), platform
    return path, None


def select_variants(paths, platform):
    if platform not in PLATFORMS:
        raise ValueError(f'unknown target platform: {platform}')
    groups = {}
    seen = set()
    for path in paths:
        if path in seen:
            raise ValueError(f'duplicate source file: {path}')
        seen.add(path)
        logical, variant = source_identity(path)
        groups.setdefault(logical, {})[variant] = path
    selected = []
    for logical, variants in sorted(groups.items()):
        chosen = variants.get(platform, variants.get(None))
        if chosen is not None:
            selected.append(chosen)
    return selected


def discover(root):
    """Walk project sources deterministically, excluding generated/vendor trees."""
    sources = []
    for directory, names, files in os.walk(root, followlinks=False):
        parent = Path(directory)
        # An app entry establishes a separate project, regardless of which
        # platform its entry targets. Never absorb a nested app's sources.
        if parent != root and any(source_identity(Path(name))[0].name == 'app.min'
                                  for name in files):
            names[:] = []
            continue
        names[:] = sorted(name for name in names
                          if not name.startswith('.')
                          and name not in IGNORED_DIRECTORIES
                          and not name.endswith(('.app', '.framework', '.bundle'))
                          and not (parent / name).is_symlink())
        for name in sorted(files):
            path = parent / name
            if name.startswith('.') or path.suffix not in ('.min', '.swift'):
                continue
            if path.is_symlink():
                raise ValueError(f'project source must not be a symbolic link: {path}')
            sources.append(path)
    return sources


def resolve_sources(inputs, platform):
    """Return selected original paths and an optional app project root.

    A single directory or app.min opts into project discovery. Explicit source
    lists retain their existing scope and select variants only among that list.
    """
    paths = [path.resolve(strict=True) for path in inputs]
    project = None
    if len(paths) == 1 and (paths[0].is_dir() or paths[0].name == 'app.min'):
        project = paths[0] if paths[0].is_dir() else paths[0].parent
        selected = select_variants(discover(project), platform)
        entries = [path for path in selected
                   if source_identity(path)[0] == project / 'app.min']
        if len(entries) != 1:
            raise ValueError(f'project requires app.min or app.{platform}.min at its root: {project}; '
                             'select an individual app directory or its app.min')
        selected.remove(entries[0])
        selected.insert(0, entries[0])
    else:
        if any(not path.is_file() for path in paths):
            raise ValueError('pass a single app directory, or a list of source files')
        if any(path.suffix not in ('.min', '.swift') for path in paths):
            raise ValueError('native sources must have a .min or .swift extension')
        selected = select_variants(paths, platform)
        # Keep the supplied order for explicit sources, including main.min.
        selected_set = set(selected)
        selected = [path for path in paths if path in selected_set]
    if not selected:
        raise ValueError(f'no sources for target platform {platform}')
    return selected, project
