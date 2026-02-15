/**
 * Thoth Plugin Settings (Plugin-only)
 *
 * This file is ONLY for the Obsidian plugin.
 * Backend settings are in vault/thoth/_thoth/settings.json (separate file).
 */

import { ChatMessage, ChatWindowState } from './index';

export interface ThothSettings {
  // === CONNECTION ===
  remoteMode: boolean;              // True = connect to remote server, False = manage local agent (desktop only)
  remoteEndpointUrl: string;        // Thoth API URL for research/discovery (e.g., "http://localhost:8000")
  lettaEndpointUrl: string;         // Letta API URL for agent chats (e.g., "http://localhost:8284")

  // === API KEYS (optional - for displaying in UI) ===
  apiKeys?: {
    mistral?: string;
    openrouter?: string;
    openai?: string;
    anthropic?: string;
    semanticScholar?: string;
  };

  // === PLUGIN BEHAVIOR ===
  autoStartAgent: boolean;          // Auto-start local agent on Obsidian startup (desktop only)
  showStatusBar: boolean;           // Show status in status bar
  showRibbonIcon: boolean;          // Show ribbon icon

  // === CHAT HISTORY ===
  chatHistoryLimit: number;         // Max messages to keep in local history
  chatHistory: ChatMessage[];       // Local chat history (fallback)

  // === MULTI-CHAT ===
  enableMultipleChats: boolean;     // Allow multiple chat sessions
  maxChatWindows: number;           // Max concurrent chat windows
  chatWindowStates: ChatWindowState[]; // Saved chat window states
  activeChatSessionId: string | null; // Currently active session
  lettaAgentId: string | null;      // Cached Letta agent ID (avoids repeated fetches)

  // === UI PREFERENCES ===
  theme: 'auto' | 'light' | 'dark';
  compactMode: boolean;
  showAdvancedSettings: boolean;
  enableNotifications: boolean;
  notificationDuration: number;     // milliseconds

  // === UPDATE CHECKING ===
  checkForUpdates: boolean;                          // User-facing toggle
  releaseChannel: 'stable' | 'alpha' | 'nightly';   // Which channel the user installed from
  lastUpdateCheck: number;                           // Epoch ms of last successful check (internal)
  dismissedVersion: string | null;                   // Version the user dismissed (internal)
}

export const DEFAULT_SETTINGS: ThothSettings = {
  // Connection
  remoteMode: true,                 // Default to remote mode (works on desktop + mobile)
  remoteEndpointUrl: 'http://localhost:8000',  // Thoth API
  lettaEndpointUrl: 'http://localhost:8284',   // Letta API (via nginx proxy)

  // API Keys (empty by default - backend reads from vault/thoth/_thoth/settings.json)
  apiKeys: {},

  // Plugin Behavior
  autoStartAgent: false,            // Don't auto-start by default
  showStatusBar: true,
  showRibbonIcon: true,

  // Chat History
  chatHistoryLimit: 50,
  chatHistory: [],

  // Multi-chat
  enableMultipleChats: true,
  maxChatWindows: 5,
  chatWindowStates: [],
  activeChatSessionId: null,
  lettaAgentId: null,

  // UI Preferences
  theme: 'auto',
  compactMode: false,
  showAdvancedSettings: false,
  enableNotifications: true,
  notificationDuration: 5000,

  // Update Checking
  checkForUpdates: true,
  releaseChannel: 'stable',
  lastUpdateCheck: 0,
  dismissedVersion: null,
};
