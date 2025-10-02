import { Notice } from 'obsidian';

export interface ThothSettings {
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

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  id?: string;
}

export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  is_active: boolean;
  metadata: Record<string, any>;
  message_count: number;
  last_message_preview: string;
}

export interface ChatWindowState {
  sessionId: string;
  title: string;
  messages: ChatMessage[];
  isActive: boolean;
}

export interface NotificationProgress {
  notice: Notice;
  updateProgress: (progress: number, message?: string) => void;
  updateMessage: (message: string) => void;
  close: () => void;
  setType: (type: 'info' | 'success' | 'warning' | 'error') => void;
}

export const DEFAULT_SETTINGS: ThothSettings = {
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
  remoteMode: true,
  remoteEndpointUrl: 'http://localhost:8000',
  endpointHost: 'localhost',
  endpointPort: 8000,
  endpointBaseUrl: 'http://localhost:8000',
  corsOrigins: ['http://localhost:3000', 'http://127.0.0.1:8000'],

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
