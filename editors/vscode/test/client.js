const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

async function main() {
    const commands = new Map();
    const instances = [];
    let active = 0;
    const vscode = {
        workspace: {
            createFileSystemWatcher: () => ({ dispose() {} }),
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
    const restart = commands.get('minyar.restartServer');
    await Promise.all([restart(), restart()]);
    assert.equal(active, 1);
    const pending = restart();
    await module.exports.deactivate();
    await pending;
    assert.equal(active, 0, 'deactivation left a language server running');
    assert(instances.every(instance => !instance.running));
    console.log('Minyar client command arguments, restart serialization and shutdown passed');
}

main().catch(error => { console.error(error); process.exitCode = 1; });
