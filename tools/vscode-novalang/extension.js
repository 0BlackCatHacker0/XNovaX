// NovaLang VS Code Extension
// Provides: syntax highlighting, LSP integration, format-on-save

const vscode = require('vscode');
const { LanguageClient, TransportKind } = require('vscode-languageclient/node');
const { execFileSync } = require('child_process');
const path = require('path');

let client;

function activate(context) {
    console.log('[NovaLang] Extension activating...');

    // LSP Server — use nova-lsp.exe
    const lspPath = findBinary('nova-lsp');
    if (lspPath) {
        const serverOptions = {
            run: { command: lspPath, transport: TransportKind.stdio },
            debug: { command: lspPath, transport: TransportKind.stdio }
        };

        const clientOptions = {
            documentSelector: [{ scheme: 'file', language: 'novalang' }],
        };

        client = new LanguageClient(
            'novalang',
            'NovaLang Language Server',
            serverOptions,
            clientOptions
        );
        client.start();
        console.log('[NovaLang] LSP client started');
    } else {
        console.log('[NovaLang] nova-lsp.exe not found — running without LSP');
    }

    // Format command
    const fmtPath = findBinary('nova-fmt');
    if (fmtPath) {
        const formatProvider = vscode.languages.registerDocumentFormattingEditProvider('novalang', {
            provideDocumentFormattingEdits(document) {
                try {
                    const formatted = execFileSync(fmtPath, [document.fileName], {
                        encoding: 'utf8',
                        timeout: 10000,
                    });
                    const fullRange = new vscode.Range(
                        document.positionAt(0),
                        document.positionAt(document.getText().length)
                    );
                    return [vscode.TextEdit.replace(fullRange, formatted)];
                } catch (e) {
                    console.error('[NovaLang] Format error:', e.message);
                    return [];
                }
            }
        });
        context.subscriptions.push(formatProvider);
        console.log('[NovaLang] Formatter registered');
    }

    // Run file command
    const runCommand = vscode.commands.registerCommand('novalang.run', () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor || editor.document.languageId !== 'novalang') {
            vscode.window.showWarningMessage('Open a .nova file first');
            return;
        }
        const novalang = findBinary('novalang');
        if (!novalang) {
            vscode.window.showErrorMessage('novalang.exe not found');
            return;
        }
        const terminal = vscode.window.createTerminal('NovaLang');
        terminal.show();
        terminal.sendText(`"${novalang}" "${editor.document.fileName}"`);
    });
    context.subscriptions.push(runCommand);
}

function deactivate() {
    if (client) {
        return client.stop();
    }
}

function findBinary(name) {
    const candidates = [
        path.join('C:', 'NovaX', `${name}.exe`),
        path.join(process.env.HOME || '', '.novax', 'bin', `${name}.exe`),
        `${name}.exe`,
    ];
    for (const p of candidates) {
        try {
            require('fs').accessSync(p);
            return p;
        } catch {}
    }
    return null;
}

module.exports = { activate, deactivate };
