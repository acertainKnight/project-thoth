/**
 * Settings Tab Component
 *
 * Plugin-only settings UI. Backend settings are in vault/thoth/_thoth/settings.json.
 */

import { Notice, Platform } from 'obsidian';
import { ThothSettings } from '../types/settings';

export class SettingsTabComponent {
  private containerEl: HTMLElement;
  private plugin: any;
  private settings: ThothSettings;

  constructor(containerEl: HTMLElement, plugin: any) {
    this.containerEl = containerEl;
    this.plugin = plugin;
    this.settings = plugin.settings;
  }

  render() {
    this.containerEl.empty();

    const settingsContainer = this.containerEl.createDiv({ cls: 'thoth-settings-container' });

    // Header
    const header = settingsContainer.createDiv({ cls: 'thoth-settings-header' });
    header.createEl('h2', { text: 'Thoth Plugin Settings', cls: 'thoth-settings-title' });
    header.createEl('p', {
      text: 'Plugin configuration only. Backend settings (API keys, LLM models, paths, etc.) are in vault/thoth/_thoth/settings.json',
      cls: 'thoth-settings-description'
    });

    // Connection Section
    this.renderConnectionSection(settingsContainer);

    // Letta Agent Model Section
    this.renderLettaModelSection(settingsContainer);

    // Plugin Behavior Section (desktop only)
    if (!Platform.isMobile) {
      this.renderPluginBehaviorSection(settingsContainer);
    }

    // UI Preferences Section
    this.renderUIPreferencesSection(settingsContainer);

    // Backend Settings Info
    this.renderBackendSettingsInfo(settingsContainer);

    // Save button
    const saveButton = settingsContainer.createEl('button', {
      text: 'Save Settings',
      cls: 'thoth-save-settings-btn'
    });
    saveButton.onclick = () => this.saveSettings();
  }

  private renderConnectionSection(container: HTMLElement) {
    const section = container.createDiv({ cls: 'thoth-settings-section' });
    section.createEl('h3', { text: '🔗 Connection' });

    // Remote Mode toggle
    const remoteModeRow = section.createDiv({ cls: 'thoth-setting-row' });
    remoteModeRow.createEl('label', { text: 'Remote Mode' });
    const remoteModeToggle = remoteModeRow.createEl('input', { type: 'checkbox' });
    remoteModeToggle.checked = this.settings.remoteMode;
    remoteModeToggle.onchange = () => {
      this.settings.remoteMode = remoteModeToggle.checked;
      this.render(); // Re-render to show/hide URL field
    };
    remoteModeRow.createEl('span', {
      text: 'Connect to remote server (unchecked = manage local agent on desktop)',
      cls: 'thoth-setting-description'
    });

    // Server URLs (when remote mode enabled)
    if (this.settings.remoteMode) {
      // Thoth API Endpoint
      const thothEndpointRow = section.createDiv({ cls: 'thoth-setting-row' });
      thothEndpointRow.createEl('label', { text: 'Thoth API URL' });
      const thothEndpointInput = thothEndpointRow.createEl('input', { type: 'text' });
      thothEndpointInput.value = this.settings.remoteEndpointUrl || 'http://localhost:8000';
      thothEndpointInput.placeholder = 'http://localhost:8000';
      thothEndpointInput.oninput = () => {
        this.settings.remoteEndpointUrl = thothEndpointInput.value;
      };
      thothEndpointRow.createEl('span', {
        text: 'Thoth backend server for research/discovery (e.g., http://localhost:8000)',
        cls: 'thoth-setting-description'
      });

      // Letta API Endpoint
      const lettaEndpointRow = section.createDiv({ cls: 'thoth-setting-row' });
      lettaEndpointRow.createEl('label', { text: 'Letta API URL' });
      const lettaEndpointInput = lettaEndpointRow.createEl('input', { type: 'text' });
      lettaEndpointInput.value = this.settings.lettaEndpointUrl || 'http://localhost:8284';
      lettaEndpointInput.placeholder = 'http://localhost:8284';
      lettaEndpointInput.oninput = () => {
        this.settings.lettaEndpointUrl = lettaEndpointInput.value;
      };
      lettaEndpointRow.createEl('span', {
        text: 'Letta backend server for AI agent chats (e.g., http://localhost:8284 or Tailscale URL)',
        cls: 'thoth-setting-description'
      });
    }
  }

