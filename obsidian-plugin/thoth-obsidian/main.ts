import { App, Editor, MarkdownView, Modal, Notice, Plugin, PluginSettingTab, Setting, TFile } from 'obsidian';
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
  promptsDirectory: string;

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

  // === MULTI-CHAT CONFIGURATION ===
  enableMultipleChats: boolean;
  maxChatWindows: number;
  chatWindowStates: ChatWindowState[];
  activeChatSessionId: string | null;

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
  id?: string;
}

interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  is_active: boolean;
  metadata: Record<string, any>;
  message_count: number;
  last_message_preview: string;
}

interface ChatWindowState {
  sessionId: string;
  title: string;
  messages: ChatMessage[];
  isActive: boolean;
}

interface NotificationProgress {
  notice: Notice;
  updateProgress: (progress: number, message?: string) => void;
  updateMessage: (message: string) => void;
  close: () => void;
  setType: (type: 'info' | 'success' | 'warning' | 'error') => void;
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
  promptsDirectory: '',

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

  // Multi-chat defaults
  enableMultipleChats: true,
  maxChatWindows: 5,
  chatWindowStates: [],
  activeChatSessionId: null,

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

  openChatModal() {
    if (this.settings.enableMultipleChats) {
      new MultiChatModal(this.app, this).open();
    } else {
      new EnhancedThothModal(this.app, this).open();
    }
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
      id: 'thoth-open-tools-tab',
      name: 'Thoth: Open Tools Tab',
      callback: () => {
        const modal = new EnhancedThothModal(this.app, this);
        modal.open();
        setTimeout(() => modal.switchTab('tools'), 100);
      }
    });

    this.addCommand({
      id: 'thoth-open-status-tab',
      name: 'Thoth: Open Status Tab',
      callback: () => {
        const modal = new EnhancedThothModal(this.app, this);
        modal.open();
        setTimeout(() => modal.switchTab('status'), 100);
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
    const modal = new CitationInserterModal(this.app, this, editor);
    modal.open();
  }

  async openDiscoverySourceCreator() {
    const modal = new DiscoverySourceModal(this.app, this);
    modal.open();
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
class MultiChatModal extends Modal {
  plugin: ThothPlugin;
  chatSessions: ChatSession[] = [];
  activeSessionId: string | null = null;
  chatWindows: Map<string, HTMLElement> = new Map();
  sessionListContainer: HTMLElement;
  chatContentContainer: HTMLElement;
  sessionTabsContainer: HTMLElement;
  sessionSelector: HTMLSelectElement;
  sidebar: HTMLElement;

  constructor(app: App, plugin: ThothPlugin) {
    super(app);
    this.plugin = plugin;
  }

  async onOpen() {
    const { contentEl, modalEl } = this;
    contentEl.empty();

    // Position modal in bottom right
    this.setupModalPosition();

    // Set modal title
    this.titleEl.setText('🧠 Thoth Chat');

    // Load existing sessions
    await this.loadChatSessions();

    // Create main layout
    this.createLayout();

    // Load session list
    this.renderSessionList();

    // Load active session or create new one
    if (this.plugin.settings.activeChatSessionId) {
      await this.switchToSession(this.plugin.settings.activeChatSessionId);
    } else {
      await this.createNewSession();
    }

    // Make draggable
    this.makeDraggable();
  }

  setupModalPosition() {
    const modalEl = this.modalEl;
    modalEl.addClass('thoth-chat-popup');

    // Position in bottom right
    modalEl.style.position = 'fixed';
    modalEl.style.bottom = '20px';
    modalEl.style.right = '20px';
    modalEl.style.top = 'unset';
    modalEl.style.left = 'unset';
    modalEl.style.transform = 'none';
    modalEl.style.width = '450px';
    modalEl.style.height = '600px';
    modalEl.style.maxWidth = '90vw';
    modalEl.style.maxHeight = '80vh';
    modalEl.style.zIndex = '1000';
    modalEl.style.borderRadius = '12px';
    modalEl.style.boxShadow = '0 8px 32px rgba(0, 0, 0, 0.3)';
    modalEl.style.resize = 'both';
    modalEl.style.overflow = 'hidden';
  }

  makeDraggable() {
    const modalEl = this.modalEl;
    const titleEl = this.titleEl;

    let isDragging = false;
    let currentX = 0;
    let currentY = 0;
    let initialX = 0;
    let initialY = 0;
    let xOffset = 0;
    let yOffset = 0;

    // Make title bar the drag handle
    titleEl.style.cursor = 'move';
    titleEl.style.userSelect = 'none';
    titleEl.style.padding = '10px 15px';
    titleEl.style.background = 'var(--background-secondary)';
    titleEl.style.borderBottom = '1px solid var(--background-modifier-border)';
    titleEl.style.borderRadius = '12px 12px 0 0';

    titleEl.addEventListener('mousedown', dragStart);
    document.addEventListener('mousemove', drag);
    document.addEventListener('mouseup', dragEnd);

    function dragStart(e: MouseEvent) {
      if (e.target !== titleEl) return;

      initialX = e.clientX - xOffset;
      initialY = e.clientY - yOffset;

      if (e.target === titleEl) {
        isDragging = true;
        modalEl.style.cursor = 'grabbing';
      }
    }

    function drag(e: MouseEvent) {
      if (isDragging) {
        e.preventDefault();

        currentX = e.clientX - initialX;
        currentY = e.clientY - initialY;

        xOffset = currentX;
        yOffset = currentY;

        // Keep modal within viewport bounds
        const rect = modalEl.getBoundingClientRect();
        const maxX = window.innerWidth - rect.width;
        const maxY = window.innerHeight - rect.height;

        currentX = Math.max(0, Math.min(currentX, maxX));
        currentY = Math.max(0, Math.min(currentY, maxY));

        modalEl.style.right = 'unset';
        modalEl.style.bottom = 'unset';
        modalEl.style.left = currentX + 'px';
        modalEl.style.top = currentY + 'px';
      }
    }

    function dragEnd() {
      initialX = currentX;
      initialY = currentY;
      isDragging = false;
      modalEl.style.cursor = 'auto';
    }
  }

  onClose() {
    const { contentEl } = this;
    contentEl.empty();
  }

  createLayout() {
    const { contentEl } = this;

    // Add styles
    this.addStyles();

    // Main container with toggle layout
    const mainContainer = contentEl.createEl('div', { cls: 'multi-chat-container compact' });

    // Top bar with session selector and new chat
    const topBar = mainContainer.createEl('div', { cls: 'chat-top-bar' });

    // Session selector dropdown
    const sessionSelector = topBar.createEl('select', { cls: 'session-selector' });
    this.sessionSelector = sessionSelector;
    sessionSelector.onchange = () => {
      const selectedId = sessionSelector.value;
      if (selectedId && selectedId !== 'new') {
        this.switchToSession(selectedId);
      } else if (selectedId === 'new') {
        this.createNewSession();
      }
    };

    // New chat button
    const newChatBtn = topBar.createEl('button', {
      text: '+',
      cls: 'new-chat-btn compact',
      title: 'New Chat'
    });
    newChatBtn.onclick = () => this.createNewSession();

    // Toggle sidebar button
    const toggleBtn = topBar.createEl('button', {
      text: '☰',
      cls: 'toggle-sidebar-btn',
      title: 'Toggle Sessions'
    });
    toggleBtn.onclick = () => this.toggleSidebar();

    // Collapsible sidebar for session list
    const sidebar = mainContainer.createEl('div', { cls: 'chat-sidebar collapsed' });
    this.sidebar = sidebar;

    // Session list container (simplified)
    this.sessionListContainer = sidebar.createEl('div', { cls: 'session-list compact' });

    // Main chat area
    const chatArea = mainContainer.createEl('div', { cls: 'chat-area' });

    // Chat content area (no tabs for compact mode)
    this.chatContentContainer = chatArea.createEl('div', { cls: 'chat-content' });
  }

  toggleSidebar() {
    if (!this.sidebar) return;

    const isCollapsed = this.sidebar.hasClass('collapsed');
    if (isCollapsed) {
      this.sidebar.removeClass('collapsed');
      this.renderSessionList();
    } else {
      this.sidebar.addClass('collapsed');
    }
  }

  addStyles() {
    const style = document.createElement('style');
    style.textContent = `
      .thoth-chat-popup {
        border-radius: 12px !important;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3) !important;
      }

      .multi-chat-container.compact {
        display: flex;
        flex-direction: column;
        height: 100%;
        gap: 0;
        padding: 0;
      }

      .chat-top-bar {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 12px;
        border-bottom: 1px solid var(--background-modifier-border);
        background: var(--background-secondary);
        border-radius: 0 0 8px 8px;
        min-height: 40px;
      }

      .session-selector {
        flex: 1;
        padding: 4px 8px;
        border: 1px solid var(--background-modifier-border);
        border-radius: 4px;
        background: var(--background-primary);
        color: var(--text-normal);
        font-size: 12px;
        min-width: 0;
      }

      .new-chat-btn.compact {
        padding: 6px 10px;
        background: var(--interactive-accent);
        color: var(--text-on-accent);
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-size: 14px;
        font-weight: 600;
        min-width: 32px;
        height: 28px;
        display: flex;
        align-items: center;
        justify-content: center;
      }

      .toggle-sidebar-btn {
        padding: 6px 8px;
        background: var(--background-modifier-hover);
        border: 1px solid var(--background-modifier-border);
        border-radius: 4px;
        cursor: pointer;
        font-size: 12px;
        color: var(--text-muted);
        min-width: 32px;
        height: 28px;
        display: flex;
        align-items: center;
        justify-content: center;
      }

      .toggle-sidebar-btn:hover {
        background: var(--background-modifier-hover-hover);
        color: var(--text-normal);
      }

      .chat-sidebar {
        position: absolute;
        top: 60px;
        left: 8px;
        right: 8px;
        background: var(--background-primary);
        border: 1px solid var(--background-modifier-border);
        border-radius: 8px;
        z-index: 10;
        max-height: 300px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
        transition: all 0.2s ease;
      }

      .chat-sidebar.collapsed {
        display: none;
      }

      .session-list.compact {
        padding: 8px;
        max-height: 280px;
        overflow-y: auto;
      }

      .session-item {
        padding: 6px 8px;
        margin-bottom: 2px;
        border-radius: 4px;
        cursor: pointer;
        border: 1px solid transparent;
        position: relative;
        font-size: 12px;
      }

      .session-item:hover {
        background: var(--background-modifier-hover);
      }

      .session-item.active {
        background: var(--interactive-accent-hover);
        border-color: var(--interactive-accent);
      }

      .session-title {
        font-weight: 500;
        font-size: 12px;
        margin-bottom: 2px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .session-preview {
        font-size: 10px;
        color: var(--text-muted);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 80%;
      }

      .session-meta {
        font-size: 9px;
        color: var(--text-faint);
        margin-top: 2px;
        display: flex;
        justify-content: space-between;
      }

      .session-actions {
        position: absolute;
        top: 2px;
        right: 2px;
        opacity: 0;
        transition: opacity 0.2s;
        display: flex;
        gap: 2px;
      }

      .session-item:hover .session-actions {
        opacity: 1;
      }

      .session-action-btn {
        padding: 2px 4px;
        background: none;
        border: none;
        cursor: pointer;
        color: var(--text-muted);
        font-size: 10px;
        border-radius: 2px;
      }

      .session-action-btn:hover {
        color: var(--text-normal);
        background: var(--background-modifier-hover);
      }

      .chat-area {
        flex: 1;
        display: flex;
        flex-direction: column;
        min-height: 0;
      }

      .chat-content {
        flex: 1;
        display: flex;
        flex-direction: column;
        padding: 8px;
        gap: 8px;
        min-height: 0;
      }

      .chat-messages {
        flex: 1;
        overflow-y: auto;
        padding: 8px;
        border: 1px solid var(--background-modifier-border);
        border-radius: 6px;
        background: var(--background-primary);
        min-height: 200px;
        max-height: none;
      }

      .chat-message {
        margin-bottom: 8px;
        padding: 6px 8px;
        border-radius: 6px;
        max-width: 85%;
        word-wrap: break-word;
      }

      .chat-message.user {
        background: var(--interactive-accent-hover);
        margin-left: auto;
        text-align: right;
      }

      .chat-message.assistant {
        background: var(--background-secondary);
        margin-right: auto;
      }

      .message-role {
        font-weight: 600;
        font-size: 10px;
        margin-bottom: 3px;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }

      .message-content {
        line-height: 1.3;
        font-size: 12px;
      }

      .chat-input-area {
        display: flex;
        gap: 6px;
        align-items: flex-end;
      }

      .chat-input {
        flex: 1;
        min-height: 36px;
        max-height: 80px;
        resize: vertical;
        padding: 6px 8px;
        border-radius: 6px;
        border: 1px solid var(--background-modifier-border);
        background: var(--background-primary);
        font-size: 12px;
        line-height: 1.3;
      }

      .chat-input:focus {
        outline: none;
        border-color: var(--interactive-accent);
        box-shadow: 0 0 0 1px var(--interactive-accent);
      }

      .chat-send-btn {
        padding: 6px 12px;
        background: var(--interactive-accent);
        color: var(--text-on-accent);
        border: none;
        border-radius: 6px;
        cursor: pointer;
        height: fit-content;
        font-size: 12px;
        font-weight: 500;
        min-height: 36px;
      }

      .chat-send-btn:hover {
        background: var(--interactive-accent-hover);
      }

      .chat-send-btn:disabled {
        opacity: 0.6;
        cursor: not-allowed;
        background: var(--text-muted);
      }

      .empty-chat {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 100%;
        color: var(--text-muted);
        text-align: center;
        padding: 20px;
      }

      .empty-chat div:first-child {
        font-size: 32px;
        margin-bottom: 8px;
      }

      .empty-chat h3 {
        margin: 0 0 4px 0;
        font-size: 14px;
      }

      .empty-chat p {
        margin: 0;
        font-size: 11px;
        color: var(--text-faint);
      }
    `;
    document.head.appendChild(style);
  }

  async loadChatSessions() {
    try {
      const endpoint = this.plugin.getEndpointUrl();
      const response = await fetch(`${endpoint}/chat/sessions?active_only=true&limit=50`);

      if (response.ok) {
        const data = await response.json();
        this.chatSessions = data.sessions || [];
      } else {
        console.warn('Could not load chat sessions from server');
        this.chatSessions = [];
      }
    } catch (error) {
      console.warn('Failed to load chat sessions:', error);
      this.chatSessions = [];
    }
  }

  renderSessionList() {
    // Update dropdown selector
    this.updateSessionSelector();

    // Update sidebar if open
    if (!this.sidebar?.hasClass('collapsed')) {
      this.sessionListContainer.empty();

      if (this.chatSessions.length === 0) {
        const emptyEl = this.sessionListContainer.createEl('div', {
          text: 'No chat sessions yet',
          cls: 'session-list-empty'
        });
        emptyEl.style.cssText = 'text-align: center; color: var(--text-muted); padding: 20px; font-size: 11px;';
        return;
      }

      this.chatSessions.forEach(session => {
        const sessionEl = this.sessionListContainer.createEl('div', {
          cls: `session-item ${session.id === this.activeSessionId ? 'active' : ''}`
        });

        sessionEl.onclick = () => this.switchToSession(session.id);

        // Session actions
        const actionsEl = sessionEl.createEl('div', { cls: 'session-actions' });

        const editBtn = actionsEl.createEl('button', {
          text: '✏️',
          cls: 'session-action-btn',
          title: 'Rename session'
        });
        editBtn.onclick = (e) => {
          e.stopPropagation();
          this.renameSession(session.id);
        };

        const deleteBtn = actionsEl.createEl('button', {
          text: '🗑️',
          cls: 'session-action-btn',
          title: 'Delete session'
        });
        deleteBtn.onclick = (e) => {
          e.stopPropagation();
          this.deleteSession(session.id);
        };

        // Session content
        sessionEl.createEl('div', {
          text: session.title,
          cls: 'session-title'
        });

        if (session.last_message_preview) {
          sessionEl.createEl('div', {
            text: session.last_message_preview,
            cls: 'session-preview'
          });
        }

        const metaEl = sessionEl.createEl('div', { cls: 'session-meta' });
        metaEl.createEl('span', { text: `${session.message_count} msgs` });

        const date = new Date(session.updated_at);
        metaEl.createEl('span', { text: date.toLocaleDateString() });
      });
    }
  }

  updateSessionSelector() {
    if (!this.sessionSelector) return;

    // Clear existing options
    this.sessionSelector.empty();

    // Add default option
    const defaultOption = this.sessionSelector.createEl('option', {
      value: '',
      text: 'Select a chat...'
    });

    // Add sessions
    this.chatSessions.forEach(session => {
      const option = this.sessionSelector.createEl('option', {
        value: session.id,
        text: session.title
      });

      if (session.id === this.activeSessionId) {
        option.selected = true;
      }
    });

    // Add "New Chat" option
    this.sessionSelector.createEl('option', {
      value: 'new',
      text: '+ New Chat'
    });
  }

  async createNewSession(title?: string) {
    try {
      const sessionTitle = title || `Chat ${this.chatSessions.length + 1}`;
      const endpoint = this.plugin.getEndpointUrl();

      const response = await fetch(`${endpoint}/chat/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: sessionTitle,
          metadata: { source: 'obsidian-multi-chat' }
        })
      });

      if (response.ok) {
        const result = await response.json();
        const newSession = result.session;

        this.chatSessions.unshift(newSession);
        this.renderSessionList();
        await this.switchToSession(newSession.id);

        new Notice(`Created new chat: ${sessionTitle}`);
      } else {
        throw new Error('Failed to create session');
      }
    } catch (error) {
      console.error('Error creating session:', error);
      new Notice('Failed to create new chat session');
    }
  }

  async switchToSession(sessionId: string) {
    this.activeSessionId = sessionId;
    this.plugin.settings.activeChatSessionId = sessionId;
    await this.plugin.saveSettings();

    // Update session list and selector
    this.renderSessionList();

    // Load and render chat messages
    await this.loadChatMessages(sessionId);
  }


  async loadChatMessages(sessionId: string) {
    this.chatContentContainer.empty();

    try {
      const endpoint = this.plugin.getEndpointUrl();
      const response = await fetch(`${endpoint}/chat/sessions/${sessionId}/messages?limit=100`);

      if (response.ok) {
        const data = await response.json();
        this.renderChatInterface(sessionId, data.messages || []);
      } else {
        throw new Error('Failed to load messages');
      }
    } catch (error) {
      console.error('Error loading messages:', error);
      this.renderChatInterface(sessionId, []);
    }
  }

  renderChatInterface(sessionId: string, messages: any[]) {
    this.chatContentContainer.empty();

    // Messages container
    const messagesContainer = this.chatContentContainer.createEl('div', {
      cls: 'chat-messages'
    });

    // Load existing messages
    messages.forEach(msg => {
      this.addMessageToChat(messagesContainer, msg.role, msg.content);
    });

    // Input area
    const inputArea = this.chatContentContainer.createEl('div', {
      cls: 'chat-input-area'
    });

    const inputEl = inputArea.createEl('textarea', {
      cls: 'chat-input',
      placeholder: 'Type your message...'
    }) as HTMLTextAreaElement;

    const sendBtn = inputArea.createEl('button', {
      text: 'Send',
      cls: 'chat-send-btn'
    });

    // Event handlers
    const sendMessage = async () => {
      const message = inputEl.value.trim();
      if (!message || sendBtn.disabled) return;

      // Add user message to UI
      this.addMessageToChat(messagesContainer, 'user', message);
      inputEl.value = '';
      messagesContainer.scrollTop = messagesContainer.scrollHeight;

      // Disable send button
      sendBtn.disabled = true;
      sendBtn.textContent = 'Sending...';

      try {
        // Send to server
        const endpoint = this.plugin.getEndpointUrl();
        const response = await fetch(`${endpoint}/research/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: message,
            conversation_id: sessionId,
            timestamp: Date.now(),
            id: crypto.randomUUID()
          })
        });

        if (response.ok) {
          const result = await response.json();
          this.addMessageToChat(messagesContainer, 'assistant', result.response);
          messagesContainer.scrollTop = messagesContainer.scrollHeight;

          // Update session list to reflect new message
          await this.loadChatSessions();
          this.renderSessionList();
        } else {
          throw new Error('Failed to send message');
        }
      } catch (error) {
        console.error('Chat error:', error);
        this.addMessageToChat(messagesContainer, 'assistant', `Error: ${error.message}`);
      } finally {
        sendBtn.disabled = false;
        sendBtn.textContent = 'Send';
        inputEl.focus();
      }
    };

    sendBtn.onclick = sendMessage;
    inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    // Focus input
    setTimeout(() => inputEl.focus(), 100);
  }

  addMessageToChat(container: HTMLElement, role: string, content: string) {
    const messageEl = container.createEl('div', {
      cls: `chat-message ${role}`
    });

    messageEl.createEl('div', {
      text: role === 'user' ? 'You' : 'Assistant',
      cls: 'message-role'
    });

    messageEl.createEl('div', {
      text: content,
      cls: 'message-content'
    });
  }

  renderEmptyState() {
    this.chatContentContainer.empty();

    const emptyEl = this.chatContentContainer.createEl('div', {
      cls: 'empty-chat'
    });

    emptyEl.createEl('div', { text: '💬' });
    emptyEl.createEl('h3', { text: 'No chat selected' });
    emptyEl.createEl('p', { text: 'Select a chat from the dropdown or create a new one' });
  }

  async renameSession(sessionId: string) {
    const session = this.chatSessions.find(s => s.id === sessionId);
    if (!session) return;

    const newTitle = prompt('Enter new title:', session.title);
    if (!newTitle || newTitle === session.title) return;

    try {
      const endpoint = this.plugin.getEndpointUrl();
      const response = await fetch(`${endpoint}/chat/sessions/${sessionId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: newTitle })
      });

      if (response.ok) {
        session.title = newTitle;
        this.renderSessionList();
        new Notice('Session renamed');
      } else {
        throw new Error('Failed to rename session');
      }
    } catch (error) {
      console.error('Error renaming session:', error);
      new Notice('Failed to rename session');
    }
  }

  async deleteSession(sessionId: string) {
    const session = this.chatSessions.find(s => s.id === sessionId);
    if (!session) return;

    if (!confirm(`Delete "${session.title}"? This cannot be undone.`)) return;

    try {
      const endpoint = this.plugin.getEndpointUrl();
      const response = await fetch(`${endpoint}/chat/sessions/${sessionId}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        this.chatSessions = this.chatSessions.filter(s => s.id !== sessionId);

        if (this.activeSessionId === sessionId) {
          this.activeSessionId = null;
          this.plugin.settings.activeChatSessionId = null;
          await this.plugin.saveSettings();
          this.renderEmptyState();
        }

        this.renderSessionList();
        new Notice('Session deleted');
      } else {
        throw new Error('Failed to delete session');
      }
    } catch (error) {
      console.error('Error deleting session:', error);
      new Notice('Failed to delete session');
    }
  }
}

