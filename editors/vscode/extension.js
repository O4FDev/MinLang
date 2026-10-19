const vscode = require('vscode');
const { LanguageClient } = require('vscode-languageclient/node');

let client;
let pending = Promise.resolve();
let disposed = false;

async function activate(context) {
    disposed = false;
    const watcher = vscode.workspace.createFileSystemWatcher('**/*.min');
    context.subscriptions.push(watcher);
    const restart = async () => {
        if (disposed) return;
        if (client) await client.stop();
        if (disposed) return;
        const settings = vscode.workspace.getConfiguration('minyar');
        client = new LanguageClient('minyar', 'Minyar', {
            command: settings.get('executablePath', 'minyar'),
            args: ['lsp', '--stdio']
        }, {
            documentSelector: [{ scheme: 'file', language: 'minyar' }],
            initializationOptions: { libraryPaths: settings.get('libraryPaths', []) },
            synchronize: { fileEvents: watcher }
        });
        await client.start();
    };
    // Serialize restarts so a configuration edit cannot leave two servers.
    const enqueue = () => {
        pending = pending.then(restart, restart);
        return pending;
    };
    context.subscriptions.push(vscode.commands.registerCommand('minyar.restartServer', enqueue));
    context.subscriptions.push(vscode.workspace.onDidChangeConfiguration(event => {
        if (event.affectsConfiguration('minyar')) {
            enqueue().catch(error => vscode.window.showErrorMessage(`Minyar: ${error.message}`));
        }
    }));
    await enqueue();
}

async function deactivate() {
    disposed = true;
    await pending.catch(() => {});
    if (client) await client.stop();
    client = undefined;
}

module.exports = { activate, deactivate };
