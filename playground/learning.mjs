import { tour } from './tour.mjs';
import { guides, recordTourRun, restoreTourProgress, summarizeTourProgress, visitTourStep } from './tour-guide.mjs';

const PROGRESS_KEY = 'minyar.playground.tour.v1';

export function createLearning({ catalog, selectExample, getCurrent, getSource }) {
  const get = id => document.getElementById(id);
  const examples = new Map(tour.map(example => [example.id, example]));
  const entries = catalog?.examples ?? [];
  for (const entry of entries) examples.set(entry.id, { ...entry, description: entry.reason });
  let progress = restoreTourProgress(null);
  let mode = 'example';
  let selectedId = null;
  try { progress = restoreTourProgress(localStorage.getItem(PROGRESS_KEY)); } catch { /* Optional device storage. */ }

  function persist() {
    try { localStorage.setItem(PROGRESS_KEY, JSON.stringify(progress)); } catch { /* The lesson still works. */ }
    const counts = summarizeTourProgress(progress);
    const element = get('tour-progress');
    element.textContent = `${counts.examples} / ${counts.total} examples run · ${counts.challenges} / ${counts.total} challenges met`;
    element.dataset.examples = String(counts.examples);
    element.dataset.challenges = String(counts.challenges);
  }

  function sourceChanged() {
    const example = getCurrent();
    const changed = getSource() !== example.source;
    get('example-provenance').textContent = example.file
      ? `${example.file}:${example.line} · ${changed ? 'edited in this browser' : 'exact original source'}` : '';
    get('lesson-feedback').textContent = '';
    delete get('lesson-feedback').dataset.achieved;
  }

  function render(example) {
    if (selectedId !== example.id) mode = 'example';
    selectedId = example.id;
    const guide = guides[example.id];
    get('lesson').hidden = !guide;
    get('example-provenance').hidden = !example.file;
    sourceChanged();
    get('example-context').hidden = !example.file;
    get('example-context').textContent = example.file ? `${example.reason}${example.note ? ` ${example.note}` : ''}` : '';
    if (guide) {
      progress = visitTourStep(progress, example.id);
      get('lesson-idea').textContent = guide.idea;
      get('lesson-instruction').textContent = mode === 'challenge' ? guide.instruction : 'Run the example, then try a small change of your own.';
      get('lesson-goal').textContent = mode === 'challenge' ? guide.expected : example.expected;
      get('lesson-hint-text').textContent = guide.hint;
      get('lesson-hint-text').hidden = true;
      get('lesson-hint').setAttribute('aria-expanded', 'false');
      get('lesson-hint').hidden = mode !== 'challenge';
      get('challenge').textContent = mode === 'challenge' ? 'Challenge in progress' : 'Try a challenge';
      get('challenge').disabled = mode === 'challenge';
      get('lesson-feedback').textContent = '';
      const index = tour.findIndex(entry => entry.id === example.id);
      get('previous-example').disabled = index === 0;
      get('next-example').disabled = index === tour.length - 1;
      persist();
    }
    for (const button of get('language-list').querySelectorAll('button')) {
      if (button.dataset.exampleId === example.id) button.setAttribute('aria-current', 'true');
      else button.removeAttribute('aria-current');
    }
  }

  function filterExamples() {
    const query = get('language-search').value.trim().toLocaleLowerCase();
    let count = 0;
    for (const item of get('language-list').children) {
      const entry = examples.get(item.firstElementChild.dataset.exampleId);
      item.hidden = !`${entry.title} ${entry.headings.join(' ')} ${entry.classification} ${entry.source}`.toLocaleLowerCase().includes(query);
      if (!item.hidden) count += 1;
    }
    get('language-count').textContent = `${count} / ${entries.length} examples · ${catalog?.summary?.runnable ?? 0} standalone`;
  }

  for (const entry of entries) {
    const item = document.createElement('li');
    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.exampleId = entry.id;
    const title = document.createElement('span');
    title.textContent = entry.title;
    const context = document.createElement('span');
    context.className = 'language-example-meta';
    context.textContent = `${entry.heading} · ${entry.runnable ? 'Run as written' : entry.classification.replaceAll('-', ' ')}`;
    button.append(title, context);
    button.addEventListener('click', () => {
      selectExample(examples.get(entry.id));
      const editor = get('source');
      editor.focus({ preventScroll: true });
      get('source-heading').scrollIntoView({ block: 'start', behavior: 'auto' });
    });
    item.append(button);
    get('language-list').append(item);
  }
  get('language-search').addEventListener('input', filterExamples);
  get('challenge').addEventListener('click', () => {
    if (!guides[getCurrent().id]) return;
    mode = 'challenge';
    render(getCurrent());
    get('lesson-instruction').focus({ preventScroll: true });
  });
  get('lesson-hint').addEventListener('click', () => {
    const open = get('lesson-hint').getAttribute('aria-expanded') !== 'true';
    get('lesson-hint').setAttribute('aria-expanded', String(open));
    get('lesson-hint-text').hidden = !open;
  });
  for (const [id, direction] of [['previous-example', -1], ['next-example', 1]]) {
    get(id).addEventListener('click', () => {
      const index = tour.findIndex(entry => entry.id === getCurrent().id);
      if (index >= 0 && tour[index + direction]) selectExample(tour[index + direction]);
    });
  }
  filterExamples();
  persist();
  return {
    resolveExample: id => examples.get(id),
    render,
    sourceChanged,
    runMode: () => mode,
    reset() { mode = 'example'; },
    blocksRun: example => example.runnable === false && getSource() === example.source,
    recordRun(id, runMode, result) {
      if (!guides[id]) return;
      const before = summarizeTourProgress(progress);
      progress = recordTourRun(progress, id, runMode, result);
      const after = summarizeTourProgress(progress);
      persist();
      if (getCurrent().id !== id || mode !== runMode) return;
      const matched = result?.exitCode === 0 && Array.isArray(result.diagnostics) && !result.diagnostics.length
        && result.output === (runMode === 'challenge' ? guides[id].expected : examples.get(id).expected);
      get('lesson-feedback').textContent = matched
        ? runMode === 'challenge' ? 'Challenge met. Your output matches the goal.' : 'Example run. Your output matches the goal. Try the challenge when you’re ready.'
        : runMode === 'challenge' && result?.exitCode === 0 && !result.diagnostics?.length
          ? 'Your program ran. Compare its output with the challenge goal and try another change.' : '';
      if (after.challenges > before.challenges) get('lesson-feedback').dataset.achieved = 'true';
      else delete get('lesson-feedback').dataset.achieved;
    },
  };
}
