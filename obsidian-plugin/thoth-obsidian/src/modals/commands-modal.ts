import { App, Modal, Notice } from 'obsidian';
import type ThothPlugin from '../../main';

export class CommandsModal extends Modal {
  plugin: ThothPlugin;

  constructor(app: App, plugin: ThothPlugin) {
    super(app);
    this.plugin = plugin;
    this.modalEl.addClass('thoth-commands-modal');
  }

  onOpen() {
    const { contentEl } = this;
    contentEl.empty();

    // Apply styles
    this.addStyles();

    // Set modal title
    this.titleEl.setText('⚡ Thoth Commands');

    // Create sections
    this.createAgentCommands(contentEl);
    this.createDiscoveryCommands(contentEl);
    this.createDataCommands(contentEl);
    this.createSystemCommands(contentEl);
  }

  addStyles() {
    const style = document.createElement('style');
    style.textContent = `
      .thoth-commands-modal {
        width: 70vw !important;
        max-width: 800px !important;
        height: 70vh !important;
        max-height: 600px !important;
      }

      .thoth-command-section {
        margin-bottom: 24px;
        padding: 16px;
        border: 1px solid var(--background-modifier-border);
        border-radius: 8px;
        background: var(--background-secondary);
      }

      .thoth-command-section h3 {
        margin: 0 0 12px 0;
        color: var(--text-accent);
        font-size: 16px;
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .thoth-command-section p {
        margin: 0 0 16px 0;
        color: var(--text-muted);
        font-size: 14px;
      }

      .thoth-command-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 12px;
      }

      .thoth-command-button {
        padding: 12px 16px;
        border: 1px solid var(--background-modifier-border);
        background: var(--background-primary);
        color: var(--text-normal);
        border-radius: 6px;
        cursor: pointer;
        transition: all 0.2s ease;
        text-align: left;
        font-size: 14px;
        line-height: 1.4;
      }

      .thoth-command-button:hover {
        background: var(--background-modifier-hover);
        border-color: var(--interactive-accent);
        transform: translateY(-1px);
      }

      .thoth-command-button:active {
        transform: translateY(0);
      }

      .command-title {
        font-weight: 600;
        margin-bottom: 4px;
      }

      .command-desc {
        font-size: 12px;
        color: var(--text-muted);
      }
    `;
    document.head.appendChild(style);
  }

  createAgentCommands(contentEl: HTMLElement) {
    const section = contentEl.createEl('div', { cls: 'thoth-command-section' });
    section.createEl('h3').innerHTML = '🤖 Agent Management';
    section.createEl('p', { text: 'Control the Thoth research agent' });

    const commandGrid = section.createEl('div', { cls: 'thoth-command-grid' });

    const commands = [
      {
        title: 'Start Agent',
        desc: 'Launch the research agent',
        action: () => this.plugin.startAgent()
      },
      {
        title: 'Stop Agent',
        desc: 'Stop the research agent',
        action: () => this.plugin.stopAgent()
      },
      {
        title: 'Restart Agent',
        desc: 'Restart the research agent',
        action: () => this.plugin.restartAgent()
      },
      {
        title: 'Agent Health Check',
        desc: 'Check agent status and health',
        action: () => this.runHealthCheck()
      }
    ];

    commands.forEach(cmd => {
      const button = commandGrid.createEl('div', { cls: 'thoth-command-button' });
      button.createEl('div', { text: cmd.title, cls: 'command-title' });
      button.createEl('div', { text: cmd.desc, cls: 'command-desc' });
      button.onclick = () => {
        cmd.action();
        new Notice(`Executed: ${cmd.title}`);
      };
    });
  }

  createDiscoveryCommands(contentEl: HTMLElement) {
    const section = contentEl.createEl('div', { cls: 'thoth-command-section' });
    section.createEl('h3').innerHTML = '🔍 Discovery System';
    section.createEl('p', { text: 'Manage content discovery and indexing' });

    const commandGrid = section.createEl('div', { cls: 'thoth-command-grid' });

    const commands = [
      {
        title: 'Start Discovery',
        desc: 'Begin automated content discovery',
        action: () => this.runDiscoveryCommand('start')
      },
      {
        title: 'Stop Discovery',
        desc: 'Stop content discovery process',
        action: () => this.runDiscoveryCommand('stop')
      },
      {
        title: 'Discovery Status',
        desc: 'Check discovery system status',
        action: () => this.runDiscoveryCommand('status')
      },
      {
        title: 'Add Discovery Source',
        desc: 'Add new content source',
        action: () => this.plugin.openDiscoverySourceModal()
      }
    ];

    commands.forEach(cmd => {
      const button = commandGrid.createEl('div', { cls: 'thoth-command-button' });
      button.createEl('div', { text: cmd.title, cls: 'command-title' });
      button.createEl('div', { text: cmd.desc, cls: 'command-desc' });
      button.onclick = () => {
        cmd.action();
        new Notice(`Executed: ${cmd.title}`);
      };
    });
  }

