import { createEngine } from './engine.mjs';

let engine;
let activeId;
let queue = Promise.resolve();
self.onmessage = ({ data }) => {
  queue = queue.then(async () => {
    const { id, type, source } = data;
    activeId = id;
    try {
      engine ??= await createEngine({ progress: (message, phase) => self.postMessage({ id: activeId, type: 'progress', message, phase }) });
      const result = await engine.request(type, source);
      self.postMessage({ id, type: 'result', ...result });
    } catch (error) {
      self.postMessage({ id, type: 'error', message: error.message || String(error) });
    }
  });
};