  private renderLettaModelSection(container: HTMLElement) {
    const section = container.createDiv({ cls: 'thoth-settings-section' });
    section.createEl('h3', { text: '🤖 Letta Agent Model' });

    const description = section.createDiv({ cls: 'thoth-setting-info' });
    description.createEl('p', {
      text: 'Configure the LLM model used by your Letta research agents. Changes are applied automatically via hot-reload.',
    });

    const settingsPath = 'thoth/_thoth/settings.json';

    // Model dropdown (rendered immediately, populated async)
    const modelRow = section.createDiv({ cls: 'thoth-setting-row' });
    modelRow.createEl('label', { text: 'Agent LLM Model' });
    const modelSelect = modelRow.createEl('select', { cls: 'dropdown' });
    modelSelect.disabled = true;
    modelSelect.style.width = '100%';
    modelSelect.style.maxWidth = '500px';
    modelSelect.createEl('option', { text: 'Loading models from Letta API...', value: '' });
    modelRow.createEl('span', {
      text: 'Select from available models. Leave empty to use Letta server default.',
      cls: 'thoth-setting-description'
    });

    // Filter input for search
    const filterRow = section.createDiv({ cls: 'thoth-setting-row' });
    filterRow.createEl('label', { text: 'Filter models' });
    const filterInput = filterRow.createEl('input', {
      type: 'text',
      placeholder: 'Type to filter models by name or provider...',
      cls: 'thoth-model-filter'
    });
    filterInput.style.width = '100%';
    filterInput.style.maxWidth = '500px';
    filterInput.disabled = true;

    // Status indicator
    const statusEl = section.createDiv({ cls: 'thoth-model-status' });
    statusEl.style.marginTop = '8px';
    statusEl.style.fontSize = '12px';
    statusEl.setText('Loading...');
    statusEl.style.color = 'var(--text-muted)';

    // Save model button
    const saveModelBtn = section.createEl('button', {
      text: 'Apply Model Change',
      cls: 'thoth-save-model-btn'
    });
    saveModelBtn.style.marginTop = '8px';
    saveModelBtn.disabled = true;

    // Store models data for filtering
    let allModels: Array<{ handle: string; display_name: string; provider_name: string; context_window: number }> = [];
    let currentConfigModel = '';

    const populateDropdown = (filterText: string = '') => {
      modelSelect.empty();

      // Add default option
      modelSelect.createEl('option', {
        text: 'Server Default (configured in Letta)',
        value: ''
      });

      // Filter models
      const filtered = allModels.filter((m) => {
        if (!filterText) return true;
        const searchStr = `${m.handle} ${m.display_name} ${m.provider_name}`.toLowerCase();
        return searchStr.includes(filterText.toLowerCase());
      });

      // Group by provider
      const byProvider: Record<string, typeof allModels> = {};
      filtered.forEach((m) => {
        if (!byProvider[m.provider_name]) byProvider[m.provider_name] = [];
        byProvider[m.provider_name].push(m);
      });

      // Add optgroups
      for (const [provider, models] of Object.entries(byProvider).sort()) {
        const optgroup = document.createElement('optgroup');
        optgroup.label = provider.toUpperCase();
        models
          .sort((a, b) => a.display_name.localeCompare(b.display_name))
          .forEach((m) => {
            const option = document.createElement('option');
            option.value = m.handle;
            option.text = `${m.display_name} (${m.context_window.toLocaleString()} ctx)`;
            optgroup.appendChild(option);
          });
        modelSelect.appendChild(optgroup);
      }

      // Select current model
      modelSelect.value = currentConfigModel;

      // Update status
      if (filtered.length === allModels.length) {
        if (currentConfigModel) {
          statusEl.setText(`Current: ${currentConfigModel} | ${allModels.length} models available`);
          statusEl.style.color = 'var(--text-success)';
        } else {
          statusEl.setText(`Using server default | ${allModels.length} models available`);
          statusEl.style.color = 'var(--text-muted)';
        }
      } else {
        statusEl.setText(`Showing ${filtered.length} of ${allModels.length} models`);
        statusEl.style.color = 'var(--text-muted)';
      }
    };

    // Filter handler
    filterInput.oninput = () => {
      populateDropdown(filterInput.value.trim());
    };

    // Async: Fetch models from Letta API and load current config
    const adapter = this.plugin.app.vault.adapter;

    Promise.all([
      // Fetch models from Letta
      fetch(`${this.settings.lettaEndpointUrl}/v1/models/`)
        .then((res) => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          return res.json();
        })
        .catch((err) => {
          console.error('[Settings] Failed to fetch Letta models:', err);
          return [];
        }),
      // Read current configured model
      adapter.exists(settingsPath)
        .then((exists: boolean) => {
          if (!exists) return '';
          return adapter.read(settingsPath).then((raw: string) => {
            const backendSettings = JSON.parse(raw);
            return backendSettings?.memory?.letta?.agentModel || '';
          });
        })
        .catch((err: Error) => {
          console.warn('[Settings] Could not read backend settings:', err);
          return '';
        })
    ]).then(([models, configModel]) => {
      allModels = models;
      currentConfigModel = configModel;

      if (allModels.length === 0) {
        statusEl.setText('⚠️ Could not fetch models from Letta API — check connection');
        statusEl.style.color = 'var(--text-warning)';
        modelSelect.empty();
        modelSelect.createEl('option', { text: 'Failed to load models', value: '' });
        modelSelect.disabled = false;
        filterInput.disabled = true;
        saveModelBtn.disabled = false;
        return;
      }

      populateDropdown();
      modelSelect.disabled = false;
      filterInput.disabled = false;
      saveModelBtn.disabled = false;
    }).catch((error: Error) => {
      console.error('[Settings] Unexpected error in model loading:', error);
      statusEl.setText(`Error: ${error.message}`);
      statusEl.style.color = 'var(--text-error)';
      modelSelect.disabled = false;
      saveModelBtn.disabled = false;
    });