class EnhancedThothModal extends Modal {
  plugin: ThothPlugin;
  currentTab: string = 'chat';
  tabContainer: HTMLElement;
  contentContainer: HTMLElement;

  // Chat-specific elements
  chatContainer: HTMLElement;
  inputElement: HTMLTextAreaElement;
  sendButton: HTMLButtonElement;

  // Command execution elements
  commandContainer: HTMLElement;
  operationsContainer: HTMLElement;

  // Status elements
  statusContainer: HTMLElement;

  constructor(app: App, plugin: ThothPlugin) {
    super(app);
    this.plugin = plugin;
    this.modalEl.addClass('thoth-enhanced-modal');
  }

  onOpen() {
    const { contentEl } = this;
    contentEl.empty();

    // Apply custom styling
    this.applyCustomStyles();

    // Set modal title and header
    this.createHeader(contentEl);

    // Create tab navigation
    this.createTabNavigation(contentEl);

    // Create content container
    this.contentContainer = contentEl.createEl('div', { cls: 'thoth-content-container' });

    // Initialize with default tab
    this.switchTab('chat');
  }

  applyCustomStyles() {
    const style = document.createElement('style');
    style.textContent = `
      .thoth-enhanced-modal {
        width: 80vw !important;
        max-width: 1000px !important;
        height: 80vh !important;
        max-height: 700px !important;
      }

      .thoth-tab-navigation {
        display: flex;
        border-bottom: 2px solid var(--background-modifier-border);
        margin-bottom: 15px;
        gap: 5px;
      }

      .thoth-tab-button {
        padding: 8px 16px;
        border: none;
        background: transparent;
        color: var(--text-muted);
        cursor: pointer;
        border-radius: 4px 4px 0 0;
        transition: all 0.2s ease;
        font-size: 14px;
        font-weight: 500;
      }

      .thoth-tab-button:hover {
        background: var(--background-modifier-hover);
        color: var(--text-normal);
      }

      .thoth-tab-button.active {
        background: var(--interactive-accent);
        color: var(--text-on-accent);
        border-bottom: 2px solid var(--interactive-accent);
      }

      .thoth-content-container {
        height: calc(100% - 120px);
        overflow: hidden;
      }

      .thoth-tab-content {
        height: 100%;
        display: none;
      }

      .thoth-tab-content.active {
        display: block;
      }

      .thoth-chat-container {
        height: calc(100% - 80px);
        overflow-y: auto;
        border: 1px solid var(--background-modifier-border);
        border-radius: 4px;
        padding: 10px;
        margin-bottom: 10px;
      }

      .thoth-input-container {
        display: flex;
        gap: 10px;
        align-items: flex-end;
      }

      .thoth-input-container textarea {
        flex: 1;
        min-height: 40px;
        max-height: 120px;
        resize: vertical;
        border-radius: 4px;
        border: 1px solid var(--background-modifier-border);
        padding: 8px;
      }

      .thoth-message {
        margin: 10px 0;
        padding: 8px 12px;
        border-radius: 8px;
        max-width: 80%;
      }

      .thoth-user {
        background: var(--interactive-accent);
        color: var(--text-on-accent);
        margin-left: auto;
        text-align: right;
      }

      .thoth-assistant {
        background: var(--background-secondary);
        color: var(--text-normal);
        margin-right: auto;
      }

      .thoth-message-role {
        font-weight: bold;
        font-size: 0.85em;
        margin-bottom: 4px;
        opacity: 0.8;
      }

      .thoth-command-section {
        margin-bottom: 20px;
        padding: 15px;
        border: 1px solid var(--background-modifier-border);
        border-radius: 8px;
      }

      .thoth-command-section h3 {
        margin: 0 0 10px 0;
        color: var(--text-accent);
      }

      .thoth-command-buttons {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 10px;
        margin-top: 10px;
      }

      .thoth-command-button {
        padding: 8px 12px;
        border: 1px solid var(--background-modifier-border);
        background: var(--background-secondary);
        color: var(--text-normal);
        border-radius: 4px;
        cursor: pointer;
        transition: all 0.2s ease;
      }

      .thoth-command-button:hover {
        background: var(--background-modifier-hover);
        border-color: var(--interactive-accent);
      }

      .thoth-status-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 15px;
      }

      .thoth-status-card {
        padding: 15px;
        border: 1px solid var(--background-modifier-border);
        border-radius: 8px;
        background: var(--background-secondary);
      }

      .thoth-status-card h4 {
        margin: 0 0 10px 0;
        color: var(--text-accent);
      }

      .thoth-status-indicator {
        display: inline-block;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.85em;
        font-weight: 500;
      }

      .thoth-status-success {
        background: var(--color-green);
        color: white;
      }

      .thoth-status-error {
        background: var(--color-red);
        color: white;
      }

      .thoth-status-warning {
        background: var(--color-orange);
        color: white;
      }

      .thoth-progress-bar {
        width: 100%;
        height: 8px;
        background: var(--background-modifier-border);
        border-radius: 4px;
        overflow: hidden;
        margin: 10px 0;
      }

      .thoth-progress-fill {
        height: 100%;
        background: var(--interactive-accent);
        transition: width 0.3s ease;
      }

      .thoth-operation-log {
        height: 300px;
        overflow-y: auto;
        border: 1px solid var(--background-modifier-border);
        border-radius: 4px;
        padding: 10px;
        font-family: var(--font-monospace);
        font-size: 0.9em;
        background: var(--background-primary);
      }
    `;
    document.head.appendChild(style);
  }

