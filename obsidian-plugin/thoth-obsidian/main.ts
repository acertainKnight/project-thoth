import { App, Editor, MarkdownView, Modal, Notice, Plugin, PluginSettingTab, Setting } from 'obsidian';
import { exec, spawn, ChildProcess } from 'child_process';
import { promisify } from 'util';
import * as fs from 'fs';
import * as path from 'path';

const execAsync = promisify(exec);

interface ThothSettings {
  // === API CONFIGURATION ===
  // Primary API Keys
  mistralKey: string;
  openrouterKey: string;

  // Optional API Keys
  opencitationsKey: string;
  googleApiKey: string;
  googleSearchEngineId: string;
  semanticScholarKey: string;
  webSearchKey: string;
  webSearchProviders: string;

  // === DIRECTORY CONFIGURATION ===
  workspaceDirectory: string;
  obsidianDirectory: string;
  dataDirectory: string;
  knowledgeDirectory: string;
  logsDirectory: string;
  queriesDirectory: string;
  agentStorageDirectory: string;
  pdfDirectory: string;

  // === CONNECTION SETTINGS ===
  remoteMode: boolean;
  remoteEndpointUrl: string;
  endpointHost: string;
  endpointPort: number;
  endpointBaseUrl: string;
  corsOrigins: string[];

  // === LLM CONFIGURATION ===
  primaryLlmModel: string;
  analysisLlmModel: string;
  researchAgentModel: string;
  llmTemperature: number;
  analysisLlmTemperature: number;
  llmMaxOutputTokens: number;
  analysisLlmMaxOutputTokens: number;

  // === AGENT BEHAVIOR ===
  researchAgentAutoStart: boolean;
  researchAgentDefaultQueries: boolean;
  researchAgentMemoryEnabled: boolean;
  agentMaxToolCalls: number;
  agentTimeoutSeconds: number;

  // === DISCOVERY SYSTEM ===
  discoveryAutoStartScheduler: boolean;
  discoveryDefaultMaxArticles: number;
  discoveryDefaultIntervalMinutes: number;
  discoveryRateLimitDelay: number;
  discoveryChromeExtensionEnabled: boolean;
  discoveryChromeExtensionPort: number;

  // === LOGGING CONFIGURATION ===
  logLevel: string;
  logFormat: string;
  logRotation: string;
  logRetention: string;
  enablePerformanceMonitoring: boolean;
  metricsInterval: number;

  // === SECURITY & PERFORMANCE ===
  encryptionKey: string;
  sessionTimeout: number;
  apiRateLimit: number;
  healthCheckTimeout: number;
  developmentMode: boolean;

  // === PLUGIN BEHAVIOR ===
  autoStartAgent: boolean;
  showStatusBar: boolean;
  showRibbonIcon: boolean;
  autoSaveSettings: boolean;
  chatHistoryLimit: number;
  chatHistory: ChatMessage[];

  // === UI PREFERENCES ===
  theme: string;
  compactMode: boolean;
  showAdvancedSettings: boolean;
  enableNotifications: boolean;
  notificationDuration: number;
}

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}

