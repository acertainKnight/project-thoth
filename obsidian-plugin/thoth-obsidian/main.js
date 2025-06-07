"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
Object.defineProperty(exports, "__esModule", { value: true });
const obsidian_1 = require("obsidian");
const child_process_1 = require("child_process");
const util_1 = require("util");
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const execAsync = (0, util_1.promisify)(child_process_1.exec);
const DEFAULT_SETTINGS = {
    // === API CONFIGURATION ===
    mistralKey: '',
    openrouterKey: '',
    opencitationsKey: '',
    googleApiKey: '',
    googleSearchEngineId: '',
    semanticScholarKey: '',
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
    // === UI PREFERENCES ===
    theme: 'auto',
    compactMode: false,
    showAdvancedSettings: false,
    enableNotifications: true,
    notificationDuration: 5000,
};
class ThothPlugin extends obsidian_1.Plugin {
    constructor() {
        super(...arguments);
        this.process = null;
        this.isAgentRunning = false;
        this.isRestarting = false;
    }
    onload() {
        return __awaiter(this, void 0, void 0, function* () {
            yield this.loadSettings();
            // Add ribbon icon for chat
            const ribbonIconEl = this.addRibbonIcon('message-circle', 'Open Thoth Chat', (evt) => {
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
                editorCallback: (editor, view) => {
                    const selectedText = editor.getSelection();
                    if (selectedText) {
                        this.performResearch(selectedText, editor);
                    }
                    else {
                        new obsidian_1.Notice('Please select text to research');
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
                        new obsidian_1.Notice('Agent is currently restarting, please wait...');
                        return;
                    }
                    if (this.isAgentRunning) {
                        this.stopAgent();
                    }
                    else {
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
        });
    }
    onunload() {
        this.stopAgent();
    }
    loadSettings() {
        return __awaiter(this, void 0, void 0, function* () {
            this.settings = Object.assign({}, DEFAULT_SETTINGS, yield this.loadData());
            // Auto-generate base URL if not set
            if (!this.settings.endpointBaseUrl) {
                this.settings.endpointBaseUrl = `http://${this.settings.endpointHost}:${this.settings.endpointPort}`;
            }
        });
    }
    saveSettings() {
        return __awaiter(this, void 0, void 0, function* () {
            yield this.saveData(this.settings);
            // Sync settings to backend if agent is running
            if (this.isAgentRunning) {
                yield this.syncSettingsToBackend();
            }
        });
    }
    syncSettingsToBackend() {
        return __awaiter(this, void 0, void 0, function* () {
            try {
                const endpoint = this.getEndpointUrl();
                const response = yield fetch(`${endpoint}/agent/sync-settings`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(this.settings),
                });
                if (response.ok) {
                    const result = yield response.json();
                    console.log('Settings synced to backend:', result.synced_keys);
                }
                else {
                    console.warn('Failed to sync settings to backend:', response.statusText);
                }
            }
            catch (error) {
                console.warn('Could not sync settings to backend:', error);
            }
        });
    }
    getEndpointUrl() {
        if (this.settings.remoteMode && this.settings.remoteEndpointUrl) {
            return this.settings.remoteEndpointUrl.replace(/\/$/, ''); // Remove trailing slash
        }
        return `http://${this.settings.endpointHost}:${this.settings.endpointPort}`;
    }
    startAgent() {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            console.log('Thoth: startAgent called');
            console.log('Remote mode:', this.settings.remoteMode);
            console.log('Remote URL:', this.settings.remoteEndpointUrl);
            console.log('Endpoint URL:', this.getEndpointUrl());
            if (this.process && !this.settings.remoteMode) {
                new obsidian_1.Notice('Thoth agent is already running');
                return;
            }
            // Handle remote mode - connect to existing server
            if (this.settings.remoteMode) {
                if (!this.settings.remoteEndpointUrl) {
                    new obsidian_1.Notice('Please configure remote endpoint URL in settings');
                    return;
                }
                new obsidian_1.Notice('Connecting to remote Thoth server...');
                try {
                    const endpointUrl = this.getEndpointUrl();
                    console.log('Testing connection to:', endpointUrl);
                    // Test connection to remote server
                    const response = yield fetch(`${endpointUrl}/health`, {
                        method: 'GET',
                        headers: {
                            'Accept': 'application/json',
                        }
                    });
                    console.log('Health check response status:', response.status);
                    if (response.ok) {
                        const healthData = yield response.json();
                        console.log('Health check response:', healthData);
                        this.isAgentRunning = true;
                        this.updateStatusBar();
                        new obsidian_1.Notice('Connected to remote Thoth server successfully!');
                        // Sync settings to remote server
                        yield this.syncSettingsToBackend();
                        return;
                    }
                    else {
                        throw new Error(`Server responded with status: ${response.status}`);
                    }
                }
                catch (error) {
                    console.error('Failed to connect to remote server:', error);
                    new obsidian_1.Notice(`Failed to connect to remote server: ${error.message}`);
                    return;
                }
            }
            // Validate settings for local mode
            if (!this.settings.mistralKey && !this.settings.openrouterKey) {
                new obsidian_1.Notice('Please configure API keys in settings first');
                return;
            }
            // Local mode - start the process
            // Ensure .env file is up to date before starting agent
            try {
                yield this.updateEnvironmentFile();
                new obsidian_1.Notice('Configuration updated, starting Thoth agent...');
            }
            catch (error) {
                console.error('Failed to update environment file:', error);
                new obsidian_1.Notice('Warning: Could not update configuration file');
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
                const env = Object.assign(Object.assign({}, process.env), this.getEnvironmentVariables());
                this.process = (0, child_process_1.spawn)(cmd, args, {
                    cwd: this.settings.workspaceDirectory,
                    env: env,
                    stdio: ['ignore', 'pipe', 'pipe']
                });
                (_a = this.process.stdout) === null || _a === void 0 ? void 0 : _a.on('data', (data) => {
                    console.log(`Thoth stdout: ${data}`);
                });
                (_b = this.process.stderr) === null || _b === void 0 ? void 0 : _b.on('data', (data) => {
                    console.log(`Thoth stderr: ${data}`);
                });
                this.process.on('close', (code) => {
                    console.log(`Thoth process exited with code ${code}`);
                    this.process = null;
                    this.isAgentRunning = false;
                    this.updateStatusBar();
                    if (code !== 0 && !this.isRestarting) {
                        new obsidian_1.Notice(`Thoth agent stopped with error code ${code}`);
                    }
                });
                this.process.on('error', (error) => {
                    console.error('Failed to start Thoth agent:', error);
                    new obsidian_1.Notice(`Failed to start Thoth agent: ${error.message}`);
                    this.process = null;
                    this.isAgentRunning = false;
                    this.updateStatusBar();
                });
                // Wait a moment for the process to start
                setTimeout(() => __awaiter(this, void 0, void 0, function* () {
                    if (this.process) {
                        // Test if the server is responding
                        try {
                            const response = yield fetch(`${this.settings.endpointBaseUrl}/health`);
                            if (response.ok) {
                                this.isAgentRunning = true;
                                this.updateStatusBar();
                                new obsidian_1.Notice('Thoth agent started successfully!');
                            }
                        }
                        catch (error) {
                            console.warn('Agent process started but server not yet responding');
                            // Give it more time
                            setTimeout(() => __awaiter(this, void 0, void 0, function* () {
                                try {
                                    const response = yield fetch(`${this.settings.endpointBaseUrl}/health`);
                                    if (response.ok) {
                                        this.isAgentRunning = true;
                                        this.updateStatusBar();
                                        new obsidian_1.Notice('Thoth agent started successfully!');
                                    }
                                    else {
                                        new obsidian_1.Notice('Thoth agent started but not responding to requests');
                                    }
                                }
                                catch (error) {
                                    new obsidian_1.Notice('Thoth agent may have failed to start properly');
                                }
                            }), 5000);
                        }
                    }
                }), 3000);
            }
            catch (error) {
                console.error('Error starting Thoth agent:', error);
                new obsidian_1.Notice(`Error starting Thoth agent: ${error.message}`);
            }
        });
    }
    stopAgent() {
        if (this.settings.remoteMode) {
            // In remote mode, we just disconnect
            this.isAgentRunning = false;
            this.updateStatusBar();
            new obsidian_1.Notice('Disconnected from remote Thoth server');
            return;
        }
        if (!this.process) {
            new obsidian_1.Notice('Thoth agent is not running');
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
        this.updateStatusBar();
        new obsidian_1.Notice('Thoth agent stopped');
    }
    restartAgent() {
        return __awaiter(this, void 0, void 0, function* () {
            if (this.isRestarting) {
                new obsidian_1.Notice('Agent is already restarting, please wait...');
                return;
            }
            this.isRestarting = true;
            this.updateStatusBar();
            try {
                if (this.settings.remoteMode) {
                    // Remote restart via API
                    new obsidian_1.Notice('Restarting remote Thoth agent...');
                    const endpoint = this.getEndpointUrl();
                    const response = yield fetch(`${endpoint}/agent/restart`, {
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
                        const result = yield response.json();
                        new obsidian_1.Notice(`Remote agent restart initiated: ${result.message}`);
                        // Wait for the agent to restart and become available
                        yield this.waitForAgentRestart();
                    }
                    else {
                        throw new Error(`Remote restart failed: ${response.statusText}`);
                    }
                }
                else {
                    // Local restart
                    new obsidian_1.Notice('Restarting Thoth agent...');
                    this.stopAgent();
                    // Wait a moment for cleanup
                    yield new Promise(resolve => setTimeout(resolve, 2000));
                    yield this.startAgent();
                }
                new obsidian_1.Notice('Thoth agent restarted successfully!');
            }
            catch (error) {
                console.error('Failed to restart agent:', error);
                new obsidian_1.Notice(`Failed to restart agent: ${error.message}`);
            }
            finally {
                this.isRestarting = false;
                this.updateStatusBar();
            }
        });
    }
    waitForAgentRestart() {
        return __awaiter(this, void 0, void 0, function* () {
            const maxAttempts = 30; // 30 seconds max
            const interval = 1000; // 1 second intervals
            for (let attempt = 0; attempt < maxAttempts; attempt++) {
                try {
                    const endpoint = this.getEndpointUrl();
                    const response = yield fetch(`${endpoint}/health`);
                    if (response.ok) {
                        this.isAgentRunning = true;
                        return;
                    }
                }
                catch (error) {
                    // Expected during restart
                }
                yield new Promise(resolve => setTimeout(resolve, interval));
            }
            throw new Error('Agent did not become available after restart');
        });
    }
    getEnvironmentVariables() {
        return {
            // API Keys
            API_MISTRAL_KEY: this.settings.mistralKey,
            API_OPENROUTER_KEY: this.settings.openrouterKey,
            API_OPENCITATIONS_KEY: this.settings.opencitationsKey,
            API_GOOGLE_API_KEY: this.settings.googleApiKey,
            API_GOOGLE_SEARCH_ENGINE_ID: this.settings.googleSearchEngineId,
            API_SEMANTIC_SCHOLAR_KEY: this.settings.semanticScholarKey,
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
    updateEnvironmentFile() {
        return __awaiter(this, void 0, void 0, function* () {
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
                yield fs.promises.writeFile(envPath, lines.join('\n'));
                console.log('Environment file updated successfully');
            }
            catch (error) {
                console.error('Failed to update environment file:', error);
                throw error;
            }
        });
    }
    updateStatusBar() {
        if (!this.statusBarItem)
            return;
        if (this.isRestarting) {
            this.statusBarItem.setText('Thoth: Restarting...');
            this.statusBarItem.style.color = '#ffa500'; // Orange
        }
        else if (this.isAgentRunning) {
            this.statusBarItem.setText('Thoth: Running');
            this.statusBarItem.style.color = '#00ff00'; // Green
        }
        else {
            this.statusBarItem.setText('Thoth: Stopped');
            this.statusBarItem.style.color = '#ff0000'; // Red
        }
    }
    performResearch(query, editor) {
        return __awaiter(this, void 0, void 0, function* () {
            if (!this.isAgentRunning) {
                new obsidian_1.Notice('Thoth agent is not running. Please start it first.');
                return;
            }
            try {
                new obsidian_1.Notice('Researching... This may take a moment.');
                const endpoint = this.getEndpointUrl();
                const response = yield fetch(`${endpoint}/research/query`, {
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
                    const result = yield response.json();
                    // Insert the research results at the cursor position
                    const cursor = editor.getCursor();
                    const researchText = `\n\n## 🔍 Research: ${query}\n*Generated on ${new Date().toLocaleString()} by Thoth Research Assistant*\n\n${result.response}\n\n---\n`;
                    editor.replaceRange(researchText, cursor);
                    new obsidian_1.Notice('Research completed and inserted!');
                }
                else {
                    throw new Error(`Research request failed: ${response.statusText}`);
                }
            }
            catch (error) {
                console.error('Research error:', error);
                new obsidian_1.Notice(`Research failed: ${error.message}`);
            }
        });
    }
    openChatModal() {
        new ChatModal(this.app, this).open();
    }
}
exports.default = ThothPlugin;
class ChatModal extends obsidian_1.Modal {
    constructor(app, plugin) {
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
    addMessageToChat(role, content) {
        const messageEl = this.chatContainer.createEl('div', { cls: `thoth-message thoth-${role}` });
        if (role === 'user') {
            messageEl.style.cssText = 'text-align: right; margin: 10px 0; padding: 8px; background-color: var(--interactive-accent); color: white; border-radius: 8px;';
        }
        else {
            messageEl.style.cssText = 'text-align: left; margin: 10px 0; padding: 8px; background-color: var(--background-secondary); border-radius: 8px;';
        }
        messageEl.createEl('div', { text: role === 'user' ? 'You' : 'Assistant', cls: 'thoth-message-role' }).style.cssText = 'font-weight: bold; margin-bottom: 4px; font-size: 0.9em;';
        messageEl.createEl('div', { text: content, cls: 'thoth-message-content' });
    }
    sendMessage() {
        return __awaiter(this, void 0, void 0, function* () {
            const message = this.inputElement.value.trim();
            if (!message)
                return;
            // Add user message to chat
            this.addMessageToChat('user', message);
            this.inputElement.value = '';
            this.scrollToBottom();
            // Disable send button
            this.sendButton.disabled = true;
            this.sendButton.textContent = 'Sending...';
            try {
                const endpoint = this.plugin.getEndpointUrl();
                const response = yield fetch(`${endpoint}/research/chat`, {
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
                if (response.ok) {
                    const result = yield response.json();
                    // Add assistant response to chat
                    this.addMessageToChat('assistant', result.response);
                    // Save to chat history
                    this.plugin.settings.chatHistory.push({ role: 'user', content: message, timestamp: Date.now() }, { role: 'assistant', content: result.response, timestamp: Date.now() });
                    // Keep only last 20 messages
                    if (this.plugin.settings.chatHistory.length > 20) {
                        this.plugin.settings.chatHistory = this.plugin.settings.chatHistory.slice(-20);
                    }
                    yield this.plugin.saveSettings();
                }
                else {
                    throw new Error(`Chat request failed: ${response.statusText}`);
                }
            }
            catch (error) {
                console.error('Chat error:', error);
                this.addMessageToChat('assistant', `Error: ${error.message}`);
            }
            finally {
                this.sendButton.disabled = false;
                this.sendButton.textContent = 'Send';
                this.scrollToBottom();
            }
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
class ThothSettingTab extends obsidian_1.PluginSettingTab {
    constructor(app, plugin) {
        super(app, plugin);
        this.plugin = plugin;
    }
    display() {
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
        const advancedToggle = new obsidian_1.Setting(containerEl)
            .setName('🔧 Show Advanced Settings')
            .setDesc('Configure LLM models, agent behavior, discovery system, and more')
            .addToggle((toggle) => toggle
            .setValue(this.plugin.settings.showAdvancedSettings)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.showAdvancedSettings = value;
            yield this.plugin.saveSettings();
            this.display(); // Refresh to show/hide advanced settings
        })));
        if (this.plugin.settings.showAdvancedSettings) {
            this.addAdvancedSettings(containerEl);
        }
        // Agent Controls (always visible at bottom)
        this.addAgentControls(containerEl);
    }
    addQuickStatus(containerEl) {
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
        }
        else if (this.plugin.isAgentRunning) {
            agentIndicator.textContent = 'Running';
            agentIndicator.className = 'thoth-status-indicator thoth-status-success';
        }
        else {
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
        }
        else {
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
    addEssentialSettings(containerEl) {
        const section = containerEl.createEl('div', { cls: 'thoth-settings-section' });
        section.createEl('h2', { text: '🔑 Essential Configuration' });
        section.createEl('p', { text: 'Required settings to get started with Thoth', cls: 'thoth-section-desc' });
        // API Keys Subsection
        const apiSection = section.createEl('div', { cls: 'thoth-subsection' });
        apiSection.createEl('h3', { text: 'API Keys' });
        new obsidian_1.Setting(apiSection)
            .setName('Mistral API Key')
            .setDesc('Required for PDF processing and document analysis')
            .addText((text) => {
            text.inputEl.type = 'password';
            text
                .setPlaceholder('Enter your Mistral API key')
                .setValue(this.plugin.settings.mistralKey)
                .onChange((value) => __awaiter(this, void 0, void 0, function* () {
                this.plugin.settings.mistralKey = value;
                yield this.plugin.saveSettings();
            }));
        })
            .addExtraButton((button) => {
            button
                .setIcon('external-link')
                .setTooltip('Get Mistral API Key')
                .onClick(() => window.open('https://console.mistral.ai', '_blank'));
        });
        new obsidian_1.Setting(apiSection)
            .setName('OpenRouter API Key')
            .setDesc('Required for AI research capabilities and language models')
            .addText((text) => {
            text.inputEl.type = 'password';
            text
                .setPlaceholder('Enter your OpenRouter API key')
                .setValue(this.plugin.settings.openrouterKey)
                .onChange((value) => __awaiter(this, void 0, void 0, function* () {
                this.plugin.settings.openrouterKey = value;
                yield this.plugin.saveSettings();
            }));
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
        new obsidian_1.Setting(optionalApiSection)
            .setName('Google API Key')
            .setDesc('For Google Scholar and search integration')
            .addText((text) => {
            text.inputEl.type = 'password';
            text
                .setPlaceholder('Enter your Google API key')
                .setValue(this.plugin.settings.googleApiKey)
                .onChange((value) => __awaiter(this, void 0, void 0, function* () {
                this.plugin.settings.googleApiKey = value;
                yield this.plugin.saveSettings();
            }));
        });
        new obsidian_1.Setting(optionalApiSection)
            .setName('Semantic Scholar API Key')
            .setDesc('For enhanced academic paper discovery')
            .addText((text) => {
            text.inputEl.type = 'password';
            text
                .setPlaceholder('Enter your Semantic Scholar API key')
                .setValue(this.plugin.settings.semanticScholarKey)
                .onChange((value) => __awaiter(this, void 0, void 0, function* () {
                this.plugin.settings.semanticScholarKey = value;
                yield this.plugin.saveSettings();
            }));
        });
        // Directory Settings
        const dirSection = section.createEl('div', { cls: 'thoth-subsection' });
        dirSection.createEl('h3', { text: 'Directory Configuration' });
        new obsidian_1.Setting(dirSection)
            .setName('Workspace Directory')
            .setDesc('Path to your Thoth workspace (where you cloned project-thoth)')
            .addText((text) => text
            .setPlaceholder('e.g., /home/user/project-thoth')
            .setValue(this.plugin.settings.workspaceDirectory)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
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
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(dirSection)
            .setName('Obsidian Notes Directory')
            .setDesc('Directory in your vault where Thoth will store research notes')
            .addText((text) => text
            .setPlaceholder('e.g., Research/Thoth')
            .setValue(this.plugin.settings.obsidianDirectory)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.obsidianDirectory = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(dirSection)
            .setName('Prompts Directory')
            .setDesc('Folder with custom prompts (leave blank for defaults)')
            .addText((text) => text
            .setPlaceholder('e.g., /path/to/prompts')
            .setValue(this.plugin.settings.promptsDirectory)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.promptsDirectory = value;
            yield this.plugin.saveSettings();
        })));
    }
    addConnectionSettings(containerEl) {
        const section = containerEl.createEl('div', { cls: 'thoth-settings-section' });
        section.createEl('h2', { text: '🌐 Connection Settings' });
        section.createEl('p', { text: 'Configure how Obsidian connects to the Thoth agent', cls: 'thoth-section-desc' });
        new obsidian_1.Setting(section)
            .setName('Remote Mode')
            .setDesc('Connect to a remote Thoth server (WSL, Docker, or remote machine)')
            .addToggle((toggle) => toggle
            .setValue(this.plugin.settings.remoteMode)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.remoteMode = value;
            yield this.plugin.saveSettings();
            this.display();
        })));
        if (this.plugin.settings.remoteMode) {
            new obsidian_1.Setting(section)
                .setName('Remote Endpoint URL')
                .setDesc('Full URL of the remote Thoth server')
                .addText((text) => text
                .setPlaceholder('http://localhost:8000')
                .setValue(this.plugin.settings.remoteEndpointUrl)
                .onChange((value) => __awaiter(this, void 0, void 0, function* () {
                this.plugin.settings.remoteEndpointUrl = value;
                yield this.plugin.saveSettings();
            })));
            // Quick connection test for remote mode
            const testContainer = section.createEl('div', { cls: 'thoth-test-container' });
            const testButton = testContainer.createEl('button', {
                text: 'Test Remote Connection',
                cls: 'thoth-test-button'
            });
            const testResult = testContainer.createEl('span', { cls: 'thoth-test-result' });
            testButton.onclick = () => __awaiter(this, void 0, void 0, function* () {
                testButton.disabled = true;
                testButton.textContent = 'Testing...';
                testResult.textContent = '';
                try {
                    const response = yield fetch(`${this.plugin.settings.remoteEndpointUrl}/health`);
                    if (response.ok) {
                        testResult.textContent = '✅ Connection successful';
                        testResult.className = 'thoth-test-result thoth-test-success';
                    }
                    else {
                        testResult.textContent = `❌ Server error: ${response.status}`;
                        testResult.className = 'thoth-test-result thoth-test-error';
                    }
                }
                catch (error) {
                    testResult.textContent = `❌ Connection failed: ${error.message}`;
                    testResult.className = 'thoth-test-result thoth-test-error';
                }
                finally {
                    testButton.disabled = false;
                    testButton.textContent = 'Test Remote Connection';
                }
            });
        }
        else {
            new obsidian_1.Setting(section)
                .setName('Local Host')
                .setDesc('Host address for local Thoth server')
                .addText((text) => text
                .setPlaceholder('127.0.0.1')
                .setValue(this.plugin.settings.endpointHost)
                .onChange((value) => __awaiter(this, void 0, void 0, function* () {
                this.plugin.settings.endpointHost = value;
                this.plugin.settings.endpointBaseUrl = `http://${value}:${this.plugin.settings.endpointPort}`;
                yield this.plugin.saveSettings();
            })));
            new obsidian_1.Setting(section)
                .setName('Local Port')
                .setDesc('Port for local Thoth server')
                .addSlider((slider) => slider
                .setLimits(3000, 9999, 1)
                .setValue(this.plugin.settings.endpointPort)
                .setDynamicTooltip()
                .onChange((value) => __awaiter(this, void 0, void 0, function* () {
                this.plugin.settings.endpointPort = value;
                this.plugin.settings.endpointBaseUrl = `http://${this.plugin.settings.endpointHost}:${value}`;
                yield this.plugin.saveSettings();
            })));
        }
    }
    addAdvancedSettings(containerEl) {
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
    addLLMSettings(parentEl) {
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
        new obsidian_1.Setting(subsection)
            .setName('Primary LLM Model')
            .setDesc('Main language model for research and general tasks')
            .addDropdown((dropdown) => {
            modelOptions.forEach(model => dropdown.addOption(model, model));
            dropdown
                .setValue(this.plugin.settings.primaryLlmModel)
                .onChange((value) => __awaiter(this, void 0, void 0, function* () {
                this.plugin.settings.primaryLlmModel = value;
                yield this.plugin.saveSettings();
            }));
        });
        new obsidian_1.Setting(subsection)
            .setName('Analysis LLM Model')
            .setDesc('Specialized model for document analysis and PDF processing')
            .addDropdown((dropdown) => {
            modelOptions.forEach(model => dropdown.addOption(model, model));
            dropdown
                .setValue(this.plugin.settings.analysisLlmModel)
                .onChange((value) => __awaiter(this, void 0, void 0, function* () {
                this.plugin.settings.analysisLlmModel = value;
                yield this.plugin.saveSettings();
            }));
        });
        new obsidian_1.Setting(subsection)
            .setName('LLM Temperature')
            .setDesc('Creativity level for responses (0.0 = focused, 1.0 = creative)')
            .addSlider((slider) => slider
            .setLimits(0, 1, 0.1)
            .setValue(this.plugin.settings.llmTemperature)
            .setDynamicTooltip()
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.llmTemperature = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(subsection)
            .setName('Max Output Tokens')
            .setDesc('Maximum response length')
            .addSlider((slider) => slider
            .setLimits(1024, 8192, 256)
            .setValue(this.plugin.settings.llmMaxOutputTokens)
            .setDynamicTooltip()
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.llmMaxOutputTokens = value;
            yield this.plugin.saveSettings();
        })));
    }
    addAgentBehaviorSettings(parentEl) {
        const subsection = parentEl.createEl('details', { cls: 'thoth-subsection' });
        subsection.createEl('summary', { text: '🧠 Agent Behavior' });
        new obsidian_1.Setting(subsection)
            .setName('Auto-start Research Agent')
            .setDesc('Automatically start the research agent when the server starts')
            .addToggle((toggle) => toggle
            .setValue(this.plugin.settings.researchAgentAutoStart)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.researchAgentAutoStart = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(subsection)
            .setName('Enable Agent Memory')
            .setDesc('Allow the agent to remember previous conversations')
            .addToggle((toggle) => toggle
            .setValue(this.plugin.settings.researchAgentMemoryEnabled)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.researchAgentMemoryEnabled = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(subsection)
            .setName('Max Tool Calls')
            .setDesc('Maximum number of tools the agent can use per request')
            .addSlider((slider) => slider
            .setLimits(5, 50, 5)
            .setValue(this.plugin.settings.agentMaxToolCalls)
            .setDynamicTooltip()
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.agentMaxToolCalls = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(subsection)
            .setName('Agent Timeout (seconds)')
            .setDesc('Maximum time to wait for agent responses')
            .addSlider((slider) => slider
            .setLimits(30, 600, 30)
            .setValue(this.plugin.settings.agentTimeoutSeconds)
            .setDynamicTooltip()
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.agentTimeoutSeconds = value;
            yield this.plugin.saveSettings();
        })));
    }
    addDiscoverySettings(parentEl) {
        const subsection = parentEl.createEl('details', { cls: 'thoth-subsection' });
        subsection.createEl('summary', { text: '🔍 Discovery System' });
        new obsidian_1.Setting(subsection)
            .setName('Auto-start Discovery Scheduler')
            .setDesc('Automatically start the discovery scheduler for finding new research')
            .addToggle((toggle) => toggle
            .setValue(this.plugin.settings.discoveryAutoStartScheduler)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.discoveryAutoStartScheduler = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(subsection)
            .setName('Max Articles per Discovery')
            .setDesc('Maximum number of articles to discover per search')
            .addSlider((slider) => slider
            .setLimits(10, 100, 10)
            .setValue(this.plugin.settings.discoveryDefaultMaxArticles)
            .setDynamicTooltip()
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.discoveryDefaultMaxArticles = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(subsection)
            .setName('Discovery Interval (minutes)')
            .setDesc('How often to run automatic discovery searches')
            .addSlider((slider) => slider
            .setLimits(15, 240, 15)
            .setValue(this.plugin.settings.discoveryDefaultIntervalMinutes)
            .setDynamicTooltip()
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.discoveryDefaultIntervalMinutes = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(subsection)
            .setName('Enable Chrome Extension Integration')
            .setDesc('Allow integration with Thoth Chrome extension for web research')
            .addToggle((toggle) => toggle
            .setValue(this.plugin.settings.discoveryChromeExtensionEnabled)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.discoveryChromeExtensionEnabled = value;
            yield this.plugin.saveSettings();
        })));
    }
    addLoggingSettings(parentEl) {
        const subsection = parentEl.createEl('details', { cls: 'thoth-subsection' });
        subsection.createEl('summary', { text: '📊 Logging & Performance' });
        const logLevels = ['DEBUG', 'INFO', 'WARNING', 'ERROR'];
        new obsidian_1.Setting(subsection)
            .setName('Log Level')
            .setDesc('Minimum level of messages to log')
            .addDropdown((dropdown) => {
            logLevels.forEach(level => dropdown.addOption(level, level));
            dropdown
                .setValue(this.plugin.settings.logLevel)
                .onChange((value) => __awaiter(this, void 0, void 0, function* () {
                this.plugin.settings.logLevel = value;
                yield this.plugin.saveSettings();
            }));
        });
        new obsidian_1.Setting(subsection)
            .setName('Enable Performance Monitoring')
            .setDesc('Track performance metrics and system health')
            .addToggle((toggle) => toggle
            .setValue(this.plugin.settings.enablePerformanceMonitoring)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.enablePerformanceMonitoring = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(subsection)
            .setName('Development Mode')
            .setDesc('Enable additional debugging features')
            .addToggle((toggle) => toggle
            .setValue(this.plugin.settings.developmentMode)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.developmentMode = value;
            yield this.plugin.saveSettings();
        })));
    }
    addUISettings(parentEl) {
        const subsection = parentEl.createEl('details', { cls: 'thoth-subsection' });
        subsection.createEl('summary', { text: '🎨 User Interface' });
        new obsidian_1.Setting(subsection)
            .setName('Show Status Bar')
            .setDesc('Display agent status in Obsidian status bar')
            .addToggle((toggle) => toggle
            .setValue(this.plugin.settings.showStatusBar)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.showStatusBar = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(subsection)
            .setName('Show Ribbon Icon')
            .setDesc('Display chat icon in left ribbon')
            .addToggle((toggle) => toggle
            .setValue(this.plugin.settings.showRibbonIcon)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.showRibbonIcon = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(subsection)
            .setName('Compact Mode')
            .setDesc('Use smaller UI elements to save space')
            .addToggle((toggle) => toggle
            .setValue(this.plugin.settings.compactMode)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.compactMode = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(subsection)
            .setName('Chat History Limit')
            .setDesc('Maximum number of chat messages to remember')
            .addSlider((slider) => slider
            .setLimits(10, 100, 10)
            .setValue(this.plugin.settings.chatHistoryLimit)
            .setDynamicTooltip()
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.chatHistoryLimit = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(subsection)
            .setName('Enable Notifications')
            .setDesc('Show notifications for important events')
            .addToggle((toggle) => toggle
            .setValue(this.plugin.settings.enableNotifications)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.enableNotifications = value;
            yield this.plugin.saveSettings();
        })));
    }
    addAgentControls(containerEl) {
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
        testButton.onclick = () => __awaiter(this, void 0, void 0, function* () {
            testButton.disabled = true;
            testButton.textContent = 'Testing...';
            try {
                const endpoint = this.plugin.getEndpointUrl();
                const response = yield fetch(`${endpoint}/health`);
                if (response.ok) {
                    new obsidian_1.Notice('✅ Connection successful!');
                }
                else {
                    new obsidian_1.Notice(`❌ Connection failed: ${response.statusText}`);
                }
            }
            catch (error) {
                new obsidian_1.Notice(`❌ Connection failed: ${error.message}`);
            }
            finally {
                testButton.disabled = false;
                testButton.textContent = 'Test Connection';
            }
        });
        // Open Chat
        const chatButton = controlsGrid.createEl('button', {
            text: 'Open Chat',
            cls: 'thoth-control-button thoth-button-chat'
        });
        chatButton.onclick = () => this.plugin.openChatModal();
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibWFpbi5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIi4uL21haW4udHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7QUFBQSx1Q0FBdUc7QUFDdkcsaURBQTBEO0FBQzFELCtCQUFpQztBQUNqQyx1Q0FBeUI7QUFDekIsMkNBQTZCO0FBRTdCLE1BQU0sU0FBUyxHQUFHLElBQUEsZ0JBQVMsRUFBQyxvQkFBSSxDQUFDLENBQUM7QUE4RmxDLE1BQU0sZ0JBQWdCLEdBQWtCO0lBQ3RDLDRCQUE0QjtJQUM1QixVQUFVLEVBQUUsRUFBRTtJQUNkLGFBQWEsRUFBRSxFQUFFO0lBQ2pCLGdCQUFnQixFQUFFLEVBQUU7SUFDcEIsWUFBWSxFQUFFLEVBQUU7SUFDaEIsb0JBQW9CLEVBQUUsRUFBRTtJQUN4QixrQkFBa0IsRUFBRSxFQUFFO0lBRXRCLGtDQUFrQztJQUNsQyxrQkFBa0IsRUFBRSxFQUFFO0lBQ3RCLGlCQUFpQixFQUFFLEVBQUU7SUFDckIsYUFBYSxFQUFFLEVBQUU7SUFDakIsa0JBQWtCLEVBQUUsRUFBRTtJQUN0QixhQUFhLEVBQUUsRUFBRTtJQUNqQixnQkFBZ0IsRUFBRSxFQUFFO0lBQ3BCLHFCQUFxQixFQUFFLEVBQUU7SUFDekIsWUFBWSxFQUFFLEVBQUU7SUFDaEIsZ0JBQWdCLEVBQUUsRUFBRTtJQUVwQiw4QkFBOEI7SUFDOUIsVUFBVSxFQUFFLEtBQUs7SUFDakIsaUJBQWlCLEVBQUUsdUJBQXVCO0lBQzFDLFlBQVksRUFBRSxXQUFXO0lBQ3pCLFlBQVksRUFBRSxJQUFJO0lBQ2xCLGVBQWUsRUFBRSxFQUFFO0lBQ25CLFdBQVcsRUFBRSxDQUFDLHVCQUF1QixFQUFFLHVCQUF1QixDQUFDO0lBRS9ELDRCQUE0QjtJQUM1QixlQUFlLEVBQUUsMkJBQTJCO0lBQzVDLGdCQUFnQixFQUFFLDJCQUEyQjtJQUM3QyxrQkFBa0IsRUFBRSwyQkFBMkI7SUFDL0MsY0FB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VUFBVSxDQUFDLFFBQVEsR0FBRyxJQUFJLENBQUM7WUFDM0IsVUFBVSxDQUFDLFdBQVcsR0FBRyxZQUFZLENBQUM7WUFFdEMsSUFBSSxDQUFDO2dCQUNILE1BQU0sUUFBUSxHQUFHLElBQUksQ0FBQyxNQUFNLENBQUMsY0FBYyxFQUFFLENBQUM7Z0JBQzlDLE1BQU0sUUFBUSxHQUFHLE1BQU0sS0FBSyxDQUFDLEdBQUcsUUFBUSxTQUFTLENBQUMsQ0FBQztnQkFDbkQsSUFBSSxRQUFRLENBQUMsRUFBRSxFQUFFLENBQUM7b0JBQ2hCLElBQUksaUJBQU0sQ0FBQywwQkFBMEIsQ0FBQyxDQUFDO2dCQUN6QyxDQUFDO3FCQUFNLENBQUM7b0JBQ04sSUFBSSxpQkFBTSxDQUFDLHdCQUF3QixRQUFRLENBQUMsVUFBVSxFQUFFLENBQUMsQ0FBQztnQkFDNUQsQ0FBQztZQUNILENBQUM7WUFBQyxPQUFPLEtBQUssRUFBRSxDQUFDO2dCQUNmLElBQUksaUJBQU0sQ0FBQyx3QkFBd0IsS0FBSyxDQUFDLE9BQU8sRUFBRSxDQUFDLENBQUM7WUFDdEQsQ0FBQztvQkFBUyxDQUFDO2dCQUNULFVBQVUsQ0FBQyxRQUFRLEdBQUcsS0FBSyxDQUFDO2dCQUM1QixVQUFVLENBQUMsV0FBVyxHQUFHLGlCQUFpQixDQUFDO1lBQzdDLENBQUM7UUFDSCxDQUFDLENBQUEsQ0FBQztRQUVGLFlBQVk7UUFDWixNQUFNLFVBQVUsR0FBRyxZQUFZLENBQUMsUUFBUSxDQUFDLFFBQVEsRUFBRTtZQUNqRCxJQUFJLEVBQUUsV0FBVztZQUNqQixHQUFHLEVBQUUsd0NBQXdDO1NBQzlDLENBQUMsQ0FBQztRQUNILFVBQVUsQ0FBQyxPQUFPLEdBQUcsR0FBRyxFQUFFLENBQUMsSUFBSSxDQUFDLE1BQU0sQ0FBQyxhQUFhLEVBQUUsQ0FBQztJQUN6RCxDQUFDO0NBQ0YiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBBcHAsIEVkaXRvciwgTWFya2Rvd25WaWV3LCBNb2RhbCwgTm90aWNlLCBQbHVnaW4sIFBsdWdpblNldHRpbmdUYWIsIFNldHRpbmcgfSBmcm9tICdvYnNpZGlhbic7XG5pbXBvcnQgeyBleGVjLCBzcGF3biwgQ2hpbGRQcm9jZXNzIH0gZnJvbSAnY2hpbGRfcHJvY2Vzcyc7XG5pbXBvcnQgeyBwcm9taXNpZnkgfSBmcm9tICd1dGlsJztcbmltcG9ydCAqIGFzIGZzIGZyb20gJ2ZzJztcbmltcG9ydCAqIGFzIHBhdGggZnJvbSAncGF0aCc7XG5cbmNvbnN0IGV4ZWNBc3luYyA9IHByb21pc2lmeShleGVjKTtcblxuaW50ZXJmYWNlIFRob3RoU2V0dGluZ3Mge1xuICAvLyA9PT0gQVBJIENPTkZJR1VSQVRJT04gPT09XG4gIC8vIFByaW1hcnkgQVBJIEtleXNcbiAgbWlzdHJhbEtleTogc3RyaW5nO1xuICBvcGVucm91dGVyS2V5OiBzdHJpbmc7XG5cbiAgLy8gT3B0aW9uYWwgQVBJIEtleXNcbiAgb3BlbmNpdGF0aW9uc0tleTogc3RyaW5nO1xuICBnb29nbGVBcGlLZXk6IHN0cmluZztcbiAgZ29vZ2xlU2VhcmNoRW5naW5lSWQ6IHN0cmluZztcbiAgc2VtYW50aWNTY2hvbGFyS2V5OiBzdHJpbmc7XG5cbiAgLy8gPT09IERJUkVDVE9SWSBDT05GSUdVUkFUSU9OID09PVxuICB3b3Jrc3BhY2VEaXJlY3Rvcnk6IHN0cmluZztcbiAgb2JzaWRpYW5EaXJlY3Rvcnk6IHN0cmluZztcbiAgZGF0YURpcmVjdG9yeTogc3RyaW5nO1xuICBrbm93bGVkZ2VEaXJlY3Rvcnk6IHN0cmluZztcbiAgbG9nc0RpcmVjdG9yeTogc3RyaW5nO1xuICBxdWVyaWVzRGlyZWN0b3J5OiBzdHJpbmc7XG4gIGFnZW50U3RvcmFnZURpcmVjdG9yeTogc3RyaW5nO1xuICBwZGZEaXJlY3Rvcnk6IHN0cmluZztcbiAgcHJvbXB0c0RpcmVjdG9yeTogc3RyaW5nO1xuXG4gIC8vID09PSBDT05ORUNUSU9OIFNFVFRJTkdTID09PVxuICByZW1vdGVNb2RlOiBib29sZWFuO1xuICByZW1vdGVFbmRwb2ludFVybDogc3RyaW5nO1xuICBlbmRwb2ludEhvc3Q6IHN0cmluZztcbiAgZW5kcG9pbnRQb3J0OiBudW1iZXI7XG4gIGVuZHBvaW50QmFzZVVybDogc3RyaW5nO1xuICBjb3JzT3JpZ2luczogc3RyaW5nW107XG5cbiAgLy8gPT09IExMTSBDT05GSUdVUkFUSU9OID09PVxuICBwcmltYXJ5TGxtTW9kZWw6IHN0cmluZztcbiAgYW5hbHlzaXNMbG1Nb2RlbDogc3RyaW5nO1xuICByZXNlYXJjaEFnZW50TW9kZWw6IHN0cmluZztcbiAgbGxtVGVtcGVyYXR1cmU6IG51bWJlcjtcbiAgYW5hbHlzaXNMbG1UZW1wZXJhdHVyZTogbnVtYmVyO1xuICBsbG1NYXhPdXRwdXRUb2tlbnM6IG51bWJlcjtcbiAgYW5hbHlzaXNMbG1NYXhPdXRwdXRUb2tlbnM6IG51bWJlcjtcblxuICAvLyA9PT0gQUdFTlQgQkVIQVZJT1IgPT09XG4gIHJlc2VhcmNoQWdlbnRBdXRvU3RhcnQ6IGJvb2xlYW47XG4gIHJlc2VhcmNoQWdlbnREZWZhdWx0UXVlcmllczogYm9vbGVhbjtcbiAgcmVzZWFyY2hBZ2VudE1lbW9yeUVuYWJsZWQ6IGJvb2xlYW47XG4gIGFnZW50TWF4VG9vbENhbGxzOiBudW1iZXI7XG4gIGFnZW50VGltZW91dFNlY29uZHM6IG51bWJlcjtcblxuICAvLyA9PT0gRElTQ09WRVJZIFNZU1RFTSA9PT1cbiAgZGlzY292ZXJ5QXV0b1N0YXJ0U2NoZWR1bGVyOiBib29sZWFuO1xuICBkaXNjb3ZlcnlEZWZhdWx0TWF4QXJ0aWNsZXM6IG51bWJlcjtcbiAgZGlzY292ZXJ5RGVmYXVsdEludGVydmFsTWludXRlczogbnVtYmVyO1xuICBkaXNjb3ZlcnlSYXRlTGltaXREZWxheTogbnVtYmVyO1xuICBkaXNjb3ZlcnlDaHJvbWVFeHRlbnNpb25FbmFibGVkOiBib29sZWFuO1xuICBkaXNjb3ZlcnlDaHJvbWVFeHRlbnNpb25Qb3J0OiBudW1iZXI7XG5cbiAgLy8gPT09IExPR0dJTkcgQ09ORklHVVJBVElPTiA9PT1cbiAgbG9nTGV2ZWw6IHN0cmluZztcbiAgbG9nRm9ybWF0OiBzdHJpbmc7XG4gIGxvZ1JvdGF0aW9uOiBzdHJpbmc7XG4gIGxvZ1JldGVudGlvbjogc3RyaW5nO1xuICBlbmFibGVQZXJmb3JtYW5jZU1vbml0b3Jpbmc6IGJvb2xlYW47XG4gIG1ldHJpY3NJbnRlcnZhbDogbnVtYmVyO1xuXG4gIC8vID09PSBTRUNVUklUWSAmIFBFUkZPUk1BTkNFID09PVxuICBlbmNyeXB0aW9uS2V5OiBzdHJpbmc7XG4gIHNlc3Npb25UaW1lb3V0OiBudW1iZXI7XG4gIGFwaVJhdGVMaW1pdDogbnVtYmVyO1xuICBoZWFsdGhDaGVja1RpbWVvdXQ6IG51bWJlcjtcbiAgZGV2ZWxvcG1lbnRNb2RlOiBib29sZWFuO1xuXG4gIC8vID09PSBQTFVHSU4gQkVIQVZJT1IgPT09XG4gIGF1dG9TdGFydEFnZW50OiBib29sZWFuO1xuICBzaG93U3RhdHVzQmFyOiBib29sZWFuO1xuICBzaG93UmliYm9uSWNvbjogYm9vbGVhbjtcbiAgYXV0b1NhdmVTZXR0aW5nczogYm9vbGVhbjtcbiAgY2hhdEhpc3RvcnlMaW1pdDogbnVtYmVyO1xuICBjaGF0SGlzdG9yeTogQ2hhdE1lc3NhZ2VbXTtcblxuICAvLyA9PT0gVUkgUFJFRkVSRU5DRVMgPT09XG4gIHRoZW1lOiBzdHJpbmc7XG4gIGNvbXBhY3RNb2RlOiBib29sZWFuO1xuICBzaG93QWR2YW5jZWRTZXR0aW5nczogYm9vbGVhbjtcbiAgZW5hYmxlTm90aWZpY2F0aW9uczogYm9vbGVhbjtcbiAgbm90aWZpY2F0aW9uRHVyYXRpb246IG51bWJlcjtcbn1cblxuaW50ZXJmYWNlIENoYXRNZXNzYWdlIHtcbiAgcm9sZTogJ3VzZXInIHwgJ2Fzc2lzdGFudCc7XG4gIGNvbnRlbnQ6IHN0cmluZztcbiAgdGltZXN0YW1wOiBudW1iZXI7XG59XG5cbmNvbnN0IERFRkFVTFRfU0VUVElOR1M6IFRob3RoU2V0dGluZ3MgPSB7XG4gIC8vID09PSBBUEkgQ09ORklHVVJBVElPTiA9PT1cbiAgbWlzdHJhbEtleTogJycsXG4gIG9wZW5yb3V0ZXJLZXk6ICcnLFxuICBvcGVuY2l0YXRpb25zS2V5OiAnJyxcbiAgZ29vZ2xlQXBpS2V5OiAnJyxcbiAgZ29vZ2xlU2VhcmNoRW5naW5lSWQ6ICcnLFxuICBzZW1hbnRpY1NjaG9sYXJLZXk6ICcnLFxuXG4gIC8vID09PSBESVJFQ1RPUlkgQ09ORklHVVJBVElPTiA9PT1cbiAgd29ya3NwYWNlRGlyZWN0b3J5OiAnJyxcbiAgb2JzaWRpYW5EaXJlY3Rvcnk6ICcnLFxuICBkYXRhRGlyZWN0b3J5OiAnJyxcbiAga25vd2xlZGdlRGlyZWN0b3J5OiAnJyxcbiAgbG9nc0RpcmVjdG9yeTogJycsXG4gIHF1ZXJpZXNEaXJlY3Rvcnk6ICcnLFxuICBhZ2VudFN0b3JhZ2VEaXJlY3Rvcnk6ICcnLFxuICBwZGZEaXJlY3Rvcnk6ICcnLFxuICBwcm9tcHRzRGlyZWN0b3J5OiAnJyxcblxuICAvLyA9PT0gQ09OTkVDVElPTiBTRVRUSU5HUyA9PT1cbiAgcmVtb3RlTW9kZTogZmFsc2UsXG4gIHJlbW90ZUVuZHBvaW50VXJsOiAnaHR0cDovL2xvY2FsaG9zdDo4MDAwJyxcbiAgZW5kcG9pbnRIb3N0OiAnMTI3LjAuMC4xJyxcbiAgZW5kcG9pbnRQb3J0OiA4MDAwLFxuICBlbmRwb2ludEJhc2VVcmw6ICcnLFxuICBjb3JzT3JpZ2luczogWydodHRwOi8vbG9jYWxob3N0OjMwMDAnLCAnaHR0cDovLzEyNy4wLjAuMTo4MDgwJ10sXG5cbiAgLy8gPT09IExMTSBDT05GSUdVUkFUSU9OID09PVxuICBwcmltYXJ5TGxtTW9kZWw6ICdhbnRocm9waWMvY2xhdWRlLTMtc29ubmV0JyxcbiAgYW5hbHlzaXNMbG1Nb2RlbDogJ2FudGhyb3BpYy9jbGF1ZGUtMy1zb25uZXQnLFxuICByZXNlYXJjaEFnZW50TW9kZWw6ICdhbnRocm9waWMvY2xhdWRlLTMtc29ubmV0JyxcbiAgbGxtVGVtcGVyYXR1cmU6IDAuNyxcbiAgYW5hbHlzaXNMbG1UZW1wZXJhdHVyZTogMC41LFxuICBsbG1NYXhPdXRwdXRUb2tlbnM6IDQwOTYsXG4gIGFuYWx5c2lzTGxtTWF4T3V0cHV0VG9rZW5zOiA4MTkyLFxuXG4gIC8vID09PSBBR0VOVCBCRUhBVklPUiA9PT1cbiAgcmVzZWFyY2hBZ2VudEF1dG9TdGFydDogZmFsc2UsXG4gIHJlc2VhcmNoQWdlbnREZWZhdWx0UXVlcmllczogdHJ1ZSxcbiAgcmVzZWFyY2hBZ2VudE1lbW9yeUVuYWJsZWQ6IHRydWUsXG4gIGFnZW50TWF4VG9vbENhbGxzOiAyMCxcbiAgYWdlbnRUaW1lb3V0U2Vjb25kczogMzAwLFxuXG4gIC8vID09PSBESVNDT1ZFUlkgU1lTVEVNID09PVxuICBkaXNjb3ZlcnlBdXRvU3RhcnRTY2hlZHVsZXI6IGZhbHNlLFxuICBkaXNjb3ZlcnlEZWZhdWx0TWF4QXJ0aWNsZXM6IDUwLFxuICBkaXNjb3ZlcnlEZWZhdWx0SW50ZXJ2YWxNaW51dGVzOiA2MCxcbiAgZGlzY292ZXJ5UmF0ZUxpbWl0RGVsYXk6IDEuMCxcbiAgZGlzY292ZXJ5Q2hyb21lRXh0ZW5zaW9uRW5hYmxlZDogdHJ1ZSxcbiAgZGlzY292ZXJ5Q2hyb21lRXh0ZW5zaW9uUG9ydDogODc2NSxcblxuICAvLyA9PT0gTE9HR0lORyBDT05GSUdVUkFUSU9OID09PVxuICBsb2dMZXZlbDogJ0lORk8nLFxuICBsb2dGb3JtYXQ6ICc8Z3JlZW4+e3RpbWV9PC9ncmVlbj4gfCA8bGV2ZWw+e2xldmVsOiA8OH08L2xldmVsPiB8IDxjeWFuPntuYW1lfTwvY3lhbj46PGN5YW4+e2Z1bmN0aW9ufTwvY3lhbj46PGN5YW4+e2xpbmV9PC9jeWFuPiAtIDxsZXZlbD57bWVzc2FnZX08L2xldmVsPicsXG4gIGxvZ1JvdGF0aW9uOiAnMTAgTUInLFxuICBsb2dSZXRlbnRpb246ICczMCBkYXlzJyxcbiAgZW5hYmxlUGVyZm9ybWFuY2VNb25pdG9yaW5nOiBmYWxzZSxcbiAgbWV0cmljc0ludGVydmFsOiA2MCxcblxuICAvLyA9PT0gU0VDVVJJVFkgJiBQRVJGT1JNQU5DRSA9PT1cbiAgZW5jcnlwdGlvbktleTogJycsXG4gIHNlc3Npb25UaW1lb3V0OiAzNjAwLFxuICBhcGlSYXRlTGltaXQ6IDEwMCxcbiAgaGVhbHRoQ2hlY2tUaW1lb3V0OiAzMCxcbiAgZGV2ZWxvcG1lbnRNb2RlOiBmYWxzZSxcblxuICAvLyA9PT0gUExVR0lOIEJFSEFWSU9SID09PVxuICBhdXRvU3RhcnRBZ2VudDogZmFsc2UsXG4gIHNob3dTdGF0dXNCYXI6IHRydWUsXG4gIHNob3dSaWJib25JY29uOiB0cnVlLFxuICBhdXRvU2F2ZVNldHRpbmdzOiB0cnVlLFxuICBjaGF0SGlzdG9yeUxpbWl0OiAyMCxcbiAgY2hhdEhpc3Rvcnk6IFtdLFxuXG4gIC8vID09PSBVSSBQUkVGRVJFTkNFUyA9PT1cbiAgdGhlbWU6ICdhdXRvJyxcbiAgY29tcGFjdE1vZGU6IGZhbHNlLFxuICBzaG93QWR2YW5jZWRTZXR0aW5nczogZmFsc2UsXG4gIGVuYWJsZU5vdGlmaWNhdGlvbnM6IHRydWUsXG4gIG5vdGlmaWNhdGlvbkR1cmF0aW9uOiA1MDAwLFxufTtcblxuZXhwb3J0IGRlZmF1bHQgY2xhc3MgVGhvdGhQbHVnaW4gZXh0ZW5kcyBQbHVnaW4ge1xuICBzZXR0aW5nczogVGhvdGhTZXR0aW5ncztcbiAgc3RhdHVzQmFySXRlbTogSFRNTEVsZW1lbnQ7XG4gIHByb2Nlc3M6IENoaWxkUHJvY2VzcyB8IG51bGwgPSBudWxsO1xuICBpc0FnZW50UnVubmluZzogYm9vbGVhbiA9IGZhbHNlO1xuICBpc1Jlc3RhcnRpbmc6IGJvb2xlYW4gPSBmYWxzZTtcblxuICBhc3luYyBvbmxvYWQoKSB7XG4gICAgYXdhaXQgdGhpcy5sb2FkU2V0dGluZ3MoKTtcblxuICAgIC8vIEFkZCByaWJib24gaWNvbiBmb3IgY2hhdFxuICAgIGNvbnN0IHJpYmJvbkljb25FbCA9IHRoaXMuYWRkUmliYm9uSWNvbignbWVzc2FnZS1jaXJjbGUnLCAnT3BlbiBUaG90aCBDaGF0JywgKGV2dDogTW91c2VFdmVudCkgPT4ge1xuICAgICAgdGhpcy5vcGVuQ2hhdE1vZGFsKCk7XG4gICAgfSk7XG4gICAgcmliYm9uSWNvbkVsLmFkZENsYXNzKCd0aG90aC1yaWJib24taWNvbicpO1xuXG4gICAgLy8gQWRkIGNvbW1hbmRzXG4gICAgdGhpcy5hZGRDb21tYW5kKHtcbiAgICAgIGlkOiAnc3RhcnQtdGhvdGgtYWdlbnQnLFxuICAgICAgbmFtZTogJ1N0YXJ0IFRob3RoIEFnZW50JyxcbiAgICAgIGNhbGxiYWNrOiAoKSA9PiB7XG4gICAgICAgIHRoaXMuc3RhcnRBZ2VudCgpO1xuICAgICAgfVxuICAgIH0pO1xuXG4gICAgdGhpcy5hZGRDb21tYW5kKHtcbiAgICAgIGlkOiAnc3RvcC10aG90aC1hZ2VudCcsXG4gICAgICBuYW1lOiAnU3RvcCBUaG90aCBBZ2VudCcsXG4gICAgICBjYWxsYmFjazogKCkgPT4ge1xuICAgICAgICB0aGlzLnN0b3BBZ2VudCgpO1xuICAgICAgfVxuICAgIH0pO1xuXG4gICAgdGhpcy5hZGRDb21tYW5kKHtcbiAgICAgIGlkOiAncmVzdGFydC10aG90aC1hZ2VudCcsXG4gICAgICBuYW1lOiAnUmVzdGFydCBUaG90aCBBZ2VudCcsXG4gICAgICBjYWxsYmFjazogKCkgPT4ge1xuICAgICAgICB0aGlzLnJlc3RhcnRBZ2VudCgpO1xuICAgICAgfVxuICAgIH0pO1xuXG4gICAgdGhpcy5hZGRDb21tYW5kKHtcbiAgICAgIGlkOiAnb3Blbi1yZXNlYXJjaC1jaGF0JyxcbiAgICAgIG5hbWU6ICdPcGVuIFJlc2VhcmNoIENoYXQnLFxuICAgICAgY2FsbGJhY2s6ICgpID0+IHtcbiAgICAgICAgdGhpcy5vcGVuQ2hhdE1vZGFsKCk7XG4gICAgICB9XG4gICAgfSk7XG5cbiAgICB0aGlzLmFkZENvbW1hbmQoe1xuICAgICAgaWQ6ICdpbnNlcnQtcmVzZWFyY2gtcXVlcnknLFxuICAgICAgbmFtZTogJ0luc2VydCBSZXNlYXJjaCBRdWVyeScsXG4gICAgICBlZGl0b3JDYWxsYmFjazogKGVkaXRvcjogRWRpdG9yLCB2aWV3OiBNYXJrZG93blZpZXcpID0+IHtcbiAgICAgICAgY29uc3Qgc2VsZWN0ZWRUZXh0ID0gZWRpdG9yLmdldFNlbGVjdGlvbigpO1xuICAgICAgICBpZiAoc2VsZWN0ZWRUZXh0KSB7XG4gICAgICAgICAgdGhpcy5wZXJmb3JtUmVzZWFyY2goc2VsZWN0ZWRUZXh0LCBlZGl0b3IpO1xuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgIG5ldyBOb3RpY2UoJ1BsZWFzZSBzZWxlY3QgdGV4dCB0byByZXNlYXJjaCcpO1xuICAgICAgICB9XG4gICAgICB9XG4gICAgfSk7XG5cbiAgICAvLyBBZGQgc3RhdHVzIGJhclxuICAgIGlmICh0aGlzLnNldHRpbmdzLnNob3dTdGF0dXNCYXIpIHtcbiAgICAgIHRoaXMuc3RhdHVzQmFySXRlbSA9IHRoaXMuYWRkU3RhdHVzQmFySXRlbSgpO1xuICAgICAgdGhpcy51cGRhdGVTdGF0dXNCYXIoKTtcblxuICAgICAgLy8gTWFrZSBzdGF0dXMgYmFyIGNsaWNrYWJsZVxuICAgICAgdGhpcy5zdGF0dXNCYXJJdGVtLmFkZEV2ZW50TGlzdGVuZXIoJ2NsaWNrJywgKCkgPT4ge1xuICAgICAgICBpZiAodGhpcy5pc1Jlc3RhcnRpbmcpIHtcbiAgICAgICAgICBuZXcgTm90aWNlKCdBZ2VudCBpcyBjdXJyZW50bHkgcmVzdGFydGluZywgcGxlYXNlIHdhaXQuLi4nKTtcbiAgICAgICAgICByZXR1cm47XG4gICAgICAgIH1cblxuICAgICAgICBpZiAodGhpcy5pc0FnZW50UnVubmluZykge1xuICAgICAgICAgIHRoaXMuc3RvcEFnZW50KCk7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgdGhpcy5zdGFydEFnZW50KCk7XG4gICAgICAgIH1cbiAgICAgIH0pO1xuICAgIH1cblxuICAgIC8vIEFkZCBzZXR0aW5ncyB0YWJcbiAgICB0aGlzLmFkZFNldHRpbmdUYWIobmV3IFRob3RoU2V0dGluZ1RhYih0aGlzLmFwcCwgdGhpcykpO1xuXG4gICAgLy8gQXV0by1zdGFydCBhZ2VudCBpZiBlbmFibGVkXG4gICAgaWYgKHRoaXMuc2V0dGluZ3MuYXV0b1N0YXJ0QWdlbnQpIHtcbiAgICAgIHNldFRpbWVvdXQoKCkgPT4ge1xuICAgICAgICB0aGlzLnN0YXJ0QWdlbnQoKTtcbiAgICAgIH0sIDIwMDApOyAvLyBXYWl0IDIgc2Vjb25kcyBmb3IgT2JzaWRpYW4gdG8gZnVsbHkgbG9hZFxuICAgIH1cbiAgfVxuXG4gIG9udW5sb2FkKCkge1xuICAgIHRoaXMuc3RvcEFnZW50KCk7XG4gIH1cblxuICBhc3luYyBsb2FkU2V0dGluZ3MoKSB7XG4gICAgdGhpcy5zZXR0aW5ncyA9IE9iamVjdC5hc3NpZ24oe30sIERFRkFVTFRfU0VUVElOR1MsIGF3YWl0IHRoaXMubG9hZERhdGEoKSk7XG5cbiAgICAvLyBBdXRvLWdlbmVyYXRlIGJhc2UgVVJMIGlmIG5vdCBzZXRcbiAgICBpZiAoIXRoaXMuc2V0dGluZ3MuZW5kcG9pbnRCYXNlVXJsKSB7XG4gICAgICB0aGlzLnNldHRpbmdzLmVuZHBvaW50QmFzZVVybCA9IGBodHRwOi8vJHt0aGlzLnNldHRpbmdzLmVuZHBvaW50SG9zdH06JHt0aGlzLnNldHRpbmdzLmVuZHBvaW50UG9ydH1gO1xuICAgIH1cbiAgfVxuXG4gIGFzeW5jIHNhdmVTZXR0aW5ncygpIHtcbiAgICBhd2FpdCB0aGlzLnNhdmVEYXRhKHRoaXMuc2V0dGluZ3MpO1xuXG4gICAgLy8gU3luYyBzZXR0aW5ncyB0byBiYWNrZW5kIGlmIGFnZW50IGlzIHJ1bm5pbmdcbiAgICBpZiAodGhpcy5pc0FnZW50UnVubmluZykge1xuICAgICAgYXdhaXQgdGhpcy5zeW5jU2V0dGluZ3NUb0JhY2tlbmQoKTtcbiAgICB9XG4gIH1cblxuICBhc3luYyBzeW5jU2V0dGluZ3NUb0JhY2tlbmQoKSB7XG4gICAgdHJ5IHtcbiAgICAgIGNvbnN0IGVuZHBvaW50ID0gdGhpcy5nZXRFbmRwb2ludFVybCgpO1xuICAgICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBmZXRjaChgJHtlbmRwb2ludH0vYWdlbnQvc3luYy1zZXR0aW5nc2AsIHtcbiAgICAgICAgbWV0aG9kOiAnUE9TVCcsXG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICB9LFxuICAgICAgICBib2R5OiBKU09OLnN0cmluZ2lmeSh0aGlzLnNldHRpbmdzKSxcbiAgICAgIH0pO1xuXG4gICAgICBpZiAocmVzcG9uc2Uub2spIHtcbiAgICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgcmVzcG9uc2UuanNvbigpO1xuICAgICAgICBjb25zb2xlLmxvZygnU2V0dGluZ3Mgc3luY2VkIHRvIGJhY2tlbmQ6JywgcmVzdWx0LnN5bmNlZF9rZXlzKTtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIGNvbnNvbGUud2FybignRmFpbGVkIHRvIHN5bmMgc2V0dGluZ3MgdG8gYmFja2VuZDonLCByZXNwb25zZS5zdGF0dXNUZXh0KTtcbiAgICAgIH1cbiAgICB9IGNhdGNoIChlcnJvcikge1xuICAgICAgY29uc29sZS53YXJuKCdDb3VsZCBub3Qgc3luYyBzZXR0aW5ncyB0byBiYWNrZW5kOicsIGVycm9yKTtcbiAgICB9XG4gIH1cblxuICBwdWJsaWMgZ2V0RW5kcG9pbnRVcmwoKTogc3RyaW5nIHtcbiAgICBpZiAodGhpcy5zZXR0aW5ncy5yZW1vdGVNb2RlICYmIHRoaXMuc2V0dGluZ3MucmVtb3RlRW5kcG9pbnRVcmwpIHtcbiAgICAgIHJldHVybiB0aGlzLnNldHRpbmdzLnJlbW90ZUVuZHBvaW50VXJsLnJlcGxhY2UoL1xcLyQvLCAnJyk7IC8vIFJlbW92ZSB0cmFpbGluZyBzbGFzaFxuICAgIH1cbiAgICByZXR1cm4gYGh0dHA6Ly8ke3RoaXMuc2V0dGluZ3MuZW5kcG9pbnRIb3N0fToke3RoaXMuc2V0dGluZ3MuZW5kcG9pbnRQb3J0fWA7XG4gIH1cblxuICAgIGFzeW5jIHN0YXJ0QWdlbnQoKTogUHJvbWlzZTx2b2lkPiB7XG4gICAgY29uc29sZS5sb2coJ1Rob3RoOiBzdGFydEFnZW50IGNhbGxlZCcpO1xuICAgIGNvbnNvbGUubG9nKCdSZW1vdGUgbW9kZTonLCB0aGlzLnNldHRpbmdzLnJlbW90ZU1vZGUpO1xuICAgIGNvbnNvbGUubG9nKCdSZW1vdGUgVVJMOicsIHRoaXMuc2V0dGluZ3MucmVtb3RlRW5kcG9pbnRVcmwpO1xuICAgIGNvbnNvbGUubG9nKCdFbmRwb2ludCBVUkw6JywgdGhpcy5nZXRFbmRwb2ludFVybCgpKTtcblxuICAgIGlmICh0aGlzLnByb2Nlc3MgJiYgIXRoaXMuc2V0dGluZ3MucmVtb3RlTW9kZSkge1xuICAgICAgbmV3IE5vdGljZSgnVGhvdGggYWdlbnQgaXMgYWxyZWFkeSBydW5uaW5nJyk7XG4gICAgICByZXR1cm47XG4gICAgfVxuXG4gICAgLy8gSGFuZGxlIHJlbW90ZSBtb2RlIC0gY29ubmVjdCB0byBleGlzdGluZyBzZXJ2ZXJcbiAgICBpZiAodGhpcy5zZXR0aW5ncy5yZW1vdGVNb2RlKSB7XG4gICAgICBpZiAoIXRoaXMuc2V0dGluZ3MucmVtb3RlRW5kcG9pbnRVcmwpIHtcbiAgICAgICAgbmV3IE5vdGljZSgnUGxlYXNlIGNvbmZpZ3VyZSByZW1vdGUgZW5kcG9pbnQgVVJMIGluIHNldHRpbmdzJyk7XG4gICAgICAgIHJldHVybjtcbiAgICAgIH1cblxuICAgICAgbmV3IE5vdGljZSgnQ29ubmVjdGluZyB0byByZW1vdGUgVGhvdGggc2VydmVyLi4uJyk7XG5cbiAgICAgIHRyeSB7XG4gICAgICAgIGNvbnN0IGVuZHBvaW50VXJsID0gdGhpcy5nZXRFbmRwb2ludFVybCgpO1xuICAgICAgICBjb25zb2xlLmxvZygnVGVzdGluZyBjb25uZWN0aW9uIHRvOicsIGVuZHBvaW50VXJsKTtcblxuICAgICAgICAvLyBUZXN0IGNvbm5lY3Rpb24gdG8gcmVtb3RlIHNlcnZlclxuICAgICAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGZldGNoKGAke2VuZHBvaW50VXJsfS9oZWFsdGhgLCB7XG4gICAgICAgICAgbWV0aG9kOiAnR0VUJyxcbiAgICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgICAnQWNjZXB0JzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgIH1cbiAgICAgICAgfSk7XG5cbiAgICAgICAgY29uc29sZS5sb2coJ0hlYWx0aCBjaGVjayByZXNwb25zZSBzdGF0dXM6JywgcmVzcG9uc2Uuc3RhdHVzKTtcblxuICAgICAgICBpZiAocmVzcG9uc2Uub2spIHtcbiAgICAgICAgICBjb25zdCBoZWFsdGhEYXRhID0gYXdhaXQgcmVzcG9uc2UuanNvbigpO1xuICAgICAgICAgIGNvbnNvbGUubG9nKCdIZWFsdGggY2hlY2sgcmVzcG9uc2U6JywgaGVhbHRoRGF0YSk7XG5cbiAgICAgICAgICB0aGlzLmlzQWdlbnRSdW5uaW5nID0gdHJ1ZTtcbiAgICAgICAgICB0aGlzLnVwZGF0ZVN0YXR1c0JhcigpO1xuICAgICAgICAgIG5ldyBOb3RpY2UoJ0Nvbm5lY3RlZCB0byByZW1vdGUgVGhvdGggc2VydmVyIHN1Y2Nlc3NmdWxseSEnKTtcblxuICAgICAgICAgIC8vIFN5bmMgc2V0dGluZ3MgdG8gcmVtb3RlIHNlcnZlclxuICAgICAgICAgIGF3YWl0IHRoaXMuc3luY1NldHRpbmdzVG9CYWNrZW5kKCk7XG4gICAgICAgICAgcmV0dXJuO1xuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgIHRocm93IG5ldyBFcnJvcihgU2VydmVyIHJlc3BvbmRlZCB3aXRoIHN0YXR1czogJHtyZXNwb25zZS5zdGF0dXN9YCk7XG4gICAgICAgIH1cbiAgICAgIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgICAgIGNvbnNvbGUuZXJyb3IoJ0ZhaWxlZCB0byBjb25uZWN0IHRvIHJlbW90ZSBzZXJ2ZXI6JywgZXJyb3IpO1xuICAgICAgICBuZXcgTm90aWNlKGBGYWlsZWQgdG8gY29ubmVjdCB0byByZW1vdGUgc2VydmVyOiAke2Vycm9yLm1lc3NhZ2V9YCk7XG4gICAgICAgIHJldHVybjtcbiAgICAgIH1cbiAgICB9XG5cbiAgICAvLyBWYWxpZGF0ZSBzZXR0aW5ncyBmb3IgbG9jYWwgbW9kZVxuICAgIGlmICghdGhpcy5zZXR0aW5ncy5taXN0cmFsS2V5ICYmICF0aGlzLnNldHRpbmdzLm9wZW5yb3V0ZXJLZXkpIHtcbiAgICAgIG5ldyBOb3RpY2UoJ1BsZWFzZSBjb25maWd1cmUgQVBJIGtleXMgaW4gc2V0dGluZ3MgZmlyc3QnKTtcbiAgICAgIHJldHVybjtcbiAgICB9XG5cbiAgICAvLyBMb2NhbCBtb2RlIC0gc3RhcnQgdGhlIHByb2Nlc3NcbiAgICAvLyBFbnN1cmUgLmVudiBmaWxlIGlzIHVwIHRvIGRhdGUgYmVmb3JlIHN0YXJ0aW5nIGFnZW50XG4gICAgdHJ5IHtcbiAgICAgIGF3YWl0IHRoaXMudXBkYXRlRW52aXJvbm1lbnRGaWxlKCk7XG4gICAgICBuZXcgTm90aWNlKCdDb25maWd1cmF0aW9uIHVwZGF0ZWQsIHN0YXJ0aW5nIFRob3RoIGFnZW50Li4uJyk7XG4gICAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICAgIGNvbnNvbGUuZXJyb3IoJ0ZhaWxlZCB0byB1cGRhdGUgZW52aXJvbm1lbnQgZmlsZTonLCBlcnJvcik7XG4gICAgICBuZXcgTm90aWNlKCdXYXJuaW5nOiBDb3VsZCBub3QgdXBkYXRlIGNvbmZpZ3VyYXRpb24gZmlsZScpO1xuICAgIH1cblxuICAgIHRyeSB7XG4gICAgICBjb25zdCBjbWQgPSAndXYnO1xuICAgICAgY29uc3QgYXJncyA9IFtcbiAgICAgICAgJ3J1bicsXG4gICAgICAgICdweXRob24nLFxuICAgICAgICAnLW0nLFxuICAgICAgICAndGhvdGgnLFxuICAgICAgICAnYXBpJyxcbiAgICAgICAgJy0taG9zdCcsXG4gICAgICAgIHRoaXMuc2V0dGluZ3MuZW5kcG9pbnRIb3N0LFxuICAgICAgICAnLS1wb3J0JyxcbiAgICAgICAgdGhpcy5zZXR0aW5ncy5lbmRwb2ludFBvcnQudG9TdHJpbmcoKVxuICAgICAgXTtcblxuICAgICAgY29uc3QgZW52ID0ge1xuICAgICAgICAuLi5wcm9jZXNzLmVudixcbiAgICAgICAgLi4udGhpcy5nZXRFbnZpcm9ubWVudFZhcmlhYmxlcygpXG4gICAgICB9O1xuXG4gICAgICB0aGlzLnByb2Nlc3MgPSBzcGF3bihjbWQsIGFyZ3MsIHtcbiAgICAgICAgY3dkOiB0aGlzLnNldHRpbmdzLndvcmtzcGFjZURpcmVjdG9yeSxcbiAgICAgICAgZW52OiBlbnYsXG4gICAgICAgIHN0ZGlvOiBbJ2lnbm9yZScsICdwaXBlJywgJ3BpcGUnXVxuICAgICAgfSk7XG5cbiAgICAgIHRoaXMucHJvY2Vzcy5zdGRvdXQ/Lm9uKCdkYXRhJywgKGRhdGEpID0+IHtcbiAgICAgICAgY29uc29sZS5sb2coYFRob3RoIHN0ZG91dDogJHtkYXRhfWApO1xuICAgICAgfSk7XG5cbiAgICAgIHRoaXMucHJvY2Vzcy5zdGRlcnI/Lm9uKCdkYXRhJywgKGRhdGEpID0+IHtcbiAgICAgICAgY29uc29sZS5sb2coYFRob3RoIHN0ZGVycjogJHtkYXRhfWApO1xuICAgICAgfSk7XG5cbiAgICAgIHRoaXMucHJvY2Vzcy5vbignY2xvc2UnLCAoY29kZSkgPT4ge1xuICAgICAgICBjb25zb2xlLmxvZyhgVGhvdGggcHJvY2VzcyBleGl0ZWQgd2l0aCBjb2RlICR7Y29kZX1gKTtcbiAgICAgICAgdGhpcy5wcm9jZXNzID0gbnVsbDtcbiAgICAgICAgdGhpcy5pc0FnZW50UnVubmluZyA9IGZhbHNlO1xuICAgICAgICB0aGlzLnVwZGF0ZVN0YXR1c0JhcigpO1xuXG4gICAgICAgIGlmIChjb2RlICE9PSAwICYmICF0aGlzLmlzUmVzdGFydGluZykge1xuICAgICAgICAgIG5ldyBOb3RpY2UoYFRob3RoIGFnZW50IHN0b3BwZWQgd2l0aCBlcnJvciBjb2RlICR7Y29kZX1gKTtcbiAgICAgICAgfVxuICAgICAgfSk7XG5cbiAgICAgIHRoaXMucHJvY2Vzcy5vbignZXJyb3InLCAoZXJyb3IpID0+IHtcbiAgICAgICAgY29uc29sZS5lcnJvcignRmFpbGVkIHRvIHN0YXJ0IFRob3RoIGFnZW50OicsIGVycm9yKTtcbiAgICAgICAgbmV3IE5vdGljZShgRmFpbGVkIHRvIHN0YXJ0IFRob3RoIGFnZW50OiAke2Vycm9yLm1lc3NhZ2V9YCk7XG4gICAgICAgIHRoaXMucHJvY2VzcyA9IG51bGw7XG4gICAgICAgIHRoaXMuaXNBZ2VudFJ1bm5pbmcgPSBmYWxzZTtcbiAgICAgICAgdGhpcy51cGRhdGVTdGF0dXNCYXIoKTtcbiAgICAgIH0pO1xuXG4gICAgICAvLyBXYWl0IGEgbW9tZW50IGZvciB0aGUgcHJvY2VzcyB0byBzdGFydFxuICAgICAgc2V0VGltZW91dChhc3luYyAoKSA9PiB7XG4gICAgICAgIGlmICh0aGlzLnByb2Nlc3MpIHtcbiAgICAgICAgICAvLyBUZXN0IGlmIHRoZSBzZXJ2ZXIgaXMgcmVzcG9uZGluZ1xuICAgICAgICAgIHRyeSB7XG4gICAgICAgICAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGZldGNoKGAke3RoaXMuc2V0dGluZ3MuZW5kcG9pbnRCYXNlVXJsfS9oZWFsdGhgKTtcbiAgICAgICAgICAgIGlmIChyZXNwb25zZS5vaykge1xuICAgICAgICAgICAgICB0aGlzLmlzQWdlbnRSdW5uaW5nID0gdHJ1ZTtcbiAgICAgICAgICAgICAgdGhpcy51cGRhdGVTdGF0dXNCYXIoKTtcbiAgICAgICAgICAgICAgbmV3IE5vdGljZSgnVGhvdGggYWdlbnQgc3RhcnRlZCBzdWNjZXNzZnVsbHkhJyk7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICAgICAgICAgIGNvbnNvbGUud2FybignQWdlbnQgcHJvY2VzcyBzdGFydGVkIGJ1dCBzZXJ2ZXIgbm90IHlldCByZXNwb25kaW5nJyk7XG4gICAgICAgICAgICAvLyBHaXZlIGl0IG1vcmUgdGltZVxuICAgICAgICAgICAgc2V0VGltZW91dChhc3luYyAoKSA9PiB7XG4gICAgICAgICAgICAgIHRyeSB7XG4gICAgICAgICAgICAgICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBmZXRjaChgJHt0aGlzLnNldHRpbmdzLmVuZHBvaW50QmFzZVVybH0vaGVhbHRoYCk7XG4gICAgICAgICAgICAgICAgaWYgKHJlc3BvbnNlLm9rKSB7XG4gICAgICAgICAgICAgICAgICB0aGlzLmlzQWdlbnRSdW5uaW5nID0gdHJ1ZTtcbiAgICAgICAgICAgICAgICAgIHRoaXMudXBkYXRlU3RhdHVzQmFyKCk7XG4gICAgICAgICAgICAgICAgICBuZXcgTm90aWNlKCdUaG90aCBhZ2VudCBzdGFydGVkIHN1Y2Nlc3NmdWxseSEnKTtcbiAgICAgICAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgICAgICAgbmV3IE5vdGljZSgnVGhvdGggYWdlbnQgc3RhcnRlZCBidXQgbm90IHJlc3BvbmRpbmcgdG8gcmVxdWVzdHMnKTtcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgICAgICAgICAgICAgbmV3IE5vdGljZSgnVGhvdGggYWdlbnQgbWF5IGhhdmUgZmFpbGVkIHRvIHN0YXJ0IHByb3Blcmx5Jyk7XG4gICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH0sIDUwMDApO1xuICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgICAgfSwgMzAwMCk7XG5cbiAgICB9IGNhdGNoIChlcnJvcikge1xuICAgICAgY29uc29sZS5lcnJvcignRXJyb3Igc3RhcnRpbmcgVGhvdGggYWdlbnQ6JywgZXJyb3IpO1xuICAgICAgbmV3IE5vdGljZShgRXJyb3Igc3RhcnRpbmcgVGhvdGggYWdlbnQ6ICR7ZXJyb3IubWVzc2FnZX1gKTtcbiAgICB9XG4gIH1cblxuICBzdG9wQWdlbnQoKTogdm9pZCB7XG4gICAgaWYgKHRoaXMuc2V0dGluZ3MucmVtb3RlTW9kZSkge1xuICAgICAgLy8gSW4gcmVtb3RlIG1vZGUsIHdlIGp1c3QgZGlzY29ubmVjdFxuICAgICAgdGhpcy5pc0FnZW50UnVubmluZyA9IGZhbHNlO1xuICAgICAgdGhpcy51cGRhdGVTdGF0dXNCYXIoKTtcbiAgICAgIG5ldyBOb3RpY2UoJ0Rpc2Nvbm5lY3RlZCBmcm9tIHJlbW90ZSBUaG90aCBzZXJ2ZXInKTtcbiAgICAgIHJldHVybjtcbiAgICB9XG5cbiAgICBpZiAoIXRoaXMucHJvY2Vzcykge1xuICAgICAgbmV3IE5vdGljZSgnVGhvdGggYWdlbnQgaXMgbm90IHJ1bm5pbmcnKTtcbiAgICAgIHJldHVybjtcbiAgICB9XG5cbiAgICB0aGlzLnByb2Nlc3Mua2lsbCgnU0lHVEVSTScpO1xuICAgIHNldFRpbWVvdXQoKCkgPT4ge1xuICAgICAgaWYgKHRoaXMucHJvY2Vzcykge1xuICAgICAgICB0aGlzLnByb2Nlc3Mua2lsbCgnU0lHS0lMTCcpO1xuICAgICAgfVxuICAgIH0sIDUwMDApO1xuXG4gICAgdGhpcy5wcm9jZXNzID0gbnVsbDtcbiAgICB0aGlzLmlzQWdlbnRSdW5uaW5nID0gZmFsc2U7XG4gICAgdGhpcy51cGRhdGVTdGF0dXNCYXIoKTtcbiAgICBuZXcgTm90aWNlKCdUaG90aCBhZ2VudCBzdG9wcGVkJyk7XG4gIH1cblxuICBhc3luYyByZXN0YXJ0QWdlbnQoKTogUHJvbWlzZTx2b2lkPiB7XG4gICAgaWYgKHRoaXMuaXNSZXN0YXJ0aW5nKSB7XG4gICAgICBuZXcgTm90aWNlKCdBZ2VudCBpcyBhbHJlYWR5IHJlc3RhcnRpbmcsIHBsZWFzZSB3YWl0Li4uJyk7XG4gICAgICByZXR1cm47XG4gICAgfVxuXG4gICAgdGhpcy5pc1Jlc3RhcnRpbmcgPSB0cnVlO1xuICAgIHRoaXMudXBkYXRlU3RhdHVzQmFyKCk7XG5cbiAgICB0cnkge1xuICAgICAgaWYgKHRoaXMuc2V0dGluZ3MucmVtb3RlTW9kZSkge1xuICAgICAgICAvLyBSZW1vdGUgcmVzdGFydCB2aWEgQVBJXG4gICAgICAgIG5ldyBOb3RpY2UoJ1Jlc3RhcnRpbmcgcmVtb3RlIFRob3RoIGFnZW50Li4uJyk7XG5cbiAgICAgICAgY29uc3QgZW5kcG9pbnQgPSB0aGlzLmdldEVuZHBvaW50VXJsKCk7XG4gICAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZmV0Y2goYCR7ZW5kcG9pbnR9L2FnZW50L3Jlc3RhcnRgLCB7XG4gICAgICAgICAgbWV0aG9kOiAnUE9TVCcsXG4gICAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICB9LFxuICAgICAgICAgIGJvZHk6IEpTT04uc3RyaW5naWZ5KHtcbiAgICAgICAgICAgIHVwZGF0ZV9jb25maWc6IHRydWUsXG4gICAgICAgICAgICBuZXdfY29uZmlnOiB7XG4gICAgICAgICAgICAgIGFwaV9rZXlzOiB7XG4gICAgICAgICAgICAgICAgbWlzdHJhbDogdGhpcy5zZXR0aW5ncy5taXN0cmFsS2V5LFxuICAgICAgICAgICAgICAgIG9wZW5yb3V0ZXI6IHRoaXMuc2V0dGluZ3Mub3BlbnJvdXRlcktleSxcbiAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAgZGlyZWN0b3JpZXM6IHtcbiAgICAgICAgICAgICAgICB3b3Jrc3BhY2U6IHRoaXMuc2V0dGluZ3Mud29ya3NwYWNlRGlyZWN0b3J5LFxuICAgICAgICAgICAgICAgIG5vdGVzOiB0aGlzLnNldHRpbmdzLm9ic2lkaWFuRGlyZWN0b3J5LFxuICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICBzZXR0aW5nczoge1xuICAgICAgICAgICAgICAgIGVuZHBvaW50X2hvc3Q6IHRoaXMuc2V0dGluZ3MuZW5kcG9pbnRIb3N0LFxuICAgICAgICAgICAgICAgIGVuZHBvaW50X3BvcnQ6IHRoaXMuc2V0dGluZ3MuZW5kcG9pbnRQb3J0LFxuICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgICAgfSksXG4gICAgICAgIH0pO1xuXG4gICAgICAgIGlmIChyZXNwb25zZS5vaykge1xuICAgICAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IHJlc3BvbnNlLmpzb24oKTtcbiAgICAgICAgICBuZXcgTm90aWNlKGBSZW1vdGUgYWdlbnQgcmVzdGFydCBpbml0aWF0ZWQ6ICR7cmVzdWx0Lm1lc3NhZ2V9YCk7XG5cbiAgICAgICAgICAvLyBXYWl0IGZvciB0aGUgYWdlbnQgdG8gcmVzdGFydCBhbmQgYmVjb21lIGF2YWlsYWJsZVxuICAgICAgICAgIGF3YWl0IHRoaXMud2FpdEZvckFnZW50UmVzdGFydCgpO1xuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgIHRocm93IG5ldyBFcnJvcihgUmVtb3RlIHJlc3RhcnQgZmFpbGVkOiAke3Jlc3BvbnNlLnN0YXR1c1RleHR9YCk7XG4gICAgICAgIH1cbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIC8vIExvY2FsIHJlc3RhcnRcbiAgICAgICAgbmV3IE5vdGljZSgnUmVzdGFydGluZyBUaG90aCBhZ2VudC4uLicpO1xuICAgICAgICB0aGlzLnN0b3BBZ2VudCgpO1xuXG4gICAgICAgIC8vIFdhaXQgYSBtb21lbnQgZm9yIGNsZWFudXBcbiAgICAgICAgYXdhaXQgbmV3IFByb21pc2UocmVzb2x2ZSA9PiBzZXRUaW1lb3V0KHJlc29sdmUsIDIwMDApKTtcblxuICAgICAgICBhd2FpdCB0aGlzLnN0YXJ0QWdlbnQoKTtcbiAgICAgIH1cblxuICAgICAgbmV3IE5vdGljZSgnVGhvdGggYWdlbnQgcmVzdGFydGVkIHN1Y2Nlc3NmdWxseSEnKTtcbiAgICB9IGNhdGNoIChlcnJvcikge1xuICAgICAgY29uc29sZS5lcnJvcignRmFpbGVkIHRvIHJlc3RhcnQgYWdlbnQ6JywgZXJyb3IpO1xuICAgICAgbmV3IE5vdGljZShgRmFpbGVkIHRvIHJlc3RhcnQgYWdlbnQ6ICR7ZXJyb3IubWVzc2FnZX1gKTtcbiAgICB9IGZpbmFsbHkge1xuICAgICAgdGhpcy5pc1Jlc3RhcnRpbmcgPSBmYWxzZTtcbiAgICAgIHRoaXMudXBkYXRlU3RhdHVzQmFyKCk7XG4gICAgfVxuICB9XG5cbiAgYXN5bmMgd2FpdEZvckFnZW50UmVzdGFydCgpOiBQcm9taXNlPHZvaWQ+IHtcbiAgICBjb25zdCBtYXhBdHRlbXB0cyA9IDMwOyAvLyAzMCBzZWNvbmRzIG1heFxuICAgIGNvbnN0IGludGVydmFsID0gMTAwMDsgLy8gMSBzZWNvbmQgaW50ZXJ2YWxzXG5cbiAgICBmb3IgKGxldCBhdHRlbXB0ID0gMDsgYXR0ZW1wdCA8IG1heEF0dGVtcHRzOyBhdHRlbXB0KyspIHtcbiAgICAgIHRyeSB7XG4gICAgICAgIGNvbnN0IGVuZHBvaW50ID0gdGhpcy5nZXRFbmRwb2ludFVybCgpO1xuICAgICAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGZldGNoKGAke2VuZHBvaW50fS9oZWFsdGhgKTtcblxuICAgICAgICBpZiAocmVzcG9uc2Uub2spIHtcbiAgICAgICAgICB0aGlzLmlzQWdlbnRSdW5uaW5nID0gdHJ1ZTtcbiAgICAgICAgICByZXR1cm47XG4gICAgICAgIH1cbiAgICAgIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgICAgIC8vIEV4cGVjdGVkIGR1cmluZyByZXN0YXJ0XG4gICAgICB9XG5cbiAgICAgIGF3YWl0IG5ldyBQcm9taXNlKHJlc29sdmUgPT4gc2V0VGltZW91dChyZXNvbHZlLCBpbnRlcnZhbCkpO1xuICAgIH1cblxuICAgIHRocm93IG5ldyBFcnJvcignQWdlbnQgZGlkIG5vdCBiZWNvbWUgYXZhaWxhYmxlIGFmdGVyIHJlc3RhcnQnKTtcbiAgfVxuXG4gIHByaXZhdGUgZ2V0RW52aXJvbm1lbnRWYXJpYWJsZXMoKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIC8vIEFQSSBLZXlzXG4gICAgICBBUElfTUlTVFJBTF9LRVk6IHRoaXMuc2V0dGluZ3MubWlzdHJhbEtleSxcbiAgICAgIEFQSV9PUEVOUk9VVEVSX0tFWTogdGhpcy5zZXR0aW5ncy5vcGVucm91dGVyS2V5LFxuICAgICAgQVBJX09QRU5DSVRBVElPTlNfS0VZOiB0aGlzLnNldHRpbmdzLm9wZW5jaXRhdGlvbnNLZXksXG4gICAgICBBUElfR09PR0xFX0FQSV9LRVk6IHRoaXMuc2V0dGluZ3MuZ29vZ2xlQXBpS2V5LFxuICAgICAgQVBJX0dPT0dMRV9TRUFSQ0hfRU5HSU5FX0lEOiB0aGlzLnNldHRpbmdzLmdvb2dsZVNlYXJjaEVuZ2luZUlkLFxuICAgICAgQVBJX1NFTUFOVElDX1NDSE9MQVJfS0VZOiB0aGlzLnNldHRpbmdzLnNlbWFudGljU2Nob2xhcktleSxcblxuICAgICAgLy8gRGlyZWN0b3JpZXNcbiAgICAgIFdPUktTUEFDRV9ESVI6IHRoaXMuc2V0dGluZ3Mud29ya3NwYWNlRGlyZWN0b3J5LFxuICAgICAgTk9URVNfRElSOiB0aGlzLnNldHRpbmdzLm9ic2lkaWFuRGlyZWN0b3J5LFxuICAgICAgREFUQV9ESVI6IHRoaXMuc2V0dGluZ3MuZGF0YURpcmVjdG9yeSxcbiAgICAgIEtOT1dMRURHRV9ESVI6IHRoaXMuc2V0dGluZ3Mua25vd2xlZGdlRGlyZWN0b3J5LFxuICAgICAgTE9HU19ESVI6IHRoaXMuc2V0dGluZ3MubG9nc0RpcmVjdG9yeSxcbiAgICAgIFFVRVJJRVNfRElSOiB0aGlzLnNldHRpbmdzLnF1ZXJpZXNEaXJlY3RvcnksXG4gICAgICBBR0VOVF9TVE9SQUdFX0RJUjogdGhpcy5zZXR0aW5ncy5hZ2VudFN0b3JhZ2VEaXJlY3RvcnksXG4gICAgICBQREZfRElSOiB0aGlzLnNldHRpbmdzLnBkZkRpcmVjdG9yeSxcbiAgICAgIFBST01QVFNfRElSOiB0aGlzLnNldHRpbmdzLnByb21wdHNEaXJlY3RvcnkgfHwgcGF0aC5qb2luKHRoaXMuc2V0dGluZ3Mud29ya3NwYWNlRGlyZWN0b3J5LCAndGVtcGxhdGVzL3Byb21wdHMnKSxcblxuICAgICAgLy8gU2VydmVyIHNldHRpbmdzXG4gICAgICBFTkRQT0lOVF9IT1NUOiB0aGlzLnNldHRpbmdzLmVuZHBvaW50SG9zdCxcbiAgICAgIEVORFBPSU5UX1BPUlQ6IHRoaXMuc2V0dGluZ3MuZW5kcG9pbnRQb3J0LnRvU3RyaW5nKCksXG4gICAgICBFTkRQT0lOVF9CQVNFX1VSTDogdGhpcy5zZXR0aW5ncy5lbmRwb2ludEJhc2VVcmwsXG5cbiAgICAgIC8vIFBsdWdpbiBDb25maWd1cmF0aW9uXG4gICAgICBSRVNFQVJDSF9BR0VOVF9BVVRPX1NUQVJUOiB0aGlzLnNldHRpbmdzLnJlc2VhcmNoQWdlbnRBdXRvU3RhcnQudG9TdHJpbmcoKSxcbiAgICAgIFJFU0VBUkNIX0FHRU5UX0RFRkFVTFRfUVVFUklFUzogdGhpcy5zZXR0aW5ncy5yZXNlYXJjaEFnZW50RGVmYXVsdFF1ZXJpZXMudG9TdHJpbmcoKSxcbiAgICAgIFJFU0VBUkNIX0FHRU5UX01FTU9SWV9FTkFCTEVEOiB0aGlzLnNldHRpbmdzLnJlc2VhcmNoQWdlbnRNZW1vcnlFbmFibGVkLnRvU3RyaW5nKCksXG4gICAgICBBR0VOVF9NQVhfVE9PTF9DQUxMUzogdGhpcy5zZXR0aW5ncy5hZ2VudE1heFRvb2xDYWxscy50b1N0cmluZygpLFxuICAgICAgQUdFTlRfVElNRU9VVF9TRUNPTkRTOiB0aGlzLnNldHRpbmdzLmFnZW50VGltZW91dFNlY29uZHMudG9TdHJpbmcoKSxcblxuICAgICAgLy8gRGlzY292ZXJ5IENvbmZpZ3VyYXRpb25cbiAgICAgIERJU0NPVkVSWV9BVVRPX1NUQVJUX1NDSEVEVUxFUjogdGhpcy5zZXR0aW5ncy5kaXNjb3ZlcnlBdXRvU3RhcnRTY2hlZHVsZXIudG9TdHJpbmcoKSxcbiAgICAgIERJU0NPVkVSWV9ERUZBVUxUX01BWF9BUlRJQ0xFUzogdGhpcy5zZXR0aW5ncy5kaXNjb3ZlcnlEZWZhdWx0TWF4QXJ0aWNsZXMudG9TdHJpbmcoKSxcbiAgICAgIERJU0NPVkVSWV9ERUZBVUxUX0lOVEVSVkFMX01JTlVURVM6IHRoaXMuc2V0dGluZ3MuZGlzY292ZXJ5RGVmYXVsdEludGVydmFsTWludXRlcy50b1N0cmluZygpLFxuICAgICAgRElTQ09WRVJZX1JBVEVfTElNSVRfREVMQVk6IHRoaXMuc2V0dGluZ3MuZGlzY292ZXJ5UmF0ZUxpbWl0RGVsYXkudG9TdHJpbmcoKSxcbiAgICAgIERJU0NPVkVSWV9DSFJPTUVfRVhURU5TSU9OX0VOQUJMRUQ6IHRoaXMuc2V0dGluZ3MuZGlzY292ZXJ5Q2hyb21lRXh0ZW5zaW9uRW5hYmxlZC50b1N0cmluZygpLFxuICAgICAgRElTQ09WRVJZX0NIUk9NRV9FWFRFTlNJT05fUE9SVDogdGhpcy5zZXR0aW5ncy5kaXNjb3ZlcnlDaHJvbWVFeHRlbnNpb25Qb3J0LnRvU3RyaW5nKCksXG5cbiAgICAgIC8vIExvZ2dpbmcgQ29uZmlndXJhdGlvblxuICAgICAgTE9HX0xFVkVMOiB0aGlzLnNldHRpbmdzLmxvZ0xldmVsLFxuICAgICAgTE9HX0ZPUk1BVDogdGhpcy5zZXR0aW5ncy5sb2dGb3JtYXQsXG4gICAgICBMT0dfUk9UQVRJT046IHRoaXMuc2V0dGluZ3MubG9nUm90YXRpb24sXG4gICAgICBMT0dfUkVURU5USU9OOiB0aGlzLnNldHRpbmdzLmxvZ1JldGVudGlvbixcbiAgICAgIEVOQUJMRV9QRVJGT1JNQU5DRV9NT05JVE9SSU5HOiB0aGlzLnNldHRpbmdzLmVuYWJsZVBlcmZvcm1hbmNlTW9uaXRvcmluZy50b1N0cmluZygpLFxuICAgICAgTUVUUklDU19JTlRFUlZBTDogdGhpcy5zZXR0aW5ncy5tZXRyaWNzSW50ZXJ2YWwudG9TdHJpbmcoKSxcblxuICAgICAgLy8gU2VjdXJpdHkgJiBQZXJmb3JtYW5jZVxuICAgICAgRU5DUllQVElPTl9LRVk6IHRoaXMuc2V0dGluZ3MuZW5jcnlwdGlvbktleSxcbiAgICAgIFNFU1NJT05fVElNRU9VVDogdGhpcy5zZXR0aW5ncy5zZXNzaW9uVGltZW91dC50b1N0cmluZygpLFxuICAgICAgQVBJX1JBVEVfTElNSVQ6IHRoaXMuc2V0dGluZ3MuYXBpUmF0ZUxpbWl0LnRvU3RyaW5nKCksXG4gICAgICBIRUFMVEhfQ0hFQ0tfVElNRU9VVDogdGhpcy5zZXR0aW5ncy5oZWFsdGhDaGVja1RpbWVvdXQudG9TdHJpbmcoKSxcbiAgICAgIERFVkVMT1BNRU5UX01PREU6IHRoaXMuc2V0dGluZ3MuZGV2ZWxvcG1lbnRNb2RlLnRvU3RyaW5nKCksXG5cbiAgICAgIC8vIExMTSBDb25maWd1cmF0aW9uXG4gICAgICBQUklNQVJZX0xMTV9NT0RFTDogdGhpcy5zZXR0aW5ncy5wcmltYXJ5TGxtTW9kZWwsXG4gICAgICBBTkFMWVNJU19MTE1fTU9ERUw6IHRoaXMuc2V0dGluZ3MuYW5hbHlzaXNMbG1Nb2RlbCxcbiAgICAgIFJFU0VBUkNIX0FHRU5UX01PREVMOiB0aGlzLnNldHRpbmdzLnJlc2VhcmNoQWdlbnRNb2RlbCxcbiAgICAgIExMTV9URU1QRVJBVFVSRTogdGhpcy5zZXR0aW5ncy5sbG1UZW1wZXJhdHVyZS50b1N0cmluZygpLFxuICAgICAgQU5BTFlTSVNfTExNX1RFTVBFUkFUVVJFOiB0aGlzLnNldHRpbmdzLmFuYWx5c2lzTGxtVGVtcGVyYXR1cmUudG9TdHJpbmcoKSxcbiAgICAgIExMTV9NQVhfT1VUUFVUX1RPS0VOUzogdGhpcy5zZXR0aW5ncy5sbG1NYXhPdXRwdXRUb2tlbnMudG9TdHJpbmcoKSxcbiAgICAgIEFOQUxZU0lTX0xMTV9NQVhfT1VUUFVUX1RPS0VOUzogdGhpcy5zZXR0aW5ncy5hbmFseXNpc0xsbU1heE91dHB1dFRva2Vucy50b1N0cmluZygpLFxuXG4gICAgICAvLyBSZW1vdGUgQ29ubmVjdGlvblxuICAgICAgUkVNT1RFX01PREU6IHRoaXMuc2V0dGluZ3MucmVtb3RlTW9kZS50b1N0cmluZygpLFxuICAgICAgUkVNT1RFX0VORFBPSU5UX1VSTDogdGhpcy5zZXR0aW5ncy5yZW1vdGVFbmRwb2ludFVybCxcblxuICAgICAgLy8gQ29ycyBPcmlnaW5zXG4gICAgICBDT1JTX09SSUdJTlM6IHRoaXMuc2V0dGluZ3MuY29yc09yaWdpbnMuam9pbignLCcpLFxuICAgIH07XG4gIH1cblxuICBwcml2YXRlIGFzeW5jIHVwZGF0ZUVudmlyb25tZW50RmlsZSgpOiBQcm9taXNlPHZvaWQ+IHtcbiAgICB0cnkge1xuICAgICAgLy8gR2VuZXJhdGUgY29tcHJlaGVuc2l2ZSAuZW52IGZpbGUgd2l0aCBhbGwgc2V0dGluZ3NcbiAgICAgIGNvbnN0IGxpbmVzID0gW1xuICAgICAgICAnIyBUaG90aCBBSSBSZXNlYXJjaCBBZ2VudCBDb25maWd1cmF0aW9uJyxcbiAgICAgICAgJyMgR2VuZXJhdGVkIGJ5IE9ic2lkaWFuIFBsdWdpbicsXG4gICAgICAgICcnLFxuICAgICAgICAnIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tJyxcbiAgICAgICAgJyMgLS0tIDEuIEFQSSBLZXlzIC0tLScsXG4gICAgICAgICcjIC0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0nLFxuICAgICAgICBgQVBJX01JU1RSQUxfS0VZPSR7dGhpcy5zZXR0aW5ncy5taXN0cmFsS2V5fWAsXG4gICAgICAgIGBBUElfT1BFTlJPVVRFUl9LRVk9JHt0aGlzLnNldHRpbmdzLm9wZW5yb3V0ZXJLZXl9YCxcbiAgICAgICAgYEFQSV9PUEVOQ0lUQVRJT05TX0tFWT0ke3RoaXMuc2V0dGluZ3Mub3BlbmNpdGF0aW9uc0tleX1gLFxuICAgICAgICBgQVBJX0dPT0dMRV9BUElfS0VZPSR7dGhpcy5zZXR0aW5ncy5nb29nbGVBcGlLZXl9YCxcbiAgICAgICAgYEFQSV9HT09HTEVfU0VBUkNIX0VOR0lORV9JRD0ke3RoaXMuc2V0dGluZ3MuZ29vZ2xlU2VhcmNoRW5naW5lSWR9YCxcbiAgICAgICAgYEFQSV9TRU1BTlRJQ19TQ0hPTEFSX0tFWT0ke3RoaXMuc2V0dGluZ3Muc2VtYW50aWNTY2hvbGFyS2V5fWAsXG4gICAgICAgICcnLFxuICAgICAgICAnIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tJyxcbiAgICAgICAgJyMgLS0tIDIuIERpcmVjdG9yeSBDb25maWd1cmF0aW9uIC0tLScsXG4gICAgICAgICcjIC0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0nLFxuICAgICAgICBgV09SS1NQQUNFX0RJUj0ke3RoaXMuc2V0dGluZ3Mud29ya3NwYWNlRGlyZWN0b3J5fWAsXG4gICAgICAgIGBOT1RFU19ESVI9JHt0aGlzLnNldHRpbmdzLm9ic2lkaWFuRGlyZWN0b3J5fWAsXG4gICAgICAgIGBEQVRBX0RJUj0ke3RoaXMuc2V0dGluZ3MuZGF0YURpcmVjdG9yeX1gLFxuICAgICAgICBgS05PV0xFREdFX0RJUj0ke3RoaXMuc2V0dGluZ3Mua25vd2xlZGdlRGlyZWN0b3J5fWAsXG4gICAgICAgIGBMT0dTX0RJUj0ke3RoaXMuc2V0dGluZ3MubG9nc0RpcmVjdG9yeX1gLFxuICAgICAgICBgUVVFUklFU19ESVI9JHt0aGlzLnNldHRpbmdzLnF1ZXJpZXNEaXJlY3Rvcnl9YCxcbiAgICAgICAgYEFHRU5UX1NUT1JBR0VfRElSPSR7dGhpcy5zZXR0aW5ncy5hZ2VudFN0b3JhZ2VEaXJlY3Rvcnl9YCxcbiAgICAgICAgYFBERl9ESVI9JHt0aGlzLnNldHRpbmdzLnBkZkRpcmVjdG9yeX1gLFxuICAgICAgICBgUFJPTVBUU19ESVI9JHt0aGlzLnNldHRpbmdzLnByb21wdHNEaXJlY3RvcnkgfHwgYCR7dGhpcy5zZXR0aW5ncy53b3Jrc3BhY2VEaXJlY3Rvcnl9L3RlbXBsYXRlcy9wcm9tcHRzYH1gLFxuICAgICAgICAnJyxcbiAgICAgICAgJyMgLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLScsXG4gICAgICAgICcjIC0tLSAzLiBTZXJ2ZXIgQ29uZmlndXJhdGlvbiAtLS0nLFxuICAgICAgICAnIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tJyxcbiAgICAgICAgYEVORFBPSU5UX0hPU1Q9JHt0aGlzLnNldHRpbmdzLmVuZHBvaW50SG9zdH1gLFxuICAgICAgICBgRU5EUE9JTlRfUE9SVD0ke3RoaXMuc2V0dGluZ3MuZW5kcG9pbnRQb3J0fWAsXG4gICAgICAgIGBFTkRQT0lOVF9CQVNFX1VSTD0ke3RoaXMuc2V0dGluZ3MuZW5kcG9pbnRCYXNlVXJsfWAsXG4gICAgICAgICcnLFxuICAgICAgICAnIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tJyxcbiAgICAgICAgJyMgLS0tIDQuIFBsdWdpbiBDb25maWd1cmF0aW9uIC0tLScsXG4gICAgICAgICcjIC0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0nLFxuICAgICAgICBgIyBQbHVnaW4gYXV0by1zdGFydDogJHt0aGlzLnNldHRpbmdzLnJlc2VhcmNoQWdlbnRBdXRvU3RhcnR9YCxcbiAgICAgICAgYCMgU2hvdyBzdGF0dXMgYmFyOiAke3RoaXMuc2V0dGluZ3Muc2hvd1N0YXR1c0Jhcn1gLFxuICAgICAgICBgIyBSZW1vdGUgbW9kZTogJHt0aGlzLnNldHRpbmdzLnJlbW90ZU1vZGV9YCxcbiAgICAgICAgJycsXG4gICAgICAgICcjIC0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0nLFxuICAgICAgICAnIyAtLS0gNS4gRGVmYXVsdCBTZXR0aW5ncyAtLS0nLFxuICAgICAgICAnIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tJyxcbiAgICAgICAgJ1JFU0VBUkNIX0FHRU5UX0FVVE9fU1RBUlQ9ZmFsc2UnLFxuICAgICAgICAnUkVTRUFSQ0hfQUdFTlRfREVGQVVMVF9RVUVSSUVTPXRydWUnLFxuICAgICAgICAnUkVTRUFSQ0hfQUdFTlRfTUVNT1JZX0VOQUJMRUQ9dHJ1ZScsXG4gICAgICAgICdBR0VOVF9NQVhfVE9PTF9DQUxMUz01JyxcbiAgICAgICAgJ0FHRU5UX1RJTUVPVVRfU0VDT05EUz0zMDAnLFxuICAgICAgICAnTE9HX0xFVkVMPUlORk8nLFxuICAgICAgICAnTE9HX0ZPUk1BVD10ZXh0JyxcbiAgICAgICAgJ0xPR19ST1RBVElPTj1kYWlseScsXG4gICAgICAgICdMT0dfUkVURU5USU9OPTMwIGRheXMnLFxuICAgICAgICAnRU5BQkxFX1BFUkZPUk1BTkNFX01PTklUT1JJTkc9dHJ1ZScsXG4gICAgICAgICdNRVRSSUNTX0lOVEVSVkFMPTYwJyxcbiAgICAgIF07XG5cbiAgICAgIGNvbnN0IGVudlBhdGggPSBwYXRoLmpvaW4odGhpcy5zZXR0aW5ncy53b3Jrc3BhY2VEaXJlY3RvcnksICcuZW52Jyk7XG4gICAgICBhd2FpdCBmcy5wcm9taXNlcy53cml0ZUZpbGUoZW52UGF0aCwgbGluZXMuam9pbignXFxuJykpO1xuXG4gICAgICBjb25zb2xlLmxvZygnRW52aXJvbm1lbnQgZmlsZSB1cGRhdGVkIHN1Y2Nlc3NmdWxseScpO1xuICAgIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgICBjb25zb2xlLmVycm9yKCdGYWlsZWQgdG8gdXBkYXRlIGVudmlyb25tZW50IGZpbGU6JywgZXJyb3IpO1xuICAgICAgdGhyb3cgZXJyb3I7XG4gICAgfVxuICB9XG5cbiAgdXBkYXRlU3RhdHVzQmFyKCkge1xuICAgIGlmICghdGhpcy5zdGF0dXNCYXJJdGVtKSByZXR1cm47XG5cbiAgICBpZiAodGhpcy5pc1Jlc3RhcnRpbmcpIHtcbiAgICAgIHRoaXMuc3RhdHVzQmFySXRlbS5zZXRUZXh0KCdUaG90aDogUmVzdGFydGluZy4uLicpO1xuICAgICAgdGhpcy5zdGF0dXNCYXJJdGVtLnN0eWxlLmNvbG9yID0gJyNmZmE1MDAnOyAvLyBPcmFuZ2VcbiAgICB9IGVsc2UgaWYgKHRoaXMuaXNBZ2VudFJ1bm5pbmcpIHtcbiAgICAgIHRoaXMuc3RhdHVzQmFySXRlbS5zZXRUZXh0KCdUaG90aDogUnVubmluZycpO1xuICAgICAgdGhpcy5zdGF0dXNCYXJJdGVtLnN0eWxlLmNvbG9yID0gJyMwMGZmMDAnOyAvLyBHcmVlblxuICAgIH0gZWxzZSB7XG4gICAgICB0aGlzLnN0YXR1c0Jhckl0ZW0uc2V0VGV4dCgnVGhvdGg6IFN0b3BwZWQnKTtcbiAgICAgIHRoaXMuc3RhdHVzQmFySXRlbS5zdHlsZS5jb2xvciA9ICcjZmYwMDAwJzsgLy8gUmVkXG4gICAgfVxuICB9XG5cbiAgYXN5bmMgcGVyZm9ybVJlc2VhcmNoKHF1ZXJ5OiBzdHJpbmcsIGVkaXRvcjogRWRpdG9yKSB7XG4gICAgaWYgKCF0aGlzLmlzQWdlbnRSdW5uaW5nKSB7XG4gICAgICBuZXcgTm90aWNlKCdUaG90aCBhZ2VudCBpcyBub3QgcnVubmluZy4gUGxlYXNlIHN0YXJ0IGl0IGZpcnN0LicpO1xuICAgICAgcmV0dXJuO1xuICAgIH1cblxuICAgIHRyeSB7XG4gICAgICBuZXcgTm90aWNlKCdSZXNlYXJjaGluZy4uLiBUaGlzIG1heSB0YWtlIGEgbW9tZW50LicpO1xuXG4gICAgICBjb25zdCBlbmRwb2ludCA9IHRoaXMuZ2V0RW5kcG9pbnRVcmwoKTtcbiAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZmV0Y2goYCR7ZW5kcG9pbnR9L3Jlc2VhcmNoL3F1ZXJ5YCwge1xuICAgICAgICBtZXRob2Q6ICdQT1NUJyxcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgIH0sXG4gICAgICAgIGJvZHk6IEpTT04uc3RyaW5naWZ5KHtcbiAgICAgICAgICBxdWVyeTogcXVlcnksXG4gICAgICAgICAgdHlwZTogJ3F1aWNrX3Jlc2VhcmNoJyxcbiAgICAgICAgICBtYXhfcmVzdWx0czogNSxcbiAgICAgICAgICBpbmNsdWRlX2NpdGF0aW9uczogdHJ1ZVxuICAgICAgICB9KSxcbiAgICAgIH0pO1xuXG4gICAgICBpZiAocmVzcG9uc2Uub2spIHtcbiAgICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgcmVzcG9uc2UuanNvbigpO1xuXG4gICAgICAgIC8vIEluc2VydCB0aGUgcmVzZWFyY2ggcmVzdWx0cyBhdCB0aGUgY3Vyc29yIHBvc2l0aW9uXG4gICAgICAgIGNvbnN0IGN1cnNvciA9IGVkaXRvci5nZXRDdXJzb3IoKTtcbiAgICAgICAgY29uc3QgcmVzZWFyY2hUZXh0ID0gYFxcblxcbiMjIPCflI0gUmVzZWFyY2g6ICR7cXVlcnl9XFxuKkdlbmVyYXRlZCBvbiAke25ldyBEYXRlKCkudG9Mb2NhbGVTdHJpbmcoKX0gYnkgVGhvdGggUmVzZWFyY2ggQXNzaXN0YW50KlxcblxcbiR7cmVzdWx0LnJlc3BvbnNlfVxcblxcbi0tLVxcbmA7XG5cbiAgICAgICAgZWRpdG9yLnJlcGxhY2VSYW5nZShyZXNlYXJjaFRleHQsIGN1cnNvcik7XG4gICAgICAgIG5ldyBOb3RpY2UoJ1Jlc2VhcmNoIGNvbXBsZXRlZCBhbmQgaW5zZXJ0ZWQhJyk7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICB0aHJvdyBuZXcgRXJyb3IoYFJlc2VhcmNoIHJlcXVlc3QgZmFpbGVkOiAke3Jlc3BvbnNlLnN0YXR1c1RleHR9YCk7XG4gICAgICB9XG4gICAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICAgIGNvbnNvbGUuZXJyb3IoJ1Jlc2VhcmNoIGVycm9yOicsIGVycm9yKTtcbiAgICAgIG5ldyBOb3RpY2UoYFJlc2VhcmNoIGZhaWxlZDogJHtlcnJvci5tZXNzYWdlfWApO1xuICAgIH1cbiAgfVxuXG4gIG9wZW5DaGF0TW9kYWwoKSB7XG4gICAgbmV3IENoYXRNb2RhbCh0aGlzLmFwcCwgdGhpcykub3BlbigpO1xuICB9XG59XG5cbmNsYXNzIENoYXRNb2RhbCBleHRlbmRzIE1vZGFsIHtcbiAgcGx1Z2luOiBUaG90aFBsdWdpbjtcbiAgY2hhdENvbnRhaW5lcjogSFRNTEVsZW1lbnQ7XG4gIGlucHV0RWxlbWVudDogSFRNTFRleHRBcmVhRWxlbWVudDtcbiAgc2VuZEJ1dHRvbjogSFRNTEJ1dHRvbkVsZW1lbnQ7XG5cbiAgY29uc3RydWN0b3IoYXBwOiBBcHAsIHBsdWdpbjogVGhvdGhQbHVnaW4pIHtcbiAgICBzdXBlcihhcHApO1xuICAgIHRoaXMucGx1Z2luID0gcGx1Z2luO1xuICB9XG5cbiAgb25PcGVuKCkge1xuICAgIGNvbnN0IHsgY29udGVudEVsIH0gPSB0aGlzO1xuICAgIGNvbnRlbnRFbC5lbXB0eSgpO1xuXG4gICAgLy8gU2V0IG1vZGFsIHRpdGxlXG4gICAgY29udGVudEVsLmNyZWF0ZUVsKCdoMicsIHsgdGV4dDogJ1Rob3RoIFJlc2VhcmNoIEFzc2lzdGFudCcgfSk7XG5cbiAgICAvLyBDaGVjayBpZiBhZ2VudCBpcyBydW5uaW5nXG4gICAgaWYgKCF0aGlzLnBsdWdpbi5pc0FnZW50UnVubmluZykge1xuICAgICAgY29uc3Qgd2FybmluZ0VsID0gY29udGVudEVsLmNyZWF0ZUVsKCdkaXYnLCB7XG4gICAgICAgIGNsczogJ3Rob3RoLXdhcm5pbmcnLFxuICAgICAgICB0ZXh0OiAn4pqg77iPIFRob3RoIGFnZW50IGlzIG5vdCBydW5uaW5nLiBQbGVhc2Ugc3RhcnQgaXQgZmlyc3QuJ1xuICAgICAgfSk7XG4gICAgICB3YXJuaW5nRWwuc3R5bGUuY3NzVGV4dCA9ICdjb2xvcjogb3JhbmdlOyBtYXJnaW4tYm90dG9tOiAxMHB4OyBwYWRkaW5nOiAxMHB4OyBib3JkZXI6IDFweCBzb2xpZCBvcmFuZ2U7IGJvcmRlci1yYWRpdXM6IDRweDsnO1xuXG4gICAgICBjb25zdCBzdGFydEJ1dHRvbiA9IHdhcm5pbmdFbC5jcmVhdGVFbCgnYnV0dG9uJywgeyB0ZXh0OiAnU3RhcnQgQWdlbnQnIH0pO1xuICAgICAgc3RhcnRCdXR0b24ub25jbGljayA9ICgpID0+IHtcbiAgICAgICAgdGhpcy5wbHVnaW4uc3RhcnRBZ2VudCgpO1xuICAgICAgICB0aGlzLmNsb3NlKCk7XG4gICAgICB9O1xuICAgICAgcmV0dXJuO1xuICAgIH1cblxuICAgIC8vIENyZWF0ZSBjaGF0IGNvbnRhaW5lclxuICAgIHRoaXMuY2hhdENvbnRhaW5lciA9IGNvbnRlbnRFbC5jcmVhdGVFbCgnZGl2JywgeyBjbHM6ICd0aG90aC1jaGF0LWNvbnRhaW5lcicgfSk7XG4gICAgdGhpcy5jaGF0Q29udGFpbmVyLnN0eWxlLmNzc1RleHQgPSAnaGVpZ2h0OiA0MDBweDsgb3ZlcmZsb3cteTogYXV0bzsgYm9yZGVyOiAxcHggc29saWQgdmFyKC0tYmFja2dyb3VuZC1tb2RpZmllci1ib3JkZXIpOyBtYXJnaW4tYm90dG9tOiAxMHB4OyBwYWRkaW5nOiAxMHB4Oyc7XG5cbiAgICAvLyBMb2FkIGNoYXQgaGlzdG9yeVxuICAgIHRoaXMubG9hZENoYXRIaXN0b3J5KCk7XG5cbiAgICAvLyBDcmVhdGUgaW5wdXQgYXJlYVxuICAgIGNvbnN0IGlucHV0Q29udGFpbmVyID0gY29udGVudEVsLmNyZWF0ZUVsKCdkaXYnLCB7IGNsczogJ3Rob3RoLWlucHV0LWNvbnRhaW5lcicgfSk7XG4gICAgaW5wdXRDb250YWluZXIuc3R5bGUuY3NzVGV4dCA9ICdkaXNwbGF5OiBmbGV4OyBnYXA6IDEwcHg7JztcblxuICAgIHRoaXMuaW5wdXRFbGVtZW50ID0gaW5wdXRDb250YWluZXIuY3JlYXRlRWwoJ3RleHRhcmVhJywge1xuICAgICAgcGxhY2Vob2xkZXI6ICdBc2sgbWUgYWJvdXQgeW91ciByZXNlYXJjaC4uLidcbiAgICB9KTtcbiAgICB0aGlzLmlucHV0RWxlbWVudC5zdHlsZS5jc3NUZXh0ID0gJ2ZsZXg6IDE7IG1pbi1oZWlnaHQ6IDYwcHg7IHJlc2l6ZTogdmVydGljYWw7JztcblxuICAgIHRoaXMuc2VuZEJ1dHRvbiA9IGlucHV0Q29udGFpbmVyLmNyZWF0ZUVsKCdidXR0b24nLCB7IHRleHQ6ICdTZW5kJyB9KTtcbiAgICB0aGlzLnNlbmRCdXR0b24uc3R5bGUuY3NzVGV4dCA9ICdhbGlnbi1zZWxmOiBmbGV4LWVuZDsnO1xuXG4gICAgLy8gQWRkIGV2ZW50IGxpc3RlbmVyc1xuICAgIHRoaXMuc2VuZEJ1dHRvbi5vbmNsaWNrID0gKCkgPT4gdGhpcy5zZW5kTWVzc2FnZSgpO1xuICAgIHRoaXMuaW5wdXRFbGVtZW50LmFkZEV2ZW50TGlzdGVuZXIoJ2tleWRvd24nLCAoZSkgPT4ge1xuICAgICAgaWYgKGUua2V5ID09PSAnRW50ZXInICYmICFlLnNoaWZ0S2V5KSB7XG4gICAgICAgIGUucHJldmVudERlZmF1bHQoKTtcbiAgICAgICAgdGhpcy5zZW5kTWVzc2FnZSgpO1xuICAgICAgfVxuICAgIH0pO1xuXG4gICAgLy8gRm9jdXMgaW5wdXRcbiAgICB0aGlzLmlucHV0RWxlbWVudC5mb2N1cygpO1xuICB9XG5cbiAgbG9hZENoYXRIaXN0b3J5KCkge1xuICAgIGNvbnN0IGhpc3RvcnkgPSB0aGlzLnBsdWdpbi5zZXR0aW5ncy5jaGF0SGlzdG9yeSB8fCBbXTtcbiAgICBoaXN0b3J5LmZvckVhY2gobWVzc2FnZSA9PiB7XG4gICAgICB0aGlzLmFkZE1lc3NhZ2VUb0NoYXQobWVzc2FnZS5yb2xlLCBtZXNzYWdlLmNvbnRlbnQpO1xuICAgIH0pO1xuICAgIHRoaXMuc2Nyb2xsVG9Cb3R0b20oKTtcbiAgfVxuXG4gIGFkZE1lc3NhZ2VUb0NoYXQocm9sZTogJ3VzZXInIHwgJ2Fzc2lzdGFudCcsIGNvbnRlbnQ6IHN0cmluZykge1xuICAgIGNvbnN0IG1lc3NhZ2VFbCA9IHRoaXMuY2hhdENvbnRhaW5lci5jcmVhdGVFbCgnZGl2JywgeyBjbHM6IGB0aG90aC1tZXNzYWdlIHRob3RoLSR7cm9sZX1gIH0pO1xuXG4gICAgaWYgKHJvbGUgPT09ICd1c2VyJykge1xuICAgICAgbWVzc2FnZUVsLnN0eWxlLmNzc1RleHQgPSAndGV4dC1hbGlnbjogcmlnaHQ7IG1hcmdpbjogMTBweCAwOyBwYWRkaW5nOiA4cHg7IGJhY2tncm91bmQtY29sb3I6IHZhcigtLWludGVyYWN0aXZlLWFjY2VudCk7IGNvbG9yOiB3aGl0ZTsgYm9yZGVyLXJhZGl1czogOHB4Oyc7XG4gICAgfSBlbHNlIHtcbiAgICAgIG1lc3NhZ2VFbC5zdHlsZS5jc3NUZXh0ID0gJ3RleHQtYWxpZ246IGxlZnQ7IG1hcmdpbjogMTBweCAwOyBwYWRkaW5nOiA4cHg7IGJhY2tncm91bmQtY29sb3I6IHZhcigtLWJhY2tncm91bmQtc2Vjb25kYXJ5KTsgYm9yZGVyLXJhZGl1czogOHB4Oyc7XG4gICAgfVxuXG4gICAgbWVzc2FnZUVsLmNyZWF0ZUVsKCdkaXYnLCB7IHRleHQ6IHJvbGUgPT09ICd1c2VyJyA/ICdZb3UnIDogJ0Fzc2lzdGFudCcsIGNsczogJ3Rob3RoLW1lc3NhZ2Utcm9sZScgfSkuc3R5bGUuY3NzVGV4dCA9ICdmb250LXdlaWdodDogYm9sZDsgbWFyZ2luLWJvdHRvbTogNHB4OyBmb250LXNpemU6IDAuOWVtOyc7XG4gICAgbWVzc2FnZUVsLmNyZWF0ZUVsKCdkaXYnLCB7IHRleHQ6IGNvbnRlbnQsIGNsczogJ3Rob3RoLW1lc3NhZ2UtY29udGVudCcgfSk7XG4gIH1cblxuICBhc3luYyBzZW5kTWVzc2FnZSgpIHtcbiAgICBjb25zdCBtZXNzYWdlID0gdGhpcy5pbnB1dEVsZW1lbnQudmFsdWUudHJpbSgpO1xuICAgIGlmICghbWVzc2FnZSkgcmV0dXJuO1xuXG4gICAgLy8gQWRkIHVzZXIgbWVzc2FnZSB0byBjaGF0XG4gICAgdGhpcy5hZGRNZXNzYWdlVG9DaGF0KCd1c2VyJywgbWVzc2FnZSk7XG4gICAgdGhpcy5pbnB1dEVsZW1lbnQudmFsdWUgPSAnJztcbiAgICB0aGlzLnNjcm9sbFRvQm90dG9tKCk7XG5cbiAgICAvLyBEaXNhYmxlIHNlbmQgYnV0dG9uXG4gICAgdGhpcy5zZW5kQnV0dG9uLmRpc2FibGVkID0gdHJ1ZTtcbiAgICB0aGlzLnNlbmRCdXR0b24udGV4dENvbnRlbnQgPSAnU2VuZGluZy4uLic7XG5cbiAgICB0cnkge1xuICAgICAgY29uc3QgZW5kcG9pbnQgPSB0aGlzLnBsdWdpbi5nZXRFbmRwb2ludFVybCgpO1xuICAgICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBmZXRjaChgJHtlbmRwb2ludH0vcmVzZWFyY2gvY2hhdGAsIHtcbiAgICAgICAgbWV0aG9kOiAnUE9TVCcsXG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICB9LFxuICAgICAgICBib2R5OiBKU09OLnN0cmluZ2lmeSh7XG4gICAgICAgICAgbWVzc2FnZTogbWVzc2FnZSxcbiAgICAgICAgICBjb252ZXJzYXRpb25faWQ6ICdvYnNpZGlhbi1jaGF0JyxcbiAgICAgICAgICB0aW1lc3RhbXA6IERhdGUubm93KClcbiAgICAgICAgfSksXG4gICAgICB9KTtcblxuICAgICAgaWYgKHJlc3BvbnNlLm9rKSB7XG4gICAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IHJlc3BvbnNlLmpzb24oKTtcblxuICAgICAgICAvLyBBZGQgYXNzaXN0YW50IHJlc3BvbnNlIHRvIGNoYXRcbiAgICAgICAgdGhpcy5hZGRNZXNzYWdlVG9DaGF0KCdhc3Npc3RhbnQnLCByZXN1bHQucmVzcG9uc2UpO1xuXG4gICAgICAgIC8vIFNhdmUgdG8gY2hhdCBoaXN0b3J5XG4gICAgICAgIHRoaXMucGx1Z2luLnNldHRpbmdzLmNoYXRIaXN0b3J5LnB1c2goXG4gICAgICAgICAgeyByb2xlOiAndXNlcicsIGNvbnRlbnQ6IG1lc3NhZ2UsIHRpbWVzdGFtcDogRGF0ZS5ub3coKSB9LFxuICAgICAgICAgIHsgcm9sZTogJ2Fzc2lzdGFudCcsIGNvbnRlbnQ6IHJlc3VsdC5yZXNwb25zZSwgdGltZXN0YW1wOiBEYXRlLm5vdygpIH1cbiAgICAgICAgKTtcblxuICAgICAgICAvLyBLZWVwIG9ubHkgbGFzdCAyMCBtZXNzYWdlc1xuICAgICAgICBpZiAodGhpcy5wbHVnaW4uc2V0dGluZ3MuY2hhdEhpc3RvcnkubGVuZ3RoID4gMjApIHtcbiAgICAgICAgICB0aGlzLnBsdWdpbi5zZXR0aW5ncy5jaGF0SGlzdG9yeSA9IHRoaXMucGx1Z2luLnNldHRpbmdzLmNoYXRIaXN0b3J5LnNsaWNlKC0yMCk7XG4gICAgICAgIH1cblxuICAgICAgICBhd2FpdCB0aGlzLnBsdWdpbi5zYXZlU2V0dGluZ3MoKTtcblxuICAgICAgfSBlbHNlIHtcbiAgICAgICAgdGhyb3cgbmV3IEVycm9yKGBDaGF0IHJlcXVlc3QgZmFpbGVkOiAke3Jlc3BvbnNlLnN0YXR1c1RleHR9YCk7XG4gICAgICB9XG4gICAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICAgIGNvbnNvbGUuZXJyb3IoJ0NoYXQgZXJyb3I6JywgZXJyb3IpO1xuICAgICAgdGhpcy5hZGRNZXNzYWdlVG9DaGF0KCdhc3Npc3RhbnQnLCBgRXJyb3I6ICR7ZXJyb3IubWVzc2FnZX1gKTtcbiAgICB9IGZpbmFsbHkge1xuICAgICAgdGhpcy5zZW5kQnV0dG9uLmRpc2FibGVkID0gZmFsc2U7XG4gICAgICB0aGlzLnNlbmRCdXR0b24udGV4dENvbnRlbnQgPSAnU2VuZCc7XG4gICAgICB0aGlzLnNjcm9sbFRvQm90dG9tKCk7XG4gICAgfVxuICB9XG5cbiAgc2Nyb2xsVG9Cb3R0b20oKSB7XG4gICAgdGhpcy5jaGF0Q29udGFpbmVyLnNjcm9sbFRvcCA9IHRoaXMuY2hhdENvbnRhaW5lci5zY3JvbGxIZWlnaHQ7XG4gIH1cblxuICBvbkNsb3NlKCkge1xuICAgIGNvbnN0IHsgY29udGVudEVsIH0gPSB0aGlzO1xuICAgIGNvbnRlbnRFbC5lbXB0eSgpO1xuICB9XG59XG5cbmNsYXNzIFRob3RoU2V0dGluZ1RhYiBleHRlbmRzIFBsdWdpblNldHRpbmdUYWIge1xuICBwbHVnaW46IFRob3RoUGx1Z2luO1xuXG4gIGNvbnN0cnVjdG9yKGFwcDogQXBwLCBwbHVnaW46IFRob3RoUGx1Z2luKSB7XG4gICAgc3VwZXIoYXBwLCBwbHVnaW4pO1xuICAgIHRoaXMucGx1Z2luID0gcGx1Z2luO1xuICB9XG5cbiAgZGlzcGxheSgpOiB2b2lkIHtcbiAgICBjb25zdCB7IGNvbnRhaW5lckVsIH0gPSB0aGlzO1xuICAgIGNvbnRhaW5lckVsLmVtcHR5KCk7XG5cbiAgICAvLyBIZWFkZXJcbiAgICBjb25zdCBoZWFkZXJFbCA9IGNvbnRhaW5lckVsLmNyZWF0ZUVsKCdkaXYnLCB7IGNsczogJ3Rob3RoLXNldHRpbmdzLWhlYWRlcicgfSk7XG4gICAgaGVhZGVyRWwuY3JlYXRlRWwoJ2gxJywgeyB0ZXh0OiAn8J+noCBUaG90aCBSZXNlYXJjaCBBc3Npc3RhbnQnIH0pO1xuICAgIGhlYWRlckVsLmNyZWF0ZUVsKCdwJywge1xuICAgICAgdGV4dDogJ0ludGVsbGlnZW50IHJlc2VhcmNoIGFzc2lzdGFudCBmb3IgYWNhZGVtaWMgd29yayBhbmQga25vd2xlZGdlIGRpc2NvdmVyeScsXG4gICAgICBjbHM6ICd0aG90aC1zZXR0aW5ncy1zdWJ0aXRsZSdcbiAgICB9KTtcblxuICAgIC8vIFF1aWNrIFN0YXR1c1xuICAgIHRoaXMuYWRkUXVpY2tTdGF0dXMoY29udGFpbmVyRWwpO1xuXG4gICAgLy8gRXNzZW50aWFsIFNldHRpbmdzIChhbHdheXMgdmlzaWJsZSlcbiAgICB0aGlzLmFkZEVzc2VudGlhbFNldHRpbmdzKGNvbnRhaW5lckVsKTtcblxuICAgIC8vIENvbm5lY3Rpb24gU2V0dGluZ3NcbiAgICB0aGlzLmFkZENvbm5lY3Rpb25TZXR0aW5ncyhjb250YWluZXJFbCk7XG5cbiAgICAvLyBBZHZhbmNlZCBTZXR0aW5ncyBUb2dnbGVcbiAgICBjb25zdCBhZHZhbmNlZFRvZ2dsZSA9IG5ldyBTZXR0aW5nKGNvbnRhaW5lckVsKVxuICAgICAgLnNldE5hbWUoJ/CflKcgU2hvdyBBZHZhbmNlZCBTZXR0aW5ncycpXG4gICAgICAuc2V0RGVzYygnQ29uZmlndXJlIExMTSBtb2RlbHMsIGFnZW50IGJlaGF2aW9yLCBkaXNjb3Zlcnkgc3lzdGVtLCBhbmQgbW9yZScpXG4gICAgICAuYWRkVG9nZ2xlKCh0b2dnbGUpID0+XG4gICAgICAgIHRvZ2dsZVxuICAgICAgICAgIC5zZXRWYWx1ZSh0aGlzLnBsdWdpbi5zZXR0aW5ncy5zaG93QWR2YW5jZWRTZXR0aW5ncylcbiAgICAgICAgICAub25DaGFuZ2UoYXN5bmMgKHZhbHVlKSA9PiB7XG4gICAgICAgICAgICB0aGlzLnBsdWdpbi5zZXR0aW5ncy5zaG93QWR2YW5jZWRTZXR0aW5ncyA9IHZhbHVlO1xuICAgICAgICAgICAgYXdhaXQgdGhpcy5wbHVnaW4uc2F2ZVNldHRpbmdzKCk7XG4gICAgICAgICAgICB0aGlzLmRpc3BsYXkoKTsgLy8gUmVmcmVzaCB0byBzaG93L2hpZGUgYWR2YW5jZWQgc2V0dGluZ3NcbiAgICAgICAgICB9KVxuICAgICAgKTtcblxuICAgIGlmICh0aGlzLnBsdWdpbi5zZXR0aW5ncy5zaG93QWR2YW5jZWRTZXR0aW5ncykge1xuICAgICAgdGhpcy5hZGRBZHZhbmNlZFNldHRpbmdzKGNvbnRhaW5lckVsKTtcbiAgICB9XG5cbiAgICAvLyBBZ2VudCBDb250cm9scyAoYWx3YXlzIHZpc2libGUgYXQgYm90dG9tKVxuICAgIHRoaXMuYWRkQWdlbnRDb250cm9scyhjb250YWluZXJFbCk7XG4gIH1cblxuICBwcml2YXRlIGFkZFF1aWNrU3RhdHVzKGNvbnRhaW5lckVsOiBIVE1MRWxlbWVudCk6IHZvaWQge1xuICAgIGNvbnN0IHN0YXR1c1NlY3Rpb24gPSBjb250YWluZXJFbC5jcmVhdGVFbCgnZGl2JywgeyBjbHM6ICd0aG90aC1zZXR0aW5ncy1zZWN0aW9uJyB9KTtcbiAgICBzdGF0dXNTZWN0aW9uLmNyZWF0ZUVsKCdoMicsIHsgdGV4dDogJ/Cfk4ogUXVpY2sgU3RhdHVzJyB9KTtcblxuICAgIGNvbnN0IHN0YXR1c0dyaWQgPSBzdGF0dXNTZWN0aW9uLmNyZWF0ZUVsKCdkaXYnLCB7IGNsczogJ3Rob3RoLXN0YXR1cy1ncmlkJyB9KTtcblxuICAgIC8vIEFnZW50IFN0YXR1c1xuICAgIGNvbnN0IGFnZW50U3RhdHVzID0gc3RhdHVzR3JpZC5jcmVhdGVFbCgnZGl2JywgeyBjbHM6ICd0aG90aC1zdGF0dXMtaXRlbScgfSk7XG4gICAgYWdlbnRTdGF0dXMuY3JlYXRlRWwoJ3NwYW4nLCB7IHRleHQ6ICdBZ2VudDogJywgY2xzOiAndGhvdGgtc3RhdHVzLWxhYmVsJyB9KTtcbiAgICBjb25zdCBhZ2VudEluZGljYXRvciA9IGFnZW50U3RhdHVzLmNyZWF0ZUVsKCdzcGFuJywgeyBjbHM6ICd0aG90aC1zdGF0dXMtaW5kaWNhdG9yJyB9KTtcblxuICAgIGlmICh0aGlzLnBsdWdpbi5pc1Jlc3RhcnRpbmcpIHtcbiAgICAgIGFnZW50SW5kaWNhdG9yLnRleHRDb250ZW50ID0gJ1Jlc3RhcnRpbmcuLi4nO1xuICAgICAgYWdlbnRJbmRpY2F0b3IuY2xhc3NOYW1lID0gJ3Rob3RoLXN0YXR1cy1pbmRpY2F0b3IgdGhvdGgtc3RhdHVzLXdhcm5pbmcnO1xuICAgIH0gZWxzZSBpZiAodGhpcy5wbHVnaW4uaXNBZ2VudFJ1bm5pbmcpIHtcbiAgICAgIGFnZW50SW5kaWNhdG9yLnRleHRDb250ZW50ID0gJ1J1bm5pbmcnO1xuICAgICAgYWdlbnRJbmRpY2F0b3IuY2xhc3NOYW1lID0gJ3Rob3RoLXN0YXR1cy1pbmRpY2F0b3IgdGhvdGgtc3RhdHVzLXN1Y2Nlc3MnO1xuICAgIH0gZWxzZSB7XG4gICAgICBhZ2VudEluZGljYXRvci50ZXh0Q29udGVudCA9ICdTdG9wcGVkJztcbiAgICAgIGFnZW50SW5kaWNhdG9yLmNsYXNzTmFtZSA9ICd0aG90aC1zdGF0dXMtaW5kaWNhdG9yIHRob3RoLXN0YXR1cy1lcnJvcic7XG4gICAgfVxuXG4gICAgLy8gQVBJIEtleXMgU3RhdHVzXG4gICAgY29uc3Qga2V5c1N0YXR1cyA9IHN0YXR1c0dyaWQuY3JlYXRlRWwoJ2RpdicsIHsgY2xzOiAndGhvdGgtc3RhdHVzLWl0ZW0nIH0pO1xuICAgIGtleXNTdGF0dXMuY3JlYXRlRWwoJ3NwYW4nLCB7IHRleHQ6ICdBUEkgS2V5czogJywgY2xzOiAndGhvdGgtc3RhdHVzLWxhYmVsJyB9KTtcbiAgICBjb25zdCBrZXlzSW5kaWNhdG9yID0ga2V5c1N0YXR1cy5jcmVhdGVFbCgnc3BhbicsIHsgY2xzOiAndGhvdGgtc3RhdHVzLWluZGljYXRvcicgfSk7XG5cbiAgICBjb25zdCBoYXNLZXlzID0gdGhpcy5wbHVnaW4uc2V0dGluZ3MubWlzdHJhbEtleSAmJiB0aGlzLnBsdWdpbi5zZXR0aW5ncy5vcGVucm91dGVyS2V5O1xuICAgIGlmIChoYXNLZXlzKSB7XG4gICAgICBrZXlzSW5kaWNhdG9yLnRleHRDb250ZW50ID0gJ0NvbmZpZ3VyZWQnO1xuICAgICAga2V5c0luZGljYXRvci5jbGFzc05hbWUgPSAndGhvdGgtc3RhdHVzLWluZGljYXRvciB0aG90aC1zdGF0dXMtc3VjY2Vzcyc7XG4gICAgfSBlbHNlIHtcbiAgICAgIGtleXNJbmRpY2F0b3IudGV4dENvbnRlbnQgPSAnTWlzc2luZyc7XG4gICAgICBrZXlzSW5kaWNhdG9yLmNsYXNzTmFtZSA9ICd0aG90aC1zdGF0dXMtaW5kaWNhdG9yIHRob3RoLXN0YXR1cy1lcnJvcic7XG4gICAgfVxuXG4gICAgLy8gQ29ubmVjdGlvbiBNb2RlXG4gICAgY29uc3QgbW9kZVN0YXR1cyA9IHN0YXR1c0dyaWQuY3JlYXRlRWwoJ2RpdicsIHsgY2xzOiAndGhvdGgtc3RhdHVzLWl0ZW0nIH0pO1xuICAgIG1vZGVTdGF0dXMuY3JlYXRlRWwoJ3NwYW4nLCB7IHRleHQ6ICdNb2RlOiAnLCBjbHM6ICd0aG90aC1zdGF0dXMtbGFiZWwnIH0pO1xuICAgIGNvbnN0IG1vZGVJbmRpY2F0b3IgPSBtb2RlU3RhdHVzLmNyZWF0ZUVsKCdzcGFuJywgeyBjbHM6ICd0aG90aC1zdGF0dXMtaW5kaWNhdG9yJyB9KTtcbiAgICBtb2RlSW5kaWNhdG9yLnRleHRDb250ZW50ID0gdGhpcy5wbHVnaW4uc2V0dGluZ3MucmVtb3RlTW9kZSA/ICdSZW1vdGUnIDogJ0xvY2FsJztcbiAgICBtb2RlSW5kaWNhdG9yLmNsYXNzTmFtZSA9ICd0aG90aC1zdGF0dXMtaW5kaWNhdG9yIHRob3RoLXN0YXR1cy1pbmZvJztcbiAgfVxuXG4gIHByaXZhdGUgYWRkRXNzZW50aWFsU2V0dGluZ3MoY29udGFpbmVyRWw6IEhUTUxFbGVtZW50KTogdm9pZCB7XG4gICAgY29uc3Qgc2VjdGlvbiA9IGNvbnRhaW5lckVsLmNyZWF0ZUVsKCdkaXYnLCB7IGNsczogJ3Rob3RoLXNldHRpbmdzLXNlY3Rpb24nIH0pO1xuICAgIHNlY3Rpb24uY3JlYXRlRWwoJ2gyJywgeyB0ZXh0OiAn8J+UkSBFc3NlbnRpYWwgQ29uZmlndXJhdGlvbicgfSk7XG4gICAgc2VjdGlvbi5jcmVhdGVFbCgncCcsIHsgdGV4dDogJ1JlcXVpcmVkIHNldHRpbmdzIHRvIGdldCBzdGFydGVkIHdpdGggVGhvdGgnLCBjbHM6ICd0aG90aC1zZWN0aW9uLWRlc2MnIH0pO1xuXG4gICAgLy8gQVBJIEtleXMgU3Vic2VjdGlvblxuICAgIGNvbnN0IGFwaVNlY3Rpb24gPSBzZWN0aW9uLmNyZWF0ZUVsKCdkaXYnLCB7IGNsczogJ3Rob3RoLXN1YnNlY3Rpb24nIH0pO1xuICAgIGFwaVNlY3Rpb24uY3JlYXRlRWwoJ2gzJywgeyB0ZXh0OiAnQVBJIEtleXMnIH0pO1xuXG4gICAgbmV3IFNldHRpbmcoYXBpU2VjdGlvbilcbiAgICAgIC5zZXROYW1lKCdNaXN0cmFsIEFQSSBLZXknKVxuICAgICAgLnNldERlc2MoJ1JlcXVpcmVkIGZvciBQREYgcHJvY2Vzc2luZyBhbmQgZG9jdW1lbnQgYW5hbHlzaXMnKVxuICAgICAgLmFkZFRleHQoKHRleHQpID0+IHtcbiAgICAgICAgdGV4dC5pbnB1dEVsLnR5cGUgPSAncGFzc3dvcmQnO1xuICAgICAgICB0ZXh0XG4gICAgICAgICAgLnNldFBsYWNlaG9sZGVyKCdFbnRlciB5b3VyIE1pc3RyYWwgQVBJIGtleScpXG4gICAgICAgICAgLnNldFZhbHVlKHRoaXMucGx1Z2luLnNldHRpbmdzLm1pc3RyYWxLZXkpXG4gICAgICAgICAgLm9uQ2hhbmdlKGFzeW5jICh2YWx1ZSkgPT4ge1xuICAgICAgICAgICAgdGhpcy5wbHVnaW4uc2V0dGluZ3MubWlzdHJhbEtleSA9IHZhbHVlO1xuICAgICAgICAgICAgYXdhaXQgdGhpcy5wbHVnaW4uc2F2ZVNldHRpbmdzKCk7XG4gICAgICAgICAgfSk7XG4gICAgICB9KVxuICAgICAgLmFkZEV4dHJhQnV0dG9uKChidXR0b24pID0+IHtcbiAgICAgICAgYnV0dG9uXG4gICAgICAgICAgLnNldEljb24oJ2V4dGVybmFsLWxpbmsnKVxuICAgICAgICAgIC5zZXRUb29sdGlwKCdHZXQgTWlzdHJhbCBBUEkgS2V5JylcbiAgICAgICAgICAub25DbGljaygoKSA9PiB3aW5kb3cub3BlbignaHR0cHM6Ly9jb25zb2xlLm1pc3RyYWwuYWknLCAnX2JsYW5rJykpO1xuICAgICAgfSk7XG5cbiAgICBuZXcgU2V0dGluZyhhcGlTZWN0aW9uKVxuICAgICAgLnNldE5hbWUoJ09wZW5Sb3V0ZXIgQVBJIEtleScpXG4gICAgICAuc2V0RGVzYygnUmVxdWlyZWQgZm9yIEFJIHJlc2VhcmNoIGNhcGFiaWxpdGllcyBhbmQgbGFuZ3VhZ2UgbW9kZWxzJylcbiAgICAgIC5hZGRUZXh0KCh0ZXh0KSA9PiB7XG4gICAgICAgIHRleHQuaW5wdXRFbC50eXBlID0gJ3Bhc3N3b3JkJztcbiAgICAgICAgdGV4dFxuICAgICAgICAgIC5zZXRQbGFjZWhvbGRlcignRW50ZXIgeW91ciBPcGVuUm91dGVyIEFQSSBrZXknKVxuICAgICAgICAgIC5zZXRWYWx1ZSh0aGlzLnBsdWdpbi5zZXR0aW5ncy5vcGVucm91dGVyS2V5KVxuICAgICAgICAgIC5vbkNoYW5nZShhc3luYyAodmFsdWUpID0+IHtcbiAgICAgICAgICAgIHRoaXMucGx1Z2luLnNldHRpbmdzLm9wZW5yb3V0ZXJLZXkgPSB2YWx1ZTtcbiAgICAgICAgICAgIGF3YWl0IHRoaXMucGx1Z2luLnNhdmVTZXR0aW5ncygpO1xuICAgICAgICAgIH0pO1xuICAgICAgfSlcbiAgICAgIC5hZGRFeHRyYUJ1dHRvbigoYnV0dG9uKSA9PiB7XG4gICAgICAgIGJ1dHRvblxuICAgICAgICAgIC5zZXRJY29uKCdleHRlcm5hbC1saW5rJylcbiAgICAgICAgICAuc2V0VG9vbHRpcCgnR2V0IE9wZW5Sb3V0ZXIgQVBJIEtleScpXG4gICAgICAgICAgLm9uQ2xpY2soKCkgPT4gd2luZG93Lm9wZW4oJ2h0dHBzOi8vb3BlbnJvdXRlci5haScsICdfYmxhbmsnKSk7XG4gICAgICB9KTtcblxuICAgIC8vIE9wdGlvbmFsIEFQSSBLZXlzXG4gICAgY29uc3Qgb3B0aW9uYWxBcGlTZWN0aW9uID0gYXBpU2VjdGlvbi5jcmVhdGVFbCgnZGV0YWlscycsIHsgY2xzOiAndGhvdGgtb3B0aW9uYWwtc2VjdGlvbicgfSk7XG4gICAgb3B0aW9uYWxBcGlTZWN0aW9uLmNyZWF0ZUVsKCdzdW1tYXJ5JywgeyB0ZXh0OiAnT3B0aW9uYWwgQVBJIEtleXMnIH0pO1xuXG4gICAgbmV3IFNldHRpbmcob3B0aW9uYWxBcGlTZWN0aW9uKVxuICAgICAgLnNldE5hbWUoJ0dvb2dsZSBBUEkgS2V5JylcbiAgICAgIC5zZXREZXNjKCdGb3IgR29vZ2xlIFNjaG9sYXIgYW5kIHNlYXJjaCBpbnRlZ3JhdGlvbicpXG4gICAgICAuYWRkVGV4dCgodGV4dCkgPT4ge1xuICAgICAgICB0ZXh0LmlucHV0RWwudHlwZSA9ICdwYXNzd29yZCc7XG4gICAgICAgIHRleHRcbiAgICAgICAgICAuc2V0UGxhY2Vob2xkZXIoJ0VudGVyIHlvdXIgR29vZ2xlIEFQSSBrZXknKVxuICAgICAgICAgIC5zZXRWYWx1ZSh0aGlzLnBsdWdpbi5zZXR0aW5ncy5nb29nbGVBcGlLZXkpXG4gICAgICAgICAgLm9uQ2hhbmdlKGFzeW5jICh2YWx1ZSkgPT4ge1xuICAgICAgICAgICAgdGhpcy5wbHVnaW4uc2V0dGluZ3MuZ29vZ2xlQXBpS2V5ID0gdmFsdWU7XG4gICAgICAgICAgICBhd2FpdCB0aGlzLnBsdWdpbi5zYXZlU2V0dGluZ3MoKTtcbiAgICAgICAgICB9KTtcbiAgICAgIH0pO1xuXG4gICAgbmV3IFNldHRpbmcob3B0aW9uYWxBcGlTZWN0aW9uKVxuICAgICAgLnNldE5hbWUoJ1NlbWFudGljIFNjaG9sYXIgQVBJIEtleScpXG4gICAgICAuc2V0RGVzYygnRm9yIGVuaGFuY2VkIGFjYWRlbWljIHBhcGVyIGRpc2NvdmVyeScpXG4gICAgICAuYWRkVGV4dCgodGV4dCkgPT4ge1xuICAgICAgICB0ZXh0LmlucHV0RWwudHlwZSA9ICdwYXNzd29yZCc7XG4gICAgICAgIHRleHRcbiAgICAgICAgICAuc2V0UGxhY2Vob2xkZXIoJ0VudGVyIHlvdXIgU2VtYW50aWMgU2Nob2xhciBBUEkga2V5JylcbiAgICAgICAgICAuc2V0VmFsdWUodGhpcy5wbHVnaW4uc2V0dGluZ3Muc2VtYW50aWNTY2hvbGFyS2V5KVxuICAgICAgICAgIC5vbkNoYW5nZShhc3luYyAodmFsdWUpID0+IHtcbiAgICAgICAgICAgIHRoaXMucGx1Z2luLnNldHRpbmdzLnNlbWFudGljU2Nob2xhcktleSA9IHZhbHVlO1xuICAgICAgICAgICAgYXdhaXQgdGhpcy5wbHVnaW4uc2F2ZVNldHRpbmdzKCk7XG4gICAgICAgICAgfSk7XG4gICAgICB9KTtcblxuICAgIC8vIERpcmVjdG9yeSBTZXR0aW5nc1xuICAgIGNvbnN0IGRpclNlY3Rpb24gPSBzZWN0aW9uLmNyZWF0ZUVsKCdkaXYnLCB7IGNsczogJ3Rob3RoLXN1YnNlY3Rpb24nIH0pO1xuICAgIGRpclNlY3Rpb24uY3JlYXRlRWwoJ2gzJywgeyB0ZXh0OiAnRGlyZWN0b3J5IENvbmZpZ3VyYXRpb24nIH0pO1xuXG4gICAgbmV3IFNldHRpbmcoZGlyU2VjdGlvbilcbiAgICAgIC5zZXROYW1lKCdXb3Jrc3BhY2UgRGlyZWN0b3J5JylcbiAgICAgIC5zZXREZXNjKCdQYXRoIHRvIHlvdXIgVGhvdGggd29ya3NwYWNlICh3aGVyZSB5b3UgY2xvbmVkIHByb2plY3QtdGhvdGgpJylcbiAgICAgIC5hZGRUZXh0KCh0ZXh0KSA9PlxuICAgICAgICB0ZXh0XG4gICAgICAgICAgLnNldFBsYWNlaG9sZGVyKCdlLmcuLCAvaG9tZS91c2VyL3Byb2plY3QtdGhvdGgnKVxuICAgICAgICAgIC5zZXRWYWx1ZSh0aGlzLnBsdWdpbi5zZXR0aW5ncy53b3Jrc3BhY2VEaXJlY3RvcnkpXG4gICAgICAgICAgLm9uQ2hhbmdlKGFzeW5jICh2YWx1ZSkgPT4ge1xuICAgICAgICAgICAgdGhpcy5wbHVnaW4uc2V0dGluZ3Mud29ya3NwYWNlRGlyZWN0b3J5ID0gdmFsdWU7XG4gICAgICAgICAgICAvLyBBdXRvLXBvcHVsYXRlIG90aGVyIGRpcmVjdG9yaWVzXG4gICAgICAgICAgICBpZiAodmFsdWUpIHtcbiAgICAgICAgICAgICAgdGhpcy5wbHVnaW4uc2V0dGluZ3MuZGF0YURpcmVjdG9yeSA9IGAke3ZhbHVlfS9kYXRhYDtcbiAgICAgICAgICAgICAgdGhpcy5wbHVnaW4uc2V0dGluZ3Mua25vd2xlZGdlRGlyZWN0b3J5ID0gYCR7dmFsdWV9L2tub3dsZWRnZWA7XG4gICAgICAgICAgICAgIHRoaXMucGx1Z2luLnNldHRpbmdzLmxvZ3NEaXJlY3RvcnkgPSBgJHt2YWx1ZX0vbG9nc2A7XG4gICAgICAgICAgICAgIHRoaXMucGx1Z2luLnNldHRpbmdzLnF1ZXJpZXNEaXJlY3RvcnkgPSBgJHt2YWx1ZX0vcGxhbm5pbmcvcXVlcmllc2A7XG4gICAgICAgICAgICAgIHRoaXMucGx1Z2luLnNldHRpbmdzLmFnZW50U3RvcmFnZURpcmVjdG9yeSA9IGAke3ZhbHVlfS9rbm93bGVkZ2UvYWdlbnRgO1xuICAgICAgICAgICAgICB0aGlzLnBsdWdpbi5zZXR0aW5ncy5wZGZEaXJlY3RvcnkgPSBgJHt2YWx1ZX0vZGF0YS9wZGZgO1xuICAgICAgICAgICAgICB0aGlzLnBsdWdpbi5zZXR0aW5ncy5wcm9tcHRzRGlyZWN0b3J5ID0gYCR7dmFsdWV9L3RlbXBsYXRlcy9wcm9tcHRzYDtcbiAgICAgICAgICAgIH1cbiAgICAgICAgICAgIGF3YWl0IHRoaXMucGx1Z2luLnNhdmVTZXR0aW5ncygpO1xuICAgICAgICAgIH0pXG4gICAgICApO1xuXG4gICAgbmV3IFNldHRpbmcoZGlyU2VjdGlvbilcbiAgICAgIC5zZXROYW1lKCdPYnNpZGlhbiBOb3RlcyBEaXJlY3RvcnknKVxuICAgICAgLnNldERlc2MoJ0RpcmVjdG9yeSBpbiB5b3VyIHZhdWx0IHdoZXJlIFRob3RoIHdpbGwgc3RvcmUgcmVzZWFyY2ggbm90ZXMnKVxuICAgICAgLmFkZFRleHQoKHRleHQpID0+XG4gICAgICAgIHRleHRcbiAgICAgICAgICAuc2V0UGxhY2Vob2xkZXIoJ2UuZy4sIFJlc2VhcmNoL1Rob3RoJylcbiAgICAgICAgICAuc2V0VmFsdWUodGhpcy5wbHVnaW4uc2V0dGluZ3Mub2JzaWRpYW5EaXJlY3RvcnkpXG4gICAgICAgICAgLm9uQ2hhbmdlKGFzeW5jICh2YWx1ZSkgPT4ge1xuICAgICAgICAgICAgdGhpcy5wbHVnaW4uc2V0dGluZ3Mub2JzaWRpYW5EaXJlY3RvcnkgPSB2YWx1ZTtcbiAgICAgICAgICAgIGF3YWl0IHRoaXMucGx1Z2luLnNhdmVTZXR0aW5ncygpO1xuICAgICAgICAgIH0pXG4gICAgICApO1xuXG4gICAgbmV3IFNldHRpbmcoZGlyU2VjdGlvbilcbiAgICAgIC5zZXROYW1lKCdQcm9tcHRzIERpcmVjdG9yeScpXG4gICAgICAuc2V0RGVzYygnRm9sZGVyIHdpdGggY3VzdG9tIHByb21wdHMgKGxlYXZlIGJsYW5rIGZvciBkZWZhdWx0cyknKVxuICAgICAgLmFkZFRleHQoKHRleHQpID0+XG4gICAgICAgIHRleHRcbiAgICAgICAgICAuc2V0UGxhY2Vob2xkZXIoJ2UuZy4sIC9wYXRoL3RvL3Byb21wdHMnKVxuICAgICAgICAgIC5zZXRWYWx1ZSh0aGlzLnBsdWdpbi5zZXR0aW5ncy5wcm9tcHRzRGlyZWN0b3J5KVxuICAgICAgICAgIC5vbkNoYW5nZShhc3luYyAodmFsdWUpID0+IHtcbiAgICAgICAgICAgIHRoaXMucGx1Z2luLnNldHRpbmdzLnByb21wdHNEaXJlY3RvcnkgPSB2YWx1ZTtcbiAgICAgICAgICAgIGF3YWl0IHRoaXMucGx1Z2luLnNhdmVTZXR0aW5ncygpO1xuICAgICAgICAgIH0pXG4gICAgICApO1xuICB9XG5cbiAgcHJpdmF0ZSBhZGRDb25uZWN0aW9uU2V0dGluZ3MoY29udGFpbmVyRWw6IEhUTUxFbGVtZW50KTogdm9pZCB7XG4gICAgY29uc3Qgc2VjdGlvbiA9IGNvbnRhaW5lckVsLmNyZWF0ZUVsKCdkaXYnLCB7IGNsczogJ3Rob3RoLXNldHRpbmdzLXNlY3Rpb24nIH0pO1xuICAgIHNlY3Rpb24uY3JlYXRlRWwoJ2gyJywgeyB0ZXh0OiAn8J+MkCBDb25uZWN0aW9uIFNldHRpbmdzJyB9KTtcbiAgICBzZWN0aW9uLmNyZWF0ZUVsKCdwJywgeyB0ZXh0OiAnQ29uZmlndXJlIGhvdyBPYnNpZGlhbiBjb25uZWN0cyB0byB0aGUgVGhvdGggYWdlbnQnLCBjbHM6ICd0aG90aC1zZWN0aW9uLWRlc2MnIH0pO1xuXG4gICAgbmV3IFNldHRpbmcoc2VjdGlvbilcbiAgICAgIC5zZXROYW1lKCdSZW1vdGUgTW9kZScpXG4gICAgICAuc2V0RGVzYygnQ29ubmVjdCB0byBhIHJlbW90ZSBUaG90aCBzZXJ2ZXIgKFdTTCwgRG9ja2VyLCBvciByZW1vdGUgbWFjaGluZSknKVxuICAgICAgLmFkZFRvZ2dsZSgodG9nZ2xlKSA9PlxuICAgICAgICB0b2dnbGVcbiAgICAgICAgICAuc2V0VmFsdWUodGhpcy5wbHVnaW4uc2V0dGluZ3MucmVtb3RlTW9kZSlcbiAgICAgICAgICAub25DaGFuZ2UoYXN5bmMgKHZhbHVlKSA9PiB7XG4gICAgICAgICAgICB0aGlzLnBsdWdpbi5zZXR0aW5ncy5yZW1vdGVNb2RlID0gdmFsdWU7XG4gICAgICAgICAgICBhd2FpdCB0aGlzLnBsdWdpbi5zYXZlU2V0dGluZ3MoKTtcbiAgICAgICAgICAgIHRoaXMuZGlzcGxheSgpO1xuICAgICAgICAgIH0pXG4gICAgICApO1xuXG4gICAgaWYgKHRoaXMucGx1Z2luLnNldHRpbmdzLnJlbW90ZU1vZGUpIHtcbiAgICAgIG5ldyBTZXR0aW5nKHNlY3Rpb24pXG4gICAgICAgIC5zZXROYW1lKCdSZW1vdGUgRW5kcG9pbnQgVVJMJylcbiAgICAgICAgLnNldERlc2MoJ0Z1bGwgVVJMIG9mIHRoZSByZW1vdGUgVGhvdGggc2VydmVyJylcbiAgICAgICAgLmFkZFRleHQoKHRleHQpID0+XG4gICAgICAgICAgdGV4dFxuICAgICAgICAgICAgLnNldFBsYWNlaG9sZGVyKCdodHRwOi8vbG9jYWxob3N0OjgwMDAnKVxuICAgICAgICAgICAgLnNldFZhbHVlKHRoaXMucGx1Z2luLnNldHRpbmdzLnJlbW90ZUVuZHBvaW50VXJsKVxuICAgICAgICAgICAgLm9uQ2hhbmdlKGFzeW5jICh2YWx1ZSkgPT4ge1xuICAgICAgICAgICAgICB0aGlzLnBsdWdpbi5zZXR0aW5ncy5yZW1vdGVFbmRwb2ludFVybCA9IHZhbHVlO1xuICAgICAgICAgICAgICBhd2FpdCB0aGlzLnBsdWdpbi5zYXZlU2V0dGluZ3MoKTtcbiAgICAgICAgICAgIH0pXG4gICAgICAgICk7XG5cbiAgICAgIC8vIFF1aWNrIGNvbm5lY3Rpb24gdGVzdCBmb3IgcmVtb3RlIG1vZGVcbiAgICAgIGNvbnN0IHRlc3RDb250YWluZXIgPSBzZWN0aW9uLmNyZWF0ZUVsKCdkaXYnLCB7IGNsczogJ3Rob3RoLXRlc3QtY29udGFpbmVyJyB9KTtcbiAgICAgIGNvbnN0IHRlc3RCdXR0b24gPSB0ZXN0Q29udGFpbmVyLmNyZWF0ZUVsKCdidXR0b24nLCB7XG4gICAgICAgIHRleHQ6ICdUZXN0IFJlbW90ZSBDb25uZWN0aW9uJyxcbiAgICAgICAgY2xzOiAndGhvdGgtdGVzdC1idXR0b24nXG4gICAgICB9KTtcbiAgICAgIGNvbnN0IHRlc3RSZXN1bHQgPSB0ZXN0Q29udGFpbmVyLmNyZWF0ZUVsKCdzcGFuJywgeyBjbHM6ICd0aG90aC10ZXN0LXJlc3VsdCcgfSk7XG5cbiAgICAgIHRlc3RCdXR0b24ub25jbGljayA9IGFzeW5jICgpID0+IHtcbiAgICAgICAgdGVzdEJ1dHRvbi5kaXNhYmxlZCA9IHRydWU7XG4gICAgICAgIHRlc3RCdXR0b24udGV4dENvbnRlbnQgPSAnVGVzdGluZy4uLic7XG4gICAgICAgIHRlc3RSZXN1bHQudGV4dENvbnRlbnQgPSAnJztcblxuICAgICAgICB0cnkge1xuICAgICAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZmV0Y2goYCR7dGhpcy5wbHVnaW4uc2V0dGluZ3MucmVtb3RlRW5kcG9pbnRVcmx9L2hlYWx0aGApO1xuICAgICAgICAgIGlmIChyZXNwb25zZS5vaykge1xuICAgICAgICAgICAgdGVzdFJlc3VsdC50ZXh0Q29udGVudCA9ICfinIUgQ29ubmVjdGlvbiBzdWNjZXNzZnVsJztcbiAgICAgICAgICAgIHRlc3RSZXN1bHQuY2xhc3NOYW1lID0gJ3Rob3RoLXRlc3QtcmVzdWx0IHRob3RoLXRlc3Qtc3VjY2Vzcyc7XG4gICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIHRlc3RSZXN1bHQudGV4dENvbnRlbnQgPSBg4p2MIFNlcnZlciBlcnJvcjogJHtyZXNwb25zZS5zdGF0dXN9YDtcbiAgICAgICAgICAgIHRlc3RSZXN1bHQuY2xhc3NOYW1lID0gJ3Rob3RoLXRlc3QtcmVzdWx0IHRob3RoLXRlc3QtZXJyb3InO1xuICAgICAgICAgIH1cbiAgICAgICAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICAgICAgICB0ZXN0UmVzdWx0LnRleHRDb250ZW50ID0gYOKdjCBDb25uZWN0aW9uIGZhaWxlZDogJHtlcnJvci5tZXNzYWdlfWA7XG4gICAgICAgICAgdGVzdFJlc3VsdC5jbGFzc05hbWUgPSAndGhvdGgtdGVzdC1yZXN1bHQgdGhvdGgtdGVzdC1lcnJvcic7XG4gICAgICAgIH0gZmluYWxseSB7XG4gICAgICAgICAgdGVzdEJ1dHRvbi5kaXNhYmxlZCA9IGZhbHNlO1xuICAgICAgICAgIHRlc3RCdXR0b24udGV4dENvbnRlbnQgPSAnVGVzdCBSZW1vdGUgQ29ubmVjdGlvbic7XG4gICAgICAgIH1cbiAgICAgIH07XG4gICAgfSBlbHNlIHtcbiAgICAgIG5ldyBTZXR0aW5nKHNlY3Rpb24pXG4gICAgICAgIC5zZXROYW1lKCdMb2NhbCBIb3N0JylcbiAgICAgICAgLnNldERlc2MoJ0hvc3QgYWRkcmVzcyBmb3IgbG9jYWwgVGhvdGggc2VydmVyJylcbiAgICAgICAgLmFkZFRleHQoKHRleHQpID0+XG4gICAgICAgICAgdGV4dFxuICAgICAgICAgICAgLnNldFBsYWNlaG9sZGVyKCcxMjcuMC4wLjEnKVxuICAgICAgICAgICAgLnNldFZhbHVlKHRoaXMucGx1Z2luLnNldHRpbmdzLmVuZHBvaW50SG9zdClcbiAgICAgICAgICAgIC5vbkNoYW5nZShhc3luYyAodmFsdWUpID0+IHtcbiAgICAgICAgICAgICAgdGhpcy5wbHVnaW4uc2V0dGluZ3MuZW5kcG9pbnRIb3N0ID0gdmFsdWU7XG4gICAgICAgICAgICAgIHRoaXMucGx1Z2luLnNldHRpbmdzLmVuZHBvaW50QmFzZVVybCA9IGBodHRwOi8vJHt2YWx1ZX06JHt0aGlzLnBsdWdpbi5zZXR0aW5ncy5lbmRwb2ludFBvcnR9YDtcbiAgICAgICAgICAgICAgYXdhaXQgdGhpcy5wbHVnaW4uc2F2ZVNldHRpbmdzKCk7XG4gICAgICAgICAgICB9KVxuICAgICAgICApO1xuXG4gICAgICBuZXcgU2V0dGluZyhzZWN0aW9uKVxuICAgICAgICAuc2V0TmFtZSgnTG9jYWwgUG9ydCcpXG4gICAgICAgIC5zZXREZXNjKCdQb3J0IGZvciBsb2NhbCBUaG90aCBzZXJ2ZXInKVxuICAgICAgICAuYWRkU2xpZGVyKChzbGlkZXIpID0+XG4gICAgICAgICAgc2xpZGVyXG4gICAgICAgICAgICAuc2V0TGltaXRzKDMwMDAsIDk5OTksIDEpXG4gICAgICAgICAgICAuc2V0VmFsdWUodGhpcy5wbHVnaW4uc2V0dGluZ3MuZW5kcG9pbnRQb3J0KVxuICAgICAgICAgICAgLnNldER5bmFtaWNUb29sdGlwKClcbiAgICAgICAgICAgIC5vbkNoYW5nZShhc3luYyAodmFsdWUpID0+IHtcbiAgICAgICAgICAgICAgdGhpcy5wbHVnaW4uc2V0dGluZ3MuZW5kcG9pbnRQb3J0ID0gdmFsdWU7XG4gICAgICAgICAgICAgIHRoaXMucGx1Z2luLnNldHRpbmdzLmVuZHBvaW50QmFzZVVybCA9IGBodHRwOi8vJHt0aGlzLnBsdWdpbi5zZXR0aW5ncy5lbmRwb2ludEhvc3R9OiR7dmFsdWV9YDtcbiAgICAgICAgICAgICAgYXdhaXQgdGhpcy5wbHVnaW4uc2F2ZVNldHRpbmdzKCk7XG4gICAgICAgICAgICB9KVxuICAgICAgICApO1xuICAgIH1cbiAgfVxuXG4gIHByaXZhdGUgYWRkQWR2YW5jZWRTZXR0aW5ncyhjb250YWluZXJFbDogSFRNTEVsZW1lbnQpOiB2b2lkIHtcbiAgICBjb25zdCBzZWN0aW9uID0gY29udGFpbmVyRWwuY3JlYXRlRWwoJ2RpdicsIHsgY2xzOiAndGhvdGgtc2V0dGluZ3Mtc2VjdGlvbiB0aG90aC1hZHZhbmNlZC1zZWN0aW9uJyB9KTtcbiAgICBzZWN0aW9uLmNyZWF0ZUVsKCdoMicsIHsgdGV4dDogJ+Kame+4jyBBZHZhbmNlZCBDb25maWd1cmF0aW9uJyB9KTtcblxuICAgIC8vIExMTSBDb25maWd1cmF0aW9uXG4gICAgdGhpcy5hZGRMTE1TZXR0aW5ncyhzZWN0aW9uKTtcblxuICAgIC8vIEFnZW50IEJlaGF2aW9yXG4gICAgdGhpcy5hZGRBZ2VudEJlaGF2aW9yU2V0dGluZ3Moc2VjdGlvbik7XG5cbiAgICAvLyBEaXNjb3ZlcnkgU3lzdGVtXG4gICAgdGhpcy5hZGREaXNjb3ZlcnlTZXR0aW5ncyhzZWN0aW9uKTtcblxuICAgIC8vIExvZ2dpbmcgJiBQZXJmb3JtYW5jZVxuICAgIHRoaXMuYWRkTG9nZ2luZ1NldHRpbmdzKHNlY3Rpb24pO1xuXG4gICAgLy8gVUkgUHJlZmVyZW5jZXNcbiAgICB0aGlzLmFkZFVJU2V0dGluZ3Moc2VjdGlvbik7XG4gIH1cblxuICBwcml2YXRlIGFkZExMTVNldHRpbmdzKHBhcmVudEVsOiBIVE1MRWxlbWVudCk6IHZvaWQge1xuICAgIGNvbnN0IHN1YnNlY3Rpb24gPSBwYXJlbnRFbC5jcmVhdGVFbCgnZGV0YWlscycsIHsgY2xzOiAndGhvdGgtc3Vic2VjdGlvbicgfSk7XG4gICAgc3Vic2VjdGlvbi5jcmVhdGVFbCgnc3VtbWFyeScsIHsgdGV4dDogJ/CfpJYgTGFuZ3VhZ2UgTW9kZWwgQ29uZmlndXJhdGlvbicgfSk7XG5cbiAgICBjb25zdCBtb2RlbE9wdGlvbnMgPSBbXG4gICAgICAnYW50aHJvcGljL2NsYXVkZS0zLW9wdXMnLFxuICAgICAgJ2FudGhyb3BpYy9jbGF1ZGUtMy1zb25uZXQnLFxuICAgICAgJ2FudGhyb3BpYy9jbGF1ZGUtMy1oYWlrdScsXG4gICAgICAnb3BlbmFpL2dwdC00JyxcbiAgICAgICdvcGVuYWkvZ3B0LTQtdHVyYm8nLFxuICAgICAgJ29wZW5haS9ncHQtMy41LXR1cmJvJyxcbiAgICAgICdtaXN0cmFsL21pc3RyYWwtbGFyZ2UnLFxuICAgICAgJ21pc3RyYWwvbWlzdHJhbC1tZWRpdW0nXG4gICAgXTtcblxuICAgIG5ldyBTZXR0aW5nKHN1YnNlY3Rpb24pXG4gICAgICAuc2V0TmFtZSgnUHJpbWFyeSBMTE0gTW9kZWwnKVxuICAgICAgLnNldERlc2MoJ01haW4gbGFuZ3VhZ2UgbW9kZWwgZm9yIHJlc2VhcmNoIGFuZCBnZW5lcmFsIHRhc2tzJylcbiAgICAgIC5hZGREcm9wZG93bigoZHJvcGRvd24pID0+IHtcbiAgICAgICAgbW9kZWxPcHRpb25zLmZvckVhY2gobW9kZWwgPT4gZHJvcGRvd24uYWRkT3B0aW9uKG1vZGVsLCBtb2RlbCkpO1xuICAgICAgICBkcm9wZG93blxuICAgICAgICAgIC5zZXRWYWx1ZSh0aGlzLnBsdWdpbi5zZXR0aW5ncy5wcmltYXJ5TGxtTW9kZWwpXG4gICAgICAgICAgLm9uQ2hhbmdlKGFzeW5jICh2YWx1ZSkgPT4ge1xuICAgICAgICAgICAgdGhpcy5wbHVnaW4uc2V0dGluZ3MucHJpbWFyeUxsbU1vZGVsID0gdmFsdWU7XG4gICAgICAgICAgICBhd2FpdCB0aGlzLnBsdWdpbi5zYXZlU2V0dGluZ3MoKTtcbiAgICAgICAgICB9KTtcbiAgICAgIH0pO1xuXG4gICAgbmV3IFNldHRpbmcoc3Vic2VjdGlvbilcbiAgICAgIC5zZXROYW1lKCdBbmFseXNpcyBMTE0gTW9kZWwnKVxuICAgICAgLnNldERlc2MoJ1NwZWNpYWxpemVkIG1vZGVsIGZvciBkb2N1bWVudCBhbmFseXNpcyBhbmQgUERGIHByb2Nlc3NpbmcnKVxuICAgICAgLmFkZERyb3Bkb3duKChkcm9wZG93bikgPT4ge1xuICAgICAgICBtb2RlbE9wdGlvbnMuZm9yRWFjaChtb2RlbCA9PiBkcm9wZG93bi5hZGRPcHRpb24obW9kZWwsIG1vZGVsKSk7XG4gICAgICAgIGRyb3Bkb3duXG4gICAgICAgICAgLnNldFZhbHVlKHRoaXMucGx1Z2luLnNldHRpbmdzLmFuYWx5c2lzTGxtTW9kZWwpXG4gICAgICAgICAgLm9uQ2hhbmdlKGFzeW5jICh2YWx1ZSkgPT4ge1xuICAgICAgICAgICAgdGhpcy5wbHVnaW4uc2V0dGluZ3MuYW5hbHlzaXNMbG1Nb2RlbCA9IHZhbHVlO1xuICAgICAgICAgICAgYXdhaXQgdGhpcy5wbHVnaW4uc2F2ZVNldHRpbmdzKCk7XG4gICAgICAgICAgfSk7XG4gICAgICB9KTtcblxuICAgIG5ldyBTZXR0aW5nKHN1YnNlY3Rpb24pXG4gICAgICAuc2V0TmFtZSgnTExNIFRlbXBlcmF0dXJlJylcbiAgICAgIC5zZXREZXNjKCdDcmVhdGl2aXR5IGxldmVsIGZvciByZXNwb25zZXMgKDAuMCA9IGZvY3VzZWQsIDEuMCA9IGNyZWF0aXZlKScpXG4gICAgICAuYWRkU2xpZGVyKChzbGlkZXIpID0+XG4gICAgICAgIHNsaWRlclxuICAgICAgICAgIC5zZXRMaW1pdHMoMCwgMSwgMC4xKVxuICAgICAgICAgIC5zZXRWYWx1ZSh0aGlzLnBsdWdpbi5zZXR0aW5ncy5sbG1UZW1wZXJhdHVyZSlcbiAgICAgICAgICAuc2V0RHluYW1pY1Rvb2x0aXAoKVxuICAgICAgICAgIC5vbkNoYW5nZShhc3luYyAodmFsdWUpID0+IHtcbiAgICAgICAgICAgIHRoaXMucGx1Z2luLnNldHRpbmdzLmxsbVRlbXBlcmF0dXJlID0gdmFsdWU7XG4gICAgICAgICAgICBhd2FpdCB0aGlzLnBsdWdpbi5zYXZlU2V0dGluZ3MoKTtcbiAgICAgICAgICB9KVxuICAgICAgKTtcblxuICAgIG5ldyBTZXR0aW5nKHN1YnNlY3Rpb24pXG4gICAgICAuc2V0TmFtZSgnTWF4IE91dHB1dCBUb2tlbnMnKVxuICAgICAgLnNldERlc2MoJ01heGltdW0gcmVzcG9uc2UgbGVuZ3RoJylcbiAgICAgIC5hZGRTbGlkZXIoKHNsaWRlcikgPT5cbiAgICAgICAgc2xpZGVyXG4gICAgICAgICAgLnNldExpbWl0cygxMDI0LCA4MTkyLCAyNTYpXG4gICAgICAgICAgLnNldFZhbHVlKHRoaXMucGx1Z2luLnNldHRpbmdzLmxsbU1heE91dHB1dFRva2VucylcbiAgICAgICAgICAuc2V0RHluYW1pY1Rvb2x0aXAoKVxuICAgICAgICAgIC5vbkNoYW5nZShhc3luYyAodmFsdWUpID0+IHtcbiAgICAgICAgICAgIHRoaXMucGx1Z2luLnNldHRpbmdzLmxsbU1heE91dHB1dFRva2VucyA9IHZhbHVlO1xuICAgICAgICAgICAgYXdhaXQgdGhpcy5wbHVnaW4uc2F2ZVNldHRpbmdzKCk7XG4gICAgICAgICAgfSlcbiAgICAgICk7XG4gIH1cblxuICBwcml2YXRlIGFkZEFnZW50QmVoYXZpb3JTZXR0aW5ncyhwYXJlbnRFbDogSFRNTEVsZW1lbnQpOiB2b2lkIHtcbiAgICBjb25zdCBzdWJzZWN0aW9uID0gcGFyZW50RWwuY3JlYXRlRWwoJ2RldGFpbHMnLCB7IGNsczogJ3Rob3RoLXN1YnNlY3Rpb24nIH0pO1xuICAgIHN1YnNlY3Rpb24uY3JlYXRlRWwoJ3N1bW1hcnknLCB7IHRleHQ6ICfwn6egIEFnZW50IEJlaGF2aW9yJyB9KTtcblxuICAgIG5ldyBTZXR0aW5nKHN1YnNlY3Rpb24pXG4gICAgICAuc2V0TmFtZSgnQXV0by1zdGFydCBSZXNlYXJjaCBBZ2VudCcpXG4gICAgICAuc2V0RGVzYygnQXV0b21hdGljYWxseSBzdGFydCB0aGUgcmVzZWFyY2ggYWdlbnQgd2hlbiB0aGUgc2VydmVyIHN0YXJ0cycpXG4gICAgICAuYWRkVG9nZ2xlKCh0b2dnbGUpID0+XG4gICAgICAgIHRvZ2dsZVxuICAgICAgICAgIC5zZXRWYWx1ZSh0aGlzLnBsdWdpbi5zZXR0aW5ncy5yZXNlYXJjaEFnZW50QXV0b1N0YXJ0KVxuICAgICAgICAgIC5vbkNoYW5nZShhc3luYyAodmFsdWUpID0+IHtcbiAgICAgICAgICAgIHRoaXMucGx1Z2luLnNldHRpbmdzLnJlc2VhcmNoQWdlbnRBdXRvU3RhcnQgPSB2YWx1ZTtcbiAgICAgICAgICAgIGF3YWl0IHRoaXMucGx1Z2luLnNhdmVTZXR0aW5ncygpO1xuICAgICAgICAgIH0pXG4gICAgICApO1xuXG4gICAgbmV3IFNldHRpbmcoc3Vic2VjdGlvbilcbiAgICAgIC5zZXROYW1lKCdFbmFibGUgQWdlbnQgTWVtb3J5JylcbiAgICAgIC5zZXREZXNjKCdBbGxvdyB0aGUgYWdlbnQgdG8gcmVtZW1iZXIgcHJldmlvdXMgY29udmVyc2F0aW9ucycpXG4gICAgICAuYWRkVG9nZ2xlKCh0b2dnbGUpID0+XG4gICAgICAgIHRvZ2dsZVxuICAgICAgICAgIC5zZXRWYWx1ZSh0aGlzLnBsdWdpbi5zZXR0aW5ncy5yZXNlYXJjaEFnZW50TWVtb3J5RW5hYmxlZClcbiAgICAgICAgICAub25DaGFuZ2UoYXN5bmMgKHZhbHVlKSA9PiB7XG4gICAgICAgICAgICB0aGlzLnBsdWdpbi5zZXR0aW5ncy5yZXNlYXJjaEFnZW50TWVtb3J5RW5hYmxlZCA9IHZhbHVlO1xuICAgICAgICAgICAgYXdhaXQgdGhpcy5wbHVnaW4uc2F2ZVNldHRpbmdzKCk7XG4gICAgICAgICAgfSlcbiAgICAgICk7XG5cbiAgICBuZXcgU2V0dGluZyhzdWJzZWN0aW9uKVxuICAgICAgLnNldE5hbWUoJ01heCBUb29sIENhbGxzJylcbiAgICAgIC5zZXREZXNjKCdNYXhpbXVtIG51bWJlciBvZiB0b29scyB0aGUgYWdlbnQgY2FuIHVzZSBwZXIgcmVxdWVzdCcpXG4gICAgICAuYWRkU2xpZGVyKChzbGlkZXIpID0+XG4gICAgICAgIHNsaWRlclxuICAgICAgICAgIC5zZXRMaW1pdHMoNSwgNTAsIDUpXG4gICAgICAgICAgLnNldFZhbHVlKHRoaXMucGx1Z2luLnNldHRpbmdzLmFnZW50TWF4VG9vbENhbGxzKVxuICAgICAgICAgIC5zZXREeW5hbWljVG9vbHRpcCgpXG4gICAgICAgICAgLm9uQ2hhbmdlKGFzeW5jICh2YWx1ZSkgPT4ge1xuICAgICAgICAgICAgdGhpcy5wbHVnaW4uc2V0dGluZ3MuYWdlbnRNYXhUb29sQ2FsbHMgPSB2YWx1ZTtcbiAgICAgICAgICAgIGF3YWl0IHRoaXMucGx1Z2luLnNhdmVTZXR0aW5ncygpO1xuICAgICAgICAgIH0pXG4gICAgICApO1xuXG4gICAgbmV3IFNldHRpbmcoc3Vic2VjdGlvbilcbiAgICAgIC5zZXROYW1lKCdBZ2VudCBUaW1lb3V0IChzZWNvbmRzKScpXG4gICAgICAuc2V0RGVzYygnTWF4aW11bSB0aW1lIHRvIHdhaXQgZm9yIGFnZW50IHJlc3BvbnNlcycpXG4gICAgICAuYWRkU2xpZGVyKChzbGlkZXIpID0+XG4gICAgICAgIHNsaWRlclxuICAgICAgICAgIC5zZXRMaW1pdHMoMzAsIDYwMCwgMzApXG4gICAgICAgICAgLnNldFZhbHVlKHRoaXMucGx1Z2luLnNldHRpbmdzLmFnZW50VGltZW91dFNlY29uZHMpXG4gICAgICAgICAgLnNldER5bmFtaWNUb29sdGlwKClcbiAgICAgICAgICAub25DaGFuZ2UoYXN5bmMgKHZhbHVlKSA9PiB7XG4gICAgICAgICAgICB0aGlzLnBsdWdpbi5zZXR0aW5ncy5hZ2VudFRpbWVvdXRTZWNvbmRzID0gdmFsdWU7XG4gICAgICAgICAgICBhd2FpdCB0aGlzLnBsdWdpbi5zYXZlU2V0dGluZ3MoKTtcbiAgICAgICAgICB9KVxuICAgICAgKTtcbiAgfVxuXG4gIHByaXZhdGUgYWRkRGlzY292ZXJ5U2V0dGluZ3MocGFyZW50RWw6IEhUTUxFbGVtZW50KTogdm9pZCB7XG4gICAgY29uc3Qgc3Vic2VjdGlvbiA9IHBhcmVudEVsLmNyZWF0ZUVsKCdkZXRhaWxzJywgeyBjbHM6ICd0aG90aC1zdWJzZWN0aW9uJyB9KTtcbiAgICBzdWJzZWN0aW9uLmNyZWF0ZUVsKCdzdW1tYXJ5JywgeyB0ZXh0OiAn8J+UjSBEaXNjb3ZlcnkgU3lzdGVtJyB9KTtcblxuICAgIG5ldyBTZXR0aW5nKHN1YnNlY3Rpb24pXG4gICAgICAuc2V0TmFtZSgnQXV0by1zdGFydCBEaXNjb3ZlcnkgU2NoZWR1bGVyJylcbiAgICAgIC5zZXREZXNjKCdBdXRvbWF0aWNhbGx5IHN0YXJ0IHRoZSBkaXNjb3Zlcnkgc2NoZWR1bGVyIGZvciBmaW5kaW5nIG5ldyByZXNlYXJjaCcpXG4gICAgICAuYWRkVG9nZ2xlKCh0b2dnbGUpID0+XG4gICAgICAgIHRvZ2dsZVxuICAgICAgICAgIC5zZXRWYWx1ZSh0aGlzLnBsdWdpbi5zZXR0aW5ncy5kaXNjb3ZlcnlBdXRvU3RhcnRTY2hlZHVsZXIpXG4gICAgICAgICAgLm9uQ2hhbmdlKGFzeW5jICh2YWx1ZSkgPT4ge1xuICAgICAgICAgICAgdGhpcy5wbHVnaW4uc2V0dGluZ3MuZGlzY292ZXJ5QXV0b1N0YXJ0U2NoZWR1bGVyID0gdmFsdWU7XG4gICAgICAgICAgICBhd2FpdCB0aGlzLnBsdWdpbi5zYXZlU2V0dGluZ3MoKTtcbiAgICAgICAgICB9KVxuICAgICAgKTtcblxuICAgIG5ldyBTZXR0aW5nKHN1YnNlY3Rpb24pXG4gICAgICAuc2V0TmFtZSgnTWF4IEFydGljbGVzIHBlciBEaXNjb3ZlcnknKVxuICAgICAgLnNldERlc2MoJ01heGltdW0gbnVtYmVyIG9mIGFydGljbGVzIHRvIGRpc2NvdmVyIHBlciBzZWFyY2gnKVxuICAgICAgLmFkZFNsaWRlcigoc2xpZGVyKSA9PlxuICAgICAgICBzbGlkZXJcbiAgICAgICAgICAuc2V0TGltaXRzKDEwLCAxMDAsIDEwKVxuICAgICAgICAgIC5zZXRWYWx1ZSh0aGlzLnBsdWdpbi5zZXR0aW5ncy5kaXNjb3ZlcnlEZWZhdWx0TWF4QXJ0aWNsZXMpXG4gICAgICAgICAgLnNldER5bmFtaWNUb29sdGlwKClcbiAgICAgICAgICAub25DaGFuZ2UoYXN5bmMgKHZhbHVlKSA9PiB7XG4gICAgICAgICAgICB0aGlzLnBsdWdpbi5zZXR0aW5ncy5kaXNjb3ZlcnlEZWZhdWx0TWF4QXJ0aWNsZXMgPSB2YWx1ZTtcbiAgICAgICAgICAgIGF3YWl0IHRoaXMucGx1Z2luLnNhdmVTZXR0aW5ncygpO1xuICAgICAgICAgIH0pXG4gICAgICApO1xuXG4gICAgbmV3IFNldHRpbmcoc3Vic2VjdGlvbilcbiAgICAgIC5zZXROYW1lKCdEaXNjb3ZlcnkgSW50ZXJ2YWwgKG1pbnV0ZXMpJylcbiAgICAgIC5zZXREZXNjKCdIb3cgb2Z0ZW4gdG8gcnVuIGF1dG9tYXRpYyBkaXNjb3Zlcnkgc2VhcmNoZXMnKVxuICAgICAgLmFkZFNsaWRlcigoc2xpZGVyKSA9PlxuICAgICAgICBzbGlkZXJcbiAgICAgICAgICAuc2V0TGltaXRzKDE1LCAyNDAsIDE1KVxuICAgICAgICAgIC5zZXRWYWx1ZSh0aGlzLnBsdWdpbi5zZXR0aW5ncy5kaXNjb3ZlcnlEZWZhdWx0SW50ZXJ2YWxNaW51dGVzKVxuICAgICAgICAgIC5zZXREeW5hbWljVG9vbHRpcCgpXG4gICAgICAgICAgLm9uQ2hhbmdlKGFzeW5jICh2YWx1ZSkgPT4ge1xuICAgICAgICAgICAgdGhpcy5wbHVnaW4uc2V0dGluZ3MuZGlzY292ZXJ5RGVmYXVsdEludGVydmFsTWludXRlcyA9IHZhbHVlO1xuICAgICAgICAgICAgYXdhaXQgdGhpcy5wbHVnaW4uc2F2ZVNldHRpbmdzKCk7XG4gICAgICAgICAgfSlcbiAgICAgICk7XG5cbiAgICBuZXcgU2V0dGluZyhzdWJzZWN0aW9uKVxuICAgICAgLnNldE5hbWUoJ0VuYWJsZSBDaHJvbWUgRXh0ZW5zaW9uIEludGVncmF0aW9uJylcbiAgICAgIC5zZXREZXNjKCdBbGxvdyBpbnRlZ3JhdGlvbiB3aXRoIFRob3RoIENocm9tZSBleHRlbnNpb24gZm9yIHdlYiByZXNlYXJjaCcpXG4gICAgICAuYWRkVG9nZ2xlKCh0b2dnbGUpID0+XG4gICAgICAgIHRvZ2dsZVxuICAgICAgICAgIC5zZXRWYWx1ZSh0aGlzLnBsdWdpbi5zZXR0aW5ncy5kaXNjb3ZlcnlDaHJvbWVFeHRlbnNpb25FbmFibGVkKVxuICAgICAgICAgIC5vbkNoYW5nZShhc3luYyAodmFsdWUpID0+IHtcbiAgICAgICAgICAgIHRoaXMucGx1Z2luLnNldHRpbmdzLmRpc2NvdmVyeUNocm9tZUV4dGVuc2lvbkVuYWJsZWQgPSB2YWx1ZTtcbiAgICAgICAgICAgIGF3YWl0IHRoaXMucGx1Z2luLnNhdmVTZXR0aW5ncygpO1xuICAgICAgICAgIH0pXG4gICAgICApO1xuICB9XG5cbiAgcHJpdmF0ZSBhZGRMb2dnaW5nU2V0dGluZ3MocGFyZW50RWw6IEhUTUxFbGVtZW50KTogdm9pZCB7XG4gICAgY29uc3Qgc3Vic2VjdGlvbiA9IHBhcmVudEVsLmNyZWF0ZUVsKCdkZXRhaWxzJywgeyBjbHM6ICd0aG90aC1zdWJzZWN0aW9uJyB9KTtcbiAgICBzdWJzZWN0aW9uLmNyZWF0ZUVsKCdzdW1tYXJ5JywgeyB0ZXh0OiAn8J+TiiBMb2dnaW5nICYgUGVyZm9ybWFuY2UnIH0pO1xuXG4gICAgY29uc3QgbG9nTGV2ZWxzID0gWydERUJVRycsICdJTkZPJywgJ1dBUk5JTkcnLCAnRVJST1InXTtcblxuICAgIG5ldyBTZXR0aW5nKHN1YnNlY3Rpb24pXG4gICAgICAuc2V0TmFtZSgnTG9nIExldmVsJylcbiAgICAgIC5zZXREZXNjKCdNaW5pbXVtIGxldmVsIG9mIG1lc3NhZ2VzIHRvIGxvZycpXG4gICAgICAuYWRkRHJvcGRvd24oKGRyb3Bkb3duKSA9PiB7XG4gICAgICAgIGxvZ0xldmVscy5mb3JFYWNoKGxldmVsID0+IGRyb3Bkb3duLmFkZE9wdGlvbihsZXZlbCwgbGV2ZWwpKTtcbiAgICAgICAgZHJvcGRvd25cbiAgICAgICAgICAuc2V0VmFsdWUodGhpcy5wbHVnaW4uc2V0dGluZ3MubG9nTGV2ZWwpXG4gICAgICAgICAgLm9uQ2hhbmdlKGFzeW5jICh2YWx1ZSkgPT4ge1xuICAgICAgICAgICAgdGhpcy5wbHVnaW4uc2V0dGluZ3MubG9nTGV2ZWwgPSB2YWx1ZTtcbiAgICAgICAgICAgIGF3YWl0IHRoaXMucGx1Z2luLnNhdmVTZXR0aW5ncygpO1xuICAgICAgICAgIH0pO1xuICAgICAgfSk7XG5cbiAgICBuZXcgU2V0dGluZyhzdWJzZWN0aW9uKVxuICAgICAgLnNldE5hbWUoJ0VuYWJsZSBQZXJmb3JtYW5jZSBNb25pdG9yaW5nJylcbiAgICAgIC5zZXREZXNjKCdUcmFjayBwZXJmb3JtYW5jZSBtZXRyaWNzIGFuZCBzeXN0ZW0gaGVhbHRoJylcbiAgICAgIC5hZGRUb2dnbGUoKHRvZ2dsZSkgPT5cbiAgICAgICAgdG9nZ2xlXG4gICAgICAgICAgLnNldFZhbHVlKHRoaXMucGx1Z2luLnNldHRpbmdzLmVuYWJsZVBlcmZvcm1hbmNlTW9uaXRvcmluZylcbiAgICAgICAgICAub25DaGFuZ2UoYXN5bmMgKHZhbHVlKSA9PiB7XG4gICAgICAgICAgICB0aGlzLnBsdWdpbi5zZXR0aW5ncy5lbmFibGVQZXJmb3JtYW5jZU1vbml0b3JpbmcgPSB2YWx1ZTtcbiAgICAgICAgICAgIGF3YWl0IHRoaXMucGx1Z2luLnNhdmVTZXR0aW5ncygpO1xuICAgICAgICAgIH0pXG4gICAgICApO1xuXG4gICAgbmV3IFNldHRpbmcoc3Vic2VjdGlvbilcbiAgICAgIC5zZXROYW1lKCdEZXZlbG9wbWVudCBNb2RlJylcbiAgICAgIC5zZXREZXNjKCdFbmFibGUgYWRkaXRpb25hbCBkZWJ1Z2dpbmcgZmVhdHVyZXMnKVxuICAgICAgLmFkZFRvZ2dsZSgodG9nZ2xlKSA9PlxuICAgICAgICB0b2dnbGVcbiAgICAgICAgICAuc2V0VmFsdWUodGhpcy5wbHVnaW4uc2V0dGluZ3MuZGV2ZWxvcG1lbnRNb2RlKVxuICAgICAgICAgIC5vbkNoYW5nZShhc3luYyAodmFsdWUpID0+IHtcbiAgICAgICAgICAgIHRoaXMucGx1Z2luLnNldHRpbmdzLmRldmVsb3BtZW50TW9kZSA9IHZhbHVlO1xuICAgICAgICAgICAgYXdhaXQgdGhpcy5wbHVnaW4uc2F2ZVNldHRpbmdzKCk7XG4gICAgICAgICAgfSlcbiAgICAgICk7XG4gIH1cblxuICBwcml2YXRlIGFkZFVJU2V0dGluZ3MocGFyZW50RWw6IEhUTUxFbGVtZW50KTogdm9pZCB7XG4gICAgY29uc3Qgc3Vic2VjdGlvbiA9IHBhcmVudEVsLmNyZWF0ZUVsKCdkZXRhaWxzJywgeyBjbHM6ICd0aG90aC1zdWJzZWN0aW9uJyB9KTtcbiAgICBzdWJzZWN0aW9uLmNyZWF0ZUVsKCdzdW1tYXJ5JywgeyB0ZXh0OiAn8J+OqCBVc2VyIEludGVyZmFjZScgfSk7XG5cbiAgICBuZXcgU2V0dGluZyhzdWJzZWN0aW9uKVxuICAgICAgLnNldE5hbWUoJ1Nob3cgU3RhdHVzIEJhcicpXG4gICAgICAuc2V0RGVzYygnRGlzcGxheSBhZ2VudCBzdGF0dXMgaW4gT2JzaWRpYW4gc3RhdHVzIGJhcicpXG4gICAgICAuYWRkVG9nZ2xlKCh0b2dnbGUpID0+XG4gICAgICAgIHRvZ2dsZVxuICAgICAgICAgIC5zZXRWYWx1ZSh0aGlzLnBsdWdpbi5zZXR0aW5ncy5zaG93U3RhdHVzQmFyKVxuICAgICAgICAgIC5vbkNoYW5nZShhc3luYyAodmFsdWUpID0+IHtcbiAgICAgICAgICAgIHRoaXMucGx1Z2luLnNldHRpbmdzLnNob3dTdGF0dXNCYXIgPSB2YWx1ZTtcbiAgICAgICAgICAgIGF3YWl0IHRoaXMucGx1Z2luLnNhdmVTZXR0aW5ncygpO1xuICAgICAgICAgIH0pXG4gICAgICApO1xuXG4gICAgbmV3IFNldHRpbmcoc3Vic2VjdGlvbilcbiAgICAgIC5zZXROYW1lKCdTaG93IFJpYmJvbiBJY29uJylcbiAgICAgIC5zZXREZXNjKCdEaXNwbGF5IGNoYXQgaWNvbiBpbiBsZWZ0IHJpYmJvbicpXG4gICAgICAuYWRkVG9nZ2xlKCh0b2dnbGUpID0+XG4gICAgICAgIHRvZ2dsZVxuICAgICAgICAgIC5zZXRWYWx1ZSh0aGlzLnBsdWdpbi5zZXR0aW5ncy5zaG93UmliYm9uSWNvbilcbiAgICAgICAgICAub25DaGFuZ2UoYXN5bmMgKHZhbHVlKSA9PiB7XG4gICAgICAgICAgICB0aGlzLnBsdWdpbi5zZXR0aW5ncy5zaG93UmliYm9uSWNvbiA9IHZhbHVlO1xuICAgICAgICAgICAgYXdhaXQgdGhpcy5wbHVnaW4uc2F2ZVNldHRpbmdzKCk7XG4gICAgICAgICAgfSlcbiAgICAgICk7XG5cbiAgICBuZXcgU2V0dGluZyhzdWJzZWN0aW9uKVxuICAgICAgLnNldE5hbWUoJ0NvbXBhY3QgTW9kZScpXG4gICAgICAuc2V0RGVzYygnVXNlIHNtYWxsZXIgVUkgZWxlbWVudHMgdG8gc2F2ZSBzcGFjZScpXG4gICAgICAuYWRkVG9nZ2xlKCh0b2dnbGUpID0+XG4gICAgICAgIHRvZ2dsZVxuICAgICAgICAgIC5zZXRWYWx1ZSh0aGlzLnBsdWdpbi5zZXR0aW5ncy5jb21wYWN0TW9kZSlcbiAgICAgICAgICAub25DaGFuZ2UoYXN5bmMgKHZhbHVlKSA9PiB7XG4gICAgICAgICAgICB0aGlzLnBsdWdpbi5zZXR0aW5ncy5jb21wYWN0TW9kZSA9IHZhbHVlO1xuICAgICAgICAgICAgYXdhaXQgdGhpcy5wbHVnaW4uc2F2ZVNldHRpbmdzKCk7XG4gICAgICAgICAgfSlcbiAgICAgICk7XG5cbiAgICBuZXcgU2V0dGluZyhzdWJzZWN0aW9uKVxuICAgICAgLnNldE5hbWUoJ0NoYXQgSGlzdG9yeSBMaW1pdCcpXG4gICAgICAuc2V0RGVzYygnTWF4aW11bSBudW1iZXIgb2YgY2hhdCBtZXNzYWdlcyB0byByZW1lbWJlcicpXG4gICAgICAuYWRkU2xpZGVyKChzbGlkZXIpID0+XG4gICAgICAgIHNsaWRlclxuICAgICAgICAgIC5zZXRMaW1pdHMoMTAsIDEwMCwgMTApXG4gICAgICAgICAgLnNldFZhbHVlKHRoaXMucGx1Z2luLnNldHRpbmdzLmNoYXRIaXN0b3J5TGltaXQpXG4gICAgICAgICAgLnNldER5bmFtaWNUb29sdGlwKClcbiAgICAgICAgICAub25DaGFuZ2UoYXN5bmMgKHZhbHVlKSA9PiB7XG4gICAgICAgICAgICB0aGlzLnBsdWdpbi5zZXR0aW5ncy5jaGF0SGlzdG9yeUxpbWl0ID0gdmFsdWU7XG4gICAgICAgICAgICBhd2FpdCB0aGlzLnBsdWdpbi5zYXZlU2V0dGluZ3MoKTtcbiAgICAgICAgICB9KVxuICAgICAgKTtcblxuICAgIG5ldyBTZXR0aW5nKHN1YnNlY3Rpb24pXG4gICAgICAuc2V0TmFtZSgnRW5hYmxlIE5vdGlmaWNhdGlvbnMnKVxuICAgICAgLnNldERlc2MoJ1Nob3cgbm90aWZpY2F0aW9ucyBmb3IgaW1wb3J0YW50IGV2ZW50cycpXG4gICAgICAuYWRkVG9nZ2xlKCh0b2dnbGUpID0+XG4gICAgICAgIHRvZ2dsZVxuICAgICAgICAgIC5zZXRWYWx1ZSh0aGlzLnBsdWdpbi5zZXR0aW5ncy5lbmFibGVOb3RpZmljYXRpb25zKVxuICAgICAgICAgIC5vbkNoYW5nZShhc3luYyAodmFsdWUpID0+IHtcbiAgICAgICAgICAgIHRoaXMucGx1Z2luLnNldHRpbmdzLmVuYWJsZU5vdGlmaWNhdGlvbnMgPSB2YWx1ZTtcbiAgICAgICAgICAgIGF3YWl0IHRoaXMucGx1Z2luLnNhdmVTZXR0aW5ncygpO1xuICAgICAgICAgIH0pXG4gICAgICApO1xuICB9XG5cbiAgcHJpdmF0ZSBhZGRBZ2VudENvbnRyb2xzKGNvbnRhaW5lckVsOiBIVE1MRWxlbWVudCk6IHZvaWQge1xuICAgIGNvbnN0IHNlY3Rpb24gPSBjb250YWluZXJFbC5jcmVhdGVFbCgnZGl2JywgeyBjbHM6ICd0aG90aC1zZXR0aW5ncy1zZWN0aW9uIHRob3RoLWNvbnRyb2xzLXNlY3Rpb24nIH0pO1xuICAgIHNlY3Rpb24uY3JlYXRlRWwoJ2gyJywgeyB0ZXh0OiAn8J+OriBBZ2VudCBDb250cm9scycgfSk7XG5cbiAgICBjb25zdCBjb250cm9sc0dyaWQgPSBzZWN0aW9uLmNyZWF0ZUVsKCdkaXYnLCB7IGNsczogJ3Rob3RoLWNvbnRyb2xzLWdyaWQnIH0pO1xuXG4gICAgLy8gU3RhcnQgQWdlbnRcbiAgICBjb25zdCBzdGFydEJ1dHRvbiA9IGNvbnRyb2xzR3JpZC5jcmVhdGVFbCgnYnV0dG9uJywge1xuICAgICAgdGV4dDogJ1N0YXJ0IEFnZW50JyxcbiAgICAgIGNsczogJ3Rob3RoLWNvbnRyb2wtYnV0dG9uIHRob3RoLWJ1dHRvbi1zdGFydCdcbiAgICB9KTtcbiAgICBzdGFydEJ1dHRvbi5vbmNsaWNrID0gKCkgPT4gdGhpcy5wbHVnaW4uc3RhcnRBZ2VudCgpO1xuXG4gICAgLy8gU3RvcCBBZ2VudFxuICAgIGNvbnN0IHN0b3BCdXR0b24gPSBjb250cm9sc0dyaWQuY3JlYXRlRWwoJ2J1dHRvbicsIHtcbiAgICAgIHRleHQ6ICdTdG9wIEFnZW50JyxcbiAgICAgIGNsczogJ3Rob3RoLWNvbnRyb2wtYnV0dG9uIHRob3RoLWJ1dHRvbi1zdG9wJ1xuICAgIH0pO1xuICAgIHN0b3BCdXR0b24ub25jbGljayA9ICgpID0+IHRoaXMucGx1Z2luLnN0b3BBZ2VudCgpO1xuXG4gICAgLy8gUmVzdGFydCBBZ2VudFxuICAgIGNvbnN0IHJlc3RhcnRCdXR0b24gPSBjb250cm9sc0dyaWQuY3JlYXRlRWwoJ2J1dHRvbicsIHtcbiAgICAgIHRleHQ6ICdSZXN0YXJ0IEFnZW50JyxcbiAgICAgIGNsczogJ3Rob3RoLWNvbnRyb2wtYnV0dG9uIHRob3RoLWJ1dHRvbi1yZXN0YXJ0J1xuICAgIH0pO1xuICAgIHJlc3RhcnRCdXR0b24ub25jbGljayA9ICgpID0+IHRoaXMucGx1Z2luLnJlc3RhcnRBZ2VudCgpO1xuXG4gICAgLy8gVGVzdCBDb25uZWN0aW9uXG4gICAgY29uc3QgdGVzdEJ1dHRvbiA9IGNvbnRyb2xzR3JpZC5jcmVhdGVFbCgnYnV0dG9uJywge1xuICAgICAgdGV4dDogJ1Rlc3QgQ29ubmVjdGlvbicsXG4gICAgICBjbHM6ICd0aG90aC1jb250cm9sLWJ1dHRvbiB0aG90aC1idXR0b24tdGVzdCdcbiAgICB9KTtcbiAgICB0ZXN0QnV0dG9uLm9uY2xpY2sgPSBhc3luYyAoKSA9PiB7XG4gICAgICB0ZXN0QnV0dG9uLmRpc2FibGVkID0gdHJ1ZTtcbiAgICAgIHRlc3RCdXR0b24udGV4dENvbnRlbnQgPSAnVGVzdGluZy4uLic7XG5cbiAgICAgIHRyeSB7XG4gICAgICAgIGNvbnN0IGVuZHBvaW50ID0gdGhpcy5wbHVnaW4uZ2V0RW5kcG9pbnRVcmwoKTtcbiAgICAgICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBmZXRjaChgJHtlbmRwb2ludH0vaGVhbHRoYCk7XG4gICAgICAgIGlmIChyZXNwb25zZS5vaykge1xuICAgICAgICAgIG5ldyBOb3RpY2UoJ+KchSBDb25uZWN0aW9uIHN1Y2Nlc3NmdWwhJyk7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgbmV3IE5vdGljZShg4p2MIENvbm5lY3Rpb24gZmFpbGVkOiAke3Jlc3BvbnNlLnN0YXR1c1RleHR9YCk7XG4gICAgICAgIH1cbiAgICAgIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgICAgIG5ldyBOb3RpY2UoYOKdjCBDb25uZWN0aW9uIGZhaWxlZDogJHtlcnJvci5tZXNzYWdlfWApO1xuICAgICAgfSBmaW5hbGx5IHtcbiAgICAgICAgdGVzdEJ1dHRvbi5kaXNhYmxlZCA9IGZhbHNlO1xuICAgICAgICB0ZXN0QnV0dG9uLnRleHRDb250ZW50ID0gJ1Rlc3QgQ29ubmVjdGlvbic7XG4gICAgICB9XG4gICAgfTtcblxuICAgIC8vIE9wZW4gQ2hhdFxuICAgIGNvbnN0IGNoYXRCdXR0b24gPSBjb250cm9sc0dyaWQuY3JlYXRlRWwoJ2J1dHRvbicsIHtcbiAgICAgIHRleHQ6ICdPcGVuIENoYXQnLFxuICAgICAgY2xzOiAndGhvdGgtY29udHJvbC1idXR0b24gdGhvdGgtYnV0dG9uLWNoYXQnXG4gICAgfSk7XG4gICAgY2hhdEJ1dHRvbi5vbmNsaWNrID0gKCkgPT4gdGhpcy5wbHVnaW4ub3BlbkNoYXRNb2RhbCgpO1xuICB9XG59XG4iXX0=
