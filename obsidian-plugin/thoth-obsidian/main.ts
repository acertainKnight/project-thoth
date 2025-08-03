import { App, Editor, MarkdownView, Modal, Notice, Plugin, PluginSettingTab, Setting, TFile } from 'obsidian';
import { exec, spawn, ChildProcess } from 'child_process';
import { promisify } from 'util';
import * as fs from 'fs';
import * as path from 'path';

// Import modular components
import { ThothSettings, ChatMessage, ChatSession, ChatWindowState, NotificationProgress, DEFAULT_SETTINGS } from './src/types';
import { MultiChatModal, CommandsModal, InputModal, ConfirmModal } from './src/modals';
import { APIUtilities } from './src/utils/api';

const execAsync = promisify(exec);

// Types and interfaces are now imported from ./src/types/

export default class ThothPlugin extends Plugin {
  settings: ThothSettings;
  statusBarItem: HTMLElement;
  process: ChildProcess | null = null;
  isAgentRunning: boolean = false;
  isRestarting: boolean = false;
  socket: WebSocket | null = null;
  wsResolvers: Map<string, { resolve: (v: string) => void; reject: (e: Error) => void }> = new Map();

  // Performance and caching
  private requestCache: Map<string, { data: any; timestamp: number; expires: number }> = new Map();
  private requestQueue: Array<{ request: () => Promise<any>; resolve: (value: any) => void; reject: (error: any) => void }> = [];
  private isProcessingQueue: boolean = false;
  private maxConcurrentRequests: number = 3;
  private activeRequests: number = 0;
  private cacheDefaultTTL: number = 300000; // 5 minutes

  async onload() {
    await this.loadSettings();

    // Add ribbon icon for chat
    const ribbonIconEl = this.addRibbonIcon('message-circle', 'Open Thoth Chat', (evt: MouseEvent) => {
      this.openChatModal();
    });
    ribbonIconEl.addClass('thoth-ribbon-icon');

    // Add commands
    this.addCommand({
      id: 'start-thoth-agent',
      name: 'Start Thoth Agent',
      callback: () => {
        this.startAgent();
      }
    });

    this.addCommand({
      id: 'stop-thoth-agent',
      name: 'Stop Thoth Agent',
      callback: () => {
        this.stopAgent();
      }
    });

    this.addCommand({
      id: 'restart-thoth-agent',
      name: 'Restart Thoth Agent',
      callback: () => {
        this.restartAgent();
      }
    });

    this.addCommand({
      id: 'open-research-chat',
      name: 'Open Research Chat',
      callback: () => {
        this.openChatModal();
      }
    });

    // Add comprehensive command palette integration
    this.registerCommands();

    this.addCommand({
      id: 'insert-research-query',
      name: 'Insert Research Query',
      editorCallback: (editor: Editor, view: MarkdownView) => {
        const selectedText = editor.getSelection();
        if (selectedText) {
          this.performResearch(selectedText, editor);
        } else {
          new Notice('Please select text to research');
        }
      }
    });

    // Add status bar
    if (this.settings.showStatusBar) {
      this.statusBarItem = this.addStatusBarItem();
      this.updateStatusBar();

      // Make status bar clickable
      this.statusBarItem.addEventListener('click', () => {
        if (this.isRestarting) {
          new Notice('Agent is currently restarting, please wait...');
          return;
        }

        if (this.isAgentRunning) {
          this.stopAgent();
        } else {
          this.startAgent();
        }
      });
    }

    // Add settings tab
    this.addSettingTab(new ThothSettingTab(this.app, this));

    // Auto-start agent if enabled
    if (this.settings.autoStartAgent) {
      setTimeout(() => {
        this.startAgent();
      }, 2000); // Wait 2 seconds for Obsidian to fully load
    }
  }

  async loadSettings() {
    this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());

