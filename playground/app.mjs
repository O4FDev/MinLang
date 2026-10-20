import { tour } from './tour.mjs';
import { createLearning } from './learning.mjs';
import { createSharing } from './share-ui.mjs';

export const MAX_SOURCE_BYTES = 64 * 1024;
export const LIVE_CHECK_DELAY_MS = 600;
const MAX_VISIBLE_OUTPUT = 128 * 1024;
const DRAFT_KEY = 'minyar.playground.draft.v1';

export function sourceByteLength(source) {
  return new TextEncoder().encode(source).byteLength;
}

// Compiler columns count Unicode scalar values; textarea offsets count UTF-16.
export function diagnosticSelection(source, line, column, endLine, endColumn) {
  const lines = source.split('\n');
  const integer = (value, fallback) => Number.isFinite(Number(value))
    ? Math.max(1, Math.trunc(Number(value))) : fallback;
  const offset = (requestedLine, requestedColumn) => {
    const row = Math.min(lines.length, integer(requestedLine, 1));
    const prefix = lines.slice(0, row - 1).reduce((sum, text) => sum + text.length + 1, 0);
    const characters = [...lines[row - 1]];
    return prefix + characters.slice(0, integer(requestedColumn, 1) - 1).join('').length;
  };
  const start = offset(line, column);
  const end = offset(endLine ?? line, endColumn ?? column);
  return { start, end: Math.max(start, end) };
}

export function requestTimeout(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) && number >= 100 && number <= 120_000
    ? Math.trunc(number) : fallback;
}