  createHeader(contentEl: HTMLElement) {
    const header = contentEl.createEl('div', { cls: 'thoth-header' });
    header.style.cssText = 'display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 1px solid var(--background-modifier-border);';

    const titleEl = header.createEl('h2', { text: '🧠 Thoth Research Assistant' });
    titleEl.style.cssText = 'margin: 0; color: var(--text-accent);';

    const statusEl = header.createEl('div', { cls: 'thoth-header-status' });
    this.updateHeaderStatus(statusEl);
  }

  updateHeaderStatus(statusEl: HTMLElement) {
    statusEl.empty();

    const status = this.plugin.isAgentRunning ? 'Running' : 'Stopped';
    const statusClass = this.plugin.isAgentRunning ? 'thoth-status-success' : 'thoth-status-error';

    const statusSpan = statusEl.createEl('span', {
      text: `Agent: ${status}`,
      cls: `thoth-status-indicator ${statusClass}`
    });
  }

  createTabNavigation(contentEl: HTMLElement) {
    this.tabContainer = contentEl.createEl('div', { cls: 'thoth-tab-navigation' });

    const tabs = [
      { id: 'chat', label: '💬 Chat', icon: 'message-circle' },
      { id: 'commands', label: '⚡ Commands', icon: 'terminal' },
      { id: 'tools', label: '🔧 Tools', icon: 'wrench' },
      { id: 'status', label: '📊 Status', icon: 'activity' }
    ];

    tabs.forEach(tab => {
      const button = this.tabContainer.createEl('button', {
        text: tab.label,
        cls: 'thoth-tab-button'
      });

      if (tab.id === this.currentTab) {
        button.addClass('active');
      }

      button.onclick = () => this.switchTab(tab.id);
    });
  }

