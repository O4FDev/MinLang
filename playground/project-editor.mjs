import { normalizeProject, projectFromSource, MAX_PROJECT_BYTES, MAX_PROJECT_FILES } from './project.mjs';

// Keep edits verbatim even while they temporarily exceed the project budget.
// Only validated snapshots may be compiled, persisted or shared.
export function createProjectEditor({ source, onEdit, onSelect }) {
  const get = id => document.getElementById(id);
  let files = new Map([['main.min', '']]);
  let entry = 'main.min';
  let current = entry;
  let removed = null;
  let enabled = false;

  function snapshot() {
    return normalizeProject({ version: 1, entry,
      files: [...files].map(([path, source]) => ({ path, source })) });
  }

  function render() {
    const list = get('project-files');
    list.textContent = '';
    for (const path of [...files.keys()].sort()) {
      const button = document.createElement('button');
      button.type = 'button';
      button.disabled = !enabled;
      button.className = 'project-file';
      button.textContent = path;
      button.dataset.path = path;
      button.title = path === entry ? `${path} · program entry` : path;
      if (path === current) button.setAttribute('aria-current', 'page');
      button.addEventListener('click', () => {
        select(path);
        source.focus();
      });
      list.append(button);
    }
    get('source-filename').textContent = current;
    get('project-entry').textContent = `Run starts in ${entry}. Files are checked when imported.`;
    get('project-remove').disabled = !enabled || current === entry;
    get('project-undo').hidden = !removed;
    get('project-undo').disabled = !enabled;
    get('project-add').disabled = !enabled || files.size >= MAX_PROJECT_FILES;
    get('project-path').disabled = !enabled;
  }

  function select(path) {
    if (!files.has(path)) return false;
    if (path !== current) {
      current = path;
      source.value = files.get(path);
      source.scrollTop = 0;
      source.scrollLeft = 0;
      render();
      onSelect();
    }
    return true;
  }

  function install(project, selected = project.entry) {
    const valid = normalizeProject(project);
    entry = valid.entry;
    files = new Map(valid.files.map(file => [file.path, file.source]));
    current = files.has(selected) ? selected : entry;
    removed = null;
    source.value = files.get(current);
    get('project-message').textContent = '';
    get('project-add-controls').open = false;
    render();
  }

  function error(problem) {
    get('project-message').textContent = problem?.message || 'This project change could not be made.';
  }

  get('project-file-form').addEventListener('submit', event => {
    event.preventDefault();
    if (!enabled) return;
    const path = get('project-path').value;
    try {
      if (files.has(path)) throw new Error('A file already has that name. Choose it from the file list.');
      const next = normalizeProject({ version: 1, entry,
        files: [...files].map(([path, source]) => ({ path, source })).concat({ path, source: '' }) });
      // The model validates limits and paths before any editor state changes.
      files = new Map(next.files.map(file => [file.path, file.source]));
      removed = null;
      current = path;
      source.value = '';
      get('project-path').value = '';
      get('project-message').textContent = '';
      get('project-add-controls').open = false;
      render();
      onEdit();
      source.focus();
    } catch (problem) { error(problem); }
  });

  get('project-remove').addEventListener('click', () => {
    if (!enabled || current === entry) return;
    removed = { path: current, source: files.get(current) };
    files.delete(current);
    current = entry;
    source.value = files.get(entry);
    get('project-message').textContent = 'File removed. Choose Undo remove to bring it back.';
    render();
    onEdit();
    source.focus();
  });

  get('project-undo').addEventListener('click', () => {
    if (!enabled || !removed) return;
    try {
      const next = normalizeProject({ version: 1, entry,
        files: [...files].map(([path, source]) => ({ path, source })).concat(removed) });
      const path = removed.path;
      files = new Map(next.files.map(file => [file.path, file.source]));
      removed = null;
      current = path;
      source.value = files.get(path);
      get('project-message').textContent = 'File restored.';
      render();
      onEdit();
      source.focus();
    } catch (problem) { error(problem); }
  });

  return {
    enable() { enabled = true; render(); },
    load: install,
    loadSource(value) { install(projectFromSource(value)); },
    updateCurrent() { files.set(current, source.value); },
    snapshot,
    entrySource: () => files.get(entry),
    currentSource: () => files.get(current),
    currentPath: () => current,
    hasExtras: () => files.size > 1 || entry !== 'main.min',
    select,
    selectDiagnostic(path) {
      if (path === 'input.min' && files.size === 1 && entry === 'main.min') return select(entry);
      return typeof path === 'string' && select(path.startsWith('./') ? path.slice(2) : path);
    },
    information() {
      let bytes = 0;
      const encoder = new TextEncoder();
      for (const value of files.values()) bytes += encoder.encode(value).byteLength;
      let problem = null;
      try { snapshot(); } catch (invalid) { problem = invalid; }
      return { bytes, count: files.size, overLimit: bytes > MAX_PROJECT_BYTES, problem };
    },
  };
}