const DEFAULT_SETTINGS: ThothSettings = {
  // === API CONFIGURATION ===
  mistralKey: '',
  openrouterKey: '',
  opencitationsKey: '',
  googleApiKey: '',
  googleSearchEngineId: '',
  semanticScholarKey: '',
  webSearchKey: '',
  webSearchProviders: 'serper',

  // === DIRECTORY CONFIGURATION ===
  workspaceDirectory: '',
  obsidianDirectory: '',
  dataDirectory: '',
  knowledgeDirectory: '',
  logsDirectory: '',
  queriesDirectory: '',
  agentStorageDirectory: '',
  pdfDirectory: '',

  // === CONNECTION SETTINGS ===
  remoteMode: false,
  remoteEndpointUrl: 'http://localhost:8000',
  endpointHost: '127.0.0.1',
  endpointPort: 8000,
  endpointBaseUrl: '',
  corsOrigins: ['http://localhost:3000', 'http://127.0.0.1:8080'],

  // === LLM CONFIGURATION ===
  primaryLlmModel: 'anthropic/claude-3-sonnet',
  analysisLlmModel: 'anthropic/claude-3-sonnet',
  researchAgentModel: 'anthropic/claude-3-sonnet',
  llmTemperature: 0.7,
  analysisLlmTemperature: 0.5,
  llmMaxOutputTokens: 4096,
  analysisLlmMaxOutputTokens: 8192,

  // === AGENT BEHAVIOR ===
  researchAgentAutoStart: false,
  researchAgentDefaultQueries: true,
  researchAgentMemoryEnabled: true,
  agentMaxToolCalls: 20,
  agentTimeoutSeconds: 300,

  // === DISCOVERY SYSTEM ===
  discoveryAutoStartScheduler: false,
  discoveryDefaultMaxArticles: 50,
  discoveryDefaultIntervalMinutes: 60,
  discoveryRateLimitDelay: 1.0,
  discoveryChromeExtensionEnabled: true,
  discoveryChromeExtensionPort: 8765,

  // === LOGGING CONFIGURATION ===
  logLevel: 'INFO',
  logFormat: '<green>{time}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>',
  logRotation: '10 MB',
  logRetention: '30 days',
  enablePerformanceMonitoring: false,
  metricsInterval: 60,

  // === SECURITY & PERFORMANCE ===
  encryptionKey: '',
  sessionTimeout: 3600,
  apiRateLimit: 100,
  healthCheckTimeout: 30,
  developmentMode: false,

  // === PLUGIN BEHAVIOR ===
  autoStartAgent: false,
  showStatusBar: true,
  showRibbonIcon: true,
  autoSaveSettings: true,
  chatHistoryLimit: 20,
  chatHistory: [],

  // === UI PREFERENCES ===
  theme: 'auto',
  compactMode: false,
  showAdvancedSettings: false,
  enableNotifications: true,
  notificationDuration: 5000,
};

export default class ThothPlugin extends Plugin {
  settings: ThothSettings;
  statusBarItem: HTMLElement;
  process: ChildProcess | null = null;
  isAgentRunning: boolean = false;
  isRestarting: boolean = false;
  socket: WebSocket | null = null;
  wsResolvers: Map<string, { resolve: (v: string) => void; reject: (e: Error) => void }> = new Map();

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

  onunload() {
    this.stopAgent();
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

  openChatModal() {
    new ChatModal(this.app, this).open();
  }
}

class ChatModal extends Modal {
  plugin: ThothPlugin;
  chatContainer: HTMLElement;
  inputElement: HTMLTextAreaElement;
  sendButton: HTMLButtonElement;

  constructor(app: App, plugin: ThothPlugin) {
    super(app);
    this.plugin = plugin;
  }