    // Save handler
    saveModelBtn.onclick = async () => {
      const newModel = modelSelect.value.trim();

      try {
        saveModelBtn.disabled = true;
        saveModelBtn.textContent = 'Saving...';

        // Read the latest settings from vault
        let settings: any = {};
        try {
          if (await adapter.exists(settingsPath)) {
            const raw = await adapter.read(settingsPath);
            settings = JSON.parse(raw);
          }
        } catch (readError) {
          console.warn('[Settings] Could not read settings, starting fresh:', readError);
        }

        // Ensure nested structure exists
        if (!settings.memory) settings.memory = {};
        if (!settings.memory.letta) settings.memory.letta = {};

        // Update the model
        settings.memory.letta.agentModel = newModel;

        // Write back to vault (triggers hot-reload on backend)
        await adapter.write(settingsPath, JSON.stringify(settings, null, 2));

        // Update status
        currentConfigModel = newModel;
        if (newModel) {
          statusEl.setText(`Model updated to: ${newModel}`);
          statusEl.style.color = 'var(--text-success)';
        } else {
          statusEl.setText('Cleared — using Letta server default');
          statusEl.style.color = 'var(--text-muted)';
        }

        new Notice(`Agent model ${newModel ? `set to ${newModel}` : 'reset to server default'}. Hot-reload will apply the change.`);
      } catch (error) {
        console.error('[Settings] Failed to save model:', error);
        statusEl.setText(`Error: ${(error as Error).message}`);
        statusEl.style.color = 'var(--text-error)';
        new Notice('Failed to save model setting');
      } finally {
        saveModelBtn.disabled = false;
        saveModelBtn.textContent = 'Apply Model Change';
      }
    };
  }

  private renderBackendSettingsInfo(container: HTMLElement) {
    const section = container.createDiv({ cls: 'thoth-settings-section' });
    section.createEl('h3', { text: '⚙️ Backend Configuration' });

    const info = section.createDiv({ cls: 'thoth-setting-info' });
    info.createEl('p', {
      text: 'Backend settings (API keys, LLM models, paths, discovery config, etc.) are stored separately in:',
    });

    const pathCode = info.createEl('code', {
      text: 'vault/thoth/_thoth/settings.json',
      cls: 'thoth-settings-path'
    });

    info.createEl('p', {
      text: 'Edit that file directly or use the setup wizard to configure backend settings.',
    });

    // Open settings file button (desktop only)
    if (!Platform.isMobile) {
      const openBtn = section.createEl('button', {
        text: '📝 Open Backend Settings File',
        cls: 'thoth-open-backend-settings-btn'
      });
      openBtn.onclick = () => {
        // Get vault path
        const vaultPath = (this.plugin.app.vault.adapter as any).basePath;
        const settingsPath = `${vaultPath}/thoth/_thoth/settings.json`;

        // Try to open in system editor
        const { exec } = require('child_process');
        exec(`xdg-open "${settingsPath}" || open "${settingsPath}" || start "" "${settingsPath}"`, (error: any) => {
          if (error) {
            new Notice('Could not open settings file. Open manually at: thoth/_thoth/settings.json');
          } else {
            new Notice('Opening backend settings file...');
          }
        });
      };
    }
  }

  private renderPluginBehaviorSection(container: HTMLElement) {
    const section = container.createDiv({ cls: 'thoth-settings-section' });
    section.createEl('h3', { text: '⚙️ Plugin Behavior' });

    // Auto-start agent
    const autoStartRow = section.createDiv({ cls: 'thoth-setting-row' });
    autoStartRow.createEl('label', { text: 'Auto-start Agent' });
    const autoStartToggle = autoStartRow.createEl('input', { type: 'checkbox' });
    autoStartToggle.checked = this.settings.autoStartAgent;
    autoStartToggle.onchange = () => {
      this.settings.autoStartAgent = autoStartToggle.checked;
    };
    autoStartRow.createEl('span', {
      text: 'Automatically start Thoth agent when Obsidian starts (desktop only)',
      cls: 'thoth-setting-description'
    });

    // Show status bar
    const statusBarRow = section.createDiv({ cls: 'thoth-setting-row' });
    statusBarRow.createEl('label', { text: 'Show Status Bar' });
    const statusBarToggle = statusBarRow.createEl('input', { type: 'checkbox' });
    statusBarToggle.checked = this.settings.showStatusBar;
    statusBarToggle.onchange = () => {
      this.settings.showStatusBar = statusBarToggle.checked;
    };

    // Show ribbon icon
    const ribbonRow = section.createDiv({ cls: 'thoth-setting-row' });
    ribbonRow.createEl('label', { text: 'Show Ribbon Icon' });
    const ribbonToggle = ribbonRow.createEl('input', { type: 'checkbox' });
    ribbonToggle.checked = this.settings.showRibbonIcon;
    ribbonToggle.onchange = () => {
      this.settings.showRibbonIcon = ribbonToggle.checked;
    };
  }

  private renderUIPreferencesSection(container: HTMLElement) {
    const section = container.createDiv({ cls: 'thoth-settings-section' });
    section.createEl('h3', { text: '🎨 UI Preferences' });

    // Theme
    const themeRow = section.createDiv({ cls: 'thoth-setting-row' });
    themeRow.createEl('label', { text: 'Theme' });
    const themeSelect = themeRow.createEl('select');
    ['auto', 'light', 'dark'].forEach(theme => {
      const option = themeSelect.createEl('option', { value: theme, text: theme });
      if (theme === this.settings.theme) {
        option.selected = true;
      }
    });
    themeSelect.onchange = () => {
      this.settings.theme = themeSelect.value as any;
    };

    // Compact mode
    const compactRow = section.createDiv({ cls: 'thoth-setting-row' });
    compactRow.createEl('label', { text: 'Compact Mode' });
    const compactToggle = compactRow.createEl('input', { type: 'checkbox' });
    compactToggle.checked = this.settings.compactMode;
    compactToggle.onchange = () => {
      this.settings.compactMode = compactToggle.checked;
    };

    // Enable notifications
    const notificationsRow = section.createDiv({ cls: 'thoth-setting-row' });
    notificationsRow.createEl('label', { text: 'Enable Notifications' });
    const notificationsToggle = notificationsRow.createEl('input', { type: 'checkbox' });
    notificationsToggle.checked = this.settings.enableNotifications;
    notificationsToggle.onchange = () => {
      this.settings.enableNotifications = notificationsToggle.checked;
    };
  }

  private async saveSettings() {
    try {
      await this.plugin.saveSettings();
      new Notice('Settings saved successfully!');
    } catch (error) {
      console.error('Failed to save settings:', error);
      new Notice('Failed to save settings');
    }
  }
}
