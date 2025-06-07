"use strict";
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
const DEFAULT_SETTINGS = {
    // API Keys
    mistralKey: '',
    openrouterKey: '',
    opencitationsKey: '',
    googleApiKey: '',
    googleSearchEngineId: '',
    semanticscholarApiKey: '',
    // Default Model Settings
    modelTemperature: 0.9,
    modelMaxTokens: 50000,
    modelTopP: 1.0,
    modelFrequencyPenalty: 0.0,
    modelPresencePenalty: 0.0,
    modelStreaming: false,
    modelUseRateLimiter: true,
    // General LLM Configuration
    llmModel: 'google/gemini-2.5-flash-preview-05-20',
    llmDocProcessing: 'auto',
    llmMaxOutputTokens: 50000,
    llmMaxContextLength: 1000000,
    llmChunkSize: 400000,
    llmChunkOverlap: 50000,
    llmRefineThresholdMultiplier: 0.75,
    llmMapReduceThresholdMultiplier: 0.9,
    // Citation LLM Configuration
    citationLlmModel: 'google/gemini-flash-1.5-8b',
    citationLlmMaxOutputTokens: 10000,
    citationLlmMaxContextLength: 4000,
    // Tag Consolidator LLM Configuration
    tagLlmConsolidateModel: 'google/gemini-flash-1.5-8b',
    tagLlmSuggestModel: 'google/gemini-flash-1.5-8b',
    tagLlmMapModel: 'mistralai/ministral-3b',
    tagLlmMaxOutputTokens: 10000,
    tagLlmMaxContextLength: 8000,
    // Citation Processing Configuration
    citationLinkFormat: 'uri',
    citationStyle: 'IEEE',
    citationUseOpencitations: true,
    citationUseScholarly: false,
    citationUseSemanticscholar: true,
    citationUseArxiv: true,
    citationBatchSize: 1,
    // Endpoint Configuration
    endpointHost: '127.0.0.1',
    endpointPort: '8000',
    endpointBaseUrl: 'http://127.0.0.1:8000',
    endpointAutoStart: false,
    // Monitor Configuration
    monitorAutoStart: false,
    monitorWatchInterval: 5,
    monitorBulkProcessSize: 10,
    // Logging Configuration
    logLevel: 'DEBUG',
    logFormat: '<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | {file}:{line} - <level>{message}</level>',
    logDateFormat: 'YYYY-MM-DD HH:mm:ss',
    logFilename: 'logs/thoth.log',
    logFilemode: 'a',
    logFileLevel: 'DEBUG',
    // Thoth Base Paths & Directories
    workspaceDir: '/home/nick/python/project-thoth',
    obsidianDir: '/mnt/c/Users/nghal/Documents/Obsidian Vault/thoth',
    pdfDir: '${OBSIDIAN_DIR}/papers/pdfs',
    markdownDir: '${WORKSPACE_DIR}/knowledge/markdown',
    notesDir: '${OBSIDIAN_DIR}',
    promptsDir: '${WORKSPACE_DIR}/templates/prompts',
    templatesDir: '${WORKSPACE_DIR}/templates',
    outputDir: '${WORKSPACE_DIR}/knowledge',
    knowledgeBaseDir: '${WORKSPACE_DIR}/knowledge',
    graphStoragePath: '${WORKSPACE_DIR}/knowledge/graph/citations.graphml',
    agentStorageDir: '${WORKSPACE_DIR}/knowledge/agent',
    queriesDir: '${AGENT_STORAGE_DIR}/queries',
    // Research Agent Configuration
    researchAgentAutoStart: false,
    researchAgentDefaultQueries: true,
    // Research Agent LLM Configuration
    researchAgentLlmModel: 'google/gemini-2.5-flash-preview-05-20',
    researchAgentLlmUseAutoModelSelection: true,
    researchAgentLlmAutoModelRequireToolCalling: true,
    researchAgentLlmAutoModelRequireStructuredOutput: true,
    researchAgentLlmMaxOutputTokens: 50000,
    researchAgentLlmMaxContextLength: 100000,
    // Scrape Filter LLM Configuration
    scrapeFilterLlmModel: 'google/gemini-2.5-flash-preview-05-20',
    scrapeFilterLlmMaxOutputTokens: 10000,
    scrapeFilterLlmMaxContextLength: 50000,
    // Discovery System Configuration
    discoveryAutoStartScheduler: false,
    discoveryDefaultMaxArticles: 50,
    discoveryDefaultIntervalMinutes: 60,
    discoveryRateLimitDelay: 1.0,
    discoveryChromeExtensionEnabled: true,
    discoveryChromeExtensionPort: 8765,
    discoverySourcesDir: '${AGENT_STORAGE_DIR}/discovery/sources',
    discoveryResultsDir: '${AGENT_STORAGE_DIR}/discovery/results',
    chromeExtensionConfigsDir: '${AGENT_STORAGE_DIR}/discovery/chrome_configs',
    // Plugin-specific settings
    autoStartAgent: false,
    showStatusBar: true,
    chatHistory: [],
    // Remote connection settings
    remoteMode: false,
    remoteEndpointUrl: '',
};
class ThothPlugin extends obsidian_1.Plugin {
    constructor() {
        super(...arguments);
        this.process = null;
        this.statusBarItem = null;
        this.isAgentRunning = false;
    }
    onload() {
        return __awaiter(this, void 0, void 0, function* () {
            yield this.loadSettings();
            // Add status bar item
            if (this.settings.showStatusBar) {
                this.statusBarItem = this.addStatusBarItem();
                this.updateStatusBar();
            }
            // Add settings tab
            this.addSettingTab(new ThothSettingTab(this.app, this));
            // Add commands
            this.addCommand({
                id: 'start-thoth-agent',
                name: 'Start Thoth Agent',
                icon: 'play',
                callback: () => this.startAgent(),
            });
            this.addCommand({
                id: 'stop-thoth-agent',
                name: 'Stop Thoth Agent',
                icon: 'stop',
                callback: () => this.stopAgent(),
            });
            this.addCommand({
                id: 'restart-thoth-agent',
                name: 'Restart Thoth Agent',
                icon: 'refresh-cw',
                callback: () => this.restartAgent(),
            });
            this.addCommand({
                id: 'open-thoth-chat',
                name: 'Open Research Chat',
                icon: 'message-circle',
                callback: () => this.openChat(),
            });
            this.addCommand({
                id: 'insert-research-query',
                name: 'Insert Research Query',
                icon: 'search',
                editorCallback: (editor) => {
                    const selection = editor.getSelection();
                    if (selection) {
                        this.performResearch(selection);
                    }
                    else {
                        new obsidian_1.Notice('Please select text to research');
                    }
                },
            });
            // Auto-start agent if enabled
            if (this.settings.autoStartAgent) {
                setTimeout(() => this.startAgent(), 2000);
            }
        });
    }
    onunload() {
        this.stopAgent();
    }
    loadSettings() {
        return __awaiter(this, void 0, void 0, function* () {
            this.settings = Object.assign({}, DEFAULT_SETTINGS, yield this.loadData());
        });
    }
    saveSettings() {
        return __awaiter(this, void 0, void 0, function* () {
            yield this.saveData(this.settings);
            yield this.updateEnvironmentFile();
        });
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
                    `API_SEMANTICSCHOLAR_API_KEY=${this.settings.semanticscholarApiKey}`,
                    '',
                    '# ----------------------------------------------------------------------------------',
                    '# --- 2. Default Model Settings ---',
                    '# ----------------------------------------------------------------------------------',
                    `MODEL_TEMPERATURE=${this.settings.modelTemperature}`,
                    `MODEL_MAX_TOKENS=${this.settings.modelMaxTokens}`,
                    `MODEL_TOP_P=${this.settings.modelTopP}`,
                    `MODEL_FREQUENCY_PENALTY=${this.settings.modelFrequencyPenalty}`,
                    `MODEL_PRESENCE_PENALTY=${this.settings.modelPresencePenalty}`,
                    `MODEL_STREAMING=${this.settings.modelStreaming}`,
                    `MODEL_USE_RATE_LIMITER=${this.settings.modelUseRateLimiter}`,
                    '',
                    '# ----------------------------------------------------------------------------------',
                    '# --- 3. General LLM Configuration ---',
                    '# ----------------------------------------------------------------------------------',
                    `LLM_MODEL=${this.settings.llmModel}`,
                    `LLM_DOC_PROCESSING=${this.settings.llmDocProcessing}`,
                    `LLM_MAX_OUTPUT_TOKENS=${this.settings.llmMaxOutputTokens}`,
                    `LLM_MAX_CONTEXT_LENGTH=${this.settings.llmMaxContextLength}`,
                    `LLM_CHUNK_SIZE=${this.settings.llmChunkSize}`,
                    `LLM_CHUNK_OVERLAP=${this.settings.llmChunkOverlap}`,
                    `LLM_REFINE_THRESHOLD_MULTIPLIER=${this.settings.llmRefineThresholdMultiplier}`,
                    `LLM_MAP_REDUCE_THRESHOLD_MULTIPLIER=${this.settings.llmMapReduceThresholdMultiplier}`,
                    '',
                    '# ----------------------------------------------------------------------------------',
                    '# --- 4. Citation LLM Configuration ---',
                    '# ----------------------------------------------------------------------------------',
                    `CITATION_LLM_MODEL=${this.settings.citationLlmModel}`,
                    `CITATION_LLM_MAX_OUTPUT_TOKENS=${this.settings.citationLlmMaxOutputTokens}`,
                    `CITATION_LLM_MAX_CONTEXT_LENGTH=${this.settings.citationLlmMaxContextLength}`,
                    '',
                    '# ----------------------------------------------------------------------------------',
                    '# --- 4.5. Tag Consolidator LLM Configuration ---',
                    '# ----------------------------------------------------------------------------------',
                    `TAG_LLM_CONSOLIDATE_MODEL=${this.settings.tagLlmConsolidateModel}`,
                    `TAG_LLM_SUGGEST_MODEL=${this.settings.tagLlmSuggestModel}`,
                    `TAG_LLM_MAP_MODEL=${this.settings.tagLlmMapModel}`,
                    `TAG_LLM_MAX_OUTPUT_TOKENS=${this.settings.tagLlmMaxOutputTokens}`,
                    `TAG_LLM_MAX_CONTEXT_LENGTH=${this.settings.tagLlmMaxContextLength}`,
                    '',
                    '# ----------------------------------------------------------------------------------',
                    '# --- 5. Citation Processing Configuration ---',
                    '# ----------------------------------------------------------------------------------',
                    `CITATION_LINK_FORMAT=${this.settings.citationLinkFormat}`,
                    `CITATION_STYLE=${this.settings.citationStyle}`,
                    `CITATION_USE_OPENCITATIONS=${this.settings.citationUseOpencitations}`,
                    `CITATION_USE_SCHOLARLY=${this.settings.citationUseScholarly}`,
                    `CITATION_USE_SEMANTICSCHOLAR=${this.settings.citationUseSemanticscholar}`,
                    `CITATION_USE_ARXIV=${this.settings.citationUseArxiv}`,
                    `CITATION_CITATION_BATCH_SIZE=${this.settings.citationBatchSize}`,
                    '',
                    '# ----------------------------------------------------------------------------------',
                    '# --- 6. Endpoint Configuration ---',
                    '# ----------------------------------------------------------------------------------',
                    `ENDPOINT_HOST=${this.settings.endpointHost}`,
                    `ENDPOINT_PORT=${this.settings.endpointPort}`,
                    `ENDPOINT_BASE_URL=${this.settings.endpointBaseUrl}`,
                    `ENDPOINT_AUTO_START=${this.settings.endpointAutoStart}`,
                    '',
                    '# ----------------------------------------------------------------------------------',
                    '# --- 7. Monitor Configuration ---',
                    '# ----------------------------------------------------------------------------------',
                    `MONITOR_AUTO_START=${this.settings.monitorAutoStart}`,
                    `MONITOR_WATCH_INTERVAL=${this.settings.monitorWatchInterval}`,
                    `MONITOR_BULK_PROCESS_SIZE=${this.settings.monitorBulkProcessSize}`,
                    '',
                    '# ----------------------------------------------------------------------------------',
                    '# --- 8. Logging Configuration ---',
                    '# ----------------------------------------------------------------------------------',
                    `LOG_LEVEL=${this.settings.logLevel}`,
                    `LOG_LOGFORMAT="${this.settings.logFormat}"`,
                    `LOG_DATEFORMAT="${this.settings.logDateFormat}"`,
                    `LOG_FILENAME=${this.settings.logFilename}`,
                    `LOG_FILEMODE=${this.settings.logFilemode}`,
                    `LOG_FILE_LEVEL=${this.settings.logFileLevel}`,
                    '',
                    '# ----------------------------------------------------------------------------------',
                    '# --- 9. Thoth Base Paths & Directories ---',
                    '# ----------------------------------------------------------------------------------',
                    `WORKSPACE_DIR=${this.settings.workspaceDir}`,
                    `OBSIDIAN_DIR=${this.settings.obsidianDir}`,
                    `PDF_DIR=${this.settings.pdfDir}`,
                    `MARKDOWN_DIR=${this.settings.markdownDir}`,
                    `NOTES_DIR=${this.settings.notesDir}`,
                    `PROMPTS_DIR=${this.settings.promptsDir}`,
                    `TEMPLATES_DIR=${this.settings.templatesDir}`,
                    `OUTPUT_DIR=${this.settings.outputDir}`,
                    `KNOWLEDGE_BASE_DIR=${this.settings.knowledgeBaseDir}`,
                    `GRAPH_STORAGE_PATH=${this.settings.graphStoragePath}`,
                    `AGENT_STORAGE_DIR=${this.settings.agentStorageDir}`,
                    `QUERIES_DIR=${this.settings.queriesDir}`,
                    '',
                    '# Research agent settings',
                    `RESEARCH_AGENT_AUTO_START=${this.settings.researchAgentAutoStart}`,
                    `RESEARCH_AGENT_DEFAULT_QUERIES=${this.settings.researchAgentDefaultQueries}`,
                    '',
                    '# ----------------------------------------------------------------------------------',
                    '# --- 10. Research Agent LLM Configuration ---',
                    '# ----------------------------------------------------------------------------------',
                    `RESEARCH_AGENT_LLM_MODEL=${this.settings.researchAgentLlmModel}`,
                    `RESEARCH_AGENT_LLM_USE_AUTO_MODEL_SELECTION=${this.settings.researchAgentLlmUseAutoModelSelection}`,
                    `RESEARCH_AGENT_LLM_AUTO_MODEL_REQUIRE_TOOL_CALLING=${this.settings.researchAgentLlmAutoModelRequireToolCalling}`,
                    `RESEARCH_AGENT_LLM_AUTO_MODEL_REQUIRE_STRUCTURED_OUTPUT=${this.settings.researchAgentLlmAutoModelRequireStructuredOutput}`,
                    `RESEARCH_AGENT_LLM_MAX_OUTPUT_TOKENS=${this.settings.researchAgentLlmMaxOutputTokens}`,
                    `RESEARCH_AGENT_LLM_MAX_CONTEXT_LENGTH=${this.settings.researchAgentLlmMaxContextLength}`,
                    '',
                    '# ----------------------------------------------------------------------------------',
                    '# --- 11. Scrape Filter LLM Configuration ---',
                    '# ----------------------------------------------------------------------------------',
                    `SCRAPE_FILTER_LLM_MODEL=${this.settings.scrapeFilterLlmModel}`,
                    `SCRAPE_FILTER_LLM_MAX_OUTPUT_TOKENS=${this.settings.scrapeFilterLlmMaxOutputTokens}`,
                    `SCRAPE_FILTER_LLM_MAX_CONTEXT_LENGTH=${this.settings.scrapeFilterLlmMaxContextLength}`,
                    '',
                    '# ----------------------------------------------------------------------------------',
                    '# --- 12. Discovery System Configuration ---',
                    '# ----------------------------------------------------------------------------------',
                    `DISCOVERY_AUTO_START_SCHEDULER=${this.settings.discoveryAutoStartScheduler}`,
                    `DISCOVERY_DEFAULT_MAX_ARTICLES=${this.settings.discoveryDefaultMaxArticles}`,
                    `DISCOVERY_DEFAULT_INTERVAL_MINUTES=${this.settings.discoveryDefaultIntervalMinutes}`,
                    `DISCOVERY_RATE_LIMIT_DELAY=${this.settings.discoveryRateLimitDelay}`,
                    `DISCOVERY_CHROME_EXTENSION_ENABLED=${this.settings.discoveryChromeExtensionEnabled}`,
                    `DISCOVERY_CHROME_EXTENSION_PORT=${this.settings.discoveryChromeExtensionPort}`,
                    '',
                    '# --- Discovery folders ---',
                    `DISCOVERY_SOURCES_DIR=${this.settings.discoverySourcesDir}`,
                    `DISCOVERY_RESULTS_DIR=${this.settings.discoveryResultsDir}`,
                    `CHROME_EXTENSION_CONFIGS_DIR=${this.settings.chromeExtensionConfigsDir}`,
                ];
                // Write to workspace directory (not vault) since that's where the process runs
                try {
                    // First try to write to workspace directory if it exists
                    if (this.settings.workspaceDir && require('fs').existsSync(this.settings.workspaceDir)) {
                        const path = require('path');
                        const fs = require('fs');
                        const envPath = path.join(this.settings.workspaceDir, '.env');
                        fs.writeFileSync(envPath, lines.join('\n'));
                        new obsidian_1.Notice('Thoth configuration updated in workspace directory');
                        return;
                    }
                }
                catch (e) {
                    console.warn('Could not write to workspace directory:', e);
                }
                // Fallback: write to vault using Obsidian's API
                try {
                    yield this.app.vault.adapter.write('.env', lines.join('\n'));
                    new obsidian_1.Notice('Thoth configuration updated in vault (fallback)');
                }
                catch (e) {
                    console.error('Could not write to vault:', e);
                    new obsidian_1.Notice('Could not update environment file in vault');
                }
            }
            catch (error) {
                console.error('Failed to update environment file:', error);
                new obsidian_1.Notice('Warning: Could not update environment file');
            }
        });
    }
    updateStatusBar() {
        if (!this.statusBarItem)
            return;
        if (this.isAgentRunning) {
            // Check actual agent health
            this.checkAgentHealth().then((healthy) => {
                const status = healthy ? 'Running' : 'Error';
                const color = healthy ? '#00ff00' : '#ffaa00';
                this.statusBarItem.innerHTML = `<span style="color: ${color}">Thoth: ${status}</span>`;
                this.statusBarItem.title = healthy
                    ? 'Thoth Agent is running and healthy. Click to stop.'
                    : 'Thoth Agent process is running but API is not responding. Click to restart.';
            }).catch(() => {
                this.statusBarItem.innerHTML = `<span style="color: #ffaa00">Thoth: Checking...</span>`;
            });
        }
        else {
            this.statusBarItem.innerHTML = `<span style="color: #ff6b6b">Thoth: Stopped</span>`;
            this.statusBarItem.title = 'Thoth Agent is stopped. Click to start.';
        }
        this.statusBarItem.onclick = () => {
            if (this.isAgentRunning) {
                this.stopAgent();
            }
            else {
                this.startAgent();
            }
        };
    }
    startAgent() {
        return __awaiter(this, void 0, void 0, function* () {
            if (this.process && !this.settings.remoteMode) {
                new obsidian_1.Notice('Thoth agent is already running');
                return;
            }
            // Validate settings first
            if (!this.settings.mistralKey && !this.settings.openrouterKey) {
                new obsidian_1.Notice('Please configure API keys in settings first');
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
                    // Test connection to remote server
                    const controller = new AbortController();
                    const timeoutId = setTimeout(() => controller.abort(), 5000);
                    const response = yield fetch(`${this.settings.remoteEndpointUrl}/health`, {
                        method: 'GET',
                        signal: controller.signal
                    });
                    clearTimeout(timeoutId);
                    if (!response.ok) {
                        throw new Error(`Server responded with ${response.status}`);
                    }
                    // Update base URL to use remote endpoint
                    this.settings.endpointBaseUrl = this.settings.remoteEndpointUrl;
                    yield this.saveSettings();
                    this.isAgentRunning = true;
                    this.updateStatusBar();
                    new obsidian_1.Notice('Connected to remote Thoth server successfully!');
                    // Check if agent is properly initialized
                    setTimeout(() => __awaiter(this, void 0, void 0, function* () {
                        const healthy = yield this.checkAgentHealth();
                        if (!healthy) {
                            new obsidian_1.Notice('Connected to server but research agent not ready. Server may still be starting up.');
                        }
                    }), 2000);
                    return;
                }
                catch (error) {
                    console.error('Failed to connect to remote server:', error);
                    new obsidian_1.Notice(`Failed to connect to remote server: ${error.message}`);
                    return;
                }
            }
            // Local mode - spawn local process
            if (this.process) {
                new obsidian_1.Notice('Thoth agent is already running');
                return;
            }
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
                    '--host', this.settings.endpointHost,
                    '--port', this.settings.endpointPort,
                    '--base-url', this.settings.endpointBaseUrl,
                ];
                // Create environment with all necessary variables
                const envVars = Object.assign(Object.assign({}, process.env), {
                    // API Keys
                    API_MISTRAL_KEY: this.settings.mistralKey, API_OPENROUTER_KEY: this.settings.openrouterKey, API_OPENCITATIONS_KEY: this.settings.opencitationsKey, API_GOOGLE_API_KEY: this.settings.googleApiKey, API_GOOGLE_SEARCH_ENGINE_ID: this.settings.googleSearchEngineId, API_SEMANTICSCHOLAR_API_KEY: this.settings.semanticscholarApiKey,
                    // Endpoint Configuration
                    ENDPOINT_HOST: this.settings.endpointHost, ENDPOINT_PORT: this.settings.endpointPort, ENDPOINT_BASE_URL: this.settings.endpointBaseUrl,
                    // Directory Configuration
                    WORKSPACE_DIR: this.settings.workspaceDir, OBSIDIAN_DIR: this.settings.obsidianDir,
                    // LLM Configuration
                    LLM_MODEL: this.settings.llmModel, CITATION_LLM_MODEL: this.settings.citationLlmModel, RESEARCH_AGENT_LLM_MODEL: this.settings.researchAgentLlmModel,
                    // Model Settings
                    MODEL_TEMPERATURE: this.settings.modelTemperature.toString(), MODEL_MAX_TOKENS: this.settings.modelMaxTokens.toString(),
                    // Logging
                    LOG_LEVEL: this.settings.logLevel });
                // Remove undefined values
                Object.keys(envVars).forEach(key => {
                    if (envVars[key] === undefined || envVars[key] === null || envVars[key] === '') {
                        delete envVars[key];
                    }
                });
                this.process = (0, child_process_1.spawn)(cmd, args, {
                    // Set working directory to workspace directory if configured
                    cwd: this.settings.workspaceDir || undefined,
                    // Set environment variables from plugin settings
                    env: envVars
                });
                this.process.stdout.on('data', (data) => {
                    const output = data.toString();
                    console.log('Thoth Agent:', output);
                    // Check for startup success indicators
                    if (output.includes('Uvicorn running on') || output.includes('Application startup complete')) {
                        new obsidian_1.Notice('Thoth API server started successfully!');
                    }
                });
                this.process.stderr.on('data', (data) => {
                    const error = data.toString();
                    console.error('Thoth Agent Error:', error);
                    // Show specific error messages to user
                    if (error.includes('API key')) {
                        new obsidian_1.Notice('API key error - check your configuration');
                    }
                    else if (error.includes('Permission denied') || error.includes('command not found')) {
                        new obsidian_1.Notice('Installation error - is uv and thoth installed?');
                    }
                    else if (error.includes('Address already in use')) {
                        new obsidian_1.Notice(`Port ${this.settings.endpointPort} already in use - try a different port`);
                    }
                    else {
                        new obsidian_1.Notice(`Thoth Agent Error: ${error.slice(0, 100)}...`);
                    }
                });
                this.process.on('close', (code) => {
                    this.process = null;
                    this.isAgentRunning = false;
                    this.updateStatusBar();
                    if (code !== 0) {
                        new obsidian_1.Notice(`Thoth agent stopped with code ${code}`);
                        console.error(`Thoth agent exited with code: ${code}`);
                    }
                    else {
                        new obsidian_1.Notice('Thoth agent stopped normally');
                    }
                });
                this.process.on('error', (error) => {
                    console.error('Failed to start Thoth agent:', error);
                    // Provide specific error messages
                    if (error.message.includes('ENOENT')) {
                        new obsidian_1.Notice('Failed to start Thoth agent: uv command not found. Please install uv first.');
                    }
                    else if (error.message.includes('EACCES')) {
                        new obsidian_1.Notice('Failed to start Thoth agent: Permission denied. Check file permissions.');
                    }
                    else {
                        new obsidian_1.Notice(`Failed to start Thoth agent: ${error.message}`);
                    }
                    this.process = null;
                    this.isAgentRunning = false;
                    this.updateStatusBar();
                });
                this.isAgentRunning = true;
                this.updateStatusBar();
                new obsidian_1.Notice('Starting Thoth agent... This may take a moment.');
                // Wait a bit then check if it actually started
                setTimeout(() => __awaiter(this, void 0, void 0, function* () {
                    const healthy = yield this.checkAgentHealth();
                    if (!healthy && this.isAgentRunning) {
                        new obsidian_1.Notice('Thoth agent process started but API not responding. Check console for errors.');
                    }
                }), 5000);
            }
            catch (error) {
                console.error('Error starting agent:', error);
                new obsidian_1.Notice(`Failed to start Thoth agent: ${error.message}`);
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
            if (this.isAgentRunning) {
                this.stopAgent();
                // Wait a moment before restarting
                setTimeout(() => this.startAgent(), 1000);
            }
            else {
                yield this.startAgent();
            }
        });
    }
    performResearch(query) {
        return __awaiter(this, void 0, void 0, function* () {
            if (!this.isAgentRunning) {
                new obsidian_1.Notice('Please start the Thoth agent first');
                return;
            }
            new obsidian_1.Notice(`Researching: "${query.slice(0, 50)}..."`);
            try {
                // Try direct research API call first
                const response = yield this.callResearchAPI(query);
                if (response) {
                    // Insert research results directly into the current note
                    yield this.insertResearchResults(query, response);
                    return;
                }
            }
            catch (error) {
                console.error('Direct research failed:', error);
                new obsidian_1.Notice('Direct research failed, opening chat interface...');
            }
            // Fallback to chat modal
            const modal = new ChatModal(this.app, this);
            modal.setInitialQuery(query);
            modal.open();
        });
    }
    callResearchAPI(query) {
        return __awaiter(this, void 0, void 0, function* () {
            const apiUrl = `${this.settings.endpointBaseUrl}/research/query`;
            try {
                const response = yield fetch(apiUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        query: query,
                        type: 'quick_research',
                        max_results: 5,
                        include_citations: true,
                    }),
                });
                if (!response.ok) {
                    return null;
                }
                const data = yield response.json();
                return data.results || data.response || null;
            }
            catch (error) {
                console.error('Research API call failed:', error);
                return null;
            }
        });
    }
    insertResearchResults(query, results) {
        return __awaiter(this, void 0, void 0, function* () {
            // Get the active editor
            const activeLeaf = this.app.workspace.activeLeaf;
            if (!activeLeaf || !activeLeaf.view || activeLeaf.view.getViewType() !== 'markdown') {
                new obsidian_1.Notice('No active markdown editor found');
                return;
            }
            const view = activeLeaf.view; // Type assertion for editor access
            if (!view.editor) {
                new obsidian_1.Notice('No editor available in active view');
                return;
            }
            const editor = view.editor;
            const cursor = editor.getCursor();
            // Format the research results
            const timestamp = new Date().toLocaleString();
            const researchBlock = [
                '',
                `## 🔍 Research: ${query}`,
                `*Generated on ${timestamp} by Thoth Research Assistant*`,
                '',
                results,
                '',
                '---',
                ''
            ].join('\n');
            // Insert at cursor position
            editor.replaceRange(researchBlock, cursor);
            new obsidian_1.Notice('Research results inserted!');
        });
    }
    checkAgentHealth() {
        return __awaiter(this, void 0, void 0, function* () {
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 5000);
                // Check basic health endpoint
                const healthResponse = yield fetch(`${this.settings.endpointBaseUrl}/health`, {
                    method: 'GET',
                    signal: controller.signal,
                });
                clearTimeout(timeoutId);
                if (!healthResponse.ok) {
                    return false;
                }
                // Also check if the agent is initialized by testing agent status
                try {
                    const agentController = new AbortController();
                    const agentTimeoutId = setTimeout(() => agentController.abort(), 3000);
                    const agentResponse = yield fetch(`${this.settings.endpointBaseUrl}/agent/status`, {
                        method: 'GET',
                        signal: agentController.signal,
                    });
                    clearTimeout(agentTimeoutId);
                    if (agentResponse.ok) {
                        const data = yield agentResponse.json();
                        return data.agent_initialized === true;
                    }
                }
                catch (error) {
                    // Agent status check failed, but basic health passed
                    console.warn('Agent status check failed:', error);
                }
                return true; // Basic health check passed
            }
            catch (error) {
                return false;
            }
        });
    }
    openChat() {
        new ChatModal(this.app, this).open();
    }
}
exports.default = ThothPlugin;
class ThothSettingTab extends obsidian_1.PluginSettingTab {
    constructor(app, plugin) {
        super(app, plugin);
        this.plugin = plugin;
    }
    display() {
        const { containerEl } = this;
        containerEl.empty();
        containerEl.createEl('h2', { text: 'Thoth Research Assistant Settings' });
        // API Keys Section
        containerEl.createEl('h3', { text: '🔑 API Configuration' });
        new obsidian_1.Setting(containerEl)
            .setName('Mistral API Key')
            .setDesc('Your Mistral API key for AI-powered research')
            .addText((text) => text
            .setPlaceholder('Enter Mistral API key')
            .setValue(this.plugin.settings.mistralKey)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.mistralKey = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(containerEl)
            .setName('OpenRouter API Key')
            .setDesc('Your OpenRouter API key for accessing multiple AI models')
            .addText((text) => text
            .setPlaceholder('Enter OpenRouter API key')
            .setValue(this.plugin.settings.openrouterKey)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.openrouterKey = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(containerEl)
            .setName('OpenCitations API Key')
            .setDesc('API key for citation services')
            .addText((text) => text
            .setPlaceholder('Enter OpenCitations API key')
            .setValue(this.plugin.settings.opencitationsKey)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.opencitationsKey = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(containerEl)
            .setName('Google API Key')
            .setDesc('Google API key for search services')
            .addText((text) => text
            .setPlaceholder('Enter Google API key')
            .setValue(this.plugin.settings.googleApiKey)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.googleApiKey = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(containerEl)
            .setName('Google Search Engine ID')
            .setDesc('Custom search engine ID')
            .addText((text) => text
            .setPlaceholder('Enter search engine ID')
            .setValue(this.plugin.settings.googleSearchEngineId)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.googleSearchEngineId = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(containerEl)
            .setName('Semantic Scholar API Key')
            .setDesc('API key for Semantic Scholar integration')
            .addText((text) => text
            .setPlaceholder('Enter Semantic Scholar API key')
            .setValue(this.plugin.settings.semanticscholarApiKey)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.semanticscholarApiKey = value;
            yield this.plugin.saveSettings();
        })));
        // Model Configuration Section
        containerEl.createEl('h3', { text: '🤖 Model Configuration' });
        new obsidian_1.Setting(containerEl)
            .setName('Primary LLM Model')
            .setDesc('Main language model for content analysis')
            .addText((text) => text
            .setPlaceholder('e.g., google/gemini-2.5-flash-preview-05-20')
            .setValue(this.plugin.settings.llmModel)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.llmModel = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(containerEl)
            .setName('Citation LLM Model')
            .setDesc('Language model for citation tasks')
            .addText((text) => text
            .setPlaceholder('e.g., google/gemini-flash-1.5-8b')
            .setValue(this.plugin.settings.citationLlmModel)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.citationLlmModel = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(containerEl)
            .setName('Model Temperature')
            .setDesc('Controls randomness in AI responses (0.0-2.0)')
            .addSlider((slider) => slider
            .setLimits(0, 2, 0.1)
            .setValue(this.plugin.settings.modelTemperature)
            .setDynamicTooltip()
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.modelTemperature = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(containerEl)
            .setName('Max Output Tokens')
            .setDesc('Maximum tokens the model can generate')
            .addText((text) => text
            .setPlaceholder('50000')
            .setValue(this.plugin.settings.llmMaxOutputTokens.toString())
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.llmMaxOutputTokens = parseInt(value) || 50000;
            yield this.plugin.saveSettings();
        })));
        // Connection Settings
        containerEl.createEl('h3', { text: '🌐 Connection Settings' });
        new obsidian_1.Setting(containerEl)
            .setName('Remote Mode')
            .setDesc('Connect to a remote Thoth server (e.g., running in WSL) instead of starting locally')
            .addToggle((toggle) => toggle
            .setValue(this.plugin.settings.remoteMode)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.remoteMode = value;
            yield this.plugin.saveSettings();
            // Refresh the display to show/hide relevant settings
            this.display();
        })));
        if (this.plugin.settings.remoteMode) {
            new obsidian_1.Setting(containerEl)
                .setName('Remote Endpoint URL')
                .setDesc('Full URL of the remote Thoth server (e.g., http://localhost:8000 or http://WSL_IP:8000)')
                .addText((text) => text
                .setPlaceholder('http://localhost:8000')
                .setValue(this.plugin.settings.remoteEndpointUrl)
                .onChange((value) => __awaiter(this, void 0, void 0, function* () {
                this.plugin.settings.remoteEndpointUrl = value;
                // Also update the base URL to match
                this.plugin.settings.endpointBaseUrl = value;
                yield this.plugin.saveSettings();
            })));
            // Add info about WSL setup
            const infoEl = containerEl.createDiv();
            infoEl.innerHTML = `
        <div style="margin: 10px 0; padding: 10px; background: #f0f8ff; border-left: 4px solid #007acc; border-radius: 4px;">
          <strong>WSL Setup:</strong><br/>
          1. Start Thoth in WSL: <code>uv run python -m thoth api --host 0.0.0.0 --port 8000</code><br/>
          2. Find WSL IP: <code>hostname -I</code><br/>
          3. Use URL: <code>http://WSL_IP:8000</code><br/>
          Or use <code>http://localhost:8000</code> if port is forwarded.
        </div>
      `;
        }
        else {
            new obsidian_1.Setting(containerEl)
                .setName('Endpoint Host')
                .setDesc('Host address for the Thoth agent')
                .addText((text) => text
                .setPlaceholder('127.0.0.1')
                .setValue(this.plugin.settings.endpointHost)
                .onChange((value) => __awaiter(this, void 0, void 0, function* () {
                this.plugin.settings.endpointHost = value;
                yield this.plugin.saveSettings();
            })));
            new obsidian_1.Setting(containerEl)
                .setName('Endpoint Port')
                .setDesc('Port number for the Thoth agent')
                .addText((text) => text
                .setPlaceholder('8000')
                .setValue(this.plugin.settings.endpointPort)
                .onChange((value) => __awaiter(this, void 0, void 0, function* () {
                this.plugin.settings.endpointPort = value;
                yield this.plugin.saveSettings();
            })));
        }
        new obsidian_1.Setting(containerEl)
            .setName('Base URL')
            .setDesc('Full base URL for the Thoth API (auto-updated when using remote mode)')
            .addText((text) => text
            .setPlaceholder('http://127.0.0.1:8000')
            .setValue(this.plugin.settings.endpointBaseUrl)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.endpointBaseUrl = value;
            yield this.plugin.saveSettings();
        })));
        // Directory Settings
        containerEl.createEl('h3', { text: '📁 Directory Settings' });
        new obsidian_1.Setting(containerEl)
            .setName('Workspace Directory')
            .setDesc('Main Thoth workspace directory')
            .addText((text) => text
            .setPlaceholder('/path/to/project-thoth')
            .setValue(this.plugin.settings.workspaceDir)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.workspaceDir = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(containerEl)
            .setName('Obsidian Directory')
            .setDesc('Directory for Obsidian-specific files')
            .addText((text) => text
            .setPlaceholder('/path/to/obsidian/vault/thoth')
            .setValue(this.plugin.settings.obsidianDir)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.obsidianDir = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(containerEl)
            .setName('PDF Directory')
            .setDesc('Directory for storing PDF files')
            .addText((text) => text
            .setPlaceholder('${OBSIDIAN_DIR}/papers/pdfs')
            .setValue(this.plugin.settings.pdfDir)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.pdfDir = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(containerEl)
            .setName('Knowledge Base Directory')
            .setDesc('Directory for knowledge base storage')
            .addText((text) => text
            .setPlaceholder('${WORKSPACE_DIR}/knowledge')
            .setValue(this.plugin.settings.knowledgeBaseDir)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.knowledgeBaseDir = value;
            yield this.plugin.saveSettings();
        })));
        // Citation Settings
        containerEl.createEl('h3', { text: '📚 Citation Settings' });
        new obsidian_1.Setting(containerEl)
            .setName('Citation Style')
            .setDesc('Default citation style format')
            .addDropdown((dropdown) => dropdown
            .addOption('IEEE', 'IEEE')
            .addOption('APA', 'APA')
            .addOption('MLA', 'MLA')
            .addOption('Chicago', 'Chicago')
            .setValue(this.plugin.settings.citationStyle)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.citationStyle = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(containerEl)
            .setName('Use OpenCitations')
            .setDesc('Enable OpenCitations integration')
            .addToggle((toggle) => toggle
            .setValue(this.plugin.settings.citationUseOpencitations)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.citationUseOpencitations = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(containerEl)
            .setName('Use Semantic Scholar')
            .setDesc('Enable Semantic Scholar integration')
            .addToggle((toggle) => toggle
            .setValue(this.plugin.settings.citationUseSemanticscholar)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.citationUseSemanticscholar = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(containerEl)
            .setName('Use arXiv')
            .setDesc('Enable arXiv integration')
            .addToggle((toggle) => toggle
            .setValue(this.plugin.settings.citationUseArxiv)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.citationUseArxiv = value;
            yield this.plugin.saveSettings();
        })));
        // Behavior Settings
        containerEl.createEl('h3', { text: '⚙️ Behavior Settings' });
        new obsidian_1.Setting(containerEl)
            .setName('Auto-start Agent')
            .setDesc('Automatically start the Thoth agent when Obsidian opens')
            .addToggle((toggle) => toggle
            .setValue(this.plugin.settings.autoStartAgent)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.autoStartAgent = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(containerEl)
            .setName('Show Status Bar')
            .setDesc('Display agent status in the status bar')
            .addToggle((toggle) => toggle
            .setValue(this.plugin.settings.showStatusBar)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.showStatusBar = value;
            yield this.plugin.saveSettings();
            // Update status bar visibility
            if (value && !this.plugin.statusBarItem) {
                this.plugin.statusBarItem = this.plugin.addStatusBarItem();
                this.plugin.updateStatusBar();
            }
            else if (!value && this.plugin.statusBarItem) {
                this.plugin.statusBarItem.remove();
                this.plugin.statusBarItem = null;
            }
        })));
        new obsidian_1.Setting(containerEl)
            .setName('Auto-start Endpoint')
            .setDesc('Automatically start the endpoint server')
            .addToggle((toggle) => toggle
            .setValue(this.plugin.settings.endpointAutoStart)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.endpointAutoStart = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(containerEl)
            .setName('Auto-start Monitor')
            .setDesc('Automatically start file monitoring')
            .addToggle((toggle) => toggle
            .setValue(this.plugin.settings.monitorAutoStart)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.monitorAutoStart = value;
            yield this.plugin.saveSettings();
        })));
        // Discovery Settings
        containerEl.createEl('h3', { text: '🔍 Discovery Settings' });
        new obsidian_1.Setting(containerEl)
            .setName('Chrome Extension Enabled')
            .setDesc('Enable Chrome extension integration')
            .addToggle((toggle) => toggle
            .setValue(this.plugin.settings.discoveryChromeExtensionEnabled)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.discoveryChromeExtensionEnabled = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(containerEl)
            .setName('Chrome Extension Port')
            .setDesc('Port for Chrome extension communication')
            .addText((text) => text
            .setPlaceholder('8765')
            .setValue(this.plugin.settings.discoveryChromeExtensionPort.toString())
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.discoveryChromeExtensionPort = parseInt(value) || 8765;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(containerEl)
            .setName('Default Max Articles')
            .setDesc('Maximum articles to discover per session')
            .addText((text) => text
            .setPlaceholder('50')
            .setValue(this.plugin.settings.discoveryDefaultMaxArticles.toString())
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.discoveryDefaultMaxArticles = parseInt(value) || 50;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(containerEl)
            .setName('Discovery Interval (minutes)')
            .setDesc('How often to run automatic discovery')
            .addText((text) => text
            .setPlaceholder('60')
            .setValue(this.plugin.settings.discoveryDefaultIntervalMinutes.toString())
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.discoveryDefaultIntervalMinutes = parseInt(value) || 60;
            yield this.plugin.saveSettings();
        })));
        // Advanced Settings
        containerEl.createEl('h3', { text: '🔧 Advanced Settings' });
        new obsidian_1.Setting(containerEl)
            .setName('Log Level')
            .setDesc('Logging verbosity level')
            .addDropdown((dropdown) => dropdown
            .addOption('DEBUG', 'DEBUG')
            .addOption('INFO', 'INFO')
            .addOption('WARNING', 'WARNING')
            .addOption('ERROR', 'ERROR')
            .setValue(this.plugin.settings.logLevel)
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.logLevel = value;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(containerEl)
            .setName('Monitor Watch Interval')
            .setDesc('File monitoring interval in seconds')
            .addText((text) => text
            .setPlaceholder('5')
            .setValue(this.plugin.settings.monitorWatchInterval.toString())
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.monitorWatchInterval = parseInt(value) || 5;
            yield this.plugin.saveSettings();
        })));
        new obsidian_1.Setting(containerEl)
            .setName('LLM Context Length')
            .setDesc('Maximum context length for primary LLM')
            .addText((text) => text
            .setPlaceholder('1000000')
            .setValue(this.plugin.settings.llmMaxContextLength.toString())
            .onChange((value) => __awaiter(this, void 0, void 0, function* () {
            this.plugin.settings.llmMaxContextLength = parseInt(value) || 1000000;
            yield this.plugin.saveSettings();
        })));
        // Control Section
        containerEl.createEl('h3', { text: 'Agent Control' });
        new obsidian_1.Setting(containerEl)
            .setName('Agent Status')
            .setDesc('Start, stop, or restart the Thoth agent')
            .addButton((btn) => btn
            .setButtonText(this.plugin.isAgentRunning ? 'Stop Agent' : 'Start Agent')
            .onClick(() => __awaiter(this, void 0, void 0, function* () {
            if (this.plugin.isAgentRunning) {
                this.plugin.stopAgent();
            }
            else {
                yield this.plugin.startAgent();
            }
            // Refresh the button text
            setTimeout(() => this.display(), 100);
        })))
            .addButton((btn) => btn
            .setButtonText('Restart Agent')
            .onClick(() => __awaiter(this, void 0, void 0, function* () {
            yield this.plugin.restartAgent();
            setTimeout(() => this.display(), 100);
        })));
    }
}
class ChatModal extends obsidian_1.Modal {
    constructor(app, plugin) {
        super(app);
        this.initialQuery = '';
        this.plugin = plugin;
    }
    setInitialQuery(query) {
        this.initialQuery = query;
    }
    onOpen() {
        const { contentEl } = this;
        contentEl.addClass('thoth-chat-modal');
        // Title
        contentEl.createEl('h2', { text: 'Thoth Research Chat' });
        // Chat history
        this.outputEl = contentEl.createDiv({ cls: 'thoth-chat-output' });
        this.loadChatHistory();
        // Input section
        const inputWrapper = contentEl.createDiv({ cls: 'thoth-chat-input-wrapper' });
        this.inputEl = inputWrapper.createEl('textarea', {
            cls: 'thoth-chat-input',
            attr: { placeholder: 'Ask Thoth about your research...' }
        });
        if (this.initialQuery) {
            this.inputEl.value = this.initialQuery;
        }
        this.sendButton = inputWrapper.createEl('button', {
            text: 'Send',
            cls: 'thoth-send-button'
        });
        this.sendButton.onclick = () => this.sendMessage();
        // Enter to send (Shift+Enter for new line)
        this.inputEl.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        // Focus on input
        this.inputEl.focus();
    }
    loadChatHistory() {
        const history = this.plugin.settings.chatHistory.slice(-10); // Show last 10 messages
        history.forEach(message => {
            this.addMessageToChat(message.role, message.content, new Date(message.timestamp));
        });
    }
    addMessageToChat(role, content, timestamp) {
        const messageEl = this.outputEl.createDiv({ cls: `thoth-message thoth-message-${role}` });
        const headerEl = messageEl.createDiv({ cls: 'thoth-message-header' });
        headerEl.createSpan({ text: role === 'user' ? 'You' : 'Thoth', cls: 'thoth-message-sender' });
        if (timestamp) {
            headerEl.createSpan({
                text: timestamp.toLocaleTimeString(),
                cls: 'thoth-message-time'
            });
        }
        messageEl.createDiv({ text: content, cls: 'thoth-message-content' });
        // Scroll to bottom
        this.outputEl.scrollTop = this.outputEl.scrollHeight;
    }
    sendMessage() {
        return __awaiter(this, void 0, void 0, function* () {
            const message = this.inputEl.value.trim();
            if (!message)
                return;
            if (!this.plugin.isAgentRunning) {
                new obsidian_1.Notice('Thoth agent is not running. Please start it first.');
                return;
            }
            // Add user message to chat
            this.addMessageToChat('user', message);
            // Save to history
            const userMessage = {
                role: 'user',
                content: message,
                timestamp: Date.now()
            };
            this.plugin.settings.chatHistory.push(userMessage);
            // Clear input
            this.inputEl.value = '';
            this.sendButton.disabled = true;
            this.sendButton.textContent = 'Sending...';
            try {
                // Send to agent (this would need to be implemented based on your agent's API)
                const response = yield this.sendToAgent(message);
                // Add response to chat
                this.addMessageToChat('assistant', response);
                // Save response to history
                const assistantMessage = {
                    role: 'assistant',
                    content: response,
                    timestamp: Date.now()
                };
                this.plugin.settings.chatHistory.push(assistantMessage);
                // Keep only last 100 messages
                if (this.plugin.settings.chatHistory.length > 100) {
                    this.plugin.settings.chatHistory = this.plugin.settings.chatHistory.slice(-100);
                }
                yield this.plugin.saveSettings();
            }
            catch (error) {
                console.error('Error sending message:', error);
                this.addMessageToChat('system', 'Error: Could not send message to Thoth agent');
            }
            finally {
                this.sendButton.disabled = false;
                this.sendButton.textContent = 'Send';
                this.inputEl.focus();
            }
        });
    }
    sendToAgent(message) {
        return __awaiter(this, void 0, void 0, function* () {
            if (!this.plugin.isAgentRunning) {
                throw new Error('Thoth agent is not running');
            }
            const apiUrl = `${this.plugin.settings.endpointBaseUrl}/research/chat`;
            try {
                const response = yield fetch(apiUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        message: message,
                        conversation_id: this.getConversationId(),
                        timestamp: Date.now(),
                    }),
                });
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                const data = yield response.json();
                return data.response || data.message || 'No response from agent';
            }
            catch (error) {
                console.error('Error communicating with Thoth agent:', error);
                // Fallback: try alternative endpoints or methods
                if (error instanceof TypeError && error.message.includes('fetch')) {
                    throw new Error('Unable to connect to Thoth agent. Is the endpoint running?');
                }
                throw new Error(`Failed to communicate with agent: ${error.message}`);
            }
        });
    }
    getConversationId() {
        // Generate or retrieve a conversation ID for this chat session
        if (!this.conversationId) {
            this.conversationId = `obsidian-${Date.now()}-${Math.random().toString(36).substring(2, 15)}`;
        }
        return this.conversationId;
    }
    onClose() {
        const { contentEl } = this;
        contentEl.empty();
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibWFpbi5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIm1haW4udHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7Ozs7Ozs7QUFBQSx1Q0FBaUY7QUFDakYsaURBQXNFO0FBZ0l0RSxNQUFNLGdCQUFnQixHQUF3QjtJQUM1QyxXQUFXO0lBQ1gsVUFBVSxFQUFFLEVBQUU7SUFDZCxhQUFhLEVBQUUsRUFBRTtJQUNqQixnQkFBZ0IsRUFBRSxFQUFFO0lBQ3BCLFlBQVksRUFBRSxFQUFFO0lBQ2hCLG9CQUFvQixFQUFFLEVBQUU7SUFDeEIscUJBQXFCLEVBQUUsRUFBRTtJQUV6Qix5QkFBeUI7SUFDekIsZ0JBQWdCLEVBQUUsR0FBRztJQUNyQixjQUFjLEVBQUUsS0FBSztJQUNyQixTQUFTLEVBQUUsR0FBRztJQUNkLHFCQUFxQixFQUFFLEdBQUc7SUFDMUIsb0JBQW9CLEVBQUUsR0FBRztJQUN6QixjQUFjLEVBQUUsS0FBSztJQUNyQixtQkFBbUIsRUFBRSxJQUFJO0lBRXpCLDRCQUE0QjtJQUM1QixRQUFRLEVBQUUsdUNBQXVDO0lBQ2pELGdCQUFnQixFQUFFLE1BQU07SUFDeEIsa0JBQWtCLEVBQUUsS0FBSztJQUN6QixtQkFBbUIsRUFBRSxPQUFPO0lBQzVCLFlBQVksRUFBRSxNQUFNO0lBQ3BCLGVBQWUsRUFBRSxLQUFLO0lBQ3RCLDRCQUE0QixFQUFFLElBQUk7SUFDbEMsK0JBQStCLEVBQUUsR0FBRztJQUVwQyw2QkFBNkI7SUFDN0IsZ0JBQWdCLEVBQUUsNEJBQTRCO0lBQzlDLDBCQUEwQixFQUFFLEtBQUs7SUFDakMsMkJBQTJCLEVBQUUsSUFBSTtJQUVqQyxxQ0FBcUM7SUFDckMsc0JBQXNCLEVBQUUsNEJBQTRCO0lBQ3BELGtCQUFrQixFQUFFLDRCQUE0QjtJQUNoRCxjQUFjLEVBQUUsd0JBQXdCO0lBQ3hDLHFCQUFxQixFQUFFLEtBQUs7SUFDNUIsc0JBQXNCLEVBQUUsSUFBSTtJQUU1QixvQ0FBb0M7SUFDcEMsa0JBQWtCLEVBQUUsS0FBSztJQUN6QixhQUFhLEVBQUUsTUFBTTtJQUNyQix3QkFBd0IsRUFBRSxJQUFJO0lBQzlCLG9CQUFvQixFQUFFLEtBQUs7SUFDM0IsMEJBQTBCLEVBQUUsSUFBSTtJQUNoQyxnQkFBZ0IsRUFBRSxJQUFJO0lBQ3RCLGlCQUFpQixFQUFFLENBQUM7SUFFcEIseUJBQXlCO0lBQ3pCLFlBQVksRUFBRSxXQUFXO0lBQ3pCLFlBQVksRUFBRSxNQUFNO0lBQ3BCLGVBQWUsRUFBRSx1QkFBdUI7SUFDeEMsaUJBQWlCLEVBQUUsS0FBSztJQUV4Qix3QkFBd0I7SUFDeEIsZ0JBQWdCLEVBQUUsS0FBSztJQUN2QixvQkFBb0IsRUFBRSxDQUFDO0lBQ3ZCLHNCQUFzQixFQUFFLEVBQUU7SUFFMUIsd0JBQXdCO0lBQ3hCLFFBQVEsRUFBRSxPQUFPO0lBQ2pCLFNBQVMsRUFBRSx1SEFBdUg7SUFDbEksYUFBYSxFQUFFLHFCQUFxQjtJQUNwQyxXQUFXLEVBQUUsZ0JBQWdCO0lBQzdCLFdBQVcsRUFBRSxHQUFHO0lBQ2hCLFlBQVksRUFBRSxPQUFPO0lBRXJCLGlDQUFpQztJQUNqQyxZQUFZLEVBQUUsaUNBQWlDO0lBQy9DLFdBQVcsRUFBRSxtREFBbUQ7SUFDaEUsTUFBTSxFQUFFLDZCQUE2QjtJQUNyQyxXQUFXLEVBQUUscUNBQXFDO0lBQ2xELFFBQVEsRUFBRSxpQkFBaUI7SUFDM0IsVUFBVSxFQUFFLG9DQUFvQztJQUNoRCxZQUFZLEVBQUUsNEJBQTRCO0lBQzFDLFNBQVMsRUFBRSw0QkFBNEI7SUFDdkMsZ0JBQWdCLEVBQUUsNEJBQTRCO0lBQzlDLGdCQUFnQixFQUFFLG9EQUFvRDtJQUN0RSxlQUFlLEVBQUUsa0NBQWtDO0lBQ25ELFVBQVUsRUFBRSw4QkFBOEI7SUFFMUMsK0JBQStCO0lBQy9CLHNCQUFzQixFQUFFLEtBQUs7SUFDN0IsMkJBQTJCLEVBQUUsSUFBSTtJQUVqQyxtQ0FBbUM7SUFDbkMscUJBQXFCLEVBQUUsdUNBQXVDO0lBQzlELHFDQUFxQyxFQUFFLElBQUk7SUFDM0MsMkNBQTJDLEVBQUUsSUFBSTtJQUNqRCxnREFBZ0QsRUFBRSxJQUFJO0lBQ3RELCtCQUErQixFQUFFLEtBQUs7SUFDdEMsZ0NBQWdDLEVBQUUsTUFBTTtJQUV4QyxrQ0FBa0M7SUFDbEMsb0JBQW9CLEVBQUUsdUNBQXVDO0lBQzdELDhCQUE4QixFQUFFLEtBQUs7SUFDckMsK0JBQStCLEVBQUUsS0FBSztJQUV0QyxpQ0FBaUM7SUFDakMsMkJBQTJCLEVBQUUsS0FBSztJQUNsQywyQkFBMkIsRUFBRSxFQUFFO0lBQy9CLCtCQUErQixFQUFFLEVBQUU7SUFDbkMsdUJBQXVCLEVBQUUsR0FBRztJQUM1QiwrQkFBK0IsRUFBRSxJQUFJO0lBQ3JDLDRCQUE0QixFQUFFLElBQUk7SUFDbEMsbUJBQW1CLEVBQUUsd0NBQXdDO0lBQzdELG1CQUFtQixFQUFFLHdDQUF3QztJQUM3RCx5QkFBeUIsRUFBRSwrQ0FBK0M7SUFFMUUsMkJBQTJCO0lBQzNCLGNBQWMsRUFBRSxLQUFLO0lBQ3JCLGFBQWEsRUFBRSxJQUFJO0lBQ25CLFdBQVcsRUFBRSxFQUFFO0lBRWYsNkJBQTZCO0lBQzdCLFVBQVUsRUFBRSxLQUFLO0lBQ2pCLGlCQUFpQixFQUFFLEVBQUU7Q0FDdEIsQ0FBQztBQUVGLE1BQXFCLFdBQVksU0FBUSxpQkFBTTtJQUEvQzs7UUFFRSxZQUFPLEdBQTBDLElBQUksQ0FBQztRQUN0RCxrQkFBYSxHQUF1QixJQUFJLENBQUM7UUFDekMsbUJBQWMsR0FBRyxLQUFLLENBQUM7SUEycEJ6QixDQUFDO0lBenBCTyxNQUFNOztZQUNWLE1BQU0sSUFBSSxDQUFDLFlBQVksRUFBRSxDQUFDO1lBRTFCLHNCQUFzQjtZQUN0QixJQUFJLElBQUksQ0FBQyxRQUFRLENBQUMsYUFBYSxFQUFFLENBQUM7Z0JBQ2hDLElBQUksQ0FBQyxhQUFhLEdBQUcsSUFBSSxDQUFDLGdCQUFnQixFQUFFLENBQUM7Z0JBQzdDLElBQUksQ0FBQyxlQUFlLEVBQUUsQ0FBQztZQUN6QixDQUFDO1lBRUQsbUJBQW1CO1lBQ25CLElBQUksQ0FBQyxhQUFhLENBQUMsSUFBSSxlQUFlLENBQUMsSUFBSSxDQUFDLEdBQUcsRUFBRSxJQUFJLENBQUMsQ0FBQyxDQUFDO1lBRXhELGVBQWU7WUFDZixJQUFJLENBQUMsVUFBVSxDQUFDO2dCQUNkLEVBQUUsRUFBRSxtQkFBbUI7Z0JBQ3ZCLElBQUksRUFBRSxtQkFBbUI7Z0JBQ3pCLElBQUksRUFBRSxNQUFNO2dCQUNaLFFBQVEsRUFBRSxHQUFHLEVBQUUsQ0FBQyxJQUFJLENBQUMsVUFBVSxFQUFFO2FBQ2xDLENBQUMsQ0FBQztZQUVILElBQUksQ0FBQyxVQUFVLENBQUM7Z0JBQ2QsRUFBRSxFQUFFLGtCQUFrQjtnQkFDdEIsSUFBSSxFQUFFLGtCQUFrQjtnQkFDeEIsSUFBSSxFQUFFLE1BQU07Z0JBQ1osUUFBUSxFQUFFLEdBQUcsRUFBRSxDQUFDLElBQUksQ0FBQyxTQUFTLEVBQUU7YUFDakMsQ0FBQyxDQUFDO1lBRUgsSUFBSSxDQUFDLFVBQVUsQ0FBQztnQkFDZCxFQUFFLEVBQUUscUJBQXFCO2dCQUN6QixJQUFJLEVBQUUscUJBQXFCO2dCQUMzQixJQUFJLEVBQUUsWUFBWTtnQkFDbEIsUUFBUSxFQUFFLEdBQUcsRUFBRSxDQUFDLElBQUksQ0FBQyxZQUFZLEVBQUU7YUFDcEMsQ0FBQyxDQUFDO1lBRUgsSUFBSSxDQUFDLFVBQVUsQ0FBQztnQkFDZCxFQUFFLEVBQUUsaUJBQWlCO2dCQUNyQixJQUFJLEVBQUUsb0JBQW9CO2dCQUMxQixJQUFJLEVBQUUsZ0JBQWdCO2dCQUN0QixRQUFRLEVBQUUsR0FBRyxFQUFFLENBQUMsSUFBSSxDQUFDLFFBQVEsRUFBRTthQUNoQyxDQUFDLENBQUM7WUFFSCxJQUFJLENBQUMsVUFBVSxDQUFDO2dCQUNkLEVBQUUsRUFBRSx1QkFBdUI7Z0JBQzNCLElBQUksRUFBRSx1QkFBdUI7Z0JBQzdCLElBQUksRUFBRSxRQUFRO2dCQUNkLGNBQWMsRUFBRSxDQUFDLE1BQU0sRUFBRSxFQUFFO29CQUN6QixNQUFNLFNBQVMsR0FBRyxNQUFNLENBQUMsWUFBWSxFQUFFLENBQUM7b0JBQ3hDLElBQUksU0FBUyxFQUFFLENBQUM7d0JBQ2QsSUFBSSxDQUFDLGVBQWUsQ0FBQyxTQUFTLENBQUMsQ0FBQztvQkFDbEMsQ0FBQzt5QkFBTSxDQUFDO3dCQUNOLElBQUksaUJBQU0sQ0FBQyxnQ0FBZ0MsQ0FBQyxDQUFDO29CQUMvQyxDQUFDO2dCQUNILENBQUM7YUFDRixDQUFDLENBQUM7WUFFSCw4QkFBOEI7WUFDOUIsSUFBSSxJQUFJLENBQUMsUUFBUSxDQUFDLGNBQWMsRUFBRSxDQUFDO2dCQUNqQyxVQUFVLENBQUMsR0FBRyxFQUFFLENBQUMsSUFBSSxDQUFDLFVBQVUsRUFBRSxFQUFFLElBQUksQ0FBQyxDQUFDO1lBQzVDLENBQUM7UUFDSCxDQUFDO0tBQUE7SUFFRCxRQUFRO1FBQ04sSUFBSSxDQUFDLFNBQVMsRUFBRSxDQUFDO0lBQ25CLENBQUM7SUFFSyxZQUFZOztZQUNoQixJQUFJLENBQUMsUUFBUSxHQUFHLE1BQU0sQ0FBQyxNQUFNLENBQUMsRUFBRSxFQUFFLGdCQUFnQixFQUFFLE1BQU0sSUFBSSxDQUFDLFFBQVEsRUFBRSxDQUFDLENBQUM7UUFDN0UsQ0FBQztLQUFBO0lBRUssWUFBWTs7WUFDaEIsTUFBTSxJQUFJLENBQUMsUUFBUSxDQUFDLElBQUksQ0FBQyxRQUFRLENBQUMsQ0FBQztZQUNuQyxNQUFNLElBQUksQ0FBQyxxQkFBcUIsRUFBRSxDQUFDO1FBQ3JDLENBQUM7S0FBQTtJQUVlLHFCQUFxQjs7WUFDbkMsSUFBSSxDQUFDO2dCQUNILHFEQUFxRDtnQkFDdkQsTUFBTSxLQUFLLEdBQUc7b0JBQ1YseUNBQXlDO29CQUN6QyxnQ0FBZ0M7b0JBQ2hDLEVBQUU7b0JBQ0Ysc0ZBQXNGO29CQUN0Rix1QkFBdUI7b0JBQ3ZCLHNGQUFzRjtvQkFDeEYsbUJBQW1CLElBQUksQ0FBQyxRQUFRLENBQUMsVUFBVSxFQUFFO29CQUM3QyxzQkFBc0IsSUFBSSxDQUFDLFFBQVEsQ0FBQyxhQUFhLEVBQUU7b0JBQ2pELHlCQUF5QixJQUFJLENBQUMsUUFBUSxDQUFDLGdCQUFnQixFQUFFO29CQUN6RCxzQkFBc0IsSUFBSSxDQUFDLFFBQVEsQ0FBQyxZQUFZLEVBQUU7b0JBQ2xELCtCQUErQixJQUFJLENBQUMsUUFBUSxDQUFDLG9CQUFvQixFQUFFO29CQUNuRSwrQkFBK0IsSUFBSSxDQUFDLFFBQVEsQ0FBQyxxQkFBcUIsRUFBRTtvQkFDcEUsRUFBRTtvQkFDRixzRkFBc0Y7b0JBQ3RGLHFDQUFxQztvQkFDckMsc0ZBQXNGO29CQUN0RixxQkFBcUIsSUFBSSxDQUFDLFFBQVEsQ0FBQyxnQkFBZ0IsRUFBRTtvQkFDckQsb0JBQW9CLElBQUksQ0FBQyxRQUFRLENBQUMsY0FBYyxFQUFFO29CQUNsRCxlQUFlLElBQUksQ0FBQyxRQUFRLENBQUMsU0FBUyxFQUFFO29CQUN4QywyQkFBMkIsSUFBSSxDQUFDLFFBQVEsQ0FBQyxxQkFBcUIsRUFBRTtvQkFDaEUsMEJBQTBCLElBQUksQ0FBQyxRQUFRLENBQUMsb0JBQW9CLEVBQUU7b0JBQzlELG1CQUFtQixJQUFJLENBQUMsUUFBUSxDQUFDLGNBQWMsRUFBRTtvQkFDakQsMEJBQTBCLElBQUksQ0FBQyxRQUFRLENBQUMsbUJBQW1CLEVBQUU7b0JBQzdELEVBQUU7b0JBQ0Ysc0ZBQXNGO29CQUN0Rix3Q0FBd0M7b0JBQ3hDLHNGQUFzRjtvQkFDdEYsYUFBYSxJQUFJLENBQUMsUUFBUSxDQUFDLFFBQVEsRUFBRTtvQkFDckMsc0JBQXNCLElBQUksQ0FBQyxRQUFRLENBQUMsZ0JBQWdCLEVBQUU7b0JBQ3RELHlCQUF5QixJQUFJLENBQUMsUUFBUSxDQUFDLGtCQUFrQixFQUFFO29CQUMzRCwwQkFBMEIsSUFBSSxDQUFDLFFBQVEsQ0FBQyxtQkFBbUIsRUFBRTtvQkFDN0Qsa0JBQWtCLElBQUksQ0FBQyxRQUFRLENBQUMsWUFBWSxFQUFFO29CQUM5QyxxQkFBcUIsSUFBSSxDQUFDLFFBQVEsQ0FBQyxlQUFlLEVBQUU7b0JBQ3BELG1DQUFtQyxJQUFJLENBQUMsUUFBUSxDQUFDLDRCQUE0QixFQUFFO29CQUMvRSx1Q0FBdUMsSUFBSSxDQUFDLFFBQVEsQ0FBQywrQkFBK0IsRUFBRTtvQkFDdEYsRUFBRTtvQkFDRixzRkFBc0Y7b0JBQ3RGLHlDQUF5QztvQkFDekMsc0ZBQXNGO29CQUN0RixzQkFBc0IsSUFBSSxDQUFDLFFBQVEsQ0FBQyxnQkFBZ0IsRUFBRTtvQkFDdEQsa0NBQWtDLElBQUksQ0FBQyxRQUFRLENBQUMsMEJBQTBCLEVBQUU7b0JBQzVFLG1DQUFtQyxJQUFJLENBQUMsUUFBUSxDQUFDLDJCQUEyQixFQUFFO29CQUM5RSxFQUFFO29CQUNGLHNGQUFzRjtvQkFDdEYsbURBQW1EO29CQUNuRCxzRkFBc0Y7b0JBQ3RGLDZCQUE2QixJQUFJLENBQUMsUUFBUSxDQUFDLHNCQUFzQixFQUFFO29CQUNuRSx5QkFBeUIsSUFBSSxDQUFDLFFBQVEsQ0FBQyxrQkFBa0IsRUFBRTtvQkFDM0QscUJBQXFCLElBQUksQ0FBQyxRQUFRLENBQUMsY0FBYyxFQUFFO29CQUNuRCw2QkFBNkIsSUFBSSxDQUFDLFFBQVEsQ0FBQyxxQkFBcUIsRUFBRTtvQkFDbEUsOEJBQThCLElBQUksQ0FBQyxRQUFRLENBQUMsc0JBQXNCLEVBQUU7b0JBQ3BFLEVBQUU7b0JBQ0Ysc0ZBQXNGO29CQUN0RixnREFBZ0Q7b0JBQ2hELHNGQUFzRjtvQkFDdEYsd0JBQXdCLElBQUksQ0FBQyxRQUFRLENBQUMsa0JBQWtCLEVBQUU7b0JBQzFELGtCQUFrQixJQUFJLENBQUMsUUFBUSxDQUFDLGFBQWEsRUFBRTtvQkFDL0MsOEJBQThCLElBQUksQ0FBQyxRQUFRLENBQUMsd0JBQXdCLEVBQUU7b0JBQ3RFLDBCQUEwQixJQUFJLENBQUMsUUFBUSxDQUFDLG9CQUFvQixFQUFFO29CQUM5RCxnQ0FBZ0MsSUFBSSxDQUFDLFFBQVEsQ0FBQywwQkFBMEIsRUFBRTtvQkFDMUUsc0JBQXNCLElBQUksQ0FBQyxRQUFRLENBQUMsZ0JBQWdCLEVBQUU7b0JBQ3RELGdDQUFnQyxJQUFJLENBQUMsUUFBUSxDQUFDLGlCQUFpQixFQUFFO29CQUNqRSxFQUFFO29CQUNGLHNGQUFzRjtvQkFDdEYscUNBQXFDO29CQUNyQyxzRkFBc0Y7b0JBQ3hGLGlCQUFpQixJQUFJLENBQUMsUUFBUSxDQUFDLFlBQVksRUFBRTtvQkFDN0MsaUJBQWlCLElBQUksQ0FBQyxRQUFRLENBQUMsWUFBWSxFQUFFO29CQUMzQyxxQkFBcUIsSUFBSSxDQUFDLFFBQVEsQ0FBQyxlQUFlLEVBQUU7b0JBQ3BELHVCQUF1QixJQUFJLENBQUMsUUFBUSxDQUFDLGlCQUFpQixFQUFFO29CQUN4RCxFQUFFO29CQUNGLHNGQUFzRjtvQkFDdEYsb0NBQW9DO29CQUNwQyxzRkFBc0Y7b0JBQ3RGLHNCQUFzQixJQUFJLENBQUMsUUFBUSxDQUFDLGdCQUFnQixFQUFFO29CQUN0RCwwQkFBMEIsSUFBSSxDQUFDLFFBQVEsQ0FBQyxvQkFBb0IsRUFBRTtvQkFDOUQsNkJBQTZCLElBQUksQ0FBQyxRQUFRLENBQUMsc0JBQXNCLEVBQUU7b0JBQ25FLEVBQUU7b0JBQ0Ysc0ZBQXNGO29CQUN0RixvQ0FBb0M7b0JBQ3BDLHNGQUFzRjtvQkFDdEYsYUFBYSxJQUFJLENBQUMsUUFBUSxDQUFDLFFBQVEsRUFBRTtvQkFDckMsa0JBQWtCLElBQUksQ0FBQyxRQUFRLENBQUMsU0FBUyxHQUFHO29CQUM1QyxtQkFBbUIsSUFBSSxDQUFDLFFBQVEsQ0FBQyxhQUFhLEdBQUc7b0JBQ2pELGdCQUFnQixJQUFJLENBQUMsUUFBUSxDQUFDLFdBQVcsRUFBRTtvQkFDM0MsZ0JBQWdCLElBQUksQ0FBQyxRQUFRLENBQUMsV0FBVyxFQUFFO29CQUMzQyxrQkFBa0IsSUFBSSxDQUFDLFFBQVEsQ0FBQyxZQUFZLEVBQUU7b0JBQzlDLEVBQUU7b0JBQ0Ysc0ZBQXNGO29CQUN0Riw2Q0FBNkM7b0JBQzdDLHNGQUFzRjtvQkFDdEYsaUJBQWlCLElBQUksQ0FBQyxRQUFRLENBQUMsWUFBWSxFQUFFO29CQUM3QyxnQkFBZ0IsSUFBSSxDQUFDLFFBQVEsQ0FBQyxXQUFXLEVBQUU7b0JBQzNDLFdBQVcsSUFBSSxDQUFDLFFBQVEsQ0FBQyxNQUFNLEVBQUU7b0JBQ2pDLGdCQUFnQixJQUFJLENBQUMsUUFBUSxDQUFDLFdBQVcsRUFBRTtvQkFDM0MsYUFBYSxJQUFJLENBQUMsUUFBUSxDQUFDLFFBQVEsRUFBRTtvQkFDckMsZUFBZSxJQUFJLENBQUMsUUFBUSxDQUFDLFVBQVUsRUFBRTtvQkFDekMsaUJBQWlCLElBQUksQ0FBQyxRQUFRLENBQUMsWUFBWSxFQUFFO29CQUM3QyxjQUFjLElBQUksQ0FBQyxRQUFRLENBQUMsU0FBUyxFQUFFO29CQUN2QyxzQkFBc0IsSUFBSSxDQUFDLFFBQVEsQ0FBQyxnQkFBZ0IsRUFBRTtvQkFDdEQsc0JBQXNCLElBQUksQ0FBQyxRQUFRLENBQUMsZ0JBQWdCLEVBQUU7b0JBQ3RELHFCQUFxQixJQUFJLENBQUMsUUFBUSxDQUFDLGVBQWUsRUFBRTtvQkFDcEQsZUFBZSxJQUFJLENBQUMsUUFBUSxDQUFDLFVBQVUsRUFBRTtvQkFDekMsRUFBRTtvQkFDRiwyQkFBMkI7b0JBQzNCLDZCQUE2QixJQUFJLENBQUMsUUFBUSxDQUFDLHNCQUFzQixFQUFFO29CQUNuRSxrQ0FBa0MsSUFBSSxDQUFDLFFBQVEsQ0FBQywyQkFBMkIsRUFBRTtvQkFDN0UsRUFBRTtvQkFDRixzRkFBc0Y7b0JBQ3RGLGdEQUFnRDtvQkFDaEQsc0ZBQXNGO29CQUN0Riw0QkFBNEIsSUFBSSxDQUFDLFFBQVEsQ0FBQyxxQkFBcUIsRUFBRTtvQkFDakUsK0NBQStDLElBQUksQ0FBQyxRQUFRLENBQUMscUNBQXFDLEVBQUU7b0JBQ3BHLHNEQUFzRCxJQUFJLENBQUMsUUFBUSxDQUFDLDJDQUEyQyxFQUFFO29CQUNqSCwyREFBMkQsSUFBSSxDQUFDLFFBQVEsQ0FBQyxnREFBZ0QsRUFBRTtvQkFDM0gsd0NBQXdDLElBQUksQ0FBQyxRQUFRLENBQUMsK0JBQStCLEVBQUU7b0JBQ3ZGLHlDQUF5QyxJQUFJLENBQUMsUUFBUSxDQUFDLGdDQUFnQyxFQUFFO29CQUN6RixFQUFFO29CQUNGLHNGQUFzRjtvQkFDdEYsK0NBQStDO29CQUMvQyxzRkFBc0Y7b0JBQ3RGLDJCQUEyQixJQUFJLENBQUMsUUFBUSxDQUFDLG9CQUFvQixFQUFFO29CQUMvRCx1Q0FBdUMsSUFBSSxDQUFDLFFBQVEsQ0FBQyw4QkFBOEIsRUFBRTtvQkFDckYsd0NBQXdDLElBQUksQ0FBQyxRQUFRLENBQUMsK0JBQStCLEVBQUU7b0JBQ3ZGLEVBQUU7b0JBQ0Ysc0ZBQXNGO29CQUN0Riw4Q0FBOEM7b0JBQzlDLHNGQUFzRjtvQkFDdEYsa0NBQWtDLElBQUksQ0FBQyxRQUFRLENBQUMsMkJBQTJCLEVBQUU7b0JBQzdFLGtDQUFrQyxJQUFJLENBQUMsUUFBUSxDQUFDLDJCQUEyQixFQUFFO29CQUM3RSxzQ0FBc0MsSUFBSSxDQUFDLFFBQVEsQ0FBQywrQkFBK0IsRUFBRTtvQkFDckYsOEJBQThCLElBQUksQ0FBQyxRQUFRLENBQUMsdUJBQXVCLEVBQUU7b0JBQ3JFLHNDQUFzQyxJQUFJLENBQUMsUUFBUSxDQUFDLCtCQUErQixFQUFFO29CQUNyRixtQ0FBbUMsSUFBSSxDQUFDLFFBQVEsQ0FBQyw0QkFBNEIsRUFBRTtvQkFDL0UsRUFBRTtvQkFDRiw2QkFBNkI7b0JBQzdCLHlCQUF5QixJQUFJLENBQUMsUUFBUSxDQUFDLG1CQUFtQixFQUFFO29CQUM1RCx5QkFBeUIsSUFBSSxDQUFDLFFBQVEsQ0FBQyxtQkFBbUIsRUFBRTtvQkFDNUQsZ0NBQWdDLElBQUksQ0FBQyxRQUFRLENBQUMseUJBQXlCLEVBQUU7aUJBQzFFLENBQUM7Z0JBRUYsK0VBQStFO2dCQUMvRSxJQUFJLENBQUM7b0JBQ0gseURBQXlEO29CQUN6RCxJQUFJLElBQUksQ0FBQyxRQUFRLENBQUMsWUFBWSxJQUFJLE9BQU8sQ0FBQyxJQUFJLENBQUMsQ0FBQyxVQUFVLENBQUMsSUFBSSxDQUFDLFFBQVEsQ0FBQyxZQUFZLENBQUMsRUFBRSxDQUFDO3dCQUN2RixNQUFNLElBQUksR0FBRyxPQUFPLENBQUMsTUFBTSxDQUFDLENBQUM7d0JBQzdCLE1BQU0sRUFBRSxHQUFHLE9BQU8sQ0FBQyxJQUFJLENBQUMsQ0FBQzt3QkFDekIsTUFBTSxPQUFPLEdBQUcsSUFBSSxDQUFDLElBQUksQ0FBQyxJQUFJLENBQUMsUUFBUSxDQUFDLFlBQVksRUFBRSxNQUFNLENBQUMsQ0FBQzt3QkFDOUQsRUFBRSxDQUFDLGFBQWEsQ0FBQyxPQUFPLEVBQUUsS0FBSyxDQUFDLElBQUksQ0FBQyxJQUFJLENBQUMsQ0FBQyxDQUFDO3dCQUM1QyxJQUFJLGlCQUFNLENBQUMsb0RBQW9ELENBQUMsQ0FBQzt3QkFDakUsT0FBTztvQkFDVCxDQUFDO2dCQUNILENBQUM7Z0JBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztvQkFDWCxPQUFPLENBQUMsSUFBSSxDQUFDLHlDQUF5QyxFQUFFLENBQUMsQ0FBQyxDQUFDO2dCQUM3RCxDQUFDO2dCQUVELGdEQUFnRDtnQkFDaEQsSUFBSSxDQUFDO29CQUNILE1BQU0sSUFBSSxDQUFDLEdBQUcsQ0FBQyxLQUFLLENBQUMsT0FBTyxDQUFDLEtBQUssQ0FBQyxNQUFNLEVBQUUsS0FBSyxDQUFDLElBQUksQ0FBQyxJQUFJLENBQUMsQ0FBQyxDQUFDO29CQUM3RCxJQUFJLGlCQUFNLENBQUMsaURBQWlELENBQUMsQ0FBQztnQkFDaEUsQ0FBQztnQkFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO29CQUNYLE9BQU8sQ0FBQyxLQUFLLENBQUMsMkJBQTJCLEVBQUUsQ0FBQyxDQUFDLENBQUM7b0JBQzlDLElBQUksaUJBQU0sQ0FBQyw0Q0FBNEMsQ0FBQyxDQUFDO2dCQUMzRCxDQUFDO1lBQ0gsQ0FBQztZQUFDLE9BQU8sS0FBSyxFQUFFLENBQUM7Z0JBQ2YsT0FBTyxDQUFDLEtBQUssQ0FBQyxvQ0FBb0MsRUFBRSxLQUFLLENBQUMsQ0FBQztnQkFDM0QsSUFBSSxpQkFBTSxDQUFDLDRDQUE0QyxDQUFDLENBQUM7WUFDM0QsQ0FBQztRQUNILENBQUM7S0FBQTtJQUVDLGVBQWU7UUFDZixJQUFJLENBQUMsSUFBSSxDQUFDLGFBQWE7WUFBRSxPQUFPO1FBRWhDLElBQUksSUFBSSxDQUFDLGNBQWMsRUFBRSxDQUFDO1lBQ3hCLDRCQUE0QjtZQUM1QixJQUFJLENBQUMsZ0JBQWdCLEVBQUUsQ0FBQyxJQUFJLENBQUMsQ0FBQyxPQUFPLEVBQUUsRUFBRTtnQkFDdkMsTUFBTSxNQUFNLEdBQUcsT0FBTyxDQUFDLENBQUMsQ0FBQyxTQUFTLENBQUMsQ0FBQyxDQUFDLE9BQU8sQ0FBQztnQkFDN0MsTUFBTSxLQUFLLEdBQUcsT0FBTyxDQUFDLENBQUMsQ0FBQyxTQUFTLENBQUMsQ0FBQyxDQUFDLFNBQVMsQ0FBQztnQkFFOUMsSUFBSSxDQUFDLGFBQWMsQ0FBQyxTQUFTLEdBQUcsdUJBQXVCLEtBQUssWUFBWSxNQUFNLFNBQVMsQ0FBQztnQkFDeEYsSUFBSSxDQUFDLGFBQWMsQ0FBQyxLQUFLLEdBQUcsT0FBTztvQkFDakMsQ0FBQyxDQUFDLG9EQUFvRDtvQkFDdEQsQ0FBQyxDQUFDLDZFQUE2RSxDQUFDO1lBQ3BGLENBQUMsQ0FBQyxDQUFDLEtBQUssQ0FBQyxHQUFHLEVBQUU7Z0JBQ1osSUFBSSxDQUFDLGFBQWMsQ0FBQyxTQUFTLEdBQUcsd0RBQXdELENBQUM7WUFDM0YsQ0FBQyxDQUFDLENBQUM7UUFDTCxDQUFDO2FBQU0sQ0FBQztZQUNOLElBQUksQ0FBQyxhQUFhLENBQUMsU0FBUyxHQUFHLG9EQUFvRCxDQUFDO1lBQ3BGLElBQUksQ0FBQyxhQUFhLENBQUMsS0FBSyxHQUFHLHlDQUF5QyxDQUFDO1FBQ3ZFLENBQUM7UUFFRCxJQUFJLENBQUMsYUFBYSxDQUFDLE9BQU8sR0FBRyxHQUFHLEVBQUU7WUFDaEMsSUFBSSxJQUFJLENBQUMsY0FBYyxFQUFFLENBQUM7Z0JBQ3hCLElBQUksQ0FBQyxTQUFTLEVBQUUsQ0FBQztZQUNuQixDQUFDO2lCQUFNLENBQUM7Z0JBQ04sSUFBSSxDQUFDLFVBQVUsRUFBRSxDQUFDO1lBQ3BCLENBQUM7UUFDSCxDQUFDLENBQUM7SUFDSixDQUFDO0lBRUssVUFBVTs7WUFDZCxJQUFJLElBQUksQ0FBQyxPQUFPLElBQUksQ0FBQyxJQUFJLENBQUMsUUFBUSxDQUFDLFVBQVUsRUFBRSxDQUFDO2dCQUM5QyxJQUFJLGlCQUFNLENBQUMsZ0NBQWdDLENBQUMsQ0FBQztnQkFDN0MsT0FBTztZQUNULENBQUM7WUFFRCwwQkFBMEI7WUFDMUIsSUFBSSxDQUFDLElBQUksQ0FBQyxRQUFRLENBQUMsVUFBVSxJQUFJLENBQUMsSUFBSSxDQUFDLFFBQVEsQ0FBQyxhQUFhLEVBQUUsQ0FBQztnQkFDOUQsSUFBSSxpQkFBTSxDQUFDLDZDQUE2QyxDQUFDLENBQUM7Z0JBQzFELE9BQU87WUFDVCxDQUFDO1lBRUQsa0RBQWtEO1lBQ2xELElBQUksSUFBSSxDQUFDLFFBQVEsQ0FBQyxVQUFVLEVBQUUsQ0FBQztnQkFDN0IsSUFBSSxDQUFDLElBQUksQ0FBQyxRQUFRLENBQUMsaUJBQWlCLEVBQUUsQ0FBQztvQkFDckMsSUFBSSxpQkFBTSxDQUFDLGtEQUFrRCxDQUFDLENBQUM7b0JBQy9ELE9BQU87Z0JBQ1QsQ0FBQztnQkFFRCxJQUFJLGlCQUFNLENBQUMsc0NBQXNDLENBQUMsQ0FBQztnQkFFbkQsSUFBSSxDQUFDO29CQUNILG1DQUFtQztvQkFDbkMsTUFBTSxVQUFVLEdBQUcsSUFBSSxlQUFlLEVBQUUsQ0FBQztvQkFDekMsTUFBTSxTQUFTLEdBQUcsVUFBVSxDQUFDLEdBQUcsRUFBRSxDQUFDLFVBQVUsQ0FBQyxLQUFLLEVBQUUsRUFBRSxJQUFJLENBQUMsQ0FBQztvQkFFN0QsTUFBTSxRQUFRLEdBQUcsTUFBTSxLQUFLLENBQUMsR0FBRyxJQUFJLENBQUMsUUFBUSxDQUFDLGlCQUFpQixTQUFTLEVBQUU7d0JBQ3hFLE1BQU0sRUFBRSxLQUFLO3dCQUNiLE1BQU0sRUFBRSxVQUFVLENBQUMsTUFBTTtxQkFDMUIsQ0FBQyxDQUFDO29CQUVILFlBQVksQ0FBQyxTQUFTLENBQUMsQ0FBQztvQkFFeEIsSUFBSSxDQUFDLFFBQVEsQ0FBQyxFQUFFLEVBQUUsQ0FBQzt3QkFDakIsTUFBTSxJQUFJLEtBQUssQ0FBQyx5QkFBeUIsUUFBUSxDQUFDLE1BQU0sRUFBRSxDQUFDLENBQUM7b0JBQzlELENBQUM7b0JBRUQseUNBQXlDO29CQUN6QyxJQUFJLENBQUMsUUFBUSxDQUFDLGVBQWUsR0FBRyxJQUFJLENBQUMsUUFBUSxDQUFDLGlCQUFpQixDQUFDO29CQUNoRSxNQUFNLElBQUksQ0FBQyxZQUFZLEVBQUUsQ0FBQztvQkFFMUIsSUFBSSxDQUFDLGNBQWMsR0FBRyxJQUFJLENBQUM7b0JBQzNCLElBQUksQ0FBQyxlQUFlLEVBQUUsQ0FBQztvQkFDdkIsSUFBSSxpQkFBTSxDQUFDLGdEQUFnRCxDQUFDLENBQUM7b0JBRTdELHlDQUF5QztvQkFDekMsVUFBVSxDQUFDLEdBQVMsRUFBRTt3QkFDcEIsTUFBTSxPQUFPLEdBQUcsTUFBTSxJQUFJLENBQUMsZ0JBQWdCLEVBQUUsQ0FBQzt3QkFDOUMsSUFBSSxDQUFDLE9BQU8sRUFBRSxDQUFDOzRCQUNiLElBQUksaUJBQU0sQ0FBQyxvRkFBb0YsQ0FBQyxDQUFDO3dCQUNuRyxDQUFDO29CQUNILENBQUMsQ0FBQSxFQUFFLElBQUksQ0FBQyxDQUFDO29CQUVULE9BQU87Z0JBRVQsQ0FBQztnQkFBQyxPQUFPLEtBQUssRUFBRSxDQUFDO29CQUNmLE9BQU8sQ0FBQyxLQUFLLENBQUMscUNBQXFDLEVBQUUsS0FBSyxDQUFDLENBQUM7b0JBQzVELElBQUksaUJBQU0sQ0FBQyx1Q0FBdUMsS0FBSyxDQUFDLE9BQU8sRUFBRSxDQUFDLENBQUM7b0JBQ25FLE9BQU87Z0JBQ1QsQ0FBQztZQUNILENBQUM7WUFFRCxtQ0FBbUM7WUFDbkMsSUFBSSxJQUFJLENBQUMsT0FBTyxFQUFFLENBQUM7Z0JBQ2pCLElBQUksaUJBQU0sQ0FBQyxnQ0FBZ0MsQ0FBQyxDQUFDO2dCQUM3QyxPQUFPO1lBQ1QsQ0FBQztZQUVELHVEQUF1RDtZQUN2RCxJQUFJLENBQUM7Z0JBQ0gsTUFBTSxJQUFJLENBQUMscUJBQXFCLEVBQUUsQ0FBQztnQkFDbkMsSUFBSSxpQkFBTSxDQUFDLGdEQUFnRCxDQUFDLENBQUM7WUFDL0QsQ0FBQztZQUFDLE9BQU8sS0FBSyxFQUFFLENBQUM7Z0JBQ2YsT0FBTyxDQUFDLEtBQUssQ0FBQyxvQ0FBb0MsRUFBRSxLQUFLLENBQUMsQ0FBQztnQkFDM0QsSUFBSSxpQkFBTSxDQUFDLDhDQUE4QyxDQUFDLENBQUM7WUFDN0QsQ0FBQztZQUVELElBQUksQ0FBQztnQkFDTCxNQUFNLEdBQUcsR0FBRyxJQUFJLENBQUM7Z0JBQ2pCLE1BQU0sSUFBSSxHQUFHO29CQUNYLEtBQUs7b0JBQ0wsUUFBUTtvQkFDUixJQUFJO29CQUNKLE9BQU87b0JBQ1AsS0FBSztvQkFDTCxRQUFRLEVBQUUsSUFBSSxDQUFDLFFBQVEsQ0FBQyxZQUFZO29CQUNwQyxRQUFRLEVBQUUsSUFBSSxDQUFDLFFBQVEsQ0FBQyxZQUFZO29CQUNwQyxZQUFZLEVBQUUsSUFBSSxDQUFDLFFBQVEsQ0FBQyxlQUFlO2lCQUM1QyxDQUFDO2dCQUVGLGtEQUFrRDtnQkFDbEQsTUFBTSxPQUFPLG1DQUNSLE9BQU8sQ0FBQyxHQUFHO29CQUNkLFdBQVc7b0JBQ1gsZUFBZSxFQUFFLElBQUksQ0FBQyxRQUFRLENBQUMsVUFBVSxFQUN6QyxrQkFBa0IsRUFBRSxJQUFJLENBQUMsUUFBUSxDQUFDLGFBQWEsRUFDL0MscUJBQXFCLEVBQUUsSUFBSSxDQUFDLFFBQVEsQ0FBQyxnQkFBZ0IsRUFDckQsa0JBQWtCLEVBQUUsSUFBSSxDQUFDLFFBQVEsQ0FBQyxZQUFZLEVBQzlDLDJCQUEyQixFQUFFLElBQUksQ0FBQyxRQUFRLENBQUMsb0JBQW9CLEVBQy9ELDJCQUEyQixFQUFFLElBQUksQ0FBQyxRQUFRLENBQUMscUJBQXFCO29CQUVoRSx5QkFBeUI7b0JBQ3pCLGFBQWEsRUFBRSxJQUFJLENBQUMsUUFBUSxDQUFDLFlBQVksRUFDekMsYUFBYSxFQUFFLElBQUksQ0FBQyxRQUFRLENBQUMsWUFBWSxFQUN6QyxpQkFBaUIsRUFBRSxJQUFJLENBQUMsUUFBUSxDQUFDLGVBQWU7b0JBRWhELDBCQUEwQjtvQkFDMUIsYUFBYSxFQUFFLElBQUksQ0FBQyxRQUFRLENBQUMsWUFBWSxFQUN6QyxZQUFZLEVBQUUsSUFBSSxDQUFDLFFBQVEsQ0FBQyxXQUFXO29CQUV2QyxvQkFBb0I7b0JBQ3BCLFNBQVMsRUFBRSxJQUFJLENBQUMsUUFBUSxDQUFDLFFBQVEsRUFDakMsa0JBQWtCLEVBQUUsSUFBSSxDQUFDLFFBQVEsQ0FBQyxnQkFBZ0IsRUFDbEQsd0JBQXdCLEVBQUUsSUFBSSxDQUFDLFFBQVEsQ0FBQyxxQkFBcUI7b0JBRTdELGlCQUFpQjtvQkFDakIsaUJBQWlCLEVBQUUsSUFBSSxDQUFDLFFBQVEsQ0FBQyxnQkFBZ0IsQ0FBQyxRQUFRLEVBQUUsRUFDNUQsZ0JBQWdCLEVBQUUsSUFBSSxDQUFDLFFBQVEsQ0FBQyxjQUFjLENBQUMsUUFBUSxFQUFFO29CQUV6RCxVQUFVO29CQUNWLFNBQVMsRUFBRSxJQUFJLENBQUMsUUFBUSxDQUFDLFFBQVEsR0FDbEMsQ0FBQztnQkFFRiwwQkFBMEI7Z0JBQzFCLE1BQU0sQ0FBQyxJQUFJLENBQUMsT0FBTyxDQUFDLENBQUMsT0FBTyxDQUFDLEdBQUcsQ0FBQyxFQUFFO29CQUNqQyxJQUFJLE9BQU8sQ0FBQyxHQUFHLENBQUMsS0FBSyxTQUFTLElBQUksT0FBTyxDQUFDLEdBQUcsQ0FBQyxLQUFLLElBQUksSUFBSSxPQUFPLENBQUMsR0FBRyxDQUFDLEtBQUssRUFBRSxFQUFFLENBQUM7d0JBQy9FLE9BQU8sT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDO29CQUN0QixDQUFDO2dCQUNILENBQUMsQ0FBQyxDQUFDO2dCQUVILElBQUksQ0FBQyxPQUFPLEdBQUcsSUFBQSxxQkFBSyxFQUFDLEdBQUcsRUFBRSxJQUFJLEVBQUU7b0JBQzVCLDZEQUE2RDtvQkFDN0QsR0FBRyxFQUFFLElBQUksQ0FBQyxRQUFRLENBQUMsWUFBWSxJQUFJLFNBQVM7b0JBQzVDLGlEQUFpRDtvQkFDakQsR0FBRyxFQUFFLE9BQU87aUJBQ2YsQ0FBQyxDQUFDO2dCQUVILElBQUksQ0FBQyxPQUFPLENBQUMsTUFBTSxDQUFDLEVBQUUsQ0FBQyxNQUFNLEVBQUUsQ0FBQyxJQUFJLEVBQUUsRUFBRTtvQkFDcEMsTUFBTSxNQUFNLEdBQUcsSUFBSSxDQUFDLFFBQVEsRUFBRSxDQUFDO29CQUMvQixPQUFPLENBQUMsR0FBRyxDQUFDLGNBQWMsRUFBRSxNQUFNLENBQUMsQ0FBQztvQkFFcEMsdUNBQXVDO29CQUN2QyxJQUFJLE1BQU0sQ0FBQyxRQUFRLENBQUMsb0JBQW9CLENBQUMsSUFBSSxNQUFNLENBQUMsUUFBUSxDQUFDLDhCQUE4QixDQUFDLEVBQUUsQ0FBQzt3QkFDN0YsSUFBSSxpQkFBTSxDQUFDLHdDQUF3QyxDQUFDLENBQUM7b0JBQ3ZELENBQUM7Z0JBQ0wsQ0FBQyxDQUFDLENBQUM7Z0JBRUgsSUFBSSxDQUFDLE9BQU8sQ0FBQyxNQUFNLENBQUMsRUFBRSxDQUFDLE1BQU0sRUFBRSxDQUFDLElBQUksRUFBRSxFQUFFO29CQUNwQyxNQUFNLEtBQUssR0FBRyxJQUFJLENBQUMsUUFBUSxFQUFFLENBQUM7b0JBQzlCLE9BQU8sQ0FBQyxLQUFLLENBQUMsb0JBQW9CLEVBQUUsS0FBSyxDQUFDLENBQUM7b0JBRTNDLHVDQUF1QztvQkFDdkMsSUFBSSxLQUFLLENBQUMsUUFBUSxDQUFDLFNBQVMsQ0FBQyxFQUFFLENBQUM7d0JBQzlCLElBQUksaUJBQU0sQ0FBQywwQ0FBMEMsQ0FBQyxDQUFDO29CQUN6RCxDQUFDO3lCQUFNLElBQUksS0FBSyxDQUFDLFFBQVEsQ0FBQyxtQkFBbUIsQ0FBQyxJQUFJLEtBQUssQ0FBQyxRQUFRLENBQUMsbUJBQW1CLENBQUMsRUFBRSxDQUFDO3dCQUN0RixJQUFJLGlCQUFNLENBQUMsaURBQWlELENBQUMsQ0FBQztvQkFDaEUsQ0FBQzt5QkFBTSxJQUFJLEtBQUssQ0FBQyxRQUFRLENBQUMsd0JBQXdCLENBQUMsRUFBRSxDQUFDO3dCQUNwRCxJQUFJLGlCQUFNLENBQUMsUUFBUSxJQUFJLENBQUMsUUFBUSxDQUFDLFlBQVksd0NBQXdDLENBQUMsQ0FBQztvQkFDekYsQ0FBQzt5QkFBTSxDQUFDO3dCQUNOLElBQUksaUJBQU0sQ0FBQyxzQkFBc0IsS0FBSyxDQUFDLEtBQUssQ0FBQyxDQUFDLEVBQUUsR0FBRyxDQUFDLEtBQUssQ0FBQyxDQUFDO29CQUM3RCxDQUFDO2dCQUNILENBQUMsQ0FBQyxDQUFDO2dCQUVILElBQUksQ0FBQyxPQUFPLENBQUMsRUFBRSxDQUFDLE9BQU8sRUFBRSxDQUFDLElBQUksRUFBRSxFQUFFO29CQUNoQyxJQUFJLENBQUMsT0FBTyxHQUFHLElBQUksQ0FBQztvQkFDcEIsSUFBSSxDQUFDLGNBQWMsR0FBRyxLQUFLLENBQUM7b0JBQzVCLElBQUksQ0FBQyxlQUFlLEVBQUUsQ0FBQztvQkFFdkIsSUFBSSxJQUFJLEtBQUssQ0FBQyxFQUFFLENBQUM7d0JBQ2YsSUFBSSxpQkFBTSxDQUFDLGlDQUFpQyxJQUFJLEVBQUUsQ0FBQyxDQUFDO3dCQUNwRCxPQUFPLENBQUMsS0FBSyxDQUFDLGlDQUFpQyxJQUFJLEVBQUUsQ0FBQyxDQUFDO29CQUN6RCxDQUFDO3lCQUFNLENBQUM7d0JBQ04sSUFBSSxpQkFBTSxDQUFDLDhCQUE4QixDQUFDLENBQUM7b0JBQzdDLENBQUM7Z0JBQ0gsQ0FBQyxDQUFDLENBQUM7Z0JBRUgsSUFBSSxDQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUMsT0FBTyxFQUFFLENBQUMsS0FBSyxFQUFFLEVBQUU7b0JBQ2pDLE9BQU8sQ0FBQyxLQUFLLENBQUMsOEJBQThCLEVBQUUsS0FBSyxDQUFDLENBQUM7b0JBRXJELGtDQUFrQztvQkFDbEMsSUFBSSxLQUFLLENBQUMsT0FBTyxDQUFDLFFBQVEsQ0FBQyxRQUFRLENBQUMsRUFBRSxDQUFDO3dCQUNyQyxJQUFJLGlCQUFNLENBQUMsNkVBQTZFLENBQUMsQ0FBQztvQkFDNUYsQ0FBQzt5QkFBTSxJQUFJLEtBQUssQ0FBQyxPQUFPLENBQUMsUUFBUSxDQUFDLFFBQVEsQ0FBQyxFQUFFLENBQUM7d0JBQzVDLElBQUksaUJBQU0sQ0FBQyx5RUFBeUUsQ0FBQyxDQUFDO29CQUN4RixDQUFDO3lCQUFNLENBQUM7d0JBQ04sSUFBSSxpQkFBTSxDQUFDLGdDQUFnQyxLQUFLLENBQUMsT0FBTyxFQUFFLENBQUMsQ0FBQztvQkFDOUQsQ0FBQztvQkFFRCxJQUFJLENBQUMsT0FBTyxHQUFHLElBQUksQ0FBQztvQkFDcEIsSUFBSSxDQUFDLGNBQWMsR0FBRyxLQUFLLENBQUM7b0JBQzVCLElBQUksQ0FBQyxlQUFlLEVBQUUsQ0FBQztnQkFDekIsQ0FBQyxDQUFDLENBQUM7Z0JBRUgsSUFBSSxDQUFDLGNBQWMsR0FBRyxJQUFJLENBQUM7Z0JBQzNCLElBQUksQ0FBQyxlQUFlLEVBQUUsQ0FBQztnQkFDdkIsSUFBSSxpQkFBTSxDQUFDLGlEQUFpRCxDQUFDLENBQUM7Z0JBRTlELCtDQUErQztnQkFDL0MsVUFBVSxDQUFDLEdBQVMsRUFBRTtvQkFDcEIsTUFBTSxPQUFPLEdBQUcsTUFBTSxJQUFJLENBQUMsZ0JBQWdCLEVBQUUsQ0FBQztvQkFDOUMsSUFBSSxDQUFDLE9BQU8sSUFBSSxJQUFJLENBQUMsY0FBYyxFQUFFLENBQUM7d0JBQ3BDLElBQUksaUJBQU0sQ0FBQywrRUFBK0UsQ0FBQyxDQUFDO29CQUM5RixDQUFDO2dCQUNILENBQUMsQ0FBQSxFQUFFLElBQUksQ0FBQyxDQUFDO1lBRVgsQ0FBQztZQUFDLE9BQU8sS0FBSyxFQUFFLENBQUM7Z0JBQ2YsT0FBTyxDQUFDLEtBQUssQ0FBQyx1QkFBdUIsRUFBRSxLQUFLLENBQUMsQ0FBQztnQkFDOUMsSUFBSSxpQkFBTSxDQUFDLGdDQUFnQyxLQUFLLENBQUMsT0FBTyxFQUFFLENBQUMsQ0FBQztZQUM5RCxDQUFDO1FBQ0gsQ0FBQztLQUFBO0lBRUQsU0FBUztRQUNQLElBQUksSUFBSSxDQUFDLFFBQVEsQ0FBQyxVQUFVLEVBQUUsQ0FBQztZQUM3QixxQ0FBcUM7WUFDckMsSUFBSSxDQUFDLGNBQWMsR0FBRyxLQUFLLENBQUM7WUFDNUIsSUFBSSxDQUFDLGVBQWUsRUFBRSxDQUFDO1lBQ3ZCLElBQUksaUJBQU0sQ0FBQyx1Q0FBdUMsQ0FBQyxDQUFDO1lBQ3BELE9BQU87UUFDVCxDQUFDO1FBRUQsSUFBSSxDQUFDLElBQUksQ0FBQyxPQUFPLEVBQUUsQ0FBQztZQUNsQixJQUFJLGlCQUFNLENBQUMsNEJBQTRCLENBQUMsQ0FBQztZQUN6QyxPQUFPO1FBQ1QsQ0FBQztRQUVELElBQUksQ0FBQyxPQUFPLENBQUMsSUFBSSxDQUFDLFNBQVMsQ0FBQyxDQUFDO1FBQzdCLFVBQVUsQ0FBQyxHQUFHLEVBQUU7WUFDZCxJQUFJLElBQUksQ0FBQyxPQUFPLEVBQUUsQ0FBQztnQkFDakIsSUFBSSxDQUFDLE9BQU8sQ0FBQyxJQUFJLENBQUMsU0FBUyxDQUFDLENBQUM7WUFDL0IsQ0FBQztRQUNILENBQUMsRUFBRSxJQUFJLENBQUMsQ0FBQztRQUVQLElBQUksQ0FBQyxPQUFPLEdBQUcsSUFBSSxDQUFDO1FBQ3RCLElBQUksQ0FBQyxjQUFjLEdBQUcsS0FBSyxDQUFDO1FBQzVCLElBQUksQ0FBQyxlQUFlLEVBQUUsQ0FBQztRQUN2QixJQUFJLGlCQUFNLENBQUMscUJBQXFCLENBQUMsQ0FBQztJQUNwQyxDQUFDO0lBRUssWUFBWTs7WUFDaEIsSUFBSSxJQUFJLENBQUMsY0FBYyxFQUFFLENBQUM7Z0JBQ3hCLElBQUksQ0FBQyxTQUFTLEVBQUUsQ0FBQztnQkFDakIsa0NBQWtDO2dCQUNsQyxVQUFVLENBQUMsR0FBRyxFQUFFLENBQUMsSUFBSSxDQUFDLFVBQVUsRUFBRSxFQUFFLElBQUksQ0FBQyxDQUFDO1lBQzVDLENBQUM7aUJBQU0sQ0FBQztnQkFDTixNQUFNLElBQUksQ0FBQyxVQUFVLEVBQUUsQ0FBQztZQUMxQixDQUFDO1FBQ0gsQ0FBQztLQUFBO0lBRUssZUFBZSxDQUFDLEtBQWE7O1lBQ2pDLElBQUksQ0FBQyxJQUFJLENBQUMsY0FBYyxFQUFFLENBQUM7Z0JBQ3pCLElBQUksaUJBQU0sQ0FBQyxvQ0FBb0MsQ0FBQyxDQUFDO2dCQUNqRCxPQUFPO1lBQ1QsQ0FBQztZQUVELElBQUksaUJBQU0sQ0FBQyxpQkFBaUIsS0FBSyxDQUFDLEtBQUssQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLE1BQU0sQ0FBQyxDQUFDO1lBRXRELElBQUksQ0FBQztnQkFDSCxxQ0FBcUM7Z0JBQ3JDLE1BQU0sUUFBUSxHQUFHLE1BQU0sSUFBSSxDQUFDLGVBQWUsQ0FBQyxLQUFLLENBQUMsQ0FBQztnQkFDbkQsSUFBSSxRQUFRLEVBQUUsQ0FBQztvQkFDYix5REFBeUQ7b0JBQ3pELE1BQU0sSUFBSSxDQUFDLHFCQUFxQixDQUFDLEtBQUssRUFBRSxRQUFRLENBQUMsQ0FBQztvQkFDbEQsT0FBTztnQkFDVCxDQUFDO1lBQ0gsQ0FBQztZQUFDLE9BQU8sS0FBSyxFQUFFLENBQUM7Z0JBQ2YsT0FBTyxDQUFDLEtBQUssQ0FBQyx5QkFBeUIsRUFBRSxLQUFLLENBQUMsQ0FBQztnQkFDaEQsSUFBSSxpQkFBTSxDQUFDLG1EQUFtRCxDQUFDLENBQUM7WUFDbEUsQ0FBQztZQUVELHlCQUF5QjtZQUN6QixNQUFNLEtBQUssR0FBRyxJQUFJLFNBQVMsQ0FBQyxJQUFJLENBQUMsR0FBRyxFQUFFLElBQUksQ0FBQyxDQUFDO1lBQzVDLEtBQUssQ0FBQyxlQUFlLENBQUMsS0FBSyxDQUFDLENBQUM7WUFDN0IsS0FBSyxDQUFDLElBQUksRUFBRSxDQUFDO1FBQ2YsQ0FBQztLQUFBO0lBRWEsZUFBZSxDQUFDLEtBQWE7O1lBQ3pDLE1BQU0sTUFBTSxHQUFHLEdBQUcsSUFBSSxDQUFDLFFBQVEsQ0FBQyxlQUFlLGlCQUFpQixDQUFDO1lBRWpFLElBQUksQ0FBQztnQkFDSCxNQUFNLFFBQVEsR0FBRyxNQUFNLEtBQUssQ0FBQyxNQUFNLEVBQUU7b0JBQ25DLE1BQU0sRUFBRSxNQUFNO29CQUNkLE9BQU8sRUFBRTt3QkFDUCxjQUFjLEVBQUUsa0JBQWtCO3FCQUNuQztvQkFDRCxJQUFJLEVBQUUsSUFBSSxDQUFDLFNBQVMsQ0FBQzt3QkFDbkIsS0FBSyxFQUFFLEtBQUs7d0JBQ1osSUFBSSxFQUFFLGdCQUFnQjt3QkFDdEIsV0FBVyxFQUFFLENBQUM7d0JBQ2QsaUJBQWlCLEVBQUUsSUFBSTtxQkFDeEIsQ0FBQztpQkFDSCxDQUFDLENBQUM7Z0JBRUgsSUFBSSxDQUFDLFFBQVEsQ0FBQyxFQUFFLEVBQUUsQ0FBQztvQkFDakIsT0FBTyxJQUFJLENBQUM7Z0JBQ2QsQ0FBQztnQkFFRCxNQUFNLElBQUksR0FBRyxNQUFNLFFBQVEsQ0FBQyxJQUFJLEVBQUUsQ0FBQztnQkFDbkMsT0FBTyxJQUFJLENBQUMsT0FBTyxJQUFJLElBQUksQ0FBQyxRQUFRLElBQUksSUFBSSxDQUFDO1lBRS9DLENBQUM7WUFBQyxPQUFPLEtBQUssRUFBRSxDQUFDO2dCQUNmLE9BQU8sQ0FBQyxLQUFLLENBQUMsMkJBQTJCLEVBQUUsS0FBSyxDQUFDLENBQUM7Z0JBQ2xELE9BQU8sSUFBSSxDQUFDO1lBQ2QsQ0FBQztRQUNILENBQUM7S0FBQTtJQUVlLHFCQUFxQixDQUFDLEtBQWEsRUFBRSxPQUFlOztZQUNsRSx3QkFBd0I7WUFDeEIsTUFBTSxVQUFVLEdBQUcsSUFBSSxDQUFDLEdBQUcsQ0FBQyxTQUFTLENBQUMsVUFBVSxDQUFDO1lBQ2pELElBQUksQ0FBQyxVQUFVLElBQUksQ0FBQyxVQUFVLENBQUMsSUFBSSxJQUFJLFVBQVUsQ0FBQyxJQUFJLENBQUMsV0FBVyxFQUFFLEtBQUssVUFBVSxFQUFFLENBQUM7Z0JBQ3BGLElBQUksaUJBQU0sQ0FBQyxpQ0FBaUMsQ0FBQyxDQUFDO2dCQUM5QyxPQUFPO1lBQ1QsQ0FBQztZQUVELE1BQU0sSUFBSSxHQUFHLFVBQVUsQ0FBQyxJQUFXLENBQUMsQ0FBQyxtQ0FBbUM7WUFDeEUsSUFBSSxDQUFDLElBQUksQ0FBQyxNQUFNLEVBQUUsQ0FBQztnQkFDakIsSUFBSSxpQkFBTSxDQUFDLG9DQUFvQyxDQUFDLENBQUM7Z0JBQ2pELE9BQU87WUFDVCxDQUFDO1lBRUQsTUFBTSxNQUFNLEdBQUcsSUFBSSxDQUFDLE1BQU0sQ0FBQztZQUMzQixNQUFNLE1BQU0sR0FBRyxNQUFNLENBQUMsU0FBUyxFQUFFLENBQUM7WUFFbEMsOEJBQThCO1lBQzlCLE1BQU0sU0FBUyxHQUFHLElBQUksSUFBSSxFQUFFLENBQUMsY0FBYyxFQUFFLENBQUM7WUFDOUMsTUFBTSxhQUFhLEdBQUc7Z0JBQ3BCLEVBQUU7Z0JBQ0YsbUJBQW1CLEtBQUssRUFBRTtnQkFDMUIsaUJBQWlCLFNBQVMsK0JBQStCO2dCQUN6RCxFQUFFO2dCQUNGLE9BQU87Z0JBQ1AsRUFBRTtnQkFDRixLQUFLO2dCQUNMLEVBQUU7YUFDSCxDQUFDLElBQUksQ0FBQyxJQUFJLENBQUMsQ0FBQztZQUViLDRCQUE0QjtZQUM1QixNQUFNLENBQUMsWUFBWSxDQUFDLGFBQWEsRUFBRSxNQUFNLENBQUMsQ0FBQztZQUMzQyxJQUFJLGlCQUFNLENBQUMsNEJBQTRCLENBQUMsQ0FBQztRQUMzQyxDQUFDO0tBQUE7SUFFTyxnQkFBZ0I7O1lBQ3RCLElBQUksQ0FBQztnQkFDSCxNQUFNLFVBQVUsR0FBRyxJQUFJLGVBQWUsRUFBRSxDQUFDO2dCQUN6QyxNQUFNLFNBQVMsR0FBRyxVQUFVLENBQUMsR0FBRyxFQUFFLENBQUMsVUFBVSxDQUFDLEtBQUssRUFBRSxFQUFFLElBQUksQ0FBQyxDQUFDO2dCQUU3RCw4QkFBOEI7Z0JBQzlCLE1BQU0sY0FBYyxHQUFHLE1BQU0sS0FBSyxDQUFDLEdBQUcsSUFBSSxDQUFDLFFBQVEsQ0FBQyxlQUFlLFNBQVMsRUFBRTtvQkFDNUUsTUFBTSxFQUFFLEtBQUs7b0JBQ2IsTUFBTSxFQUFFLFVBQVUsQ0FBQyxNQUFNO2lCQUMxQixDQUFDLENBQUM7Z0JBRUgsWUFBWSxDQUFDLFNBQVMsQ0FBQyxDQUFDO2dCQUV4QixJQUFJLENBQUMsY0FBYyxDQUFDLEVBQUUsRUFBRSxDQUFDO29CQUN2QixPQUFPLEtBQUssQ0FBQztnQkFDZixDQUFDO2dCQUVELGlFQUFpRTtnQkFDakUsSUFBSSxDQUFDO29CQUNILE1BQU0sZUFBZSxHQUFHLElBQUksZUFBZSxFQUFFLENBQUM7b0JBQzlDLE1BQU0sY0FBYyxHQUFHLFVBQVUsQ0FBQyxHQUFHLEVBQUUsQ0FBQyxlQUFlLENBQUMsS0FBSyxFQUFFLEVBQUUsSUFBSSxDQUFDLENBQUM7b0JBRXZFLE1BQU0sYUFBYSxHQUFHLE1BQU0sS0FBSyxDQUFDLEdBQUcsSUFBSSxDQUFDLFFBQVEsQ0FBQyxlQUFlLGVBQWUsRUFBRTt3QkFDakYsTUFBTSxFQUFFLEtBQUs7d0JBQ2IsTUFBTSxFQUFFLGVBQWUsQ0FBQyxNQUFNO3FCQUMvQixDQUFDLENBQUM7b0JBRUgsWUFBWSxDQUFDLGNBQWMsQ0FBQyxDQUFDO29CQUU3QixJQUFJLGFBQWEsQ0FBQyxFQUFFLEVBQUUsQ0FBQzt3QkFDckIsTUFBTSxJQUFJLEdBQUcsTUFBTSxhQUFhLENBQUMsSUFBSSxFQUFFLENBQUM7d0JBQ3hDLE9BQU8sSUFBSSxDQUFDLGlCQUFpQixLQUFLLElBQUksQ0FBQztvQkFDekMsQ0FBQztnQkFDSCxDQUFDO2dCQUFDLE9BQU8sS0FBSyxFQUFFLENBQUM7b0JBQ2YscURBQXFEO29CQUNyRCxPQUFPLENBQUMsSUFBSSxDQUFDLDRCQUE0QixFQUFFLEtBQUssQ0FBQyxDQUFDO2dCQUNwRCxDQUFDO2dCQUVELE9BQU8sSUFBSSxDQUFDLENBQUMsNEJBQTRCO1lBQzNDLENBQUM7WUFBQyxPQUFPLEtBQUssRUFBRSxDQUFDO2dCQUNmLE9BQU8sS0FBSyxDQUFDO1lBQ2YsQ0FBQztRQUNILENBQUM7S0FBQTtJQUVELFFBQVE7UUFDTixJQUFJLFNBQVMsQ0FBQyxJQUFJLENBQUMsR0FBRyxFQUFFLElBQUksQ0FBQyxDQUFDLElBQUksRUFBRSxDQUFDO0lBQ3ZDLENBQUM7Q0FDRjtBQS9wQkQsOEJBK3BCQztBQUVELE1BQU0sZUFBZ0IsU0FBUSwyQkFBZ0I7SUFHNUMsWUFBWSxHQUFRLEVBQUUsTUFBbUI7UUFDdkMsS0FBSyxDQUFDLEdBQUcsRUFBRSxNQUFNLENBQUMsQ0FBQztRQUNuQixJQUFJLENBQUMsTUFBTSxHQUFHLE1BQU0sQ0FBQztJQUN2QixDQUFDO0lBRUQsT0FBTztRQUNMLE1BQU0sRUFBRSxXQUFXLEVBQUUsR0FBRyxJQUFJLENBQUM7UUFDN0IsV0FBVyxDQUFDLEtBQUssRUFBRSxDQUFDO1FBRXBCLFdBQVcsQ0FBQyxRQUFRLENBQUMsSUFBSSxFQUFFLEVBQUUsSUFBSSxFQUFFLG1DQUFtQyxFQUFFLENBQUMsQ0FBQztRQUUxRSxtQkFBbUI7UUFDbkIsV0FBVyxDQUFDLFFBQVEsQ0FBQyxJQUFJLEVBQUUsRUFBRSxJQUFJLEVBQUUsc0JBQXNCLEVBQUUsQ0FBQyxDQUFDO1FBRTdELElBQUksa0JBQU8sQ0FBQyxXQUFXLENBQUM7YUFDckIsT0FBTyxDQUFDLGlCQUFpQixDQUFDO2FBQzFCLE9BQU8sQ0FBQyw4Q0FBOEMsQ0FBQzthQUN2RCxPQUFPLENBQUMsQ0FBQyxJQUFJLEVBQUUsRUFBRSxDQUNoQixJQUFJO2FBQ0QsY0FBYyxDQUFDLHVCQUF1QixDQUFDO2FBQ3ZDLFFBQVEsQ0FBQyxJQUFJLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxVQUFVLENBQUM7YUFDekMsUUFBUSxDQUFDLENBQU8sS0FBSyxFQUFFLEVBQUU7WUFDeEIsSUFBSSxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsVUFBVSxHQUFHLEtBQUssQ0FBQztZQUN4QyxNQUFNLElBQUksQ0FBQyxNQUFNLENBQUMsWUFBWSxFQUFFLENBQUM7UUFDbkMsQ0FBQyxDQUFBLENBQUMsQ0FDTCxDQUFDO1FBRUosSUFBSSxrQkFBTyxDQUFDLFdBQVcsQ0FBQzthQUNyQixPQUFPLENBQUMsb0JBQW9CLENBQUM7YUFDN0IsT0FBTyxDQUFDLDBEQUEwRCxDQUFDO2FBQ25FLE9BQU8sQ0FBQyxDQUFDLElBQUksRUFBRSxFQUFFLENBQ2hCLElBQUk7YUFDRCxjQUFjLENBQUMsMEJBQTBCLENBQUM7YUFDMUMsUUFBUSxDQUFDLElBQUksQ0FBQyxNQUFNLENBQUMsUUFBUSxDQUFDLGFBQWEsQ0FBQzthQUM1QyxRQUFRLENBQUMsQ0FBTyxLQUFLLEVBQUUsRUFBRTtZQUN4QixJQUFJLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxhQUFhLEdBQUcsS0FBSyxDQUFDO1lBQzNDLE1BQU0sSUFBSSxDQUFDLE1BQU0sQ0FBQyxZQUFZLEVBQUUsQ0FBQztRQUNuQyxDQUFDLENBQUEsQ0FBQyxDQUNMLENBQUM7UUFFSixJQUFJLGtCQUFPLENBQUMsV0FBVyxDQUFDO2FBQ3JCLE9BQU8sQ0FBQyx1QkFBdUIsQ0FBQzthQUNoQyxPQUFPLENBQUMsK0JBQStCLENBQUM7YUFDeEMsT0FBTyxDQUFDLENBQUMsSUFBSSxFQUFFLEVBQUUsQ0FDaEIsSUFBSTthQUNELGNBQWMsQ0FBQyw2QkFBNkIsQ0FBQzthQUM3QyxRQUFRLENBQUMsSUFBSSxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsZ0JBQWdCLENBQUM7YUFDL0MsUUFBUSxDQUFDLENBQU8sS0FBSyxFQUFFLEVBQUU7WUFDeEIsSUFBSSxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsZ0JBQWdCLEdBQUcsS0FBSyxDQUFDO1lBQzlDLE1BQU0sSUFBSSxDQUFDLE1BQU0sQ0FBQyxZQUFZLEVBQUUsQ0FBQztRQUNuQyxDQUFDLENBQUEsQ0FBQyxDQUNMLENBQUM7UUFFSixJQUFJLGtCQUFPLENBQUMsV0FBVyxDQUFDO2FBQ3JCLE9BQU8sQ0FBQyxnQkFBZ0IsQ0FBQzthQUN6QixPQUFPLENBQUMsb0NBQW9DLENBQUM7YUFDN0MsT0FBTyxDQUFDLENBQUMsSUFBSSxFQUFFLEVBQUUsQ0FDaEIsSUFBSTthQUNELGNBQWMsQ0FBQyxzQkFBc0IsQ0FBQzthQUN0QyxRQUFRLENBQUMsSUFBSSxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsWUFBWSxDQUFDO2FBQzNDLFFBQVEsQ0FBQyxDQUFPLEtBQUssRUFBRSxFQUFFO1lBQ3hCLElBQUksQ0FBQyxNQUFNLENBQUMsUUFBUSxDQUFDLFlBQVksR0FBRyxLQUFLLENBQUM7WUFDMUMsTUFBTSxJQUFJLENBQUMsTUFBTSxDQUFDLFlBQVksRUFBRSxDQUFDO1FBQ25DLENBQUMsQ0FBQSxDQUFDLENBQ0wsQ0FBQztRQUVKLElBQUksa0JBQU8sQ0FBQyxXQUFXLENBQUM7YUFDckIsT0FBTyxDQUFDLHlCQUF5QixDQUFDO2FBQ2xDLE9BQU8sQ0FBQyx5QkFBeUIsQ0FBQzthQUNsQyxPQUFPLENBQUMsQ0FBQyxJQUFJLEVBQUUsRUFBRSxDQUNoQixJQUFJO2FBQ0QsY0FBYyxDQUFDLHdCQUF3QixDQUFDO2FBQ3hDLFFBQVEsQ0FBQyxJQUFJLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxvQkFBb0IsQ0FBQzthQUNuRCxRQUFRLENBQUMsQ0FBTyxLQUFLLEVBQUUsRUFBRTtZQUN4QixJQUFJLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxvQkFBb0IsR0FBRyxLQUFLLENBQUM7WUFDbEQsTUFBTSxJQUFJLENBQUMsTUFBTSxDQUFDLFlBQVksRUFBRSxDQUFDO1FBQ25DLENBQUMsQ0FBQSxDQUFDLENBQ0wsQ0FBQztRQUVKLElBQUksa0JBQU8sQ0FBQyxXQUFXLENBQUM7YUFDckIsT0FBTyxDQUFDLDBCQUEwQixDQUFDO2FBQ25DLE9BQU8sQ0FBQywwQ0FBMEMsQ0FBQzthQUNuRCxPQUFPLENBQUMsQ0FBQyxJQUFJLEVBQUUsRUFBRSxDQUNoQixJQUFJO2FBQ0QsY0FBYyxDQUFDLGdDQUFnQyxDQUFDO2FBQ2hELFFBQVEsQ0FBQyxJQUFJLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxxQkFBcUIsQ0FBQzthQUNwRCxRQUFRLENBQUMsQ0FBTyxLQUFLLEVBQUUsRUFBRTtZQUN4QixJQUFJLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxxQkFBcUIsR0FBRyxLQUFLLENBQUM7WUFDbkQsTUFBTSxJQUFJLENBQUMsTUFBTSxDQUFDLFlBQVksRUFBRSxDQUFDO1FBQ25DLENBQUMsQ0FBQSxDQUFDLENBQ0wsQ0FBQztRQUVKLDhCQUE4QjtRQUM5QixXQUFXLENBQUMsUUFBUSxDQUFDLElBQUksRUFBRSxFQUFFLElBQUksRUFBRSx3QkFBd0IsRUFBRSxDQUFDLENBQUM7UUFFL0QsSUFBSSxrQkFBTyxDQUFDLFdBQVcsQ0FBQzthQUNyQixPQUFPLENBQUMsbUJBQW1CLENBQUM7YUFDNUIsT0FBTyxDQUFDLDBDQUEwQyxDQUFDO2FBQ25ELE9BQU8sQ0FBQyxDQUFDLElBQUksRUFBRSxFQUFFLENBQ2hCLElBQUk7YUFDRCxjQUFjLENBQUMsNkNBQTZDLENBQUM7YUFDN0QsUUFBUSxDQUFDLElBQUksQ0FBQyxNQUFNLENBQUMsUUFBUSxDQUFDLFFBQVEsQ0FBQzthQUN2QyxRQUFRLENBQUMsQ0FBTyxLQUFLLEVBQUUsRUFBRTtZQUN4QixJQUFJLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxRQUFRLEdBQUcsS0FBSyxDQUFDO1lBQ3RDLE1BQU0sSUFBSSxDQUFDLE1BQU0sQ0FBQyxZQUFZLEVBQUUsQ0FBQztRQUNuQyxDQUFDLENBQUEsQ0FBQyxDQUNMLENBQUM7UUFFSixJQUFJLGtCQUFPLENBQUMsV0FBVyxDQUFDO2FBQ3JCLE9BQU8sQ0FBQyxvQkFBb0IsQ0FBQzthQUM3QixPQUFPLENBQUMsbUNBQW1DLENBQUM7YUFDNUMsT0FBTyxDQUFDLENBQUMsSUFBSSxFQUFFLEVBQUUsQ0FDaEIsSUFBSTthQUNELGNBQWMsQ0FBQyxrQ0FBa0MsQ0FBQzthQUNsRCxRQUFRLENBQUMsSUFBSSxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsZ0JBQWdCLENBQUM7YUFDL0MsUUFBUSxDQUFDLENBQU8sS0FBSyxFQUFFLEVBQUU7WUFDeEIsSUFBSSxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsZ0JBQWdCLEdBQUcsS0FBSyxDQUFDO1lBQzlDLE1BQU0sSUFBSSxDQUFDLE1BQU0sQ0FBQyxZQUFZLEVBQUUsQ0FBQztRQUNuQyxDQUFDLENBQUEsQ0FBQyxDQUNMLENBQUM7UUFFSixJQUFJLGtCQUFPLENBQUMsV0FBVyxDQUFDO2FBQ3JCLE9BQU8sQ0FBQyxtQkFBbUIsQ0FBQzthQUM1QixPQUFPLENBQUMsK0NBQStDLENBQUM7YUFDeEQsU0FBUyxDQUFDLENBQUMsTUFBTSxFQUFFLEVBQUUsQ0FDcEIsTUFBTTthQUNILFNBQVMsQ0FBQyxDQUFDLEVBQUUsQ0FBQyxFQUFFLEdBQUcsQ0FBQzthQUNwQixRQUFRLENBQUMsSUFBSSxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsZ0JBQWdCLENBQUM7YUFDL0MsaUJBQWlCLEVBQUU7YUFDbkIsUUFBUSxDQUFDLENBQU8sS0FBSyxFQUFFLEVBQUU7WUFDeEIsSUFBSSxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsZ0JBQWdCLEdBQUcsS0FBSyxDQUFDO1lBQzlDLE1BQU0sSUFBSSxDQUFDLE1BQU0sQ0FBQyxZQUFZLEVBQUUsQ0FBQztRQUNuQyxDQUFDLENBQUEsQ0FBQyxDQUNMLENBQUM7UUFFSixJQUFJLGtCQUFPLENBQUMsV0FBVyxDQUFDO2FBQ3JCLE9BQU8sQ0FBQyxtQkFBbUIsQ0FBQzthQUM1QixPQUFPLENBQUMsdUNBQXVDLENBQUM7YUFDaEQsT0FBTyxDQUFDLENBQUMsSUFBSSxFQUFFLEVBQUUsQ0FDaEIsSUFBSTthQUNELGNBQWMsQ0FBQyxPQUFPLENBQUM7YUFDdkIsUUFBUSxDQUFDLElBQUksQ0FBQyxNQUFNLENBQUMsUUFBUSxDQUFDLGtCQUFrQixDQUFDLFFBQVEsRUFBRSxDQUFDO2FBQzVELFFBQVEsQ0FBQyxDQUFPLEtBQUssRUFBRSxFQUFFO1lBQ3hCLElBQUksQ0FBQyxNQUFNLENBQUMsUUFBUSxDQUFDLGtCQUFrQixHQUFHLFFBQVEsQ0FBQyxLQUFLLENBQUMsSUFBSSxLQUFLLENBQUM7WUFDbkUsTUFBTSxJQUFJLENBQUMsTUFBTSxDQUFDLFlBQVksRUFBRSxDQUFDO1FBQ25DLENBQUMsQ0FBQSxDQUFDLENBQ0wsQ0FBQztRQUVKLHNCQUFzQjtRQUN0QixXQUFXLENBQUMsUUFBUSxDQUFDLElBQUksRUFBRSxFQUFFLElBQUksRUFBRSx3QkFBd0IsRUFBRSxDQUFDLENBQUM7UUFFL0QsSUFBSSxrQkFBTyxDQUFDLFdBQVcsQ0FBQzthQUNyQixPQUFPLENBQUMsYUFBYSxDQUFDO2FBQ3RCLE9BQU8sQ0FBQyxxRkFBcUYsQ0FBQzthQUM5RixTQUFTLENBQUMsQ0FBQyxNQUFNLEVBQUUsRUFBRSxDQUNwQixNQUFNO2FBQ0gsUUFBUSxDQUFDLElBQUksQ0FBQyxNQUFNLENBQUMsUUFBUSxDQUFDLFVBQVUsQ0FBQzthQUN6QyxRQUFRLENBQUMsQ0FBTyxLQUFLLEVBQUUsRUFBRTtZQUN4QixJQUFJLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxVQUFVLEdBQUcsS0FBSyxDQUFDO1lBQ3hDLE1BQU0sSUFBSSxDQUFDLE1BQU0sQ0FBQyxZQUFZLEVBQUUsQ0FBQztZQUNqQyxxREFBcUQ7WUFDckQsSUFBSSxDQUFDLE9BQU8sRUFBRSxDQUFDO1FBQ2pCLENBQUMsQ0FBQSxDQUFDLENBQ0wsQ0FBQztRQUVKLElBQUksSUFBSSxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsVUFBVSxFQUFFLENBQUM7WUFDcEMsSUFBSSxrQkFBTyxDQUFDLFdBQVcsQ0FBQztpQkFDckIsT0FBTyxDQUFDLHFCQUFxQixDQUFDO2lCQUM5QixPQUFPLENBQUMseUZBQXlGLENBQUM7aUJBQ2xHLE9BQU8sQ0FBQyxDQUFDLElBQUksRUFBRSxFQUFFLENBQ2hCLElBQUk7aUJBQ0QsY0FBYyxDQUFDLHVCQUF1QixDQUFDO2lCQUN2QyxRQUFRLENBQUMsSUFBSSxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsaUJBQWlCLENBQUM7aUJBQ2hELFFBQVEsQ0FBQyxDQUFPLEtBQUssRUFBRSxFQUFFO2dCQUN4QixJQUFJLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxpQkFBaUIsR0FBRyxLQUFLLENBQUM7Z0JBQy9DLG9DQUFvQztnQkFDcEMsSUFBSSxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsZUFBZSxHQUFHLEtBQUssQ0FBQztnQkFDN0MsTUFBTSxJQUFJLENBQUMsTUFBTSxDQUFDLFlBQVksRUFBRSxDQUFDO1lBQ25DLENBQUMsQ0FBQSxDQUFDLENBQ0wsQ0FBQztZQUVKLDJCQUEyQjtZQUMzQixNQUFNLE1BQU0sR0FBRyxXQUFXLENBQUMsU0FBUyxFQUFFLENBQUM7WUFDdkMsTUFBTSxDQUFDLFNBQVMsR0FBRzs7Ozs7Ozs7T0FRbEIsQ0FBQztRQUNKLENBQUM7YUFBTSxDQUFDO1lBQ04sSUFBSSxrQkFBTyxDQUFDLFdBQVcsQ0FBQztpQkFDckIsT0FBTyxDQUFDLGVBQWUsQ0FBQztpQkFDeEIsT0FBTyxDQUFDLGtDQUFrQyxDQUFDO2lCQUMzQyxPQUFPLENBQUMsQ0FBQyxJQUFJLEVBQUUsRUFBRSxDQUNoQixJQUFJO2lCQUNELGNBQWMsQ0FBQyxXQUFXLENBQUM7aUJBQzNCLFFBQVEsQ0FBQyxJQUFJLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxZQUFZLENBQUM7aUJBQzNDLFFBQVEsQ0FBQyxDQUFPLEtBQUssRUFBRSxFQUFFO2dCQUN4QixJQUFJLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxZQUFZLEdBQUcsS0FBSyxDQUFDO2dCQUMxQyxNQUFNLElBQUksQ0FBQyxNQUFNLENBQUMsWUFBWSxFQUFFLENBQUM7WUFDbkMsQ0FBQyxDQUFBLENBQUMsQ0FDTCxDQUFDO1lBRUosSUFBSSxrQkFBTyxDQUFDLFdBQVcsQ0FBQztpQkFDckIsT0FBTyxDQUFDLGVBQWUsQ0FBQztpQkFDeEIsT0FBTyxDQUFDLGlDQUFpQyxDQUFDO2lCQUMxQyxPQUFPLENBQUMsQ0FBQyxJQUFJLEVBQUUsRUFBRSxDQUNoQixJQUFJO2lCQUNELGNBQWMsQ0FBQyxNQUFNLENBQUM7aUJBQ3RCLFFBQVEsQ0FBQyxJQUFJLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxZQUFZLENBQUM7aUJBQzNDLFFBQVEsQ0FBQyxDQUFPLEtBQUssRUFBRSxFQUFFO2dCQUN4QixJQUFJLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxZQUFZLEdBQUcsS0FBSyxDQUFDO2dCQUMxQyxNQUFNLElBQUksQ0FBQyxNQUFNLENBQUMsWUFBWSxFQUFFLENBQUM7WUFDbkMsQ0FBQyxDQUFBLENBQUMsQ0FDTCxDQUFDO1FBQ04sQ0FBQztRQUVELElBQUksa0JBQU8sQ0FBQyxXQUFXLENBQUM7YUFDckIsT0FBTyxDQUFDLFVBQVUsQ0FBQzthQUNuQixPQUFPLENBQUMsdUVBQXVFLENBQUM7YUFDaEYsT0FBTyxDQUFDLENBQUMsSUFBSSxFQUFFLEVBQUUsQ0FDaEIsSUFBSTthQUNELGNBQWMsQ0FBQyx1QkFBdUIsQ0FBQzthQUN2QyxRQUFRLENBQUMsSUFBSSxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsZUFBZSxDQUFDO2FBQzlDLFFBQVEsQ0FBQyxDQUFPLEtBQUssRUFBRSxFQUFFO1lBQ3hCLElBQUksQ0FBQyxNQUFNLENBQUMsUUFBUSxDQUFDLGVBQWUsR0FBRyxLQUFLLENBQUM7WUFDN0MsTUFBTSxJQUFJLENBQUMsTUFBTSxDQUFDLFlBQVksRUFBRSxDQUFDO1FBQ25DLENBQUMsQ0FBQSxDQUFDLENBQ0wsQ0FBQztRQUVKLHFCQUFxQjtRQUNyQixXQUFXLENBQUMsUUFBUSxDQUFDLElBQUksRUFBRSxFQUFFLElBQUksRUFBRSx1QkFBdUIsRUFBRSxDQUFDLENBQUM7UUFFOUQsSUFBSSxrQkFBTyxDQUFDLFdBQVcsQ0FBQzthQUNyQixPQUFPLENBQUMscUJBQXFCLENBQUM7YUFDOUIsT0FBTyxDQUFDLGdDQUFnQyxDQUFDO2FBQ3pDLE9BQU8sQ0FBQyxDQUFDLElBQUksRUFBRSxFQUFFLENBQ2hCLElBQUk7YUFDRCxjQUFjLENBQUMsd0JBQXdCLENBQUM7YUFDeEMsUUFBUSxDQUFDLElBQUksQ0FBQyxNQUFNLENBQUMsUUFBUSxDQUFDLFlBQVksQ0FBQzthQUMzQyxRQUFRLENBQUMsQ0FBTyxLQUFLLEVBQUUsRUFBRTtZQUN4QixJQUFJLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxZQUFZLEdBQUcsS0FBSyxDQUFDO1lBQzFDLE1BQU0sSUFBSSxDQUFDLE1BQU0sQ0FBQyxZQUFZLEVBQUUsQ0FBQztRQUNuQyxDQUFDLENBQUEsQ0FBQyxDQUNMLENBQUM7UUFFSixJQUFJLGtCQUFPLENBQUMsV0FBVyxDQUFDO2FBQ3JCLE9BQU8sQ0FBQyxvQkFBb0IsQ0FBQzthQUM3QixPQUFPLENBQUMsdUNBQXVDLENBQUM7YUFDaEQsT0FBTyxDQUFDLENBQUMsSUFBSSxFQUFFLEVBQUUsQ0FDaEIsSUFBSTthQUNELGNBQWMsQ0FBQywrQkFBK0IsQ0FBQzthQUMvQyxRQUFRLENBQUMsSUFBSSxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsV0FBVyxDQUFDO2FBQzFDLFFBQVEsQ0FBQyxDQUFPLEtBQUssRUFBRSxFQUFFO1lBQ3hCLElBQUksQ0FBQyxNQUFNLENBQUMsUUFBUSxDQUFDLFdBQVcsR0FBRyxLQUFLLENBQUM7WUFDekMsTUFBTSxJQUFJLENBQUMsTUFBTSxDQUFDLFlBQVksRUFBRSxDQUFDO1FBQ25DLENBQUMsQ0FBQSxDQUFDLENBQ0wsQ0FBQztRQUVKLElBQUksa0JBQU8sQ0FBQyxXQUFXLENBQUM7YUFDckIsT0FBTyxDQUFDLGVBQWUsQ0FBQzthQUN4QixPQUFPLENBQUMsaUNBQWlDLENBQUM7YUFDMUMsT0FBTyxDQUFDLENBQUMsSUFBSSxFQUFFLEVBQUUsQ0FDaEIsSUFBSTthQUNELGNBQWMsQ0FBQyw2QkFBNkIsQ0FBQzthQUM3QyxRQUFRLENBQUMsSUFBSSxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsTUFBTSxDQUFDO2FBQ3JDLFFBQVEsQ0FBQyxDQUFPLEtBQUssRUFBRSxFQUFFO1lBQ3hCLElBQUksQ0FBQyxNQUFNLENBQUMsUUFBUSxDQUFDLE1BQU0sR0FBRyxLQUFLLENBQUM7WUFDcEMsTUFBTSxJQUFJLENBQUMsTUFBTSxDQUFDLFlBQVksRUFBRSxDQUFDO1FBQ25DLENBQUMsQ0FBQSxDQUFDLENBQ0wsQ0FBQztRQUVKLElBQUksa0JBQU8sQ0FBQyxXQUFXLENBQUM7YUFDckIsT0FBTyxDQUFDLDBCQUEwQixDQUFDO2FBQ25DLE9BQU8sQ0FBQyxzQ0FBc0MsQ0FBQzthQUMvQyxPQUFPLENBQUMsQ0FBQyxJQUFJLEVBQUUsRUFBRSxDQUNoQixJQUFJO2FBQ0QsY0FBYyxDQUFDLDRCQUE0QixDQUFDO2FBQzVDLFFBQVEsQ0FBQyxJQUFJLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxnQkFBZ0IsQ0FBQzthQUMvQyxRQUFRLENBQUMsQ0FBTyxLQUFLLEVBQUUsRUFBRTtZQUN4QixJQUFJLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxnQkFBZ0IsR0FBRyxLQUFLLENBQUM7WUFDOUMsTUFBTSxJQUFJLENBQUMsTUFBTSxDQUFDLFlBQVksRUFBRSxDQUFDO1FBQ25DLENBQUMsQ0FBQSxDQUFDLENBQ0wsQ0FBQztRQUVKLG9CQUFvQjtRQUNwQixXQUFXLENBQUMsUUFBUSxDQUFDLElBQUksRUFBRSxFQUFFLElBQUksRUFBRSxzQkFBc0IsRUFBRSxDQUFDLENBQUM7UUFFN0QsSUFBSSxrQkFBTyxDQUFDLFdBQVcsQ0FBQzthQUNyQixPQUFPLENBQUMsZ0JBQWdCLENBQUM7YUFDekIsT0FBTyxDQUFDLCtCQUErQixDQUFDO2FBQ3hDLFdBQVcsQ0FBQyxDQUFDLFFBQVEsRUFBRSxFQUFFLENBQ3hCLFFBQVE7YUFDTCxTQUFTLENBQUMsTUFBTSxFQUFFLE1BQU0sQ0FBQzthQUN6QixTQUFTLENBQUMsS0FBSyxFQUFFLEtBQUssQ0FBQzthQUN2QixTQUFTLENBQUMsS0FBSyxFQUFFLEtBQUssQ0FBQzthQUN2QixTQUFTLENBQUMsU0FBUyxFQUFFLFNBQVMsQ0FBQzthQUMvQixRQUFRLENBQUMsSUFBSSxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsYUFBYSxDQUFDO2FBQzVDLFFBQVEsQ0FBQyxDQUFPLEtBQUssRUFBRSxFQUFFO1lBQ3hCLElBQUksQ0FBQyxNQUFNLENBQUMsUUFBUSxDQUFDLGFBQWEsR0FBRyxLQUFLLENBQUM7WUFDM0MsTUFBTSxJQUFJLENBQUMsTUFBTSxDQUFDLFlBQVksRUFBRSxDQUFDO1FBQ25DLENBQUMsQ0FBQSxDQUFDLENBQ0wsQ0FBQztRQUVKLElBQUksa0JBQU8sQ0FBQyxXQUFXLENBQUM7YUFDckIsT0FBTyxDQUFDLG1CQUFtQixDQUFDO2FBQzVCLE9BQU8sQ0FBQyxrQ0FBa0MsQ0FBQzthQUMzQyxTQUFTLENBQUMsQ0FBQyxNQUFNLEVBQUUsRUFBRSxDQUNwQixNQUFNO2FBQ0gsUUFBUSxDQUFDLElBQUksQ0FBQyxNQUFNLENBQUMsUUFBUSxDQUFDLHdCQUF3QixDQUFDO2FBQ3ZELFFBQVEsQ0FBQyxDQUFPLEtBQUssRUFBRSxFQUFFO1lBQ3hCLElBQUksQ0FBQyxNQUFNLENBQUMsUUFBUSxDQUFDLHdCQUF3QixHQUFHLEtBQUssQ0FBQztZQUN0RCxNQUFNLElBQUksQ0FBQyxNQUFNLENBQUMsWUFBWSxFQUFFLENBQUM7UUFDbkMsQ0FBQyxDQUFBLENBQUMsQ0FDTCxDQUFDO1FBRUosSUFBSSxrQkFBTyxDQUFDLFdBQVcsQ0FBQzthQUNyQixPQUFPLENBQUMsc0JBQXNCLENBQUM7YUFDL0IsT0FBTyxDQUFDLHFDQUFxQyxDQUFDO2FBQzlDLFNBQVMsQ0FBQyxDQUFDLE1BQU0sRUFBRSxFQUFFLENBQ3BCLE1BQU07YUFDSCxRQUFRLENBQUMsSUFBSSxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsMEJBQTBCLENBQUM7YUFDekQsUUFBUSxDQUFDLENBQU8sS0FBSyxFQUFFLEVBQUU7WUFDeEIsSUFBSSxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsMEJBQTBCLEdBQUcsS0FBSyxDQUFDO1lBQ3hELE1BQU0sSUFBSSxDQUFDLE1BQU0sQ0FBQyxZQUFZLEVBQUUsQ0FBQztRQUNuQyxDQUFDLENBQUEsQ0FBQyxDQUNMLENBQUM7UUFFSixJQUFJLGtCQUFPLENBQUMsV0FBVyxDQUFDO2FBQ3JCLE9BQU8sQ0FBQyxXQUFXLENBQUM7YUFDcEIsT0FBTyxDQUFDLDBCQUEwQixDQUFDO2FBQ25DLFNBQVMsQ0FBQyxDQUFDLE1BQU0sRUFBRSxFQUFFLENBQ3BCLE1BQU07YUFDSCxRQUFRLENBQUMsSUFBSSxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsZ0JBQWdCLENBQUM7YUFDL0MsUUFBUSxDQUFDLENBQU8sS0FBSyxFQUFFLEVBQUU7WUFDeEIsSUFBSSxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsZ0JBQWdCLEdBQUcsS0FBSyxDQUFDO1lBQzlDLE1BQU0sSUFBSSxDQUFDLE1BQU0sQ0FBQyxZQUFZLEVBQUUsQ0FBQztRQUNuQyxDQUFDLENBQUEsQ0FBQyxDQUNMLENBQUM7UUFFQSxvQkFBb0I7UUFDeEIsV0FBVyxDQUFDLFFBQVEsQ0FBQyxJQUFJLEVBQUUsRUFBRSxJQUFJLEVBQUUsc0JBQXNCLEVBQUUsQ0FBQyxDQUFDO1FBRTdELElBQUksa0JBQU8sQ0FBQyxXQUFXLENBQUM7YUFDckIsT0FBTyxDQUFDLGtCQUFrQixDQUFDO2FBQzNCLE9BQU8sQ0FBQyx5REFBeUQsQ0FBQzthQUNsRSxTQUFTLENBQUMsQ0FBQyxNQUFNLEVBQUUsRUFBRSxDQUNwQixNQUFNO2FBQ0gsUUFBUSxDQUFDLElBQUksQ0FBQyxNQUFNLENBQUMsUUFBUSxDQUFDLGNBQWMsQ0FBQzthQUM3QyxRQUFRLENBQUMsQ0FBTyxLQUFLLEVBQUUsRUFBRTtZQUN4QixJQUFJLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxjQUFjLEdBQUcsS0FBSyxDQUFDO1lBQzVDLE1BQU0sSUFBSSxDQUFDLE1BQU0sQ0FBQyxZQUFZLEVBQUUsQ0FBQztRQUNuQyxDQUFDLENBQUEsQ0FBQyxDQUNMLENBQUM7UUFFSixJQUFJLGtCQUFPLENBQUMsV0FBVyxDQUFDO2FBQ3JCLE9BQU8sQ0FBQyxpQkFBaUIsQ0FBQzthQUMxQixPQUFPLENBQUMsd0NBQXdDLENBQUM7YUFDakQsU0FBUyxDQUFDLENBQUMsTUFBTSxFQUFFLEVBQUUsQ0FDcEIsTUFBTTthQUNILFFBQVEsQ0FBQyxJQUFJLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxhQUFhLENBQUM7YUFDNUMsUUFBUSxDQUFDLENBQU8sS0FBSyxFQUFFLEVBQUU7WUFDeEIsSUFBSSxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsYUFBYSxHQUFHLEtBQUssQ0FBQztZQUMzQyxNQUFNLElBQUksQ0FBQyxNQUFNLENBQUMsWUFBWSxFQUFFLENBQUM7WUFFakMsK0JBQStCO1lBQy9CLElBQUksS0FBSyxJQUFJLENBQUMsSUFBSSxDQUFDLE1BQU0sQ0FBQyxhQUFhLEVBQUUsQ0FBQztnQkFDeEMsSUFBSSxDQUFDLE1BQU0sQ0FBQyxhQUFhLEdBQUcsSUFBSSxDQUFDLE1BQU0sQ0FBQyxnQkFBZ0IsRUFBRSxDQUFDO2dCQUMzRCxJQUFJLENBQUMsTUFBTSxDQUFDLGVBQWUsRUFBRSxDQUFDO1lBQ2hDLENBQUM7aUJBQU0sSUFBSSxDQUFDLEtBQUssSUFBSSxJQUFJLENBQUMsTUFBTSxDQUFDLGFBQWEsRUFBRSxDQUFDO2dCQUMvQyxJQUFJLENBQUMsTUFBTSxDQUFDLGFBQWEsQ0FBQyxNQUFNLEVBQUUsQ0FBQztnQkFDbkMsSUFBSSxDQUFDLE1BQU0sQ0FBQyxhQUFhLEdBQUcsSUFBSSxDQUFDO1lBQ25DLENBQUM7UUFDSCxDQUFDLENBQUEsQ0FBQyxDQUNMLENBQUM7UUFFSixJQUFJLGtCQUFPLENBQUMsV0FBVyxDQUFDO2FBQ3JCLE9BQU8sQ0FBQyxxQkFBcUIsQ0FBQzthQUM5QixPQUFPLENBQUMseUNBQXlDLENBQUM7YUFDbEQsU0FBUyxDQUFDLENBQUMsTUFBTSxFQUFFLEVBQUUsQ0FDcEIsTUFBTTthQUNILFFBQVEsQ0FBQyxJQUFJLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxpQkFBaUIsQ0FBQzthQUNoRCxRQUFRLENBQUMsQ0FBTyxLQUFLLEVBQUUsRUFBRTtZQUN4QixJQUFJLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxpQkFBaUIsR0FBRyxLQUFLLENBQUM7WUFDL0MsTUFBTSxJQUFJLENBQUMsTUFBTSxDQUFDLFlBQVksRUFBRSxDQUFDO1FBQ25DLENBQUMsQ0FBQSxDQUFDLENBQ0wsQ0FBQztRQUVKLElBQUksa0JBQU8sQ0FBQyxXQUFXLENBQUM7YUFDckIsT0FBTyxDQUFDLG9CQUFvQixDQUFDO2FBQzdCLE9BQU8sQ0FBQyxxQ0FBcUMsQ0FBQzthQUM5QyxTQUFTLENBQUMsQ0FBQyxNQUFNLEVBQUUsRUFBRSxDQUNwQixNQUFNO2FBQ0gsUUFBUSxDQUFDLElBQUksQ0FBQyxNQUFNLENBQUMsUUFBUSxDQUFDLGdCQUFnQixDQUFDO2FBQy9DLFFBQVEsQ0FBQyxDQUFPLEtBQUssRUFBRSxFQUFFO1lBQ3hCLElBQUksQ0FBQyxNQUFNLENBQUMsUUFBUSxDQUFDLGdCQUFnQixHQUFHLEtBQUssQ0FBQztZQUM5QyxNQUFNLElBQUksQ0FBQyxNQUFNLENBQUMsWUFBWSxFQUFFLENBQUM7UUFDbkMsQ0FBQyxDQUFBLENBQUMsQ0FDTCxDQUFDO1FBRUoscUJBQXFCO1FBQ3JCLFdBQVcsQ0FBQyxRQUFRLENBQUMsSUFBSSxFQUFFLEVBQUUsSUFBSSxFQUFFLHVCQUF1QixFQUFFLENBQUMsQ0FBQztRQUU5RCxJQUFJLGtCQUFPLENBQUMsV0FBVyxDQUFDO2FBQ3JCLE9BQU8sQ0FBQywwQkFBMEIsQ0FBQzthQUNuQyxPQUFPLENBQUMscUNBQXFDLENBQUM7YUFDOUMsU0FBUyxDQUFDLENBQUMsTUFBTSxFQUFFLEVBQUUsQ0FDcEIsTUFBTTthQUNILFFBQVEsQ0FBQyxJQUFJLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQywrQkFBK0IsQ0FBQzthQUM5RCxRQUFRLENBQUMsQ0FBTyxLQUFLLEVBQUUsRUFBRTtZQUN4QixJQUFJLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQywrQkFBK0IsR0FBRyxLQUFLLENBQUM7WUFDN0QsTUFBTSxJQUFJLENBQUMsTUFBTSxDQUFDLFlBQVksRUFBRSxDQUFDO1FBQ25DLENBQUMsQ0FBQSxDQUFDLENBQ0wsQ0FBQztRQUVKLElBQUksa0JBQU8sQ0FBQyxXQUFXLENBQUM7YUFDckIsT0FBTyxDQUFDLHVCQUF1QixDQUFDO2FBQ2hDLE9BQU8sQ0FBQyx5Q0FBeUMsQ0FBQzthQUNsRCxPQUFPLENBQUMsQ0FBQyxJQUFJLEVBQUUsRUFBRSxDQUNoQixJQUFJO2FBQ0QsY0FBYyxDQUFDLE1BQU0sQ0FBQzthQUN0QixRQUFRLENBQUMsSUFBSSxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsNEJBQTRCLENBQUMsUUFBUSxFQUFFLENBQUM7YUFDdEUsUUFBUSxDQUFDLENBQU8sS0FBSyxFQUFFLEVBQUU7WUFDeEIsSUFBSSxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsNEJBQTRCLEdBQUcsUUFBUSxDQUFDLEtBQUssQ0FBQyxJQUFJLElBQUksQ0FBQztZQUM1RSxNQUFNLElBQUksQ0FBQyxNQUFNLENBQUMsWUFBWSxFQUFFLENBQUM7UUFDbkMsQ0FBQyxDQUFBLENBQUMsQ0FDTCxDQUFDO1FBRUosSUFBSSxrQkFBTyxDQUFDLFdBQVcsQ0FBQzthQUNyQixPQUFPLENBQUMsc0JBQXNCLENBQUM7YUFDL0IsT0FBTyxDQUFDLDBDQUEwQyxDQUFDO2FBQ25ELE9BQU8sQ0FBQyxDQUFDLElBQUksRUFBRSxFQUFFLENBQ2hCLElBQUk7YUFDRCxjQUFjLENBQUMsSUFBSSxDQUFDO2FBQ3BCLFFBQVEsQ0FBQyxJQUFJLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQywyQkFBMkIsQ0FBQyxRQUFRLEVBQUUsQ0FBQzthQUNyRSxRQUFRLENBQUMsQ0FBTyxLQUFLLEVBQUUsRUFBRTtZQUN4QixJQUFJLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQywyQkFBMkIsR0FBRyxRQUFRLENBQUMsS0FBSyxDQUFDLElBQUksRUFBRSxDQUFDO1lBQ3pFLE1BQU0sSUFBSSxDQUFDLE1BQU0sQ0FBQyxZQUFZLEVBQUUsQ0FBQztRQUNuQyxDQUFDLENBQUEsQ0FBQyxDQUNMLENBQUM7UUFFSixJQUFJLGtCQUFPLENBQUMsV0FBVyxDQUFDO2FBQ3JCLE9BQU8sQ0FBQyw4QkFBOEIsQ0FBQzthQUN2QyxPQUFPLENBQUMsc0NBQXNDLENBQUM7YUFDL0MsT0FBTyxDQUFDLENBQUMsSUFBSSxFQUFFLEVBQUUsQ0FDaEIsSUFBSTthQUNELGNBQWMsQ0FBQyxJQUFJLENBQUM7YUFDcEIsUUFBUSxDQUFDLElBQUksQ0FBQyxNQUFNLENBQUMsUUFBUSxDQUFDLCtCQUErQixDQUFDLFFBQVEsRUFBRSxDQUFDO2FBQ3pFLFFBQVEsQ0FBQyxDQUFPLEtBQUssRUFBRSxFQUFFO1lBQ3hCLElBQUksQ0FBQyxNQUFNLENBQUMsUUFBUSxDQUFDLCtCQUErQixHQUFHLFFBQVEsQ0FBQyxLQUFLLENBQUMsSUFBSSxFQUFFLENBQUM7WUFDN0UsTUFBTSxJQUFJLENBQUMsTUFBTSxDQUFDLFlBQVksRUFBRSxDQUFDO1FBQ25DLENBQUMsQ0FBQSxDQUFDLENBQ0wsQ0FBQztRQUVKLG9CQUFvQjtRQUNwQixXQUFXLENBQUMsUUFBUSxDQUFDLElBQUksRUFBRSxFQUFFLElBQUksRUFBRSxzQkFBc0IsRUFBRSxDQUFDLENBQUM7UUFFN0QsSUFBSSxrQkFBTyxDQUFDLFdBQVcsQ0FBQzthQUNyQixPQUFPLENBQUMsV0FBVyxDQUFDO2FBQ3BCLE9BQU8sQ0FBQyx5QkFBeUIsQ0FBQzthQUNsQyxXQUFXLENBQUMsQ0FBQyxRQUFRLEVBQUUsRUFBRSxDQUN4QixRQUFRO2FBQ0wsU0FBUyxDQUFDLE9BQU8sRUFBRSxPQUFPLENBQUM7YUFDM0IsU0FBUyxDQUFDLE1BQU0sRUFBRSxNQUFNLENBQUM7YUFDekIsU0FBUyxDQUFDLFNBQVMsRUFBRSxTQUFTLENBQUM7YUFDL0IsU0FBUyxDQUFDLE9BQU8sRUFBRSxPQUFPLENBQUM7YUFDM0IsUUFBUSxDQUFDLElBQUksQ0FBQyxNQUFNLENBQUMsUUFBUSxDQUFDLFFBQVEsQ0FBQzthQUN2QyxRQUFRLENBQUMsQ0FBTyxLQUFLLEVBQUUsRUFBRTtZQUN4QixJQUFJLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxRQUFRLEdBQUcsS0FBSyxDQUFDO1lBQ3RDLE1BQU0sSUFBSSxDQUFDLE1BQU0sQ0FBQyxZQUFZLEVBQUUsQ0FBQztRQUNuQyxDQUFDLENBQUEsQ0FBQyxDQUNMLENBQUM7UUFFSixJQUFJLGtCQUFPLENBQUMsV0FBVyxDQUFDO2FBQ3JCLE9BQU8sQ0FBQyx3QkFBd0IsQ0FBQzthQUNqQyxPQUFPLENBQUMscUNBQXFDLENBQUM7YUFDOUMsT0FBTyxDQUFDLENBQUMsSUFBSSxFQUFFLEVBQUUsQ0FDaEIsSUFBSTthQUNELGNBQWMsQ0FBQyxHQUFHLENBQUM7YUFDbkIsUUFBUSxDQUFDLElBQUksQ0FBQyxNQUFNLENBQUMsUUFBUSxDQUFDLG9CQUFvQixDQUFDLFFBQVEsRUFBRSxDQUFDO2FBQzlELFFBQVEsQ0FBQyxDQUFPLEtBQUssRUFBRSxFQUFFO1lBQ3hCLElBQUksQ0FBQyxNQUFNLENBQUMsUUFBUSxDQUFDLG9CQUFvQixHQUFHLFFBQVEsQ0FBQyxLQUFLLENBQUMsSUFBSSxDQUFDLENBQUM7WUFDakUsTUFBTSxJQUFJLENBQUMsTUFBTSxDQUFDLFlBQVksRUFBRSxDQUFDO1FBQ25DLENBQUMsQ0FBQSxDQUFDLENBQ0wsQ0FBQztRQUVKLElBQUksa0JBQU8sQ0FBQyxXQUFXLENBQUM7YUFDckIsT0FBTyxDQUFDLG9CQUFvQixDQUFDO2FBQzdCLE9BQU8sQ0FBQyx3Q0FBd0MsQ0FBQzthQUNqRCxPQUFPLENBQUMsQ0FBQyxJQUFJLEVBQUUsRUFBRSxDQUNoQixJQUFJO2FBQ0QsY0FBYyxDQUFDLFNBQVMsQ0FBQzthQUN6QixRQUFRLENBQUMsSUFBSSxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsbUJBQW1CLENBQUMsUUFBUSxFQUFFLENBQUM7YUFDN0QsUUFBUSxDQUFDLENBQU8sS0FBSyxFQUFFLEVBQUU7WUFDeEIsSUFBSSxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsbUJBQW1CLEdBQUcsUUFBUSxDQUFDLEtBQUssQ0FBQyxJQUFJLE9BQU8sQ0FBQztZQUN0RSxNQUFNLElBQUksQ0FBQyxNQUFNLENBQUMsWUFBWSxFQUFFLENBQUM7UUFDbkMsQ0FBQyxDQUFBLENBQUMsQ0FDTCxDQUFDO1FBRUosa0JBQWtCO1FBQ2xCLFdBQVcsQ0FBQyxRQUFRLENBQUMsSUFBSSxFQUFFLEVBQUUsSUFBSSxFQUFFLGVBQWUsRUFBRSxDQUFDLENBQUM7UUFFdEQsSUFBSSxrQkFBTyxDQUFDLFdBQVcsQ0FBQzthQUNyQixPQUFPLENBQUMsY0FBYyxDQUFDO2FBQ3ZCLE9BQU8sQ0FBQyx5Q0FBeUMsQ0FBQzthQUNsRCxTQUFTLENBQUMsQ0FBQyxHQUFHLEVBQUUsRUFBRSxDQUNqQixHQUFHO2FBQ0EsYUFBYSxDQUFDLElBQUksQ0FBQyxNQUFNLENBQUMsY0FBYyxDQUFDLENBQUMsQ0FBQyxZQUFZLENBQUMsQ0FBQyxDQUFDLGFBQWEsQ0FBQzthQUN4RSxPQUFPLENBQUMsR0FBUyxFQUFFO1lBQ2xCLElBQUksSUFBSSxDQUFDLE1BQU0sQ0FBQyxjQUFjLEVBQUUsQ0FBQztnQkFDL0IsSUFBSSxDQUFDLE1BQU0sQ0FBQyxTQUFTLEVBQUUsQ0FBQztZQUMxQixDQUFDO2lCQUFNLENBQUM7Z0JBQ04sTUFBTSxJQUFJLENBQUMsTUFBTSxDQUFDLFVBQVUsRUFBRSxDQUFDO1lBQ2pDLENBQUM7WUFDRCwwQkFBMEI7WUFDMUIsVUFBVSxDQUFDLEdBQUcsRUFBRSxDQUFDLElBQUksQ0FBQyxPQUFPLEVBQUUsRUFBRSxHQUFHLENBQUMsQ0FBQztRQUN4QyxDQUFDLENBQUEsQ0FBQyxDQUNMO2FBQ0EsU0FBUyxDQUFDLENBQUMsR0FBRyxFQUFFLEVBQUUsQ0FDakIsR0FBRzthQUNBLGFBQWEsQ0FBQyxlQUFlLENBQUM7YUFDOUIsT0FBTyxDQUFDLEdBQVMsRUFBRTtZQUNsQixNQUFNLElBQUksQ0FBQyxNQUFNLENBQUMsWUFBWSxFQUFFLENBQUM7WUFDakMsVUFBVSxDQUFDLEdBQUcsRUFBRSxDQUFDLElBQUksQ0FBQyxPQUFPLEVBQUUsRUFBRSxHQUFHLENBQUMsQ0FBQztRQUMxQyxDQUFDLENBQUEsQ0FBQyxDQUNILENBQUM7SUFDTixDQUFDO0NBQ0Y7QUFFRCxNQUFNLFNBQVUsU0FBUSxnQkFBSztJQVEzQixZQUFZLEdBQVEsRUFBRSxNQUFtQjtRQUN2QyxLQUFLLENBQUMsR0FBRyxDQUFDLENBQUM7UUFKYixpQkFBWSxHQUFHLEVBQUUsQ0FBQztRQUtoQixJQUFJLENBQUMsTUFBTSxHQUFHLE1BQU0sQ0FBQztJQUN2QixDQUFDO0lBRUQsZUFBZSxDQUFDLEtBQWE7UUFDM0IsSUFBSSxDQUFDLFlBQVksR0FBRyxLQUFLLENBQUM7SUFDNUIsQ0FBQztJQUVELE1BQU07UUFDSixNQUFNLEVBQUUsU0FBUyxFQUFFLEdBQUcsSUFBSSxDQUFDO1FBQzNCLFNBQVMsQ0FBQyxRQUFRLENBQUMsa0JBQWtCLENBQUMsQ0FBQztRQUV2QyxRQUFRO1FBQ1IsU0FBUyxDQUFDLFFBQVEsQ0FBQyxJQUFJLEVBQUUsRUFBRSxJQUFJLEVBQUUscUJBQXFCLEVBQUUsQ0FBQyxDQUFDO1FBRTFELGVBQWU7UUFDZixJQUFJLENBQUMsUUFBUSxHQUFHLFNBQVMsQ0FBQyxTQUFTLENBQUMsRUFBRSxHQUFHLEVBQUUsbUJBQW1CLEVBQUUsQ0FBQyxDQUFDO1FBQ2xFLElBQUksQ0FBQyxlQUFlLEVBQUUsQ0FBQztRQUV2QixnQkFBZ0I7UUFDaEIsTUFBTSxZQUFZLEdBQUcsU0FBUyxDQUFDLFNBQVMsQ0FBQyxFQUFFLEdBQUcsRUFBRSwwQkFBMEIsRUFBRSxDQUFDLENBQUM7UUFFOUUsSUFBSSxDQUFDLE9BQU8sR0FBRyxZQUFZLENBQUMsUUFBUSxDQUFDLFVBQVUsRUFBRTtZQUMvQyxHQUFHLEVBQUUsa0JBQWtCO1lBQ3ZCLElBQUksRUFBRSxFQUFFLFdBQVcsRUFBRSxrQ0FBa0MsRUFBRTtTQUMxRCxDQUFDLENBQUM7UUFFSCxJQUFJLElBQUksQ0FBQyxZQUFZLEVBQUUsQ0FBQztZQUN0QixJQUFJLENBQUMsT0FBTyxDQUFDLEtBQUssR0FBRyxJQUFJLENBQUMsWUFBWSxDQUFDO1FBQ3pDLENBQUM7UUFFRCxJQUFJLENBQUMsVUFBVSxHQUFHLFlBQVksQ0FBQyxRQUFRLENBQUMsUUFBUSxFQUFFO1lBQ2hELElBQUksRUFBRSxNQUFNO1lBQ1osR0FBRyxFQUFFLG1CQUFtQjtTQUN6QixDQUFDLENBQUM7UUFFSCxJQUFJLENBQUMsVUFBVSxDQUFDLE9BQU8sR0FBRyxHQUFHLEVBQUUsQ0FBQyxJQUFJLENBQUMsV0FBVyxFQUFFLENBQUM7UUFFbkQsMkNBQTJDO1FBQzNDLElBQUksQ0FBQyxPQUFPLENBQUMsZ0JBQWdCLENBQUMsU0FBUyxFQUFFLENBQUMsQ0FBQyxFQUFFLEVBQUU7WUFDN0MsSUFBSSxDQUFDLENBQUMsR0FBRyxLQUFLLE9BQU8sSUFBSSxDQUFDLENBQUMsQ0FBQyxRQUFRLEVBQUUsQ0FBQztnQkFDckMsQ0FBQyxDQUFDLGNBQWMsRUFBRSxDQUFDO2dCQUNuQixJQUFJLENBQUMsV0FBVyxFQUFFLENBQUM7WUFDckIsQ0FBQztRQUNILENBQUMsQ0FBQyxDQUFDO1FBRUgsaUJBQWlCO1FBQ2pCLElBQUksQ0FBQyxPQUFPLENBQUMsS0FBSyxFQUFFLENBQUM7SUFDdkIsQ0FBQztJQUVPLGVBQWU7UUFDckIsTUFBTSxPQUFPLEdBQUcsSUFBSSxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsV0FBVyxDQUFDLEtBQUssQ0FBQyxDQUFDLEVBQUUsQ0FBQyxDQUFDLENBQUMsd0JBQXdCO1FBRXJGLE9BQU8sQ0FBQyxPQUFPLENBQUMsT0FBTyxDQUFDLEVBQUU7WUFDeEIsSUFBSSxDQUFDLGdCQUFnQixDQUFDLE9BQU8sQ0FBQyxJQUFJLEVBQUUsT0FBTyxDQUFDLE9BQU8sRUFBRSxJQUFJLElBQUksQ0FBQyxPQUFPLENBQUMsU0FBUyxDQUFDLENBQUMsQ0FBQztRQUNwRixDQUFDLENBQUMsQ0FBQztJQUNMLENBQUM7SUFFTyxnQkFBZ0IsQ0FBQyxJQUFxQyxFQUFFLE9BQWUsRUFBRSxTQUFnQjtRQUMvRixNQUFNLFNBQVMsR0FBRyxJQUFJLENBQUMsUUFBUSxDQUFDLFNBQVMsQ0FBQyxFQUFFLEdBQUcsRUFBRSwrQkFBK0IsSUFBSSxFQUFFLEVBQUUsQ0FBQyxDQUFDO1FBRTFGLE1BQU0sUUFBUSxHQUFHLFNBQVMsQ0FBQyxTQUFTLENBQUMsRUFBRSxHQUFHLEVBQUUsc0JBQXNCLEVBQUUsQ0FBQyxDQUFDO1FBQ3RFLFFBQVEsQ0FBQyxVQUFVLENBQUMsRUFBRSxJQUFJLEVBQUUsSUFBSSxLQUFLLE1BQU0sQ0FBQyxDQUFDLENBQUMsS0FBSyxDQUFDLENBQUMsQ0FBQyxPQUFPLEVBQUUsR0FBRyxFQUFFLHNCQUFzQixFQUFFLENBQUMsQ0FBQztRQUU5RixJQUFJLFNBQVMsRUFBRSxDQUFDO1lBQ2QsUUFBUSxDQUFDLFVBQVUsQ0FBQztnQkFDbEIsSUFBSSxFQUFFLFNBQVMsQ0FBQyxrQkFBa0IsRUFBRTtnQkFDcEMsR0FBRyxFQUFFLG9CQUFvQjthQUMxQixDQUFDLENBQUM7UUFDTCxDQUFDO1FBRUQsU0FBUyxDQUFDLFNBQVMsQ0FBQyxFQUFFLElBQUksRUFBRSxPQUFPLEVBQUUsR0FBRyxFQUFFLHVCQUF1QixFQUFFLENBQUMsQ0FBQztRQUVyRSxtQkFBbUI7UUFDbkIsSUFBSSxDQUFDLFFBQVEsQ0FBQyxTQUFTLEdBQUcsSUFBSSxDQUFDLFFBQVEsQ0FBQyxZQUFZLENBQUM7SUFDdkQsQ0FBQztJQUVhLFdBQVc7O1lBQ3ZCLE1BQU0sT0FBTyxHQUFHLElBQUksQ0FBQyxPQUFPLENBQUMsS0FBSyxDQUFDLElBQUksRUFBRSxDQUFDO1lBQzFDLElBQUksQ0FBQyxPQUFPO2dCQUFFLE9BQU87WUFFckIsSUFBSSxDQUFDLElBQUksQ0FBQyxNQUFNLENBQUMsY0FBYyxFQUFFLENBQUM7Z0JBQ2hDLElBQUksaUJBQU0sQ0FBQyxvREFBb0QsQ0FBQyxDQUFDO2dCQUNqRSxPQUFPO1lBQ1QsQ0FBQztZQUVELDJCQUEyQjtZQUMzQixJQUFJLENBQUMsZ0JBQWdCLENBQUMsTUFBTSxFQUFFLE9BQU8sQ0FBQyxDQUFDO1lBRXZDLGtCQUFrQjtZQUNsQixNQUFNLFdBQVcsR0FBZ0I7Z0JBQy9CLElBQUksRUFBRSxNQUFNO2dCQUNaLE9BQU8sRUFBRSxPQUFPO2dCQUNoQixTQUFTLEVBQUUsSUFBSSxDQUFDLEdBQUcsRUFBRTthQUN0QixDQUFDO1lBQ0YsSUFBSSxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsV0FBVyxDQUFDLElBQUksQ0FBQyxXQUFXLENBQUMsQ0FBQztZQUVuRCxjQUFjO1lBQ2QsSUFBSSxDQUFDLE9BQU8sQ0FBQyxLQUFLLEdBQUcsRUFBRSxDQUFDO1lBQ3hCLElBQUksQ0FBQyxVQUFVLENBQUMsUUFBUSxHQUFHLElBQUksQ0FBQztZQUNoQyxJQUFJLENBQUMsVUFBVSxDQUFDLFdBQVcsR0FBRyxZQUFZLENBQUM7WUFFM0MsSUFBSSxDQUFDO2dCQUNILDhFQUE4RTtnQkFDOUUsTUFBTSxRQUFRLEdBQUcsTUFBTSxJQUFJLENBQUMsV0FBVyxDQUFDLE9BQU8sQ0FBQyxDQUFDO2dCQUVqRCx1QkFBdUI7Z0JBQ3ZCLElBQUksQ0FBQyxnQkFBZ0IsQ0FBQyxXQUFXLEVBQUUsUUFBUSxDQUFDLENBQUM7Z0JBRTdDLDJCQUEyQjtnQkFDM0IsTUFBTSxnQkFBZ0IsR0FBZ0I7b0JBQ3BDLElBQUksRUFBRSxXQUFXO29CQUNqQixPQUFPLEVBQUUsUUFBUTtvQkFDakIsU0FBUyxFQUFFLElBQUksQ0FBQyxHQUFHLEVBQUU7aUJBQ3RCLENBQUM7Z0JBQ0YsSUFBSSxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsV0FBVyxDQUFDLElBQUksQ0FBQyxnQkFBZ0IsQ0FBQyxDQUFDO2dCQUV4RCw4QkFBOEI7Z0JBQzlCLElBQUksSUFBSSxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsV0FBVyxDQUFDLE1BQU0sR0FBRyxHQUFHLEVBQUUsQ0FBQztvQkFDbEQsSUFBSSxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsV0FBVyxHQUFHLElBQUksQ0FBQyxNQUFNLENBQUMsUUFBUSxDQUFDLFdBQVcsQ0FBQyxLQUFLLENBQUMsQ0FBQyxHQUFHLENBQUMsQ0FBQztnQkFDbEYsQ0FBQztnQkFFRCxNQUFNLElBQUksQ0FBQyxNQUFNLENBQUMsWUFBWSxFQUFFLENBQUM7WUFFbkMsQ0FBQztZQUFDLE9BQU8sS0FBSyxFQUFFLENBQUM7Z0JBQ2YsT0FBTyxDQUFDLEtBQUssQ0FBQyx3QkFBd0IsRUFBRSxLQUFLLENBQUMsQ0FBQztnQkFDL0MsSUFBSSxDQUFDLGdCQUFnQixDQUFDLFFBQVEsRUFBRSw4Q0FBOEMsQ0FBQyxDQUFDO1lBQ2xGLENBQUM7b0JBQVMsQ0FBQztnQkFDVCxJQUFJLENBQUMsVUFBVSxDQUFDLFFBQVEsR0FBRyxLQUFLLENBQUM7Z0JBQ2pDLElBQUksQ0FBQyxVQUFVLENBQUMsV0FBVyxHQUFHLE1BQU0sQ0FBQztnQkFDckMsSUFBSSxDQUFDLE9BQU8sQ0FBQyxLQUFLLEVBQUUsQ0FBQztZQUN2QixDQUFDO1FBQ0gsQ0FBQztLQUFBO0lBRWUsV0FBVyxDQUFDLE9BQWU7O1lBQ3pDLElBQUksQ0FBQyxJQUFJLENBQUMsTUFBTSxDQUFDLGNBQWMsRUFBRSxDQUFDO2dCQUNoQyxNQUFNLElBQUksS0FBSyxDQUFDLDRCQUE0QixDQUFDLENBQUM7WUFDaEQsQ0FBQztZQUVELE1BQU0sTUFBTSxHQUFHLEdBQUcsSUFBSSxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsZUFBZSxnQkFBZ0IsQ0FBQztZQUV2RSxJQUFJLENBQUM7Z0JBQ0gsTUFBTSxRQUFRLEdBQUcsTUFBTSxLQUFLLENBQUMsTUFBTSxFQUFFO29CQUNuQyxNQUFNLEVBQUUsTUFBTTtvQkFDZCxPQUFPLEVBQUU7d0JBQ1AsY0FBYyxFQUFFLGtCQUFrQjtxQkFDbkM7b0JBQ0QsSUFBSSxFQUFFLElBQUksQ0FBQyxTQUFTLENBQUM7d0JBQ25CLE9BQU8sRUFBRSxPQUFPO3dCQUNoQixlQUFlLEVBQUUsSUFBSSxDQUFDLGlCQUFpQixFQUFFO3dCQUN6QyxTQUFTLEVBQUUsSUFBSSxDQUFDLEdBQUcsRUFBRTtxQkFDdEIsQ0FBQztpQkFDSCxDQUFDLENBQUM7Z0JBRUgsSUFBSSxDQUFDLFFBQVEsQ0FBQyxFQUFFLEVBQUUsQ0FBQztvQkFDakIsTUFBTSxJQUFJLEtBQUssQ0FBQyxRQUFRLFFBQVEsQ0FBQyxNQUFNLEtBQUssUUFBUSxDQUFDLFVBQVUsRUFBRSxDQUFDLENBQUM7Z0JBQ3JFLENBQUM7Z0JBRUQsTUFBTSxJQUFJLEdBQUcsTUFBTSxRQUFRLENBQUMsSUFBSSxFQUFFLENBQUM7Z0JBQ25DLE9BQU8sSUFBSSxDQUFDLFFBQVEsSUFBSSxJQUFJLENBQUMsT0FBTyxJQUFJLHdCQUF3QixDQUFDO1lBRW5FLENBQUM7WUFBQyxPQUFPLEtBQUssRUFBRSxDQUFDO2dCQUNmLE9BQU8sQ0FBQyxLQUFLLENBQUMsdUNBQXVDLEVBQUUsS0FBSyxDQUFDLENBQUM7Z0JBRTlELGlEQUFpRDtnQkFDakQsSUFBSSxLQUFLLFlBQVksU0FBUyxJQUFJLEtBQUssQ0FBQyxPQUFPLENBQUMsUUFBUSxDQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7b0JBQ2xFLE1BQU0sSUFBSSxLQUFLLENBQUMsNERBQTRELENBQUMsQ0FBQztnQkFDaEYsQ0FBQztnQkFFRCxNQUFNLElBQUksS0FBSyxDQUFDLHFDQUFxQyxLQUFLLENBQUMsT0FBTyxFQUFFLENBQUMsQ0FBQztZQUN4RSxDQUFDO1FBQ0gsQ0FBQztLQUFBO0lBRU8saUJBQWlCO1FBQ3ZCLCtEQUErRDtRQUMvRCxJQUFJLENBQUMsSUFBSSxDQUFDLGNBQWMsRUFBRSxDQUFDO1lBQ3pCLElBQUksQ0FBQyxjQUFjLEdBQUcsWUFBWSxJQUFJLENBQUMsR0FBRyxFQUFFLElBQUksSUFBSSxDQUFDLE1BQU0sRUFBRSxDQUFDLFFBQVEsQ0FBQyxFQUFFLENBQUMsQ0FBQyxTQUFTLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxFQUFFLENBQUM7UUFDaEcsQ0FBQztRQUNELE9BQU8sSUFBSSxDQUFDLGNBQWMsQ0FBQztJQUM3QixDQUFDO0lBRUQsT0FBTztRQUNMLE1BQU0sRUFBRSxTQUFTLEVBQUUsR0FBRyxJQUFJLENBQUM7UUFDM0IsU0FBUyxDQUFDLEtBQUssRUFBRSxDQUFDO0lBQ3BCLENBQUM7Q0FDRiIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IEFwcCwgTW9kYWwsIE5vdGljZSwgUGx1Z2luLCBQbHVnaW5TZXR0aW5nVGFiLCBTZXR0aW5nIH0gZnJvbSAnb2JzaWRpYW4nO1xuaW1wb3J0IHsgc3Bhd24sIENoaWxkUHJvY2Vzc1dpdGhvdXROdWxsU3RyZWFtcyB9IGZyb20gJ2NoaWxkX3Byb2Nlc3MnO1xuXG5pbnRlcmZhY2UgVGhvdGhQbHVnaW5TZXR0aW5ncyB7XG4gIC8vIEFQSSBLZXlzXG4gIG1pc3RyYWxLZXk6IHN0cmluZztcbiAgb3BlbnJvdXRlcktleTogc3RyaW5nO1xuICBvcGVuY2l0YXRpb25zS2V5OiBzdHJpbmc7XG4gIGdvb2dsZUFwaUtleTogc3RyaW5nO1xuICBnb29nbGVTZWFyY2hFbmdpbmVJZDogc3RyaW5nO1xuICBzZW1hbnRpY3NjaG9sYXJBcGlLZXk6IHN0cmluZztcblxuICAvLyBEZWZhdWx0IE1vZGVsIFNldHRpbmdzXG4gIG1vZGVsVGVtcGVyYXR1cmU6IG51bWJlcjtcbiAgbW9kZWxNYXhUb2tlbnM6IG51bWJlcjtcbiAgbW9kZWxUb3BQOiBudW1iZXI7XG4gIG1vZGVsRnJlcXVlbmN5UGVuYWx0eTogbnVtYmVyO1xuICBtb2RlbFByZXNlbmNlUGVuYWx0eTogbnVtYmVyO1xuICBtb2RlbFN0cmVhbWluZzogYm9vbGVhbjtcbiAgbW9kZWxVc2VSYXRlTGltaXRlcjogYm9vbGVhbjtcblxuICAvLyBHZW5lcmFsIExMTSBDb25maWd1cmF0aW9uXG4gIGxsbU1vZGVsOiBzdHJpbmc7XG4gIGxsbURvY1Byb2Nlc3Npbmc6IHN0cmluZztcbiAgbGxtTWF4T3V0cHV0VG9rZW5zOiBudW1iZXI7XG4gIGxsbU1heENvbnRleHRMZW5ndGg6IG51bWJlcjtcbiAgbGxtQ2h1bmtTaXplOiBudW1iZXI7XG4gIGxsbUNodW5rT3ZlcmxhcDogbnVtYmVyO1xuICBsbG1SZWZpbmVUaHJlc2hvbGRNdWx0aXBsaWVyOiBudW1iZXI7XG4gIGxsbU1hcFJlZHVjZVRocmVzaG9sZE11bHRpcGxpZXI6IG51bWJlcjtcblxuICAvLyBDaXRhdGlvbiBMTE0gQ29uZmlndXJhdGlvblxuICBjaXRhdGlvbkxsbU1vZGVsOiBzdHJpbmc7XG4gIGNpdGF0aW9uTGxtTWF4T3V0cHV0VG9rZW5zOiBudW1iZXI7XG4gIGNpdGF0aW9uTGxtTWF4Q29udGV4dExlbmd0aDogbnVtYmVyO1xuXG4gIC8vIFRhZyBDb25zb2xpZGF0b3IgTExNIENvbmZpZ3VyYXRpb25cbiAgdGFnTGxtQ29uc29saWRhdGVNb2RlbDogc3RyaW5nO1xuICB0YWdMbG1TdWdnZXN0TW9kZWw6IHN0cmluZztcbiAgdGFnTGxtTWFwTW9kZWw6IHN0cmluZztcbiAgdGFnTGxtTWF4T3V0cHV0VG9rZW5zOiBudW1iZXI7XG4gIHRhZ0xsbU1heENvbnRleHRMZW5ndGg6IG51bWJlcjtcblxuICAvLyBDaXRhdGlvbiBQcm9jZXNzaW5nIENvbmZpZ3VyYXRpb25cbiAgY2l0YXRpb25MaW5rRm9ybWF0OiBzdHJpbmc7XG4gIGNpdGF0aW9uU3R5bGU6IHN0cmluZztcbiAgY2l0YXRpb25Vc2VPcGVuY2l0YXRpb25zOiBib29sZWFuO1xuICBjaXRhdGlvblVzZVNjaG9sYXJseTogYm9vbGVhbjtcbiAgY2l0YXRpb25Vc2VTZW1hbnRpY3NjaG9sYXI6IGJvb2xlYW47XG4gIGNpdGF0aW9uVXNlQXJ4aXY6IGJvb2xlYW47XG4gIGNpdGF0aW9uQmF0Y2hTaXplOiBudW1iZXI7XG5cbiAgLy8gRW5kcG9pbnQgQ29uZmlndXJhdGlvblxuICBlbmRwb2ludEhvc3Q6IHN0cmluZztcbiAgZW5kcG9pbnRQb3J0OiBzdHJpbmc7XG4gIGVuZHBvaW50QmFzZVVybDogc3RyaW5nO1xuICBlbmRwb2ludEF1dG9TdGFydDogYm9vbGVhbjtcblxuICAvLyBNb25pdG9yIENvbmZpZ3VyYXRpb25cbiAgbW9uaXRvckF1dG9TdGFydDogYm9vbGVhbjtcbiAgbW9uaXRvcldhdGNoSW50ZXJ2YWw6IG51bWJlcjtcbiAgbW9uaXRvckJ1bGtQcm9jZXNzU2l6ZTogbnVtYmVyO1xuXG4gIC8vIExvZ2dpbmcgQ29uZmlndXJhdGlvblxuICBsb2dMZXZlbDogc3RyaW5nO1xuICBsb2dGb3JtYXQ6IHN0cmluZztcbiAgbG9nRGF0ZUZvcm1hdDogc3RyaW5nO1xuICBsb2dGaWxlbmFtZTogc3RyaW5nO1xuICBsb2dGaWxlbW9kZTogc3RyaW5nO1xuICBsb2dGaWxlTGV2ZWw6IHN0cmluZztcblxuICAvLyBUaG90aCBCYXNlIFBhdGhzICYgRGlyZWN0b3JpZXNcbiAgd29ya3NwYWNlRGlyOiBzdHJpbmc7XG4gIG9ic2lkaWFuRGlyOiBzdHJpbmc7XG4gIHBkZkRpcjogc3RyaW5nO1xuICBtYXJrZG93bkRpcjogc3RyaW5nO1xuICBub3Rlc0Rpcjogc3RyaW5nO1xuICBwcm9tcHRzRGlyOiBzdHJpbmc7XG4gIHRlbXBsYXRlc0Rpcjogc3RyaW5nO1xuICBvdXRwdXREaXI6IHN0cmluZztcbiAga25vd2xlZGdlQmFzZURpcjogc3RyaW5nO1xuICBncmFwaFN0b3JhZ2VQYXRoOiBzdHJpbmc7XG4gIGFnZW50U3RvcmFnZURpcjogc3RyaW5nO1xuICBxdWVyaWVzRGlyOiBzdHJpbmc7XG5cbiAgLy8gUmVzZWFyY2ggQWdlbnQgQ29uZmlndXJhdGlvblxuICByZXNlYXJjaEFnZW50QXV0b1N0YXJ0OiBib29sZWFuO1xuICByZXNlYXJjaEFnZW50RGVmYXVsdFF1ZXJpZXM6IGJvb2xlYW47XG5cbiAgLy8gUmVzZWFyY2ggQWdlbnQgTExNIENvbmZpZ3VyYXRpb25cbiAgcmVzZWFyY2hBZ2VudExsbU1vZGVsOiBzdHJpbmc7XG4gIHJlc2VhcmNoQWdlbnRMbG1Vc2VBdXRvTW9kZWxTZWxlY3Rpb246IGJvb2xlYW47XG4gIHJlc2VhcmNoQWdlbnRMbG1BdXRvTW9kZWxSZXF1aXJlVG9vbENhbGxpbmc6IGJvb2xlYW47XG4gIHJlc2VhcmNoQWdlbnRMbG1BdXRvTW9kZWxSZXF1aXJlU3RydWN0dXJlZE91dHB1dDogYm9vbGVhbjtcbiAgcmVzZWFyY2hBZ2VudExsbU1heE91dHB1dFRva2VuczogbnVtYmVyO1xuICByZXNlYXJjaEFnZW50TGxtTWF4Q29udGV4dExlbmd0aDogbnVtYmVyO1xuXG4gIC8vIFNjcmFwZSBGaWx0ZXIgTExNIENvbmZpZ3VyYXRpb25cbiAgc2NyYXBlRmlsdGVyTGxtTW9kZWw6IHN0cmluZztcbiAgc2NyYXBlRmlsdGVyTGxtTWF4T3V0cHV0VG9rZW5zOiBudW1iZXI7XG4gIHNjcmFwZUZpbHRlckxsbU1heENvbnRleHRMZW5ndGg6IG51bWJlcjtcblxuICAvLyBEaXNjb3ZlcnkgU3lzdGVtIENvbmZpZ3VyYXRpb25cbiAgZGlzY292ZXJ5QXV0b1N0YXJ0U2NoZWR1bGVyOiBib29sZWFuO1xuICBkaXNjb3ZlcnlEZWZhdWx0TWF4QXJ0aWNsZXM6IG51bWJlcjtcbiAgZGlzY292ZXJ5RGVmYXVsdEludGVydmFsTWludXRlczogbnVtYmVyO1xuICBkaXNjb3ZlcnlSYXRlTGltaXREZWxheTogbnVtYmVyO1xuICBkaXNjb3ZlcnlDaHJvbWVFeHRlbnNpb25FbmFibGVkOiBib29sZWFuO1xuICBkaXNjb3ZlcnlDaHJvbWVFeHRlbnNpb25Qb3J0OiBudW1iZXI7XG4gIGRpc2NvdmVyeVNvdXJjZXNEaXI6IHN0cmluZztcbiAgZGlzY292ZXJ5UmVzdWx0c0Rpcjogc3RyaW5nO1xuICBjaHJvbWVFeHRlbnNpb25Db25maWdzRGlyOiBzdHJpbmc7XG5cbiAgLy8gUGx1Z2luLXNwZWNpZmljIHNldHRpbmdzXG4gIGF1dG9TdGFydEFnZW50OiBib29sZWFuO1xuICBzaG93U3RhdHVzQmFyOiBib29sZWFuO1xuICBjaGF0SGlzdG9yeTogQ2hhdE1lc3NhZ2VbXTtcblxuICAvLyBSZW1vdGUgY29ubmVjdGlvbiBzZXR0aW5nc1xuICByZW1vdGVNb2RlOiBib29sZWFuO1xuICByZW1vdGVFbmRwb2ludFVybDogc3RyaW5nO1xufVxuXG5pbnRlcmZhY2UgQ2hhdE1lc3NhZ2Uge1xuICByb2xlOiAndXNlcicgfCAnYXNzaXN0YW50JyB8ICdzeXN0ZW0nO1xuICBjb250ZW50OiBzdHJpbmc7XG4gIHRpbWVzdGFtcDogbnVtYmVyO1xufVxuXG5jb25zdCBERUZBVUxUX1NFVFRJTkdTOiBUaG90aFBsdWdpblNldHRpbmdzID0ge1xuICAvLyBBUEkgS2V5c1xuICBtaXN0cmFsS2V5OiAnJyxcbiAgb3BlbnJvdXRlcktleTogJycsXG4gIG9wZW5jaXRhdGlvbnNLZXk6ICcnLFxuICBnb29nbGVBcGlLZXk6ICcnLFxuICBnb29nbGVTZWFyY2hFbmdpbmVJZDogJycsXG4gIHNlbWFudGljc2Nob2xhckFwaUtleTogJycsXG5cbiAgLy8gRGVmYXVsdCBNb2RlbCBTZXR0aW5nc1xuICBtb2RlbFRlbXBlcmF0dXJlOiAwLjksXG4gIG1vZGVsTWF4VG9rZW5zOiA1MDAwMCxcbiAgbW9kZWxUb3BQOiAxLjAsXG4gIG1vZGVsRnJlcXVlbmN5UGVuYWx0eTogMC4wLFxuICBtb2RlbFByZXNlbmNlUGVuYWx0eTogMC4wLFxuICBtb2RlbFN0cmVhbWluZzogZmFsc2UsXG4gIG1vZGVsVXNlUmF0ZUxpbWl0ZXI6IHRydWUsXG5cbiAgLy8gR2VuZXJhbCBMTE0gQ29uZmlndXJhdGlvblxuICBsbG1Nb2RlbDogJ2dvb2dsZS9nZW1pbmktMi41LWZsYXNoLXByZXZpZXctMDUtMjAnLFxuICBsbG1Eb2NQcm9jZXNzaW5nOiAnYXV0bycsXG4gIGxsbU1heE91dHB1dFRva2VuczogNTAwMDAsXG4gIGxsbU1heENvbnRleHRMZW5ndGg6IDEwMDAwMDAsXG4gIGxsbUNodW5rU2l6ZTogNDAwMDAwLFxuICBsbG1DaHVua092ZXJsYXA6IDUwMDAwLFxuICBsbG1SZWZpbmVUaHJlc2hvbGRNdWx0aXBsaWVyOiAwLjc1LFxuICBsbG1NYXBSZWR1Y2VUaHJlc2hvbGRNdWx0aXBsaWVyOiAwLjksXG5cbiAgLy8gQ2l0YXRpb24gTExNIENvbmZpZ3VyYXRpb25cbiAgY2l0YXRpb25MbG1Nb2RlbDogJ2dvb2dsZS9nZW1pbmktZmxhc2gtMS41LThiJyxcbiAgY2l0YXRpb25MbG1NYXhPdXRwdXRUb2tlbnM6IDEwMDAwLFxuICBjaXRhdGlvbkxsbU1heENvbnRleHRMZW5ndGg6IDQwMDAsXG5cbiAgLy8gVGFnIENvbnNvbGlkYXRvciBMTE0gQ29uZmlndXJhdGlvblxuICB0YWdMbG1Db25zb2xpZGF0ZU1vZGVsOiAnZ29vZ2xlL2dlbWluaS1mbGFzaC0xLjUtOGInLFxuICB0YWdMbG1TdWdnZXN0TW9kZWw6ICdnb29nbGUvZ2VtaW5pLWZsYXNoLTEuNS04YicsXG4gIHRhZ0xsbU1hcE1vZGVsOiAnbWlzdHJhbGFpL21pbmlzdHJhbC0zYicsXG4gIHRhZ0xsbU1heE91dHB1dFRva2VuczogMTAwMDAsXG4gIHRhZ0xsbU1heENvbnRleHRMZW5ndGg6IDgwMDAsXG5cbiAgLy8gQ2l0YXRpb24gUHJvY2Vzc2luZyBDb25maWd1cmF0aW9uXG4gIGNpdGF0aW9uTGlua0Zvcm1hdDogJ3VyaScsXG4gIGNpdGF0aW9uU3R5bGU6ICdJRUVFJyxcbiAgY2l0YXRpb25Vc2VPcGVuY2l0YXRpb25zOiB0cnVlLFxuICBjaXRhdGlvblVzZVNjaG9sYXJseTogZmFsc2UsXG4gIGNpdGF0aW9uVXNlU2VtYW50aWNzY2hvbGFyOiB0cnVlLFxuICBjaXRhdGlvblVzZUFyeGl2OiB0cnVlLFxuICBjaXRhdGlvbkJhdGNoU2l6ZTogMSxcblxuICAvLyBFbmRwb2ludCBDb25maWd1cmF0aW9uXG4gIGVuZHBvaW50SG9zdDogJzEyNy4wLjAuMScsXG4gIGVuZHBvaW50UG9ydDogJzgwMDAnLFxuICBlbmRwb2ludEJhc2VVcmw6ICdodHRwOi8vMTI3LjAuMC4xOjgwMDAnLFxuICBlbmRwb2ludEF1dG9TdGFydDogZmFsc2UsXG5cbiAgLy8gTW9uaXRvciBDb25maWd1cmF0aW9uXG4gIG1vbml0b3JBdXRvU3RhcnQ6IGZhbHNlLFxuICBtb25pdG9yV2F0Y2hJbnRlcnZhbDogNSxcbiAgbW9uaXRvckJ1bGtQcm9jZXNzU2l6ZTogMTAsXG5cbiAgLy8gTG9nZ2luZyBDb25maWd1cmF0aW9uXG4gIGxvZ0xldmVsOiAnREVCVUcnLFxuICBsb2dGb3JtYXQ6ICc8Z3JlZW4+e3RpbWU6WVlZWS1NTS1ERCBISDptbTpzcy5TU1N9PC9ncmVlbj4gfCA8bGV2ZWw+e2xldmVsOiA8OH08L2xldmVsPiB8IHtmaWxlfTp7bGluZX0gLSA8bGV2ZWw+e21lc3NhZ2V9PC9sZXZlbD4nLFxuICBsb2dEYXRlRm9ybWF0OiAnWVlZWS1NTS1ERCBISDptbTpzcycsXG4gIGxvZ0ZpbGVuYW1lOiAnbG9ncy90aG90aC5sb2cnLFxuICBsb2dGaWxlbW9kZTogJ2EnLFxuICBsb2dGaWxlTGV2ZWw6ICdERUJVRycsXG5cbiAgLy8gVGhvdGggQmFzZSBQYXRocyAmIERpcmVjdG9yaWVzXG4gIHdvcmtzcGFjZURpcjogJy9ob21lL25pY2svcHl0aG9uL3Byb2plY3QtdGhvdGgnLFxuICBvYnNpZGlhbkRpcjogJy9tbnQvYy9Vc2Vycy9uZ2hhbC9Eb2N1bWVudHMvT2JzaWRpYW4gVmF1bHQvdGhvdGgnLFxuICBwZGZEaXI6ICcke09CU0lESUFOX0RJUn0vcGFwZXJzL3BkZnMnLFxuICBtYXJrZG93bkRpcjogJyR7V09SS1NQQUNFX0RJUn0va25vd2xlZGdlL21hcmtkb3duJyxcbiAgbm90ZXNEaXI6ICcke09CU0lESUFOX0RJUn0nLFxuICBwcm9tcHRzRGlyOiAnJHtXT1JLU1BBQ0VfRElSfS90ZW1wbGF0ZXMvcHJvbXB0cycsXG4gIHRlbXBsYXRlc0RpcjogJyR7V09SS1NQQUNFX0RJUn0vdGVtcGxhdGVzJyxcbiAgb3V0cHV0RGlyOiAnJHtXT1JLU1BBQ0VfRElSfS9rbm93bGVkZ2UnLFxuICBrbm93bGVkZ2VCYXNlRGlyOiAnJHtXT1JLU1BBQ0VfRElSfS9rbm93bGVkZ2UnLFxuICBncmFwaFN0b3JhZ2VQYXRoOiAnJHtXT1JLU1BBQ0VfRElSfS9rbm93bGVkZ2UvZ3JhcGgvY2l0YXRpb25zLmdyYXBobWwnLFxuICBhZ2VudFN0b3JhZ2VEaXI6ICcke1dPUktTUEFDRV9ESVJ9L2tub3dsZWRnZS9hZ2VudCcsXG4gIHF1ZXJpZXNEaXI6ICcke0FHRU5UX1NUT1JBR0VfRElSfS9xdWVyaWVzJyxcblxuICAvLyBSZXNlYXJjaCBBZ2VudCBDb25maWd1cmF0aW9uXG4gIHJlc2VhcmNoQWdlbnRBdXRvU3RhcnQ6IGZhbHNlLFxuICByZXNlYXJjaEFnZW50RGVmYXVsdFF1ZXJpZXM6IHRydWUsXG5cbiAgLy8gUmVzZWFyY2ggQWdlbnQgTExNIENvbmZpZ3VyYXRpb25cbiAgcmVzZWFyY2hBZ2VudExsbU1vZGVsOiAnZ29vZ2xlL2dlbWluaS0yLjUtZmxhc2gtcHJldmlldy0wNS0yMCcsXG4gIHJlc2VhcmNoQWdlbnRMbG1Vc2VBdXRvTW9kZWxTZWxlY3Rpb246IHRydWUsXG4gIHJlc2VhcmNoQWdlbnRMbG1BdXRvTW9kZWxSZXF1aXJlVG9vbENhbGxpbmc6IHRydWUsXG4gIHJlc2VhcmNoQWdlbnRMbG1BdXRvTW9kZWxSZXF1aXJlU3RydWN0dXJlZE91dHB1dDogdHJ1ZSxcbiAgcmVzZWFyY2hBZ2VudExsbU1heE91dHB1dFRva2VuczogNTAwMDAsXG4gIHJlc2VhcmNoQWdlbnRMbG1NYXhDb250ZXh0TGVuZ3RoOiAxMDAwMDAsXG5cbiAgLy8gU2NyYXBlIEZpbHRlciBMTE0gQ29uZmlndXJhdGlvblxuICBzY3JhcGVGaWx0ZXJMbG1Nb2RlbDogJ2dvb2dsZS9nZW1pbmktMi41LWZsYXNoLXByZXZpZXctMDUtMjAnLFxuICBzY3JhcGVGaWx0ZXJMbG1NYXhPdXRwdXRUb2tlbnM6IDEwMDAwLFxuICBzY3JhcGVGaWx0ZXJMbG1NYXhDb250ZXh0TGVuZ3RoOiA1MDAwMCxcblxuICAvLyBEaXNjb3ZlcnkgU3lzdGVtIENvbmZpZ3VyYXRpb25cbiAgZGlzY292ZXJ5QXV0b1N0YXJ0U2NoZWR1bGVyOiBmYWxzZSxcbiAgZGlzY292ZXJ5RGVmYXVsdE1heEFydGljbGVzOiA1MCxcbiAgZGlzY292ZXJ5RGVmYXVsdEludGVydmFsTWludXRlczogNjAsXG4gIGRpc2NvdmVyeVJhdGVMaW1pdERlbGF5OiAxLjAsXG4gIGRpc2NvdmVyeUNocm9tZUV4dGVuc2lvbkVuYWJsZWQ6IHRydWUsXG4gIGRpc2NvdmVyeUNocm9tZUV4dGVuc2lvblBvcnQ6IDg3NjUsXG4gIGRpc2NvdmVyeVNvdXJjZXNEaXI6ICcke0FHRU5UX1NUT1JBR0VfRElSfS9kaXNjb3Zlcnkvc291cmNlcycsXG4gIGRpc2NvdmVyeVJlc3VsdHNEaXI6ICcke0FHRU5UX1NUT1JBR0VfRElSfS9kaXNjb3ZlcnkvcmVzdWx0cycsXG4gIGNocm9tZUV4dGVuc2lvbkNvbmZpZ3NEaXI6ICcke0FHRU5UX1NUT1JBR0VfRElSfS9kaXNjb3ZlcnkvY2hyb21lX2NvbmZpZ3MnLFxuXG4gIC8vIFBsdWdpbi1zcGVjaWZpYyBzZXR0aW5nc1xuICBhdXRvU3RhcnRBZ2VudDogZmFsc2UsXG4gIHNob3dTdGF0dXNCYXI6IHRydWUsXG4gIGNoYXRIaXN0b3J5OiBbXSxcblxuICAvLyBSZW1vdGUgY29ubmVjdGlvbiBzZXR0aW5nc1xuICByZW1vdGVNb2RlOiBmYWxzZSxcbiAgcmVtb3RlRW5kcG9pbnRVcmw6ICcnLFxufTtcblxuZXhwb3J0IGRlZmF1bHQgY2xhc3MgVGhvdGhQbHVnaW4gZXh0ZW5kcyBQbHVnaW4ge1xuICBzZXR0aW5nczogVGhvdGhQbHVnaW5TZXR0aW5ncztcbiAgcHJvY2VzczogQ2hpbGRQcm9jZXNzV2l0aG91dE51bGxTdHJlYW1zIHwgbnVsbCA9IG51bGw7XG4gIHN0YXR1c0Jhckl0ZW06IEhUTUxFbGVtZW50IHwgbnVsbCA9IG51bGw7XG4gIGlzQWdlbnRSdW5uaW5nID0gZmFsc2U7XG5cbiAgYXN5bmMgb25sb2FkKCk6IFByb21pc2U8dm9pZD4ge1xuICAgIGF3YWl0IHRoaXMubG9hZFNldHRpbmdzKCk7XG5cbiAgICAvLyBBZGQgc3RhdHVzIGJhciBpdGVtXG4gICAgaWYgKHRoaXMuc2V0dGluZ3Muc2hvd1N0YXR1c0Jhcikge1xuICAgICAgdGhpcy5zdGF0dXNCYXJJdGVtID0gdGhpcy5hZGRTdGF0dXNCYXJJdGVtKCk7XG4gICAgICB0aGlzLnVwZGF0ZVN0YXR1c0JhcigpO1xuICAgIH1cblxuICAgIC8vIEFkZCBzZXR0aW5ncyB0YWJcbiAgICB0aGlzLmFkZFNldHRpbmdUYWIobmV3IFRob3RoU2V0dGluZ1RhYih0aGlzLmFwcCwgdGhpcykpO1xuXG4gICAgLy8gQWRkIGNvbW1hbmRzXG4gICAgdGhpcy5hZGRDb21tYW5kKHtcbiAgICAgIGlkOiAnc3RhcnQtdGhvdGgtYWdlbnQnLFxuICAgICAgbmFtZTogJ1N0YXJ0IFRob3RoIEFnZW50JyxcbiAgICAgIGljb246ICdwbGF5JyxcbiAgICAgIGNhbGxiYWNrOiAoKSA9PiB0aGlzLnN0YXJ0QWdlbnQoKSxcbiAgICB9KTtcblxuICAgIHRoaXMuYWRkQ29tbWFuZCh7XG4gICAgICBpZDogJ3N0b3AtdGhvdGgtYWdlbnQnLFxuICAgICAgbmFtZTogJ1N0b3AgVGhvdGggQWdlbnQnLFxuICAgICAgaWNvbjogJ3N0b3AnLFxuICAgICAgY2FsbGJhY2s6ICgpID0+IHRoaXMuc3RvcEFnZW50KCksXG4gICAgfSk7XG5cbiAgICB0aGlzLmFkZENvbW1hbmQoe1xuICAgICAgaWQ6ICdyZXN0YXJ0LXRob3RoLWFnZW50JyxcbiAgICAgIG5hbWU6ICdSZXN0YXJ0IFRob3RoIEFnZW50JyxcbiAgICAgIGljb246ICdyZWZyZXNoLWN3JyxcbiAgICAgIGNhbGxiYWNrOiAoKSA9PiB0aGlzLnJlc3RhcnRBZ2VudCgpLFxuICAgIH0pO1xuXG4gICAgdGhpcy5hZGRDb21tYW5kKHtcbiAgICAgIGlkOiAnb3Blbi10aG90aC1jaGF0JyxcbiAgICAgIG5hbWU6ICdPcGVuIFJlc2VhcmNoIENoYXQnLFxuICAgICAgaWNvbjogJ21lc3NhZ2UtY2lyY2xlJyxcbiAgICAgIGNhbGxiYWNrOiAoKSA9PiB0aGlzLm9wZW5DaGF0KCksXG4gICAgfSk7XG5cbiAgICB0aGlzLmFkZENvbW1hbmQoe1xuICAgICAgaWQ6ICdpbnNlcnQtcmVzZWFyY2gtcXVlcnknLFxuICAgICAgbmFtZTogJ0luc2VydCBSZXNlYXJjaCBRdWVyeScsXG4gICAgICBpY29uOiAnc2VhcmNoJyxcbiAgICAgIGVkaXRvckNhbGxiYWNrOiAoZWRpdG9yKSA9PiB7XG4gICAgICAgIGNvbnN0IHNlbGVjdGlvbiA9IGVkaXRvci5nZXRTZWxlY3Rpb24oKTtcbiAgICAgICAgaWYgKHNlbGVjdGlvbikge1xuICAgICAgICAgIHRoaXMucGVyZm9ybVJlc2VhcmNoKHNlbGVjdGlvbik7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgbmV3IE5vdGljZSgnUGxlYXNlIHNlbGVjdCB0ZXh0IHRvIHJlc2VhcmNoJyk7XG4gICAgICAgIH1cbiAgICAgIH0sXG4gICAgfSk7XG5cbiAgICAvLyBBdXRvLXN0YXJ0IGFnZW50IGlmIGVuYWJsZWRcbiAgICBpZiAodGhpcy5zZXR0aW5ncy5hdXRvU3RhcnRBZ2VudCkge1xuICAgICAgc2V0VGltZW91dCgoKSA9PiB0aGlzLnN0YXJ0QWdlbnQoKSwgMjAwMCk7XG4gICAgfVxuICB9XG5cbiAgb251bmxvYWQoKTogdm9pZCB7XG4gICAgdGhpcy5zdG9wQWdlbnQoKTtcbiAgfVxuXG4gIGFzeW5jIGxvYWRTZXR0aW5ncygpOiBQcm9taXNlPHZvaWQ+IHtcbiAgICB0aGlzLnNldHRpbmdzID0gT2JqZWN0LmFzc2lnbih7fSwgREVGQVVMVF9TRVRUSU5HUywgYXdhaXQgdGhpcy5sb2FkRGF0YSgpKTtcbiAgfVxuXG4gIGFzeW5jIHNhdmVTZXR0aW5ncygpOiBQcm9taXNlPHZvaWQ+IHtcbiAgICBhd2FpdCB0aGlzLnNhdmVEYXRhKHRoaXMuc2V0dGluZ3MpO1xuICAgIGF3YWl0IHRoaXMudXBkYXRlRW52aXJvbm1lbnRGaWxlKCk7XG4gIH1cblxuICAgIHByaXZhdGUgYXN5bmMgdXBkYXRlRW52aXJvbm1lbnRGaWxlKCk6IFByb21pc2U8dm9pZD4ge1xuICAgIHRyeSB7XG4gICAgICAvLyBHZW5lcmF0ZSBjb21wcmVoZW5zaXZlIC5lbnYgZmlsZSB3aXRoIGFsbCBzZXR0aW5nc1xuICAgIGNvbnN0IGxpbmVzID0gW1xuICAgICAgICAnIyBUaG90aCBBSSBSZXNlYXJjaCBBZ2VudCBDb25maWd1cmF0aW9uJyxcbiAgICAgICAgJyMgR2VuZXJhdGVkIGJ5IE9ic2lkaWFuIFBsdWdpbicsXG4gICAgICAgICcnLFxuICAgICAgICAnIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tJyxcbiAgICAgICAgJyMgLS0tIDEuIEFQSSBLZXlzIC0tLScsXG4gICAgICAgICcjIC0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0nLFxuICAgICAgYEFQSV9NSVNUUkFMX0tFWT0ke3RoaXMuc2V0dGluZ3MubWlzdHJhbEtleX1gLFxuICAgICAgYEFQSV9PUEVOUk9VVEVSX0tFWT0ke3RoaXMuc2V0dGluZ3Mub3BlbnJvdXRlcktleX1gLFxuICAgICAgICBgQVBJX09QRU5DSVRBVElPTlNfS0VZPSR7dGhpcy5zZXR0aW5ncy5vcGVuY2l0YXRpb25zS2V5fWAsXG4gICAgICAgIGBBUElfR09PR0xFX0FQSV9LRVk9JHt0aGlzLnNldHRpbmdzLmdvb2dsZUFwaUtleX1gLFxuICAgICAgICBgQVBJX0dPT0dMRV9TRUFSQ0hfRU5HSU5FX0lEPSR7dGhpcy5zZXR0aW5ncy5nb29nbGVTZWFyY2hFbmdpbmVJZH1gLFxuICAgICAgICBgQVBJX1NFTUFOVElDU0NIT0xBUl9BUElfS0VZPSR7dGhpcy5zZXR0aW5ncy5zZW1hbnRpY3NjaG9sYXJBcGlLZXl9YCxcbiAgICAgICAgJycsXG4gICAgICAgICcjIC0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0nLFxuICAgICAgICAnIyAtLS0gMi4gRGVmYXVsdCBNb2RlbCBTZXR0aW5ncyAtLS0nLFxuICAgICAgICAnIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tJyxcbiAgICAgICAgYE1PREVMX1RFTVBFUkFUVVJFPSR7dGhpcy5zZXR0aW5ncy5tb2RlbFRlbXBlcmF0dXJlfWAsXG4gICAgICAgIGBNT0RFTF9NQVhfVE9LRU5TPSR7dGhpcy5zZXR0aW5ncy5tb2RlbE1heFRva2Vuc31gLFxuICAgICAgICBgTU9ERUxfVE9QX1A9JHt0aGlzLnNldHRpbmdzLm1vZGVsVG9wUH1gLFxuICAgICAgICBgTU9ERUxfRlJFUVVFTkNZX1BFTkFMVFk9JHt0aGlzLnNldHRpbmdzLm1vZGVsRnJlcXVlbmN5UGVuYWx0eX1gLFxuICAgICAgICBgTU9ERUxfUFJFU0VOQ0VfUEVOQUxUWT0ke3RoaXMuc2V0dGluZ3MubW9kZWxQcmVzZW5jZVBlbmFsdHl9YCxcbiAgICAgICAgYE1PREVMX1NUUkVBTUlORz0ke3RoaXMuc2V0dGluZ3MubW9kZWxTdHJlYW1pbmd9YCxcbiAgICAgICAgYE1PREVMX1VTRV9SQVRFX0xJTUlURVI9JHt0aGlzLnNldHRpbmdzLm1vZGVsVXNlUmF0ZUxpbWl0ZXJ9YCxcbiAgICAgICAgJycsXG4gICAgICAgICcjIC0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0nLFxuICAgICAgICAnIyAtLS0gMy4gR2VuZXJhbCBMTE0gQ29uZmlndXJhdGlvbiAtLS0nLFxuICAgICAgICAnIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tJyxcbiAgICAgICAgYExMTV9NT0RFTD0ke3RoaXMuc2V0dGluZ3MubGxtTW9kZWx9YCxcbiAgICAgICAgYExMTV9ET0NfUFJPQ0VTU0lORz0ke3RoaXMuc2V0dGluZ3MubGxtRG9jUHJvY2Vzc2luZ31gLFxuICAgICAgICBgTExNX01BWF9PVVRQVVRfVE9LRU5TPSR7dGhpcy5zZXR0aW5ncy5sbG1NYXhPdXRwdXRUb2tlbnN9YCxcbiAgICAgICAgYExMTV9NQVhfQ09OVEVYVF9MRU5HVEg9JHt0aGlzLnNldHRpbmdzLmxsbU1heENvbnRleHRMZW5ndGh9YCxcbiAgICAgICAgYExMTV9DSFVOS19TSVpFPSR7dGhpcy5zZXR0aW5ncy5sbG1DaHVua1NpemV9YCxcbiAgICAgICAgYExMTV9DSFVOS19PVkVSTEFQPSR7dGhpcy5zZXR0aW5ncy5sbG1DaHVua092ZXJsYXB9YCxcbiAgICAgICAgYExMTV9SRUZJTkVfVEhSRVNIT0xEX01VTFRJUExJRVI9JHt0aGlzLnNldHRpbmdzLmxsbVJlZmluZVRocmVzaG9sZE11bHRpcGxpZXJ9YCxcbiAgICAgICAgYExMTV9NQVBfUkVEVUNFX1RIUkVTSE9MRF9NVUxUSVBMSUVSPSR7dGhpcy5zZXR0aW5ncy5sbG1NYXBSZWR1Y2VUaHJlc2hvbGRNdWx0aXBsaWVyfWAsXG4gICAgICAgICcnLFxuICAgICAgICAnIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tJyxcbiAgICAgICAgJyMgLS0tIDQuIENpdGF0aW9uIExMTSBDb25maWd1cmF0aW9uIC0tLScsXG4gICAgICAgICcjIC0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0nLFxuICAgICAgICBgQ0lUQVRJT05fTExNX01PREVMPSR7dGhpcy5zZXR0aW5ncy5jaXRhdGlvbkxsbU1vZGVsfWAsXG4gICAgICAgIGBDSVRBVElPTl9MTE1fTUFYX09VVFBVVF9UT0tFTlM9JHt0aGlzLnNldHRpbmdzLmNpdGF0aW9uTGxtTWF4T3V0cHV0VG9rZW5zfWAsXG4gICAgICAgIGBDSVRBVElPTl9MTE1fTUFYX0NPTlRFWFRfTEVOR1RIPSR7dGhpcy5zZXR0aW5ncy5jaXRhdGlvbkxsbU1heENvbnRleHRMZW5ndGh9YCxcbiAgICAgICAgJycsXG4gICAgICAgICcjIC0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0nLFxuICAgICAgICAnIyAtLS0gNC41LiBUYWcgQ29uc29saWRhdG9yIExMTSBDb25maWd1cmF0aW9uIC0tLScsXG4gICAgICAgICcjIC0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0nLFxuICAgICAgICBgVEFHX0xMTV9DT05TT0xJREFURV9NT0RFTD0ke3RoaXMuc2V0dGluZ3MudGFnTGxtQ29uc29saWRhdGVNb2RlbH1gLFxuICAgICAgICBgVEFHX0xMTV9TVUdHRVNUX01PREVMPSR7dGhpcy5zZXR0aW5ncy50YWdMbG1TdWdnZXN0TW9kZWx9YCxcbiAgICAgICAgYFRBR19MTE1fTUFQX01PREVMPSR7dGhpcy5zZXR0aW5ncy50YWdMbG1NYXBNb2RlbH1gLFxuICAgICAgICBgVEFHX0xMTV9NQVhfT1VUUFVUX1RPS0VOUz0ke3RoaXMuc2V0dGluZ3MudGFnTGxtTWF4T3V0cHV0VG9rZW5zfWAsXG4gICAgICAgIGBUQUdfTExNX01BWF9DT05URVhUX0xFTkdUSD0ke3RoaXMuc2V0dGluZ3MudGFnTGxtTWF4Q29udGV4dExlbmd0aH1gLFxuICAgICAgICAnJyxcbiAgICAgICAgJyMgLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLScsXG4gICAgICAgICcjIC0tLSA1LiBDaXRhdGlvbiBQcm9jZXNzaW5nIENvbmZpZ3VyYXRpb24gLS0tJyxcbiAgICAgICAgJyMgLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLScsXG4gICAgICAgIGBDSVRBVElPTl9MSU5LX0ZPUk1BVD0ke3RoaXMuc2V0dGluZ3MuY2l0YXRpb25MaW5rRm9ybWF0fWAsXG4gICAgICAgIGBDSVRBVElPTl9TVFlMRT0ke3RoaXMuc2V0dGluZ3MuY2l0YXRpb25TdHlsZX1gLFxuICAgICAgICBgQ0lUQVRJT05fVVNFX09QRU5DSVRBVElPTlM9JHt0aGlzLnNldHRpbmdzLmNpdGF0aW9uVXNlT3BlbmNpdGF0aW9uc31gLFxuICAgICAgICBgQ0lUQVRJT05fVVNFX1NDSE9MQVJMWT0ke3RoaXMuc2V0dGluZ3MuY2l0YXRpb25Vc2VTY2hvbGFybHl9YCxcbiAgICAgICAgYENJVEFUSU9OX1VTRV9TRU1BTlRJQ1NDSE9MQVI9JHt0aGlzLnNldHRpbmdzLmNpdGF0aW9uVXNlU2VtYW50aWNzY2hvbGFyfWAsXG4gICAgICAgIGBDSVRBVElPTl9VU0VfQVJYSVY9JHt0aGlzLnNldHRpbmdzLmNpdGF0aW9uVXNlQXJ4aXZ9YCxcbiAgICAgICAgYENJVEFUSU9OX0NJVEFUSU9OX0JBVENIX1NJWkU9JHt0aGlzLnNldHRpbmdzLmNpdGF0aW9uQmF0Y2hTaXplfWAsXG4gICAgICAgICcnLFxuICAgICAgICAnIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tJyxcbiAgICAgICAgJyMgLS0tIDYuIEVuZHBvaW50IENvbmZpZ3VyYXRpb24gLS0tJyxcbiAgICAgICAgJyMgLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLScsXG4gICAgICBgRU5EUE9JTlRfSE9TVD0ke3RoaXMuc2V0dGluZ3MuZW5kcG9pbnRIb3N0fWAsXG4gICAgICBgRU5EUE9JTlRfUE9SVD0ke3RoaXMuc2V0dGluZ3MuZW5kcG9pbnRQb3J0fWAsXG4gICAgICAgIGBFTkRQT0lOVF9CQVNFX1VSTD0ke3RoaXMuc2V0dGluZ3MuZW5kcG9pbnRCYXNlVXJsfWAsXG4gICAgICAgIGBFTkRQT0lOVF9BVVRPX1NUQVJUPSR7dGhpcy5zZXR0aW5ncy5lbmRwb2ludEF1dG9TdGFydH1gLFxuICAgICAgICAnJyxcbiAgICAgICAgJyMgLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLScsXG4gICAgICAgICcjIC0tLSA3LiBNb25pdG9yIENvbmZpZ3VyYXRpb24gLS0tJyxcbiAgICAgICAgJyMgLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLScsXG4gICAgICAgIGBNT05JVE9SX0FVVE9fU1RBUlQ9JHt0aGlzLnNldHRpbmdzLm1vbml0b3JBdXRvU3RhcnR9YCxcbiAgICAgICAgYE1PTklUT1JfV0FUQ0hfSU5URVJWQUw9JHt0aGlzLnNldHRpbmdzLm1vbml0b3JXYXRjaEludGVydmFsfWAsXG4gICAgICAgIGBNT05JVE9SX0JVTEtfUFJPQ0VTU19TSVpFPSR7dGhpcy5zZXR0aW5ncy5tb25pdG9yQnVsa1Byb2Nlc3NTaXplfWAsXG4gICAgICAgICcnLFxuICAgICAgICAnIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tJyxcbiAgICAgICAgJyMgLS0tIDguIExvZ2dpbmcgQ29uZmlndXJhdGlvbiAtLS0nLFxuICAgICAgICAnIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tJyxcbiAgICAgICAgYExPR19MRVZFTD0ke3RoaXMuc2V0dGluZ3MubG9nTGV2ZWx9YCxcbiAgICAgICAgYExPR19MT0dGT1JNQVQ9XCIke3RoaXMuc2V0dGluZ3MubG9nRm9ybWF0fVwiYCxcbiAgICAgICAgYExPR19EQVRFRk9STUFUPVwiJHt0aGlzLnNldHRpbmdzLmxvZ0RhdGVGb3JtYXR9XCJgLFxuICAgICAgICBgTE9HX0ZJTEVOQU1FPSR7dGhpcy5zZXR0aW5ncy5sb2dGaWxlbmFtZX1gLFxuICAgICAgICBgTE9HX0ZJTEVNT0RFPSR7dGhpcy5zZXR0aW5ncy5sb2dGaWxlbW9kZX1gLFxuICAgICAgICBgTE9HX0ZJTEVfTEVWRUw9JHt0aGlzLnNldHRpbmdzLmxvZ0ZpbGVMZXZlbH1gLFxuICAgICAgICAnJyxcbiAgICAgICAgJyMgLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLScsXG4gICAgICAgICcjIC0tLSA5LiBUaG90aCBCYXNlIFBhdGhzICYgRGlyZWN0b3JpZXMgLS0tJyxcbiAgICAgICAgJyMgLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLScsXG4gICAgICAgIGBXT1JLU1BBQ0VfRElSPSR7dGhpcy5zZXR0aW5ncy53b3Jrc3BhY2VEaXJ9YCxcbiAgICAgICAgYE9CU0lESUFOX0RJUj0ke3RoaXMuc2V0dGluZ3Mub2JzaWRpYW5EaXJ9YCxcbiAgICAgICAgYFBERl9ESVI9JHt0aGlzLnNldHRpbmdzLnBkZkRpcn1gLFxuICAgICAgICBgTUFSS0RPV05fRElSPSR7dGhpcy5zZXR0aW5ncy5tYXJrZG93bkRpcn1gLFxuICAgICAgICBgTk9URVNfRElSPSR7dGhpcy5zZXR0aW5ncy5ub3Rlc0Rpcn1gLFxuICAgICAgICBgUFJPTVBUU19ESVI9JHt0aGlzLnNldHRpbmdzLnByb21wdHNEaXJ9YCxcbiAgICAgICAgYFRFTVBMQVRFU19ESVI9JHt0aGlzLnNldHRpbmdzLnRlbXBsYXRlc0Rpcn1gLFxuICAgICAgICBgT1VUUFVUX0RJUj0ke3RoaXMuc2V0dGluZ3Mub3V0cHV0RGlyfWAsXG4gICAgICAgIGBLTk9XTEVER0VfQkFTRV9ESVI9JHt0aGlzLnNldHRpbmdzLmtub3dsZWRnZUJhc2VEaXJ9YCxcbiAgICAgICAgYEdSQVBIX1NUT1JBR0VfUEFUSD0ke3RoaXMuc2V0dGluZ3MuZ3JhcGhTdG9yYWdlUGF0aH1gLFxuICAgICAgICBgQUdFTlRfU1RPUkFHRV9ESVI9JHt0aGlzLnNldHRpbmdzLmFnZW50U3RvcmFnZURpcn1gLFxuICAgICAgICBgUVVFUklFU19ESVI9JHt0aGlzLnNldHRpbmdzLnF1ZXJpZXNEaXJ9YCxcbiAgICAgICAgJycsXG4gICAgICAgICcjIFJlc2VhcmNoIGFnZW50IHNldHRpbmdzJyxcbiAgICAgICAgYFJFU0VBUkNIX0FHRU5UX0FVVE9fU1RBUlQ9JHt0aGlzLnNldHRpbmdzLnJlc2VhcmNoQWdlbnRBdXRvU3RhcnR9YCxcbiAgICAgICAgYFJFU0VBUkNIX0FHRU5UX0RFRkFVTFRfUVVFUklFUz0ke3RoaXMuc2V0dGluZ3MucmVzZWFyY2hBZ2VudERlZmF1bHRRdWVyaWVzfWAsXG4gICAgICAgICcnLFxuICAgICAgICAnIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tJyxcbiAgICAgICAgJyMgLS0tIDEwLiBSZXNlYXJjaCBBZ2VudCBMTE0gQ29uZmlndXJhdGlvbiAtLS0nLFxuICAgICAgICAnIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tJyxcbiAgICAgICAgYFJFU0VBUkNIX0FHRU5UX0xMTV9NT0RFTD0ke3RoaXMuc2V0dGluZ3MucmVzZWFyY2hBZ2VudExsbU1vZGVsfWAsXG4gICAgICAgIGBSRVNFQVJDSF9BR0VOVF9MTE1fVVNFX0FVVE9fTU9ERUxfU0VMRUNUSU9OPSR7dGhpcy5zZXR0aW5ncy5yZXNlYXJjaEFnZW50TGxtVXNlQXV0b01vZGVsU2VsZWN0aW9ufWAsXG4gICAgICAgIGBSRVNFQVJDSF9BR0VOVF9MTE1fQVVUT19NT0RFTF9SRVFVSVJFX1RPT0xfQ0FMTElORz0ke3RoaXMuc2V0dGluZ3MucmVzZWFyY2hBZ2VudExsbUF1dG9Nb2RlbFJlcXVpcmVUb29sQ2FsbGluZ31gLFxuICAgICAgICBgUkVTRUFSQ0hfQUdFTlRfTExNX0FVVE9fTU9ERUxfUkVRVUlSRV9TVFJVQ1RVUkVEX09VVFBVVD0ke3RoaXMuc2V0dGluZ3MucmVzZWFyY2hBZ2VudExsbUF1dG9Nb2RlbFJlcXVpcmVTdHJ1Y3R1cmVkT3V0cHV0fWAsXG4gICAgICAgIGBSRVNFQVJDSF9BR0VOVF9MTE1fTUFYX09VVFBVVF9UT0tFTlM9JHt0aGlzLnNldHRpbmdzLnJlc2VhcmNoQWdlbnRMbG1NYXhPdXRwdXRUb2tlbnN9YCxcbiAgICAgICAgYFJFU0VBUkNIX0FHRU5UX0xMTV9NQVhfQ09OVEVYVF9MRU5HVEg9JHt0aGlzLnNldHRpbmdzLnJlc2VhcmNoQWdlbnRMbG1NYXhDb250ZXh0TGVuZ3RofWAsXG4gICAgICAgICcnLFxuICAgICAgICAnIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tJyxcbiAgICAgICAgJyMgLS0tIDExLiBTY3JhcGUgRmlsdGVyIExMTSBDb25maWd1cmF0aW9uIC0tLScsXG4gICAgICAgICcjIC0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0nLFxuICAgICAgICBgU0NSQVBFX0ZJTFRFUl9MTE1fTU9ERUw9JHt0aGlzLnNldHRpbmdzLnNjcmFwZUZpbHRlckxsbU1vZGVsfWAsXG4gICAgICAgIGBTQ1JBUEVfRklMVEVSX0xMTV9NQVhfT1VUUFVUX1RPS0VOUz0ke3RoaXMuc2V0dGluZ3Muc2NyYXBlRmlsdGVyTGxtTWF4T3V0cHV0VG9rZW5zfWAsXG4gICAgICAgIGBTQ1JBUEVfRklMVEVSX0xMTV9NQVhfQ09OVEVYVF9MRU5HVEg9JHt0aGlzLnNldHRpbmdzLnNjcmFwZUZpbHRlckxsbU1heENvbnRleHRMZW5ndGh9YCxcbiAgICAgICAgJycsXG4gICAgICAgICcjIC0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0nLFxuICAgICAgICAnIyAtLS0gMTIuIERpc2NvdmVyeSBTeXN0ZW0gQ29uZmlndXJhdGlvbiAtLS0nLFxuICAgICAgICAnIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tJyxcbiAgICAgICAgYERJU0NPVkVSWV9BVVRPX1NUQVJUX1NDSEVEVUxFUj0ke3RoaXMuc2V0dGluZ3MuZGlzY292ZXJ5QXV0b1N0YXJ0U2NoZWR1bGVyfWAsXG4gICAgICAgIGBESVNDT1ZFUllfREVGQVVMVF9NQVhfQVJUSUNMRVM9JHt0aGlzLnNldHRpbmdzLmRpc2NvdmVyeURlZmF1bHRNYXhBcnRpY2xlc31gLFxuICAgICAgICBgRElTQ09WRVJZX0RFRkFVTFRfSU5URVJWQUxfTUlOVVRFUz0ke3RoaXMuc2V0dGluZ3MuZGlzY292ZXJ5RGVmYXVsdEludGVydmFsTWludXRlc31gLFxuICAgICAgICBgRElTQ09WRVJZX1JBVEVfTElNSVRfREVMQVk9JHt0aGlzLnNldHRpbmdzLmRpc2NvdmVyeVJhdGVMaW1pdERlbGF5fWAsXG4gICAgICAgIGBESVNDT1ZFUllfQ0hST01FX0VYVEVOU0lPTl9FTkFCTEVEPSR7dGhpcy5zZXR0aW5ncy5kaXNjb3ZlcnlDaHJvbWVFeHRlbnNpb25FbmFibGVkfWAsXG4gICAgICAgIGBESVNDT1ZFUllfQ0hST01FX0VYVEVOU0lPTl9QT1JUPSR7dGhpcy5zZXR0aW5ncy5kaXNjb3ZlcnlDaHJvbWVFeHRlbnNpb25Qb3J0fWAsXG4gICAgICAgICcnLFxuICAgICAgICAnIyAtLS0gRGlzY292ZXJ5IGZvbGRlcnMgLS0tJyxcbiAgICAgICAgYERJU0NPVkVSWV9TT1VSQ0VTX0RJUj0ke3RoaXMuc2V0dGluZ3MuZGlzY292ZXJ5U291cmNlc0Rpcn1gLFxuICAgICAgICBgRElTQ09WRVJZX1JFU1VMVFNfRElSPSR7dGhpcy5zZXR0aW5ncy5kaXNjb3ZlcnlSZXN1bHRzRGlyfWAsXG4gICAgICAgIGBDSFJPTUVfRVhURU5TSU9OX0NPTkZJR1NfRElSPSR7dGhpcy5zZXR0aW5ncy5jaHJvbWVFeHRlbnNpb25Db25maWdzRGlyfWAsXG4gICAgICBdO1xuXG4gICAgICAvLyBXcml0ZSB0byB3b3Jrc3BhY2UgZGlyZWN0b3J5IChub3QgdmF1bHQpIHNpbmNlIHRoYXQncyB3aGVyZSB0aGUgcHJvY2VzcyBydW5zXG4gICAgICB0cnkge1xuICAgICAgICAvLyBGaXJzdCB0cnkgdG8gd3JpdGUgdG8gd29ya3NwYWNlIGRpcmVjdG9yeSBpZiBpdCBleGlzdHNcbiAgICAgICAgaWYgKHRoaXMuc2V0dGluZ3Mud29ya3NwYWNlRGlyICYmIHJlcXVpcmUoJ2ZzJykuZXhpc3RzU3luYyh0aGlzLnNldHRpbmdzLndvcmtzcGFjZURpcikpIHtcbiAgICAgICAgICBjb25zdCBwYXRoID0gcmVxdWlyZSgncGF0aCcpO1xuICAgICAgICAgIGNvbnN0IGZzID0gcmVxdWlyZSgnZnMnKTtcbiAgICAgICAgICBjb25zdCBlbnZQYXRoID0gcGF0aC5qb2luKHRoaXMuc2V0dGluZ3Mud29ya3NwYWNlRGlyLCAnLmVudicpO1xuICAgICAgICAgIGZzLndyaXRlRmlsZVN5bmMoZW52UGF0aCwgbGluZXMuam9pbignXFxuJykpO1xuICAgICAgICAgIG5ldyBOb3RpY2UoJ1Rob3RoIGNvbmZpZ3VyYXRpb24gdXBkYXRlZCBpbiB3b3Jrc3BhY2UgZGlyZWN0b3J5Jyk7XG4gICAgICAgICAgcmV0dXJuO1xuICAgICAgICB9XG4gICAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgIGNvbnNvbGUud2FybignQ291bGQgbm90IHdyaXRlIHRvIHdvcmtzcGFjZSBkaXJlY3Rvcnk6JywgZSk7XG4gICAgICB9XG5cbiAgICAgIC8vIEZhbGxiYWNrOiB3cml0ZSB0byB2YXVsdCB1c2luZyBPYnNpZGlhbidzIEFQSVxuICAgICAgdHJ5IHtcbiAgICAgICAgYXdhaXQgdGhpcy5hcHAudmF1bHQuYWRhcHRlci53cml0ZSgnLmVudicsIGxpbmVzLmpvaW4oJ1xcbicpKTtcbiAgICAgICAgbmV3IE5vdGljZSgnVGhvdGggY29uZmlndXJhdGlvbiB1cGRhdGVkIGluIHZhdWx0IChmYWxsYmFjayknKTtcbiAgICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgY29uc29sZS5lcnJvcignQ291bGQgbm90IHdyaXRlIHRvIHZhdWx0OicsIGUpO1xuICAgICAgICBuZXcgTm90aWNlKCdDb3VsZCBub3QgdXBkYXRlIGVudmlyb25tZW50IGZpbGUgaW4gdmF1bHQnKTtcbiAgICAgIH1cbiAgICB9IGNhdGNoIChlcnJvcikge1xuICAgICAgY29uc29sZS5lcnJvcignRmFpbGVkIHRvIHVwZGF0ZSBlbnZpcm9ubWVudCBmaWxlOicsIGVycm9yKTtcbiAgICAgIG5ldyBOb3RpY2UoJ1dhcm5pbmc6IENvdWxkIG5vdCB1cGRhdGUgZW52aXJvbm1lbnQgZmlsZScpO1xuICAgIH1cbiAgfVxuXG4gICAgdXBkYXRlU3RhdHVzQmFyKCk6IHZvaWQge1xuICAgIGlmICghdGhpcy5zdGF0dXNCYXJJdGVtKSByZXR1cm47XG5cbiAgICBpZiAodGhpcy5pc0FnZW50UnVubmluZykge1xuICAgICAgLy8gQ2hlY2sgYWN0dWFsIGFnZW50IGhlYWx0aFxuICAgICAgdGhpcy5jaGVja0FnZW50SGVhbHRoKCkudGhlbigoaGVhbHRoeSkgPT4ge1xuICAgICAgICBjb25zdCBzdGF0dXMgPSBoZWFsdGh5ID8gJ1J1bm5pbmcnIDogJ0Vycm9yJztcbiAgICAgICAgY29uc3QgY29sb3IgPSBoZWFsdGh5ID8gJyMwMGZmMDAnIDogJyNmZmFhMDAnO1xuXG4gICAgICAgIHRoaXMuc3RhdHVzQmFySXRlbSEuaW5uZXJIVE1MID0gYDxzcGFuIHN0eWxlPVwiY29sb3I6ICR7Y29sb3J9XCI+VGhvdGg6ICR7c3RhdHVzfTwvc3Bhbj5gO1xuICAgICAgICB0aGlzLnN0YXR1c0Jhckl0ZW0hLnRpdGxlID0gaGVhbHRoeVxuICAgICAgICAgID8gJ1Rob3RoIEFnZW50IGlzIHJ1bm5pbmcgYW5kIGhlYWx0aHkuIENsaWNrIHRvIHN0b3AuJ1xuICAgICAgICAgIDogJ1Rob3RoIEFnZW50IHByb2Nlc3MgaXMgcnVubmluZyBidXQgQVBJIGlzIG5vdCByZXNwb25kaW5nLiBDbGljayB0byByZXN0YXJ0Lic7XG4gICAgICB9KS5jYXRjaCgoKSA9PiB7XG4gICAgICAgIHRoaXMuc3RhdHVzQmFySXRlbSEuaW5uZXJIVE1MID0gYDxzcGFuIHN0eWxlPVwiY29sb3I6ICNmZmFhMDBcIj5UaG90aDogQ2hlY2tpbmcuLi48L3NwYW4+YDtcbiAgICAgIH0pO1xuICAgIH0gZWxzZSB7XG4gICAgICB0aGlzLnN0YXR1c0Jhckl0ZW0uaW5uZXJIVE1MID0gYDxzcGFuIHN0eWxlPVwiY29sb3I6ICNmZjZiNmJcIj5UaG90aDogU3RvcHBlZDwvc3Bhbj5gO1xuICAgICAgdGhpcy5zdGF0dXNCYXJJdGVtLnRpdGxlID0gJ1Rob3RoIEFnZW50IGlzIHN0b3BwZWQuIENsaWNrIHRvIHN0YXJ0Lic7XG4gICAgfVxuXG4gICAgdGhpcy5zdGF0dXNCYXJJdGVtLm9uY2xpY2sgPSAoKSA9PiB7XG4gICAgICBpZiAodGhpcy5pc0FnZW50UnVubmluZykge1xuICAgICAgICB0aGlzLnN0b3BBZ2VudCgpO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgdGhpcy5zdGFydEFnZW50KCk7XG4gICAgICB9XG4gICAgfTtcbiAgfVxuXG4gIGFzeW5jIHN0YXJ0QWdlbnQoKTogUHJvbWlzZTx2b2lkPiB7XG4gICAgaWYgKHRoaXMucHJvY2VzcyAmJiAhdGhpcy5zZXR0aW5ncy5yZW1vdGVNb2RlKSB7XG4gICAgICBuZXcgTm90aWNlKCdUaG90aCBhZ2VudCBpcyBhbHJlYWR5IHJ1bm5pbmcnKTtcbiAgICAgIHJldHVybjtcbiAgICB9XG5cbiAgICAvLyBWYWxpZGF0ZSBzZXR0aW5ncyBmaXJzdFxuICAgIGlmICghdGhpcy5zZXR0aW5ncy5taXN0cmFsS2V5ICYmICF0aGlzLnNldHRpbmdzLm9wZW5yb3V0ZXJLZXkpIHtcbiAgICAgIG5ldyBOb3RpY2UoJ1BsZWFzZSBjb25maWd1cmUgQVBJIGtleXMgaW4gc2V0dGluZ3MgZmlyc3QnKTtcbiAgICAgIHJldHVybjtcbiAgICB9XG5cbiAgICAvLyBIYW5kbGUgcmVtb3RlIG1vZGUgLSBjb25uZWN0IHRvIGV4aXN0aW5nIHNlcnZlclxuICAgIGlmICh0aGlzLnNldHRpbmdzLnJlbW90ZU1vZGUpIHtcbiAgICAgIGlmICghdGhpcy5zZXR0aW5ncy5yZW1vdGVFbmRwb2ludFVybCkge1xuICAgICAgICBuZXcgTm90aWNlKCdQbGVhc2UgY29uZmlndXJlIHJlbW90ZSBlbmRwb2ludCBVUkwgaW4gc2V0dGluZ3MnKTtcbiAgICAgICAgcmV0dXJuO1xuICAgICAgfVxuXG4gICAgICBuZXcgTm90aWNlKCdDb25uZWN0aW5nIHRvIHJlbW90ZSBUaG90aCBzZXJ2ZXIuLi4nKTtcblxuICAgICAgdHJ5IHtcbiAgICAgICAgLy8gVGVzdCBjb25uZWN0aW9uIHRvIHJlbW90ZSBzZXJ2ZXJcbiAgICAgICAgY29uc3QgY29udHJvbGxlciA9IG5ldyBBYm9ydENvbnRyb2xsZXIoKTtcbiAgICAgICAgY29uc3QgdGltZW91dElkID0gc2V0VGltZW91dCgoKSA9PiBjb250cm9sbGVyLmFib3J0KCksIDUwMDApO1xuXG4gICAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZmV0Y2goYCR7dGhpcy5zZXR0aW5ncy5yZW1vdGVFbmRwb2ludFVybH0vaGVhbHRoYCwge1xuICAgICAgICAgIG1ldGhvZDogJ0dFVCcsXG4gICAgICAgICAgc2lnbmFsOiBjb250cm9sbGVyLnNpZ25hbFxuICAgICAgICB9KTtcblxuICAgICAgICBjbGVhclRpbWVvdXQodGltZW91dElkKTtcblxuICAgICAgICBpZiAoIXJlc3BvbnNlLm9rKSB7XG4gICAgICAgICAgdGhyb3cgbmV3IEVycm9yKGBTZXJ2ZXIgcmVzcG9uZGVkIHdpdGggJHtyZXNwb25zZS5zdGF0dXN9YCk7XG4gICAgICAgIH1cblxuICAgICAgICAvLyBVcGRhdGUgYmFzZSBVUkwgdG8gdXNlIHJlbW90ZSBlbmRwb2ludFxuICAgICAgICB0aGlzLnNldHRpbmdzLmVuZHBvaW50QmFzZVVybCA9IHRoaXMuc2V0dGluZ3MucmVtb3RlRW5kcG9pbnRVcmw7XG4gICAgICAgIGF3YWl0IHRoaXMuc2F2ZVNldHRpbmdzKCk7XG5cbiAgICAgICAgdGhpcy5pc0FnZW50UnVubmluZyA9IHRydWU7XG4gICAgICAgIHRoaXMudXBkYXRlU3RhdHVzQmFyKCk7XG4gICAgICAgIG5ldyBOb3RpY2UoJ0Nvbm5lY3RlZCB0byByZW1vdGUgVGhvdGggc2VydmVyIHN1Y2Nlc3NmdWxseSEnKTtcblxuICAgICAgICAvLyBDaGVjayBpZiBhZ2VudCBpcyBwcm9wZXJseSBpbml0aWFsaXplZFxuICAgICAgICBzZXRUaW1lb3V0KGFzeW5jICgpID0+IHtcbiAgICAgICAgICBjb25zdCBoZWFsdGh5ID0gYXdhaXQgdGhpcy5jaGVja0FnZW50SGVhbHRoKCk7XG4gICAgICAgICAgaWYgKCFoZWFsdGh5KSB7XG4gICAgICAgICAgICBuZXcgTm90aWNlKCdDb25uZWN0ZWQgdG8gc2VydmVyIGJ1dCByZXNlYXJjaCBhZ2VudCBub3QgcmVhZHkuIFNlcnZlciBtYXkgc3RpbGwgYmUgc3RhcnRpbmcgdXAuJyk7XG4gICAgICAgICAgfVxuICAgICAgICB9LCAyMDAwKTtcblxuICAgICAgICByZXR1cm47XG5cbiAgICAgIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgICAgIGNvbnNvbGUuZXJyb3IoJ0ZhaWxlZCB0byBjb25uZWN0IHRvIHJlbW90ZSBzZXJ2ZXI6JywgZXJyb3IpO1xuICAgICAgICBuZXcgTm90aWNlKGBGYWlsZWQgdG8gY29ubmVjdCB0byByZW1vdGUgc2VydmVyOiAke2Vycm9yLm1lc3NhZ2V9YCk7XG4gICAgICAgIHJldHVybjtcbiAgICAgIH1cbiAgICB9XG5cbiAgICAvLyBMb2NhbCBtb2RlIC0gc3Bhd24gbG9jYWwgcHJvY2Vzc1xuICAgIGlmICh0aGlzLnByb2Nlc3MpIHtcbiAgICAgIG5ldyBOb3RpY2UoJ1Rob3RoIGFnZW50IGlzIGFscmVhZHkgcnVubmluZycpO1xuICAgICAgcmV0dXJuO1xuICAgIH1cblxuICAgIC8vIEVuc3VyZSAuZW52IGZpbGUgaXMgdXAgdG8gZGF0ZSBiZWZvcmUgc3RhcnRpbmcgYWdlbnRcbiAgICB0cnkge1xuICAgICAgYXdhaXQgdGhpcy51cGRhdGVFbnZpcm9ubWVudEZpbGUoKTtcbiAgICAgIG5ldyBOb3RpY2UoJ0NvbmZpZ3VyYXRpb24gdXBkYXRlZCwgc3RhcnRpbmcgVGhvdGggYWdlbnQuLi4nKTtcbiAgICB9IGNhdGNoIChlcnJvcikge1xuICAgICAgY29uc29sZS5lcnJvcignRmFpbGVkIHRvIHVwZGF0ZSBlbnZpcm9ubWVudCBmaWxlOicsIGVycm9yKTtcbiAgICAgIG5ldyBOb3RpY2UoJ1dhcm5pbmc6IENvdWxkIG5vdCB1cGRhdGUgY29uZmlndXJhdGlvbiBmaWxlJyk7XG4gICAgfVxuXG4gICAgdHJ5IHtcbiAgICBjb25zdCBjbWQgPSAndXYnO1xuICAgIGNvbnN0IGFyZ3MgPSBbXG4gICAgICAncnVuJyxcbiAgICAgICdweXRob24nLFxuICAgICAgJy1tJyxcbiAgICAgICd0aG90aCcsXG4gICAgICAnYXBpJyxcbiAgICAgICctLWhvc3QnLCB0aGlzLnNldHRpbmdzLmVuZHBvaW50SG9zdCxcbiAgICAgICctLXBvcnQnLCB0aGlzLnNldHRpbmdzLmVuZHBvaW50UG9ydCxcbiAgICAgICctLWJhc2UtdXJsJywgdGhpcy5zZXR0aW5ncy5lbmRwb2ludEJhc2VVcmwsXG4gICAgXTtcblxuICAgIC8vIENyZWF0ZSBlbnZpcm9ubWVudCB3aXRoIGFsbCBuZWNlc3NhcnkgdmFyaWFibGVzXG4gICAgY29uc3QgZW52VmFycyA9IHtcbiAgICAgIC4uLnByb2Nlc3MuZW52LFxuICAgICAgLy8gQVBJIEtleXNcbiAgICAgIEFQSV9NSVNUUkFMX0tFWTogdGhpcy5zZXR0aW5ncy5taXN0cmFsS2V5LFxuICAgICAgQVBJX09QRU5ST1VURVJfS0VZOiB0aGlzLnNldHRpbmdzLm9wZW5yb3V0ZXJLZXksXG4gICAgICBBUElfT1BFTkNJVEFUSU9OU19LRVk6IHRoaXMuc2V0dGluZ3Mub3BlbmNpdGF0aW9uc0tleSxcbiAgICAgIEFQSV9HT09HTEVfQVBJX0tFWTogdGhpcy5zZXR0aW5ncy5nb29nbGVBcGlLZXksXG4gICAgICBBUElfR09PR0xFX1NFQVJDSF9FTkdJTkVfSUQ6IHRoaXMuc2V0dGluZ3MuZ29vZ2xlU2VhcmNoRW5naW5lSWQsXG4gICAgICBBUElfU0VNQU5USUNTQ0hPTEFSX0FQSV9LRVk6IHRoaXMuc2V0dGluZ3Muc2VtYW50aWNzY2hvbGFyQXBpS2V5LFxuXG4gICAgICAvLyBFbmRwb2ludCBDb25maWd1cmF0aW9uXG4gICAgICBFTkRQT0lOVF9IT1NUOiB0aGlzLnNldHRpbmdzLmVuZHBvaW50SG9zdCxcbiAgICAgIEVORFBPSU5UX1BPUlQ6IHRoaXMuc2V0dGluZ3MuZW5kcG9pbnRQb3J0LFxuICAgICAgRU5EUE9JTlRfQkFTRV9VUkw6IHRoaXMuc2V0dGluZ3MuZW5kcG9pbnRCYXNlVXJsLFxuXG4gICAgICAvLyBEaXJlY3RvcnkgQ29uZmlndXJhdGlvblxuICAgICAgV09SS1NQQUNFX0RJUjogdGhpcy5zZXR0aW5ncy53b3Jrc3BhY2VEaXIsXG4gICAgICBPQlNJRElBTl9ESVI6IHRoaXMuc2V0dGluZ3Mub2JzaWRpYW5EaXIsXG5cbiAgICAgIC8vIExMTSBDb25maWd1cmF0aW9uXG4gICAgICBMTE1fTU9ERUw6IHRoaXMuc2V0dGluZ3MubGxtTW9kZWwsXG4gICAgICBDSVRBVElPTl9MTE1fTU9ERUw6IHRoaXMuc2V0dGluZ3MuY2l0YXRpb25MbG1Nb2RlbCxcbiAgICAgIFJFU0VBUkNIX0FHRU5UX0xMTV9NT0RFTDogdGhpcy5zZXR0aW5ncy5yZXNlYXJjaEFnZW50TGxtTW9kZWwsXG5cbiAgICAgIC8vIE1vZGVsIFNldHRpbmdzXG4gICAgICBNT0RFTF9URU1QRVJBVFVSRTogdGhpcy5zZXR0aW5ncy5tb2RlbFRlbXBlcmF0dXJlLnRvU3RyaW5nKCksXG4gICAgICBNT0RFTF9NQVhfVE9LRU5TOiB0aGlzLnNldHRpbmdzLm1vZGVsTWF4VG9rZW5zLnRvU3RyaW5nKCksXG5cbiAgICAgIC8vIExvZ2dpbmdcbiAgICAgIExPR19MRVZFTDogdGhpcy5zZXR0aW5ncy5sb2dMZXZlbCxcbiAgICB9O1xuXG4gICAgLy8gUmVtb3ZlIHVuZGVmaW5lZCB2YWx1ZXNcbiAgICBPYmplY3Qua2V5cyhlbnZWYXJzKS5mb3JFYWNoKGtleSA9PiB7XG4gICAgICBpZiAoZW52VmFyc1trZXldID09PSB1bmRlZmluZWQgfHwgZW52VmFyc1trZXldID09PSBudWxsIHx8IGVudlZhcnNba2V5XSA9PT0gJycpIHtcbiAgICAgICAgZGVsZXRlIGVudlZhcnNba2V5XTtcbiAgICAgIH1cbiAgICB9KTtcblxuICAgIHRoaXMucHJvY2VzcyA9IHNwYXduKGNtZCwgYXJncywge1xuICAgICAgICAvLyBTZXQgd29ya2luZyBkaXJlY3RvcnkgdG8gd29ya3NwYWNlIGRpcmVjdG9yeSBpZiBjb25maWd1cmVkXG4gICAgICAgIGN3ZDogdGhpcy5zZXR0aW5ncy53b3Jrc3BhY2VEaXIgfHwgdW5kZWZpbmVkLFxuICAgICAgICAvLyBTZXQgZW52aXJvbm1lbnQgdmFyaWFibGVzIGZyb20gcGx1Z2luIHNldHRpbmdzXG4gICAgICAgIGVudjogZW52VmFyc1xuICAgIH0pO1xuXG4gICAgdGhpcy5wcm9jZXNzLnN0ZG91dC5vbignZGF0YScsIChkYXRhKSA9PiB7XG4gICAgICAgIGNvbnN0IG91dHB1dCA9IGRhdGEudG9TdHJpbmcoKTtcbiAgICAgICAgY29uc29sZS5sb2coJ1Rob3RoIEFnZW50OicsIG91dHB1dCk7XG5cbiAgICAgICAgLy8gQ2hlY2sgZm9yIHN0YXJ0dXAgc3VjY2VzcyBpbmRpY2F0b3JzXG4gICAgICAgIGlmIChvdXRwdXQuaW5jbHVkZXMoJ1V2aWNvcm4gcnVubmluZyBvbicpIHx8IG91dHB1dC5pbmNsdWRlcygnQXBwbGljYXRpb24gc3RhcnR1cCBjb21wbGV0ZScpKSB7XG4gICAgICAgICAgbmV3IE5vdGljZSgnVGhvdGggQVBJIHNlcnZlciBzdGFydGVkIHN1Y2Nlc3NmdWxseSEnKTtcbiAgICAgICAgfVxuICAgIH0pO1xuXG4gICAgdGhpcy5wcm9jZXNzLnN0ZGVyci5vbignZGF0YScsIChkYXRhKSA9PiB7XG4gICAgICAgIGNvbnN0IGVycm9yID0gZGF0YS50b1N0cmluZygpO1xuICAgICAgICBjb25zb2xlLmVycm9yKCdUaG90aCBBZ2VudCBFcnJvcjonLCBlcnJvcik7XG5cbiAgICAgICAgLy8gU2hvdyBzcGVjaWZpYyBlcnJvciBtZXNzYWdlcyB0byB1c2VyXG4gICAgICAgIGlmIChlcnJvci5pbmNsdWRlcygnQVBJIGtleScpKSB7XG4gICAgICAgICAgbmV3IE5vdGljZSgnQVBJIGtleSBlcnJvciAtIGNoZWNrIHlvdXIgY29uZmlndXJhdGlvbicpO1xuICAgICAgICB9IGVsc2UgaWYgKGVycm9yLmluY2x1ZGVzKCdQZXJtaXNzaW9uIGRlbmllZCcpIHx8IGVycm9yLmluY2x1ZGVzKCdjb21tYW5kIG5vdCBmb3VuZCcpKSB7XG4gICAgICAgICAgbmV3IE5vdGljZSgnSW5zdGFsbGF0aW9uIGVycm9yIC0gaXMgdXYgYW5kIHRob3RoIGluc3RhbGxlZD8nKTtcbiAgICAgICAgfSBlbHNlIGlmIChlcnJvci5pbmNsdWRlcygnQWRkcmVzcyBhbHJlYWR5IGluIHVzZScpKSB7XG4gICAgICAgICAgbmV3IE5vdGljZShgUG9ydCAke3RoaXMuc2V0dGluZ3MuZW5kcG9pbnRQb3J0fSBhbHJlYWR5IGluIHVzZSAtIHRyeSBhIGRpZmZlcmVudCBwb3J0YCk7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgbmV3IE5vdGljZShgVGhvdGggQWdlbnQgRXJyb3I6ICR7ZXJyb3Iuc2xpY2UoMCwgMTAwKX0uLi5gKTtcbiAgICAgICAgfVxuICAgICAgfSk7XG5cbiAgICAgIHRoaXMucHJvY2Vzcy5vbignY2xvc2UnLCAoY29kZSkgPT4ge1xuICAgICAgICB0aGlzLnByb2Nlc3MgPSBudWxsO1xuICAgICAgICB0aGlzLmlzQWdlbnRSdW5uaW5nID0gZmFsc2U7XG4gICAgICAgIHRoaXMudXBkYXRlU3RhdHVzQmFyKCk7XG5cbiAgICAgICAgaWYgKGNvZGUgIT09IDApIHtcbiAgICAgICAgICBuZXcgTm90aWNlKGBUaG90aCBhZ2VudCBzdG9wcGVkIHdpdGggY29kZSAke2NvZGV9YCk7XG4gICAgICAgICAgY29uc29sZS5lcnJvcihgVGhvdGggYWdlbnQgZXhpdGVkIHdpdGggY29kZTogJHtjb2RlfWApO1xuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgIG5ldyBOb3RpY2UoJ1Rob3RoIGFnZW50IHN0b3BwZWQgbm9ybWFsbHknKTtcbiAgICAgICAgfVxuICAgICAgfSk7XG5cbiAgICAgIHRoaXMucHJvY2Vzcy5vbignZXJyb3InLCAoZXJyb3IpID0+IHtcbiAgICAgICAgY29uc29sZS5lcnJvcignRmFpbGVkIHRvIHN0YXJ0IFRob3RoIGFnZW50OicsIGVycm9yKTtcblxuICAgICAgICAvLyBQcm92aWRlIHNwZWNpZmljIGVycm9yIG1lc3NhZ2VzXG4gICAgICAgIGlmIChlcnJvci5tZXNzYWdlLmluY2x1ZGVzKCdFTk9FTlQnKSkge1xuICAgICAgICAgIG5ldyBOb3RpY2UoJ0ZhaWxlZCB0byBzdGFydCBUaG90aCBhZ2VudDogdXYgY29tbWFuZCBub3QgZm91bmQuIFBsZWFzZSBpbnN0YWxsIHV2IGZpcnN0LicpO1xuICAgICAgICB9IGVsc2UgaWYgKGVycm9yLm1lc3NhZ2UuaW5jbHVkZXMoJ0VBQ0NFUycpKSB7XG4gICAgICAgICAgbmV3IE5vdGljZSgnRmFpbGVkIHRvIHN0YXJ0IFRob3RoIGFnZW50OiBQZXJtaXNzaW9uIGRlbmllZC4gQ2hlY2sgZmlsZSBwZXJtaXNzaW9ucy4nKTtcbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICBuZXcgTm90aWNlKGBGYWlsZWQgdG8gc3RhcnQgVGhvdGggYWdlbnQ6ICR7ZXJyb3IubWVzc2FnZX1gKTtcbiAgICAgICAgfVxuXG4gICAgICAgIHRoaXMucHJvY2VzcyA9IG51bGw7XG4gICAgICAgIHRoaXMuaXNBZ2VudFJ1bm5pbmcgPSBmYWxzZTtcbiAgICAgICAgdGhpcy51cGRhdGVTdGF0dXNCYXIoKTtcbiAgICAgIH0pO1xuXG4gICAgICB0aGlzLmlzQWdlbnRSdW5uaW5nID0gdHJ1ZTtcbiAgICAgIHRoaXMudXBkYXRlU3RhdHVzQmFyKCk7XG4gICAgICBuZXcgTm90aWNlKCdTdGFydGluZyBUaG90aCBhZ2VudC4uLiBUaGlzIG1heSB0YWtlIGEgbW9tZW50LicpO1xuXG4gICAgICAvLyBXYWl0IGEgYml0IHRoZW4gY2hlY2sgaWYgaXQgYWN0dWFsbHkgc3RhcnRlZFxuICAgICAgc2V0VGltZW91dChhc3luYyAoKSA9PiB7XG4gICAgICAgIGNvbnN0IGhlYWx0aHkgPSBhd2FpdCB0aGlzLmNoZWNrQWdlbnRIZWFsdGgoKTtcbiAgICAgICAgaWYgKCFoZWFsdGh5ICYmIHRoaXMuaXNBZ2VudFJ1bm5pbmcpIHtcbiAgICAgICAgICBuZXcgTm90aWNlKCdUaG90aCBhZ2VudCBwcm9jZXNzIHN0YXJ0ZWQgYnV0IEFQSSBub3QgcmVzcG9uZGluZy4gQ2hlY2sgY29uc29sZSBmb3IgZXJyb3JzLicpO1xuICAgICAgICB9XG4gICAgICB9LCA1MDAwKTtcblxuICAgIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgICBjb25zb2xlLmVycm9yKCdFcnJvciBzdGFydGluZyBhZ2VudDonLCBlcnJvcik7XG4gICAgICBuZXcgTm90aWNlKGBGYWlsZWQgdG8gc3RhcnQgVGhvdGggYWdlbnQ6ICR7ZXJyb3IubWVzc2FnZX1gKTtcbiAgICB9XG4gIH1cblxuICBzdG9wQWdlbnQoKTogdm9pZCB7XG4gICAgaWYgKHRoaXMuc2V0dGluZ3MucmVtb3RlTW9kZSkge1xuICAgICAgLy8gSW4gcmVtb3RlIG1vZGUsIHdlIGp1c3QgZGlzY29ubmVjdFxuICAgICAgdGhpcy5pc0FnZW50UnVubmluZyA9IGZhbHNlO1xuICAgICAgdGhpcy51cGRhdGVTdGF0dXNCYXIoKTtcbiAgICAgIG5ldyBOb3RpY2UoJ0Rpc2Nvbm5lY3RlZCBmcm9tIHJlbW90ZSBUaG90aCBzZXJ2ZXInKTtcbiAgICAgIHJldHVybjtcbiAgICB9XG5cbiAgICBpZiAoIXRoaXMucHJvY2Vzcykge1xuICAgICAgbmV3IE5vdGljZSgnVGhvdGggYWdlbnQgaXMgbm90IHJ1bm5pbmcnKTtcbiAgICAgIHJldHVybjtcbiAgICB9XG5cbiAgICB0aGlzLnByb2Nlc3Mua2lsbCgnU0lHVEVSTScpO1xuICAgIHNldFRpbWVvdXQoKCkgPT4ge1xuICAgICAgaWYgKHRoaXMucHJvY2Vzcykge1xuICAgICAgICB0aGlzLnByb2Nlc3Mua2lsbCgnU0lHS0lMTCcpO1xuICAgICAgfVxuICAgIH0sIDUwMDApO1xuXG4gICAgICB0aGlzLnByb2Nlc3MgPSBudWxsO1xuICAgIHRoaXMuaXNBZ2VudFJ1bm5pbmcgPSBmYWxzZTtcbiAgICB0aGlzLnVwZGF0ZVN0YXR1c0JhcigpO1xuICAgIG5ldyBOb3RpY2UoJ1Rob3RoIGFnZW50IHN0b3BwZWQnKTtcbiAgfVxuXG4gIGFzeW5jIHJlc3RhcnRBZ2VudCgpOiBQcm9taXNlPHZvaWQ+IHtcbiAgICBpZiAodGhpcy5pc0FnZW50UnVubmluZykge1xuICAgICAgdGhpcy5zdG9wQWdlbnQoKTtcbiAgICAgIC8vIFdhaXQgYSBtb21lbnQgYmVmb3JlIHJlc3RhcnRpbmdcbiAgICAgIHNldFRpbWVvdXQoKCkgPT4gdGhpcy5zdGFydEFnZW50KCksIDEwMDApO1xuICAgIH0gZWxzZSB7XG4gICAgICBhd2FpdCB0aGlzLnN0YXJ0QWdlbnQoKTtcbiAgICB9XG4gIH1cblxuICBhc3luYyBwZXJmb3JtUmVzZWFyY2gocXVlcnk6IHN0cmluZyk6IFByb21pc2U8dm9pZD4ge1xuICAgIGlmICghdGhpcy5pc0FnZW50UnVubmluZykge1xuICAgICAgbmV3IE5vdGljZSgnUGxlYXNlIHN0YXJ0IHRoZSBUaG90aCBhZ2VudCBmaXJzdCcpO1xuICAgICAgcmV0dXJuO1xuICAgIH1cblxuICAgIG5ldyBOb3RpY2UoYFJlc2VhcmNoaW5nOiBcIiR7cXVlcnkuc2xpY2UoMCwgNTApfS4uLlwiYCk7XG5cbiAgICB0cnkge1xuICAgICAgLy8gVHJ5IGRpcmVjdCByZXNlYXJjaCBBUEkgY2FsbCBmaXJzdFxuICAgICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCB0aGlzLmNhbGxSZXNlYXJjaEFQSShxdWVyeSk7XG4gICAgICBpZiAocmVzcG9uc2UpIHtcbiAgICAgICAgLy8gSW5zZXJ0IHJlc2VhcmNoIHJlc3VsdHMgZGlyZWN0bHkgaW50byB0aGUgY3VycmVudCBub3RlXG4gICAgICAgIGF3YWl0IHRoaXMuaW5zZXJ0UmVzZWFyY2hSZXN1bHRzKHF1ZXJ5LCByZXNwb25zZSk7XG4gICAgICAgIHJldHVybjtcbiAgICAgIH1cbiAgICB9IGNhdGNoIChlcnJvcikge1xuICAgICAgY29uc29sZS5lcnJvcignRGlyZWN0IHJlc2VhcmNoIGZhaWxlZDonLCBlcnJvcik7XG4gICAgICBuZXcgTm90aWNlKCdEaXJlY3QgcmVzZWFyY2ggZmFpbGVkLCBvcGVuaW5nIGNoYXQgaW50ZXJmYWNlLi4uJyk7XG4gICAgfVxuXG4gICAgLy8gRmFsbGJhY2sgdG8gY2hhdCBtb2RhbFxuICAgIGNvbnN0IG1vZGFsID0gbmV3IENoYXRNb2RhbCh0aGlzLmFwcCwgdGhpcyk7XG4gICAgbW9kYWwuc2V0SW5pdGlhbFF1ZXJ5KHF1ZXJ5KTtcbiAgICBtb2RhbC5vcGVuKCk7XG4gIH1cblxuICBwcml2YXRlIGFzeW5jIGNhbGxSZXNlYXJjaEFQSShxdWVyeTogc3RyaW5nKTogUHJvbWlzZTxzdHJpbmcgfCBudWxsPiB7XG4gICAgY29uc3QgYXBpVXJsID0gYCR7dGhpcy5zZXR0aW5ncy5lbmRwb2ludEJhc2VVcmx9L3Jlc2VhcmNoL3F1ZXJ5YDtcblxuICAgIHRyeSB7XG4gICAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGZldGNoKGFwaVVybCwge1xuICAgICAgICBtZXRob2Q6ICdQT1NUJyxcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgIH0sXG4gICAgICAgIGJvZHk6IEpTT04uc3RyaW5naWZ5KHtcbiAgICAgICAgICBxdWVyeTogcXVlcnksXG4gICAgICAgICAgdHlwZTogJ3F1aWNrX3Jlc2VhcmNoJyxcbiAgICAgICAgICBtYXhfcmVzdWx0czogNSxcbiAgICAgICAgICBpbmNsdWRlX2NpdGF0aW9uczogdHJ1ZSxcbiAgICAgICAgfSksXG4gICAgICB9KTtcblxuICAgICAgaWYgKCFyZXNwb25zZS5vaykge1xuICAgICAgICByZXR1cm4gbnVsbDtcbiAgICAgIH1cblxuICAgICAgY29uc3QgZGF0YSA9IGF3YWl0IHJlc3BvbnNlLmpzb24oKTtcbiAgICAgIHJldHVybiBkYXRhLnJlc3VsdHMgfHwgZGF0YS5yZXNwb25zZSB8fCBudWxsO1xuXG4gICAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICAgIGNvbnNvbGUuZXJyb3IoJ1Jlc2VhcmNoIEFQSSBjYWxsIGZhaWxlZDonLCBlcnJvcik7XG4gICAgICByZXR1cm4gbnVsbDtcbiAgICB9XG4gIH1cblxuICAgIHByaXZhdGUgYXN5bmMgaW5zZXJ0UmVzZWFyY2hSZXN1bHRzKHF1ZXJ5OiBzdHJpbmcsIHJlc3VsdHM6IHN0cmluZyk6IFByb21pc2U8dm9pZD4ge1xuICAgIC8vIEdldCB0aGUgYWN0aXZlIGVkaXRvclxuICAgIGNvbnN0IGFjdGl2ZUxlYWYgPSB0aGlzLmFwcC53b3Jrc3BhY2UuYWN0aXZlTGVhZjtcbiAgICBpZiAoIWFjdGl2ZUxlYWYgfHwgIWFjdGl2ZUxlYWYudmlldyB8fCBhY3RpdmVMZWFmLnZpZXcuZ2V0Vmlld1R5cGUoKSAhPT0gJ21hcmtkb3duJykge1xuICAgICAgbmV3IE5vdGljZSgnTm8gYWN0aXZlIG1hcmtkb3duIGVkaXRvciBmb3VuZCcpO1xuICAgICAgcmV0dXJuO1xuICAgIH1cblxuICAgIGNvbnN0IHZpZXcgPSBhY3RpdmVMZWFmLnZpZXcgYXMgYW55OyAvLyBUeXBlIGFzc2VydGlvbiBmb3IgZWRpdG9yIGFjY2Vzc1xuICAgIGlmICghdmlldy5lZGl0b3IpIHtcbiAgICAgIG5ldyBOb3RpY2UoJ05vIGVkaXRvciBhdmFpbGFibGUgaW4gYWN0aXZlIHZpZXcnKTtcbiAgICAgIHJldHVybjtcbiAgICB9XG5cbiAgICBjb25zdCBlZGl0b3IgPSB2aWV3LmVkaXRvcjtcbiAgICBjb25zdCBjdXJzb3IgPSBlZGl0b3IuZ2V0Q3Vyc29yKCk7XG5cbiAgICAvLyBGb3JtYXQgdGhlIHJlc2VhcmNoIHJlc3VsdHNcbiAgICBjb25zdCB0aW1lc3RhbXAgPSBuZXcgRGF0ZSgpLnRvTG9jYWxlU3RyaW5nKCk7XG4gICAgY29uc3QgcmVzZWFyY2hCbG9jayA9IFtcbiAgICAgICcnLFxuICAgICAgYCMjIPCflI0gUmVzZWFyY2g6ICR7cXVlcnl9YCxcbiAgICAgIGAqR2VuZXJhdGVkIG9uICR7dGltZXN0YW1wfSBieSBUaG90aCBSZXNlYXJjaCBBc3Npc3RhbnQqYCxcbiAgICAgICcnLFxuICAgICAgcmVzdWx0cyxcbiAgICAgICcnLFxuICAgICAgJy0tLScsXG4gICAgICAnJ1xuICAgIF0uam9pbignXFxuJyk7XG5cbiAgICAvLyBJbnNlcnQgYXQgY3Vyc29yIHBvc2l0aW9uXG4gICAgZWRpdG9yLnJlcGxhY2VSYW5nZShyZXNlYXJjaEJsb2NrLCBjdXJzb3IpO1xuICAgIG5ldyBOb3RpY2UoJ1Jlc2VhcmNoIHJlc3VsdHMgaW5zZXJ0ZWQhJyk7XG4gIH1cblxuICAgIGFzeW5jIGNoZWNrQWdlbnRIZWFsdGgoKTogUHJvbWlzZTxib29sZWFuPiB7XG4gICAgdHJ5IHtcbiAgICAgIGNvbnN0IGNvbnRyb2xsZXIgPSBuZXcgQWJvcnRDb250cm9sbGVyKCk7XG4gICAgICBjb25zdCB0aW1lb3V0SWQgPSBzZXRUaW1lb3V0KCgpID0+IGNvbnRyb2xsZXIuYWJvcnQoKSwgNTAwMCk7XG5cbiAgICAgIC8vIENoZWNrIGJhc2ljIGhlYWx0aCBlbmRwb2ludFxuICAgICAgY29uc3QgaGVhbHRoUmVzcG9uc2UgPSBhd2FpdCBmZXRjaChgJHt0aGlzLnNldHRpbmdzLmVuZHBvaW50QmFzZVVybH0vaGVhbHRoYCwge1xuICAgICAgICBtZXRob2Q6ICdHRVQnLFxuICAgICAgICBzaWduYWw6IGNvbnRyb2xsZXIuc2lnbmFsLFxuICAgICAgfSk7XG5cbiAgICAgIGNsZWFyVGltZW91dCh0aW1lb3V0SWQpO1xuXG4gICAgICBpZiAoIWhlYWx0aFJlc3BvbnNlLm9rKSB7XG4gICAgICAgIHJldHVybiBmYWxzZTtcbiAgICAgIH1cblxuICAgICAgLy8gQWxzbyBjaGVjayBpZiB0aGUgYWdlbnQgaXMgaW5pdGlhbGl6ZWQgYnkgdGVzdGluZyBhZ2VudCBzdGF0dXNcbiAgICAgIHRyeSB7XG4gICAgICAgIGNvbnN0IGFnZW50Q29udHJvbGxlciA9IG5ldyBBYm9ydENvbnRyb2xsZXIoKTtcbiAgICAgICAgY29uc3QgYWdlbnRUaW1lb3V0SWQgPSBzZXRUaW1lb3V0KCgpID0+IGFnZW50Q29udHJvbGxlci5hYm9ydCgpLCAzMDAwKTtcblxuICAgICAgICBjb25zdCBhZ2VudFJlc3BvbnNlID0gYXdhaXQgZmV0Y2goYCR7dGhpcy5zZXR0aW5ncy5lbmRwb2ludEJhc2VVcmx9L2FnZW50L3N0YXR1c2AsIHtcbiAgICAgICAgICBtZXRob2Q6ICdHRVQnLFxuICAgICAgICAgIHNpZ25hbDogYWdlbnRDb250cm9sbGVyLnNpZ25hbCxcbiAgICAgICAgfSk7XG5cbiAgICAgICAgY2xlYXJUaW1lb3V0KGFnZW50VGltZW91dElkKTtcblxuICAgICAgICBpZiAoYWdlbnRSZXNwb25zZS5vaykge1xuICAgICAgICAgIGNvbnN0IGRhdGEgPSBhd2FpdCBhZ2VudFJlc3BvbnNlLmpzb24oKTtcbiAgICAgICAgICByZXR1cm4gZGF0YS5hZ2VudF9pbml0aWFsaXplZCA9PT0gdHJ1ZTtcbiAgICAgICAgfVxuICAgICAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICAgICAgLy8gQWdlbnQgc3RhdHVzIGNoZWNrIGZhaWxlZCwgYnV0IGJhc2ljIGhlYWx0aCBwYXNzZWRcbiAgICAgICAgY29uc29sZS53YXJuKCdBZ2VudCBzdGF0dXMgY2hlY2sgZmFpbGVkOicsIGVycm9yKTtcbiAgICAgIH1cblxuICAgICAgcmV0dXJuIHRydWU7IC8vIEJhc2ljIGhlYWx0aCBjaGVjayBwYXNzZWRcbiAgICB9IGNhdGNoIChlcnJvcikge1xuICAgICAgcmV0dXJuIGZhbHNlO1xuICAgIH1cbiAgfVxuXG4gIG9wZW5DaGF0KCkge1xuICAgIG5ldyBDaGF0TW9kYWwodGhpcy5hcHAsIHRoaXMpLm9wZW4oKTtcbiAgfVxufVxuXG5jbGFzcyBUaG90aFNldHRpbmdUYWIgZXh0ZW5kcyBQbHVnaW5TZXR0aW5nVGFiIHtcbiAgcGx1Z2luOiBUaG90aFBsdWdpbjtcblxuICBjb25zdHJ1Y3RvcihhcHA6IEFwcCwgcGx1Z2luOiBUaG90aFBsdWdpbikge1xuICAgIHN1cGVyKGFwcCwgcGx1Z2luKTtcbiAgICB0aGlzLnBsdWdpbiA9IHBsdWdpbjtcbiAgfVxuXG4gIGRpc3BsYXkoKTogdm9pZCB7XG4gICAgY29uc3QgeyBjb250YWluZXJFbCB9ID0gdGhpcztcbiAgICBjb250YWluZXJFbC5lbXB0eSgpO1xuXG4gICAgY29udGFpbmVyRWwuY3JlYXRlRWwoJ2gyJywgeyB0ZXh0OiAnVGhvdGggUmVzZWFyY2ggQXNzaXN0YW50IFNldHRpbmdzJyB9KTtcblxuICAgIC8vIEFQSSBLZXlzIFNlY3Rpb25cbiAgICBjb250YWluZXJFbC5jcmVhdGVFbCgnaDMnLCB7IHRleHQ6ICfwn5SRIEFQSSBDb25maWd1cmF0aW9uJyB9KTtcblxuICAgIG5ldyBTZXR0aW5nKGNvbnRhaW5lckVsKVxuICAgICAgLnNldE5hbWUoJ01pc3RyYWwgQVBJIEtleScpXG4gICAgICAuc2V0RGVzYygnWW91ciBNaXN0cmFsIEFQSSBrZXkgZm9yIEFJLXBvd2VyZWQgcmVzZWFyY2gnKVxuICAgICAgLmFkZFRleHQoKHRleHQpID0+XG4gICAgICAgIHRleHRcbiAgICAgICAgICAuc2V0UGxhY2Vob2xkZXIoJ0VudGVyIE1pc3RyYWwgQVBJIGtleScpXG4gICAgICAgICAgLnNldFZhbHVlKHRoaXMucGx1Z2luLnNldHRpbmdzLm1pc3RyYWxLZXkpXG4gICAgICAgICAgLm9uQ2hhbmdlKGFzeW5jICh2YWx1ZSkgPT4ge1xuICAgICAgICAgICAgdGhpcy5wbHVnaW4uc2V0dGluZ3MubWlzdHJhbEtleSA9IHZhbHVlO1xuICAgICAgICAgICAgYXdhaXQgdGhpcy5wbHVnaW4uc2F2ZVNldHRpbmdzKCk7XG4gICAgICAgICAgfSlcbiAgICAgICk7XG5cbiAgICBuZXcgU2V0dGluZyhjb250YWluZXJFbClcbiAgICAgIC5zZXROYW1lKCdPcGVuUm91dGVyIEFQSSBLZXknKVxuICAgICAgLnNldERlc2MoJ1lvdXIgT3BlblJvdXRlciBBUEkga2V5IGZvciBhY2Nlc3NpbmcgbXVsdGlwbGUgQUkgbW9kZWxzJylcbiAgICAgIC5hZGRUZXh0KCh0ZXh0KSA9PlxuICAgICAgICB0ZXh0XG4gICAgICAgICAgLnNldFBsYWNlaG9sZGVyKCdFbnRlciBPcGVuUm91dGVyIEFQSSBrZXknKVxuICAgICAgICAgIC5zZXRWYWx1ZSh0aGlzLnBsdWdpbi5zZXR0aW5ncy5vcGVucm91dGVyS2V5KVxuICAgICAgICAgIC5vbkNoYW5nZShhc3luYyAodmFsdWUpID0+IHtcbiAgICAgICAgICAgIHRoaXMucGx1Z2luLnNldHRpbmdzLm9wZW5yb3V0ZXJLZXkgPSB2YWx1ZTtcbiAgICAgICAgICAgIGF3YWl0IHRoaXMucGx1Z2luLnNhdmVTZXR0aW5ncygpO1xuICAgICAgICAgIH0pXG4gICAgICApO1xuXG4gICAgbmV3IFNldHRpbmcoY29udGFpbmVyRWwpXG4gICAgICAuc2V0TmFtZSgnT3BlbkNpdGF0aW9ucyBBUEkgS2V5JylcbiAgICAgIC5zZXREZXNjKCdBUEkga2V5IGZvciBjaXRhdGlvbiBzZXJ2aWNlcycpXG4gICAgICAuYWRkVGV4dCgodGV4dCkgPT5cbiAgICAgICAgdGV4dFxuICAgICAgICAgIC5zZXRQbGFjZWhvbGRlcignRW50ZXIgT3BlbkNpdGF0aW9ucyBBUEkga2V5JylcbiAgICAgICAgICAuc2V0VmFsdWUodGhpcy5wbHVnaW4uc2V0dGluZ3Mub3BlbmNpdGF0aW9uc0tleSlcbiAgICAgICAgICAub25DaGFuZ2UoYXN5bmMgKHZhbHVlKSA9PiB7XG4gICAgICAgICAgICB0aGlzLnBsdWdpbi5zZXR0aW5ncy5vcGVuY2l0YXRpb25zS2V5ID0gdmFsdWU7XG4gICAgICAgICAgICBhd2FpdCB0aGlzLnBsdWdpbi5zYXZlU2V0dGluZ3MoKTtcbiAgICAgICAgICB9KVxuICAgICAgKTtcblxuICAgIG5ldyBTZXR0aW5nKGNvbnRhaW5lckVsKVxuICAgICAgLnNldE5hbWUoJ0dvb2dsZSBBUEkgS2V5JylcbiAgICAgIC5zZXREZXNjKCdHb29nbGUgQVBJIGtleSBmb3Igc2VhcmNoIHNlcnZpY2VzJylcbiAgICAgIC5hZGRUZXh0KCh0ZXh0KSA9PlxuICAgICAgICB0ZXh0XG4gICAgICAgICAgLnNldFBsYWNlaG9sZGVyKCdFbnRlciBHb29nbGUgQVBJIGtleScpXG4gICAgICAgICAgLnNldFZhbHVlKHRoaXMucGx1Z2luLnNldHRpbmdzLmdvb2dsZUFwaUtleSlcbiAgICAgICAgICAub25DaGFuZ2UoYXN5bmMgKHZhbHVlKSA9PiB7XG4gICAgICAgICAgICB0aGlzLnBsdWdpbi5zZXR0aW5ncy5nb29nbGVBcGlLZXkgPSB2YWx1ZTtcbiAgICAgICAgICAgIGF3YWl0IHRoaXMucGx1Z2luLnNhdmVTZXR0aW5ncygpO1xuICAgICAgICAgIH0pXG4gICAgICApO1xuXG4gICAgbmV3IFNldHRpbmcoY29udGFpbmVyRWwpXG4gICAgICAuc2V0TmFtZSgnR29vZ2xlIFNlYXJjaCBFbmdpbmUgSUQnKVxuICAgICAgLnNldERlc2MoJ0N1c3RvbSBzZWFyY2ggZW5naW5lIElEJylcbiAgICAgIC5hZGRUZXh0KCh0ZXh0KSA9PlxuICAgICAgICB0ZXh0XG4gICAgICAgICAgLnNldFBsYWNlaG9sZGVyKCdFbnRlciBzZWFyY2ggZW5naW5lIElEJylcbiAgICAgICAgICAuc2V0VmFsdWUodGhpcy5wbHVnaW4uc2V0dGluZ3MuZ29vZ2xlU2VhcmNoRW5naW5lSWQpXG4gICAgICAgICAgLm9uQ2hhbmdlKGFzeW5jICh2YWx1ZSkgPT4ge1xuICAgICAgICAgICAgdGhpcy5wbHVnaW4uc2V0dGluZ3MuZ29vZ2xlU2VhcmNoRW5naW5lSWQgPSB2YWx1ZTtcbiAgICAgICAgICAgIGF3YWl0IHRoaXMucGx1Z2luLnNhdmVTZXR0aW5ncygpO1xuICAgICAgICAgIH0pXG4gICAgICApO1xuXG4gICAgbmV3IFNldHRpbmcoY29udGFpbmVyRWwpXG4gICAgICAuc2V0TmFtZSgnU2VtYW50aWMgU2Nob2xhciBBUEkgS2V5JylcbiAgICAgIC5zZXREZXNjKCdBUEkga2V5IGZvciBTZW1hbnRpYyBTY2hvbGFyIGludGVncmF0aW9uJylcbiAgICAgIC5hZGRUZXh0KCh0ZXh0KSA9PlxuICAgICAgICB0ZXh0XG4gICAgICAgICAgLnNldFBsYWNlaG9sZGVyKCdFbnRlciBTZW1hbnRpYyBTY2hvbGFyIEFQSSBrZXknKVxuICAgICAgICAgIC5zZXRWYWx1ZSh0aGlzLnBsdWdpbi5zZXR0aW5ncy5zZW1hbnRpY3NjaG9sYXJBcGlLZXkpXG4gICAgICAgICAgLm9uQ2hhbmdlKGFzeW5jICh2YWx1ZSkgPT4ge1xuICAgICAgICAgICAgdGhpcy5wbHVnaW4uc2V0dGluZ3Muc2VtYW50aWNzY2hvbGFyQXBpS2V5ID0gdmFsdWU7XG4gICAgICAgICAgICBhd2FpdCB0aGlzLnBsdWdpbi5zYXZlU2V0dGluZ3MoKTtcbiAgICAgICAgICB9KVxuICAgICAgKTtcblxuICAgIC8vIE1vZGVsIENvbmZpZ3VyYXRpb24gU2VjdGlvblxuICAgIGNvbnRhaW5lckVsLmNyZWF0ZUVsKCdoMycsIHsgdGV4dDogJ/CfpJYgTW9kZWwgQ29uZmlndXJhdGlvbicgfSk7XG5cbiAgICBuZXcgU2V0dGluZyhjb250YWluZXJFbClcbiAgICAgIC5zZXROYW1lKCdQcmltYXJ5IExMTSBNb2RlbCcpXG4gICAgICAuc2V0RGVzYygnTWFpbiBsYW5ndWFnZSBtb2RlbCBmb3IgY29udGVudCBhbmFseXNpcycpXG4gICAgICAuYWRkVGV4dCgodGV4dCkgPT5cbiAgICAgICAgdGV4dFxuICAgICAgICAgIC5zZXRQbGFjZWhvbGRlcignZS5nLiwgZ29vZ2xlL2dlbWluaS0yLjUtZmxhc2gtcHJldmlldy0wNS0yMCcpXG4gICAgICAgICAgLnNldFZhbHVlKHRoaXMucGx1Z2luLnNldHRpbmdzLmxsbU1vZGVsKVxuICAgICAgICAgIC5vbkNoYW5nZShhc3luYyAodmFsdWUpID0+IHtcbiAgICAgICAgICAgIHRoaXMucGx1Z2luLnNldHRpbmdzLmxsbU1vZGVsID0gdmFsdWU7XG4gICAgICAgICAgICBhd2FpdCB0aGlzLnBsdWdpbi5zYXZlU2V0dGluZ3MoKTtcbiAgICAgICAgICB9KVxuICAgICAgKTtcblxuICAgIG5ldyBTZXR0aW5nKGNvbnRhaW5lckVsKVxuICAgICAgLnNldE5hbWUoJ0NpdGF0aW9uIExMTSBNb2RlbCcpXG4gICAgICAuc2V0RGVzYygnTGFuZ3VhZ2UgbW9kZWwgZm9yIGNpdGF0aW9uIHRhc2tzJylcbiAgICAgIC5hZGRUZXh0KCh0ZXh0KSA9PlxuICAgICAgICB0ZXh0XG4gICAgICAgICAgLnNldFBsYWNlaG9sZGVyKCdlLmcuLCBnb29nbGUvZ2VtaW5pLWZsYXNoLTEuNS04YicpXG4gICAgICAgICAgLnNldFZhbHVlKHRoaXMucGx1Z2luLnNldHRpbmdzLmNpdGF0aW9uTGxtTW9kZWwpXG4gICAgICAgICAgLm9uQ2hhbmdlKGFzeW5jICh2YWx1ZSkgPT4ge1xuICAgICAgICAgICAgdGhpcy5wbHVnaW4uc2V0dGluZ3MuY2l0YXRpb25MbG1Nb2RlbCA9IHZhbHVlO1xuICAgICAgICAgICAgYXdhaXQgdGhpcy5wbHVnaW4uc2F2ZVNldHRpbmdzKCk7XG4gICAgICAgICAgfSlcbiAgICAgICk7XG5cbiAgICBuZXcgU2V0dGluZyhjb250YWluZXJFbClcbiAgICAgIC5zZXROYW1lKCdNb2RlbCBUZW1wZXJhdHVyZScpXG4gICAgICAuc2V0RGVzYygnQ29udHJvbHMgcmFuZG9tbmVzcyBpbiBBSSByZXNwb25zZXMgKDAuMC0yLjApJylcbiAgICAgIC5hZGRTbGlkZXIoKHNsaWRlcikgPT5cbiAgICAgICAgc2xpZGVyXG4gICAgICAgICAgLnNldExpbWl0cygwLCAyLCAwLjEpXG4gICAgICAgICAgLnNldFZhbHVlKHRoaXMucGx1Z2luLnNldHRpbmdzLm1vZGVsVGVtcGVyYXR1cmUpXG4gICAgICAgICAgLnNldER5bmFtaWNUb29sdGlwKClcbiAgICAgICAgICAub25DaGFuZ2UoYXN5bmMgKHZhbHVlKSA9PiB7XG4gICAgICAgICAgICB0aGlzLnBsdWdpbi5zZXR0aW5ncy5tb2RlbFRlbXBlcmF0dXJlID0gdmFsdWU7XG4gICAgICAgICAgICBhd2FpdCB0aGlzLnBsdWdpbi5zYXZlU2V0dGluZ3MoKTtcbiAgICAgICAgICB9KVxuICAgICAgKTtcblxuICAgIG5ldyBTZXR0aW5nKGNvbnRhaW5lckVsKVxuICAgICAgLnNldE5hbWUoJ01heCBPdXRwdXQgVG9rZW5zJylcbiAgICAgIC5zZXREZXNjKCdNYXhpbXVtIHRva2VucyB0aGUgbW9kZWwgY2FuIGdlbmVyYXRlJylcbiAgICAgIC5hZGRUZXh0KCh0ZXh0KSA9PlxuICAgICAgICB0ZXh0XG4gICAgICAgICAgLnNldFBsYWNlaG9sZGVyKCc1MDAwMCcpXG4gICAgICAgICAgLnNldFZhbHVlKHRoaXMucGx1Z2luLnNldHRpbmdzLmxsbU1heE91dHB1dFRva2Vucy50b1N0cmluZygpKVxuICAgICAgICAgIC5vbkNoYW5nZShhc3luYyAodmFsdWUpID0+IHtcbiAgICAgICAgICAgIHRoaXMucGx1Z2luLnNldHRpbmdzLmxsbU1heE91dHB1dFRva2VucyA9IHBhcnNlSW50KHZhbHVlKSB8fCA1MDAwMDtcbiAgICAgICAgICAgIGF3YWl0IHRoaXMucGx1Z2luLnNhdmVTZXR0aW5ncygpO1xuICAgICAgICAgIH0pXG4gICAgICApO1xuXG4gICAgLy8gQ29ubmVjdGlvbiBTZXR0aW5nc1xuICAgIGNvbnRhaW5lckVsLmNyZWF0ZUVsKCdoMycsIHsgdGV4dDogJ/CfjJAgQ29ubmVjdGlvbiBTZXR0aW5ncycgfSk7XG5cbiAgICBuZXcgU2V0dGluZyhjb250YWluZXJFbClcbiAgICAgIC5zZXROYW1lKCdSZW1vdGUgTW9kZScpXG4gICAgICAuc2V0RGVzYygnQ29ubmVjdCB0byBhIHJlbW90ZSBUaG90aCBzZXJ2ZXIgKGUuZy4sIHJ1bm5pbmcgaW4gV1NMKSBpbnN0ZWFkIG9mIHN0YXJ0aW5nIGxvY2FsbHknKVxuICAgICAgLmFkZFRvZ2dsZSgodG9nZ2xlKSA9PlxuICAgICAgICB0b2dnbGVcbiAgICAgICAgICAuc2V0VmFsdWUodGhpcy5wbHVnaW4uc2V0dGluZ3MucmVtb3RlTW9kZSlcbiAgICAgICAgICAub25DaGFuZ2UoYXN5bmMgKHZhbHVlKSA9PiB7XG4gICAgICAgICAgICB0aGlzLnBsdWdpbi5zZXR0aW5ncy5yZW1vdGVNb2RlID0gdmFsdWU7XG4gICAgICAgICAgICBhd2FpdCB0aGlzLnBsdWdpbi5zYXZlU2V0dGluZ3MoKTtcbiAgICAgICAgICAgIC8vIFJlZnJlc2ggdGhlIGRpc3BsYXkgdG8gc2hvdy9oaWRlIHJlbGV2YW50IHNldHRpbmdzXG4gICAgICAgICAgICB0aGlzLmRpc3BsYXkoKTtcbiAgICAgICAgICB9KVxuICAgICAgKTtcblxuICAgIGlmICh0aGlzLnBsdWdpbi5zZXR0aW5ncy5yZW1vdGVNb2RlKSB7XG4gICAgICBuZXcgU2V0dGluZyhjb250YWluZXJFbClcbiAgICAgICAgLnNldE5hbWUoJ1JlbW90ZSBFbmRwb2ludCBVUkwnKVxuICAgICAgICAuc2V0RGVzYygnRnVsbCBVUkwgb2YgdGhlIHJlbW90ZSBUaG90aCBzZXJ2ZXIgKGUuZy4sIGh0dHA6Ly9sb2NhbGhvc3Q6ODAwMCBvciBodHRwOi8vV1NMX0lQOjgwMDApJylcbiAgICAgICAgLmFkZFRleHQoKHRleHQpID0+XG4gICAgICAgICAgdGV4dFxuICAgICAgICAgICAgLnNldFBsYWNlaG9sZGVyKCdodHRwOi8vbG9jYWxob3N0OjgwMDAnKVxuICAgICAgICAgICAgLnNldFZhbHVlKHRoaXMucGx1Z2luLnNldHRpbmdzLnJlbW90ZUVuZHBvaW50VXJsKVxuICAgICAgICAgICAgLm9uQ2hhbmdlKGFzeW5jICh2YWx1ZSkgPT4ge1xuICAgICAgICAgICAgICB0aGlzLnBsdWdpbi5zZXR0aW5ncy5yZW1vdGVFbmRwb2ludFVybCA9IHZhbHVlO1xuICAgICAgICAgICAgICAvLyBBbHNvIHVwZGF0ZSB0aGUgYmFzZSBVUkwgdG8gbWF0Y2hcbiAgICAgICAgICAgICAgdGhpcy5wbHVnaW4uc2V0dGluZ3MuZW5kcG9pbnRCYXNlVXJsID0gdmFsdWU7XG4gICAgICAgICAgICAgIGF3YWl0IHRoaXMucGx1Z2luLnNhdmVTZXR0aW5ncygpO1xuICAgICAgICAgICAgfSlcbiAgICAgICAgKTtcblxuICAgICAgLy8gQWRkIGluZm8gYWJvdXQgV1NMIHNldHVwXG4gICAgICBjb25zdCBpbmZvRWwgPSBjb250YWluZXJFbC5jcmVhdGVEaXYoKTtcbiAgICAgIGluZm9FbC5pbm5lckhUTUwgPSBgXG4gICAgICAgIDxkaXYgc3R5bGU9XCJtYXJnaW46IDEwcHggMDsgcGFkZGluZzogMTBweDsgYmFja2dyb3VuZDogI2YwZjhmZjsgYm9yZGVyLWxlZnQ6IDRweCBzb2xpZCAjMDA3YWNjOyBib3JkZXItcmFkaXVzOiA0cHg7XCI+XG4gICAgICAgICAgPHN0cm9uZz5XU0wgU2V0dXA6PC9zdHJvbmc+PGJyLz5cbiAgICAgICAgICAxLiBTdGFydCBUaG90aCBpbiBXU0w6IDxjb2RlPnV2IHJ1biBweXRob24gLW0gdGhvdGggYXBpIC0taG9zdCAwLjAuMC4wIC0tcG9ydCA4MDAwPC9jb2RlPjxici8+XG4gICAgICAgICAgMi4gRmluZCBXU0wgSVA6IDxjb2RlPmhvc3RuYW1lIC1JPC9jb2RlPjxici8+XG4gICAgICAgICAgMy4gVXNlIFVSTDogPGNvZGU+aHR0cDovL1dTTF9JUDo4MDAwPC9jb2RlPjxici8+XG4gICAgICAgICAgT3IgdXNlIDxjb2RlPmh0dHA6Ly9sb2NhbGhvc3Q6ODAwMDwvY29kZT4gaWYgcG9ydCBpcyBmb3J3YXJkZWQuXG4gICAgICAgIDwvZGl2PlxuICAgICAgYDtcbiAgICB9IGVsc2Uge1xuICAgICAgbmV3IFNldHRpbmcoY29udGFpbmVyRWwpXG4gICAgICAgIC5zZXROYW1lKCdFbmRwb2ludCBIb3N0JylcbiAgICAgICAgLnNldERlc2MoJ0hvc3QgYWRkcmVzcyBmb3IgdGhlIFRob3RoIGFnZW50JylcbiAgICAgICAgLmFkZFRleHQoKHRleHQpID0+XG4gICAgICAgICAgdGV4dFxuICAgICAgICAgICAgLnNldFBsYWNlaG9sZGVyKCcxMjcuMC4wLjEnKVxuICAgICAgICAgICAgLnNldFZhbHVlKHRoaXMucGx1Z2luLnNldHRpbmdzLmVuZHBvaW50SG9zdClcbiAgICAgICAgICAgIC5vbkNoYW5nZShhc3luYyAodmFsdWUpID0+IHtcbiAgICAgICAgICAgICAgdGhpcy5wbHVnaW4uc2V0dGluZ3MuZW5kcG9pbnRIb3N0ID0gdmFsdWU7XG4gICAgICAgICAgICAgIGF3YWl0IHRoaXMucGx1Z2luLnNhdmVTZXR0aW5ncygpO1xuICAgICAgICAgICAgfSlcbiAgICAgICAgKTtcblxuICAgICAgbmV3IFNldHRpbmcoY29udGFpbmVyRWwpXG4gICAgICAgIC5zZXROYW1lKCdFbmRwb2ludCBQb3J0JylcbiAgICAgICAgLnNldERlc2MoJ1BvcnQgbnVtYmVyIGZvciB0aGUgVGhvdGggYWdlbnQnKVxuICAgICAgICAuYWRkVGV4dCgodGV4dCkgPT5cbiAgICAgICAgICB0ZXh0XG4gICAgICAgICAgICAuc2V0UGxhY2Vob2xkZXIoJzgwMDAnKVxuICAgICAgICAgICAgLnNldFZhbHVlKHRoaXMucGx1Z2luLnNldHRpbmdzLmVuZHBvaW50UG9ydClcbiAgICAgICAgICAgIC5vbkNoYW5nZShhc3luYyAodmFsdWUpID0+IHtcbiAgICAgICAgICAgICAgdGhpcy5wbHVnaW4uc2V0dGluZ3MuZW5kcG9pbnRQb3J0ID0gdmFsdWU7XG4gICAgICAgICAgICAgIGF3YWl0IHRoaXMucGx1Z2luLnNhdmVTZXR0aW5ncygpO1xuICAgICAgICAgICAgfSlcbiAgICAgICAgKTtcbiAgICB9XG5cbiAgICBuZXcgU2V0dGluZyhjb250YWluZXJFbClcbiAgICAgIC5zZXROYW1lKCdCYXNlIFVSTCcpXG4gICAgICAuc2V0RGVzYygnRnVsbCBiYXNlIFVSTCBmb3IgdGhlIFRob3RoIEFQSSAoYXV0by11cGRhdGVkIHdoZW4gdXNpbmcgcmVtb3RlIG1vZGUpJylcbiAgICAgIC5hZGRUZXh0KCh0ZXh0KSA9PlxuICAgICAgICB0ZXh0XG4gICAgICAgICAgLnNldFBsYWNlaG9sZGVyKCdodHRwOi8vMTI3LjAuMC4xOjgwMDAnKVxuICAgICAgICAgIC5zZXRWYWx1ZSh0aGlzLnBsdWdpbi5zZXR0aW5ncy5lbmRwb2ludEJhc2VVcmwpXG4gICAgICAgICAgLm9uQ2hhbmdlKGFzeW5jICh2YWx1ZSkgPT4ge1xuICAgICAgICAgICAgdGhpcy5wbHVnaW4uc2V0dGluZ3MuZW5kcG9pbnRCYXNlVXJsID0gdmFsdWU7XG4gICAgICAgICAgICBhd2FpdCB0aGlzLnBsdWdpbi5zYXZlU2V0dGluZ3MoKTtcbiAgICAgICAgICB9KVxuICAgICAgKTtcblxuICAgIC8vIERpcmVjdG9yeSBTZXR0aW5nc1xuICAgIGNvbnRhaW5lckVsLmNyZWF0ZUVsKCdoMycsIHsgdGV4dDogJ/Cfk4EgRGlyZWN0b3J5IFNldHRpbmdzJyB9KTtcblxuICAgIG5ldyBTZXR0aW5nKGNvbnRhaW5lckVsKVxuICAgICAgLnNldE5hbWUoJ1dvcmtzcGFjZSBEaXJlY3RvcnknKVxuICAgICAgLnNldERlc2MoJ01haW4gVGhvdGggd29ya3NwYWNlIGRpcmVjdG9yeScpXG4gICAgICAuYWRkVGV4dCgodGV4dCkgPT5cbiAgICAgICAgdGV4dFxuICAgICAgICAgIC5zZXRQbGFjZWhvbGRlcignL3BhdGgvdG8vcHJvamVjdC10aG90aCcpXG4gICAgICAgICAgLnNldFZhbHVlKHRoaXMucGx1Z2luLnNldHRpbmdzLndvcmtzcGFjZURpcilcbiAgICAgICAgICAub25DaGFuZ2UoYXN5bmMgKHZhbHVlKSA9PiB7XG4gICAgICAgICAgICB0aGlzLnBsdWdpbi5zZXR0aW5ncy53b3Jrc3BhY2VEaXIgPSB2YWx1ZTtcbiAgICAgICAgICAgIGF3YWl0IHRoaXMucGx1Z2luLnNhdmVTZXR0aW5ncygpO1xuICAgICAgICAgIH0pXG4gICAgICApO1xuXG4gICAgbmV3IFNldHRpbmcoY29udGFpbmVyRWwpXG4gICAgICAuc2V0TmFtZSgnT2JzaWRpYW4gRGlyZWN0b3J5JylcbiAgICAgIC5zZXREZXNjKCdEaXJlY3RvcnkgZm9yIE9ic2lkaWFuLXNwZWNpZmljIGZpbGVzJylcbiAgICAgIC5hZGRUZXh0KCh0ZXh0KSA9PlxuICAgICAgICB0ZXh0XG4gICAgICAgICAgLnNldFBsYWNlaG9sZGVyKCcvcGF0aC90by9vYnNpZGlhbi92YXVsdC90aG90aCcpXG4gICAgICAgICAgLnNldFZhbHVlKHRoaXMucGx1Z2luLnNldHRpbmdzLm9ic2lkaWFuRGlyKVxuICAgICAgICAgIC5vbkNoYW5nZShhc3luYyAodmFsdWUpID0+IHtcbiAgICAgICAgICAgIHRoaXMucGx1Z2luLnNldHRpbmdzLm9ic2lkaWFuRGlyID0gdmFsdWU7XG4gICAgICAgICAgICBhd2FpdCB0aGlzLnBsdWdpbi5zYXZlU2V0dGluZ3MoKTtcbiAgICAgICAgICB9KVxuICAgICAgKTtcblxuICAgIG5ldyBTZXR0aW5nKGNvbnRhaW5lckVsKVxuICAgICAgLnNldE5hbWUoJ1BERiBEaXJlY3RvcnknKVxuICAgICAgLnNldERlc2MoJ0RpcmVjdG9yeSBmb3Igc3RvcmluZyBQREYgZmlsZXMnKVxuICAgICAgLmFkZFRleHQoKHRleHQpID0+XG4gICAgICAgIHRleHRcbiAgICAgICAgICAuc2V0UGxhY2Vob2xkZXIoJyR7T0JTSURJQU5fRElSfS9wYXBlcnMvcGRmcycpXG4gICAgICAgICAgLnNldFZhbHVlKHRoaXMucGx1Z2luLnNldHRpbmdzLnBkZkRpcilcbiAgICAgICAgICAub25DaGFuZ2UoYXN5bmMgKHZhbHVlKSA9PiB7XG4gICAgICAgICAgICB0aGlzLnBsdWdpbi5zZXR0aW5ncy5wZGZEaXIgPSB2YWx1ZTtcbiAgICAgICAgICAgIGF3YWl0IHRoaXMucGx1Z2luLnNhdmVTZXR0aW5ncygpO1xuICAgICAgICAgIH0pXG4gICAgICApO1xuXG4gICAgbmV3IFNldHRpbmcoY29udGFpbmVyRWwpXG4gICAgICAuc2V0TmFtZSgnS25vd2xlZGdlIEJhc2UgRGlyZWN0b3J5JylcbiAgICAgIC5zZXREZXNjKCdEaXJlY3RvcnkgZm9yIGtub3dsZWRnZSBiYXNlIHN0b3JhZ2UnKVxuICAgICAgLmFkZFRleHQoKHRleHQpID0+XG4gICAgICAgIHRleHRcbiAgICAgICAgICAuc2V0UGxhY2Vob2xkZXIoJyR7V09SS1NQQUNFX0RJUn0va25vd2xlZGdlJylcbiAgICAgICAgICAuc2V0VmFsdWUodGhpcy5wbHVnaW4uc2V0dGluZ3Mua25vd2xlZGdlQmFzZURpcilcbiAgICAgICAgICAub25DaGFuZ2UoYXN5bmMgKHZhbHVlKSA9PiB7XG4gICAgICAgICAgICB0aGlzLnBsdWdpbi5zZXR0aW5ncy5rbm93bGVkZ2VCYXNlRGlyID0gdmFsdWU7XG4gICAgICAgICAgICBhd2FpdCB0aGlzLnBsdWdpbi5zYXZlU2V0dGluZ3MoKTtcbiAgICAgICAgICB9KVxuICAgICAgKTtcblxuICAgIC8vIENpdGF0aW9uIFNldHRpbmdzXG4gICAgY29udGFpbmVyRWwuY3JlYXRlRWwoJ2gzJywgeyB0ZXh0OiAn8J+TmiBDaXRhdGlvbiBTZXR0aW5ncycgfSk7XG5cbiAgICBuZXcgU2V0dGluZyhjb250YWluZXJFbClcbiAgICAgIC5zZXROYW1lKCdDaXRhdGlvbiBTdHlsZScpXG4gICAgICAuc2V0RGVzYygnRGVmYXVsdCBjaXRhdGlvbiBzdHlsZSBmb3JtYXQnKVxuICAgICAgLmFkZERyb3Bkb3duKChkcm9wZG93bikgPT5cbiAgICAgICAgZHJvcGRvd25cbiAgICAgICAgICAuYWRkT3B0aW9uKCdJRUVFJywgJ0lFRUUnKVxuICAgICAgICAgIC5hZGRPcHRpb24oJ0FQQScsICdBUEEnKVxuICAgICAgICAgIC5hZGRPcHRpb24oJ01MQScsICdNTEEnKVxuICAgICAgICAgIC5hZGRPcHRpb24oJ0NoaWNhZ28nLCAnQ2hpY2FnbycpXG4gICAgICAgICAgLnNldFZhbHVlKHRoaXMucGx1Z2luLnNldHRpbmdzLmNpdGF0aW9uU3R5bGUpXG4gICAgICAgICAgLm9uQ2hhbmdlKGFzeW5jICh2YWx1ZSkgPT4ge1xuICAgICAgICAgICAgdGhpcy5wbHVnaW4uc2V0dGluZ3MuY2l0YXRpb25TdHlsZSA9IHZhbHVlO1xuICAgICAgICAgICAgYXdhaXQgdGhpcy5wbHVnaW4uc2F2ZVNldHRpbmdzKCk7XG4gICAgICAgICAgfSlcbiAgICAgICk7XG5cbiAgICBuZXcgU2V0dGluZyhjb250YWluZXJFbClcbiAgICAgIC5zZXROYW1lKCdVc2UgT3BlbkNpdGF0aW9ucycpXG4gICAgICAuc2V0RGVzYygnRW5hYmxlIE9wZW5DaXRhdGlvbnMgaW50ZWdyYXRpb24nKVxuICAgICAgLmFkZFRvZ2dsZSgodG9nZ2xlKSA9PlxuICAgICAgICB0b2dnbGVcbiAgICAgICAgICAuc2V0VmFsdWUodGhpcy5wbHVnaW4uc2V0dGluZ3MuY2l0YXRpb25Vc2VPcGVuY2l0YXRpb25zKVxuICAgICAgICAgIC5vbkNoYW5nZShhc3luYyAodmFsdWUpID0+IHtcbiAgICAgICAgICAgIHRoaXMucGx1Z2luLnNldHRpbmdzLmNpdGF0aW9uVXNlT3BlbmNpdGF0aW9ucyA9IHZhbHVlO1xuICAgICAgICAgICAgYXdhaXQgdGhpcy5wbHVnaW4uc2F2ZVNldHRpbmdzKCk7XG4gICAgICAgICAgfSlcbiAgICAgICk7XG5cbiAgICBuZXcgU2V0dGluZyhjb250YWluZXJFbClcbiAgICAgIC5zZXROYW1lKCdVc2UgU2VtYW50aWMgU2Nob2xhcicpXG4gICAgICAuc2V0RGVzYygnRW5hYmxlIFNlbWFudGljIFNjaG9sYXIgaW50ZWdyYXRpb24nKVxuICAgICAgLmFkZFRvZ2dsZSgodG9nZ2xlKSA9PlxuICAgICAgICB0b2dnbGVcbiAgICAgICAgICAuc2V0VmFsdWUodGhpcy5wbHVnaW4uc2V0dGluZ3MuY2l0YXRpb25Vc2VTZW1hbnRpY3NjaG9sYXIpXG4gICAgICAgICAgLm9uQ2hhbmdlKGFzeW5jICh2YWx1ZSkgPT4ge1xuICAgICAgICAgICAgdGhpcy5wbHVnaW4uc2V0dGluZ3MuY2l0YXRpb25Vc2VTZW1hbnRpY3NjaG9sYXIgPSB2YWx1ZTtcbiAgICAgICAgICAgIGF3YWl0IHRoaXMucGx1Z2luLnNhdmVTZXR0aW5ncygpO1xuICAgICAgICAgIH0pXG4gICAgICApO1xuXG4gICAgbmV3IFNldHRpbmcoY29udGFpbmVyRWwpXG4gICAgICAuc2V0TmFtZSgnVXNlIGFyWGl2JylcbiAgICAgIC5zZXREZXNjKCdFbmFibGUgYXJYaXYgaW50ZWdyYXRpb24nKVxuICAgICAgLmFkZFRvZ2dsZSgodG9nZ2xlKSA9PlxuICAgICAgICB0b2dnbGVcbiAgICAgICAgICAuc2V0VmFsdWUodGhpcy5wbHVnaW4uc2V0dGluZ3MuY2l0YXRpb25Vc2VBcnhpdilcbiAgICAgICAgICAub25DaGFuZ2UoYXN5bmMgKHZhbHVlKSA9PiB7XG4gICAgICAgICAgICB0aGlzLnBsdWdpbi5zZXR0aW5ncy5jaXRhdGlvblVzZUFyeGl2ID0gdmFsdWU7XG4gICAgICAgICAgICBhd2FpdCB0aGlzLnBsdWdpbi5zYXZlU2V0dGluZ3MoKTtcbiAgICAgICAgICB9KVxuICAgICAgKTtcblxuICAgICAgICAvLyBCZWhhdmlvciBTZXR0aW5nc1xuICAgIGNvbnRhaW5lckVsLmNyZWF0ZUVsKCdoMycsIHsgdGV4dDogJ+Kame+4jyBCZWhhdmlvciBTZXR0aW5ncycgfSk7XG5cbiAgICBuZXcgU2V0dGluZyhjb250YWluZXJFbClcbiAgICAgIC5zZXROYW1lKCdBdXRvLXN0YXJ0IEFnZW50JylcbiAgICAgIC5zZXREZXNjKCdBdXRvbWF0aWNhbGx5IHN0YXJ0IHRoZSBUaG90aCBhZ2VudCB3aGVuIE9ic2lkaWFuIG9wZW5zJylcbiAgICAgIC5hZGRUb2dnbGUoKHRvZ2dsZSkgPT5cbiAgICAgICAgdG9nZ2xlXG4gICAgICAgICAgLnNldFZhbHVlKHRoaXMucGx1Z2luLnNldHRpbmdzLmF1dG9TdGFydEFnZW50KVxuICAgICAgICAgIC5vbkNoYW5nZShhc3luYyAodmFsdWUpID0+IHtcbiAgICAgICAgICAgIHRoaXMucGx1Z2luLnNldHRpbmdzLmF1dG9TdGFydEFnZW50ID0gdmFsdWU7XG4gICAgICAgICAgICBhd2FpdCB0aGlzLnBsdWdpbi5zYXZlU2V0dGluZ3MoKTtcbiAgICAgICAgICB9KVxuICAgICAgKTtcblxuICAgIG5ldyBTZXR0aW5nKGNvbnRhaW5lckVsKVxuICAgICAgLnNldE5hbWUoJ1Nob3cgU3RhdHVzIEJhcicpXG4gICAgICAuc2V0RGVzYygnRGlzcGxheSBhZ2VudCBzdGF0dXMgaW4gdGhlIHN0YXR1cyBiYXInKVxuICAgICAgLmFkZFRvZ2dsZSgodG9nZ2xlKSA9PlxuICAgICAgICB0b2dnbGVcbiAgICAgICAgICAuc2V0VmFsdWUodGhpcy5wbHVnaW4uc2V0dGluZ3Muc2hvd1N0YXR1c0JhcilcbiAgICAgICAgICAub25DaGFuZ2UoYXN5bmMgKHZhbHVlKSA9PiB7XG4gICAgICAgICAgICB0aGlzLnBsdWdpbi5zZXR0aW5ncy5zaG93U3RhdHVzQmFyID0gdmFsdWU7XG4gICAgICAgICAgICBhd2FpdCB0aGlzLnBsdWdpbi5zYXZlU2V0dGluZ3MoKTtcblxuICAgICAgICAgICAgLy8gVXBkYXRlIHN0YXR1cyBiYXIgdmlzaWJpbGl0eVxuICAgICAgICAgICAgaWYgKHZhbHVlICYmICF0aGlzLnBsdWdpbi5zdGF0dXNCYXJJdGVtKSB7XG4gICAgICAgICAgICAgIHRoaXMucGx1Z2luLnN0YXR1c0Jhckl0ZW0gPSB0aGlzLnBsdWdpbi5hZGRTdGF0dXNCYXJJdGVtKCk7XG4gICAgICAgICAgICAgIHRoaXMucGx1Z2luLnVwZGF0ZVN0YXR1c0JhcigpO1xuICAgICAgICAgICAgfSBlbHNlIGlmICghdmFsdWUgJiYgdGhpcy5wbHVnaW4uc3RhdHVzQmFySXRlbSkge1xuICAgICAgICAgICAgICB0aGlzLnBsdWdpbi5zdGF0dXNCYXJJdGVtLnJlbW92ZSgpO1xuICAgICAgICAgICAgICB0aGlzLnBsdWdpbi5zdGF0dXNCYXJJdGVtID0gbnVsbDtcbiAgICAgICAgICAgIH1cbiAgICAgICAgICB9KVxuICAgICAgKTtcblxuICAgIG5ldyBTZXR0aW5nKGNvbnRhaW5lckVsKVxuICAgICAgLnNldE5hbWUoJ0F1dG8tc3RhcnQgRW5kcG9pbnQnKVxuICAgICAgLnNldERlc2MoJ0F1dG9tYXRpY2FsbHkgc3RhcnQgdGhlIGVuZHBvaW50IHNlcnZlcicpXG4gICAgICAuYWRkVG9nZ2xlKCh0b2dnbGUpID0+XG4gICAgICAgIHRvZ2dsZVxuICAgICAgICAgIC5zZXRWYWx1ZSh0aGlzLnBsdWdpbi5zZXR0aW5ncy5lbmRwb2ludEF1dG9TdGFydClcbiAgICAgICAgICAub25DaGFuZ2UoYXN5bmMgKHZhbHVlKSA9PiB7XG4gICAgICAgICAgICB0aGlzLnBsdWdpbi5zZXR0aW5ncy5lbmRwb2ludEF1dG9TdGFydCA9IHZhbHVlO1xuICAgICAgICAgICAgYXdhaXQgdGhpcy5wbHVnaW4uc2F2ZVNldHRpbmdzKCk7XG4gICAgICAgICAgfSlcbiAgICAgICk7XG5cbiAgICBuZXcgU2V0dGluZyhjb250YWluZXJFbClcbiAgICAgIC5zZXROYW1lKCdBdXRvLXN0YXJ0IE1vbml0b3InKVxuICAgICAgLnNldERlc2MoJ0F1dG9tYXRpY2FsbHkgc3RhcnQgZmlsZSBtb25pdG9yaW5nJylcbiAgICAgIC5hZGRUb2dnbGUoKHRvZ2dsZSkgPT5cbiAgICAgICAgdG9nZ2xlXG4gICAgICAgICAgLnNldFZhbHVlKHRoaXMucGx1Z2luLnNldHRpbmdzLm1vbml0b3JBdXRvU3RhcnQpXG4gICAgICAgICAgLm9uQ2hhbmdlKGFzeW5jICh2YWx1ZSkgPT4ge1xuICAgICAgICAgICAgdGhpcy5wbHVnaW4uc2V0dGluZ3MubW9uaXRvckF1dG9TdGFydCA9IHZhbHVlO1xuICAgICAgICAgICAgYXdhaXQgdGhpcy5wbHVnaW4uc2F2ZVNldHRpbmdzKCk7XG4gICAgICAgICAgfSlcbiAgICAgICk7XG5cbiAgICAvLyBEaXNjb3ZlcnkgU2V0dGluZ3NcbiAgICBjb250YWluZXJFbC5jcmVhdGVFbCgnaDMnLCB7IHRleHQ6ICfwn5SNIERpc2NvdmVyeSBTZXR0aW5ncycgfSk7XG5cbiAgICBuZXcgU2V0dGluZyhjb250YWluZXJFbClcbiAgICAgIC5zZXROYW1lKCdDaHJvbWUgRXh0ZW5zaW9uIEVuYWJsZWQnKVxuICAgICAgLnNldERlc2MoJ0VuYWJsZSBDaHJvbWUgZXh0ZW5zaW9uIGludGVncmF0aW9uJylcbiAgICAgIC5hZGRUb2dnbGUoKHRvZ2dsZSkgPT5cbiAgICAgICAgdG9nZ2xlXG4gICAgICAgICAgLnNldFZhbHVlKHRoaXMucGx1Z2luLnNldHRpbmdzLmRpc2NvdmVyeUNocm9tZUV4dGVuc2lvbkVuYWJsZWQpXG4gICAgICAgICAgLm9uQ2hhbmdlKGFzeW5jICh2YWx1ZSkgPT4ge1xuICAgICAgICAgICAgdGhpcy5wbHVnaW4uc2V0dGluZ3MuZGlzY292ZXJ5Q2hyb21lRXh0ZW5zaW9uRW5hYmxlZCA9IHZhbHVlO1xuICAgICAgICAgICAgYXdhaXQgdGhpcy5wbHVnaW4uc2F2ZVNldHRpbmdzKCk7XG4gICAgICAgICAgfSlcbiAgICAgICk7XG5cbiAgICBuZXcgU2V0dGluZyhjb250YWluZXJFbClcbiAgICAgIC5zZXROYW1lKCdDaHJvbWUgRXh0ZW5zaW9uIFBvcnQnKVxuICAgICAgLnNldERlc2MoJ1BvcnQgZm9yIENocm9tZSBleHRlbnNpb24gY29tbXVuaWNhdGlvbicpXG4gICAgICAuYWRkVGV4dCgodGV4dCkgPT5cbiAgICAgICAgdGV4dFxuICAgICAgICAgIC5zZXRQbGFjZWhvbGRlcignODc2NScpXG4gICAgICAgICAgLnNldFZhbHVlKHRoaXMucGx1Z2luLnNldHRpbmdzLmRpc2NvdmVyeUNocm9tZUV4dGVuc2lvblBvcnQudG9TdHJpbmcoKSlcbiAgICAgICAgICAub25DaGFuZ2UoYXN5bmMgKHZhbHVlKSA9PiB7XG4gICAgICAgICAgICB0aGlzLnBsdWdpbi5zZXR0aW5ncy5kaXNjb3ZlcnlDaHJvbWVFeHRlbnNpb25Qb3J0ID0gcGFyc2VJbnQodmFsdWUpIHx8IDg3NjU7XG4gICAgICAgICAgICBhd2FpdCB0aGlzLnBsdWdpbi5zYXZlU2V0dGluZ3MoKTtcbiAgICAgICAgICB9KVxuICAgICAgKTtcblxuICAgIG5ldyBTZXR0aW5nKGNvbnRhaW5lckVsKVxuICAgICAgLnNldE5hbWUoJ0RlZmF1bHQgTWF4IEFydGljbGVzJylcbiAgICAgIC5zZXREZXNjKCdNYXhpbXVtIGFydGljbGVzIHRvIGRpc2NvdmVyIHBlciBzZXNzaW9uJylcbiAgICAgIC5hZGRUZXh0KCh0ZXh0KSA9PlxuICAgICAgICB0ZXh0XG4gICAgICAgICAgLnNldFBsYWNlaG9sZGVyKCc1MCcpXG4gICAgICAgICAgLnNldFZhbHVlKHRoaXMucGx1Z2luLnNldHRpbmdzLmRpc2NvdmVyeURlZmF1bHRNYXhBcnRpY2xlcy50b1N0cmluZygpKVxuICAgICAgICAgIC5vbkNoYW5nZShhc3luYyAodmFsdWUpID0+IHtcbiAgICAgICAgICAgIHRoaXMucGx1Z2luLnNldHRpbmdzLmRpc2NvdmVyeURlZmF1bHRNYXhBcnRpY2xlcyA9IHBhcnNlSW50KHZhbHVlKSB8fCA1MDtcbiAgICAgICAgICAgIGF3YWl0IHRoaXMucGx1Z2luLnNhdmVTZXR0aW5ncygpO1xuICAgICAgICAgIH0pXG4gICAgICApO1xuXG4gICAgbmV3IFNldHRpbmcoY29udGFpbmVyRWwpXG4gICAgICAuc2V0TmFtZSgnRGlzY292ZXJ5IEludGVydmFsIChtaW51dGVzKScpXG4gICAgICAuc2V0RGVzYygnSG93IG9mdGVuIHRvIHJ1biBhdXRvbWF0aWMgZGlzY292ZXJ5JylcbiAgICAgIC5hZGRUZXh0KCh0ZXh0KSA9PlxuICAgICAgICB0ZXh0XG4gICAgICAgICAgLnNldFBsYWNlaG9sZGVyKCc2MCcpXG4gICAgICAgICAgLnNldFZhbHVlKHRoaXMucGx1Z2luLnNldHRpbmdzLmRpc2NvdmVyeURlZmF1bHRJbnRlcnZhbE1pbnV0ZXMudG9TdHJpbmcoKSlcbiAgICAgICAgICAub25DaGFuZ2UoYXN5bmMgKHZhbHVlKSA9PiB7XG4gICAgICAgICAgICB0aGlzLnBsdWdpbi5zZXR0aW5ncy5kaXNjb3ZlcnlEZWZhdWx0SW50ZXJ2YWxNaW51dGVzID0gcGFyc2VJbnQodmFsdWUpIHx8IDYwO1xuICAgICAgICAgICAgYXdhaXQgdGhpcy5wbHVnaW4uc2F2ZVNldHRpbmdzKCk7XG4gICAgICAgICAgfSlcbiAgICAgICk7XG5cbiAgICAvLyBBZHZhbmNlZCBTZXR0aW5nc1xuICAgIGNvbnRhaW5lckVsLmNyZWF0ZUVsKCdoMycsIHsgdGV4dDogJ/CflKcgQWR2YW5jZWQgU2V0dGluZ3MnIH0pO1xuXG4gICAgbmV3IFNldHRpbmcoY29udGFpbmVyRWwpXG4gICAgICAuc2V0TmFtZSgnTG9nIExldmVsJylcbiAgICAgIC5zZXREZXNjKCdMb2dnaW5nIHZlcmJvc2l0eSBsZXZlbCcpXG4gICAgICAuYWRkRHJvcGRvd24oKGRyb3Bkb3duKSA9PlxuICAgICAgICBkcm9wZG93blxuICAgICAgICAgIC5hZGRPcHRpb24oJ0RFQlVHJywgJ0RFQlVHJylcbiAgICAgICAgICAuYWRkT3B0aW9uKCdJTkZPJywgJ0lORk8nKVxuICAgICAgICAgIC5hZGRPcHRpb24oJ1dBUk5JTkcnLCAnV0FSTklORycpXG4gICAgICAgICAgLmFkZE9wdGlvbignRVJST1InLCAnRVJST1InKVxuICAgICAgICAgIC5zZXRWYWx1ZSh0aGlzLnBsdWdpbi5zZXR0aW5ncy5sb2dMZXZlbClcbiAgICAgICAgICAub25DaGFuZ2UoYXN5bmMgKHZhbHVlKSA9PiB7XG4gICAgICAgICAgICB0aGlzLnBsdWdpbi5zZXR0aW5ncy5sb2dMZXZlbCA9IHZhbHVlO1xuICAgICAgICAgICAgYXdhaXQgdGhpcy5wbHVnaW4uc2F2ZVNldHRpbmdzKCk7XG4gICAgICAgICAgfSlcbiAgICAgICk7XG5cbiAgICBuZXcgU2V0dGluZyhjb250YWluZXJFbClcbiAgICAgIC5zZXROYW1lKCdNb25pdG9yIFdhdGNoIEludGVydmFsJylcbiAgICAgIC5zZXREZXNjKCdGaWxlIG1vbml0b3JpbmcgaW50ZXJ2YWwgaW4gc2Vjb25kcycpXG4gICAgICAuYWRkVGV4dCgodGV4dCkgPT5cbiAgICAgICAgdGV4dFxuICAgICAgICAgIC5zZXRQbGFjZWhvbGRlcignNScpXG4gICAgICAgICAgLnNldFZhbHVlKHRoaXMucGx1Z2luLnNldHRpbmdzLm1vbml0b3JXYXRjaEludGVydmFsLnRvU3RyaW5nKCkpXG4gICAgICAgICAgLm9uQ2hhbmdlKGFzeW5jICh2YWx1ZSkgPT4ge1xuICAgICAgICAgICAgdGhpcy5wbHVnaW4uc2V0dGluZ3MubW9uaXRvcldhdGNoSW50ZXJ2YWwgPSBwYXJzZUludCh2YWx1ZSkgfHwgNTtcbiAgICAgICAgICAgIGF3YWl0IHRoaXMucGx1Z2luLnNhdmVTZXR0aW5ncygpO1xuICAgICAgICAgIH0pXG4gICAgICApO1xuXG4gICAgbmV3IFNldHRpbmcoY29udGFpbmVyRWwpXG4gICAgICAuc2V0TmFtZSgnTExNIENvbnRleHQgTGVuZ3RoJylcbiAgICAgIC5zZXREZXNjKCdNYXhpbXVtIGNvbnRleHQgbGVuZ3RoIGZvciBwcmltYXJ5IExMTScpXG4gICAgICAuYWRkVGV4dCgodGV4dCkgPT5cbiAgICAgICAgdGV4dFxuICAgICAgICAgIC5zZXRQbGFjZWhvbGRlcignMTAwMDAwMCcpXG4gICAgICAgICAgLnNldFZhbHVlKHRoaXMucGx1Z2luLnNldHRpbmdzLmxsbU1heENvbnRleHRMZW5ndGgudG9TdHJpbmcoKSlcbiAgICAgICAgICAub25DaGFuZ2UoYXN5bmMgKHZhbHVlKSA9PiB7XG4gICAgICAgICAgICB0aGlzLnBsdWdpbi5zZXR0aW5ncy5sbG1NYXhDb250ZXh0TGVuZ3RoID0gcGFyc2VJbnQodmFsdWUpIHx8IDEwMDAwMDA7XG4gICAgICAgICAgICBhd2FpdCB0aGlzLnBsdWdpbi5zYXZlU2V0dGluZ3MoKTtcbiAgICAgICAgICB9KVxuICAgICAgKTtcblxuICAgIC8vIENvbnRyb2wgU2VjdGlvblxuICAgIGNvbnRhaW5lckVsLmNyZWF0ZUVsKCdoMycsIHsgdGV4dDogJ0FnZW50IENvbnRyb2wnIH0pO1xuXG4gICAgbmV3IFNldHRpbmcoY29udGFpbmVyRWwpXG4gICAgICAuc2V0TmFtZSgnQWdlbnQgU3RhdHVzJylcbiAgICAgIC5zZXREZXNjKCdTdGFydCwgc3RvcCwgb3IgcmVzdGFydCB0aGUgVGhvdGggYWdlbnQnKVxuICAgICAgLmFkZEJ1dHRvbigoYnRuKSA9PlxuICAgICAgICBidG5cbiAgICAgICAgICAuc2V0QnV0dG9uVGV4dCh0aGlzLnBsdWdpbi5pc0FnZW50UnVubmluZyA/ICdTdG9wIEFnZW50JyA6ICdTdGFydCBBZ2VudCcpXG4gICAgICAgICAgLm9uQ2xpY2soYXN5bmMgKCkgPT4ge1xuICAgICAgICAgICAgaWYgKHRoaXMucGx1Z2luLmlzQWdlbnRSdW5uaW5nKSB7XG4gICAgICAgICAgICAgIHRoaXMucGx1Z2luLnN0b3BBZ2VudCgpO1xuICAgICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgICAgYXdhaXQgdGhpcy5wbHVnaW4uc3RhcnRBZ2VudCgpO1xuICAgICAgICAgICAgfVxuICAgICAgICAgICAgLy8gUmVmcmVzaCB0aGUgYnV0dG9uIHRleHRcbiAgICAgICAgICAgIHNldFRpbWVvdXQoKCkgPT4gdGhpcy5kaXNwbGF5KCksIDEwMCk7XG4gICAgICAgICAgfSlcbiAgICAgIClcbiAgICAgIC5hZGRCdXR0b24oKGJ0bikgPT5cbiAgICAgICAgYnRuXG4gICAgICAgICAgLnNldEJ1dHRvblRleHQoJ1Jlc3RhcnQgQWdlbnQnKVxuICAgICAgICAgIC5vbkNsaWNrKGFzeW5jICgpID0+IHtcbiAgICAgICAgICAgIGF3YWl0IHRoaXMucGx1Z2luLnJlc3RhcnRBZ2VudCgpO1xuICAgICAgICAgICAgc2V0VGltZW91dCgoKSA9PiB0aGlzLmRpc3BsYXkoKSwgMTAwKTtcbiAgICAgICAgfSlcbiAgICAgICk7XG4gIH1cbn1cblxuY2xhc3MgQ2hhdE1vZGFsIGV4dGVuZHMgTW9kYWwge1xuICBwbHVnaW46IFRob3RoUGx1Z2luO1xuICBpbnB1dEVsITogSFRNTFRleHRBcmVhRWxlbWVudDtcbiAgb3V0cHV0RWwhOiBIVE1MRGl2RWxlbWVudDtcbiAgc2VuZEJ1dHRvbiE6IEhUTUxCdXR0b25FbGVtZW50O1xuICBpbml0aWFsUXVlcnkgPSAnJztcbiAgY29udmVyc2F0aW9uSWQ/OiBzdHJpbmc7XG5cbiAgY29uc3RydWN0b3IoYXBwOiBBcHAsIHBsdWdpbjogVGhvdGhQbHVnaW4pIHtcbiAgICBzdXBlcihhcHApO1xuICAgIHRoaXMucGx1Z2luID0gcGx1Z2luO1xuICB9XG5cbiAgc2V0SW5pdGlhbFF1ZXJ5KHF1ZXJ5OiBzdHJpbmcpOiB2b2lkIHtcbiAgICB0aGlzLmluaXRpYWxRdWVyeSA9IHF1ZXJ5O1xuICB9XG5cbiAgb25PcGVuKCk6IHZvaWQge1xuICAgIGNvbnN0IHsgY29udGVudEVsIH0gPSB0aGlzO1xuICAgIGNvbnRlbnRFbC5hZGRDbGFzcygndGhvdGgtY2hhdC1tb2RhbCcpO1xuXG4gICAgLy8gVGl0bGVcbiAgICBjb250ZW50RWwuY3JlYXRlRWwoJ2gyJywgeyB0ZXh0OiAnVGhvdGggUmVzZWFyY2ggQ2hhdCcgfSk7XG5cbiAgICAvLyBDaGF0IGhpc3RvcnlcbiAgICB0aGlzLm91dHB1dEVsID0gY29udGVudEVsLmNyZWF0ZURpdih7IGNsczogJ3Rob3RoLWNoYXQtb3V0cHV0JyB9KTtcbiAgICB0aGlzLmxvYWRDaGF0SGlzdG9yeSgpO1xuXG4gICAgLy8gSW5wdXQgc2VjdGlvblxuICAgIGNvbnN0IGlucHV0V3JhcHBlciA9IGNvbnRlbnRFbC5jcmVhdGVEaXYoeyBjbHM6ICd0aG90aC1jaGF0LWlucHV0LXdyYXBwZXInIH0pO1xuXG4gICAgdGhpcy5pbnB1dEVsID0gaW5wdXRXcmFwcGVyLmNyZWF0ZUVsKCd0ZXh0YXJlYScsIHtcbiAgICAgIGNsczogJ3Rob3RoLWNoYXQtaW5wdXQnLFxuICAgICAgYXR0cjogeyBwbGFjZWhvbGRlcjogJ0FzayBUaG90aCBhYm91dCB5b3VyIHJlc2VhcmNoLi4uJyB9XG4gICAgfSk7XG5cbiAgICBpZiAodGhpcy5pbml0aWFsUXVlcnkpIHtcbiAgICAgIHRoaXMuaW5wdXRFbC52YWx1ZSA9IHRoaXMuaW5pdGlhbFF1ZXJ5O1xuICAgIH1cblxuICAgIHRoaXMuc2VuZEJ1dHRvbiA9IGlucHV0V3JhcHBlci5jcmVhdGVFbCgnYnV0dG9uJywge1xuICAgICAgdGV4dDogJ1NlbmQnLFxuICAgICAgY2xzOiAndGhvdGgtc2VuZC1idXR0b24nXG4gICAgfSk7XG5cbiAgICB0aGlzLnNlbmRCdXR0b24ub25jbGljayA9ICgpID0+IHRoaXMuc2VuZE1lc3NhZ2UoKTtcblxuICAgIC8vIEVudGVyIHRvIHNlbmQgKFNoaWZ0K0VudGVyIGZvciBuZXcgbGluZSlcbiAgICB0aGlzLmlucHV0RWwuYWRkRXZlbnRMaXN0ZW5lcigna2V5ZG93bicsIChlKSA9PiB7XG4gICAgICBpZiAoZS5rZXkgPT09ICdFbnRlcicgJiYgIWUuc2hpZnRLZXkpIHtcbiAgICAgICAgZS5wcmV2ZW50RGVmYXVsdCgpO1xuICAgICAgICB0aGlzLnNlbmRNZXNzYWdlKCk7XG4gICAgICB9XG4gICAgfSk7XG5cbiAgICAvLyBGb2N1cyBvbiBpbnB1dFxuICAgIHRoaXMuaW5wdXRFbC5mb2N1cygpO1xuICB9XG5cbiAgcHJpdmF0ZSBsb2FkQ2hhdEhpc3RvcnkoKTogdm9pZCB7XG4gICAgY29uc3QgaGlzdG9yeSA9IHRoaXMucGx1Z2luLnNldHRpbmdzLmNoYXRIaXN0b3J5LnNsaWNlKC0xMCk7IC8vIFNob3cgbGFzdCAxMCBtZXNzYWdlc1xuXG4gICAgaGlzdG9yeS5mb3JFYWNoKG1lc3NhZ2UgPT4ge1xuICAgICAgdGhpcy5hZGRNZXNzYWdlVG9DaGF0KG1lc3NhZ2Uucm9sZSwgbWVzc2FnZS5jb250ZW50LCBuZXcgRGF0ZShtZXNzYWdlLnRpbWVzdGFtcCkpO1xuICAgIH0pO1xuICB9XG5cbiAgcHJpdmF0ZSBhZGRNZXNzYWdlVG9DaGF0KHJvbGU6ICd1c2VyJyB8ICdhc3Npc3RhbnQnIHwgJ3N5c3RlbScsIGNvbnRlbnQ6IHN0cmluZywgdGltZXN0YW1wPzogRGF0ZSk6IHZvaWQge1xuICAgIGNvbnN0IG1lc3NhZ2VFbCA9IHRoaXMub3V0cHV0RWwuY3JlYXRlRGl2KHsgY2xzOiBgdGhvdGgtbWVzc2FnZSB0aG90aC1tZXNzYWdlLSR7cm9sZX1gIH0pO1xuXG4gICAgY29uc3QgaGVhZGVyRWwgPSBtZXNzYWdlRWwuY3JlYXRlRGl2KHsgY2xzOiAndGhvdGgtbWVzc2FnZS1oZWFkZXInIH0pO1xuICAgIGhlYWRlckVsLmNyZWF0ZVNwYW4oeyB0ZXh0OiByb2xlID09PSAndXNlcicgPyAnWW91JyA6ICdUaG90aCcsIGNsczogJ3Rob3RoLW1lc3NhZ2Utc2VuZGVyJyB9KTtcblxuICAgIGlmICh0aW1lc3RhbXApIHtcbiAgICAgIGhlYWRlckVsLmNyZWF0ZVNwYW4oe1xuICAgICAgICB0ZXh0OiB0aW1lc3RhbXAudG9Mb2NhbGVUaW1lU3RyaW5nKCksXG4gICAgICAgIGNsczogJ3Rob3RoLW1lc3NhZ2UtdGltZSdcbiAgICAgIH0pO1xuICAgIH1cblxuICAgIG1lc3NhZ2VFbC5jcmVhdGVEaXYoeyB0ZXh0OiBjb250ZW50LCBjbHM6ICd0aG90aC1tZXNzYWdlLWNvbnRlbnQnIH0pO1xuXG4gICAgLy8gU2Nyb2xsIHRvIGJvdHRvbVxuICAgIHRoaXMub3V0cHV0RWwuc2Nyb2xsVG9wID0gdGhpcy5vdXRwdXRFbC5zY3JvbGxIZWlnaHQ7XG4gIH1cblxuICBwcml2YXRlIGFzeW5jIHNlbmRNZXNzYWdlKCk6IFByb21pc2U8dm9pZD4ge1xuICAgIGNvbnN0IG1lc3NhZ2UgPSB0aGlzLmlucHV0RWwudmFsdWUudHJpbSgpO1xuICAgIGlmICghbWVzc2FnZSkgcmV0dXJuO1xuXG4gICAgaWYgKCF0aGlzLnBsdWdpbi5pc0FnZW50UnVubmluZykge1xuICAgICAgbmV3IE5vdGljZSgnVGhvdGggYWdlbnQgaXMgbm90IHJ1bm5pbmcuIFBsZWFzZSBzdGFydCBpdCBmaXJzdC4nKTtcbiAgICAgIHJldHVybjtcbiAgICB9XG5cbiAgICAvLyBBZGQgdXNlciBtZXNzYWdlIHRvIGNoYXRcbiAgICB0aGlzLmFkZE1lc3NhZ2VUb0NoYXQoJ3VzZXInLCBtZXNzYWdlKTtcblxuICAgIC8vIFNhdmUgdG8gaGlzdG9yeVxuICAgIGNvbnN0IHVzZXJNZXNzYWdlOiBDaGF0TWVzc2FnZSA9IHtcbiAgICAgIHJvbGU6ICd1c2VyJyxcbiAgICAgIGNvbnRlbnQ6IG1lc3NhZ2UsXG4gICAgICB0aW1lc3RhbXA6IERhdGUubm93KClcbiAgICB9O1xuICAgIHRoaXMucGx1Z2luLnNldHRpbmdzLmNoYXRIaXN0b3J5LnB1c2godXNlck1lc3NhZ2UpO1xuXG4gICAgLy8gQ2xlYXIgaW5wdXRcbiAgICB0aGlzLmlucHV0RWwudmFsdWUgPSAnJztcbiAgICB0aGlzLnNlbmRCdXR0b24uZGlzYWJsZWQgPSB0cnVlO1xuICAgIHRoaXMuc2VuZEJ1dHRvbi50ZXh0Q29udGVudCA9ICdTZW5kaW5nLi4uJztcblxuICAgIHRyeSB7XG4gICAgICAvLyBTZW5kIHRvIGFnZW50ICh0aGlzIHdvdWxkIG5lZWQgdG8gYmUgaW1wbGVtZW50ZWQgYmFzZWQgb24geW91ciBhZ2VudCdzIEFQSSlcbiAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgdGhpcy5zZW5kVG9BZ2VudChtZXNzYWdlKTtcblxuICAgICAgLy8gQWRkIHJlc3BvbnNlIHRvIGNoYXRcbiAgICAgIHRoaXMuYWRkTWVzc2FnZVRvQ2hhdCgnYXNzaXN0YW50JywgcmVzcG9uc2UpO1xuXG4gICAgICAvLyBTYXZlIHJlc3BvbnNlIHRvIGhpc3RvcnlcbiAgICAgIGNvbnN0IGFzc2lzdGFudE1lc3NhZ2U6IENoYXRNZXNzYWdlID0ge1xuICAgICAgICByb2xlOiAnYXNzaXN0YW50JyxcbiAgICAgICAgY29udGVudDogcmVzcG9uc2UsXG4gICAgICAgIHRpbWVzdGFtcDogRGF0ZS5ub3coKVxuICAgICAgfTtcbiAgICAgIHRoaXMucGx1Z2luLnNldHRpbmdzLmNoYXRIaXN0b3J5LnB1c2goYXNzaXN0YW50TWVzc2FnZSk7XG5cbiAgICAgIC8vIEtlZXAgb25seSBsYXN0IDEwMCBtZXNzYWdlc1xuICAgICAgaWYgKHRoaXMucGx1Z2luLnNldHRpbmdzLmNoYXRIaXN0b3J5Lmxlbmd0aCA+IDEwMCkge1xuICAgICAgICB0aGlzLnBsdWdpbi5zZXR0aW5ncy5jaGF0SGlzdG9yeSA9IHRoaXMucGx1Z2luLnNldHRpbmdzLmNoYXRIaXN0b3J5LnNsaWNlKC0xMDApO1xuICAgICAgfVxuXG4gICAgICBhd2FpdCB0aGlzLnBsdWdpbi5zYXZlU2V0dGluZ3MoKTtcblxuICAgIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgICBjb25zb2xlLmVycm9yKCdFcnJvciBzZW5kaW5nIG1lc3NhZ2U6JywgZXJyb3IpO1xuICAgICAgdGhpcy5hZGRNZXNzYWdlVG9DaGF0KCdzeXN0ZW0nLCAnRXJyb3I6IENvdWxkIG5vdCBzZW5kIG1lc3NhZ2UgdG8gVGhvdGggYWdlbnQnKTtcbiAgICB9IGZpbmFsbHkge1xuICAgICAgdGhpcy5zZW5kQnV0dG9uLmRpc2FibGVkID0gZmFsc2U7XG4gICAgICB0aGlzLnNlbmRCdXR0b24udGV4dENvbnRlbnQgPSAnU2VuZCc7XG4gICAgICB0aGlzLmlucHV0RWwuZm9jdXMoKTtcbiAgICB9XG4gIH1cblxuICAgIHByaXZhdGUgYXN5bmMgc2VuZFRvQWdlbnQobWVzc2FnZTogc3RyaW5nKTogUHJvbWlzZTxzdHJpbmc+IHtcbiAgICBpZiAoIXRoaXMucGx1Z2luLmlzQWdlbnRSdW5uaW5nKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJ1Rob3RoIGFnZW50IGlzIG5vdCBydW5uaW5nJyk7XG4gICAgfVxuXG4gICAgY29uc3QgYXBpVXJsID0gYCR7dGhpcy5wbHVnaW4uc2V0dGluZ3MuZW5kcG9pbnRCYXNlVXJsfS9yZXNlYXJjaC9jaGF0YDtcblxuICAgIHRyeSB7XG4gICAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGZldGNoKGFwaVVybCwge1xuICAgICAgICBtZXRob2Q6ICdQT1NUJyxcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgIH0sXG4gICAgICAgIGJvZHk6IEpTT04uc3RyaW5naWZ5KHtcbiAgICAgICAgICBtZXNzYWdlOiBtZXNzYWdlLFxuICAgICAgICAgIGNvbnZlcnNhdGlvbl9pZDogdGhpcy5nZXRDb252ZXJzYXRpb25JZCgpLFxuICAgICAgICAgIHRpbWVzdGFtcDogRGF0ZS5ub3coKSxcbiAgICAgICAgfSksXG4gICAgICB9KTtcblxuICAgICAgaWYgKCFyZXNwb25zZS5vaykge1xuICAgICAgICB0aHJvdyBuZXcgRXJyb3IoYEhUVFAgJHtyZXNwb25zZS5zdGF0dXN9OiAke3Jlc3BvbnNlLnN0YXR1c1RleHR9YCk7XG4gICAgICB9XG5cbiAgICAgIGNvbnN0IGRhdGEgPSBhd2FpdCByZXNwb25zZS5qc29uKCk7XG4gICAgICByZXR1cm4gZGF0YS5yZXNwb25zZSB8fCBkYXRhLm1lc3NhZ2UgfHwgJ05vIHJlc3BvbnNlIGZyb20gYWdlbnQnO1xuXG4gICAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICAgIGNvbnNvbGUuZXJyb3IoJ0Vycm9yIGNvbW11bmljYXRpbmcgd2l0aCBUaG90aCBhZ2VudDonLCBlcnJvcik7XG5cbiAgICAgIC8vIEZhbGxiYWNrOiB0cnkgYWx0ZXJuYXRpdmUgZW5kcG9pbnRzIG9yIG1ldGhvZHNcbiAgICAgIGlmIChlcnJvciBpbnN0YW5jZW9mIFR5cGVFcnJvciAmJiBlcnJvci5tZXNzYWdlLmluY2x1ZGVzKCdmZXRjaCcpKSB7XG4gICAgICAgIHRocm93IG5ldyBFcnJvcignVW5hYmxlIHRvIGNvbm5lY3QgdG8gVGhvdGggYWdlbnQuIElzIHRoZSBlbmRwb2ludCBydW5uaW5nPycpO1xuICAgICAgfVxuXG4gICAgICB0aHJvdyBuZXcgRXJyb3IoYEZhaWxlZCB0byBjb21tdW5pY2F0ZSB3aXRoIGFnZW50OiAke2Vycm9yLm1lc3NhZ2V9YCk7XG4gICAgfVxuICB9XG5cbiAgcHJpdmF0ZSBnZXRDb252ZXJzYXRpb25JZCgpOiBzdHJpbmcge1xuICAgIC8vIEdlbmVyYXRlIG9yIHJldHJpZXZlIGEgY29udmVyc2F0aW9uIElEIGZvciB0aGlzIGNoYXQgc2Vzc2lvblxuICAgIGlmICghdGhpcy5jb252ZXJzYXRpb25JZCkge1xuICAgICAgdGhpcy5jb252ZXJzYXRpb25JZCA9IGBvYnNpZGlhbi0ke0RhdGUubm93KCl9LSR7TWF0aC5yYW5kb20oKS50b1N0cmluZygzNikuc3Vic3RyaW5nKDIsIDE1KX1gO1xuICAgIH1cbiAgICByZXR1cm4gdGhpcy5jb252ZXJzYXRpb25JZDtcbiAgfVxuXG4gIG9uQ2xvc2UoKTogdm9pZCB7XG4gICAgY29uc3QgeyBjb250ZW50RWwgfSA9IHRoaXM7XG4gICAgY29udGVudEVsLmVtcHR5KCk7XG4gIH1cbn1cblxuIl19