  onOpen() {
    const { contentEl } = this;
    contentEl.empty();

    // Set modal title
    contentEl.createEl('h2', { text: 'Thoth Research Assistant' });

    // Check if agent is running
    if (!this.plugin.isAgentRunning) {
      const warningEl = contentEl.createEl('div', {
        cls: 'thoth-warning',
        text: '⚠️ Thoth agent is not running. Please start it first.'
      });
      warningEl.style.cssText = 'color: orange; margin-bottom: 10px; padding: 10px; border: 1px solid orange; border-radius: 4px;';

      const startButton = warningEl.createEl('button', { text: 'Start Agent' });
      startButton.onclick = () => {
        this.plugin.startAgent();
        this.close();
      };
      return;
    }

    // Create chat container
    this.chatContainer = contentEl.createEl('div', { cls: 'thoth-chat-container' });
    this.chatContainer.style.cssText = 'height: 400px; overflow-y: auto; border: 1px solid var(--background-modifier-border); margin-bottom: 10px; padding: 10px;';

    // Load chat history
    this.loadChatHistory();

    // Create input area
    const inputContainer = contentEl.createEl('div', { cls: 'thoth-input-container' });
    inputContainer.style.cssText = 'display: flex; gap: 10px;';

    this.inputElement = inputContainer.createEl('textarea', {
      placeholder: 'Ask me about your research...'
    });
    this.inputElement.style.cssText = 'flex: 1; min-height: 60px; resize: vertical;';

    this.sendButton = inputContainer.createEl('button', { text: 'Send' });
    this.sendButton.style.cssText = 'align-self: flex-end;';

    // Add event listeners
    this.sendButton.onclick = () => this.sendMessage();
    this.inputElement.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.sendMessage();
      }
    });

    // Focus input
    this.inputElement.focus();
  }

  loadChatHistory() {
    const history = this.plugin.settings.chatHistory || [];
    history.forEach(message => {
      this.addMessageToChat(message.role, message.content);
    });
    this.scrollToBottom();
  }

  addMessageToChat(role: 'user' | 'assistant', content: string) {
    const messageEl = this.chatContainer.createEl('div', { cls: `thoth-message thoth-${role}` });

    if (role === 'user') {
      messageEl.style.cssText = 'text-align: right; margin: 10px 0; padding: 8px; background-color: var(--interactive-accent); color: white; border-radius: 8px;';
    } else {
      messageEl.style.cssText = 'text-align: left; margin: 10px 0; padding: 8px; background-color: var(--background-secondary); border-radius: 8px;';
    }

    messageEl.createEl('div', { text: role === 'user' ? 'You' : 'Assistant', cls: 'thoth-message-role' }).style.cssText = 'font-weight: bold; margin-bottom: 4px; font-size: 0.9em;';
    messageEl.createEl('div', { text: content, cls: 'thoth-message-content' });
  }

  async sendMessage() {
    const message = this.inputElement.value.trim();
    if (!message) return;

    // Add user message to chat
    this.addMessageToChat('user', message);
    this.inputElement.value = '';
    this.scrollToBottom();

    // Disable send button
    this.sendButton.disabled = true;
    this.sendButton.textContent = 'Sending...';

    try {
      let reply: string | null = null;

      if (this.plugin.socket && this.plugin.socket.readyState === WebSocket.OPEN) {
        reply = await this.sendViaWebSocket(message);
      } else {
        await this.plugin.connectWebSocket();
        if (this.plugin.socket && this.plugin.socket.readyState === WebSocket.OPEN) {
          reply = await this.sendViaWebSocket(message);
        } else {
          reply = await this.sendViaHttp(message);
        }
      }

      if (reply !== null) {
        this.addMessageToChat('assistant', reply);

        this.plugin.settings.chatHistory.push(
          { role: 'user', content: message, timestamp: Date.now() },
          { role: 'assistant', content: reply, timestamp: Date.now() }
        );
        if (this.plugin.settings.chatHistory.length > this.plugin.settings.chatHistoryLimit) {
          this.plugin.settings.chatHistory = this.plugin.settings.chatHistory.slice(-this.plugin.settings.chatHistoryLimit);
        }
        await this.plugin.saveSettings();
      }
    } catch (error) {
      console.error('Chat error:', error);
      this.addMessageToChat('assistant', `Error: ${error.message}`);
    } finally {
      this.sendButton.disabled = false;
      this.sendButton.textContent = 'Send';
      this.scrollToBottom();
    }
  }

  private async sendViaHttp(message: string): Promise<string> {
    const endpoint = this.plugin.getEndpointUrl();
    const response = await fetch(`${endpoint}/research/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: message,
        conversation_id: 'obsidian-chat',
        timestamp: Date.now()
      }),
    });

    if (!response.ok) {
      throw new Error(`Chat request failed: ${response.statusText}`);
    }

    const result = await response.json();
    return result.response;
  }

  private async sendViaWebSocket(message: string): Promise<string> {
    return new Promise((resolve, reject) => {
      if (!this.plugin.socket) {
        reject(new Error('WebSocket not connected'));
        return;
      }
      const id = Date.now().toString(36) + Math.random().toString(36).slice(2);
      this.plugin.wsResolvers.set(id, { resolve, reject });
      this.plugin.socket!.send(
        JSON.stringify({
          id,
          message,
          conversation_id: 'obsidian-chat',
          timestamp: Date.now()
        })
      );
    });
  }

  scrollToBottom() {
    this.chatContainer.scrollTop = this.chatContainer.scrollHeight;
  }

  onClose() {
    const { contentEl } = this;
    contentEl.empty();
  }
}

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