  switchTab(tabId: string) {
    // Update tab buttons
    this.tabContainer.querySelectorAll('.thoth-tab-button').forEach((btn, index) => {
      if (index === ['chat', 'commands', 'tools', 'status'].indexOf(tabId)) {
        btn.addClass('active');
      } else {
        btn.removeClass('active');
      }
    });

    // Update content
    this.currentTab = tabId;
    this.renderTabContent();
  }

  renderTabContent() {
    this.contentContainer.empty();

    const tabContent = this.contentContainer.createEl('div', {
      cls: `thoth-tab-content active thoth-${this.currentTab}-tab`
    });

    switch (this.currentTab) {
      case 'chat':
        this.renderChatTab(tabContent);
        break;
      case 'commands':
        this.renderCommandsTab(tabContent);
        break;
      case 'tools':
        this.renderToolsTab(tabContent);
        break;
      case 'status':
        this.renderStatusTab(tabContent);
        break;
    }
  }

  renderChatTab(container: HTMLElement) {
    // Check if agent is running
    if (!this.plugin.isAgentRunning) {
      const warningEl = container.createEl('div', {
        cls: 'thoth-warning',
        text: '⚠️ Thoth agent is not running. Please start it first.'
      });
      warningEl.style.cssText = 'color: orange; margin-bottom: 10px; padding: 15px; border: 1px solid orange; border-radius: 4px; text-align: center;';

      const startButton = warningEl.createEl('button', { text: 'Start Agent' });
      startButton.style.cssText = 'margin-top: 10px; padding: 8px 16px; background: var(--interactive-accent); color: var(--text-on-accent); border: none; border-radius: 4px; cursor: pointer;';
      startButton.onclick = () => {
        this.plugin.startAgent();
        setTimeout(() => this.renderTabContent(), 2000); // Refresh after 2 seconds
      };
      return;
    }

    // Add quick action buttons at the top
    this.createQuickActionButtons(container, 'chat');

    // Create chat container
    this.chatContainer = container.createEl('div', { cls: 'thoth-chat-container' });

    // Load chat history
    this.loadChatHistory();

    // Create input area
    const inputContainer = container.createEl('div', { cls: 'thoth-input-container' });

    this.inputElement = inputContainer.createEl('textarea', {
      placeholder: 'Ask me about your research...'
    });

    this.sendButton = inputContainer.createEl('button', { text: 'Send' });
    this.sendButton.style.cssText = 'padding: 8px 16px; background: var(--interactive-accent); color: var(--text-on-accent); border: none; border-radius: 4px; cursor: pointer;';

    // Add event listeners
    this.sendButton.onclick = () => this.sendMessage();
    this.inputElement.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.sendMessage();
      }
    });

    // Focus input
    setTimeout(() => this.inputElement.focus(), 100);
  }

  renderCommandsTab(container: HTMLElement) {
    // Add quick action buttons at the top
    this.createQuickActionButtons(container, 'commands');

    const sections = [
      {
        title: 'Discovery Commands',
        commands: [
          { name: 'List Sources', command: 'discovery', args: ['list'], description: 'View all discovery sources' },
          { name: 'Run Discovery', command: 'discovery', args: ['run'], description: 'Execute discovery for sources' },
          { name: 'Create Source', command: 'discovery', args: ['create'], description: 'Add new discovery source' }
        ]
      },
      {
        title: 'PDF Management',
        commands: [
          { name: 'Locate PDF', command: 'pdf-locate', args: [], description: 'Find open-access PDFs' },
          { name: 'PDF Statistics', command: 'pdf-stats', args: [], description: 'Show PDF availability stats' }
        ]
      },
      {
        title: 'RAG System',
        commands: [
          { name: 'Index Knowledge', command: 'rag', args: ['index'], description: 'Build RAG index' },
          { name: 'Search Knowledge', command: 'rag', args: ['search'], description: 'Query knowledge base' },
          { name: 'RAG Statistics', command: 'rag', args: ['stats'], description: 'Show RAG system stats' }
        ]
      },
      {
        title: 'Notes Management',
        commands: [
          { name: 'Regenerate Notes', command: 'notes', args: ['regenerate-all-notes'], description: 'Rebuild all notes' },
          { name: 'Consolidate Tags', command: 'notes', args: ['consolidate-tags'], description: 'Organize tags' }
        ]
      }
    ];

    sections.forEach(section => {
      const sectionEl = container.createEl('div', { cls: 'thoth-command-section' });
      sectionEl.createEl('h3', { text: section.title });

      const buttonsContainer = sectionEl.createEl('div', { cls: 'thoth-command-buttons' });

      section.commands.forEach(cmd => {
        const button = buttonsContainer.createEl('div', { cls: 'thoth-command-button' });

        const nameEl = button.createEl('div', { text: cmd.name });
        nameEl.style.fontWeight = 'bold';

        const descEl = button.createEl('div', { text: cmd.description });
        descEl.style.fontSize = '0.9em';
        descEl.style.color = 'var(--text-muted)';
        descEl.style.marginTop = '4px';

        button.onclick = () => this.executeCommand(cmd.command, cmd.args);
      });
    });
  }

  renderToolsTab(container: HTMLElement) {
    if (!this.plugin.isAgentRunning) {
      container.createEl('div', {
        text: 'Agent must be running to access tools',
        cls: 'thoth-warning'
      }).style.cssText = 'text-align: center; padding: 20px; color: var(--text-muted);';
      return;
    }

    // Add quick action buttons at the top
    this.createQuickActionButtons(container, 'tools');

    // Tools will be loaded dynamically
    container.createEl('div', { text: 'Loading available tools...' });
    this.loadAvailableTools(container);
  }

  renderStatusTab(container: HTMLElement) {
    // Add quick action buttons at the top
    this.createQuickActionButtons(container, 'status');

    const statusGrid = container.createEl('div', { cls: 'thoth-status-grid' });

    // Agent Status Card
    const agentCard = statusGrid.createEl('div', { cls: 'thoth-status-card' });
    agentCard.createEl('h4', { text: 'Agent Status' });

    const agentStatus = this.plugin.isAgentRunning ? 'Running' : 'Stopped';
    const agentClass = this.plugin.isAgentRunning ? 'thoth-status-success' : 'thoth-status-error';
    agentCard.createEl('div', {
      text: agentStatus,
      cls: `thoth-status-indicator ${agentClass}`
    });

    // Connection Status Card
    const connectionCard = statusGrid.createEl('div', { cls: 'thoth-status-card' });
    connectionCard.createEl('h4', { text: 'Connection' });
    connectionCard.createEl('div', { text: `Mode: ${this.plugin.settings.remoteMode ? 'Remote' : 'Local'}` });
    connectionCard.createEl('div', { text: `Endpoint: ${this.plugin.getEndpointUrl()}` });

    // Configuration Status Card
    const configCard = statusGrid.createEl('div', { cls: 'thoth-status-card' });
    configCard.createEl('h4', { text: 'Configuration' });

    const hasKeys = this.plugin.settings.mistralKey || this.plugin.settings.openrouterKey;
    const keyStatus = hasKeys ? 'Configured' : 'Missing Keys';
    const keyClass = hasKeys ? 'thoth-status-success' : 'thoth-status-error';
    configCard.createEl('div', {
      text: `API Keys: ${keyStatus}`,
      cls: `thoth-status-indicator ${keyClass}`
    });

    // Operations Status (if any running)
    this.addOperationsStatus(statusGrid);
  }

  createQuickActionButtons(container: HTMLElement, tabType: string) {
    const quickActionsContainer = container.createEl('div', { cls: 'thoth-quick-actions' });
    quickActionsContainer.style.cssText = `
      display: flex;
      gap: 8px;
      margin-bottom: 15px;
      padding: 10px;
      background: var(--background-secondary);
      border-radius: 8px;
      flex-wrap: wrap;
    `;

    // Define quick actions for each tab type
    const quickActions = {
      chat: [
        { label: '💡 Quick Research', action: () => this.triggerQuickResearch() },
        { label: '📄 Process Current PDF', action: () => this.plugin.processCurrentFile() },
        { label: '🔄 Clear Chat', action: () => this.clearChatHistory() },
        { label: '💾 Save Chat', action: () => this.saveChatHistory() }
      ],
      commands: [
        { label: '🚀 Run Discovery', action: () => this.executeCommand('discovery', ['run']) },
        { label: '📑 Index Knowledge', action: () => this.executeCommand('rag', ['index']) },
        { label: '🔍 PDF Locate', action: () => this.promptPdfLocate() },
        { label: '📊 System Stats', action: () => this.showSystemStats() }
      ],
      tools: [
        { label: '🔧 Refresh Tools', action: () => this.loadAvailableTools(container) },
        { label: '⚡ Health Check', action: () => this.plugin.performHealthCheck() },
        { label: '🔄 Restart Agent', action: () => this.plugin.restartAgent() },
        { label: '⚙️ Validate Config', action: () => this.plugin.validateConfiguration() }
      ],
      status: [
        { label: '🔄 Refresh Status', action: () => this.renderTabContent() },
        { label: '🧪 Health Check', action: () => this.plugin.performHealthCheck() },
        { label: '📋 Export Config', action: () => this.exportConfiguration() },
        { label: '🔧 System Diagnostics', action: () => this.runSystemDiagnostics() }
      ]
    };

    const actions = quickActions[tabType] || [];

    actions.forEach(action => {
      const button = quickActionsContainer.createEl('button', {
        text: action.label,
        cls: 'thoth-quick-action-btn'
      });
      button.style.cssText = `
        padding: 6px 12px;
        background: var(--interactive-normal);
        color: var(--text-normal);
        border: 1px solid var(--background-modifier-border);
        border-radius: 4px;
        cursor: pointer;
        font-size: 0.85em;
        transition: all 0.2s ease;
      `;

      button.onmouseenter = () => {
        button.style.background = 'var(--interactive-hover)';
      };

      button.onmouseleave = () => {
        button.style.background = 'var(--interactive-normal)';
      };

      button.onclick = action.action;
    });
  }

  async triggerQuickResearch() {
    const query = await this.plugin.showInputPrompt('Enter your research query:');
    if (query && this.inputElement) {
      this.inputElement.value = query;
      this.sendMessage();
    }
  }

  clearChatHistory() {
    this.plugin.settings.chatHistory = [];
    this.plugin.saveSettings();
    this.chatContainer?.empty();
    new Notice('Chat history cleared');
  }

  saveChatHistory() {
    const historyText = this.plugin.settings.chatHistory
      .map(msg => `**${msg.role}**: ${msg.content}`)
      .join('\n\n');

    const activeFile = this.app.workspace.getActiveFile();
    const fileName = activeFile ? activeFile.basename : 'chat-history';

    this.app.vault.create(`${fileName}-chat-${Date.now()}.md`, historyText)
      .then(() => new Notice('Chat history saved to file'))
      .catch(err => new Notice(`Failed to save chat history: ${err.message}`));
  }

  async promptPdfLocate() {
    const doi = await this.plugin.showInputPrompt('Enter DOI or identifier:');
    if (doi) {
      this.executeCommand('pdf-locate', [doi]);
    }
  }

  async showSystemStats() {
    // Show combined stats from multiple commands
    this.executeCommand('rag', ['stats']);
    this.executeCommand('pdf-stats', []);
    this.executeCommand('discovery', ['list']);
  }

  exportConfiguration() {
    const config = {
      timestamp: new Date().toISOString(),
      settings: { ...this.plugin.settings }
    };

    // Remove sensitive data
    delete (config.settings as any).mistralKey;
    delete (config.settings as any).openrouterKey;
    delete (config.settings as any).encryptionKey;

    const configText = JSON.stringify(config, null, 2);
    this.app.vault.create(`thoth-config-export-${Date.now()}.json`, configText)
      .then(() => new Notice('Configuration exported'))
      .catch(err => new Notice(`Export failed: ${err.message}`));
  }

  async runSystemDiagnostics() {
    new Notice('Running system diagnostics...');

    // Run multiple diagnostic commands
    const diagnostics = [
      { name: 'Health Check', command: () => this.plugin.performHealthCheck() },
      { name: 'Config Validation', command: () => this.plugin.validateConfiguration() },
      { name: 'Agent Status', command: () => this.updateHeaderStatus(this.modalEl.querySelector('.thoth-header-status') as HTMLElement) }
    ];

    for (const diagnostic of diagnostics) {
      try {
        await diagnostic.command();
      } catch (error) {
        console.warn(`${diagnostic.name} failed:`, error);
      }
    }

    new Notice('System diagnostics completed. Check console for details.');
  }

  async executeCommand(command: string, args: string[]) {
    if (!this.plugin.isAgentRunning) {
      new Notice('Agent must be running to execute commands');
      return;
    }

    try {
      const endpoint = this.plugin.getEndpointUrl();
      const response = await fetch(`${endpoint}/execute/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          command: command,
          args: args,
          stream_output: true
        })
      });

      if (response.ok) {
        const result = await response.json();
        if (result.streaming) {
          this.trackOperation(result.operation_id);
          new Notice(`${command} command started. Check Status tab for progress.`);
        } else {
          new Notice(`${command} command completed`);
        }
      } else {
        throw new Error(`Command failed: ${response.statusText}`);
      }
    } catch (error) {
      console.error('Command execution error:', error);
      new Notice(`Command failed: ${error.message}`);
    }
  }

  async loadAvailableTools(container: HTMLElement) {
    try {
      const endpoint = this.plugin.getEndpointUrl();
      const response = await fetch(`${endpoint}/agent/tools`);

      if (response.ok) {
        const result = await response.json();
        this.renderToolsList(container, result.tools);
      } else {
        container.createEl('div', { text: 'Failed to load tools' });
      }
    } catch (error) {
      container.createEl('div', { text: `Error loading tools: ${error.message}` });
    }
  }

  renderToolsList(container: HTMLElement, tools: any[]) {
    container.empty();

    if (!tools || tools.length === 0) {
      container.createEl('div', { text: 'No tools available' });
      return;
    }

    const toolsGrid = container.createEl('div', { cls: 'thoth-command-buttons' });

    tools.forEach(tool => {
      const toolButton = toolsGrid.createEl('div', { cls: 'thoth-command-button' });

      const nameEl = toolButton.createEl('div', { text: tool.name || tool.tool || 'Unknown Tool' });
      nameEl.style.fontWeight = 'bold';

      if (tool.description) {
        const descEl = toolButton.createEl('div', { text: tool.description });
        descEl.style.fontSize = '0.9em';
        descEl.style.color = 'var(--text-muted)';
        descEl.style.marginTop = '4px';
      }

      toolButton.onclick = () => this.executeTool(tool.name || tool.tool);
    });
  }

  async executeTool(toolName: string) {
    try {
      const endpoint = this.plugin.getEndpointUrl();
      const response = await fetch(`${endpoint}/tools/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tool_name: toolName,
          parameters: {},
          bypass_agent: true
        })
      });

      if (response.ok) {
        const result = await response.json();
        new Notice(`Tool ${toolName} executed successfully`);
        console.log('Tool result:', result);
      } else {
        throw new Error(`Tool execution failed: ${response.statusText}`);
      }
    } catch (error) {
      console.error('Tool execution error:', error);
      new Notice(`Tool execution failed: ${error.message}`);
    }
  }

  trackOperation(operationId: string) {
    // This would track the operation progress
    // Implementation would depend on WebSocket integration
    console.log('Tracking operation:', operationId);
  }

  addOperationsStatus(container: HTMLElement) {
    // Placeholder for operation tracking
    // Would show currently running operations
  }

  // Chat-related methods (from original ChatModal)
  loadChatHistory() {
    if (!this.chatContainer) return;

    const history = this.plugin.settings.chatHistory || [];
    history.forEach(message => {
      this.addMessageToChat(message.role, message.content);
    });
    this.scrollToBottom();
  }

  addMessageToChat(role: 'user' | 'assistant', content: string) {
    if (!this.chatContainer) return;

    const messageEl = this.chatContainer.createEl('div', { cls: `thoth-message thoth-${role}` });

    messageEl.createEl('div', { text: role === 'user' ? 'You' : 'Assistant', cls: 'thoth-message-role' });
    messageEl.createEl('div', { text: content, cls: 'thoth-message-content' });
  }

  async sendMessage() {
    if (!this.inputElement || !this.sendButton) return;

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
    if (this.chatContainer) {
      this.chatContainer.scrollTop = this.chatContainer.scrollHeight;
    }
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

class InputModal extends Modal {
  private promptText: string;
  private resolve: (value: string | null) => void;
  private inputEl: HTMLInputElement;

  constructor(app: App, promptText: string, resolve: (value: string | null) => void) {
    super(app);
    this.promptText = promptText;
    this.resolve = resolve;
  }

  onOpen() {
    const { contentEl } = this;
    contentEl.empty();

    contentEl.createEl('h3', { text: this.promptText });

    this.inputEl = contentEl.createEl('input', { type: 'text' });
    this.inputEl.style.cssText = 'width: 100%; padding: 8px; margin: 10px 0; border: 1px solid var(--background-modifier-border); border-radius: 4px;';
    this.inputEl.focus();

    const buttonContainer = contentEl.createEl('div');
    buttonContainer.style.cssText = 'display: flex; justify-content: flex-end; gap: 10px; margin-top: 15px;';

    const cancelButton = buttonContainer.createEl('button', { text: 'Cancel' });
    cancelButton.style.cssText = 'padding: 8px 16px; border: 1px solid var(--background-modifier-border); background: var(--background-secondary); border-radius: 4px;';
    cancelButton.onclick = () => {
      this.resolve(null);
      this.close();
    };

    const okButton = buttonContainer.createEl('button', { text: 'OK' });
    okButton.style.cssText = 'padding: 8px 16px; background: var(--interactive-accent); color: var(--text-on-accent); border: none; border-radius: 4px;';
    okButton.onclick = () => {
      this.resolve(this.inputEl.value.trim() || null);
      this.close();
    };

    this.inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        this.resolve(this.inputEl.value.trim() || null);
        this.close();
      } else if (e.key === 'Escape') {
        this.resolve(null);
        this.close();
      }
    });
  }

  onClose() {
    const { contentEl } = this;
    contentEl.empty();
  }
}

