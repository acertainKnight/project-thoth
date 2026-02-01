import { Notice } from 'obsidian';

// Export clean settings from settings.ts
export type { ThothSettings } from './settings';
export { DEFAULT_SETTINGS } from './settings';

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