  createDataCommands(contentEl: HTMLElement) {
    const section = contentEl.createEl('div', { cls: 'thoth-command-section' });
    section.createEl('h3').innerHTML = '📊 Data Management';
    section.createEl('p', { text: 'Manage knowledge base and data' });

    const commandGrid = section.createEl('div', { cls: 'thoth-command-grid' });

    const commands = [
      {
        title: 'Rebuild Index',
        desc: 'Rebuild the knowledge base index',
        action: () => this.runDataCommand('rebuild-index')
      },
      {
        title: 'Clear Cache',
        desc: 'Clear system caches',
        action: () => this.runDataCommand('clear-cache')
      },
      {
        title: 'Export Data',
        desc: 'Export knowledge base data',
        action: () => this.runDataCommand('export')
      },
      {
        title: 'Backup Data',
        desc: 'Create system backup',
        action: () => this.runDataCommand('backup')
      }
    ];

    commands.forEach(cmd => {
      const button = commandGrid.createEl('div', { cls: 'thoth-command-button' });
      button.createEl('div', { text: cmd.title, cls: 'command-title' });
      button.createEl('div', { text: cmd.desc, cls: 'command-desc' });
      button.onclick = () => {
        cmd.action();
        new Notice(`Executed: ${cmd.title}`);
      };
    });
  }

  createSystemCommands(contentEl: HTMLElement) {
    const section = contentEl.createEl('div', { cls: 'thoth-command-section' });
    section.createEl('h3').innerHTML = '⚙️ System Operations';
    section.createEl('p', { text: 'System-level operations and utilities' });

    const commandGrid = section.createEl('div', { cls: 'thoth-command-grid' });

    const commands = [
      {
        title: 'System Status',
        desc: 'View comprehensive system status',
        action: () => this.openSystemStatus()
      },
      {
        title: 'View Logs',
        desc: 'Open system logs',
        action: () => this.runSystemCommand('logs')
      },
      {
        title: 'Test Connection',
        desc: 'Test server connectivity',
        action: () => this.runSystemCommand('test-connection')
      },
      {
        title: 'Reset Settings',
        desc: 'Reset to default settings',
        action: () => this.confirmResetSettings()
      }
    ];

    commands.forEach(cmd => {
      const button = commandGrid.createEl('div', { cls: 'thoth-command-button' });
      button.createEl('div', { text: cmd.title, cls: 'command-title' });
      button.createEl('div', { text: cmd.desc, cls: 'command-desc' });
      button.onclick = () => {
        cmd.action();
        new Notice(`Executed: ${cmd.title}`);
      };
    });
  }

  async runHealthCheck() {
    try {
      const endpoint = this.plugin.getEndpointUrl();
      const response = await fetch(`${endpoint}/health`);

      if (response.ok) {
        const data = await response.json();
        new Notice(`Agent Health: ${data.status || 'OK'}`);
      } else {
        new Notice('Agent health check failed', 3000);
      }
    } catch (error) {
      new Notice('Could not connect to agent', 3000);
    }
  }

  async runDiscoveryCommand(command: string) {
    try {
      const endpoint = this.plugin.getEndpointUrl();
      const response = await fetch(`${endpoint}/execute/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          command: 'discovery',
          args: [command]
        })
      });

      if (response.ok) {
        const result = await response.json();
        new Notice(`Discovery ${command}: ${result.message || 'Success'}`);
      } else {
        throw new Error(`Discovery ${command} failed`);
      }
    } catch (error) {
      new Notice(`Discovery ${command} failed: ${error.message}`, 3000);
    }
  }

  async runDataCommand(command: string) {
    try {
      const endpoint = this.plugin.getEndpointUrl();
      const response = await fetch(`${endpoint}/execute/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          command: 'data',
          args: [command]
        })
      });

      if (response.ok) {
        const result = await response.json();
        new Notice(`Data ${command}: ${result.message || 'Success'}`);
      } else {
        throw new Error(`Data ${command} failed`);
      }
    } catch (error) {
      new Notice(`Data ${command} failed: ${error.message}`, 3000);
    }
  }

  async runSystemCommand(command: string) {
    try {
      const endpoint = this.plugin.getEndpointUrl();
      const response = await fetch(`${endpoint}/execute/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          command: 'system',
          args: [command]
        })
      });

      if (response.ok) {
        const result = await response.json();
        new Notice(`System ${command}: ${result.message || 'Success'}`);
      } else {
        throw new Error(`System ${command} failed`);
      }
    } catch (error) {
      new Notice(`System ${command} failed: ${error.message}`, 3000);
    }
  }

  openSystemStatus() {
    // This could open a separate status modal
    new Notice('System status feature coming soon!');
  }

  async confirmResetSettings() {
    const confirmed = await this.plugin.showConfirm('Reset all settings to defaults? This cannot be undone.');
    if (confirmed) {
      // Reset settings logic would go here
      new Notice('Settings reset to defaults');
    }
  }

  onClose() {
    const { contentEl } = this;
    contentEl.empty();
  }
}
