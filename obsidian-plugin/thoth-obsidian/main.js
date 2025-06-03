import { Modal, Notice, Plugin, PluginSettingTab, Setting } from 'obsidian';
import { spawn } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
const DEFAULT_SETTINGS = {
    mistralKey: '',
    openrouterKey: '',
    endpointHost: 'localhost',
    endpointPort: '8000',
};
export default class ThothPlugin extends Plugin {
    constructor() {
        super(...arguments);
        this.process = null;
    }
    async onload() {
        await this.loadSettings();
        this.addSettingTab(new ThothSettingTab(this.app, this));
        this.addCommand({
            id: 'start-thoth-agent',
            name: 'Start Agent',
            callback: () => this.startAgent(),
        });
        this.addCommand({
            id: 'open-thoth-chat',
            name: 'Open Chat',
            callback: () => this.openChat(),
        });
    }
    onunload() {
        if (this.process) {
            this.process.kill();
        }
    }
    async loadSettings() {
        this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
    }
    async saveSettings() {
        await this.saveData(this.settings);
        const envPath = path.join(this.app.vault.adapter.getBasePath(), '.env');
        const lines = [
            `API_MISTRAL_KEY=${this.settings.mistralKey}`,
            `API_OPENROUTER_KEY=${this.settings.openrouterKey}`,
            `ENDPOINT_HOST=${this.settings.endpointHost}`,
            `ENDPOINT_PORT=${this.settings.endpointPort}`,
        ];
        fs.writeFileSync(envPath, lines.join('\n'), 'utf8');
    }
    startAgent() {
        if (this.process) {
            new Notice('Agent already running');
            return;
        }
        const cmd = 'thoth';
        const args = ['agent'];
        this.process = spawn(cmd, args, {
            cwd: this.app.vault.adapter.getBasePath(),
        });
        this.process.stdout.on('data', (data) => {
            console.log('thoth:', data.toString());
        });
        this.process.stderr.on('data', (data) => {
            console.error('thoth:', data.toString());
        });
        this.process.on('close', () => {
            this.process = null;
        });
        new Notice('Thoth agent started');
    }
    openChat() {
        new ChatModal(this.app, this).open();
    }
}
class ThothSettingTab extends PluginSettingTab {
    constructor(app, plugin) {
        super(app, plugin);
        this.plugin = plugin;
    }
    display() {
        const { containerEl } = this;
        containerEl.empty();
        new Setting(containerEl)
            .setName('Mistral API Key')
            .addText((text) => text
            .setPlaceholder('Enter Mistral API key')
            .setValue(this.plugin.settings.mistralKey)
            .onChange(async (value) => {
            this.plugin.settings.mistralKey = value;
            await this.plugin.saveSettings();
        }));
        new Setting(containerEl)
            .setName('OpenRouter API Key')
            .addText((text) => text
            .setPlaceholder('Enter OpenRouter API key')
            .setValue(this.plugin.settings.openrouterKey)
            .onChange(async (value) => {
            this.plugin.settings.openrouterKey = value;
            await this.plugin.saveSettings();
        }));
        new Setting(containerEl)
            .setName('Endpoint Host')
            .addText((text) => text
            .setPlaceholder('localhost')
            .setValue(this.plugin.settings.endpointHost)
            .onChange(async (value) => {
            this.plugin.settings.endpointHost = value;
            await this.plugin.saveSettings();
        }));
        new Setting(containerEl)
            .setName('Endpoint Port')
            .addText((text) => text
            .setPlaceholder('8000')
            .setValue(this.plugin.settings.endpointPort)
            .onChange(async (value) => {
            this.plugin.settings.endpointPort = value;
            await this.plugin.saveSettings();
        }));
        new Setting(containerEl)
            .setName('Start Agent')
            .addButton((btn) => btn.setButtonText('Start').onClick(() => {
            this.plugin.startAgent();
        }));
    }
}
class ChatModal extends Modal {
    constructor(app, plugin) {
        super(app);
        this.plugin = plugin;
    }
    onOpen() {
        const { contentEl } = this;
        this.outputEl = contentEl.createDiv({ cls: 'thoth-output' });
        const inputWrapper = contentEl.createDiv();
        this.inputEl = inputWrapper.createEl('input', { type: 'text' });
        inputWrapper.createEl('button', { text: 'Send' }).onclick = () => this.sendInput();
    }
    sendInput() {
        if (!this.plugin.process) {
            new Notice('Agent not running');
            return;
        }
        const text = this.inputEl.value;
        this.plugin.process.stdin.write(text + '\n');
        this.inputEl.value = '';
    }
    onClose() {
        const { contentEl } = this;
        contentEl.empty();
    }
}
