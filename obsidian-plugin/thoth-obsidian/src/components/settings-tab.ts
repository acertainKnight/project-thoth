/**
 * Settings Tab Component
 *
 * Plugin-only settings UI. Backend settings are in vault/thoth/_thoth/settings.json.
 */

import { Notice, Platform } from 'obsidian';
import { PluginInstaller } from '../services/plugin-installer';
import { ThothSettings } from '../types/settings';

export class SettingsTabComponent {
  private containerEl: HTMLElement;
  private plugin: any;
  private settings: ThothSettings;
  private saveTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(containerEl: HTMLElement, plugin: any) {
    this.containerEl = containerEl;
    this.plugin = plugin;
    this.settings = plugin.settings;
  }

  private debouncedSave(): void {
    if (this.saveTimer) clearTimeout(this.saveTimer);
    this.saveTimer = setTimeout(() => this.saveSettings(), 500);
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

    // Plugin Updates Section (remote mode only)
    if (this.settings.remoteMode) {
      this.renderPluginUpdateSection(settingsContainer);
    }

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
        this.debouncedSave();
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
        this.debouncedSave();
      };
      lettaEndpointRow.createEl('span', {
        text: 'Letta backend server for AI agent chats (e.g., http://localhost:8284 or Tailscale URL)',
        cls: 'thoth-setting-description'
      });

      // API Token (multi-user mode only — leave blank for single-user)
      const tokenSection = section.createDiv({ cls: 'thoth-setting-row' });
      tokenSection.createEl('label', { text: 'API Token (Multi-User)' });
      const tokenInput = tokenSection.createEl('input', { type: 'password' });
      tokenInput.value = (this.settings as any).apiToken ?? '';
      tokenInput.placeholder = 'thoth_… (leave blank for single-user mode)';
      tokenInput.style.width = '100%';
      tokenInput.style.maxWidth = '500px';
      tokenInput.oninput = () => {
        (this.settings as any).apiToken = tokenInput.value.trim();
        this.debouncedSave();
      };
      tokenSection.createEl('span', {
        text: 'Token from your Thoth server admin. Required when connecting to a shared server.',
        cls: 'thoth-setting-description'
      });

      // Verify token button
      const verifyRow = section.createDiv({ cls: 'thoth-setting-row' });
      const verifyBtn = verifyRow.createEl('button', { text: 'Verify Token & Connection' });
      const verifyStatus = verifyRow.createEl('span', { cls: 'thoth-setting-description' });