    // Auto-generate base URL if not set
    if (!this.settings.endpointBaseUrl) {
      this.settings.endpointBaseUrl = `http://${this.settings.endpointHost}:${this.settings.endpointPort}`;
    }
  }

  async saveSettings() {
    await this.saveData(this.settings);

    // Sync settings to backend if agent is running
    if (this.isAgentRunning) {
      await this.syncSettingsToBackend();
    }
  }

  async syncSettingsToBackend() {
    try {
      const endpoint = this.getEndpointUrl();
      const response = await fetch(`${endpoint}/agent/sync-settings`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(this.settings),
      });

      if (response.ok) {
        const result = await response.json();
        console.log('Settings synced to backend:', result.synced_keys);
      } else {
        console.warn('Failed to sync settings to backend:', response.statusText);
      }
    } catch (error) {
      console.warn('Could not sync settings to backend:', error);
    }
  }

  public getEndpointUrl(): string {
    if (this.settings.remoteMode && this.settings.remoteEndpointUrl) {
      return this.settings.remoteEndpointUrl.replace(/\/$/, ''); // Remove trailing slash
    }
    return `http://${this.settings.endpointHost}:${this.settings.endpointPort}`;
  }

    async startAgent(): Promise<void> {
    console.log('Thoth: startAgent called');
    console.log('Remote mode:', this.settings.remoteMode);
    console.log('Remote URL:', this.settings.remoteEndpointUrl);
    console.log('Endpoint URL:', this.getEndpointUrl());

    if (this.process && !this.settings.remoteMode) {
      new Notice('Thoth agent is already running');
      return;
    }

    // Handle remote mode - connect to existing server
    if (this.settings.remoteMode) {
      if (!this.settings.remoteEndpointUrl) {
        new Notice('Please configure remote endpoint URL in settings');
        return;
      }

      new Notice('Connecting to remote Thoth server...');

      try {
        const endpointUrl = this.getEndpointUrl();
        console.log('Testing connection to:', endpointUrl);

        // Test connection to remote server
        const response = await fetch(`${endpointUrl}/health`, {
          method: 'GET',
          headers: {
            'Accept': 'application/json',
          }
        });

        console.log('Health check response status:', response.status);

        if (response.ok) {
          const healthData = await response.json();
          console.log('Health check response:', healthData);

          this.isAgentRunning = true;
          this.updateStatusBar();
          new Notice('Connected to remote Thoth server successfully!');
          await this.connectWebSocket();

          // Sync settings to remote server
          await this.syncSettingsToBackend();
          return;
        } else {
          throw new Error(`Server responded with status: ${response.status}`);
        }
      } catch (error) {
        console.error('Failed to connect to remote server:', error);
        new Notice(`Failed to connect to remote server: ${error.message}`);
        return;
      }
    }

    // Validate settings for local mode
    if (!this.settings.mistralKey && !this.settings.openrouterKey) {
      new Notice('Please configure API keys in settings first');
      return;
    }

    // Local mode - start the process
    // Ensure .env file is up to date before starting agent
    try {
      await this.updateEnvironmentFile();
      new Notice('Configuration updated, starting Thoth agent...');
    } catch (error) {
      console.error('Failed to update environment file:', error);
      new Notice('Warning: Could not update configuration file');
    }

    try {
      const cmd = 'uv';
      const args = [
        'run',
        'python',
        '-m',
        'thoth',
        'api',
        '--host',
        this.settings.endpointHost,
        '--port',
        this.settings.endpointPort.toString()
      ];

      const env = {
        ...process.env,
        ...this.getEnvironmentVariables()
      };

      this.process = spawn(cmd, args, {
        cwd: this.settings.workspaceDirectory,
        env: env,
        stdio: ['ignore', 'pipe', 'pipe']
      });

      this.process.stdout?.on('data', (data) => {
        console.log(`Thoth stdout: ${data}`);
      });

      this.process.stderr?.on('data', (data) => {
        console.log(`Thoth stderr: ${data}`);
      });

      this.process.on('close', (code) => {
        console.log(`Thoth process exited with code ${code}`);
        this.process = null;
        this.isAgentRunning = false;
        this.updateStatusBar();

        if (code !== 0 && !this.isRestarting) {
          new Notice(`Thoth agent stopped with error code ${code}`);
        }
      });

      this.process.on('error', (error) => {
        console.error('Failed to start Thoth agent:', error);
        new Notice(`Failed to start Thoth agent: ${error.message}`);
        this.process = null;
        this.isAgentRunning = false;
        this.updateStatusBar();
      });

      // Wait a moment for the process to start
      setTimeout(async () => {
        if (this.process) {
          // Test if the server is responding
          try {
            const response = await fetch(`${this.settings.endpointBaseUrl}/health`);
              if (response.ok) {
                this.isAgentRunning = true;
                this.updateStatusBar();
              new Notice('Thoth agent started successfully!');
              await this.connectWebSocket();
              }
          } catch (error) {
            console.warn('Agent process started but server not yet responding');
            // Give it more time
            setTimeout(async () => {
              try {
                const response = await fetch(`${this.settings.endpointBaseUrl}/health`);
                if (response.ok) {
                  this.isAgentRunning = true;
                  this.updateStatusBar();
                  new Notice('Thoth agent started successfully!');
                  await this.connectWebSocket();
                } else {
                  new Notice('Thoth agent started but not responding to requests');
                }
              } catch (error) {
                new Notice('Thoth agent may have failed to start properly');
              }
            }, 5000);
          }
        }
      }, 3000);

    } catch (error) {
      console.error('Error starting Thoth agent:', error);
      new Notice(`Error starting Thoth agent: ${error.message}`);
    }
  }

  stopAgent(): void {
    if (this.settings.remoteMode) {
      // In remote mode, we just disconnect
      this.disconnectWebSocket();
      this.isAgentRunning = false;
      this.updateStatusBar();
      new Notice('Disconnected from remote Thoth server');
      return;
    }

    if (!this.process) {
      new Notice('Thoth agent is not running');
      return;
    }

    this.process.kill('SIGTERM');
    setTimeout(() => {
      if (this.process) {
        this.process.kill('SIGKILL');
      }
    }, 5000);

    this.process = null;
    this.isAgentRunning = false;
    this.disconnectWebSocket();
    this.updateStatusBar();
    new Notice('Thoth agent stopped');
  }

  async restartAgent(): Promise<void> {
    if (this.isRestarting) {
      new Notice('Agent is already restarting, please wait...');
      return;
    }

    this.isRestarting = true;
    this.updateStatusBar();

    try {
      if (this.settings.remoteMode) {
        // Remote restart via API
        new Notice('Restarting remote Thoth agent...');

        const endpoint = this.getEndpointUrl();
        const response = await fetch(`${endpoint}/agent/restart`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            update_config: true,
            new_config: {
              api_keys: {
                mistral: this.settings.mistralKey,
                openrouter: this.settings.openrouterKey,
              },
              directories: {
                workspace: this.settings.workspaceDirectory,
                notes: this.settings.obsidianDirectory,
              },
              settings: {
                endpoint_host: this.settings.endpointHost,
                endpoint_port: this.settings.endpointPort,
              }
            }
          }),
        });

        if (response.ok) {
          const result = await response.json();
          new Notice(`Remote agent restart initiated: ${result.message}`);

          // Wait for the agent to restart and become available
          await this.waitForAgentRestart();
        } else {
          throw new Error(`Remote restart failed: ${response.statusText}`);
        }
      } else {
        // Local restart
        new Notice('Restarting Thoth agent...');
        this.stopAgent();

        // Wait a moment for cleanup
        await new Promise(resolve => setTimeout(resolve, 2000));

        await this.startAgent();
      }

      new Notice('Thoth agent restarted successfully!');
    } catch (error) {
      console.error('Failed to restart agent:', error);
      new Notice(`Failed to restart agent: ${error.message}`);
    } finally {
      this.isRestarting = false;
      this.updateStatusBar();
    }
  }

  async waitForAgentRestart(): Promise<void> {
    const maxAttempts = 30; // 30 seconds max
    const interval = 1000; // 1 second intervals

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      try {
        const endpoint = this.getEndpointUrl();
        const response = await fetch(`${endpoint}/health`);

        if (response.ok) {
          this.isAgentRunning = true;
          return;
        }
      } catch (error) {
        // Expected during restart
      }

      await new Promise(resolve => setTimeout(resolve, interval));
    }

    throw new Error('Agent did not become available after restart');
  }

  async connectWebSocket(retries = 3): Promise<void> {
    const wsUrl = this.getEndpointUrl().replace(/^http/, 'ws') + '/ws/chat';

    for (let attempt = 0; attempt < retries; attempt++) {
      try {
        await new Promise<void>((resolve, reject) => {
          const ws = new WebSocket(wsUrl);
          ws.onopen = () => {
            this.socket = ws;
            ws.onclose = () => {
              this.socket = null;
            };
            ws.onmessage = (event: MessageEvent) => {
              let id: string | undefined;
              let text = event.data;
              try {
                const data = JSON.parse(event.data);
                id = data.id;
                text = data.response || event.data;
              } catch (e) {}
              if (id && this.wsResolvers.has(id)) {
                this.wsResolvers.get(id)!.resolve(text);
                this.wsResolvers.delete(id);
              }
            };
            ws.onerror = () => {
              this.wsResolvers.forEach(({ reject }) => reject(new Error('WebSocket error')));
              this.wsResolvers.clear();
            };
            resolve();
          };
          ws.onerror = () => {
            ws.close();
            reject(new Error('WebSocket error'));
          };
        });
        console.log('WebSocket connected');
        return;
      } catch (e) {
        console.warn(`WebSocket connection failed (attempt ${attempt + 1})`);
        await new Promise(r => setTimeout(r, 1000));
      }
    }
    console.warn('Unable to establish WebSocket connection');
  }

  disconnectWebSocket(): void {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
      this.wsResolvers.forEach(({ reject }) => reject(new Error('WebSocket disconnected')));
      this.wsResolvers.clear();
    }
  }

  private getEnvironmentVariables() {
    return {
      // API Keys
      API_MISTRAL_KEY: this.settings.mistralKey,
      API_OPENROUTER_KEY: this.settings.openrouterKey,
      API_OPENCITATIONS_KEY: this.settings.opencitationsKey,
      API_GOOGLE_API_KEY: this.settings.googleApiKey,
      API_GOOGLE_SEARCH_ENGINE_ID: this.settings.googleSearchEngineId,
      API_SEMANTIC_SCHOLAR_KEY: this.settings.semanticScholarKey,
      API_WEB_SEARCH_KEY: this.settings.webSearchKey,
      API_WEB_SEARCH_PROVIDERS: this.settings.webSearchProviders,

      // Directories
      WORKSPACE_DIR: this.settings.workspaceDirectory,
      NOTES_DIR: this.settings.obsidianDirectory,
      DATA_DIR: this.settings.dataDirectory,
      KNOWLEDGE_DIR: this.settings.knowledgeDirectory,
      LOGS_DIR: this.settings.logsDirectory,
      QUERIES_DIR: this.settings.queriesDirectory,
      AGENT_STORAGE_DIR: this.settings.agentStorageDirectory,
      PDF_DIR: this.settings.pdfDirectory,
      PROMPTS_DIR: this.settings.promptsDirectory || path.join(this.settings.workspaceDirectory, 'templates/prompts'),

      // Server settings
      ENDPOINT_HOST: this.settings.endpointHost,
      ENDPOINT_PORT: this.settings.endpointPort.toString(),
      ENDPOINT_BASE_URL: this.settings.endpointBaseUrl,

      // Plugin Configuration
      RESEARCH_AGENT_AUTO_START: this.settings.researchAgentAutoStart.toString(),
      RESEARCH_AGENT_DEFAULT_QUERIES: this.settings.researchAgentDefaultQueries.toString(),
      RESEARCH_AGENT_MEMORY_ENABLED: this.settings.researchAgentMemoryEnabled.toString(),
      AGENT_MAX_TOOL_CALLS: this.settings.agentMaxToolCalls.toString(),
      AGENT_TIMEOUT_SECONDS: this.settings.agentTimeoutSeconds.toString(),

      // Discovery Configuration
      DISCOVERY_AUTO_START_SCHEDULER: this.settings.discoveryAutoStartScheduler.toString(),
      DISCOVERY_DEFAULT_MAX_ARTICLES: this.settings.discoveryDefaultMaxArticles.toString(),
      DISCOVERY_DEFAULT_INTERVAL_MINUTES: this.settings.discoveryDefaultIntervalMinutes.toString(),
      DISCOVERY_RATE_LIMIT_DELAY: this.settings.discoveryRateLimitDelay.toString(),
      DISCOVERY_CHROME_EXTENSION_ENABLED: this.settings.discoveryChromeExtensionEnabled.toString(),
      DISCOVERY_CHROME_EXTENSION_PORT: this.settings.discoveryChromeExtensionPort.toString(),

      // Logging Configuration
      LOG_LEVEL: this.settings.logLevel,
      LOG_FORMAT: this.settings.logFormat,
      LOG_ROTATION: this.settings.logRotation,
      LOG_RETENTION: this.settings.logRetention,
      ENABLE_PERFORMANCE_MONITORING: this.settings.enablePerformanceMonitoring.toString(),
      METRICS_INTERVAL: this.settings.metricsInterval.toString(),

      // Security & Performance
      ENCRYPTION_KEY: this.settings.encryptionKey,
      SESSION_TIMEOUT: this.settings.sessionTimeout.toString(),
      API_RATE_LIMIT: this.settings.apiRateLimit.toString(),
      HEALTH_CHECK_TIMEOUT: this.settings.healthCheckTimeout.toString(),
      DEVELOPMENT_MODE: this.settings.developmentMode.toString(),

      // LLM Configuration
      PRIMARY_LLM_MODEL: this.settings.primaryLlmModel,
      ANALYSIS_LLM_MODEL: this.settings.analysisLlmModel,
      RESEARCH_AGENT_MODEL: this.settings.researchAgentModel,
      LLM_TEMPERATURE: this.settings.llmTemperature.toString(),
      ANALYSIS_LLM_TEMPERATURE: this.settings.analysisLlmTemperature.toString(),
      LLM_MAX_OUTPUT_TOKENS: this.settings.llmMaxOutputTokens.toString(),
      ANALYSIS_LLM_MAX_OUTPUT_TOKENS: this.settings.analysisLlmMaxOutputTokens.toString(),

      // Remote Connection
      REMOTE_MODE: this.settings.remoteMode.toString(),
      REMOTE_ENDPOINT_URL: this.settings.remoteEndpointUrl,

      // Cors Origins
      CORS_ORIGINS: this.settings.corsOrigins.join(','),
    };
  }

  private async updateEnvironmentFile(): Promise<void> {
    try {
      // Generate comprehensive .env file with all settings
      const lines = [
        '# Thoth AI Research Agent Configuration',
        '# Generated by Obsidian Plugin',
        '',
        '# ----------------------------------------------------------------------------------',
        '# --- 1. API Keys ---',
        '# ----------------------------------------------------------------------------------',
        `API_MISTRAL_KEY=${this.settings.mistralKey}`,
        `API_OPENROUTER_KEY=${this.settings.openrouterKey}`,
        `API_OPENCITATIONS_KEY=${this.settings.opencitationsKey}`,
        `API_GOOGLE_API_KEY=${this.settings.googleApiKey}`,
        `API_GOOGLE_SEARCH_ENGINE_ID=${this.settings.googleSearchEngineId}`,
        `API_SEMANTIC_SCHOLAR_KEY=${this.settings.semanticScholarKey}`,
        `API_WEB_SEARCH_KEY=${this.settings.webSearchKey}`,
        `API_WEB_SEARCH_PROVIDERS=${this.settings.webSearchProviders}`,
        '',
        '# ----------------------------------------------------------------------------------',
        '# --- 2. Directory Configuration ---',
        '# ----------------------------------------------------------------------------------',
        `WORKSPACE_DIR=${this.settings.workspaceDirectory}`,
        `NOTES_DIR=${this.settings.obsidianDirectory}`,
        `DATA_DIR=${this.settings.dataDirectory}`,
        `KNOWLEDGE_DIR=${this.settings.knowledgeDirectory}`,
        `LOGS_DIR=${this.settings.logsDirectory}`,
        `QUERIES_DIR=${this.settings.queriesDirectory}`,
        `AGENT_STORAGE_DIR=${this.settings.agentStorageDirectory}`,
        `PDF_DIR=${this.settings.pdfDirectory}`,
        `PROMPTS_DIR=${this.settings.promptsDirectory || `${this.settings.workspaceDirectory}/templates/prompts`}`,
        '',
        '# ----------------------------------------------------------------------------------',
        '# --- 3. Server Configuration ---',
        '# ----------------------------------------------------------------------------------',
        `ENDPOINT_HOST=${this.settings.endpointHost}`,
        `ENDPOINT_PORT=${this.settings.endpointPort}`,
        `ENDPOINT_BASE_URL=${this.settings.endpointBaseUrl}`,
        '',
        '# ----------------------------------------------------------------------------------',
        '# --- 4. Plugin Configuration ---',
        '# ----------------------------------------------------------------------------------',
        `# Plugin auto-start: ${this.settings.researchAgentAutoStart}`,
        `# Show status bar: ${this.settings.showStatusBar}`,
        `# Remote mode: ${this.settings.remoteMode}`,
        '',
        '# ----------------------------------------------------------------------------------',
        '# --- 5. Default Settings ---',
        '# ----------------------------------------------------------------------------------',
        'RESEARCH_AGENT_AUTO_START=false',
        'RESEARCH_AGENT_DEFAULT_QUERIES=true',
        'RESEARCH_AGENT_MEMORY_ENABLED=true',
        'AGENT_MAX_TOOL_CALLS=5',
        'AGENT_TIMEOUT_SECONDS=300',
        'LOG_LEVEL=INFO',
        'LOG_FORMAT=text',
        'LOG_ROTATION=daily',
        'LOG_RETENTION=30 days',
        'ENABLE_PERFORMANCE_MONITORING=true',
        'METRICS_INTERVAL=60',
      ];

      const envPath = path.join(this.settings.workspaceDirectory, '.env');
      await fs.promises.writeFile(envPath, lines.join('\n'));

      console.log('Environment file updated successfully');
    } catch (error) {
      console.error('Failed to update environment file:', error);
      throw error;
    }
  }

  updateStatusBar() {
    if (!this.statusBarItem) return;

    if (this.isRestarting) {
      this.statusBarItem.setText('Thoth: Restarting...');
      this.statusBarItem.style.color = '#ffa500'; // Orange
    } else if (this.isAgentRunning) {
      this.statusBarItem.setText('Thoth: Running');
      this.statusBarItem.style.color = '#00ff00'; // Green
    } else {
      this.statusBarItem.setText('Thoth: Stopped');
      this.statusBarItem.style.color = '#ff0000'; // Red
    }
  }

  async performResearch(query: string, editor: Editor) {
    if (!this.isAgentRunning) {
      new Notice('Thoth agent is not running. Please start it first.');
      return;
    }

    try {
      new Notice('Researching... This may take a moment.');

      const endpoint = this.getEndpointUrl();
      const response = await fetch(`${endpoint}/research/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: query,
          type: 'quick_research',
          max_results: 5,
          include_citations: true
        }),
      });

      if (response.ok) {
        const result = await response.json();

        // Insert the research results at the cursor position
        const cursor = editor.getCursor();
        const researchText = `\n\n## 🔍 Research: ${query}\n*Generated on ${new Date().toLocaleString()} by Thoth Research Assistant*\n\n${result.response}\n\n---\n`;

        editor.replaceRange(researchText, cursor);
        new Notice('Research completed and inserted!');
      } else {
        throw new Error(`Research request failed: ${response.statusText}`);
      }
    } catch (error) {
      console.error('Research error:', error);
      new Notice(`Research failed: ${error.message}`);
    }
  }

  private floatingChatPanel: HTMLElement | null = null;
  private chatModalInstance: MultiChatModal | null = null;
  private isMinimized: boolean = false;

  openChatModal() {
    // Platform-adaptive chat interface
    if ((this.app as any).isMobile) {
      // Mobile: Use full-screen modal
      new MultiChatModal(this.app, this).open();
    } else {
      // Desktop: Use floating panel
      // Check if floating panel already exists
      if (this.floatingChatPanel) {
        // Toggle visibility
        if (this.floatingChatPanel.style.display === 'none') {
          this.floatingChatPanel.style.display = 'flex';
        } else {
          this.floatingChatPanel.style.display = 'none';
        }
        return;
      }

      // Create floating panel for desktop
      this.createFloatingChatPanel();
    }
  }

  createFloatingChatPanel() {
    // Create floating panel
    this.floatingChatPanel = document.body.createEl('div', {
      cls: 'thoth-floating-chat-panel'
    });

    // Position and style
    this.floatingChatPanel.style.cssText = `
      position: fixed;
      bottom: 20px;
      right: 20px;
      width: 450px;
      height: 600px;
      max-width: 90vw;
      max-height: 80vh;
      z-index: 1000;
      border-radius: 12px;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
      background: var(--background-primary);
      border: 1px solid var(--background-modifier-border);
      resize: both;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      font-family: var(--font-interface);
    `;

    // Create modal instance but don't open it - just use its functionality
    this.chatModalInstance = new MultiChatModal(this.app, this);

    // Replace the modal's contentEl with our floating panel
    this.chatModalInstance.contentEl = this.floatingChatPanel;
    this.chatModalInstance.modalEl = this.floatingChatPanel;

    // Initialize the modal's content in our floating panel
    this.initializeFloatingPanel();
  }

  async initializeFloatingPanel() {
    if (!this.chatModalInstance || !this.floatingChatPanel) return;

    // Add title bar with minimize and close buttons
    const titleBar = this.floatingChatPanel.createEl('div', { cls: 'thoth-title-bar' });

    const titleText = titleBar.createEl('span', { text: '🧠 Thoth Chat' });
    titleText.style.flexGrow = '1';

    titleBar.style.cssText = `
      padding: 10px 15px;
      background: var(--background-secondary);
      border-bottom: 1px solid var(--background-modifier-border);
      border-radius: 12px 12px 0 0;
      cursor: move;
      user-select: none;
      font-weight: 600;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-shrink: 0;
      gap: 8px;
    `;

    // Button container
    const buttonContainer = titleBar.createEl('div');
    buttonContainer.style.cssText = `
      display: flex;
      gap: 4px;
      align-items: center;
    `;

    // Add minimize button
    const minimizeBtn = buttonContainer.createEl('button', { text: '_' });
    minimizeBtn.addClass('thoth-minimize-btn');
    minimizeBtn.title = 'Minimize';
    minimizeBtn.style.cssText = `
      background: none;
      border: none;
      font-size: 16px;
      cursor: pointer;
      color: var(--text-muted);
      padding: 0;
      width: 24px;
      height: 24px;
      font-weight: bold;
    `;
    minimizeBtn.onclick = () => this.toggleMinimize();

    // Add close button
    const closeBtn = buttonContainer.createEl('button', { text: '×' });
    closeBtn.style.cssText = `
      background: none;
      border: none;
      font-size: 18px;
      cursor: pointer;
      color: var(--text-muted);
      padding: 0;
      width: 24px;
      height: 24px;
    `;
    closeBtn.onclick = () => this.closeFloatingPanel();

    // Content area for the modal content
    const contentArea = this.floatingChatPanel.createEl('div', { cls: 'thoth-panel-content' });
    contentArea.style.cssText = `
      flex: 1;
      display: flex;
      flex-direction: column;
      min-height: 0;
      overflow: hidden;
    `;

    // Now use the content area as the modal's contentEl
    this.chatModalInstance.contentEl = contentArea;

    // Initialize the modal content
    await this.chatModalInstance.onOpen();

    // Make draggable
    this.makeFloatingPanelDraggable();
  }

  toggleMinimize() {
    if (!this.floatingChatPanel) return;

    this.isMinimized = !this.isMinimized;

    if (this.isMinimized) {
      this.minimizePanel();
    } else {
      this.restorePanel();
    }
  }

  minimizePanel() {
    if (!this.floatingChatPanel) return;

    // Store original dimensions
    const originalWidth = this.floatingChatPanel.style.width || '450px';
    const originalHeight = this.floatingChatPanel.style.height || '600px';
    this.floatingChatPanel.dataset.originalWidth = originalWidth;
    this.floatingChatPanel.dataset.originalHeight = originalHeight;

    // Hide the main content
    const contentArea = this.floatingChatPanel.querySelector('.thoth-panel-content') as HTMLElement;
    if (contentArea) {
      contentArea.style.display = 'none';
    }

    // Create minimized view
    const minimizedContent = this.floatingChatPanel.createEl('div', { cls: 'thoth-minimized-content' });
    minimizedContent.style.cssText = `
      flex: 1;
      display: flex;
      flex-direction: column;
      padding: 12px;
      gap: 8px;
      min-height: 0;
    `;

    // Create quick response area (last message if any)
    const responseArea = minimizedContent.createEl('div', { cls: 'quick-response' });
    responseArea.style.cssText = `
      flex: 1;
      background: var(--background-secondary);
      border-radius: 6px;
      padding: 8px;
      font-size: 12px;
      overflow-y: auto;
      max-height: 60px;
      color: var(--text-muted);
      border: 1px solid var(--background-modifier-border);
    `;

    // Get last assistant message
    const lastMessage = this.getLastAssistantMessage();
    if (lastMessage) {
      responseArea.textContent = lastMessage.length > 150 ? lastMessage.substring(0, 150) + '...' : lastMessage;
    } else {
      responseArea.textContent = 'Ask me anything... ';
      responseArea.style.fontStyle = 'italic';
    }

    // Create quick input
    const quickInput = minimizedContent.createEl('div', { cls: 'quick-input-area' });
    quickInput.style.cssText = `
      display: flex;
      gap: 6px;
      align-items: flex-end;
    `;

    const inputEl = quickInput.createEl('textarea', {
      placeholder: 'Quick question...'
    }) as HTMLTextAreaElement;
    inputEl.style.cssText = `
      flex: 1;
      min-height: 32px;
      max-height: 60px;
      resize: vertical;
      padding: 6px 8px;
      border-radius: 6px;
      border: 1px solid var(--background-modifier-border);
      background: var(--background-primary);
      font-size: 12px;
      line-height: 1.3;
    `;

    const sendBtn = quickInput.createEl('button', { text: 'Ask' });
    sendBtn.style.cssText = `
      padding: 6px 12px;
      background: var(--interactive-accent);
      color: var(--text-on-accent);
      border: none;
      border-radius: 6px;
      cursor: pointer;
      height: fit-content;
      font-size: 12px;
      font-weight: 500;
      min-height: 32px;
    `;

    // Handle quick message sending
    const sendQuickMessage = async () => {
      const message = inputEl.value.trim();
      if (!message || sendBtn.disabled) return;

      // Show user message in response area
      responseArea.textContent = `You: ${message}`;
      responseArea.style.fontStyle = 'normal';
      inputEl.value = '';

      // Disable send button
      sendBtn.disabled = true;
      sendBtn.textContent = 'Asking...';

      try {
        // Use the chat modal instance to send message
        if (this.chatModalInstance && this.chatModalInstance.activeSessionId) {
          // Send to server using existing chat functionality
          const endpoint = this.getEndpointUrl();
          const response = await fetch(`${endpoint}/research/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              message: message,
              conversation_id: this.chatModalInstance.activeSessionId,
              timestamp: Date.now(),
              id: crypto.randomUUID()
            })
          });

          if (response.ok) {
            const result = await response.json();
            const assistantResponse = result.response;

            // Show response
            responseArea.textContent = assistantResponse.length > 150 ?
              assistantResponse.substring(0, 150) + '...' : assistantResponse;

            // Update full chat in background
            if (this.chatModalInstance) {
              await this.chatModalInstance.loadChatSessions();
              this.chatModalInstance.renderSessionList();
            }
          } else {
            throw new Error('Failed to send message');
          }
        } else {
          throw new Error('No active chat session');
        }
      } catch (error) {
        console.error('Quick chat error:', error);
        responseArea.textContent = `Error: ${error.message}`;
      } finally {
        sendBtn.disabled = false;
        sendBtn.textContent = 'Ask';
        inputEl.focus();
      }
    };

    sendBtn.onclick = sendQuickMessage;
    inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendQuickMessage();
      }
    });

    // Change panel size for minimized view
    this.floatingChatPanel.style.width = '400px';
    this.floatingChatPanel.style.height = '160px';
    this.floatingChatPanel.style.resize = 'horizontal';

    // Update minimize button
    const minimizeBtn = this.floatingChatPanel.querySelector('.thoth-minimize-btn') as HTMLButtonElement;
    if (minimizeBtn) {
      minimizeBtn.textContent = '□';
      minimizeBtn.title = 'Restore';
    }

    // Focus input
    setTimeout(() => inputEl.focus(), 100);
  }

  restorePanel() {
    if (!this.floatingChatPanel) return;

    // Remove minimized content
    const minimizedContent = this.floatingChatPanel.querySelector('.thoth-minimized-content');
    if (minimizedContent) {
      minimizedContent.remove();
    }

    // Show the main content
    const contentArea = this.floatingChatPanel.querySelector('.thoth-panel-content') as HTMLElement;
    if (contentArea) {
      contentArea.style.display = 'flex';
    }

    // Restore original dimensions
    const originalWidth = this.floatingChatPanel.dataset.originalWidth || '450px';
    const originalHeight = this.floatingChatPanel.dataset.originalHeight || '600px';
    this.floatingChatPanel.style.width = originalWidth;
    this.floatingChatPanel.style.height = originalHeight;
    this.floatingChatPanel.style.resize = 'both';

    // Update minimize button
    const minimizeBtn = this.floatingChatPanel.querySelector('.thoth-minimize-btn') as HTMLButtonElement;
    if (minimizeBtn) {
      minimizeBtn.textContent = '_';
      minimizeBtn.title = 'Minimize';
    }
  }

  getLastAssistantMessage(): string | null {
    // Try to get the last assistant message from the current session
    if (this.chatModalInstance && this.chatModalInstance.activeSessionId) {
      // This is a simplified version - in a full implementation, you'd access the actual messages
      return null; // For now, return null - can be enhanced later
    }
    return null;
  }

  closeFloatingPanel() {
    if (this.floatingChatPanel) {
      this.floatingChatPanel.remove();
      this.floatingChatPanel = null;
    }
    if (this.chatModalInstance) {
      this.chatModalInstance.onClose();
      this.chatModalInstance = null;
    }
    this.isMinimized = false;
  }

  makeFloatingPanelDraggable() {
    if (!this.floatingChatPanel) return;

    const titleBar = this.floatingChatPanel.querySelector('.thoth-title-bar') as HTMLElement;
    let isDragging = false;
    let currentX = 0;
    let currentY = 0;
    let initialX = 0;
    let initialY = 0;
    let xOffset = 0;
    let yOffset = 0;

    titleBar.addEventListener('mousedown', dragStart);
    document.addEventListener('mousemove', drag);
    document.addEventListener('mouseup', dragEnd);

    const self = this;
    function dragStart(e: MouseEvent) {
      if ((e.target as HTMLElement).tagName === 'BUTTON') return;

      initialX = e.clientX - xOffset;
      initialY = e.clientY - yOffset;
      isDragging = true;
      self.floatingChatPanel!.style.cursor = 'grabbing';
    }

    function drag(e: MouseEvent) {
      if (isDragging) {
        e.preventDefault();
        currentX = e.clientX - initialX;
        currentY = e.clientY - initialY;
        xOffset = currentX;
        yOffset = currentY;

        const rect = self.floatingChatPanel!.getBoundingClientRect();
        const maxX = window.innerWidth - rect.width;
        const maxY = window.innerHeight - rect.height;

        currentX = Math.max(0, Math.min(currentX, maxX));
        currentY = Math.max(0, Math.min(currentY, maxY));

        self.floatingChatPanel!.style.right = 'unset';
        self.floatingChatPanel!.style.bottom = 'unset';
        self.floatingChatPanel!.style.left = currentX + 'px';
        self.floatingChatPanel!.style.top = currentY + 'px';
      }
    }

    function dragEnd() {
      initialX = currentX;
      initialY = currentY;
      isDragging = false;
      if (self.floatingChatPanel) {
        self.floatingChatPanel.style.cursor = 'auto';
      }
    }
  }

  openDiscoverySourceModal() {
    // Placeholder for discovery source modal - create when needed
    new Notice('Discovery source modal not yet implemented');
  }

  async showConfirm(message: string): Promise<boolean> {
    return new Promise((resolve) => {
      new ConfirmModal(this.app, message, resolve).open();
    });
  }

  async showInput(prompt: string): Promise<string | null> {
    return new Promise((resolve) => {
      new InputModal(this.app, prompt, resolve).open();
    });
  }

  openCommandsModal() {
    new CommandsModal(this.app, this).open();
  }

  registerCommands() {
    // Discovery Commands
    this.addCommand({
      id: 'thoth-discovery-list',
      name: 'Thoth: List Discovery Sources',
      callback: () => {
        this.executeQuickCommand('discovery', ['list']);
      }
    });

    this.addCommand({
      id: 'thoth-discovery-run',
      name: 'Thoth: Run Discovery',
      callback: () => {
        this.promptAndExecuteCommand('discovery', ['run'], 'Enter source name (optional):');
      }
    });

    this.addCommand({
      id: 'thoth-discovery-create',
      name: 'Thoth: Create Discovery Source',
      callback: () => {
        this.openDiscoverySourceCreator();
      }
    });

    // PDF Commands
    this.addCommand({
      id: 'thoth-pdf-locate',
      name: 'Thoth: Locate PDF',
      callback: () => {
        this.promptAndExecuteCommand('pdf-locate', [], 'Enter DOI or paper identifier:');
      }
    });

    this.addCommand({
      id: 'thoth-pdf-stats',
      name: 'Thoth: PDF Statistics',
      callback: () => {
        this.executeQuickCommand('pdf-stats', []);
      }
    });

    this.addCommand({
      id: 'thoth-pdf-process-current',
      name: 'Thoth: Process Current PDF',
      callback: () => {
        this.processCurrentFile();
      }
    });

    // RAG Commands
    this.addCommand({
      id: 'thoth-rag-index',
      name: 'Thoth: Index Knowledge Base',
      callback: () => {
        this.executeQuickCommand('rag', ['index']);
      }
    });

    this.addCommand({
      id: 'thoth-rag-search',
      name: 'Thoth: Search Knowledge Base',
      callback: () => {
        this.promptAndExecuteCommand('rag', ['search'], 'Enter search query:');
      }
    });

    this.addCommand({
      id: 'thoth-rag-ask',
      name: 'Thoth: Ask Knowledge Base',
      callback: () => {
        this.promptAndExecuteCommand('rag', ['ask'], 'Enter your question:');
      }
    });

    this.addCommand({
      id: 'thoth-rag-stats',
      name: 'Thoth: RAG Statistics',
      callback: () => {
        this.executeQuickCommand('rag', ['stats']);
      }
    });

    // Notes Commands
    this.addCommand({
      id: 'thoth-notes-regenerate',
      name: 'Thoth: Regenerate All Notes',
      callback: () => {
        this.confirmAndExecuteCommand('notes', ['regenerate-all-notes'], 'This will regenerate all notes. Continue?');
      }
    });

    this.addCommand({
      id: 'thoth-notes-consolidate-tags',
      name: 'Thoth: Consolidate Tags',
      callback: () => {
        this.executeQuickCommand('notes', ['consolidate-tags']);
      }
    });

    this.addCommand({
      id: 'thoth-notes-reprocess',
      name: 'Thoth: Reprocess Current Note',
      callback: () => {
        this.reprocessCurrentNote();
      }
    });

    // Quick Actions
    this.addCommand({
      id: 'thoth-quick-research',
      name: 'Thoth: Quick Research (Selected Text)',
      editorCallback: (editor: Editor, view: MarkdownView) => {
        const selectedText = editor.getSelection();
        if (selectedText) {
          this.performQuickResearch(selectedText, editor);
        } else {
          new Notice('Please select text to research');
        }
      }
    });

    this.addCommand({
      id: 'thoth-insert-citation',
      name: 'Thoth: Insert Citation',
      editorCallback: (editor: Editor, view: MarkdownView) => {
        this.openCitationInserter(editor);
      }
    });

    this.addCommand({
      id: 'thoth-open-commands',
      name: 'Thoth: Open Commands',
      callback: () => {
        this.openCommandsModal();
      }
    });

    this.addCommand({
      id: 'thoth-open-status',
      name: 'Thoth: Open Status',
      callback: () => {
        // TODO: Create StatusModal when needed
        new Notice('Status modal coming soon! Use Commands modal for now.');
        this.openCommandsModal();
      }
    });

    // Agent Management
    this.addCommand({
      id: 'thoth-toggle-agent',
      name: 'Thoth: Toggle Agent (Start/Stop)',
      callback: () => {
        if (this.isAgentRunning) {
          this.stopAgent();
        } else {
          this.startAgent();
        }
      }
    });

    this.addCommand({
      id: 'thoth-agent-health-check',
      name: 'Thoth: Agent Health Check',
      callback: () => {
        this.performHealthCheck();
      }
    });

    // Configuration
    this.addCommand({
      id: 'thoth-validate-config',
      name: 'Thoth: Validate Configuration',
      callback: () => {
        this.validateConfiguration();
      }
    });

    this.addCommand({
      id: 'thoth-sync-config',
      name: 'Thoth: Sync Configuration to Backend',
      callback: () => {
        this.syncSettingsToBackend();
      }
    });
  }

  async executeQuickCommand(command: string, args: string[]) {
    if (!this.isAgentRunning) {
      this.smartNotice('Thoth agent is not running. Please start it first.', 'warning', 2);
      return;
    }

    const commandId = `cmd-${command}-${Date.now()}`;
    const progressNotification = this.createProgressNotification(
      commandId,
      `Executing ${command}...`,
      {
        type: 'info',
        canCancel: true,
        onCancel: () => {
          // TODO: Implement command cancellation
          this.smartNotice(`${command} operation cancelled`, 'warning');
        }
      }
    );

    try {
      progressNotification.updateProgress(10, `Sending ${command} request...`);

      const endpoint = this.getEndpointUrl();
      const response = await fetch(`${endpoint}/execute/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          command: command,
          args: args,
          stream_output: true
        })
      });

      progressNotification.updateProgress(30, 'Processing request...');

      if (response.ok) {
        const result = await response.json();
        if (result.streaming) {
          progressNotification.updateProgress(60, `${command} running...`);

          // Simulate progress for long-running operations
          setTimeout(() => {
            progressNotification.updateProgress(80, 'Finalizing...');
            setTimeout(() => {
              progressNotification.updateProgress(100, `${command} completed!`);
              progressNotification.setType('success');

              setTimeout(() => {
                progressNotification.close();
                this.smartNotice(`${command} completed successfully`, 'success');
              }, 1500);
            }, 1000);
          }, 2000);
        } else {
          progressNotification.updateProgress(100, `${command} completed!`);
          progressNotification.setType('success');

          setTimeout(() => {
            progressNotification.close();
            this.smartNotice(`${command} completed successfully`, 'success');
          }, 1500);
        }
      } else {
        throw new Error(`Command failed: ${response.statusText}`);
      }
    } catch (error) {
      console.error('Command execution error:', error);
      progressNotification.setType('error');
      progressNotification.updateMessage(`${command} failed: ${error.message}`);

      setTimeout(() => {
        progressNotification.close();
        this.smartNotice(`${command} execution failed`, 'error', 3);
      }, 3000);
    }
  }

  async promptAndExecuteCommand(command: string, baseArgs: string[], promptText: string) {
    const input = await this.showInputPrompt(promptText);
    if (input) {
      const args = input ? [...baseArgs, ...input.split(' ')] : baseArgs;
      this.executeQuickCommand(command, args);
    }
  }

  async confirmAndExecuteCommand(command: string, args: string[], confirmText: string) {
    const confirmed = await this.showConfirmDialog(confirmText);
    if (confirmed) {
      this.executeQuickCommand(command, args);
    }
  }

  async showInputPrompt(promptText: string): Promise<string | null> {
    return new Promise((resolve) => {
      const modal = new InputModal(this.app, promptText, resolve);
      modal.open();
    });
  }

  async showConfirmDialog(message: string): Promise<boolean> {
    return new Promise((resolve) => {
      const modal = new ConfirmModal(this.app, message, resolve);
      modal.open();
    });
  }

  async processCurrentFile() {
    const activeFile = this.app.workspace.getActiveFile();
    if (!activeFile) {
      new Notice('No active file');
      return;
    }

    if (!activeFile.path.endsWith('.pdf')) {
      new Notice('Current file is not a PDF');
      return;
    }

    try {
      const endpoint = this.getEndpointUrl();
      const response = await fetch(`${endpoint}/stream/operation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          operation_type: 'pdf_process',
          parameters: {
            pdf_paths: [activeFile.path]
          }
        })
      });

      if (response.ok) {
        const result = await response.json();
        new Notice(`Processing ${activeFile.name}. Check Thoth status for progress.`);
      } else {
        throw new Error(`PDF processing failed: ${response.statusText}`);
      }
    } catch (error) {
      console.error('PDF processing error:', error);
      new Notice(`PDF processing failed: ${error.message}`);
    }
  }

  async reprocessCurrentNote() {
    const activeFile = this.app.workspace.getActiveFile();
    if (!activeFile) {
      new Notice('No active file');
      return;
    }

    // Extract article ID from filename or metadata
    const articleId = this.extractArticleId(activeFile);
    if (!articleId) {
      new Notice('Could not determine article ID from current note');
      return;
    }

    this.executeQuickCommand('notes', ['reprocess-note', '--article-id', articleId]);
  }

  extractArticleId(file: TFile): string | null {
    // Try to extract article ID from filename or frontmatter
    const basename = file.basename;

    // Check if filename contains DOI pattern
    const doiMatch = basename.match(/10\.\d{4,}\/[^\s]+/);
    if (doiMatch) {
      return doiMatch[0];
    }

    // Check if filename contains arXiv pattern
    const arxivMatch = basename.match(/(\d{4}\.\d{4,5})/);
    if (arxivMatch) {
      return `arxiv:${arxivMatch[1]}`;
    }

    // Fallback to using filename
    return basename;
  }

  async performQuickResearch(query: string, editor: Editor) {
    if (!this.isAgentRunning) {
      new Notice('Thoth agent is not running. Please start it first.');
      return;
    }

    try {
      new Notice('Researching... This may take a moment.');

      const endpoint = this.getEndpointUrl();
      const response = await fetch(`${endpoint}/research/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: query,
          type: 'quick_research',
          max_results: 5,
          include_citations: true
        }),
      });

      if (response.ok) {
        const result = await response.json();

        // Insert the research results at the cursor position
        const cursor = editor.getCursor();
        const researchText = `\n\n## 🔍 Research: ${query}\n*Generated on ${new Date().toLocaleString()} by Thoth Research Assistant*\n\n${result.response || result.results}\n\n---\n`;

        editor.replaceRange(researchText, cursor);
        new Notice('Research completed and inserted!');
      } else {
        throw new Error(`Research request failed: ${response.statusText}`);
      }
    } catch (error) {
      console.error('Research error:', error);
      new Notice(`Research failed: ${error.message}`);
    }
  }

  async openCitationInserter(editor: Editor) {
    // Citation inserter functionality would go here
    new Notice('Citation inserter not yet implemented');
  }

  async openDiscoverySourceCreator() {
    // Discovery source creator functionality would go here
    new Notice('Discovery source creator not yet implemented');
  }

  async performHealthCheck() {
    try {
      const endpoint = this.getEndpointUrl();
      const response = await fetch(`${endpoint}/health`);

      if (response.ok) {
        const health = await response.json();
        new Notice(`Health Check: ${health.status || 'OK'}`);
      } else {
        new Notice(`Health Check Failed: ${response.statusText}`);
      }
    } catch (error) {
      new Notice(`Health Check Failed: ${error.message}`);
    }
  }

  async validateConfiguration() {
    try {
      const endpoint = this.getEndpointUrl();
      const response = await fetch(`${endpoint}/config/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(this.settings)
      });

      if (response.ok) {
        const validation = await response.json();
        if (validation.is_valid) {
          new Notice('✅ Configuration is valid');
        } else {
          new Notice(`❌ Configuration errors: ${validation.error_count}`);
          console.log('Validation errors:', validation.errors);
        }
      } else {
        new Notice('Configuration validation failed');
      }
    } catch (error) {
      new Notice(`Validation failed: ${error.message}`);
    }
  }

  // ============================================================================
  // PERFORMANCE & CACHING SYSTEM
  // ============================================================================

  /**
   * Cached HTTP request with automatic cache management
   */
  async cachedRequest(url: string, options: RequestInit = {}, ttl: number = this.cacheDefaultTTL): Promise<any> {
    const cacheKey = this.generateCacheKey(url, options);

    // Check cache first
    const cached = this.requestCache.get(cacheKey);
    if (cached && Date.now() < cached.expires) {
      return cached.data;
    }

    // Queue the request to avoid overwhelming the server
    return this.queueRequest(async () => {
      const response = await fetch(url, options);
      if (!response.ok) {
        throw new Error(`Request failed: ${response.statusText}`);
      }

      const data = await response.json();

      // Cache the result
      this.requestCache.set(cacheKey, {
        data,
        timestamp: Date.now(),
        expires: Date.now() + ttl
      });

      return data;
    });
  }

  /**
   * Queue requests to prevent overwhelming the backend
   */
  private async queueRequest<T>(request: () => Promise<T>): Promise<T> {
    return new Promise((resolve, reject) => {
      this.requestQueue.push({ request, resolve, reject });
      this.processQueue();
    });
  }

  /**
   * Process the request queue with concurrency control
   */
  private async processQueue(): Promise<void> {
    if (this.isProcessingQueue || this.activeRequests >= this.maxConcurrentRequests) {
      return;
    }

    this.isProcessingQueue = true;

    while (this.requestQueue.length > 0 && this.activeRequests < this.maxConcurrentRequests) {
      const { request, resolve, reject } = this.requestQueue.shift()!;

      this.activeRequests++;

      request()
        .then(resolve)
        .catch(reject)
        .finally(() => {
          this.activeRequests--;
          this.processQueue(); // Process next items in queue
        });
    }

    this.isProcessingQueue = false;
  }

  /**
   * Generate cache key from URL and options
   */
  private generateCacheKey(url: string, options: RequestInit): string {
    const method = options.method || 'GET';
    const body = options.body ? JSON.stringify(options.body) : '';
    return `${method}:${url}:${body}`;
  }

  /**
   * Clear expired cache entries
   */
  private cleanupCache(): void {
    const now = Date.now();
    for (const [key, entry] of this.requestCache.entries()) {
      if (now > entry.expires) {
        this.requestCache.delete(key);
      }
    }
  }

  /**
   * Enhanced fetch with intelligent caching and retries
   */
  async enhancedFetch(url: string, options: RequestInit = {}, config: {
    cache?: boolean;
    cacheTTL?: number;
    retries?: number;
    retryDelay?: number;
  } = {}): Promise<Response> {
    const {
      cache = true,
      cacheTTL = this.cacheDefaultTTL,
      retries = 2,
      retryDelay = 1000
    } = config;

    if (cache && options.method === 'GET') {
      try {
        return await this.cachedRequest(url, options, cacheTTL);
      } catch (error) {
        // Fall through to regular fetch with retries
      }
    }

    // Implement retry logic
    let lastError: Error;
    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        const response = await this.queueRequest(() => fetch(url, options));
        if (response.ok) {
          return response;
        }
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      } catch (error) {
        lastError = error as Error;
        if (attempt < retries) {
          await new Promise(resolve => setTimeout(resolve, retryDelay * Math.pow(2, attempt)));
        }
      }
    }

    throw lastError!;
  }

  /**
   * Batch multiple operations for efficiency
   */
  async batchExecute<T>(operations: Array<() => Promise<T>>, maxConcurrent: number = 3): Promise<T[]> {
    const results: T[] = [];
    const errors: Error[] = [];

    for (let i = 0; i < operations.length; i += maxConcurrent) {
      const batch = operations.slice(i, i + maxConcurrent);
      const batchPromises = batch.map(async (op, index) => {
        try {
          return await op();
        } catch (error) {
          errors.push(error as Error);
          return null;
        }
      });

      const batchResults = await Promise.all(batchPromises);
      const validResults = batchResults.filter(result => result !== null) as T[];
      results.push(...validResults);
    }

    if (errors.length > 0) {
      console.warn(`Batch execution completed with ${errors.length} errors:`, errors);
    }

    return results;
  }

  /**
   * Enhanced notification system with progress indicators and deduplication
   */
  private notificationHistory: Map<string, number> = new Map();
  private activeProgressNotifications: Map<string, NotificationProgress> = new Map();
  private readonly NOTIFICATION_COOLDOWN = 5000; // 5 seconds

  smartNotice(message: string, type: 'info' | 'success' | 'warning' | 'error' = 'info', priority: number = 1): void {
    const notificationKey = `${type}:${message}`;
    const lastShown = this.notificationHistory.get(notificationKey) || 0;
    const now = Date.now();

    // Deduplicate notifications within cooldown period
    if (now - lastShown < this.NOTIFICATION_COOLDOWN && priority <= 1) {
      return;
    }

    this.notificationHistory.set(notificationKey, now);

    // Create styled notice based on type
    const notice = new Notice('', this.settings.notificationDuration);
    const noticeEl = notice.noticeEl;

    // Apply custom styling
    noticeEl.empty();
    const content = noticeEl.createDiv();

    const iconMap = {
      info: 'ℹ️',
      success: '✅',
      warning: '⚠️',
      error: '❌'
    };

    const colorMap = {
      info: 'var(--text-accent)',
      success: 'var(--color-green)',
      warning: 'var(--color-orange)',
      error: 'var(--color-red)'
    };

    content.innerHTML = `
      <div style="display: flex; align-items: center; gap: 8px;">
        <span style="font-size: 16px;">${iconMap[type]}</span>
        <span style="color: ${colorMap[type]}; font-weight: 500;">Thoth:</span>
        <span>${message}</span>
      </div>
    `;

    // Auto-cleanup old notifications from history
    if (this.notificationHistory.size > 100) {
      const cutoff = now - this.NOTIFICATION_COOLDOWN * 2;
      for (const [key, timestamp] of this.notificationHistory.entries()) {
        if (timestamp < cutoff) {
          this.notificationHistory.delete(key);
        }
      }
    }
  }

  /**
   * Get notification icon based on type
   */
  private getNotificationIcon(type: 'info' | 'success' | 'warning' | 'error'): string {
    const iconMap = {
      info: '🔵',
      success: '✅',
      warning: '⚠️',
      error: '❌'
    };
    return iconMap[type];
  }

  /**
   * Create a progress notification that can be updated
   */
  createProgressNotification(
    id: string,
    initialMessage: string,
    options: {
      type?: 'info' | 'success' | 'warning' | 'error';
      canCancel?: boolean;
      onCancel?: () => void;
      duration?: number;
    } = {}
  ): NotificationProgress {
    const { type = 'info', canCancel = false, onCancel, duration = 0 } = options;

    // Close existing progress notification with same ID
    if (this.activeProgressNotifications.has(id)) {
      this.activeProgressNotifications.get(id)!.close();
    }

    // Ensure enhanced notification styles are loaded
    this.loadEnhancedNotificationStyles();

    const notice = new Notice('', duration);
    const noticeEl = notice.noticeEl;

    noticeEl.addClass(`thoth-notice-${type}`);
    noticeEl.addClass('thoth-progress-notification');

    // Create progress notification HTML
    noticeEl.innerHTML = `
      <div class="thoth-notice-content">
        <span class="thoth-notice-icon">${this.getNotificationIcon(type)}</span>
        <span class="thoth-progress-message">${initialMessage}</span>
      </div>
      <div class="thoth-progress-container">
        <div class="thoth-progress-bar" style="width: 0%"></div>
      </div>
      ${canCancel ? `
        <div class="thoth-notice-actions">
          <button class="thoth-notice-btn thoth-cancel-btn">🚫 Cancel</button>
        </div>
      ` : ''}
    `;

    // Set up cancel functionality
    if (canCancel && onCancel) {
      const cancelBtn = noticeEl.querySelector('.thoth-cancel-btn') as HTMLButtonElement;
      if (cancelBtn) {
        cancelBtn.onclick = () => {
          onCancel();
          this.closeProgressNotification(id);
        };
      }
    }

    const progressNotification: NotificationProgress = {
      notice,
      updateProgress: (progress: number, message?: string) => {
        const progressBar = noticeEl.querySelector('.thoth-progress-bar') as HTMLElement;
        const messageEl = noticeEl.querySelector('.thoth-progress-message') as HTMLElement;

        if (progressBar) {
          progressBar.style.width = `${Math.min(100, Math.max(0, progress))}%`;
        }

        if (message && messageEl) {
          messageEl.textContent = message;
        }
      },
      updateMessage: (message: string) => {
        const messageEl = noticeEl.querySelector('.thoth-progress-message') as HTMLElement;
        if (messageEl) {
          messageEl.textContent = message;
        }
      },
      close: () => {
        notice.hide();
        this.activeProgressNotifications.delete(id);
      },
      setType: (newType: 'info' | 'success' | 'warning' | 'error') => {
        noticeEl.removeClass(`thoth-notice-${type}`);
        noticeEl.addClass(`thoth-notice-${newType}`);

        const iconEl = noticeEl.querySelector('.thoth-notice-icon') as HTMLElement;
        if (iconEl) {
          iconEl.textContent = this.getNotificationIcon(newType);
        }
      }
    };

    this.activeProgressNotifications.set(id, progressNotification);
    return progressNotification;
  }

  /**
   * Update an existing progress notification
   */
  updateProgressNotification(id: string, progress: number, message?: string): boolean {
    const notification = this.activeProgressNotifications.get(id);
    if (notification) {
      notification.updateProgress(progress, message);
      return true;
    }
    return false;
  }

  /**
   * Close a progress notification
   */
  closeProgressNotification(id: string): void {
    const notification = this.activeProgressNotifications.get(id);
    if (notification) {
      notification.close();
    }
  }

  /**
   * Create a notification with action buttons
   */
  createActionNotification(
    message: string,
    actions: Array<{label: string, action: () => void, style?: 'primary' | 'secondary'}>,
    type: 'info' | 'success' | 'warning' | 'error' = 'info',
    duration: number = 0
  ): void {
    this.loadEnhancedNotificationStyles();

    const notice = new Notice('', duration);
    const noticeEl = notice.noticeEl;

    noticeEl.addClass(`thoth-notice-${type}`);

    noticeEl.innerHTML = `
      <div class="thoth-notice-content">
        <span class="thoth-notice-icon">${this.getNotificationIcon(type)}</span>
        ${message}
      </div>
      <div class="thoth-notice-actions">
        ${actions.map(action => `
          <button class="thoth-notice-btn ${action.style === 'primary' ? 'primary' : ''}">${action.label}</button>
        `).join('')}
      </div>
    `;

    // Set up action handlers
    const actionButtons = noticeEl.querySelectorAll('.thoth-notice-btn');
    actionButtons.forEach((btn, index) => {
      btn.addEventListener('click', () => {
        actions[index].action();
        notice.hide();
      });
    });
  }

  /**
   * Load enhanced notification styles
   */
  private loadEnhancedNotificationStyles(): void {
    if (document.getElementById('thoth-notification-styles')) {
      return; // Styles already loaded
    }

    const style = document.createElement('style');
    style.id = 'thoth-notification-styles';
    style.textContent = `
      .thoth-notice-success {
        background: linear-gradient(135deg, var(--color-green), #4CAF50);
        color: white;
        border-left: 4px solid #2E7D32;
        box-shadow: 0 4px 12px rgba(76, 175, 80, 0.3);
      }
      .thoth-notice-warning {
        background: linear-gradient(135deg, var(--color-orange), #FF9800);
        color: white;
        border-left: 4px solid #F57F17;
        box-shadow: 0 4px 12px rgba(255, 152, 0, 0.3);
      }
      .thoth-notice-error {
        background: linear-gradient(135deg, var(--color-red), #F44336);
        color: white;
        border-left: 4px solid #C62828;
        box-shadow: 0 4px 12px rgba(244, 67, 54, 0.3);
      }
      .thoth-notice-info {
        background: linear-gradient(135deg, var(--interactive-accent), #2196F3);
        color: var(--text-on-accent);
        border-left: 4px solid #1565C0;
        box-shadow: 0 4px 12px rgba(33, 150, 243, 0.3);
      }
      .thoth-notice-content {
        display: flex;
        align-items: center;
        gap: 8px;
        font-weight: 500;
      }
      .thoth-notice-icon {
        font-size: 1.2em;
        filter: drop-shadow(0 1px 2px rgba(0,0,0,0.2));
      }
      .thoth-progress-container {
        margin-top: 8px;
        background: rgba(255,255,255,0.2);
        border-radius: 10px;
        height: 6px;
        overflow: hidden;
      }
      .thoth-progress-bar {
        height: 100%;
        background: rgba(255,255,255,0.8);
        border-radius: 10px;
        transition: width 0.3s ease;
        box-shadow: 0 0 10px rgba(255,255,255,0.3);
      }
      .thoth-notice-actions {
        margin-top: 8px;
        display: flex;
        gap: 8px;
      }
      .thoth-notice-btn {
        padding: 4px 8px;
        background: rgba(255,255,255,0.2);
        border: 1px solid rgba(255,255,255,0.3);
        border-radius: 4px;
        color: inherit;
        cursor: pointer;
        font-size: 0.8em;
        transition: all 0.2s ease;
      }
      .thoth-notice-btn:hover {
        background: rgba(255,255,255,0.3);
        transform: translateY(-1px);
      }
      .thoth-notice-btn.primary {
        background: rgba(255,255,255,0.9);
        color: var(--text-normal);
        font-weight: 600;
      }
      .thoth-progress-notification {
        min-width: 300px;
        animation: slideInRight 0.3s ease;
      }
      @keyframes slideInRight {
        from {
          transform: translateX(100%);
          opacity: 0;
        }
        to {
          transform: translateX(0);
          opacity: 1;
        }
      }
    `;
    document.head.appendChild(style);
  }

  /**
   * Optimized settings save with debouncing
   */
  private saveSettingsTimeout: NodeJS.Timeout | null = null;

  async debouncedSaveSettings(delay: number = 1000): Promise<void> {
    if (this.saveSettingsTimeout) {
      clearTimeout(this.saveSettingsTimeout);
    }

    return new Promise((resolve) => {
      this.saveSettingsTimeout = setTimeout(async () => {
        await this.saveSettings();
        resolve();
      }, delay);
    });
  }

  /**
   * Performance monitoring and reporting
   */
  private performanceMetrics: {
    requestCount: number;
    averageResponseTime: number;
    cacheHitRate: number;
    errorRate: number;
    startTime: number;
  } = {
    requestCount: 0,
    averageResponseTime: 0,
    cacheHitRate: 0,
    errorRate: 0,
    startTime: Date.now()
  };

  getPerformanceReport(): any {
    const uptime = Date.now() - this.performanceMetrics.startTime;
    const cacheSize = this.requestCache.size;
    const queueLength = this.requestQueue.length;

    return {
      uptime: Math.round(uptime / 1000), // seconds
      cacheSize,
      queueLength,
      activeRequests: this.activeRequests,
      ...this.performanceMetrics
    };
  }

  /**
   * Cleanup resources on plugin unload
   */
  onunload() {
    // Clean up floating panel
    this.closeFloatingPanel();

    // Clear cache
    this.requestCache.clear();

    // Clear queue
    this.requestQueue.length = 0;

    // Clear timeouts
    if (this.saveSettingsTimeout) {
      clearTimeout(this.saveSettingsTimeout);
    }

    // Stop agent
    this.stopAgent();
  }
}

// Enhanced modal with tabbed interface


class ThothSettingTab extends PluginSettingTab {
  plugin: ThothPlugin;

  constructor(app: App, plugin: ThothPlugin) {
    super(app, plugin);
    this.plugin = plugin;
  }

  display(): void {
    const { containerEl } = this;
    containerEl.empty();

    // Header
    const headerEl = containerEl.createEl('div', { cls: 'thoth-settings-header' });
    headerEl.createEl('h1', { text: '🧠 Thoth Research Assistant' });
    headerEl.createEl('p', {
      text: 'Intelligent research assistant for academic work and knowledge discovery',
      cls: 'thoth-settings-subtitle'
    });

    // Quick Status
    this.addQuickStatus(containerEl);

    // Essential Settings (always visible)
    this.addEssentialSettings(containerEl);

    // Connection Settings
    this.addConnectionSettings(containerEl);

    // Advanced Settings Toggle
    const advancedToggle = new Setting(containerEl)
      .setName('🔧 Show Advanced Settings')
      .setDesc('Configure LLM models, agent behavior, discovery system, and more')
      .addToggle((toggle) =>
        toggle
          .setValue(this.plugin.settings.showAdvancedSettings)
          .onChange(async (value) => {
            this.plugin.settings.showAdvancedSettings = value;
            await this.plugin.saveSettings();
            this.display(); // Refresh to show/hide advanced settings
          })
      );

    if (this.plugin.settings.showAdvancedSettings) {
      this.addAdvancedSettings(containerEl);
    }

    // Agent Controls (always visible at bottom)
    this.addAgentControls(containerEl);
  }

  private addQuickStatus(containerEl: HTMLElement): void {
    const statusSection = containerEl.createEl('div', { cls: 'thoth-settings-section' });
    statusSection.createEl('h2', { text: '📊 Quick Status' });

    const statusGrid = statusSection.createEl('div', { cls: 'thoth-status-grid' });

    // Agent Status
    const agentStatus = statusGrid.createEl('div', { cls: 'thoth-status-item' });
    agentStatus.createEl('span', { text: 'Agent: ', cls: 'thoth-status-label' });
    const agentIndicator = agentStatus.createEl('span', { cls: 'thoth-status-indicator' });

    if (this.plugin.isRestarting) {
      agentIndicator.textContent = 'Restarting...';
      agentIndicator.className = 'thoth-status-indicator thoth-status-warning';
    } else if (this.plugin.isAgentRunning) {
      agentIndicator.textContent = 'Running';
      agentIndicator.className = 'thoth-status-indicator thoth-status-success';
    } else {
      agentIndicator.textContent = 'Stopped';
      agentIndicator.className = 'thoth-status-indicator thoth-status-error';
    }

    // API Keys Status
    const keysStatus = statusGrid.createEl('div', { cls: 'thoth-status-item' });
    keysStatus.createEl('span', { text: 'API Keys: ', cls: 'thoth-status-label' });
    const keysIndicator = keysStatus.createEl('span', { cls: 'thoth-status-indicator' });

    const hasKeys = this.plugin.settings.mistralKey && this.plugin.settings.openrouterKey;
    if (hasKeys) {
      keysIndicator.textContent = 'Configured';
      keysIndicator.className = 'thoth-status-indicator thoth-status-success';
    } else {
      keysIndicator.textContent = 'Missing';
      keysIndicator.className = 'thoth-status-indicator thoth-status-error';
    }

    // Connection Mode
    const modeStatus = statusGrid.createEl('div', { cls: 'thoth-status-item' });
    modeStatus.createEl('span', { text: 'Mode: ', cls: 'thoth-status-label' });
    const modeIndicator = modeStatus.createEl('span', { cls: 'thoth-status-indicator' });
    modeIndicator.textContent = this.plugin.settings.remoteMode ? 'Remote' : 'Local';
    modeIndicator.className = 'thoth-status-indicator thoth-status-info';
  }

  private addEssentialSettings(containerEl: HTMLElement): void {
    const section = containerEl.createEl('div', { cls: 'thoth-settings-section' });
    section.createEl('h2', { text: '🔑 Essential Configuration' });
    section.createEl('p', { text: 'Required settings to get started with Thoth', cls: 'thoth-section-desc' });

    // API Keys Subsection
    const apiSection = section.createEl('div', { cls: 'thoth-subsection' });
    apiSection.createEl('h3', { text: 'API Keys' });

    new Setting(apiSection)
      .setName('Mistral API Key')
      .setDesc('Required for PDF processing and document analysis')
      .addText((text) => {
        text.inputEl.type = 'password';
        text
          .setPlaceholder('Enter your Mistral API key')
          .setValue(this.plugin.settings.mistralKey)
          .onChange(async (value) => {
            this.plugin.settings.mistralKey = value;
            await this.plugin.saveSettings();
          });
      })
      .addExtraButton((button) => {
        button
          .setIcon('external-link')
          .setTooltip('Get Mistral API Key')
          .onClick(() => window.open('https://console.mistral.ai', '_blank'));
      });

    new Setting(apiSection)
      .setName('OpenRouter API Key')
      .setDesc('Required for AI research capabilities and language models')
      .addText((text) => {
        text.inputEl.type = 'password';
        text
          .setPlaceholder('Enter your OpenRouter API key')
          .setValue(this.plugin.settings.openrouterKey)
          .onChange(async (value) => {
            this.plugin.settings.openrouterKey = value;
            await this.plugin.saveSettings();
          });
      })
      .addExtraButton((button) => {
        button
          .setIcon('external-link')
          .setTooltip('Get OpenRouter API Key')
          .onClick(() => window.open('https://openrouter.ai', '_blank'));
      });

    // Optional API Keys
    const optionalApiSection = apiSection.createEl('details', { cls: 'thoth-optional-section' });
    optionalApiSection.createEl('summary', { text: 'Optional API Keys' });

    new Setting(optionalApiSection)
      .setName('Google API Key')
      .setDesc('For Google Scholar and search integration')
      .addText((text) => {
        text.inputEl.type = 'password';
        text
          .setPlaceholder('Enter your Google API key')
          .setValue(this.plugin.settings.googleApiKey)
          .onChange(async (value) => {
            this.plugin.settings.googleApiKey = value;
            await this.plugin.saveSettings();
          });
      });

    new Setting(optionalApiSection)
      .setName('Semantic Scholar API Key')
      .setDesc('For enhanced academic paper discovery')
      .addText((text) => {
        text.inputEl.type = 'password';
        text
          .setPlaceholder('Enter your Semantic Scholar API key')
          .setValue(this.plugin.settings.semanticScholarKey)
          .onChange(async (value) => {
            this.plugin.settings.semanticScholarKey = value;
            await this.plugin.saveSettings();
          });
      });

    new Setting(optionalApiSection)
      .setName('Serper API Key')
      .setDesc('For general web search integration')
      .addText((text) => {
        text.inputEl.type = 'password';
        text
          .setPlaceholder('Enter your Serper API key')
          .setValue(this.plugin.settings.webSearchKey)
          .onChange(async (value) => {
            this.plugin.settings.webSearchKey = value;
            await this.plugin.saveSettings();
          });
      });

    new Setting(optionalApiSection)
      .setName('Web Search Providers')
      .setDesc('Comma-separated providers e.g. "serper,duckduckgo"')
      .addText((text) => {
        text
          .setPlaceholder('serper,duckduckgo')
          .setValue(this.plugin.settings.webSearchProviders)
          .onChange(async (value) => {
            this.plugin.settings.webSearchProviders = value;
            await this.plugin.saveSettings();
          });
      });

    // Directory Settings
    const dirSection = section.createEl('div', { cls: 'thoth-subsection' });
    dirSection.createEl('h3', { text: 'Directory Configuration' });

    new Setting(dirSection)
      .setName('Workspace Directory')
      .setDesc('Path to your Thoth workspace (where you cloned project-thoth)')
      .addText((text) =>
        text
          .setPlaceholder('e.g., /home/user/project-thoth')
          .setValue(this.plugin.settings.workspaceDirectory)
          .onChange(async (value) => {
            this.plugin.settings.workspaceDirectory = value;
            // Auto-populate other directories
            if (value) {
              this.plugin.settings.dataDirectory = `${value}/data`;
              this.plugin.settings.knowledgeDirectory = `${value}/knowledge`;
              this.plugin.settings.logsDirectory = `${value}/logs`;
              this.plugin.settings.queriesDirectory = `${value}/planning/queries`;
              this.plugin.settings.agentStorageDirectory = `${value}/knowledge/agent`;
              this.plugin.settings.pdfDirectory = `${value}/data/pdf`;
            }
            await this.plugin.saveSettings();
          })
      );

    new Setting(dirSection)
      .setName('Obsidian Notes Directory')
      .setDesc('Directory in your vault where Thoth will store research notes')
      .addText((text) =>
        text
          .setPlaceholder('e.g., Research/Thoth')
          .setValue(this.plugin.settings.obsidianDirectory)
          .onChange(async (value) => {
            this.plugin.settings.obsidianDirectory = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(dirSection)
      .setName('Prompts Directory')
      .setDesc('Folder with custom prompts (leave blank for defaults)')
      .addText((text) =>
        text
          .setPlaceholder('e.g., /path/to/prompts')
          .setValue(this.plugin.settings.promptsDirectory)
          .onChange(async (value) => {
            this.plugin.settings.promptsDirectory = value;
            await this.plugin.saveSettings();
          })
      );
  }

  private addConnectionSettings(containerEl: HTMLElement): void {
    const section = containerEl.createEl('div', { cls: 'thoth-settings-section' });
    section.createEl('h2', { text: '🌐 Connection Settings' });
    section.createEl('p', { text: 'Configure how Obsidian connects to the Thoth agent', cls: 'thoth-section-desc' });

    new Setting(section)
      .setName('Remote Mode')
      .setDesc('Connect to a remote Thoth server (WSL, Docker, or remote machine)')
      .addToggle((toggle) =>
        toggle
          .setValue(this.plugin.settings.remoteMode)
          .onChange(async (value) => {
            this.plugin.settings.remoteMode = value;
            await this.plugin.saveSettings();
            this.display();
          })
      );

    if (this.plugin.settings.remoteMode) {
      new Setting(section)
        .setName('Remote Endpoint URL')
        .setDesc('Full URL of the remote Thoth server')
        .addText((text) =>
          text
            .setPlaceholder('http://localhost:8000')
            .setValue(this.plugin.settings.remoteEndpointUrl)
            .onChange(async (value) => {
              this.plugin.settings.remoteEndpointUrl = value;
              await this.plugin.saveSettings();
            })
        );

      // Quick connection test for remote mode
      const testContainer = section.createEl('div', { cls: 'thoth-test-container' });
      const testButton = testContainer.createEl('button', {
        text: 'Test Remote Connection',
        cls: 'thoth-test-button'
      });
      const testResult = testContainer.createEl('span', { cls: 'thoth-test-result' });

      testButton.onclick = async () => {
        testButton.disabled = true;
        testButton.textContent = 'Testing...';
        testResult.textContent = '';

        try {
          const response = await fetch(`${this.plugin.settings.remoteEndpointUrl}/health`);
          if (response.ok) {
            testResult.textContent = '✅ Connection successful';
            testResult.className = 'thoth-test-result thoth-test-success';
          } else {
            testResult.textContent = `❌ Server error: ${response.status}`;
            testResult.className = 'thoth-test-result thoth-test-error';
          }
        } catch (error) {
          testResult.textContent = `❌ Connection failed: ${error.message}`;
          testResult.className = 'thoth-test-result thoth-test-error';
        } finally {
          testButton.disabled = false;
          testButton.textContent = 'Test Remote Connection';
        }
      };
    } else {
      new Setting(section)
        .setName('Local Host')
        .setDesc('Host address for local Thoth server')
        .addText((text) =>
          text
            .setPlaceholder('127.0.0.1')
            .setValue(this.plugin.settings.endpointHost)
            .onChange(async (value) => {
              this.plugin.settings.endpointHost = value;
              this.plugin.settings.endpointBaseUrl = `http://${value}:${this.plugin.settings.endpointPort}`;
              await this.plugin.saveSettings();
            })
        );

      new Setting(section)
        .setName('Local Port')
        .setDesc('Port for local Thoth server')
        .addSlider((slider) =>
          slider
            .setLimits(3000, 9999, 1)
            .setValue(this.plugin.settings.endpointPort)
            .setDynamicTooltip()
            .onChange(async (value) => {
              this.plugin.settings.endpointPort = value;
              this.plugin.settings.endpointBaseUrl = `http://${this.plugin.settings.endpointHost}:${value}`;
              await this.plugin.saveSettings();
            })
        );
    }
  }

  private addAdvancedSettings(containerEl: HTMLElement): void {
    const section = containerEl.createEl('div', { cls: 'thoth-settings-section thoth-advanced-section' });
    section.createEl('h2', { text: '⚙️ Advanced Configuration' });

    // LLM Configuration
    this.addLLMSettings(section);

    // Agent Behavior
    this.addAgentBehaviorSettings(section);

    // Discovery System
    this.addDiscoverySettings(section);

    // Logging & Performance
    this.addLoggingSettings(section);

    // UI Preferences
    this.addUISettings(section);
  }

  private addLLMSettings(parentEl: HTMLElement): void {
    const subsection = parentEl.createEl('details', { cls: 'thoth-subsection' });
    subsection.createEl('summary', { text: '🤖 Language Model Configuration' });

    const modelOptions = [
      'anthropic/claude-3-opus',
      'anthropic/claude-3-sonnet',
      'anthropic/claude-3-haiku',
      'openai/gpt-4',
      'openai/gpt-4-turbo',
      'openai/gpt-3.5-turbo',
      'mistral/mistral-large',
      'mistral/mistral-medium'
    ];

    new Setting(subsection)
      .setName('Primary LLM Model')
      .setDesc('Main language model for research and general tasks')
      .addDropdown((dropdown) => {
        modelOptions.forEach(model => dropdown.addOption(model, model));
        dropdown
          .setValue(this.plugin.settings.primaryLlmModel)
          .onChange(async (value) => {
            this.plugin.settings.primaryLlmModel = value;
            await this.plugin.saveSettings();
          });
      });

    new Setting(subsection)
      .setName('Analysis LLM Model')
      .setDesc('Specialized model for document analysis and PDF processing')
      .addDropdown((dropdown) => {
        modelOptions.forEach(model => dropdown.addOption(model, model));
        dropdown
          .setValue(this.plugin.settings.analysisLlmModel)
          .onChange(async (value) => {
            this.plugin.settings.analysisLlmModel = value;
            await this.plugin.saveSettings();
          });
      });

    new Setting(subsection)
      .setName('LLM Temperature')
      .setDesc('Creativity level for responses (0.0 = focused, 1.0 = creative)')
      .addSlider((slider) =>
        slider
          .setLimits(0, 1, 0.1)
          .setValue(this.plugin.settings.llmTemperature)
          .setDynamicTooltip()
          .onChange(async (value) => {
            this.plugin.settings.llmTemperature = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(subsection)
      .setName('Max Output Tokens')
      .setDesc('Maximum response length')
      .addSlider((slider) =>
        slider
          .setLimits(1024, 8192, 256)
          .setValue(this.plugin.settings.llmMaxOutputTokens)
          .setDynamicTooltip()
          .onChange(async (value) => {
            this.plugin.settings.llmMaxOutputTokens = value;
            await this.plugin.saveSettings();
          })
      );
  }

  private addAgentBehaviorSettings(parentEl: HTMLElement): void {
    const subsection = parentEl.createEl('details', { cls: 'thoth-subsection' });
    subsection.createEl('summary', { text: '🧠 Agent Behavior' });

    new Setting(subsection)
      .setName('Auto-start Research Agent')
      .setDesc('Automatically start the research agent when the server starts')
      .addToggle((toggle) =>
        toggle
          .setValue(this.plugin.settings.researchAgentAutoStart)
          .onChange(async (value) => {
            this.plugin.settings.researchAgentAutoStart = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(subsection)
      .setName('Enable Agent Memory')
      .setDesc('Allow the agent to remember previous conversations')
      .addToggle((toggle) =>
        toggle
          .setValue(this.plugin.settings.researchAgentMemoryEnabled)
          .onChange(async (value) => {
            this.plugin.settings.researchAgentMemoryEnabled = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(subsection)
      .setName('Max Tool Calls')
      .setDesc('Maximum number of tools the agent can use per request')
      .addSlider((slider) =>
        slider
          .setLimits(5, 50, 5)
          .setValue(this.plugin.settings.agentMaxToolCalls)
          .setDynamicTooltip()
          .onChange(async (value) => {
            this.plugin.settings.agentMaxToolCalls = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(subsection)
      .setName('Agent Timeout (seconds)')
      .setDesc('Maximum time to wait for agent responses')
      .addSlider((slider) =>
        slider
          .setLimits(30, 600, 30)
          .setValue(this.plugin.settings.agentTimeoutSeconds)
          .setDynamicTooltip()
          .onChange(async (value) => {
            this.plugin.settings.agentTimeoutSeconds = value;
            await this.plugin.saveSettings();
          })
      );
  }

  private addDiscoverySettings(parentEl: HTMLElement): void {
    const subsection = parentEl.createEl('details', { cls: 'thoth-subsection' });
    subsection.createEl('summary', { text: '🔍 Discovery System' });

    new Setting(subsection)
      .setName('Auto-start Discovery Scheduler')
      .setDesc('Automatically start the discovery scheduler for finding new research')
      .addToggle((toggle) =>
        toggle
          .setValue(this.plugin.settings.discoveryAutoStartScheduler)
          .onChange(async (value) => {
            this.plugin.settings.discoveryAutoStartScheduler = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(subsection)
      .setName('Max Articles per Discovery')
      .setDesc('Maximum number of articles to discover per search')
      .addSlider((slider) =>
        slider
          .setLimits(10, 100, 10)
          .setValue(this.plugin.settings.discoveryDefaultMaxArticles)
          .setDynamicTooltip()
          .onChange(async (value) => {
            this.plugin.settings.discoveryDefaultMaxArticles = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(subsection)
      .setName('Discovery Interval (minutes)')
      .setDesc('How often to run automatic discovery searches')
      .addSlider((slider) =>
        slider
          .setLimits(15, 240, 15)
          .setValue(this.plugin.settings.discoveryDefaultIntervalMinutes)
          .setDynamicTooltip()
          .onChange(async (value) => {
            this.plugin.settings.discoveryDefaultIntervalMinutes = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(subsection)
      .setName('Enable Chrome Extension Integration')
      .setDesc('Allow integration with Thoth Chrome extension for web research')
      .addToggle((toggle) =>
        toggle
          .setValue(this.plugin.settings.discoveryChromeExtensionEnabled)
          .onChange(async (value) => {
            this.plugin.settings.discoveryChromeExtensionEnabled = value;
            await this.plugin.saveSettings();
          })
      );
  }

  private addLoggingSettings(parentEl: HTMLElement): void {
    const subsection = parentEl.createEl('details', { cls: 'thoth-subsection' });
    subsection.createEl('summary', { text: '📊 Logging & Performance' });

    const logLevels = ['DEBUG', 'INFO', 'WARNING', 'ERROR'];

    new Setting(subsection)
      .setName('Log Level')
      .setDesc('Minimum level of messages to log')
      .addDropdown((dropdown) => {
        logLevels.forEach(level => dropdown.addOption(level, level));
        dropdown
          .setValue(this.plugin.settings.logLevel)
          .onChange(async (value) => {
            this.plugin.settings.logLevel = value;
            await this.plugin.saveSettings();
          });
      });

    new Setting(subsection)
      .setName('Enable Performance Monitoring')
      .setDesc('Track performance metrics and system health')
      .addToggle((toggle) =>
        toggle
          .setValue(this.plugin.settings.enablePerformanceMonitoring)
          .onChange(async (value) => {
            this.plugin.settings.enablePerformanceMonitoring = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(subsection)
      .setName('Development Mode')
      .setDesc('Enable additional debugging features')
      .addToggle((toggle) =>
        toggle
          .setValue(this.plugin.settings.developmentMode)
          .onChange(async (value) => {
            this.plugin.settings.developmentMode = value;
            await this.plugin.saveSettings();
          })
      );
  }

  private addUISettings(parentEl: HTMLElement): void {
    const subsection = parentEl.createEl('details', { cls: 'thoth-subsection' });
    subsection.createEl('summary', { text: '🎨 User Interface' });

    new Setting(subsection)
      .setName('Show Status Bar')
      .setDesc('Display agent status in Obsidian status bar')
      .addToggle((toggle) =>
        toggle
          .setValue(this.plugin.settings.showStatusBar)
          .onChange(async (value) => {
            this.plugin.settings.showStatusBar = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(subsection)
      .setName('Show Ribbon Icon')
      .setDesc('Display chat icon in left ribbon')
      .addToggle((toggle) =>
        toggle
          .setValue(this.plugin.settings.showRibbonIcon)
          .onChange(async (value) => {
            this.plugin.settings.showRibbonIcon = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(subsection)
      .setName('Compact Mode')
      .setDesc('Use smaller UI elements to save space')
      .addToggle((toggle) =>
        toggle
          .setValue(this.plugin.settings.compactMode)
          .onChange(async (value) => {
            this.plugin.settings.compactMode = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(subsection)
      .setName('Chat History Limit')
      .setDesc('Maximum number of chat messages to remember')
      .addSlider((slider) =>
        slider
          .setLimits(10, 100, 10)
          .setValue(this.plugin.settings.chatHistoryLimit)
          .setDynamicTooltip()
          .onChange(async (value) => {
            this.plugin.settings.chatHistoryLimit = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(subsection)
      .setName('Enable Notifications')
      .setDesc('Show notifications for important events')
      .addToggle((toggle) =>
        toggle
          .setValue(this.plugin.settings.enableNotifications)
          .onChange(async (value) => {
            this.plugin.settings.enableNotifications = value;
            await this.plugin.saveSettings();
          })
      );
  }

  private addAgentControls(containerEl: HTMLElement): void {
    const section = containerEl.createEl('div', { cls: 'thoth-settings-section thoth-controls-section' });
    section.createEl('h2', { text: '🎮 Agent Controls' });

    const controlsGrid = section.createEl('div', { cls: 'thoth-controls-grid' });

    // Start Agent
    const startButton = controlsGrid.createEl('button', {
      text: 'Start Agent',
      cls: 'thoth-control-button thoth-button-start'
    });
    startButton.onclick = () => this.plugin.startAgent();

    // Stop Agent
    const stopButton = controlsGrid.createEl('button', {
      text: 'Stop Agent',
      cls: 'thoth-control-button thoth-button-stop'
    });
    stopButton.onclick = () => this.plugin.stopAgent();

    // Restart Agent
    const restartButton = controlsGrid.createEl('button', {
      text: 'Restart Agent',
      cls: 'thoth-control-button thoth-button-restart'
    });
    restartButton.onclick = () => this.plugin.restartAgent();

    // Test Connection
    const testButton = controlsGrid.createEl('button', {
      text: 'Test Connection',
      cls: 'thoth-control-button thoth-button-test'
    });
    testButton.onclick = async () => {
      testButton.disabled = true;
      testButton.textContent = 'Testing...';

      try {
        const endpoint = this.plugin.getEndpointUrl();
        const response = await fetch(`${endpoint}/health`);
        if (response.ok) {
          new Notice('✅ Connection successful!');
        } else {
          new Notice(`❌ Connection failed: ${response.statusText}`);
        }
      } catch (error) {
        new Notice(`❌ Connection failed: ${error.message}`);
      } finally {
        testButton.disabled = false;
        testButton.textContent = 'Test Connection';
      }
    };

    // Open Chat
    const chatButton = controlsGrid.createEl('button', {
      text: 'Open Chat',
      cls: 'thoth-control-button thoth-button-chat'
    });
    chatButton.onclick = () => this.plugin.openChatModal();
  }
}

// ============================================================================
// ADDITIONAL MODAL CLASSES FOR ENHANCED UX
// ============================================================================