class ConfirmModal extends Modal {
  private message: string;
  private resolve: (value: boolean) => void;

  constructor(app: App, message: string, resolve: (value: boolean) => void) {
    super(app);
    this.message = message;
    this.resolve = resolve;
  }

  onOpen() {
    const { contentEl } = this;
    contentEl.empty();

    contentEl.createEl('h3', { text: 'Confirmation' });
    contentEl.createEl('p', { text: this.message });

    const buttonContainer = contentEl.createEl('div');
    buttonContainer.style.cssText = 'display: flex; justify-content: flex-end; gap: 10px; margin-top: 15px;';

    const cancelButton = buttonContainer.createEl('button', { text: 'Cancel' });
    cancelButton.style.cssText = 'padding: 8px 16px; border: 1px solid var(--background-modifier-border); background: var(--background-secondary); border-radius: 4px;';
    cancelButton.onclick = () => {
      this.resolve(false);
      this.close();
    };

    const confirmButton = buttonContainer.createEl('button', { text: 'Confirm' });
    confirmButton.style.cssText = 'padding: 8px 16px; background: var(--interactive-accent); color: var(--text-on-accent); border: none; border-radius: 4px;';
    confirmButton.onclick = () => {
      this.resolve(true);
      this.close();
    };
  }

  onClose() {
    const { contentEl } = this;
    contentEl.empty();
  }
}