      verifyBtn.onclick = async () => {
        const token: string = tokenInput.value.trim();
        const thothUrl = this.settings.remoteEndpointUrl.replace(/\/$/, '');

        if (!token) {
          verifyStatus.textContent = '⚠ No token entered — running in single-user mode';
          verifyStatus.style.color = 'var(--color-orange)';
          return;
        }

        verifyBtn.disabled = true;
        verifyStatus.textContent = 'Checking…';
        verifyStatus.style.color = 'var(--text-muted)';

        try {
          const response = await this.plugin.authFetch(`${thothUrl}/auth/me`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (response.ok) {
            const info = await response.json();
            verifyStatus.textContent = `✓ Connected as ${info.username}`;
            verifyStatus.style.color = 'var(--color-green)';
            (this.settings as any).apiToken = token;
            await this.saveSettings();
          } else if (response.status === 401) {
            verifyStatus.textContent = '✗ Invalid token';
            verifyStatus.style.color = 'var(--color-red)';
          } else {
            verifyStatus.textContent = `✗ Server returned ${response.status}`;
            verifyStatus.style.color = 'var(--color-red)';
          }
        } catch {
          verifyStatus.textContent = '✗ Cannot reach server';
          verifyStatus.style.color = 'var(--color-red)';
        } finally {
          verifyBtn.disabled = false;
        }
      };
    }
  }

  private renderPluginUpdateSection(container: HTMLElement) {
    const section = container.createDiv({ cls: 'thoth-settings-section' });
    section.createEl('h3', { text: '🔄 Plugin Updates' });

    const desc = section.createDiv({ cls: 'thoth-setting-info' });
    desc.createEl('p', {
      text: 'Manage plugin updates directly from here when using a remote server. ' +
            'The installer downloads the pre-built release files and applies them to your vault.',
    });

    // ── Static rows (known immediately) ──────────────────────────────────
    const currentPluginVersion = this.plugin.manifest.version;

    const makeRow = (label: string, valueText: string) => {
      const row = section.createDiv({ cls: 'thoth-setting-row' });
      row.createEl('label', { text: label });
      const val = row.createEl('span', { text: valueText, cls: 'thoth-setting-description' });
      return val;
    };

    makeRow('Current plugin:', `v${currentPluginVersion}`);

    // Async-populated rows
    const serverVersionEl = makeRow('Server version:', 'Checking…');
    const serverReqEl     = makeRow('Server requires plugin:', 'Checking…');
    const compatEl        = makeRow('Current compatibility:', 'Checking…');

    section.createEl('hr');

    const latestEl      = makeRow('Latest available:', 'Checking GitHub…');
    const updateCompatEl = makeRow('Update compatible with server:', '—');

    // ── Buttons ──────────────────────────────────────────────────────────
    const buttonRow = section.createDiv({ cls: 'thoth-setting-row' });
    buttonRow.style.gap = '10px';
    buttonRow.style.display = 'flex';
    buttonRow.style.alignItems = 'center';
    buttonRow.style.flexWrap = 'wrap';

    const checkBtn = buttonRow.createEl('button', { text: 'Check for Updates' });

    // Install button — desktop only
    let installBtn: HTMLButtonElement | null = null;
    if (!Platform.isMobile) {
      installBtn = buttonRow.createEl('button', {
        text: 'Install Update',
        cls: 'thoth-install-update-btn',
      });
      installBtn.disabled = true;
    }

    const statusEl = section.createDiv({ cls: 'thoth-model-status' });
    statusEl.style.marginTop = '8px';
    statusEl.style.fontSize = '12px';

    // State tracked across refreshes
    let latestVersion: string | null = null;
    let updateIsCompatible = false;

    // ── Core refresh logic ────────────────────────────────────────────────
    const refresh = async () => {
      checkBtn.disabled = true;
      checkBtn.textContent = 'Checking…';
      if (installBtn) installBtn.disabled = true;
      statusEl.textContent = '';

      try {
        const [compat, release] = await Promise.all([
          this.plugin.updateChecker.checkCompatibility(),
          this.plugin.updateChecker.getLatestRelease(),
        ]);

        // ── Compatibility rows ──
        if (compat) {
          serverVersionEl.textContent = `v${compat.serverVersion}`;
          serverReqEl.textContent = `≥ ${compat.minPluginVersion}`;

          if (compat.ok) {
            compatEl.textContent = '✓ Compatible';
            compatEl.style.color = 'var(--color-green)';
          } else {
            const reasons: string[] = [];
            if (!compat.pluginCompatible) {
              reasons.push(`server requires plugin ≥ ${compat.minPluginVersion}`);
            }
            if (!compat.serverCompatible) {
              reasons.push(`plugin requires server ≥ ${compat.minServerVersion}`);
            }
            compatEl.textContent = `✗ Incompatible — ${reasons.join('; ')}`;
            compatEl.style.color = 'var(--color-red)';
          }
        } else {
          serverVersionEl.textContent = '⚠ Could not reach server';
          serverVersionEl.style.color = 'var(--color-orange)';
          serverReqEl.textContent = '—';
          compatEl.textContent = '—';
        }

        // ── Latest release rows ──
        if (release) {
          const normalise = (v: string) => v.replace(/^v/, '').split('-')[0].split('+')[0];
          latestVersion = normalise(release.tag_name);
          const hasUpdate = (() => {
            const a = latestVersion.split('.').map(Number);
            const b = currentPluginVersion.split('.').map(Number);
            for (let i = 0; i < 3; i++) {
              if ((a[i] || 0) > (b[i] || 0)) return true;
              if ((a[i] || 0) < (b[i] || 0)) return false;
            }
            return false;
          })();

          if (hasUpdate) {
            latestEl.textContent = `v${latestVersion} (new)`;
            latestEl.style.color = 'var(--color-blue)';

            // Fetch the candidate release's manifest to check minServerVersion
            let candidateMinServer = '0.0.0';
            if (compat) {
              const ghManifest = await this.plugin.updateChecker.fetchGitHubManifest(latestVersion);
              candidateMinServer = ghManifest?.minServerVersion ?? '0.0.0';
            }

            const serverSatisfied = compat
              ? (() => {
                  const sv = compat.serverVersion.replace(/^v/, '').split('-')[0];
                  const req = candidateMinServer.replace(/^v/, '').split('-')[0];
                  const a = sv.split('.').map(Number);
                  const b = req.split('.').map(Number);
                  for (let i = 0; i < 3; i++) {
                    if ((a[i] || 0) > (b[i] || 0)) return true;
                    if ((a[i] || 0) < (b[i] || 0)) return false;
                  }
                  return true;
                })()
              : true; // can't verify → optimistically allow

            updateIsCompatible = serverSatisfied;

            if (serverSatisfied) {
              updateCompatEl.textContent = '✓ Yes';
              updateCompatEl.style.color = 'var(--color-green)';
            } else {
              updateCompatEl.textContent = `✗ No — update requires server ≥ ${candidateMinServer}`;
              updateCompatEl.style.color = 'var(--color-red)';
            }

            if (installBtn) {
              installBtn.textContent = `Install v${latestVersion}`;
              installBtn.disabled = !updateIsCompatible;
            }
          } else {
            latestEl.textContent = `v${latestVersion} (up to date)`;
            latestEl.style.color = 'var(--text-muted)';
            updateCompatEl.textContent = '—';
            if (installBtn) {
              installBtn.textContent = 'Install Update';
              installBtn.disabled = true;
            }
          }
        } else {
          latestEl.textContent = '⚠ Could not fetch release info';
          latestEl.style.color = 'var(--color-orange)';
        }
      } catch (err) {
        console.error('[Settings] Plugin update check error:', err);
        statusEl.textContent = `Error: ${(err as Error).message}`;
        statusEl.style.color = 'var(--color-red)';
      } finally {
        checkBtn.disabled = false;
        checkBtn.textContent = 'Check for Updates';
      }
    };

    // ── Wire up buttons ───────────────────────────────────────────────────
    checkBtn.onclick = () => refresh();

    if (installBtn) {
      installBtn.onclick = async () => {
        if (!latestVersion || !updateIsCompatible) return;

        const installer = new PluginInstaller(this.plugin);
        installBtn!.disabled = true;
        checkBtn.disabled = true;

        try {
          await installer.install(latestVersion, (msg) => {
            statusEl.textContent = msg;
            statusEl.style.color = 'var(--text-muted)';
          });
        } catch (err) {
          console.error('[Settings] Plugin install error:', err);
          statusEl.textContent = `Install failed: ${(err as Error).message}`;
          statusEl.style.color = 'var(--color-red)';
          installBtn!.disabled = false;
          checkBtn.disabled = false;
        }
      };
    }

    // Kick off initial check without blocking render
    refresh().catch(err => {
      console.error('[Settings] Initial plugin update check failed:', err);
    });
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
      this.plugin.authFetch(`${this.settings.lettaEndpointUrl}/v1/models/`)
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

    // Check for updates
    const updatesRow = section.createDiv({ cls: 'thoth-setting-row' });
    updatesRow.createEl('label', { text: 'Check for Updates' });
    const updatesToggle = updatesRow.createEl('input', { type: 'checkbox' });
    updatesToggle.checked = this.settings.checkForUpdates;
    updatesToggle.onchange = () => {
      this.settings.checkForUpdates = updatesToggle.checked;
    };
    updatesRow.createEl('span', {
      text: 'Automatically check for new stable releases daily',
      cls: 'thoth-setting-description'
    });

    // Release channel
    const channelRow = section.createDiv({ cls: 'thoth-setting-row' });
    channelRow.createEl('label', { text: 'Release Channel' });
    const channelSelect = channelRow.createEl('select');
    ['stable', 'alpha', 'nightly'].forEach(channel => {
      const option = channelSelect.createEl('option', { value: channel, text: channel });
      if (channel === this.settings.releaseChannel) {
        option.selected = true;
      }
    });
    channelSelect.onchange = () => {
      this.settings.releaseChannel = channelSelect.value as any;
    };
    channelRow.createEl('span', {
      text: 'Update checks only run for stable channel',
      cls: 'thoth-setting-description'
    });

    // Check now button
    const checkNowBtn = section.createEl('button', {
      text: 'Check for Updates Now',
      cls: 'thoth-check-update-btn'
    });
    checkNowBtn.style.marginTop = '10px';
    checkNowBtn.onclick = async () => {
      checkNowBtn.disabled = true;
      checkNowBtn.textContent = 'Checking...';
      try {
        await this.plugin.updateChecker.checkForUpdate(true);
        checkNowBtn.textContent = 'Check Complete';
        setTimeout(() => {
          checkNowBtn.disabled = false;
          checkNowBtn.textContent = 'Check for Updates Now';
        }, 2000);
      } catch (error) {
        console.error('Update check failed:', error);
        checkNowBtn.textContent = 'Check Failed';
        setTimeout(() => {
          checkNowBtn.disabled = false;
          checkNowBtn.textContent = 'Check for Updates Now';
        }, 2000);
      }
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