async function initialisePlayground() {
  const get = (id) => document.getElementById(id);
  const source = get('source');
  const output = get('output');
  const outputNote = get('output-note');
  const outputPlaceholder = get('output-placeholder');
  const diagnostics = get('diagnostics');
  const diagnosticCount = get('diagnostic-count');
  const run = get('run');
  const stop = get('stop');
  const download = get('download');
  const draftState = get('draft-state');
  const lineNumbers = get('line-numbers');
  const startupTimeout = requestTimeout(document.documentElement.dataset.startupTimeoutMs, 120_000);
  const runTimeout = requestTimeout(document.documentElement.dataset.runTimeoutMs, 10_000);
  const supported = typeof Worker === 'function' && typeof WebAssembly === 'object';
  let currentExample = tour[0];
  let sourceRevision = 0;
  let nextRequestId = 0;
  let worker = null;
  let frontendIsWarm = false;
  let backendIsWarm = false;
  let activeRequest = null;
  let queuedType = null;
  let checkTimer = null;
  let saveTimer = null;
  let draftShouldPersist = true;
  let requestTimer = null;
  let lastOutputRevision = null;
  let wasmBytes = null;
  let downloadUrl = null;
  const tourButtons = new Map();
  let learning = null;
  let sharing = null;

  function customExample(program) {
    return { id: 'shared', title: 'Your program', description: 'A thought to make your own. Review the source, then run it when you’re ready.', source: program };
  }

  function status(message, state = 'ready') {
    get('status').textContent = message;
    get('status-light').dataset.state = state;
  }

  function text(value, fallback = '') {
    return typeof value === 'string' ? value : fallback;
  }

  function formatBytes(bytes) {
    return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KiB`;
  }

  function renderSourceInformation() {
    const bytes = sourceByteLength(source.value);
    const lines = source.value.split('\n').length;
    get('source-info').textContent = `${lines} ${lines === 1 ? 'line' : 'lines'} · ${formatBytes(bytes)} / 64 KiB`;
    get('source-info').parentElement.dataset.overLimit = String(bytes > MAX_SOURCE_BYTES);
    lineNumbers.textContent = Array.from({ length: lines }, (_, index) => index + 1).join('\n');
    lineNumbers.style.transform = `translateY(${-source.scrollTop}px)`;
    run.disabled = !supported || bytes > MAX_SOURCE_BYTES || learning?.blocksRun(currentExample)
      || activeRequest?.type === 'run' || queuedType === 'run';
    stop.disabled = !activeRequest && !queuedType;
    output.setAttribute('aria-busy', String(activeRequest?.type === 'run' && activeRequest.revision === sourceRevision));
    return bytes;
  }

  function discardDownload() {
    wasmBytes = null;
    if (downloadUrl) URL.revokeObjectURL(downloadUrl);
    downloadUrl = null;
    download.hidden = true;
  }

  function diagnosticNote(message, clear = false) {
    diagnostics.textContent = '';
    const paragraph = document.createElement('p');
    paragraph.className = clear ? 'diagnostics-empty diagnostics-clear' : 'diagnostics-empty';
    paragraph.textContent = message;
    diagnostics.append(paragraph);
    diagnosticCount.textContent = clear ? 'All clear' : 'Ready';
  }

  function renderDiagnostics(problems) {
    if (!problems.length) {
      diagnosticNote('No errors found. Keep going.', true);
      return;
    }
    diagnostics.textContent = '';
    diagnosticCount.textContent = `${problems.length} ${problems.length === 1 ? 'issue' : 'issues'}`;
    const list = document.createElement('ol');
    list.className = 'diagnostics-list';
    for (const problem of problems.slice(0, 50)) {
      const item = document.createElement('li');
      item.className = 'diagnostic';
      if (Number.isInteger(problem.line) && problem.line > 0) {
        const location = document.createElement('button');
        location.type = 'button';
        location.className = 'diagnostic-location';
        const column = Number.isInteger(problem.column) && problem.column > 0 ? problem.column : 1;
        location.textContent = `${text(problem.file, 'main.min')}:${problem.line}:${column}`;
        location.setAttribute('aria-label', `Go to line ${problem.line}, column ${column}`);
        location.addEventListener('click', () => {
          const selection = diagnosticSelection(source.value, problem.line, column, problem.endLine, problem.endColumn);
          source.focus();
          source.setSelectionRange(selection.start, selection.end);
        });
        item.append(location);
      }
      const message = document.createElement('p');
      message.className = 'diagnostic-message';
      message.textContent = text(problem.message, 'The compiler reported an error.');
      item.append(message);
      if (typeof problem.sourceLine === 'string' && problem.sourceLine.length) {
        const excerpt = document.createElement('pre');
        excerpt.className = 'diagnostic-source';
        excerpt.textContent = problem.sourceLine;
        item.append(excerpt);
      }
      const suggestions = Array.isArray(problem.help) ? problem.help : [problem.help];
      for (const detail of [problem.label, ...suggestions]) {
        if (typeof detail !== 'string' || !detail.length) continue;
        const help = document.createElement('p');
        help.className = 'diagnostic-help';
        help.textContent = detail;
        item.append(help);
      }
      list.append(item);
    }
    diagnostics.append(list);
    if (problems.length > 50) {
      const remaining = document.createElement('p');
      remaining.className = 'diagnostic-help';
      remaining.textContent = `${problems.length - 50} more issues. Start with the ones above.`;
      diagnostics.append(remaining);
    }
  }

  function checkSize() {
    if (renderSourceInformation() <= MAX_SOURCE_BYTES) return true;
    queuedType = null;
    renderDiagnostics([{
      message: 'This program is too large for the playground.',
      help: 'Keep the source within 64 KiB, then try again.',
    }]);
    status('This program is over the 64 KiB source limit.', 'error');
    return false;
  }

  function persistDraft() {
    clearTimeout(saveTimer);
    if (!draftShouldPersist) {
      draftState.textContent = 'Shared program · local draft kept';
      return;
    }
    if (sourceByteLength(source.value) > MAX_SOURCE_BYTES) {
      draftState.textContent = 'Over limit · draft not saved';
      return;
    }
    try {
      localStorage.setItem(DRAFT_KEY, JSON.stringify({ version: 1, exampleId: currentExample.id, source: source.value }));
      draftState.textContent = 'Saved on this device';
    } catch {
      draftState.textContent = 'Local saving unavailable';
    }
  }

  function restoreDraft() {
    try {
      const draft = JSON.parse(localStorage.getItem(DRAFT_KEY));
      if (draft?.version !== 1 || typeof draft.source !== 'string'
          || draft.source.length > MAX_SOURCE_BYTES || sourceByteLength(draft.source) > MAX_SOURCE_BYTES) return false;
      currentExample = learning.resolveExample(draft.exampleId) ?? customExample(draft.source);
      source.value = draft.source;
      return true;
    } catch {
      draftState.textContent = 'Local saving unavailable';
      return false;
    }
  }

  function renderExampleHeading() {
    const index = tour.indexOf(currentExample);
    get('example-position').textContent = index >= 0
      ? `${String(index + 1).padStart(2, '0')} / ${String(tour.length).padStart(2, '0')}`
      : currentExample.file ? 'GUIDE' : 'YOURS';
    get('example-title').textContent = currentExample.title;
    get('example-description').textContent = currentExample.description;
    for (const [id, button] of tourButtons) {
      if (id === currentExample.id) button.setAttribute('aria-current', 'step');
      else button.removeAttribute('aria-current');
    }
    learning.render(currentExample);
  }

  function destroyWorker() {
    clearTimeout(requestTimer);
    worker?.terminate();
    worker = null;
    frontendIsWarm = false;
    backendIsWarm = false;
  }

  function stopWork() {
    clearTimeout(checkTimer);
    queuedType = null;
    activeRequest = null;
    destroyWorker();
    outputPlaceholder.textContent = 'A moment of quiet.';
    outputPlaceholder.hidden = output.textContent.length > 0;
    outputNote.textContent = 'Stopped. You can edit your program or run it again.';
    diagnosticNote('Stopped before the current check or run finished.');
    status('Stopped. Ready when you are.');
    renderSourceInformation();
  }

  function workerFailure(message) {
    const staleSource = activeRequest && activeRequest.revision !== sourceRevision;
    const nextType = queuedType;
    activeRequest = null;
    queuedType = null;
    destroyWorker();
    discardDownload();
    if (staleSource) {
      if (!checkSize()) return;
      status('Your code changed. Waiting to check the latest version.');
      renderSourceInformation();
      if (nextType) startRequest(nextType);
      return;
    }
    renderDiagnostics([{
      message: 'The browser compiler could not finish.',
      help: message || 'Check that the playground assets are available, then try again.',
    }]);
    outputPlaceholder.textContent = 'Ready for another try.';
    outputPlaceholder.hidden = output.textContent.length > 0;
    outputNote.textContent = 'The task stopped. Your source is still here.';
    status('The task stopped. Try running your program again.', 'error');
    renderSourceInformation();
  }

  function formatMilliseconds(value) {
    return value < 1000 ? `${Math.round(value)} ms` : `${(value / 1000).toFixed(2)} s`;
  }

  function armRequestTimeout(request, timeout, execution = false) {
    clearTimeout(requestTimer);
    requestTimer = setTimeout(() => {
      if (activeRequest?.id !== request.id) return;
      workerFailure(execution
        ? `The program exceeded ${formatMilliseconds(timeout)} and was stopped. Check for an endless loop, then try again.`
        : `Getting ready or compiling took longer than ${formatMilliseconds(timeout)}. The worker was stopped; run again to retry.`);
    }, timeout);
  }

  function finishRequest(data) {
    const request = activeRequest;
    clearTimeout(requestTimer);
    activeRequest = null;
    frontendIsWarm = true;
    if (data.wasm instanceof Uint8Array && data.wasm.byteLength) backendIsWarm = true;
    if (request.revision === sourceRevision) {
      const problems = Array.isArray(data.diagnostics)
        ? data.diagnostics.filter((problem) => problem && typeof problem === 'object') : [];
      renderDiagnostics(problems);
      const exitCode = Number.isInteger(data.exitCode) ? data.exitCode : 1;
      if (request.type === 'run') {
        const printed = text(data.output);
        output.textContent = printed.slice(0, MAX_VISIBLE_OUTPUT);
        if (printed.length > MAX_VISIBLE_OUTPUT) output.textContent += '\n[Output display limit reached.]\n';
        outputPlaceholder.hidden = printed.length > 0;
        outputPlaceholder.textContent = problems.length ? 'A little revision,\nthen another try.' : 'Finished quietly.';
        lastOutputRevision = sourceRevision;
        outputNote.textContent = problems.length ? 'Your program needs a change before it can run.'
          : exitCode === 0 ? (printed.length ? 'Your program finished.' : 'Your program finished without printing anything.')
            : `Your program stopped with exit code ${exitCode}.`;
        if (!problems.length && exitCode === 0 && data.wasm instanceof Uint8Array && data.wasm.byteLength) {
          wasmBytes = data.wasm;
          download.hidden = false;
        }
        learning.recordRun(request.exampleId, request.lessonMode, { output: printed, diagnostics: problems, exitCode });
      }
      const timings = [];
      if (Number.isFinite(data.compileMs) && data.compileMs >= 0) timings.push(`compiled ${formatMilliseconds(data.compileMs)}`);
      if (request.type === 'run' && Number.isFinite(data.runMs) && data.runMs >= 0) timings.push(`ran ${formatMilliseconds(data.runMs)}`);
      get('timing').textContent = timings.join(' · ');
      if (problems.length) status(`${problems.length} ${problems.length === 1 ? 'issue to look at' : 'issues to look at'}. Select a location to find it.`, 'error');
      else if (exitCode !== 0) status(`The ${request.type === 'run' ? 'program' : 'check'} stopped with exit code ${exitCode}.`, 'error');
      else status(request.type === 'run' ? 'A little thought, brought to life.' : 'No errors found. Ready to run.');
    } else {
      status('Your code changed. Waiting to check the latest version.');
    }
    renderSourceInformation();
    if (queuedType) {
      const nextType = queuedType;
      queuedType = null;
      startRequest(nextType);
    }
  }

  function getWorker() {
    if (worker) return worker;
    const created = new Worker(new URL('./worker.mjs', import.meta.url), { type: 'module' });
    worker = created;
    frontendIsWarm = false;
    backendIsWarm = false;
    created.addEventListener('message', (event) => {
      if (worker !== created) return;
      const data = event.data;
      if (!data || typeof data !== 'object' || !activeRequest || data.id !== activeRequest.id) return;
      if (data.type === 'progress') {
        if (data.phase === 'running' && activeRequest.type === 'run' && !activeRequest.executionStarted) {
          activeRequest.executionStarted = true;
          armRequestTimeout(activeRequest, runTimeout, true);
          if (activeRequest.revision === sourceRevision) outputNote.textContent = 'Your program is running.';
        }
        if (activeRequest.revision === sourceRevision && typeof data.message === 'string') status(data.message.slice(0, 300), 'busy');
      } else if (data.type === 'result') {
        finishRequest(data);
      } else if (data.type === 'error') {
        workerFailure(text(data.message).slice(0, 2000));
      }
    });
    created.addEventListener('error', (event) => {
      if (worker !== created) return;
      event.preventDefault();
      workerFailure(text(event.message, 'Check that the browser compiler and its assets are available.').slice(0, 2000));
    });
    created.addEventListener('messageerror', () => {
      if (worker === created) workerFailure('The browser could not read the compiler’s response. Try again.');
    });
    return created;
  }

  function startRequest(type) {
    if (!supported || !checkSize()) return;
    if (learning.blocksRun(currentExample)) {
      diagnosticNote('This excerpt needs surrounding code. Read its context, or edit it into a complete program.');
      status('This guide excerpt is not a standalone program.');
      renderSourceInformation();
      return;
    }
    try {
      const currentWorker = getWorker();
      const isStartup = type === 'run' ? !backendIsWarm : !frontendIsWarm;
      const request = { id: ++nextRequestId, type, revision: sourceRevision, executionStarted: false,
        exampleId: currentExample.id, lessonMode: learning.runMode() };
      activeRequest = request;
      status(isStartup ? 'Getting the compiler ready…' : type === 'run' ? 'Running your program…' : 'Checking your program…', 'busy');
      diagnosticCount.textContent = 'Checking…';
      if (type === 'run') {
        discardDownload();
        output.textContent = '';
        lastOutputRevision = null;
        outputPlaceholder.hidden = false;
        outputPlaceholder.textContent = 'A thought in motion…';
        outputNote.textContent = isStartup ? 'The first run may take a moment to get ready.' : 'Your program is running.';
      }
      armRequestTimeout(request, startupTimeout);
      currentWorker.postMessage({ id: request.id, type, source: source.value });
      renderSourceInformation();
    } catch (error) {
      workerFailure(text(error?.message, 'This browser could not start the compiler worker.'));
    }
  }

  function queueRequest(type) {
    if (!supported || !checkSize()) return;
    if (type === 'run') clearTimeout(checkTimer);
    if (activeRequest) {
      if (type === 'run' || queuedType !== 'run') queuedType = type;
      status(queuedType === 'run' ? 'Run queued. Finishing the current check first…' : 'Your latest edit will be checked next…', 'busy');
      renderSourceInformation();
      return;
    }
    startRequest(type);
  }

  function sourceChanged({ save = true, check = true } = {}) {
    if (save) draftShouldPersist = true;
    sourceRevision += 1;
    sharing?.invalidate({ clearFragment: save });
    learning.sourceChanged();
    queuedType = null;
    clearTimeout(checkTimer);
    clearTimeout(saveTimer);
    discardDownload();
    get('timing').textContent = '';
    if (lastOutputRevision !== null) outputNote.textContent = 'Output from an earlier version. Run to see your changes.';
    else if (activeRequest?.type === 'run') {
      outputNote.textContent = 'Your code changed. Run again to see the latest version.';
      outputPlaceholder.textContent = 'A new thought,\nwaiting to happen.';
    }
    if (!checkSize()) {
      if (save) persistDraft();
      return;
    }
    const contextual = learning.blocksRun(currentExample);
    if (contextual) check = false;
    diagnosticNote(contextual ? 'This excerpt needs surrounding code. Read its context, or edit it into a complete program.'
      : check ? 'Waiting to check your changes…' : 'Edit your program to check it, or run it when you’re ready.');
    if (contextual) status('This guide excerpt is not a standalone program.');
    if (check && supported) {
      status(activeRequest ? 'Your changes will be checked after the current task.' : 'Checking after you finish typing…', 'busy');
      checkTimer = setTimeout(() => queueRequest('check'), LIVE_CHECK_DELAY_MS);
    }
    if (save) {
      draftState.textContent = 'Saving…';
      saveTimer = setTimeout(persistDraft, 300);
    }
  }

  function selectExample(example, reset = false) {
    if (currentExample === example && !reset) return;
    currentExample = example;
    if (reset) learning.reset();
    source.value = example.source;
    source.scrollTop = 0;
    source.scrollLeft = 0;
    output.textContent = '';
    outputPlaceholder.hidden = false;
    outputPlaceholder.textContent = 'A small thought,\nwaiting to happen.';
    outputNote.textContent = 'Choose Run code to see your program’s output.';
    lastOutputRevision = null;
    renderExampleHeading();
    sourceChanged();
    if (reset) source.focus();
  }

  // Load only the small local catalog before restoring a draft. No compiler
  // worker or toolchain asset is requested until an edit or an explicit Run.
  let catalog = null;
  try {
    const response = await fetch(new URL('./language-examples.json', import.meta.url), { signal: AbortSignal.timeout(10_000) });
    if (!response.ok) throw new Error('The language catalog could not be loaded.');
    catalog = await response.json();
  } catch {
    get('language-unavailable').hidden = false;
  }
  learning = createLearning({ catalog, selectExample, getCurrent: () => currentExample, getSource: () => source.value });
  sharing = createSharing({
    getSource: () => source.value,
    getRevision: () => sourceRevision,
    getExampleId: () => currentExample.id,
    loadShared(shared) {
      persistDraft();
      clearTimeout(checkTimer);
      clearTimeout(saveTimer);
      activeRequest = null;
      queuedType = null;
      destroyWorker();
      draftShouldPersist = false;
      currentExample = learning.resolveExample(shared.exampleId) ?? customExample(shared.source);
      learning.reset();
      source.value = shared.source;
      source.scrollTop = 0;
      source.scrollLeft = 0;
      output.textContent = '';
      outputPlaceholder.hidden = false;
      outputPlaceholder.textContent = 'A shared thought,\nwaiting to happen.';
      outputNote.textContent = 'Review the shared program, then choose Run code.';
      lastOutputRevision = null;
      renderExampleHeading();
      sourceChanged({ save: false, check: false });
      persistDraft();
      status('Shared program ready. Review it, then choose Run code.');
    },
  });

  for (const [index, example] of tour.entries()) {
    const item = document.createElement('li');
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'tour-button';
    const number = document.createElement('span');
    number.className = 'tour-number';
    number.setAttribute('aria-hidden', 'true');
    number.textContent = String(index + 1).padStart(2, '0');
    const title = document.createElement('span');
    title.textContent = example.title;
    button.append(number, title);
    button.addEventListener('click', () => selectExample(example));
    item.append(button);
    get('tour-list').append(item);
    tourButtons.set(example.id, button);
  }

  source.value = currentExample.source;
  const restored = restoreDraft();
  source.readOnly = false;
  get('share').disabled = false;
  get('reset').disabled = false;
  renderExampleHeading();
  renderSourceInformation();
  status(restored ? 'Your saved draft is ready when you are.' : 'Ready when you are.');
  if (!supported) {
    renderDiagnostics([{ message: 'This browser needs WebAssembly and Web Workers to run Minyar.', help: 'Open the playground in a browser that supports both.' }]);
    status('This browser cannot run the playground.', 'error');
  }

  source.addEventListener('input', () => sourceChanged());
  source.addEventListener('scroll', () => { lineNumbers.style.transform = `translateY(${-source.scrollTop}px)`; });
  source.addEventListener('keydown', (event) => {
    if (event.key !== 'Tab' || event.shiftKey || event.ctrlKey || event.metaKey || event.altKey) return;
    event.preventDefault();
    source.setRangeText('    ', source.selectionStart, source.selectionEnd, 'end');
    sourceChanged();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter' || !(event.ctrlKey || event.metaKey) || event.altKey || event.isComposing) return;
    event.preventDefault();
    if (!run.disabled) queueRequest('run');
  });
  run.addEventListener('click', () => queueRequest('run'));
  stop.addEventListener('click', stopWork);
  get('reset').addEventListener('click', () => selectExample(currentExample, true));
  download.addEventListener('click', () => {
    if (!wasmBytes) return;
    if (!downloadUrl) downloadUrl = URL.createObjectURL(new Blob([wasmBytes], { type: 'application/wasm' }));
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = 'main.wasm';
    link.hidden = true;
    document.body.append(link);
    link.click();
    link.remove();
  });
  window.addEventListener('pagehide', () => {
    persistDraft();
    clearTimeout(checkTimer);
    const wasWorking = Boolean(activeRequest);
    queuedType = null;
    activeRequest = null;
    destroyWorker();
    discardDownload();
    if (wasWorking) {
      status('Ready when you are.');
      diagnosticNote('Run your program to continue.');
      outputNote.textContent = 'The task stopped when you left this page. Run it again to continue.';
      outputPlaceholder.textContent = 'A small thought,\nwaiting to happen.';
    }
    renderSourceInformation();
  });
  await sharing.load();
}

if (typeof document !== 'undefined') void initialisePlayground();
