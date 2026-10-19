const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const textmate = require('vscode-textmate');
const oniguruma = require('vscode-oniguruma');

async function main() {
    const wasm = fs.readFileSync(require.resolve('vscode-oniguruma/release/onig.wasm'));
    await oniguruma.loadWASM(wasm.buffer.slice(wasm.byteOffset, wasm.byteOffset + wasm.byteLength));
    const registry = new textmate.Registry({
        onigLib: Promise.resolve({
            createOnigScanner: patterns => new oniguruma.OnigScanner(patterns),
            createOnigString: value => new oniguruma.OnigString(value)
        }),
        loadGrammar: async scope => scope === 'source.minyar'
            ? JSON.parse(fs.readFileSync(path.join(__dirname, '../syntaxes/minyar.tmLanguage.json'), 'utf8'))
            : null
    });
    const grammar = await registry.loadGrammar('source.minyar');
    function tokenized(source) {
        let stack = textmate.INITIAL;
        return source.split('\n').map(line => {
            const result = grammar.tokenizeLine(line, stack);
            stack = result.ruleStack;
            return result.tokens.map(token => ({ text: line.slice(token.startIndex, token.endIndex), scopes: token.scopes }));
        });
    }
    function scoped(tokens, text, scope) {
        assert(tokens.some(token => token.text.includes(text) && token.scopes.some(value => value.startsWith(scope))), JSON.stringify(tokens));
    }
    const lines = tokenized('/// A little light.\npublic choice Glow<Item> { Some(value: Item); None }\nfunction Account.deposit(amount: Integer) { self.balance += amount }\nlet choice = 0xFF\nlet type = "hello \\(name + "nested \\(Integer(2))")"\nprint(42)\nlet raw = #"\\(notCode)"#\nlet poem = """\n    hello \\(name)\n    """\nlet rawPoem = #"""\n    \\(stillNotCode)\n    """#\nprint(0o755)');
    scoped(lines[0], 'A little light', 'comment.line.documentation');
    scoped(lines[1], 'choice', 'storage.type');
    scoped(lines[1], 'Glow', 'entity.name.type');
    scoped(lines[2], 'Account.deposit', 'entity.name.function');
    scoped(lines[3], '0xFF', 'constant.numeric');
    assert(!lines[3].some(token => token.text.includes('choice') && token.scopes.some(scope => scope.startsWith('storage.type'))));
    scoped(lines[4], 'name', 'meta.interpolation');
    scoped(lines[4], 'Integer', 'support.type');
    scoped(lines[5], 'print', 'support.function');
    assert(!lines[5].some(token => token.scopes.some(scope => scope.startsWith('string.'))));
    scoped(lines[6], 'notCode', 'string.quoted.double.raw');
    assert(!lines[6].some(token => token.scopes.includes('meta.interpolation.minyar')));
    scoped(lines[8], 'name', 'meta.interpolation');
    scoped(lines[11], 'stillNotCode', 'string.quoted.triple.raw');
    assert(!lines[11].some(token => token.scopes.includes('meta.interpolation.minyar')));
    scoped(lines[13], '0o755', 'constant.numeric');
    assert(!lines[13].some(token => token.scopes.some(scope => scope.startsWith('string.'))));
    const gallery = fs.readFileSync(path.join(__dirname, '../../../examples/gallery/lantern.min'), 'utf8');
    const galleryTokens = tokenized(gallery);
    scoped(galleryTokens[0], 'little light', 'comment.line.documentation');
    assert(galleryTokens.flat().some(token => token.scopes.includes('meta.interpolation.minyar')));
    registry.dispose();
    console.log('Minyar TextMate grammar passed with the real Oniguruma engine');
}

main().catch(error => { console.error(error); process.exitCode = 1; });