class CitationInserterModal extends Modal {
  private plugin: ThothPlugin;
  private editor: Editor;
  private searchInput: HTMLInputElement;
  private resultsContainer: HTMLElement;

  constructor(app: App, plugin: ThothPlugin, editor: Editor) {
    super(app);
    this.plugin = plugin;
    this.editor = editor;
  }

  onOpen() {
    const { contentEl } = this;
    contentEl.empty();

    contentEl.createEl('h2', { text: '📖 Insert Citation' });

    const searchContainer = contentEl.createEl('div');
    searchContainer.style.cssText = 'margin-bottom: 15px;';

    this.searchInput = searchContainer.createEl('input', {
      type: 'text',
      placeholder: 'Search for papers by title, author, or DOI...'
    });
    this.searchInput.style.cssText = 'width: 100%; padding: 8px; border: 1px solid var(--background-modifier-border); border-radius: 4px;';

    const searchButton = searchContainer.createEl('button', { text: 'Search' });
    searchButton.style.cssText = 'margin-left: 10px; padding: 8px 16px; background: var(--interactive-accent); color: var(--text-on-accent); border: none; border-radius: 4px;';

    this.resultsContainer = contentEl.createEl('div');
    this.resultsContainer.style.cssText = 'max-height: 400px; overflow-y: auto; border: 1px solid var(--background-modifier-border); border-radius: 4px; padding: 10px;';

    searchButton.onclick = () => this.searchCitations();
    this.searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        this.searchCitations();
      }
    });

    this.searchInput.focus();
  }

  async searchCitations() {
    const query = this.searchInput.value.trim();
    if (!query) return;

    this.resultsContainer.empty();
    this.resultsContainer.createEl('div', { text: 'Searching...' });

    try {
      // This would integrate with a citation search API
      // For now, show a placeholder
      this.resultsContainer.empty();

      const placeholder = this.resultsContainer.createEl('div');
      placeholder.innerHTML = `
        <div style="padding: 10px; border: 1px solid var(--background-modifier-border); border-radius: 4px; margin-bottom: 10px; cursor: pointer;" onclick="this.insertCitation('${query}')">
          <div style="font-weight: bold;">${query} - Sample Paper</div>
          <div style="color: var(--text-muted); font-size: 0.9em;">Authors: Sample Author et al.</div>
          <div style="color: var(--text-muted); font-size: 0.9em;">Year: 2024</div>
        </div>
      `;

      // Add click handler for citation insertion
      placeholder.querySelector('div')?.addEventListener('click', () => {
        this.insertCitation(query);
      });

    } catch (error) {
      this.resultsContainer.empty();
      this.resultsContainer.createEl('div', { text: `Search failed: ${error.message}` });
    }
  }

  insertCitation(title: string) {
    const cursor = this.editor.getCursor();
    const citation = `[@${title.toLowerCase().replace(/\s+/g, '_')}]`;
    this.editor.replaceRange(citation, cursor);
    new Notice('Citation inserted');
    this.close();
  }

  onClose() {
    const { contentEl } = this;
    contentEl.empty();
  }
}

