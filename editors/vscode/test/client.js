const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

async function main() {
    const commands = new Map();
    const watchers = new Map();
    const instances = [];
    let active = 0;
    const vscode = {
        workspace: {
            createFileSystemWatcher: pattern => {
                const listeners = new Map();
                const watcher = {
                    dispose() { listeners.clear(); },
                    fire: event => listeners.get(event)?.()
                };
                for (const event of ['onDidCreate', 'onDidChange', 'onDidDelete']) {
                    watcher[event] = listener => {
                        listeners.set(event, listener);
                        return { dispose: () => listeners.delete(event) };
                    };
                }
                watchers.set(pattern, watcher);
                return watcher;
            },
            getConfiguration: () => ({ get: key => key === 'executablePath' ? '/a path with spaces/minyar' : ['packages/paint/src'] }),
            onDidChangeConfiguration: () => ({ dispose() {} })
        },
        commands: { registerCommand: (name, run) => { commands.set(name, run); return { dispose() {} }; } },
        window: { showErrorMessage: message => { throw new Error(message); } }
    };
    class LanguageClient {
        constructor(id, name, server, options) {
            this.server = server;
            this.options = options;
            this.running = false;
            instances.push(this);
        }
        async start() {
            await Promise.resolve();
            this.running = true;
            active++;
            assert.equal(active, 1, 'two language servers ran at once');
        }
        async stop() {
            if (this.running) active--;
            this.running = false;
        }
    }
    const module = { exports: {} };
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../extension.js'), 'utf8'), {
        module,
        require: name => {
            if (name === 'vscode') return vscode;
            if (name === 'vscode-languageclient/node') return { LanguageClient };
            throw new Error(`unexpected module: ${name}`);
        }
    });
    await module.exports.activate({ subscriptions: [] });
    assert.equal(instances[0].server.command, '/a path with spaces/minyar');
    assert.equal(JSON.stringify(instances[0].server.args), '["lsp","--stdio"]');
    assert.equal(instances[0].options.documentSelector[0].language, 'minyar');
    assert.equal(instances[0].options.initializationOptions.libraryPaths[0], 'packages/paint/src');
    assert.equal(instances[0].options.synchronize.fileEvents, watchers.get('**/*.min'));
    const dependencies = watchers.get('**/{Minyar.toml,Minyar.lock}');
    assert(dependencies, 'project and lockfile changes must refresh package discovery');
    for (const event of ['onDidCreate', 'onDidChange', 'onDidDelete']) {
        const previous = instances.length;
        await dependencies.fire(event);
        assert.equal(instances.length, previous + 1, `${event} did not restart package discovery`);
        assert.equal(instances[previous - 1].running, false, 'old server was left running');
        assert.equal(active, 1);
    }
    const restart = commands.get('minyar.restartServer');
    await Promise.all([restart(), dependencies.fire('onDidCreate'), dependencies.fire('onDidChange')]);
    assert.equal(active, 1);
    const pending = restart();
    await module.exports.deactivate();
    await pending;
    assert.equal(active, 0, 'deactivation left a language server running');
    assert(instances.every(instance => !instance.running));
    const stopped = instances.length;
    await dependencies.fire('onDidChange');
    assert.equal(instances.length, stopped, 'a late package event restarted a deactivated extension');
    console.log('Minyar client arguments, package refresh, restart serialization and shutdown passed');
}

main().catch(error => { console.error(error); process.exitCode = 1; });
