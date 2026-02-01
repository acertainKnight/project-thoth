/**
 * Settings Tab Component
 * 
 * Plugin-only settings UI. Backend settings are in vault/_thoth/settings.json.
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
      text: 'Plugin configuration only. Backend settings (API keys, LLM models, paths, etc.) are in vault/_thoth/settings.json',
      cls: 'thoth-settings-description'
    });

    // Connection Section
    this.renderConnectionSection(settingsContainer);

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

    // Server URL (when remote mode enabled)
    if (this.settings.remoteMode) {
      const endpointRow = section.createDiv({ cls: 'thoth-setting-row' });
      endpointRow.createEl('label', { text: 'Server URL' });
      const endpointInput = endpointRow.createEl('input', { type: 'text' });
      endpointInput.value = this.settings.remoteEndpointUrl || 'http://localhost:8000';
      endpointInput.placeholder = 'http://localhost:8000';
      endpointInput.oninput = () => {
        this.settings.remoteEndpointUrl = endpointInput.value;
      };
      endpointRow.createEl('span', {
        text: 'Thoth backend server URL (local: http://localhost:8000, remote: https://your-server:8284)',
        cls: 'thoth-setting-description'
      });
    }
  }

  private renderBackendSettingsInfo(container: HTMLElement) {
    const section = container.createDiv({ cls: 'thoth-settings-section' });
    section.createEl('h3', { text: '⚙️ Backend Configuration' });

    const info = section.createDiv({ cls: 'thoth-setting-info' });
    info.createEl('p', {
      text: 'Backend settings (API keys, LLM models, paths, discovery config, etc.) are stored separately in:',
    });
    
    const pathCode = info.createEl('code', {
      text: 'vault/_thoth/settings.json',
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
        const settingsPath = `${vaultPath}/_thoth/settings.json`;
        
        // Try to open in system editor
        const { exec } = require('child_process');
        exec(`xdg-open "${settingsPath}" || open "${settingsPath}" || start "" "${settingsPath}"`, (error: any) => {
          if (error) {
            new Notice('Could not open settings file. Open manually at: _thoth/settings.json');
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