class DiscoverySourceModal extends Modal {
  private plugin: ThothPlugin;
  private nameInput: HTMLInputElement;
  private typeSelect: HTMLSelectElement;
  private configArea: HTMLTextAreaElement;

  constructor(app: App, plugin: ThothPlugin) {
    super(app);
    this.plugin = plugin;
  }

  onOpen() {
    const { contentEl } = this;
    contentEl.empty();

    contentEl.createEl('h2', { text: '🔍 Create Discovery Source' });

    // Name input
    const nameContainer = contentEl.createEl('div');
    nameContainer.style.cssText = 'margin-bottom: 15px;';
    nameContainer.createEl('label', { text: 'Source Name:' });
    this.nameInput = nameContainer.createEl('input', { type: 'text' });
    this.nameInput.style.cssText = 'width: 100%; padding: 8px; margin-top: 5px; border: 1px solid var(--background-modifier-border); border-radius: 4px;';

    // Type select
    const typeContainer = contentEl.createEl('div');
    typeContainer.style.cssText = 'margin-bottom: 15px;';
    typeContainer.createEl('label', { text: 'Source Type:' });
    this.typeSelect = typeContainer.createEl('select');
    this.typeSelect.style.cssText = 'width: 100%; padding: 8px; margin-top: 5px; border: 1px solid var(--background-modifier-border); border-radius: 4px;';

    ['arxiv', 'pubmed', 'semantic_scholar', 'custom'].forEach(type => {
      const option = this.typeSelect.createEl('option', { value: type, text: type.charAt(0).toUpperCase() + type.slice(1) });
    });

    // Configuration area
    const configContainer = contentEl.createEl('div');
    configContainer.style.cssText = 'margin-bottom: 15px;';
    configContainer.createEl('label', { text: 'Configuration (JSON):' });
    this.configArea = configContainer.createEl('textarea');
    this.configArea.style.cssText = 'width: 100%; height: 150px; padding: 8px; margin-top: 5px; border: 1px solid var(--background-modifier-border); border-radius: 4px; font-family: monospace;';
    this.configArea.placeholder = '{\n  "query": "machine learning",\n  "max_results": 50\n}';

    // Buttons
    const buttonContainer = contentEl.createEl('div');
    buttonContainer.style.cssText = 'display: flex; justify-content: flex-end; gap: 10px;';

    const cancelButton = buttonContainer.createEl('button', { text: 'Cancel' });
    cancelButton.style.cssText = 'padding: 8px 16px; border: 1px solid var(--background-modifier-border); background: var(--background-secondary); border-radius: 4px;';
    cancelButton.onclick = () => this.close();

    const createButton = buttonContainer.createEl('button', { text: 'Create' });
    createButton.style.cssText = 'padding: 8px 16px; background: var(--interactive-accent); color: var(--text-on-accent); border: none; border-radius: 4px;';
    createButton.onclick = () => this.createSource();
  }

  async createSource() {
    const name = this.nameInput.value.trim();
    const type = this.typeSelect.value;
    const configText = this.configArea.value.trim();

    if (!name) {
      new Notice('Please enter a source name');
      return;
    }

    let config;
    try {
      config = configText ? JSON.parse(configText) : {};
    } catch (error) {
      new Notice('Invalid JSON configuration');
      return;
    }

    try {
      const endpoint = this.plugin.getEndpointUrl();
      const response = await fetch(`${endpoint}/execute/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          command: 'discovery',
          args: ['create', '--name', name, '--type', type],
          options: { config: JSON.stringify(config) }
        })
      });

      if (response.ok) {
        new Notice(`Discovery source "${name}" created successfully`);
        this.close();
      } else {
        throw new Error(`Creation failed: ${response.statusText}`);
      }
    } catch (error) {
      console.error('Source creation error:', error);
      new Notice(`Failed to create source: ${error.message}`);
    }
  }

  onClose() {
    const { contentEl } = this;
    contentEl.empty();
  }
}
