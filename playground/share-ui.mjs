import { createShareURL, decodeShareFragment, SHARE_FRAGMENT_LIMIT } from './share.mjs';

export function createSharing({ getSource, getRevision, getExampleId, loadShared }) {
  const button = document.getElementById('share');
  const field = document.getElementById('share-url');
  const message = document.getElementById('share-message');
  let navigation = 0;
  let sharing = 0;
  let clipboardTail = Promise.resolve();

  async function load() {
    const token = ++navigation;
    const revision = getRevision();
    const fragment = location.hash;
    try {
      const shared = await decodeShareFragment(fragment);
      if (navigation !== token || location.hash !== fragment || !shared) return false;
      if (getRevision() !== revision) {
        message.textContent = 'You edited the program while the link was opening. Your changes are still here.';
        return false;
      }
      loadShared(shared);
      message.textContent = 'Shared program loaded. Review it, then choose Run code. Nothing runs automatically.';
      return true;
    } catch (error) {
      if (navigation === token && location.hash === fragment) message.textContent = error.message || 'This shared link could not be opened. Your program is still here.';
      return false;
    }
  }

  button.addEventListener('click', async () => {
    const token = ++sharing;
    const revision = getRevision();
    const source = getSource();
    const exampleId = getExampleId();
    button.disabled = true;
    try {
      const base = new URL(location.origin);
      base.pathname = location.pathname;
      const url = await createShareURL(base, source,
        /^[A-Za-z0-9_-]{1,64}$/.test(exampleId ?? '') ? { exampleId } : {});
      if (token !== sharing) return;
      if (getRevision() !== revision) {
        message.textContent = 'Your program changed. Choose Share code again to make a link to the latest version.';
        return;
      }
      field.value = url;
      field.hidden = false;
      button.disabled = false;
      message.textContent = 'Link ready. Select the address below to copy it. Anyone with the link can read the source.';
      try {
        if (!navigator.clipboard?.writeText) return;
        // Preserve click order even if a permission prompt delays an earlier
        // write. A later link must be the last thing placed on the clipboard.
        const copied = clipboardTail.catch(() => {}).then(async () => {
          if (token !== sharing || getRevision() !== revision) return false;
          await navigator.clipboard.writeText(url);
          return true;
        });
        clipboardTail = copied;
        if (await copied && token === sharing && getRevision() === revision) message.textContent = 'Link copied. Anyone with the link can read the source.';
      } catch { /* A visible, selectable address is the clipboard fallback. */ }
    } catch (error) {
      if (token === sharing) message.textContent = error.message || 'This program could not be shared. Your source is still here.';
    } finally {
      if (token === sharing) button.disabled = false;
    }
  });
  field.addEventListener('click', () => field.select());
  window.addEventListener('hashchange', () => { void load(); });
  return {
    load,
    invalidate({ clearFragment = false } = {}) {
      sharing += 1;
      const hash = location.hash;
      if (clearFragment && (hash.length > SHARE_FRAGMENT_LIMIT || new URLSearchParams(hash.slice(1)).has('minyar'))) {
        const address = new URL(location.href);
        address.hash = '';
        history.replaceState(history.state, '', address.href);
        navigation += 1;
      }
      button.disabled = false;
      field.hidden = true;
      field.value = '';
      if (message.textContent) message.textContent = 'Choose Share code to make a link to this version of your program.';
    },
  };
}
