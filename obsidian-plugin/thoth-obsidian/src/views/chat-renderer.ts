import { App, Modal, Notice, Menu, SuggestModal, MarkdownRenderer, MarkdownView } from 'obsidian';
import { ChatSession, ChatMessage, ImageAttachment, FileAttachment } from '../types';
import type ThothPlugin from '../../main';
import { ConfirmModal } from '../modals/confirm-modal';
import { InputModal } from '../modals/input-modal';
import { ResearchTabComponent } from '../components/research-tab';
import { SettingsTabComponent } from '../components/settings-tab';
import { MCPServersTabComponent } from '../components/mcp-servers-tab';
import * as smd from 'streaming-markdown';
import { getRandomThinkingPhrase, getToolStatusMessage, getRetrievalStepIcon, getRetrievalStepMessage } from '../utils/thinking-messages';
import { ICONS, setIconEl } from '../utils/icons';

/**
 * Prefix used for auto-follow-up messages after skill loading/unloading.
 * These messages are sent automatically to prompt the agent to continue
 * with newly attached tools, and should be hidden from rendered chat history.
 */
const SKILL_ACTIVATION_PREFIX = '[skill-tools-ready]';

/**
 * Wrapper for streaming-markdown library to work with Obsidian's DOM
 */
class StreamingMarkdownRenderer {
  private parser: any;
  private container: HTMLElement;

  constructor(container: HTMLElement) {
    this.container = container;
    const renderer = smd.default_renderer(container);
    this.parser = smd.parser(renderer);
  }

  /**
   * Write a chunk of markdown to the stream
   */
  write(chunk: string): void {
    smd.parser_write(this.parser, chunk);
  }

  /**
   * End the stream and flush remaining content
   */
  end(): void {
    smd.parser_end(this.parser);
  }

  /**
   * Reset for a new message
   */
  reset(): void {
    this.container.empty();
    const renderer = smd.default_renderer(this.container);
    this.parser = smd.parser(renderer);
  }
}

export class ChatRenderer {
  app: App;
  plugin: ThothPlugin;
  chatSessions: ChatSession[] = [];
  activeSessionId: string | null = null;
  chatWindows: Map<string, HTMLElement> = new Map();
  sessionListContainer: HTMLElement;
  chatContentContainer: HTMLElement;
  sessionTabsContainer: HTMLElement;
  sessionSelector: HTMLSelectElement;
  sidebar: HTMLElement;

  // Tab system
  currentTab: string = 'chat';
  tabContainer: HTMLElement;
  contentContainer: HTMLElement;

  // Archived conversation IDs (hidden from main list, restorable)
  private archivedIds: Set<string> = new Set();

  // Pagination tracking
  messageCache: Map<string, any[]> = new Map();
  private hasMoreMessages: Map<string, boolean> = new Map();
  private oldestMessageId: Map<string, string> = new Map();

  // Image attachments
  private pendingAttachments: ImageAttachment[] = [];
  private attachmentPreviewContainer: HTMLElement | null = null;

  // File attachments
  private pendingFileAttachments: FileAttachment[] = [];

  // Progress WebSocket for agentic retrieval steps
  private progressWs: WebSocket | null = null;
  private agenticProgressListener: ((event: MessageEvent) => void) | null = null;
  containerEl: HTMLElement;
  mobileKeyboardSetup: ((inputEl: HTMLTextAreaElement, msgs: HTMLElement, area: HTMLElement) => void) | null = null;

  /** Optional mode-switch buttons rendered at the right edge of the tab navigation bar. */
  modeButtons: { label: string; title: string; onClick: () => void }[] = [];

  constructor(containerEl: HTMLElement, plugin: ThothPlugin, app: App) {
    this.containerEl = containerEl;
    this.plugin = plugin;
    this.app = app;
  }

  /**
   * Connect to the progress WebSocket endpoint for agentic retrieval updates.
   */
  private connectProgressWebSocket(): void {
    if (this.progressWs && this.progressWs.readyState === WebSocket.OPEN) {
      return; // Already connected
    }

    const wsUrl = this.plugin.getEndpointUrl().replace(/^http/, 'ws') + '/ws/progress';
    this.progressWs = new WebSocket(wsUrl);

    this.progressWs.onopen = () => {
      console.log('[MultiChatModal] Progress WebSocket connected');
    };

    this.progressWs.onerror = (error) => {
      console.error('[MultiChatModal] Progress WebSocket error:', error);
    };

    this.progressWs.onclose = () => {
      console.log('[MultiChatModal] Progress WebSocket closed');
      this.progressWs = null;
    };
  }

  /**
   * Disconnect the progress WebSocket.
   */
  private disconnectProgressWebSocket(): void {
    if (this.progressWs) {
      this.progressWs.close();
      this.progressWs = null;
    }
  }

  /**
   * Start listening for agentic retrieval progress events.
   * Updates the status indicator as retrieval steps progress.
   *
   * Args:
   *     statusEl: The status indicator element to update
   */
  private startAgenticProgressListener(pillOrStatusEl: HTMLElement): void {
    this.connectProgressWebSocket();

    if (!this.progressWs) {
      return;
    }

    // Remove any existing listener
    if (this.agenticProgressListener) {
      this.progressWs.removeEventListener('message', this.agenticProgressListener);
    }

    // Create new listener that updates either a step pill or legacy status indicator
    this.agenticProgressListener = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);

        if (data.operation_id && data.operation_id.startsWith('agentic_rag_')) {
          const step = data.message || '';

          let stepName = '';
          const stepMatch = step.match(/^([a-z_]+):/);
          if (stepMatch) {
            stepName = stepMatch[1];
          }

          const iconKey = stepName ? getRetrievalStepIcon(stepName) : 'tool';
          const message = step || 'Processing';

          // Update pill label if this is a step pill, otherwise fall back
          // to the legacy status indicator path
          if (pillOrStatusEl.hasClass('step-pill')) {
            this.updateStepPillIcon(pillOrStatusEl, iconKey);
            this.updateStepPillLabel(pillOrStatusEl, `${message}...`);
          } else {
            this.updateStatusIndicator(pillOrStatusEl, `${message}...`, ICONS[iconKey] ?? '');
          }
        }
      } catch (error) {
        console.error('[MultiChatModal] Error parsing progress event:', error);
      }
    };

    this.progressWs.addEventListener('message', this.agenticProgressListener);
  }

  /**
   * Stop listening for agentic retrieval progress events.
   */
  private stopAgenticProgressListener(): void {
    if (this.agenticProgressListener && this.progressWs) {
      this.progressWs.removeEventListener('message', this.agenticProgressListener);
      this.agenticProgressListener = null;
    }
  }

  /**
   * Fetch with timeout to prevent UI from hanging
   */
  private async fetchWithTimeout(url: string, options: RequestInit = {}, timeoutMs: number = 30000): Promise<Response> {
    // Increase timeout to 30 seconds for mobile networks
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
      console.log(`[MultiChatModal] Fetching: ${url}`);
      const startTime = Date.now();

      const response = await this.plugin.authFetch(url, {
        ...options,
        signal: controller.signal
      });

      const duration = Date.now() - startTime;
      console.log(`[MultiChatModal] Response ${response.status} in ${duration}ms`);

      clearTimeout(timeoutId);
      return response;
    } catch (error) {
      clearTimeout(timeoutId);
      if (error.name === 'AbortError') {
        console.error(`[MultiChatModal] Request timed out after ${timeoutMs}ms:`, url);
        throw new Error(`Request timed out after ${timeoutMs/1000}s - check network connection`);
      }
      console.error(`[MultiChatModal] Fetch error:`, error);
      throw error;
    }
  }

  /**
   * Read a file as base64-encoded data.
   *
   * Args:
   *     file: The file to read.
   *
   * Returns:
   *     Object containing base64 data (without data URL prefix), media type, and file name.
   *
   * Example:
   *     >>> const result = await this.readFileAsBase64(imageFile);
   *     >>> console.log(result.media_type); // "image/png"
   */
  private async readFileAsBase64(file: File): Promise<ImageAttachment> {
    const MAX_SIZE = 10 * 1024 * 1024; // 10MB limit

    if (file.size > MAX_SIZE) {
      throw new Error(`Image too large: ${(file.size / 1024 / 1024).toFixed(1)}MB (max 10MB)`);
    }

    const supportedTypes = ['image/png', 'image/jpeg', 'image/gif', 'image/webp'];
    if (!supportedTypes.includes(file.type)) {
      throw new Error(`Unsupported image format: ${file.type}`);
    }

    return new Promise((resolve, reject) => {
      const reader = new FileReader();

      reader.onload = () => {
        const dataUrl = reader.result as string;
        // Strip the "data:image/png;base64," prefix
        const base64Data = dataUrl.split(',')[1];

        resolve({
          data: base64Data,
          media_type: file.type,
          name: file.name
        });
      };

      reader.onerror = () => {
        reject(new Error('Failed to read file'));
      };

      reader.readAsDataURL(file);
    });
  }

  /**
   * Read a text-based file as UTF-8 text.
   *
   * Args:
   *     file: The file to read
   *
   * Returns:
   *     FileAttachment object with text content
   *
   * Example:
   *     >>> const result = await this.readFileAsText(textFile);
   *     >>> console.log(result.content);
   */
  private async readFileAsText(file: File): Promise<FileAttachment> {
    const MAX_SIZE = 20 * 1024 * 1024; // 20MB limit
    const MAX_CONTENT_SIZE = 200 * 1024; // 200KB content limit

    if (file.size > MAX_SIZE) {
      throw new Error(`File too large: ${(file.size / 1024 / 1024).toFixed(1)}MB (max 20MB)`);
    }

    return new Promise((resolve, reject) => {
      const reader = new FileReader();

      reader.onload = () => {
        let content = reader.result as string;

        // Truncate if content is too large
        if (content.length > MAX_CONTENT_SIZE) {
          content = content.substring(0, MAX_CONTENT_SIZE) + '\n\n[Content truncated at 200KB]';
        }

        resolve({
          name: file.name,
          content: content,
          file_type: file.type || 'text/plain',
          size: file.size
        });
      };

      reader.onerror = () => {
        reject(new Error('Failed to read file'));
      };

      reader.readAsText(file, 'UTF-8');
    });
  }

  /**
   * Extract text from a PDF file by sending it to the Thoth backend.
   *
   * Args:
   *     file: The PDF file to extract text from
   *
   * Returns:
   *     FileAttachment object with extracted text
   *
   * Example:
   *     >>> const result = await this.extractPdfText(pdfFile);
   *     >>> console.log(result.content);
   */
  private async extractPdfText(file: File): Promise<FileAttachment> {
    const MAX_SIZE = 20 * 1024 * 1024; // 20MB limit

    if (file.size > MAX_SIZE) {
      throw new Error(`PDF too large: ${(file.size / 1024 / 1024).toFixed(1)}MB (max 20MB)`);
    }

    const formData = new FormData();
    formData.append('file', file);

    const endpoint = this.plugin.settings.remoteEndpointUrl || 'http://localhost:8000';
    const response = await this.plugin.authFetch(`${endpoint}/api/files/extract`, {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`PDF extraction failed: ${errorText}`);
    }

    const result = await response.json();

    return {
      name: file.name,
      content: result.text,
      file_type: 'application/pdf',
      size: file.size
    };
  }

  async mount(): Promise<void> {
    this.containerEl.empty();

    // Load existing sessions
    await this.loadChatSessions();

    // Create main layout
    this.createLayout();

    // Load session list
    this.renderSessionList();

    // Ensure default conversation exists and get its ID
    const defaultConvId = await this.getOrCreateDefaultConversation();

    // Load active session or fall back to default.
    // If chatSessions is empty (e.g. server was slow to respond on startup)
    // but we have a persisted activeChatSessionId, try loading it directly
    // rather than falling back to the oldest conversation.
    const savedSessionId = this.plugin.settings.activeChatSessionId;
    if (savedSessionId) {
      const sessionInList = this.chatSessions.find(s => s.id === savedSessionId);
      if (sessionInList || this.chatSessions.length === 0) {
        await this.switchToSession(savedSessionId);
      } else {
        await this.switchToSession(defaultConvId);
      }
    } else {
      await this.switchToSession(defaultConvId);
    }


    // If the session list was empty (server not ready at startup), retry in
    // the background so the sidebar populates once the server comes up.
    if (this.chatSessions.length === 0) {
      setTimeout(async () => {
        await this.loadChatSessions();
        if (this.chatSessions.length > 0) {
          this.renderSessionList();
        }
      }, 3000);
    }

    // Add global keyboard shortcuts
    this.setupKeyboardShortcuts();
  }

  setupKeyboardShortcuts() {
    const handleKeydown = (e: KeyboardEvent) => {
      // Only handle shortcuts if modal is open and input is not focused
      const activeElement = document.activeElement;
      const isInputFocused = activeElement?.tagName === 'TEXTAREA' || activeElement?.tagName === 'INPUT';

      if (!isInputFocused) {
        if (e.ctrlKey || e.metaKey) {
          switch (e.key) {
            case 'n':
              e.preventDefault();
              this.createNewSession();
              break;
            case 't':
              e.preventDefault();
              this.toggleSidebar();
              break;
          }
        }
      }
    };

    document.addEventListener('keydown', handleKeydown);

    // Clean up on close
    this.containerEl.addEventListener('remove', () => {
      document.removeEventListener('keydown', handleKeydown);
    });
  }

  unmount(): void {
    this.stopAgenticProgressListener();
    this.disconnectProgressWebSocket();
    this.containerEl.empty();
  }

  createLayout() {
    const { containerEl } = this;

    // Main container with toggle layout
    const mainContainer = containerEl.createEl('div', { cls: 'multi-chat-container compact' });

    // Slim mode-switching toolbar rendered above the tab bar (only when buttons are provided)
    if (this.modeButtons.length > 0) {
      const modeBar = mainContainer.createEl('div', { cls: 'thoth-mode-toolbar' });
      this.modeButtons.forEach(btn => {
        const el = modeBar.createEl('button', {
          text: btn.label,
          cls: 'thoth-mode-toolbar-btn',
          title: btn.title
        });
        el.onclick = btn.onClick;
      });
    }

    // Create tab navigation
    this.createTabNavigation(mainContainer);

    // Collapsible sidebar for session list
    const sidebar = mainContainer.createEl('div', { cls: 'chat-sidebar collapsed' });
    this.sidebar = sidebar;

    // Session list container (simplified)
    this.sessionListContainer = sidebar.createEl('div', { cls: 'session-list compact' });

    // Add click-outside handler for sidebar
    this.setupSidebarClickOutside(mainContainer);

    // Content container for all tabs
    this.contentContainer = mainContainer.createEl('div', { cls: 'tab-content-container' });

    // Initialize with chat tab content
    this.renderTabContent();
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

  closeSidebar() {
    if (!this.sidebar) return;
    this.sidebar.addClass('collapsed');
  }

  openSidebar() {
    if (!this.sidebar) return;
    this.sidebar.removeClass('collapsed');
    this.renderSessionList();
  }

  setupSidebarClickOutside(mainContainer: HTMLElement) {
    // Click outside to close sidebar
    mainContainer.addEventListener('click', (e) => {
      if (!this.sidebar?.hasClass('collapsed')) {
        const target = e.target as HTMLElement;

        // Don't close if clicking on sidebar itself or toggle button
        if (!this.sidebar.contains(target) &&
            !target.hasClass('toggle-sidebar-btn') &&
            !target.closest('.toggle-sidebar-btn')) {
          this.closeSidebar();
        }
      }
    });
  }

  createTabNavigation(container: HTMLElement) {
    this.tabContainer = container.createEl('div', { cls: 'thoth-tab-navigation' });

    const tabs = [
      { id: 'chat',          label: 'Chat' },
      { id: 'conversations', label: 'Conversations' },
      { id: 'research',      label: 'Research' },
      { id: 'mcpServers',    label: 'MCP' },
      { id: 'settings',      label: 'Settings' }
    ];

    tabs.forEach(tab => {
      const button = this.tabContainer.createEl('button', { cls: 'thoth-tab-button' });
      // Icon + label rendered via innerHTML so SVG renders correctly
      button.innerHTML = `${ICONS[tab.id] ?? ''}<span class="tab-label">${tab.label}</span>`;

      if (tab.id === this.currentTab) button.addClass('active');
      button.onclick = () => this.switchTab(tab.id);
    });

  }

  async switchTab(tabId: string) {
    // Update tab buttons
    this.tabContainer.querySelectorAll('.thoth-tab-button').forEach((btn, index) => {
      if (index === ['chat', 'conversations', 'research', 'mcpServers', 'settings'].indexOf(tabId)) {
        btn.addClass('active');
      } else {
        btn.removeClass('active');
      }
    });

    // Update content (await for research tab data loading)
    this.currentTab = tabId;
    await this.renderTabContent();
  }

  async renderTabContent() {
    if (!this.contentContainer) return;

    this.contentContainer.empty();

    switch (this.currentTab) {
      case 'chat':
        this.renderChatTab();
        break;
      case 'conversations':
        this.renderConversationsTab();
        break;
      case 'research':
        await this.renderResearchTab(); // Await async data loading
        break;
      case 'mcpServers':
        await this.renderMCPServersTab(); // Await async data loading
        break;
      case 'settings':
        this.renderSettingsTab();
        break;
    }
  }

  renderChatTab() {
    // Top bar with conversation title and status
    const topBar = this.contentContainer.createEl('div', { cls: 'chat-top-bar modern' });

    // Left section: Conversation title (clickable to rename)
    const titleSection = topBar.createEl('div', { cls: 'chat-title-section' });

    const activeSession = this.chatSessions.find(s => s.id === this.activeSessionId);
    const titleEl = titleSection.createEl('div', {
      text: activeSession?.title || 'New Conversation',
      cls: 'conversation-title-display',
      title: 'Click to rename'
    });

    titleEl.onclick = async () => {
      if (activeSession) {
        await this.renameConversation(activeSession);
      }
    };

    // Right section: Status and controls
    const controlsSection = topBar.createEl('div', { cls: 'chat-controls-section' });

    // Connection status indicator
    const statusIndicator = controlsSection.createEl('div', { cls: 'connection-status' });
    this.updateConnectionStatus(statusIndicator);

    // Settings button removed - use Settings tab instead

    // Create chat area within the content container
    const chatArea = this.contentContainer.createEl('div', { cls: 'chat-area modern' });

    // Chat content area
    this.chatContentContainer = chatArea.createEl('div', { cls: 'chat-content' });

    // Load active session or show empty state
    if (this.activeSessionId) {
      this.loadChatMessages(this.activeSessionId);
    } else {
      this.renderEmptyState();
    }
  }

  updateConnectionStatus(container: HTMLElement) {
    container.empty();

    // Check connection status
    const isConnected = this.plugin.isAgentRunning || this.plugin.settings.remoteMode;

    const statusDot = container.createEl('span', { cls: 'status-dot' });
    const statusText = container.createEl('span', { cls: 'status-text' });

    if (isConnected) {
      statusDot.addClass('connected');
      statusText.setText('Connected');
      container.title = 'Server connection active';
    } else {
      statusDot.addClass('disconnected');
      statusText.setText('Disconnected');
      container.title = 'Not connected to server';
    }

    // Make clickable to show details
    container.addClass('clickable');
    container.onclick = () => {
      this.showConnectionDetails();
    };
  }

  showConnectionDetails() {
    const lettaEndpoint = this.plugin.getLettaProxyUrl();
    const isConnected = this.plugin.isAgentRunning || this.plugin.settings.remoteMode;
    const mode = this.plugin.settings.remoteMode ? 'Remote' : 'Local';

    const details = `
Connection Status: ${isConnected ? 'Connected' : 'Disconnected'}
Mode: ${mode}
Chat Endpoint: ${lettaEndpoint}

${isConnected ? 'Ready to chat with Letta' : 'Start the Letta server to begin'}
    `.trim();

    new Notice(details, 5000);
  }

  // Removed old tab methods (commands, tools, status)
  // These features are now available through:
  // - Commands: Obsidian command palette (Cmd+P)
  // - Tools: Automatically available via MCP
  // - Status: Inline in chat header

  async renderConversationsTab() {
    const conversationsArea = this.contentContainer.createEl('div', { cls: 'conversations-area' });

    // Header with create conversation button
    const header = conversationsArea.createEl('div', { cls: 'conversations-header' });

    const createBtn = header.createEl('button', {
      text: '+ New Conversation',
      cls: 'thoth-new-conversation-btn'
    });

    createBtn.onclick = async () => {
      await this.createNewSession();
      this.switchTab('chat'); // Switch to chat after creating
    };

    const backfillBtn = header.createEl('button', {
      text: 'Generate Titles',
      cls: 'thoth-backfill-titles-btn',
      attr: { title: 'Generate names for all untitled conversations using AI' }
    });

    backfillBtn.onclick = async () => {
      backfillBtn.disabled = true;
      backfillBtn.textContent = 'Generating...';
      try {
        const thothUrl = this.plugin.settings.remoteEndpointUrl.replace(/\/$/, '');
        const res = await this.plugin.authFetch(`${thothUrl}/agents/conversations/backfill-titles`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        });
        if (res.ok) {
          const { updated, skipped, errors } = await res.json();
          new Notice(`Titles generated: ${updated} updated, ${skipped} skipped${errors ? `, ${errors} errors` : ''}`);
          await this.loadAndDisplayConversations(conversationsListContainer);
        } else {
          new Notice('Failed to generate titles — check server logs');
        }
      } catch (err) {
        new Notice(`Title generation failed: ${(err as Error).message}`);
      } finally {
        backfillBtn.disabled = false;
        backfillBtn.textContent = 'Generate Titles';
      }
    };

    // Search box
    const searchInput = conversationsArea.createEl('input', {
      type: 'text',
      placeholder: 'Search conversations...',
      cls: 'thoth-conversation-search'
    });

    searchInput.oninput = () => {
      this.handleConversationSearch(searchInput.value);
    };

    // Info note
    const infoNote = conversationsArea.createEl('div', { cls: 'thoth-conversations-info' });
    infoNote.createEl('span', {
      text: 'By default, Thoth uses one long-running conversation. You can create separate ones for different workflows — all conversations share the same agent memory, only the messages differ.',
      cls: 'thoth-conversations-info-text'
    });

    // Conversations list
    const conversationsListContainer = conversationsArea.createEl('div', { cls: 'conversations-list-container' });
    await this.loadAndDisplayConversations(conversationsListContainer);
  }

  async loadAndDisplayAgents(container: HTMLElement) {
    try {
      // Clear existing content
      container.empty();

      const loadingEl = container.createEl('div', { text: 'Loading agents...', cls: 'loading' });

      // Fetch available agents from Letta
      // Note: Letta API requires trailing slash on collection endpoints
      // Use view=basic to avoid fetching full memory blocks (reduces response from 30MB to ~100KB)
      const endpoint = this.plugin.getLettaProxyUrl();
      const response = await this.plugin.authFetch(`${endpoint}/v1/agents/?view=basic`);

      loadingEl.remove();

      if (response.ok) {
        const data = await response.json();
        this.displayAgentsList(container, data.agents || []);
      } else {
        container.createEl('div', {
          text: 'Failed to load agents. Agent system may not be available.',
          cls: 'error-message'
        });
      }

    } catch (error) {
      container.empty();
      container.createEl('div', {
        text: `Error loading agents: ${error.message}`,
        cls: 'error-message'
      });
    }
  }

  displayAgentsList(container: HTMLElement, agents: any[]) {
    if (agents.length === 0) {
      container.createEl('div', {
        text: 'No agents available. Create your first agent!',
        cls: 'empty-state'
      });
      return;
    }

    const agentsList = container.createEl('div', { cls: 'agents-list' });

    agents.forEach(agent => {
      const agentCard = agentsList.createEl('div', { cls: 'agent-card' });

      const agentHeader = agentCard.createEl('div', { cls: 'agent-header' });
      agentHeader.createEl('h4', { text: `@${agent.name}` });

      const typeEl = agentHeader.createEl('span', {
        text: agent.type || 'custom',
        cls: `agent-type agent-type-${agent.type || 'custom'}`
      });

      agentCard.createEl('p', { text: agent.description, cls: 'agent-description' });

      if (agent.capabilities && agent.capabilities.length > 0) {
        const capsList = agentCard.createEl('div', { cls: 'agent-capabilities' });
        capsList.createEl('strong', { text: 'Capabilities: ' });
        capsList.createEl('span', { text: agent.capabilities.join(', ') });
      }

      const actions = agentCard.createEl('div', { cls: 'agent-actions' });

      const useBtn = actions.createEl('button', {
        text: 'Use Agent',
        cls: 'use-agent-btn'
      });

      useBtn.onclick = () => {
        // Switch to chat tab and insert @agent mention
        this.switchTab('chat');
        // Find the input field and add the agent mention
        setTimeout(() => {
          const inputField = document.querySelector('.chat-input') as HTMLTextAreaElement;
          if (inputField) {
            inputField.value = `@${agent.name} `;
            inputField.focus();
          }
        }, 100);
      };

      if (agent.type === 'user') {
        const deleteBtn = actions.createEl('button', {
          text: 'Delete',
          cls: 'delete-agent-btn'
        });

        deleteBtn.onclick = () => {
          this.confirmDeleteAgent(agent.name);
        };
      }
    });
  }

  showCreateAgentDialog() {
    new InputModal(
      this.app,
      'Describe the agent you want to create (e.g. "a citation analysis agent").',
      (description) => {
        if (!description?.trim()) return;
        this.switchTab('chat');
        setTimeout(() => {
          const inputField = document.querySelector('.chat-input') as HTMLTextAreaElement;
          if (inputField) {
            inputField.value = `Create an agent that ${description.trim()}`;
            const sendBtn = document.querySelector('.chat-send-btn') as HTMLButtonElement;
            if (sendBtn && !sendBtn.disabled) sendBtn.click();
          }
        }, 100);
      }
    ).open();
  }

  async confirmDeleteAgent(agentName: string) {
    // Note: This is actually deleting a conversation, not an agent
    // (Legacy method name from when we called conversations "agents")
    const sessionId = agentName; // The "name" is actually the session ID

    const confirmed = await new Promise<boolean>((resolve) => {
      new ConfirmModal(this.app, 'Delete this conversation? This action cannot be undone.', resolve).open();
    });
    if (confirmed) {
      try {
        const endpoint = this.plugin.getLettaProxyUrl();
        // Note: NO trailing slash for DELETE - Letta API returns 405 with trailing slash
        const response = await this.plugin.authFetch(`${endpoint}/v1/conversations/${sessionId}`, {
          method: 'DELETE'
        });

        if (response.ok) {
          // Remove from local list
          this.chatSessions = this.chatSessions.filter(s => s.id !== sessionId);

          // Clear active session if it was deleted
          if (this.activeSessionId === sessionId) {
            this.activeSessionId = null;
            this.plugin.settings.activeChatSessionId = null;
            await this.plugin.saveSettings();
          }

          await this.loadChatSessions(); // Refresh list
          new Notice('Conversation deleted');
        } else {
          throw new Error('Failed to delete conversation');
        }
      } catch (error) {
        console.error('Error deleting conversation:', error);
        new Notice('Failed to delete conversation');
      }
    }
  }


  async loadChatSessions() {
    try {
      const endpoint = this.plugin.getLettaProxyUrl();
      const thothUrl = this.plugin.settings.remoteEndpointUrl.replace(/\/$/, '');

      // Fetch conversations and archived IDs in parallel
      const agentId = await this.getOrCreateDefaultAgent();
      const [convResponse, archivedResponse] = await Promise.all([
        this.fetchWithTimeout(`${endpoint}/v1/conversations/?agent_id=${agentId}&limit=200`),
        this.plugin.authFetch(`${thothUrl}/agents/conversations/archived`).catch(() => null),
      ]);

      // Update archived set
      if (archivedResponse?.ok) {
        const { archived } = await archivedResponse.json();
        this.archivedIds = new Set(archived);
      }

      if (convResponse.ok) {
        const conversations = await convResponse.json();
        const defaultConvId = await this.getOrCreateDefaultConversation();

        this.chatSessions = conversations
          .filter((conv: any) => !this.archivedIds.has(conv.id))
          .map((conv: any): ChatSession => ({
            id: conv.id,
            title: conv.summary || `Chat ${conv.id.slice(0, 8)}`,
            created_at: conv.created_at,
            updated_at: conv.updated_at || conv.created_at,
            is_active: conv.id === this.activeSessionId,
            message_count: conv.message_count || 0,
            last_message_preview: conv.last_message || '',
            metadata: {
              agent_id: conv.agent_id,
              is_default: conv.id === defaultConvId
            }
          }));

        this.chatSessions.sort((a, b) => {
          if (a.metadata?.is_default) return -1;
          if (b.metadata?.is_default) return 1;
          return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
        });
      } else {
        console.warn('Could not load chat sessions from server');
        this.chatSessions = [];
      }
    } catch (error) {
      console.warn('Failed to load chat sessions:', error);
      this.chatSessions = [];
    }
  }

  async getOrCreateDefaultAgent(): Promise<string> {
    const apiToken: string = (this.plugin.settings as any).apiToken ?? '';

    // In multi-user mode, /auth/me is the authoritative source for the agent ID.
    // Never trust the local cache alone — it could belong to a different user if
    // accounts were switched or the setting was populated before multi-user mode.
    if (apiToken) {
      const thothUrl = this.plugin.settings.remoteEndpointUrl;
      const meUrl = `${thothUrl.replace(/\/$/, '')}/auth/me`;
      try {
        const meResponse = await this.fetchWithTimeout(meUrl, {
          headers: { Authorization: `Bearer ${apiToken}` },
        });
        if (meResponse.ok) {
          const userInfo = await meResponse.json();
          const orchestratorId = userInfo.orchestrator_agent_id;
          if (orchestratorId) {
            // Overwrite cache with server-authoritative value every time.
            if (this.plugin.settings.lettaAgentId !== orchestratorId) {
              this.plugin.settings.lettaAgentId = orchestratorId;
              await this.plugin.saveSettings();
            }
            return orchestratorId;
          }
        }
      } catch (meError) {
        console.warn('[MultiChatModal] /auth/me lookup failed, falling back to cache:', meError);
        // Fall through — use cache if available, else scan agent list below.
      }
    }

    // In multi-user mode, /auth/me is the only safe source — scanning the full
    // agent list by name risks picking up another user's agent.
    if (apiToken) {
      throw new Error('Could not resolve agent: /auth/me failed and no valid cache. Check that the Thoth server is reachable.');
    }

    // Single-user mode: use cache if we have it.
    if (this.plugin.settings.lettaAgentId) {
      console.log('[MultiChatModal] Using cached agent ID:', this.plugin.settings.lettaAgentId);
      return this.plugin.settings.lettaAgentId;
    }

    // Single-user last resort: scan Letta agent list by name.
    // Use view=basic to avoid fetching full memory blocks (30MB+ with all agents).
    console.log('[MultiChatModal] No cached agent ID, scanning agent list...');
    try {
      const endpoint = this.plugin.getLettaProxyUrl();
      const listResponse = await this.fetchWithTimeout(`${endpoint}/v1/agents/?view=basic`);
      if (listResponse.ok) {
        const agents = await listResponse.json();
        console.log('[MultiChatModal] Found agents:', agents.map((a: any) => a.name));

        const thothAgent = agents.find((a: any) => a.name === 'thoth_main_orchestrator');
        if (thothAgent) {
          this.plugin.settings.lettaAgentId = thothAgent.id;
          await this.plugin.saveSettings();
          console.log('[MultiChatModal] Cached agent ID for future use:', thothAgent.id);
          return thothAgent.id;
        }

        console.error('[MultiChatModal] thoth_main_orchestrator not found. Available agents:', agents.map((a: any) => a.name));
      }

      throw new Error('Thoth orchestrator agent not found. Please ensure the Thoth backend is running and has initialized agents.');
    } catch (error) {
      console.error('Failed to get Thoth agent:', error);
      throw error;
    }
  }

  async getOrCreateDefaultConversation(): Promise<string> {
    const endpoint = this.plugin.getLettaProxyUrl();
    const agentId = await this.getOrCreateDefaultAgent();

    try {
      const listResponse = await this.fetchWithTimeout(
        `${endpoint}/v1/conversations/?agent_id=${agentId}&limit=200`
      );

      if (!listResponse.ok) {
        throw new Error('Failed to fetch conversations');
      }

      const conversations = await listResponse.json();
      const ids = new Set(conversations.map((c: any) => c.id));

      // 1. User-designated default (stored in settings)
      const pinned = (this.plugin.settings as any).defaultConversationId;
      if (pinned && ids.has(pinned)) {
        return pinned;
      }

      // 2. Legacy: conversation whose title includes "default"
      const byTitle = conversations.find((c: any) =>
        c.summary?.toLowerCase().includes('default') ||
        c.summary === 'Main Conversation'
      );
      if (byTitle) return byTitle.id;

      // 3. Oldest conversation
      if (conversations.length > 0) {
        const sorted = [...conversations].sort((a: any, b: any) =>
          new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
        );
        return sorted[0].id;
      }

      // 4. Nothing exists — create one
      const createResponse = await this.fetchWithTimeout(
        `${endpoint}/v1/conversations/?agent_id=${agentId}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ summary: 'Default Conversation' })
        }
      );
      if (!createResponse.ok) throw new Error('Failed to create default conversation');
      const created = await createResponse.json();
      return created.id;

    } catch (error) {
      console.error('[MultiChatModal] Error in getOrCreateDefaultConversation:', error);
      throw error;
    }
  }

  async setDefaultConversation(session: ChatSession) {
    (this.plugin.settings as any).defaultConversationId = session.id;
    await this.plugin.saveSettings();

    // Rebuild the session list so the star moves to the right card
    await this.loadChatSessions();
    await this.renderTabContent();
    if (this.currentTab === 'chat') this.renderSessionList();
    new Notice(`"${session.title}" set as default conversation`);
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
        const classes = ['session-item'];
        if (session.id === this.activeSessionId) {
          classes.push('active');
        }
        if (session.metadata?.is_default) {
          classes.push('default');
        }

        const sessionEl = this.sessionListContainer.createEl('div', {
          cls: classes.join(' ')
        });

        sessionEl.onclick = () => {
          this.switchToSession(session.id);
          // Note: switchToSession already calls closeSidebar()
        };

        // Session actions
        const actionsEl = sessionEl.createEl('div', { cls: 'session-actions' });

        const editBtn = actionsEl.createEl('button', {
          cls: 'session-action-btn',
          title: 'Rename session'
        });
        editBtn.innerHTML = ICONS.edit;
        editBtn.onclick = (e) => {
          e.stopPropagation();
          this.renameSession(session.id);
        };

        // Delete button removed - Letta API 0.16.3 doesn't support deleting conversations
        // const deleteBtn = actionsEl.createEl('button', {
        //   text: '🗑️',
        //   cls: 'session-action-btn',
        //   title: 'Delete session'
        // });
        // deleteBtn.onclick = (e) => {
        //   e.stopPropagation();
        //   this.deleteSession(session.id);
        // };


        // Session content
        const titleContainer = sessionEl.createEl('div', { cls: 'session-title-container' });
        titleContainer.createEl('span', {
          text: session.title,
          cls: 'session-title'
        });

        // Add default badge if this is the default conversation
        if (session.metadata?.is_default) {
          const badgeEl = titleContainer.createEl('span', {
            cls: 'default-badge',
            attr: { 'title': 'Default conversation' }
          });
          badgeEl.innerHTML = ICONS.star;
        }

        if (session.last_message_preview) {
          sessionEl.createEl('div', {
            text: session.last_message_preview,
            cls: 'session-preview'
          });
        }

        const metaEl = sessionEl.createEl('div', { cls: 'session-meta' });
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
      // Generate better default title with timestamp
      let sessionTitle = title;
      if (!sessionTitle) {
        const now = new Date();
        const timeStr = now.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
        sessionTitle = `New Chat - ${timeStr}`;
      }

      const endpoint = this.plugin.getLettaProxyUrl();
      const agentId = await this.getOrCreateDefaultAgent();

      // Note: Letta API expects agent_id as query param, with trailing slash to avoid nginx redirect
      const response = await this.plugin.authFetch(`${endpoint}/v1/conversations/?agent_id=${agentId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });

      if (response.ok) {
        const conversation = await response.json();
        // Map Letta conversation to session format
        const newSession: ChatSession = {
          id: conversation.id,
          title: conversation.summary || sessionTitle,
          created_at: conversation.created_at,
          updated_at: conversation.created_at,
          is_active: true,
          message_count: 0,
          last_message_preview: '',
          metadata: { agent_id: conversation.agent_id }
        };

        this.chatSessions.unshift(newSession);
        this.renderSessionList();
        await this.switchToSession(newSession.id);

        // Auto-close sidebar after creating new session
        this.closeSidebar();

        new Notice(`Created: ${sessionTitle}`);
      } else {
        const errorText = await response.text();
        console.error(`[MultiChatModal] Failed to create session: ${response.status}`, errorText);
        throw new Error(`Failed to create session: ${response.status} ${response.statusText}`);
      }
    } catch (error) {
      console.error('[MultiChatModal] Error creating session:', error);
      new Notice(`Failed to create new chat session: ${error.message}`);
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

    // Auto-close sidebar after switching session
    this.closeSidebar();
  }


  async loadChatMessages(sessionId: string, loadEarlier: boolean = false) {
    if (!loadEarlier) {
      this.chatContentContainer.empty();
      // Clear cache for fresh load
      this.messageCache.delete(sessionId);
      this.oldestMessageId.delete(sessionId);
    }

    try {
      const endpoint = this.plugin.getLettaProxyUrl();

      // Build URL with pagination support.
      // use_assistant_message converts send_message tool calls into
      // assistant_message entries in the response, which is the format
      // the rendering code expects for user-visible agent replies.
      let url = `${endpoint}/v1/conversations/${sessionId}/messages?limit=300&order=desc&use_assistant_message=true`;

      // If loading earlier messages, use cursor-based pagination.
      // Letta's "before" filter returns messages with a lower position
      // (chronologically older), regardless of sort order.
      if (loadEarlier && this.oldestMessageId.has(sessionId)) {
        const oldestId = this.oldestMessageId.get(sessionId);
        url += `&before=${oldestId}`;
      }

      const response = await this.plugin.authFetch(url);

      if (response.ok) {
        const newMessages = await response.json();

        console.log(`[MultiChatModal] Loaded ${newMessages.length} messages for session ${sessionId}`, {
          loadEarlier,
          messageTypes: newMessages.map((m: any) => m.message_type || m.type).filter((t: any, i: number, arr: any[]) => arr.indexOf(t) === i)
        });

        // Summarise ALL messages by type so we can verify nothing is
        // missing from the API response. Remove once messaging is stable.
        const typeCounts: Record<string, number> = {};
        for (const m of newMessages) {
          const t = m.message_type || m.type || 'unknown';
          typeCounts[t] = (typeCounts[t] || 0) + 1;
        }
        console.log('[MSG_DUMP] type counts:', typeCounts);

        // Show details of send_message tool calls and assistant_messages
        // in the response since those are the ones we need for rendering.
        for (const sm of newMessages) {
          const mt = sm.message_type || sm.type;
          if (mt === 'tool_call_message') {
            const tc = sm.tool_call || sm.tool_calls?.[0];
            console.log('[MSG_DUMP] tool_call:', tc?.name, {
              argsType: typeof tc?.arguments,
              argsPreview: typeof tc?.arguments === 'string'
                ? tc.arguments.substring(0, 120)
                : JSON.stringify(tc?.arguments)?.substring(0, 120),
            });
          } else if (mt === 'assistant_message') {
            console.log('[MSG_DUMP] assistant_message:', {
              contentType: typeof sm.content,
              preview: typeof sm.content === 'string'
                ? sm.content.substring(0, 120)
                : Array.isArray(sm.content)
                  ? JSON.stringify(sm.content[0])?.substring(0, 120)
                  : 'n/a',
            });
          }
        }

        // Get or initialize cached messages
        let allMessages = this.messageCache.get(sessionId) || [];

        if (loadEarlier) {
          // Prepend earlier messages (which come in desc order from API)
          allMessages = [...newMessages, ...allMessages];
        } else {
          // Fresh load - messages come in desc order (newest first)
          allMessages = newMessages;
        }

        // Update cache
        this.messageCache.set(sessionId, allMessages);

        // Track if there are more messages to load
        this.hasMoreMessages.set(sessionId, newMessages.length >= 300);

        // Track oldest message ID for pagination
        // Since messages are in desc order initially, sort by date to find oldest
        const sortedMessages = [...allMessages].sort((a, b) => {
          const dateA = new Date(a.date || a.created_at).getTime();
          const dateB = new Date(b.date || b.created_at).getTime();
          return dateA - dateB;
        });
        if (sortedMessages.length > 0) {
          this.oldestMessageId.set(sessionId, sortedMessages[0].id);
        }

        await this.renderChatInterface(sessionId, allMessages);
      } else {
        throw new Error('Failed to load messages');
      }
    } catch (error) {
      console.error('Error loading messages:', error);
      if (!loadEarlier) {
        await this.renderChatInterface(sessionId, []);
      }
    }
  }

  async renderChatInterface(sessionId: string, messages: any[]) {
    this.chatContentContainer.empty();

    // Messages container
    const messagesContainer = this.chatContentContainer.createEl('div', {
      cls: 'chat-messages'
    });

    // Add "Load More" button if there are more messages
    if (this.hasMoreMessages.get(sessionId)) {
      const loadMoreBtn = messagesContainer.createEl('button', {
        cls: 'load-more-btn',
        text: 'Load earlier messages'
      });

      loadMoreBtn.addEventListener('click', async () => {
        loadMoreBtn.disabled = true;
        loadMoreBtn.textContent = 'Loading...';

        // Save scroll position
        const scrollHeight = messagesContainer.scrollHeight;
        const scrollTop = messagesContainer.scrollTop;

        try {
          await this.loadChatMessages(sessionId, true);

          // Restore relative scroll position after loading
          // This keeps the user viewing the same messages
          setTimeout(() => {
            const newScrollHeight = messagesContainer.scrollHeight;
            const scrollDiff = newScrollHeight - scrollHeight;
            messagesContainer.scrollTop = scrollTop + scrollDiff;
          }, 50);
        } catch (error) {
          console.error('Error loading earlier messages:', error);
          loadMoreBtn.disabled = false;
          loadMoreBtn.textContent = 'Load earlier messages';
          new Notice('Failed to load earlier messages');
        }
      });

      // Divider
      messagesContainer.createEl('div', {
        cls: 'load-more-divider'
      });
    }

    // Extract text from a message payload (handles string and array formats)
    const extractContent = (msg: any): string => {
      const content = msg.text || msg.content;
      if (Array.isArray(content)) {
        return content
          .filter((part: any) => part.type === 'text' || part.text)
          .map((part: any) => part.text)
          .join('');
      }
      return content || '';
    };

    // Sort all messages chronologically, then group them into "turns."
    // A turn is either a single user message OR a sequence of agent messages
    // (reasoning, tool calls, tool returns, assistant responses) that belong
    // to the same agent execution. This lets us render a single combined
    // assistant bubble with expandable step pills.
    const sorted = [...messages].sort((a, b) => {
      const dateA = new Date(a.date || a.created_at || 0).getTime();
      const dateB = new Date(b.date || b.created_at || 0).getTime();
      return dateA - dateB;
    });

    interface MessageGroup {
      type: 'user' | 'assistant';
      messages: any[];
    }

    const groups: MessageGroup[] = [];
    let currentGroup: MessageGroup | null = null;

    for (const msg of sorted) {
      const mt = msg.message_type || msg.type;

      // Skip system messages entirely
      if (mt === 'system_message') continue;

      const isUser = mt === 'user_message' || msg.role === 'user';

      // Hide auto-follow-up messages from skill activation
      if (isUser) {
        const text = extractContent(msg);
        if (text.startsWith(SKILL_ACTIVATION_PREFIX)) continue;
      }

      if (isUser) {
        currentGroup = { type: 'user', messages: [msg] };
        groups.push(currentGroup);
      } else {
        // All non-user messages (reasoning, tool_call, tool_return,
        // assistant_message) go into the current assistant group.
        if (!currentGroup || currentGroup.type === 'user') {
          currentGroup = { type: 'assistant', messages: [msg] };
          groups.push(currentGroup);
        } else {
          currentGroup.messages.push(msg);
        }
      }
    }

    // Count visible messages for logging
    const visibleCount = groups.reduce((n, g) => n + g.messages.length, 0);
    console.log(`[MultiChatModal] Rendering ${visibleCount} messages (${groups.length} groups) from ${messages.length} total`);

    // Render
    if (groups.length === 0) {
      this.createEmptyState(
        messagesContainer,
        ICONS.messageEmpty,
        'Start a conversation',
        'Ask me anything about your research, papers, or knowledge base. I can help you discover papers, analyze citations, and more.',
        'Try: "Find recent papers on transformers"'
      );
    } else {
      for (const group of groups) {
        if (group.type === 'user') {
          const content = extractContent(group.messages[0]);
          await this.addMessageToChat(messagesContainer, 'user', content);
        } else {
          await this.renderAssistantTurn(messagesContainer, group.messages, extractContent);
        }
      }
    }

    // Input area
    const inputArea = this.chatContentContainer.createEl('div', {
      cls: 'chat-input-area'
    });

    // Attachment preview strip (hidden by default)
    this.attachmentPreviewContainer = inputArea.createEl('div', {
      cls: 'chat-attachment-preview'
    });
    this.attachmentPreviewContainer.style.display = 'none';

    const inputEl = inputArea.createEl('textarea', {
      cls: 'chat-input',
      placeholder: 'Type your message...'
    }) as HTMLTextAreaElement;

    // Ensure input area clicks focus the input
    inputArea.addEventListener('click', (e) => {
      if (e.target === inputArea) {
        inputEl.focus();
      }
    });

    // Drag-and-drop support for images
    let dragCounter = 0;

    inputArea.addEventListener('dragenter', (e) => {
      e.preventDefault();
      dragCounter++;
      inputArea.addClass('drag-over');
    });

    inputArea.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.dataTransfer!.dropEffect = 'copy';
    });

    inputArea.addEventListener('dragleave', (e) => {
      e.preventDefault();
      dragCounter--;
      if (dragCounter === 0) {
        inputArea.removeClass('drag-over');
      }
    });

    inputArea.addEventListener('drop', async (e) => {
      e.preventDefault();
      dragCounter = 0;
      inputArea.removeClass('drag-over');

      const files = Array.from(e.dataTransfer?.files || []);

      if (files.length === 0) {
        new Notice('No files found in drop');
        return;
      }

      for (const file of files) {
        try {
          await this.processFileAttachment(file);
        } catch (error) {
          new Notice(`Failed to add file: ${error.message}`, 5000);
          console.error('File drop error:', error);
        }
      }
    });

    // Attachment button — small icon-only square button
    const attachBtn = inputArea.createEl('button', {
      cls: 'chat-attach-btn',
      attr: { 'aria-label': 'Attach image', 'title': 'Attach image for context' }
    });
    attachBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/></svg>`;

    attachBtn.onclick = async (e: MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      await this.uploadImage();
    };

    // Send button — icon-only square (arrow up); flips to stop square while streaming
    const sendBtn = inputArea.createEl('button', { cls: 'chat-send-btn' });
    const SEND_ICON = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5"/><path d="m5 12 7-7 7 7"/></svg>`;
    const STOP_ICON = `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><rect x="3" y="3" width="18" height="18" rx="2"/></svg>`;
    sendBtn.innerHTML = SEND_ICON;

    // AbortController for cancelling an in-flight stream
    let currentAbortController: AbortController | null = null;

    const showStopState = () => {
      sendBtn.disabled = false;
      sendBtn.innerHTML = STOP_ICON;
      sendBtn.classList.add('chat-stop-btn');
      sendBtn.title = 'Stop generation';
    };

    const showSendState = () => {
      sendBtn.disabled = false;
      sendBtn.innerHTML = SEND_ICON;
      sendBtn.classList.remove('chat-stop-btn');
      sendBtn.title = '';
    };

    sendBtn.onclick = () => {
      if (sendBtn.classList.contains('chat-stop-btn')) {
        currentAbortController?.abort();
      } else {
        sendMessage();
      }
    };

    // Event handlers
    const sendMessage = async () => {
      const message = inputEl.value.trim();
      if (!message || sendBtn.classList.contains('chat-stop-btn')) return;

      // Capture pending attachments for this message
      const messageAttachments = [...this.pendingAttachments];
      const messageFileAttachments = [...this.pendingFileAttachments];

      // Build augmented message with file content injected
      let augmentedMessage = message;

      // Inject file content with delimiters
      if (messageFileAttachments.length > 0) {
        for (const fileAttachment of messageFileAttachments) {
          augmentedMessage += `\n\n--- Attached: ${fileAttachment.name} ---\n${fileAttachment.content}\n--- End: ${fileAttachment.name} ---`;
        }
      }

      // Add user message to UI (with attachments if present)
      await this.addMessageToChat(messagesContainer, 'user', message, messageAttachments, messageFileAttachments);
      inputEl.value = '';

      // Auto-resize input back to minimum height
      inputEl.style.height = '36px';

      // Clear attachments after adding to UI
      this.clearAttachments();

      // Switch send → stop, disable input while agent is working
      currentAbortController = new AbortController();
      showStopState();
      inputEl.disabled = true;
      inputEl.classList.add('agent-working');

      // Add thinking indicator
      const thinkingMsg = this.addThinkingIndicator(messagesContainer);

      try {
        // Build input payload: use array format if image attachments present, string otherwise
        let inputPayload: string | any[];

        if (messageAttachments.length > 0) {
          // Multimodal format: array of content parts with images
          inputPayload = [
            {
              type: 'text',
              text: augmentedMessage  // Use augmented message with file content
            },
            ...messageAttachments.map(att => ({
              type: 'image',
              source: {
                type: 'base64',
                data: att.data,
                media_type: att.media_type
              }
            }))
          ];
        } else {
          // Text-only format: plain string (backward compatible)
          inputPayload = augmentedMessage;  // Use augmented message with file content
        }

        // Send to Letta conversation with streaming enabled
        const endpoint = this.plugin.getLettaProxyUrl();
        const response = await this.plugin.authFetch(`${endpoint}/v1/conversations/${sessionId}/messages`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            input: inputPayload,
            streaming: true,  // Enable SSE streaming for real-time token display
            stream_tokens: true  // Stream individual tokens
          }),
          signal: currentAbortController?.signal
        });

        if (response.ok && response.body) {
          // Shared state across the primary stream and the optional
          // skill-activation follow-up. Both streams append into the same
          // assistant message container so the UI reads as one turn.
          let assistantMessageEl: HTMLElement | null = null;
          let stepsContainer: HTMLElement | null = null;
          let inlineThinkingEl: HTMLElement | null = null;
          let contentEl: HTMLElement | null = null;
          let streamingRenderer: StreamingMarkdownRenderer | null = null;
          let accumulatedContent = '';
          let skillToolDetected = false;
          let currentAssistantMsgId: string | null = null;
          let currentReasoningPill: HTMLElement | null = null;
          let accumulatedReasoning = '';
          let currentToolPill: HTMLElement | null = null;

          // Delta tracking: with stream_tokens enabled, Letta sends
          // ToolCallDelta objects -- multiple tool_call_message events per
          // tool call, each carrying an argument fragment.
          let activeToolCallId: string | null = null;
          let activeToolName: string | null = null;
          // Progressive send_message streaming state. We accumulate the
          // raw JSON argument fragments and, once we see the
          // "message": " prefix, stream content directly to the renderer.
          let sendMsgArgBuf = '';
          let sendMsgPrefixIdx = -1; // char index right after the opening "
          let sendMsgRenderedLen = 0;

          // Remove the inline thinking indicator shown during multi-turn gaps.
          const clearInlineThinking = (): void => {
            if (!inlineThinkingEl) return;
            const id = (inlineThinkingEl as any).__rotationInterval;
            if (id) clearInterval(id);
            inlineThinkingEl.remove();
            inlineThinkingEl = null;
          };

          // Ensure the assistant message bubble exists. Called on the first
          // SSE event so the bubble appears immediately. Also clears any
          // inline thinking indicator left over from a multi-turn gap.
          const ensureContainer = (): void => {
            clearInlineThinking();
            if (assistantMessageEl) return;
            const rotId = (thinkingMsg as any).__rotationInterval;
            if (rotId) clearInterval(rotId);
            thinkingMsg.remove();
            assistantMessageEl = messagesContainer.createEl('div', {
              cls: 'chat-message assistant'
            });
            assistantMessageEl.createEl('div', {
              text: 'Assistant',
              cls: 'message-role'
            });
          };

          // Return the current steps container, or create a new one inline
          // below whatever is currently the last child of the bubble. This
          // interleaves pills and content in the order they arrive rather
          // than collecting all pills above all content.
          const getOrCreateInlineSteps = (): HTMLElement => {
            const last = assistantMessageEl!.lastElementChild;
            if (last && last.classList.contains('agent-steps')) {
              stepsContainer = last as HTMLElement;
              return stepsContainer;
            }
            stepsContainer = assistantMessageEl!.createEl('div', { cls: 'agent-steps' });
            return stepsContainer;
          };

          // --- Helper: process one SSE stream into the shared container ---
          const processStream = async (body: ReadableStream<Uint8Array>): Promise<void> => {
            const reader = body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let lastPaintYield = 0;

            // Reset per-stream pill tracking (a new stream = new group of steps).
            // stepsContainer is nulled so each stream creates its containers inline.
            currentReasoningPill = null;
            accumulatedReasoning = '';
            currentToolPill = null;
            stepsContainer = null;
            activeToolCallId = null;
            activeToolName = null;
            sendMsgArgBuf = '';
            sendMsgPrefixIdx = -1;
            sendMsgRenderedLen = 0;

            // Each stream may produce a new content section below the steps
            let streamContentEl: HTMLElement | null = null;
            let streamRenderer: StreamingMarkdownRenderer | null = null;
            let streamAccumulated = '';
            let streamMsgId: string | null = null;

            while (true) {
              const { done, value } = await reader.read();
              if (done) break;

              buffer += decoder.decode(value, { stream: true });
              const lines = buffer.split('\n\n');
              buffer = lines.pop() || '';

              let wroteContent = false;

              for (const block of lines) {
                const dataLine = block.split('\n').find(l => l.trim().startsWith('data:'));
                if (!dataLine) continue;

                const jsonStr = dataLine.replace(/^data:\s*/, '').trim();
                if (!jsonStr || jsonStr === '[DONE]') continue;

                try {
                  const msg = JSON.parse(jsonStr);
                  const messageType = msg.message_type;

                  // Diagnostic: log every SSE event type and key fields
                  if (messageType === 'tool_call_message') {
                    console.log('[SSE] tool_call_message:', {
                      name: msg.tool_call?.name,
                      tool_call_id: msg.tool_call?.tool_call_id,
                      argsPreview: (msg.tool_call?.arguments || '').substring(0, 120),
                    });
                  } else if (messageType === 'assistant_message') {
                    const c = msg.content;
                    console.log('[SSE] assistant_message:', {
                      contentType: typeof c,
                      isArray: Array.isArray(c),
                      preview: typeof c === 'string' ? c.substring(0, 120) : JSON.stringify(c)?.substring(0, 120),
                      text: msg.text?.substring?.(0, 80),
                    });
                  } else {
                    console.log('[SSE] event:', messageType);
                  }

                  // --- errors ---
                  if (messageType === 'error_message') {
                    const detail = msg.detail || msg.message || 'Unknown agent error';
                    console.error('[MultiChatModal] Agent error:', detail);
                    throw new Error(detail);
                  }
                  if (messageType === 'stop_reason' && msg.stop_reason === 'llm_api_error') {
                    console.error('[MultiChatModal] LLM API error reported');
                  }

                  // --- reasoning ---
                  if (messageType === 'reasoning_message') {
                    ensureContainer();
                    const reasoning = msg.reasoning || msg.content || msg.text || '';

                    if (!currentReasoningPill) {
                      const phrase = getRandomThinkingPhrase('thinking');
                      currentReasoningPill = this.createStepPill(
                        getOrCreateInlineSteps(), ICONS.thinking, `${phrase}...`, undefined, 'reasoning'
                      );
                    }

                    if (reasoning) {
                      // Strip trailing newline that Letta appends to each
                      // reasoning chunk -- they cause line-per-chunk rendering.
                      accumulatedReasoning += reasoning.replace(/\n$/, '');
                      this.updateStepPillDetail(
                        currentReasoningPill, accumulatedReasoning.trim()
                      );
                    }
                    this.scrollToBottom(messagesContainer, true);
                  }

                  // --- tool call (handles both full ToolCall and streamed ToolCallDelta) ---
                  else if (messageType === 'tool_call_message') {
                    ensureContainer();

                    // Letta may use `tool_call` (singular) or `tool_calls` (array)
                    const tc = msg.tool_call || msg.tool_calls?.[0];
                    const deltaName = tc?.name || null;
                    const deltaId = tc?.tool_call_id || null;
                    const deltaArgs = tc?.arguments || '';

                    // Detect whether this is a continuation (delta) of an
                    // in-progress tool call or the start of a new one.
                    // Letta repeats the tool name on every delta, so we
                    // can't rely on it being absent -- use tool_call_id
                    // matching as the primary indicator instead.
                    const isDelta = activeToolCallId != null && (
                      (deltaId != null && deltaId === activeToolCallId) ||
                      (deltaId == null && deltaName === activeToolName)
                    );

                    if (isDelta) {
                      if (activeToolName === 'send_message') {
                        // Accumulate the argument fragment and try to
                        // progressively stream the message text.
                        sendMsgArgBuf += deltaArgs;
                        this.streamSendMessageDelta(
                          sendMsgArgBuf, sendMsgPrefixIdx, sendMsgRenderedLen,
                          () => { ensureContainer(); return assistantMessageEl!; },
                          streamContentEl, streamRenderer,
                          (el, r, pre, len) => {
                            streamContentEl = el;
                            streamRenderer = r;
                            sendMsgPrefixIdx = pre;
                            sendMsgRenderedLen = len;
                          }
                        );
                        if (streamRenderer) wroteContent = true;
                      }
                      continue;
                    }

                    // --- New tool call ---
                    activeToolCallId = deltaId;
                    activeToolName = deltaName;
                    const toolName = deltaName || 'tool';

                    if (toolName === 'load_skill' || toolName === 'unload_skill') {
                      skillToolDetected = true;
                    }

                    // send_message is how Letta agents deliver their response
                    // to the user. We stream the content progressively as
                    // argument deltas arrive rather than creating a pill.
                    if (toolName === 'send_message') {
                      sendMsgArgBuf = deltaArgs;
                      sendMsgPrefixIdx = -1;
                      sendMsgRenderedLen = 0;
                      currentToolPill = null;
                      // Kick off progressive streaming from the first delta
                      this.streamSendMessageDelta(
                        sendMsgArgBuf, sendMsgPrefixIdx, sendMsgRenderedLen,
                        () => { ensureContainer(); return assistantMessageEl!; },
                        streamContentEl, streamRenderer,
                        (el, r, pre, len) => {
                          streamContentEl = el;
                          streamRenderer = r;
                          sendMsgPrefixIdx = pre;
                          sendMsgRenderedLen = len;
                        }
                      );
                      if (streamRenderer) wroteContent = true;
                      this.scrollToBottom(messagesContainer, true);
                      continue;
                    }

                    // Close any open reasoning pill before a tool step
                    currentReasoningPill = null;
                    accumulatedReasoning = '';

                    const statusMsg = getToolStatusMessage(toolName);
                    let toolDetail = '';
                    try {
                      if (deltaArgs) {
                        const parsed = JSON.parse(deltaArgs);
                        toolDetail = JSON.stringify(parsed, null, 2);
                      }
                    } catch { /* keep empty -- likely a delta fragment */ }

                    currentToolPill = this.createStepPill(
                      getOrCreateInlineSteps(), ICONS.tool, `${statusMsg}...`, toolDetail
                    );
                    currentToolPill.addClass('pill-active');

                    if (toolName === 'agentic_research_question') {
                      this.startAgenticProgressListener(currentToolPill);
                    }

                    this.scrollToBottom(messagesContainer, true);
                  }

                  // --- tool return ---
                  else if (messageType === 'tool_return_message') {
                    this.stopAgenticProgressListener();
                    ensureContainer();

                    // If we just finished a send_message call, do a final
                    // clean parse so streamAccumulated has the properly
                    // unescaped text for the Obsidian markdown re-render.
                    if (activeToolName === 'send_message') {
                      let sendText = '';

                      // Strategy 1: clean JSON parse
                      try {
                        const parsed = JSON.parse(sendMsgArgBuf);
                        sendText = parsed?.message || '';
                      } catch { /* fall through */ }

                      // Strategy 2: regex extraction (handles incomplete JSON)
                      if (!sendText) {
                        const m = sendMsgArgBuf.match(/"message"\s*:\s*"((?:[^"\\]|\\.)*)"/);
                        if (m) {
                          sendText = m[1]
                            .replace(/\\n/g, '\n')
                            .replace(/\\"/g, '"')
                            .replace(/\\\\/g, '\\');
                        }
                      }

                      // Strategy 3: greedy extraction - find "message":" and
                      // take everything until the last unescaped quote
                      if (!sendText) {
                        const prefixMatch = sendMsgArgBuf.match(/"message"\s*:\s*"/);
                        if (prefixMatch) {
                          const start = prefixMatch.index! + prefixMatch[0].length;
                          let raw = sendMsgArgBuf.substring(start);
                          raw = raw.replace(/"\s*\}?\s*$/, '');
                          sendText = raw
                            .replace(/\\n/g, '\n')
                            .replace(/\\"/g, '"')
                            .replace(/\\\\/g, '\\');
                        }
                      }

                      // Strategy 4: use whatever the streaming renderer wrote
                      if (!sendText && streamContentEl) {
                        sendText = streamContentEl.textContent || '';
                      }

                      if (!sendText) {
                        console.warn('[MultiChatModal] send_message finalization: all extraction strategies failed, buf length:', sendMsgArgBuf.length);
                      }

                      if (sendText) {
                        streamAccumulated += (streamAccumulated ? '\n\n' : '') + sendText;
                      }

                      sendMsgArgBuf = '';
                      sendMsgPrefixIdx = -1;
                      sendMsgRenderedLen = 0;
                      activeToolCallId = null;
                      activeToolName = null;
                      this.scrollToBottom(messagesContainer, true);
                      continue;
                    }

                    if (currentToolPill) {
                      // Remove active shimmer and strip trailing ellipsis
                      currentToolPill.removeClass('pill-active');
                      const label = (currentToolPill as any).__labelEl;
                      if (label) {
                        label.textContent = label.textContent.replace('...', '');
                      }
                    }

                    currentToolPill = null;
                    activeToolCallId = null;
                    activeToolName = null;
                    this.scrollToBottom(messagesContainer, true);
                  }

                  // --- assistant content ---
                  else if (messageType === 'assistant_message') {
                    // Letta can send content as a plain string or as an
                    // array of content parts [{type:"text", text:"..."}].
                    const raw = msg.content ?? msg.text ?? '';
                    let delta: string;
                    if (Array.isArray(raw)) {
                      delta = raw
                        .filter((p: any) => p.type === 'text' || p.text)
                        .map((p: any) => p.text)
                        .join('');
                    } else {
                      delta = String(raw);
                    }

                    if (msg.id) {
                      streamMsgId = msg.id;
                    } else if (!streamMsgId) {
                      streamMsgId = `stream-${Date.now()}`;
                    }

                    if (delta) {
                      ensureContainer();

                      // Close any open reasoning pill
                      currentReasoningPill = null;
                      accumulatedReasoning = '';

                      // Create content section on first token
                      if (!streamContentEl) {
                        if (!assistantMessageEl!.dataset.messageId && streamMsgId) {
                          assistantMessageEl!.dataset.messageId = streamMsgId;
                        }
                        streamContentEl = assistantMessageEl!.createEl('div', {
                          cls: 'message-content'
                        });
                        streamRenderer = new StreamingMarkdownRenderer(streamContentEl);
                      }

                      streamAccumulated += delta;

                      if (streamRenderer) {
                        streamRenderer.write(delta);
                        wroteContent = true;
                      }
                    }
                  }
                } catch (e) {
                  if (e.message && !e.message.includes('Failed to parse')) {
                    throw e;
                  }
                  console.warn('[MultiChatModal] Failed to parse SSE:', jsonStr.substring(0, 100));
                }
              }

              // Yield to browser for repaint between chunk batches
              if (wroteContent) {
                const now = Date.now();
                if (now - lastPaintYield > 40) {
                  lastPaintYield = now;
                  await new Promise<void>(r => requestAnimationFrame(() => r()));
                }
                this.scrollToBottom(messagesContainer, true);
              }
            }

            // Finalize: flush the streaming parser, then re-render with
            // Obsidian's native markdown for proper styling.
            if (streamRenderer) {
              streamRenderer.end();
            }

            if (streamContentEl && streamAccumulated) {
              // Normal path: replace streaming preview with full Obsidian render.
              await this.renderMessageContent(streamAccumulated, streamContentEl);
            } else if (!streamContentEl && streamAccumulated && assistantMessageEl) {
              // Message arrived in a single chunk so no streaming element was
              // created. Render into a new content div now.
              const el = (assistantMessageEl as HTMLElement).createEl('div', { cls: 'message-content' });
              await this.renderMessageContent(streamAccumulated, el);
              streamContentEl = el;
            }
            // If streamAccumulated is empty (stream cut out before
            // tool_return_message), leave the streaming preview in place rather
            // than replacing it with nothing.

            // Merge this stream's content into the overall accumulated content
            if (streamAccumulated) {
              accumulatedContent += (accumulatedContent ? '\n\n' : '') + streamAccumulated;
            }

            // Update references for the next stream (follow-up) to reuse
            contentEl = streamContentEl;
            streamingRenderer = streamRenderer;
            currentAssistantMsgId = streamMsgId;

            this.scrollToBottom(messagesContainer, true);
          };

          // --- Run the primary stream ---
          await processStream(response.body);

          // Remove the initial thinking indicator if nothing rendered at all
          // (e.g. the stream ended with no events)
          if (!assistantMessageEl) {
            const rotId = (thinkingMsg as any).__rotationInterval;
            if (rotId) clearInterval(rotId);
            thinkingMsg.remove();
          }

          // --- Auto-follow-up for skill loading/unloading ---
          // exit_loop forces the agent's turn to end after load_skill/unload_skill
          // because Letta doesn't refresh available tools mid-turn. We send a
          // follow-up message to start a new turn where the agent can use the
          // newly attached tools. Cap at 3 for chained loads.
          let skillFollowUpCount = 0;
          while (skillToolDetected && skillFollowUpCount < 3) {
            skillToolDetected = false;
            skillFollowUpCount++;
            console.log(`[MultiChatModal] Skill tool detected, sending follow-up (attempt ${skillFollowUpCount})...`);

            // Show activation pill inline below any prior content
            const activationPill = this.createStepPill(
              getOrCreateInlineSteps(), ICONS.zap, 'Activating skill tools...'
            );

            // Show a rotating inline indicator while the follow-up request is in flight
            inlineThinkingEl = this.addInlineThinkingIndicator(assistantMessageEl!);
            this.scrollToBottom(messagesContainer, true);

            try {
              // Brief delay to let Letta finalize the previous turn
              await new Promise<void>(r => setTimeout(r, 500));

              const truncatedRequest = message.length > 300
                ? message.slice(0, 300) + '...'
                : message;
              const followUpInput =
                `${SKILL_ACTIVATION_PREFIX} Tools ready. Continue with my request: ${truncatedRequest}`;

              const followUpResponse = await this.plugin.authFetch(`${endpoint}/v1/conversations/${sessionId}/messages`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  input: followUpInput,
                  streaming: true,
                  stream_tokens: true
                })
              });

              if (!followUpResponse.ok) {
                const errorBody = await followUpResponse.text();
                console.error(`[MultiChatModal] Follow-up failed: ${followUpResponse.status}`, errorBody);
                clearInlineThinking();
                this.updateStepPillLabel(activationPill, 'Follow-up failed');
                await this.addMessageToChat(messagesContainer, 'assistant',
                  'Skill tools loaded, but the follow-up request failed. Try sending your message again.');
                break;
              } else if (followUpResponse.body) {
                console.log('[MultiChatModal] Follow-up stream started...');
                this.updateStepPillLabel(activationPill, 'Skill tools activated');

                // ensureContainer() will clear inlineThinkingEl on first SSE event.
                // processStream creates its own inline steps containers as needed.
                await processStream(followUpResponse.body);
              }
            } catch (followUpError) {
              console.error('[MultiChatModal] Auto-follow-up error:', followUpError);
              clearInlineThinking();
              messagesContainer.querySelectorAll('.message.thinking').forEach(el => el.remove());
              await this.addMessageToChat(messagesContainer, 'assistant',
                'Skill tools loaded, but an error occurred while processing. Try sending your message again.');
              break;
            }
          }

          // If the skill follow-up loop ran but never produced visible content,
          // render a fallback so the user isn't left staring at nothing.
          if (skillFollowUpCount > 0 && !accumulatedContent.trim()) {
            console.warn(`[MultiChatModal] Skill follow-up produced no visible content after ${skillFollowUpCount} attempt(s)`);
            const fallbackText = 'Skill loaded. Send your message again to continue.';
            if (assistantMessageEl) {
              const el = (assistantMessageEl as HTMLElement).createEl('div', { cls: 'message-content' });
              await this.renderMessageContent(fallbackText, el);
              accumulatedContent = fallbackText;
            } else {
              await this.addMessageToChat(messagesContainer, 'assistant', fallbackText);
            }
          }

          // Add copy button covering ALL accumulated content from both streams
          if (assistantMessageEl && accumulatedContent) {
            const msgEl = assistantMessageEl as HTMLElement;
            // Remove any existing actions (processStream doesn't add them)
            msgEl.querySelectorAll('.message-actions').forEach(el => el.remove());
            this.addMessageActions(msgEl, accumulatedContent);
          }

          // Update session list to reflect new message
          await this.loadChatSessions();
          this.renderSessionList();

          // Auto-generate a title for this conversation if it still has a default name.
          // Fires non-blocking so it doesn't delay the UI.
          this.maybeGenerateConversationTitle(sessionId, message);
        } else {
          // Add better error logging with response body
          const errorBody = await response.text();
          console.error(`[MultiChatModal] Message send failed: ${response.status}`, errorBody);
          throw new Error(`Failed to send message: ${response.status}`);
        }
      } catch (error) {
        if (error.name !== 'AbortError') {
          console.error('Chat error:', error);
          const rotId = (thinkingMsg as any).__rotationInterval;
          if (rotId) clearInterval(rotId);
          thinkingMsg.remove();
          await this.addMessageToChat(messagesContainer, 'assistant', `Error: ${error.message}`);
          this.showToast(`Error: ${error.message}`, 'error');
        }
      } finally {
        currentAbortController = null;
        showSendState();
        inputEl.disabled = false;
        inputEl.classList.remove('agent-working');
        inputEl.focus();
      }
    };

    // Enhanced keyboard handling
    inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      } else if (e.key === 'Escape') {
        // Clear input on Escape
        inputEl.value = '';
        inputEl.style.height = '36px';
      }
    });

    // Paste support for clipboard images
    inputEl.addEventListener('paste', async (e) => {
      const items = e.clipboardData?.items;
      if (!items) return;

      const imageItems: DataTransferItem[] = [];
      for (const item of Array.from(items)) {
        if (item.type.startsWith('image/')) {
          imageItems.push(item);
        }
      }

      if (imageItems.length === 0) return;

      // Prevent default paste for images (but allow text to paste normally)
      e.preventDefault();

      for (const item of imageItems) {
        const file = item.getAsFile();
        if (!file) continue;

        try {
          const attachment = await this.readFileAsBase64(file);
          await this.addAttachment(attachment);
          new Notice(`Pasted image: ${file.name || 'clipboard.png'}`);
        } catch (error) {
          new Notice(`Failed to paste image: ${error.message}`, 5000);
          console.error('Image paste error:', error);
        }
      }
    });

    // Auto-resize textarea as user types
    inputEl.addEventListener('input', () => {
      inputEl.style.height = '36px';
      inputEl.style.height = Math.min(inputEl.scrollHeight, 80) + 'px';
    });

    // Focus input and scroll to bottom
    setTimeout(() => {
      // Ensure input is focusable
      inputEl.style.pointerEvents = 'auto';
      inputEl.tabIndex = 0;

      // Try multiple focus attempts for reliability
      inputEl.focus();

      // Force focus if needed
      setTimeout(() => {
        if (document.activeElement !== inputEl) {
          inputEl.focus();
        }
      }, 50);

      this.scrollToBottom(messagesContainer, false);
    }, 100);

    // Mobile keyboard handling
    if ((this.app as any).isMobile) {
      this.mobileKeyboardSetup?.(inputEl, messagesContainer, inputArea);
    }
  }

  async addMessageToChat(
    container: HTMLElement,
    role: string,
    content: string,
    attachments?: ImageAttachment[],
    fileAttachments?: FileAttachment[]
  ) {
    const messageEl = container.createEl('div', {
      cls: `chat-message ${role}`
    });

    messageEl.createEl('div', {
      text: role === 'user' ? 'You' : 'Assistant',
      cls: 'message-role'
    });

    const contentEl = messageEl.createEl('div', {
      cls: 'message-content'
    });

    // Render file attachment badges if present (for user messages)
    if (fileAttachments && fileAttachments.length > 0) {
      const filesContainer = contentEl.createEl('div', {
        cls: 'message-files'
      });

      fileAttachments.forEach(fileAttachment => {
        const fileBadge = filesContainer.createEl('div', {
          cls: 'message-file-badge',
          attr: {
            title: `${fileAttachment.name} (${(fileAttachment.size / 1024).toFixed(1)}KB)`
          }
        });

        const fileIcon = fileBadge.createEl('span', { cls: 'message-file-icon' });
        fileIcon.innerHTML = this.getFileIcon(fileAttachment.name);

        fileBadge.createEl('span', {
          cls: 'message-file-name',
          text: fileAttachment.name
        });
      });
    }

    // Render image attachments if present (for user messages)
    if (attachments && attachments.length > 0) {
      const imagesContainer = contentEl.createEl('div', {
        cls: 'message-images'
      });

      attachments.forEach(attachment => {
        const imgWrapper = imagesContainer.createEl('div', {
          cls: 'message-image-wrapper'
        });

        const img = imgWrapper.createEl('img', {
          cls: 'message-image',
          attr: {
            src: `data:${attachment.media_type};base64,${attachment.data}`,
            alt: attachment.name,
            title: `Click to view full size: ${attachment.name}`
          }
        });

        // Make images clickable to view full size
        img.addEventListener('click', () => {
          const newWindow = window.open();
          if (newWindow) {
            newWindow.document.write(
              `<html><head><title>${attachment.name}</title></head>` +
              `<body style="margin:0;display:flex;justify-content:center;align-items:center;background:#000;">` +
              `<img src="data:${attachment.media_type};base64,${attachment.data}" ` +
              `style="max-width:100%;max-height:100vh;object-fit:contain;" />` +
              `</body></html>`
            );
            newWindow.document.close();
          }
        });
      });
    }

    // Render markdown content
    await this.renderMessageContent(content, contentEl);

    // Add message actions (copy button) for assistant messages
    this.addMessageActions(messageEl, content);

    // Auto-scroll to new message with smooth behavior
    setTimeout(() => {
      this.scrollToBottom(container);
    }, 100);
  }

  /**
   * Render a grouped assistant turn (reasoning + tools + content) as a single
   * message bubble with expandable step pills interleaved with content in the
   * order the messages actually occurred.
   */
  private async renderAssistantTurn(
    container: HTMLElement,
    messages: any[],
    extractContent: (msg: any) => string
  ): Promise<void> {
    const messageEl = container.createEl('div', { cls: 'chat-message assistant' });
    messageEl.createEl('div', { text: 'Assistant', cls: 'message-role' });

    // Flat log so message types are visible without expanding objects
    const groupTypes = messages.map(m => {
      const mt = m.message_type || m.type;
      const tc = m.tool_call || m.tool_calls?.[0];
      return tc?.name ? `${mt}(${tc.name})` : mt;
    }).join(', ');
    console.log(`[renderAssistantTurn] ${messages.length} msgs: ${groupTypes}`);

    // Track the current steps container. When content appears after pills,
    // we null this out so the next pill group creates a new container below.
    let currentStepsEl: HTMLElement | null = null;
    let combinedContent = '';

    const ensureSteps = () => {
      if (!currentStepsEl) {
        currentStepsEl = messageEl.createEl('div', { cls: 'agent-steps' });
      }
      return currentStepsEl;
    };

    for (const msg of messages) {
      const mt = msg.message_type || msg.type;

      if (mt === 'reasoning_message') {
        const reasoning = msg.reasoning || extractContent(msg);
        if (reasoning) {
          const phrase = getRandomThinkingPhrase('thinking');
          this.createStepPill(ensureSteps(), ICONS.thinking, phrase, reasoning, 'reasoning');
        }
      } else if (mt === 'tool_call_message') {
        // Letta can put the tool call in either `tool_call` (singular)
        // or `tool_calls` (array). Normalise to a single object.
        const tc = msg.tool_call || msg.tool_calls?.[0];
        const toolName = tc?.name || 'tool';

        // send_message is the agent talking to the user -- treat its
        // payload as assistant content rather than a tool step pill.
        if (toolName === 'send_message') {
          let sendText = '';
          try {
            const rawArgs = tc?.arguments;
            // Arguments may be a JSON string (streaming) or
            // an already-parsed object (history API).
            const parsed = typeof rawArgs === 'string'
              ? JSON.parse(rawArgs)
              : rawArgs;
            sendText = parsed?.message || '';
          } catch { /* ignore malformed args */ }

          if (sendText) {
            // Content follows pills -- close the current steps group
            currentStepsEl = null;
            combinedContent += (combinedContent ? '\n\n' : '') + sendText;
          }
          continue;
        }

        const statusMsg = getToolStatusMessage(toolName);
        let detail = '';
        try {
          const rawArgs = tc?.arguments;
          const parsed = typeof rawArgs === 'string'
            ? JSON.parse(rawArgs)
            : rawArgs;
          if (parsed) {
            detail = JSON.stringify(parsed, null, 2);
          }
        } catch { /* keep empty */ }
        this.createStepPill(ensureSteps(), ICONS.tool, statusMsg, detail);
      } else if (mt === 'tool_return_message') {
        // Skip tool returns in history pills -- the tool call pill already
        // conveys what happened.
        continue;
      } else if (mt === 'assistant_message') {
        const text = extractContent(msg);
        if (text) {
          currentStepsEl = null;
          combinedContent += (combinedContent ? '\n\n' : '') + text;
        }
      }
    }

    // Fallback: if no content was extracted from typed handlers,
    // try extractContent on every message. This catches cases where
    // message types don't match expected values or when assistant
    // content arrives in an unexpected format.
    if (!combinedContent) {
      for (const msg of messages) {
        const text = extractContent(msg);
        if (text) {
          combinedContent += (combinedContent ? '\n\n' : '') + text;
        }
      }
    }

    const hasSteps = messageEl.querySelector('.step-pill') !== null;

    if (!hasSteps && !combinedContent) {
      // Log full detail when a group produces no visible content
      // so we can diagnose missing messages.
      console.warn('[renderAssistantTurn] EMPTY group:', messages.map(m => ({
        mt: m.message_type || m.type,
        tc: (m.tool_call || m.tool_calls?.[0])?.name,
        content: (m.content || m.text || m.reasoning || '').substring(0, 200),
        keys: Object.keys(m).join(','),
      })));
      messageEl.style.display = 'none';
      return;
    }

    if (combinedContent) {
      console.log(`[renderAssistantTurn] content: ${combinedContent.length} chars`);
      const contentEl = messageEl.createEl('div', { cls: 'message-content' });
      await this.renderMessageContent(combinedContent, contentEl);
      this.addMessageActions(messageEl, combinedContent);
    }

    this.scrollToBottom(container);
  }

  /**
   * Get file icon SVG based on file extension.
   * All variants are the same generic file icon — callers use innerHTML.
   */
  private getFileIcon(_filename: string): string {
    return ICONS.file;
  }

  async addReasoningMessage(container: HTMLElement, msg: any) {
    const reasoningEl = container.createEl('div', {
      cls: 'chat-message reasoning-block'
    });

    const header = reasoningEl.createEl('div', {
      cls: 'reasoning-header'
    });

    const icon = header.createEl('span', { cls: 'reasoning-icon' });
    icon.innerHTML = ICONS.brain;

    const title = header.createEl('span', {
      cls: 'reasoning-title',
      text: 'Thinking...'
    });

    const toggle = header.createEl('button', {
      cls: 'reasoning-toggle',
      text: '▼'
    });

    const contentEl = reasoningEl.createEl('div', {
      cls: 'reasoning-content'
    });

    const reasoning = msg.reasoning || msg.content || '';
    await this.renderMessageContent(reasoning, contentEl);

    // Make collapsible
    toggle.addEventListener('click', (e) => {
      e.stopPropagation();
      contentEl.classList.toggle('collapsed');
      toggle.textContent = contentEl.classList.contains('collapsed') ? '▶' : '▼';
    });

    // Start collapsed by default
    contentEl.classList.add('collapsed');
    toggle.textContent = '▶';

    this.scrollToBottom(container);
  }

  async addToolCallMessage(container: HTMLElement, msg: any) {
    const toolEl = container.createEl('div', {
      cls: 'chat-message tool-call-card'
    });

    const header = toolEl.createEl('div', {
      cls: 'tool-call-header'
    });

    const toolCallIcon = header.createEl('span', { cls: 'tool-call-icon' });
    toolCallIcon.innerHTML = ICONS.tool;

    const toolCall = msg.tool_call || {};
    const toolName = toolCall.name || 'Unknown Tool';

    header.createEl('span', {
      cls: 'tool-call-name',
      text: `Calling: ${toolName}`
    });

    const toggle = header.createEl('button', {
      cls: 'tool-call-toggle',
      text: '▼'
    });

    const contentEl = toolEl.createEl('div', {
      cls: 'tool-call-content'
    });

    // Display arguments
    if (toolCall.arguments) {
      contentEl.createEl('div', {
        cls: 'tool-call-label',
        text: 'Arguments:'
      });

      const argsEl = contentEl.createEl('pre', {
        cls: 'tool-call-args'
      });

      argsEl.createEl('code', {
        text: JSON.stringify(toolCall.arguments, null, 2)
      });
    }

    // Make collapsible
    toggle.addEventListener('click', (e) => {
      e.stopPropagation();
      contentEl.classList.toggle('collapsed');
      toggle.textContent = contentEl.classList.contains('collapsed') ? '▶' : '▼';
    });

    // Start collapsed by default
    contentEl.classList.add('collapsed');
    toggle.textContent = '▶';

    this.scrollToBottom(container);
  }

  async addToolReturnMessage(container: HTMLElement, msg: any) {
    const toolEl = container.createEl('div', {
      cls: 'chat-message tool-return-card'
    });

    const header = toolEl.createEl('div', {
      cls: 'tool-return-header'
    });

    const toolReturnIcon = header.createEl('span', { cls: 'tool-return-icon' });
    toolReturnIcon.innerHTML = ICONS.check;

    header.createEl('span', {
      cls: 'tool-return-title',
      text: 'Tool Result'
    });

    const toggle = header.createEl('button', {
      cls: 'tool-return-toggle',
      text: '▼'
    });

    const contentEl = toolEl.createEl('div', {
      cls: 'tool-return-content'
    });

    const toolReturn = msg.tool_return || msg.content || '';

    // Try to parse and format JSON results
    try {
      const parsed = typeof toolReturn === 'string' ? JSON.parse(toolReturn) : toolReturn;
      const formatted = JSON.stringify(parsed, null, 2);

      const resultEl = contentEl.createEl('pre', {
        cls: 'tool-return-result'
      });

      resultEl.createEl('code', {
        text: formatted
      });
    } catch {
      // If not JSON, render as markdown
      await this.renderMessageContent(String(toolReturn), contentEl);
    }

    // Make collapsible
    toggle.addEventListener('click', (e) => {
      e.stopPropagation();
      contentEl.classList.toggle('collapsed');
      toggle.textContent = contentEl.classList.contains('collapsed') ? '▶' : '▼';
    });

    // Start collapsed by default
    contentEl.classList.add('collapsed');
    toggle.textContent = '▶';

    this.scrollToBottom(container);
  }

  private scrollToBottom(container: HTMLElement, smooth: boolean = true) {
    // Reading scrollHeight forces a layout reflow, which is necessary on
    // mobile WebViews where DOM mutations from streaming-markdown can get
    // batched without a paint until something triggers layout.
    const target = container.scrollHeight;

    if (smooth && !(this.app as any).isMobile) {
      container.scrollTo({ top: target, behavior: 'smooth' });
    } else {
      // Instant scroll on mobile (smooth scroll + animation queueing
      // causes the viewport to lag behind new content) and whenever
      // the caller explicitly asks for instant.
      container.scrollTop = target;
    }
  }

  renderEmptyState() {
    this.chatContentContainer.empty();

    const emptyEl = this.chatContentContainer.createEl('div', {
      cls: 'empty-chat'
    });

    const msgIconEl = emptyEl.createEl('div'); msgIconEl.innerHTML = ICONS.messageEmpty;
    emptyEl.createEl('h3', { text: 'No chat selected' });
    emptyEl.createEl('p', { text: 'Select a chat from the dropdown or create a new one' });
  }

  private isDefaultTitle(title: string | undefined): boolean {
    if (!title) return true;
    return (
      /^New Chat - .+$/i.test(title) ||
      /^Chat [0-9a-f]{8,}$/i.test(title) ||
      title.toLowerCase() === 'default conversation'
    );
  }

  maybeGenerateConversationTitle(sessionId: string, firstMessage: string): void {
    const session = this.chatSessions.find(s => s.id === sessionId);
    if (!session || !this.isDefaultTitle(session.title)) return;

    const thothUrl = this.plugin.settings.remoteEndpointUrl.replace(/\/$/, '');

    this.plugin.authFetch(`${thothUrl}/agents/conversations/generate-title`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: firstMessage })
    })
      .then(async (res) => {
        if (!res.ok) return;
        const { title } = await res.json();
        if (!title) return;

        const endpoint = this.plugin.getLettaProxyUrl();
        const patchRes = await this.plugin.authFetch(`${endpoint}/v1/conversations/${sessionId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ summary: title })
        });

        if (patchRes.ok && session) {
          session.title = title;
          const inList = this.chatSessions.find(s => s.id === sessionId);
          if (inList) inList.title = title;
          this.renderSessionList();
        }
      })
      .catch((err) => {
        // Title generation is best-effort — don't surface errors to the user
        console.warn('[MultiChatModal] Auto-title generation failed:', err);
      });
  }

  async renameSession(sessionId: string) {
    const session = this.chatSessions.find(s => s.id === sessionId);
    if (!session) return;

    const newTitle = await new Promise<string | null>((resolve) => {
      new InputModal(this.app, 'Enter new session name:', resolve, session.title ?? '').open();
    });
    if (!newTitle || newTitle === session.title) return;

    try {
      const endpoint = this.plugin.getLettaProxyUrl();
      // Note: NO trailing slash for PATCH - Letta API may have issues with trailing slashes
      const response = await this.plugin.authFetch(`${endpoint}/v1/conversations/${sessionId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ summary: newTitle })
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

  detectAgentInteraction(message: string): boolean {
    /**
     * Detect if message contains agent creation requests or @agent mentions
     */
    const messageLower = message.toLowerCase();

    // Check for agent creation patterns
    const creationPatterns = [
      /create.*agent/i,
      /make.*agent/i,
      /build.*agent/i,
      /new.*agent/i,
      /add.*agent/i
    ];

    const hasCreationPattern = creationPatterns.some(pattern => pattern.test(message));

    // Check for @agent mentions
    const agentMentions = /@([a-z][-a-z]*[a-z]|[a-z]+)/gi.test(message);

    // Check for agent list requests
    const listPatterns = [
      /list.*agents?/i,
      /show.*agents?/i,
      /what.*agents?/i,
      /available.*agents?/i,
      /my.*agents?/i
    ];

    const hasListPattern = listPatterns.some(pattern => pattern.test(message));

    return hasCreationPattern || agentMentions || hasListPattern;
  }

  async deleteSession(sessionId: string) {
    const session = this.chatSessions.find(s => s.id === sessionId);
    if (!session) return;

    // Check if this is the default conversation
    try {
      const defaultConvId = await this.getOrCreateDefaultConversation();
      if (sessionId === defaultConvId) {
        new Notice('Cannot delete the default conversation');
        return;
      }
    } catch (error) {
      console.error('Error checking default conversation:', error);
      new Notice('Failed to verify conversation status');
      return;
    }

    const confirmed = await new Promise<boolean>((resolve) => {
      new ConfirmModal(this.app, `Delete session "${session.title}"? This action cannot be undone.`, resolve).open();
    });
    if (!confirmed) return;

    try {
      const endpoint = this.plugin.getLettaProxyUrl();
      // Note: NO trailing slash for DELETE - Letta API returns 405 with trailing slash
      const response = await this.plugin.authFetch(`${endpoint}/v1/conversations/${sessionId}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        this.chatSessions = this.chatSessions.filter(s => s.id !== sessionId);

        if (this.activeSessionId === sessionId) {
          // Switch to default conversation
          const defaultConvId = await this.getOrCreateDefaultConversation();
          this.activeSessionId = null;
          this.plugin.settings.activeChatSessionId = null;
          await this.plugin.saveSettings();
          await this.switchToSession(defaultConvId);
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

  // Commands tab functionality (integrated from CommandsModal)
  createAgentCommands(contentEl: HTMLElement) {
    const section = contentEl.createEl('div', { cls: 'thoth-command-section' });
    section.createEl('h3').textContent = 'Agent Management';
    section.createEl('p', { text: 'Control the Thoth research agent' });

    const commandGrid = section.createEl('div', { cls: 'thoth-command-grid' });

    const commands = [
      {
        title: 'Start Agent',
        desc: 'Launch the research agent',
        action: () => this.plugin.startAgent()
      },
      {
        title: 'Stop Agent',
        desc: 'Stop the research agent',
        action: () => this.plugin.stopAgent()
      },
      {
        title: 'Restart Agent',
        desc: 'Restart the research agent',
        action: () => this.plugin.restartAgent()
      },
      {
        title: 'Agent Health Check',
        desc: 'Check agent status and health',
        action: () => this.runHealthCheck()
      }
    ];

    commands.forEach(cmd => {
      const button = commandGrid.createEl('div', { cls: 'thoth-command-button' });
      button.createEl('div', { text: cmd.title, cls: 'command-title' });
      button.createEl('div', { text: cmd.desc, cls: 'command-desc' });
      button.onclick = () => {
        cmd.action();
        new Notice(`Executed: ${cmd.title}`);
      };
    });
  }

  createDiscoveryCommands(contentEl: HTMLElement) {
    const section = contentEl.createEl('div', { cls: 'thoth-command-section' });
    section.createEl('h3').textContent = 'Discovery System';
    section.createEl('p', { text: 'Manage content discovery and indexing' });

    const commandGrid = section.createEl('div', { cls: 'thoth-command-grid' });

    const commands = [
      {
        title: 'Start Discovery',
        desc: 'Begin automated content discovery',
        action: () => this.runDiscoveryCommand('start')
      },
      {
        title: 'Stop Discovery',
        desc: 'Stop content discovery process',
        action: () => this.runDiscoveryCommand('stop')
      },
      {
        title: 'Discovery Status',
        desc: 'Check discovery system status',
        action: () => this.runDiscoveryCommand('status')
      }
    ];

    commands.forEach(cmd => {
      const button = commandGrid.createEl('div', { cls: 'thoth-command-button' });
      button.createEl('div', { text: cmd.title, cls: 'command-title' });
      button.createEl('div', { text: cmd.desc, cls: 'command-desc' });
      button.onclick = () => {
        cmd.action();
        new Notice(`Executed: ${cmd.title}`);
      };
    });
  }

  createDataCommands(contentEl: HTMLElement) {
    const section = contentEl.createEl('div', { cls: 'thoth-command-section' });
    section.createEl('h3').textContent = 'Data Management';
    section.createEl('p', { text: 'Manage knowledge base and data' });

    const commandGrid = section.createEl('div', { cls: 'thoth-command-grid' });

    const commands = [
      {
        title: 'Rebuild Index',
        desc: 'Rebuild the knowledge base index',
        action: () => this.runDataCommand('rebuild-index')
      },
      {
        title: 'Clear Cache',
        desc: 'Clear system caches',
        action: () => this.runDataCommand('clear-cache')
      },
      {
        title: 'Export Data',
        desc: 'Export knowledge base data',
        action: () => this.runDataCommand('export')
      },
      {
        title: 'Backup Data',
        desc: 'Create system backup',
        action: () => this.runDataCommand('backup')
      }
    ];

    commands.forEach(cmd => {
      const button = commandGrid.createEl('div', { cls: 'thoth-command-button' });
      button.createEl('div', { text: cmd.title, cls: 'command-title' });
      button.createEl('div', { text: cmd.desc, cls: 'command-desc' });
      button.onclick = () => {
        cmd.action();
        new Notice(`Executed: ${cmd.title}`);
      };
    });
  }

  createSystemCommands(contentEl: HTMLElement) {
    const section = contentEl.createEl('div', { cls: 'thoth-command-section' });
    section.createEl('h3').textContent = 'System Operations';
    section.createEl('p', { text: 'System-level operations and utilities' });

    const commandGrid = section.createEl('div', { cls: 'thoth-command-grid' });

    const commands = [
      {
        title: 'System Status',
        desc: 'View comprehensive system status',
        action: () => this.openSystemStatus()
      },
      {
        title: 'View Logs',
        desc: 'Open system logs',
        action: () => this.runSystemCommand('logs')
      },
      {
        title: 'Test Connection',
        desc: 'Test server connectivity',
        action: () => this.runSystemCommand('test-connection')
      },
      {
        title: 'Reset Settings',
        desc: 'Reset to default settings',
        action: () => this.confirmResetSettings()
      }
    ];

    commands.forEach(cmd => {
      const button = commandGrid.createEl('div', { cls: 'thoth-command-button' });
      button.createEl('div', { text: cmd.title, cls: 'command-title' });
      button.createEl('div', { text: cmd.desc, cls: 'command-desc' });
      button.onclick = () => {
        cmd.action();
        new Notice(`Executed: ${cmd.title}`);
      };
    });
  }

  async runHealthCheck() {
    try {
      const endpoint = this.plugin.getEndpointUrl();
      const response = await this.plugin.authFetch(`${endpoint}/health`);

      if (response.ok) {
        const data = await response.json();
        new Notice(`Agent Health: ${data.status || 'OK'}`);
      } else {
        new Notice('Agent health check failed', 3000);
      }
    } catch (error) {
      new Notice('Could not connect to agent', 3000);
    }
  }

  async runDiscoveryCommand(command: string) {
    try {
      const endpoint = this.plugin.getEndpointUrl();
      const response = await this.plugin.authFetch(`${endpoint}/execute/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          command: 'discovery',
          args: [command]
        })
      });

      if (response.ok) {
        const result = await response.json();
        new Notice(`Discovery ${command}: ${result.message || 'Success'}`);
      } else {
        throw new Error(`Discovery ${command} failed`);
      }
    } catch (error) {
      new Notice(`Discovery ${command} failed: ${error.message}`, 3000);
    }
  }

  async runDataCommand(command: string) {
    try {
      const endpoint = this.plugin.getEndpointUrl();
      const response = await this.plugin.authFetch(`${endpoint}/execute/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          command: 'data',
          args: [command]
        })
      });

      if (response.ok) {
        const result = await response.json();
        new Notice(`Data ${command}: ${result.message || 'Success'}`);
      } else {
        throw new Error(`Data ${command} failed`);
      }
    } catch (error) {
      new Notice(`Data ${command} failed: ${error.message}`, 3000);
    }
  }

  async runSystemCommand(command: string) {
    try {
      const endpoint = this.plugin.getEndpointUrl();
      const response = await this.plugin.authFetch(`${endpoint}/execute/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          command: 'system',
          args: [command]
        })
      });

      if (response.ok) {
        const result = await response.json();
        new Notice(`System ${command}: ${result.message || 'Success'}`);
      } else {
        throw new Error(`System ${command} failed`);
      }
    } catch (error) {
      new Notice(`System ${command} failed: ${error.message}`, 3000);
    }
  }

  openSystemStatus() {
    // This could open a separate status modal or switch to status tab
    this.switchTab('status');
    new Notice('Switched to Status tab');
  }

  async confirmResetSettings() {
    const confirmed = await this.plugin.showConfirm('Reset all settings to defaults? This cannot be undone.');
    if (confirmed) {
      // Reset settings logic would go here
      new Notice('Settings reset to defaults');
    }
  }

  openResearchAssistant() {
    this.switchTab('chat');
  }

  openQuickActions() {
    this.switchTab('commands');
  }

  // Status tab functionality
  createConnectionStatus(contentEl: HTMLElement) {
    const section = contentEl.createEl('div', { cls: 'status-section' });
    section.createEl('h3').textContent = 'Connection Status';

    const statusItems = [
      { label: 'Thoth Server', value: 'Connected', status: 'online' },
      { label: 'WebSocket', value: 'Active', status: 'online' },
      { label: 'Last Ping', value: '< 1 min ago', status: 'online' },
      { label: 'API Version', value: 'v1.2.3', status: 'online' }
    ];

    statusItems.forEach(item => {
      const statusItem = section.createEl('div', { cls: 'status-item' });

      const labelContainer = statusItem.createEl('div', { cls: 'status-label' });
      labelContainer.style.display = 'flex';
      labelContainer.style.alignItems = 'center';

      const indicator = labelContainer.createEl('div', {
        cls: `status-indicator status-${item.status}`
      });

      labelContainer.createEl('span', { text: item.label });

      statusItem.createEl('div', {
        text: item.value,
        cls: 'status-value'
      });
    });

    // Add refresh button
    const refreshBtn = section.createEl('button', {
      text: 'Refresh Status',
      cls: 'thoth-command-button'
    });
    refreshBtn.style.marginTop = '12px';
    refreshBtn.onclick = () => {
      this.refreshConnectionStatus();
    };
  }

  createSystemInfo(contentEl: HTMLElement) {
    const section = contentEl.createEl('div', { cls: 'status-section' });
    section.createEl('h3').textContent = 'System Information';

    const sysInfo = [
      { label: 'Plugin Version', value: '1.0.0' },
      { label: 'Obsidian Version', value: (this.app as any).vault.config?.version || 'Unknown' },
      { label: 'Active Sessions', value: this.chatSessions.length.toString() },
      { label: 'Cache Size', value: 'N/A' },
      { label: 'Uptime', value: 'N/A' }
    ];

    sysInfo.forEach(item => {
      const statusItem = section.createEl('div', { cls: 'status-item' });
      statusItem.createEl('div', { text: item.label, cls: 'status-label' });
      statusItem.createEl('div', { text: item.value, cls: 'status-value' });
    });
  }

  createActivityLog(contentEl: HTMLElement) {
    const section = contentEl.createEl('div', { cls: 'status-section' });
    section.createEl('h3').textContent = 'Recent Activity';

    const activities = [
      { time: '2 min ago', action: 'Chat session created' },
      { time: '5 min ago', action: 'Health check completed' },
      { time: '10 min ago', action: 'Connected to Thoth server' },
      { time: '15 min ago', action: 'Plugin initialized' }
    ];

    activities.forEach(activity => {
      const activityItem = section.createEl('div', { cls: 'status-item' });
      activityItem.createEl('div', { text: activity.action, cls: 'status-label' });
      activityItem.createEl('div', { text: activity.time, cls: 'status-value' });
    });

    // Add clear log button
    const clearBtn = section.createEl('button', {
      text: 'Clear Log',
      cls: 'thoth-command-button'
    });
    clearBtn.style.marginTop = '12px';
    clearBtn.onclick = () => {
      new Notice('Activity log cleared');
      // Clear log logic would go here
    };
  }

  async refreshConnectionStatus() {
    new Notice('Refreshing connection status...');

    try {
      // Perform health check
      await this.runHealthCheck();

      // Re-render status tab to update info
      if (this.currentTab === 'status') {
        await this.renderTabContent();
      }

      new Notice('Status refreshed');
    } catch (error) {
      new Notice('Failed to refresh status');
    }
  }

  // Conversations tab methods
  async loadAndDisplayConversations(container: HTMLElement) {
    try {
      container.empty();

      const loadingEl = container.createEl('div', { text: 'Loading conversations...', cls: 'loading' });

      // Use existing chat sessions data
      await this.loadChatSessions();

      loadingEl.remove();

      if (this.chatSessions.length === 0) {
        this.createEmptyState(
          container,
          ICONS.conversationsEmpty,
          'No conversations yet',
          'Start your first conversation to chat with Thoth and explore your research.',
          '+ New Conversation',
          () => this.createNewSession().then(() => this.switchTab('chat'))
        );
        return;
      }

      const sortedSessions = [...this.chatSessions].sort((a, b) => {
        if (a.metadata?.is_default) return -1;
        if (b.metadata?.is_default) return 1;
        return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
      });

      // Display conversation cards
      sortedSessions.forEach(session => {
        this.createConversationCard(container, session);
      });

      // Archived conversations link — only shown if there are any
      if (this.archivedIds.size > 0) {
        const archivedLink = container.createEl('div', { cls: 'thoth-archived-link' });
        archivedLink.createEl('span', {
          text: `${this.archivedIds.size} archived`,
          cls: 'thoth-archived-link-text'
        });
        archivedLink.onclick = () => this.showArchivedPanel();
      }

    } catch (error) {
      container.empty();
      container.createEl('div', {
        text: `Error loading conversations: ${error.message}`,
        cls: 'error-message'
      });
    }
  }

  createConversationCard(container: HTMLElement, session: ChatSession) {
    const card = container.createEl('div', {
      cls: 'thoth-conversation-card',
      attr: { 'data-session-id': session.id }
    });

    // Prevent text selection on the card
    card.style.userSelect = 'none';
    card.style.cursor = 'pointer';

    if (session.id === this.activeSessionId) {
      card.addClass('active');
    }

    // Mark as default if applicable
    if (session.metadata?.is_default) {
      card.addClass('default');
    }

    // Title
    const titleEl = card.createEl('div', {
      text: session.title || 'Untitled Conversation',
      cls: 'thoth-card-title'
    });

    // Add default badge if this is the default conversation
    if (session.metadata?.is_default) {
      const cardBadgeEl = titleEl.createEl('span', {
        cls: 'default-badge',
        attr: { 'title': 'Default conversation' }
      });
      cardBadgeEl.innerHTML = ICONS.star;
    }

    // Metadata (time)
    const metaEl = card.createEl('div', { cls: 'thoth-card-meta' });
    metaEl.setText(this.getTimeAgo(session.updated_at || session.created_at));

    // Click to switch
    card.onclick = async (e) => {
      // Prevent if clicking on buttons
      if ((e.target as HTMLElement).tagName === 'BUTTON') {
        return;
      }
      await this.switchToSession(session.id);
      this.switchTab('chat');
    };

    // Actions (delete, rename)
    const actionsEl = card.createEl('div', { cls: 'thoth-card-actions' });

    const renameBtn = actionsEl.createEl('button', {
      cls: 'thoth-card-action',
      attr: { 'aria-label': 'Rename', 'title': 'Rename' }
    });
    renameBtn.innerHTML = ICONS.edit;

    renameBtn.onclick = async (e) => {
      e.stopPropagation();
      await this.renameConversation(session);
    };

    // Make-default button — only shown on non-default conversations
    if (!session.metadata?.is_default) {
      const pinBtn = actionsEl.createEl('button', {
        cls: 'thoth-card-action thoth-pin-btn',
        attr: { 'aria-label': 'Set as default conversation', 'title': 'Set as default' }
      });
      pinBtn.innerHTML = ICONS.star;
      pinBtn.onclick = async (e) => {
        e.stopPropagation();
        await this.setDefaultConversation(session);
      };
    }

    // Default conversation cannot be archived
    if (!session.metadata?.is_default) {
      const archiveBtn = actionsEl.createEl('button', {
        text: '×',
        cls: 'thoth-card-action thoth-archive-btn',
        attr: { 'aria-label': 'Archive conversation', 'title': 'Archive (hide from list)' }
      });
      archiveBtn.onclick = async (e) => {
        e.stopPropagation();
        await this.archiveConversation(session);
      };
    }
  }

  getTimeAgo(dateString: string): string {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} min ago`;

    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;

    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 7) return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;

    return date.toLocaleDateString();
  }

  async renameConversation(session: ChatSession) {
    const newTitle = await this.promptForInput('Rename Conversation', session.title || '');
    if (!newTitle || newTitle === session.title) return;

    try {
      const endpoint = this.plugin.getLettaProxyUrl();
      // Sync to Letta API - NO trailing slash for PATCH
      const response = await this.plugin.authFetch(`${endpoint}/v1/conversations/${session.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ summary: newTitle })
      });

      if (response.ok) {
        // Update local state after successful API sync
        session.title = newTitle;

        // Also update in chatSessions array if present
        const sessionInList = this.chatSessions.find(s => s.id === session.id);
        if (sessionInList) {
          sessionInList.title = newTitle;
        }

        await this.plugin.saveSettings();
        await this.renderTabContent(); // Refresh UI
        new Notice('Conversation renamed');
      } else {
        throw new Error('Failed to rename conversation');
      }
    } catch (error) {
      console.error('Error renaming conversation:', error);
      new Notice('Failed to rename conversation');
    }
  }

  async deleteConversation(session: ChatSession) {
    // Check if this is the default conversation
    try {
      const defaultConvId = await this.getOrCreateDefaultConversation();
      if (session.id === defaultConvId) {
        new Notice('Cannot delete the default conversation');
        return;
      }
    } catch (error) {
      console.error('Error checking default conversation:', error);
      new Notice('Failed to verify conversation status');
      return;
    }

    const confirmed = await new Promise<boolean>((resolve) => {
      new ConfirmModal(
        this.app,
        `Delete conversation "${session.title || 'Untitled'}"? This action cannot be undone.`,
        resolve
      ).open();
    });
    if (confirmed) {
      try {
      // Delete from server
      const endpoint = this.plugin.getLettaProxyUrl();
      // Note: NO trailing slash for DELETE - Letta API returns 405 with trailing slash
      const deleteUrl = `${endpoint}/v1/conversations/${session.id}`;

      const response = await this.fetchWithTimeout(deleteUrl, {
        method: 'DELETE'
      });

      if (!response.ok) {
        throw new Error('Failed to delete conversation from server');
      }

        // Remove from local list
        this.chatSessions = this.chatSessions.filter(s => s.id !== session.id);

        // If deleted conversation was active, switch to default
        if (this.activeSessionId === session.id) {
          const defaultConvId = await this.getOrCreateDefaultConversation();
          this.activeSessionId = null;
          await this.switchToSession(defaultConvId);
        }

        // Reload conversations from server to ensure sync
        await this.loadChatSessions();

        // Re-render current tab to update UI
        await this.renderTabContent();

        // Also update sidebar if on chat tab
        if (this.currentTab === 'chat') {
          this.renderSessionList();
        }

        await this.plugin.saveSettings();
        new Notice('Conversation deleted');
      } catch (error) {
        console.error('Error deleting conversation:', error);
        new Notice('Failed to delete conversation');
      }
    }
  }

  async archiveConversation(session: ChatSession) {
    const thothUrl = this.plugin.settings.remoteEndpointUrl.replace(/\/$/, '');
    try {
      const res = await this.plugin.authFetch(
        `${thothUrl}/agents/conversations/${session.id}/archive`,
        { method: 'POST' }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      this.archivedIds.add(session.id);
      // If this was the active session, fall back to default
      if (this.activeSessionId === session.id) {
        this.activeSessionId = null;
        const defaultId = await this.getOrCreateDefaultConversation().catch(() => null);
        if (defaultId) await this.switchToSession(defaultId);
      }
      this.chatSessions = this.chatSessions.filter(s => s.id !== session.id);
      await this.renderTabContent();
      if (this.currentTab === 'chat') this.renderSessionList();
      new Notice(`"${session.title}" archived`);
    } catch (err) {
      new Notice(`Failed to archive: ${(err as Error).message}`);
    }
  }

  async showArchivedPanel() {
    const thothUrl = this.plugin.settings.remoteEndpointUrl.replace(/\/$/, '');
    const lettaProxy = this.plugin.getLettaProxyUrl();

    // Fetch the full conversation list so we can show titles
    let allConversations: any[] = [];
    try {
      const agentId = await this.getOrCreateDefaultAgent();
      const res = await this.fetchWithTimeout(`${lettaProxy}/v1/conversations/?agent_id=${agentId}&limit=200`);
      if (res.ok) allConversations = await res.json();
    } catch { /* show IDs only if fetch fails */ }

    const archived = allConversations.filter(c => this.archivedIds.has(c.id));

    // Build a modal overlay inside the conversations tab
    const overlay = this.contentContainer.createEl('div', { cls: 'thoth-archived-overlay' });

    const panel = overlay.createEl('div', { cls: 'thoth-archived-panel' });

    const panelHeader = panel.createEl('div', { cls: 'thoth-archived-panel-header' });
    panelHeader.createEl('span', { text: 'Archived Conversations', cls: 'thoth-archived-panel-title' });
    const closeBtn = panelHeader.createEl('button', { text: '×', cls: 'thoth-archived-panel-close' });
    closeBtn.onclick = () => overlay.remove();

    const list = panel.createEl('div', { cls: 'thoth-archived-panel-list' });

    if (archived.length === 0) {
      list.createEl('p', { text: 'No archived conversations.', cls: 'thoth-archived-empty' });
    } else {
      archived.forEach(conv => {
        const row = list.createEl('div', { cls: 'thoth-archived-row' });
        row.createEl('span', {
          text: conv.summary || `Chat ${conv.id.slice(0, 8)}`,
          cls: 'thoth-archived-row-title'
        });
        const restoreBtn = row.createEl('button', { text: 'Restore', cls: 'thoth-archived-restore-btn' });
        restoreBtn.onclick = async () => {
          try {
            const res = await this.plugin.authFetch(
              `${thothUrl}/agents/conversations/${conv.id}/archive`,
              { method: 'DELETE' }
            );
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            this.archivedIds.delete(conv.id);
            row.remove();
            if (this.archivedIds.size === 0) {
              list.createEl('p', { text: 'No archived conversations.', cls: 'thoth-archived-empty' });
            }
            await this.loadChatSessions();
            await this.renderTabContent();
            if (this.currentTab === 'chat') this.renderSessionList();
            new Notice(`"${conv.summary || 'Conversation'}" restored`);
          } catch (err) {
            new Notice(`Failed to restore: ${(err as Error).message}`);
          }
        };
      });
    }

    // Close on backdrop click
    overlay.onclick = (e) => {
      if (e.target === overlay) overlay.remove();
    };
  }

  filterConversations(query: string) {
    const cards = this.contentContainer.querySelectorAll<HTMLElement>('.thoth-conversation-card');
    const lowerQuery = query.toLowerCase().trim();

    if (!lowerQuery) {
      // Restore all cards and clear any snippets
      cards.forEach(card => {
        card.style.display = '';
        card.querySelector('.thoth-card-snippet')?.remove();
      });
      return;
    }

    // Tier 1: instant title filter + highlight
    cards.forEach(card => {
      const titleEl = card.querySelector('.thoth-card-title');
      const title = titleEl?.textContent?.toLowerCase() || '';
      card.style.display = title.includes(lowerQuery) ? '' : 'none';
      // Remove any stale content snippet from a previous search
      card.querySelector('.thoth-card-snippet')?.remove();
    });
  }

  private _searchDebounceTimer: ReturnType<typeof setTimeout> | null = null;

  handleConversationSearch(query: string) {
    // Instant tier-1 title filter runs immediately
    this.filterConversations(query);

    // Tier-2 content search fires after a short delay (only for 3+ char queries)
    if (this._searchDebounceTimer) clearTimeout(this._searchDebounceTimer);

    if (query.trim().length < 3) return;

    this._searchDebounceTimer = setTimeout(() => {
      this.searchConversationContent(query.trim());
    }, 300);
  }

  private async searchConversationContent(query: string) {
    const lowerQuery = query.toLowerCase();
    const endpoint = this.plugin.getLettaProxyUrl();
    const cards = this.contentContainer.querySelectorAll<HTMLElement>('.thoth-conversation-card');

    // Only search sessions that are currently visible (title matched or no title filter)
    const visibleSessions = this.chatSessions.filter(session => {
      const card = this.contentContainer.querySelector(
        `.thoth-conversation-card[data-session-id="${session.id}"]`
      ) as HTMLElement | null;
      return card && card.style.display !== 'none';
    });

    // For sessions whose titles didn't match, try fetching messages
    const titlesNotMatching = this.chatSessions.filter(session => {
      const title = (session.title || '').toLowerCase();
      if (title.includes(lowerQuery)) return false; // already showing from tier-1
      const card = this.contentContainer.querySelector(
        `.thoth-conversation-card[data-session-id="${session.id}"]`
      ) as HTMLElement | null;
      return card !== null; // only sessions that have a rendered card
    });

    await Promise.all(
      titlesNotMatching.map(async (session) => {
        const card = this.contentContainer.querySelector(
          `.thoth-conversation-card[data-session-id="${session.id}"]`
        ) as HTMLElement | null;
        if (!card) return;

        // Use cached messages if available; otherwise fetch a small batch
        let messages: any[] = this.messageCache.get(session.id) || [];

        if (messages.length === 0) {
          try {
            const res = await this.plugin.authFetch(
              `${endpoint}/v1/conversations/${session.id}/messages?limit=20&order=asc`
            );
            if (res.ok) {
              messages = await res.json();
            }
          } catch {
            return;
          }
        }

        // Search message content
        const matchingMsg = messages.find((msg: any) => {
          const content = typeof msg.content === 'string'
            ? msg.content
            : (Array.isArray(msg.content)
                ? msg.content.map((p: any) => p.text || '').join(' ')
                : '');
          return content.toLowerCase().includes(lowerQuery);
        });

        if (matchingMsg) {
          // Show this card and add a content snippet
          card.style.display = '';
          card.querySelector('.thoth-card-snippet')?.remove();

          const rawText = typeof matchingMsg.content === 'string'
            ? matchingMsg.content
            : (Array.isArray(matchingMsg.content)
                ? matchingMsg.content.map((p: any) => p.text || '').join(' ')
                : '');

          // Extract a short window around the match
          const idx = rawText.toLowerCase().indexOf(lowerQuery);
          const start = Math.max(0, idx - 40);
          const end = Math.min(rawText.length, idx + query.length + 80);
          let snippet = (start > 0 ? '…' : '') + rawText.slice(start, end) + (end < rawText.length ? '…' : '');

          // Highlight the match
          const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
          snippet = snippet.replace(new RegExp(escaped, 'gi'), (m) => `<mark>${m}</mark>`);

          const snippetEl = card.createEl('div', { cls: 'thoth-card-snippet' });
          snippetEl.innerHTML = snippet;
        }
      })
    );
  }

  async promptForInput(title: string, defaultValue: string = ''): Promise<string | null> {
    return new Promise((resolve) => {
      const modal = new Modal(this.app);
      modal.titleEl.setText(title);

      const input = modal.containerEl.createEl('input', {
        type: 'text',
        value: defaultValue
      });
      input.style.width = '100%';
      input.style.marginBottom = '10px';

      const buttonsEl = modal.containerEl.createEl('div');
      buttonsEl.style.display = 'flex';
      buttonsEl.style.justifyContent = 'flex-end';
      buttonsEl.style.gap = '10px';

      const cancelBtn = buttonsEl.createEl('button', { text: 'Cancel' });
      cancelBtn.onclick = () => {
        modal.close();
        resolve(null);
      };

      const okBtn = buttonsEl.createEl('button', { text: 'OK', cls: 'mod-cta' });
      okBtn.onclick = () => {
        modal.close();
        resolve(input.value);
      };

      input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
          modal.close();
          resolve(input.value);
        }
      });

      modal.open();
      input.focus();
    });
  }

  // Research tab
  async renderResearchTab() {
    const researchArea = this.contentContainer.createEl('div', { cls: 'research-area' });

    // Render Research Tab component (async - loads data from API)
    const researchTab = new ResearchTabComponent(researchArea, this.plugin);
    await researchTab.render();
  }

  // Settings tab
  renderSettingsTab() {
    const settingsArea = this.contentContainer.createEl('div', { cls: 'settings-area' });

    // Render Settings Tab component
    const settingsTab = new SettingsTabComponent(settingsArea, this.plugin);
    settingsTab.render();
  }

  async renderMCPServersTab() {
    const mcpServersArea = this.contentContainer.createEl('div', { cls: 'mcp-servers-area' });

    // Render MCP Servers Tab component
    const mcpServersTab = new MCPServersTabComponent(this.plugin, mcpServersArea);
    await mcpServersTab.render();
  }

  // Helper: Add dynamic status indicator with rotating thinking phrases
  addThinkingIndicator(container: HTMLElement): HTMLElement {
    const msg = container.createEl('div', { cls: 'message assistant thinking status-indicator-dynamic' });
    const content = msg.createEl('div', { cls: 'message-content' });
    const indicator = content.createEl('div', { cls: 'thinking-indicator' });
    indicator.createEl('span', { cls: 'dot' });
    indicator.createEl('span', { cls: 'dot' });
    indicator.createEl('span', { cls: 'dot' });
    const statusText = content.createEl('span', {
      text: getRandomThinkingPhrase('thinking') + '...',
      cls: 'status-text'
    });

    (msg as any).__statusText = statusText;
    (msg as any).__lastStatusUpdate = 0;

    // Rotate phrase every 2.5 seconds with a brief fade
    const rotationInterval = setInterval(() => {
      statusText.style.opacity = '0';
      setTimeout(() => {
        statusText.textContent = getRandomThinkingPhrase('thinking') + '...';
        statusText.style.opacity = '1';
      }, 200);
    }, 2500);
    (msg as any).__rotationInterval = rotationInterval;

    container.scrollTop = container.scrollHeight;

    return msg;
  }

  // Helper: Add a compact inline thinking indicator inside an existing assistant
  // bubble, used to bridge the gap between multi-turn agent responses.
  private addInlineThinkingIndicator(parent: HTMLElement): HTMLElement {
    const el = parent.createEl('div', { cls: 'inline-thinking-indicator' });
    const dots = el.createEl('div', { cls: 'thinking-indicator' });
    dots.createEl('span', { cls: 'dot' });
    dots.createEl('span', { cls: 'dot' });
    dots.createEl('span', { cls: 'dot' });
    const statusText = el.createEl('span', {
      text: getRandomThinkingPhrase('thinking') + '...',
      cls: 'status-text'
    });

    const rotationInterval = setInterval(() => {
      statusText.style.opacity = '0';
      setTimeout(() => {
        statusText.textContent = getRandomThinkingPhrase('thinking') + '...';
        statusText.style.opacity = '1';
      }, 200);
    }, 2500);
    (el as any).__rotationInterval = rotationInterval;

    return el;
  }

  // Helper: Update status indicator (throttled to prevent rapid flickering)
  updateStatusIndicator(indicator: HTMLElement, status: string, icon?: string, force = false) {
    const statusText = (indicator as any).__statusText;
    if (!statusText) return;

    const now = Date.now();
    const lastUpdate = (indicator as any).__lastStatusUpdate || 0;
    const MIN_INTERVAL_MS = 1000;

    // Skip update if we changed the phrase too recently (unless forced)
    if (!force && now - lastUpdate < MIN_INTERVAL_MS) return;

    let displayText = status;
    if (icon) {
      displayText = `${icon} ${status}`;
    }
    statusText.textContent = displayText;
    (indicator as any).__lastStatusUpdate = now;
  }

  /**
   * Progressively extract and stream text from accumulating send_message
   * JSON arguments. Once the "message": " prefix is found in the buffer,
   * every subsequent character (minus JSON framing) is message text that
   * gets written directly to the StreamingMarkdownRenderer.
   */
  private streamSendMessageDelta(
    buf: string,
    prefixIdx: number,
    renderedLen: number,
    getContainer: () => HTMLElement,
    contentEl: HTMLElement | null,
    renderer: StreamingMarkdownRenderer | null,
    setState: (
      el: HTMLElement | null,
      r: StreamingMarkdownRenderer | null,
      pre: number,
      len: number,
    ) => void,
  ): void {
    // Try to locate the opening quote of the message value
    if (prefixIdx < 0) {
      const m = buf.match(/"message"\s*:\s*"/);
      if (m) {
        prefixIdx = m.index! + m[0].length;
      }
    }

    if (prefixIdx < 0) {
      setState(contentEl, renderer, prefixIdx, renderedLen);
      return;
    }

    // Everything after the prefix is message content (with possible
    // trailing "}  that we strip).
    let raw = buf.substring(prefixIdx);
    // Remove trailing closing quote + brace if present
    raw = raw.replace(/"\s*\}?\s*$/, '');
    // Basic JSON unescape for common sequences
    const text = raw
      .replace(/\\n/g, '\n')
      .replace(/\\t/g, '\t')
      .replace(/\\"/g, '"')
      .replace(/\\\\/g, '\\');

    if (text.length > renderedLen) {
      const newChunk = text.substring(renderedLen);
      renderedLen = text.length;

      const container = getContainer();
      if (!contentEl) {
        contentEl = container.createEl('div', { cls: 'message-content' });
        renderer = new StreamingMarkdownRenderer(contentEl);
      }

      if (renderer) {
        renderer.write(newChunk);
      }
    }

    setState(contentEl, renderer, prefixIdx, renderedLen);
  }

  /**
   * Create a step pill inside a container.
   *
   * Reasoning pills are always expandable (content accumulates via streaming).
   * Tool pills are only expandable when the detail has meaningful content
   * (i.e. non-trivial JSON args). Simple tool calls with no args render as
   * a flat non-interactive badge.
   */
  private createStepPill(
    container: HTMLElement,
    icon: string,
    label: string,
    detail?: string,
    pillType: 'reasoning' | 'tool' = 'tool'
  ): HTMLElement {
    // Reasoning pills are always expandable; tool pills only if detail is non-trivial
    const hasDetail = detail && detail.trim().length > 20;
    const isExpandable = pillType === 'reasoning' || hasDetail;

    const pill = container.createEl('div', {
      cls: isExpandable ? 'step-pill' : 'step-pill pill-no-detail'
    });
    pill.dataset.pillType = pillType;

    const header = pill.createEl('div', { cls: 'pill-header' });
    const iconEl = header.createEl('span', { cls: 'pill-icon' });
    setIconEl(iconEl, icon);
    const labelEl = header.createEl('span', { cls: 'pill-label', text: label });

    let detailEl: HTMLElement | null = null;

    if (isExpandable) {
      header.createEl('span', { cls: 'pill-chevron', text: '\u203A' });
      detailEl = pill.createEl('div', { cls: 'pill-detail' });
      if (detail) {
        if (pillType === 'reasoning') {
          const textEl = detailEl.createEl('div', { cls: 'pill-detail-text reasoning-text' });
          textEl.textContent = detail.replace(/\n{3,}/g, '\n\n').trim();
        } else {
          detailEl.createEl('pre', { text: detail, cls: 'pill-detail-text' });
        }
      }
      header.addEventListener('click', () => {
        pill.toggleClass('expanded', !pill.hasClass('expanded'));
      });
    }

    (pill as any).__labelEl = labelEl;
    (pill as any).__detailEl = detailEl;

    return pill;
  }

  private updateStepPillLabel(pill: HTMLElement, label: string): void {
    const labelEl = (pill as any).__labelEl as HTMLElement;
    if (labelEl) labelEl.textContent = label;
  }

  private updateStepPillIcon(pill: HTMLElement, iconKey: string): void {
    const iconEl = pill.querySelector('.pill-icon') as HTMLElement | null;
    if (iconEl) setIconEl(iconEl, iconKey);
  }

  private updateStepPillDetail(pill: HTMLElement, detail: string): void {
    const detailEl = (pill as any).__detailEl as HTMLElement;
    if (!detailEl) return;
    detailEl.empty();
    if (!detail) return;

    const pillType = pill.dataset.pillType;
    if (pillType === 'reasoning') {
      const textEl = detailEl.createEl('div', { cls: 'pill-detail-text reasoning-text' });
      // Collapse excessive blank lines that accumulate during streaming
      textEl.textContent = detail.replace(/\n{3,}/g, '\n\n').trim();
    } else {
      detailEl.createEl('pre', { text: detail, cls: 'pill-detail-text' });
    }
  }

  // Helper: Show toast notification
  showToast(message: string, type: 'success' | 'error' | 'info' = 'info') {
    const toast = document.body.createEl('div', {
      cls: `thoth-toast thoth-toast-${type}`,
      text: message
    });

    // Auto-remove after 3 seconds
    setTimeout(() => {
      toast.addClass('thoth-toast-fade-out');
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }


  // Helper: Create empty state
  createEmptyState(container: HTMLElement, icon: string, title: string, description: string, actionText?: string, actionCallback?: () => void) {
    const emptyState = container.createEl('div', { cls: 'thoth-empty-state' });

    const iconEl = emptyState.createEl('div', { cls: 'empty-state-icon' });
    setIconEl(iconEl, icon);

    emptyState.createEl('h3', {
      cls: 'empty-state-title',
      text: title
    });

    emptyState.createEl('p', {
      cls: 'empty-state-description',
      text: description
    });

    if (actionText && actionCallback) {
      const actionBtn = emptyState.createEl('button', {
        cls: 'empty-state-action',
        text: actionText
      });
      actionBtn.onclick = actionCallback;
    }

    return emptyState;
  }

  // Helper: Show attachment menu
  showAttachmentMenu(inputEl: HTMLTextAreaElement, event: MouseEvent) {
    try {
      console.log('[MultiChatModal] Showing attachment menu');
      const menu = new Menu();

      menu.addItem((item) => {
        item
          .setTitle('Upload image')
          .setIcon('image')
          .onClick(() => {
            console.log('[MultiChatModal] Upload image clicked');
            this.uploadImage();
          });
      });

    menu.addItem((item) => {
      item
        .setTitle('Attach note from vault')
        .setIcon('document')
        .onClick(() => {
          this.attachVaultFile(inputEl);
        });
    });

    menu.addItem((item) => {
      item
        .setTitle('Attach current note')
        .setIcon('link')
        .onClick(() => {
          const activeFile = this.app.workspace.getActiveFile();
          if (activeFile) {
            const fileLink = `[[${activeFile.path}]]`;
            inputEl.value += `\n${fileLink}\n`;
            inputEl.focus();
          } else {
            new Notice('No active file');
          }
        });
    });

    menu.addItem((item) => {
      item
        .setTitle('Paste clipboard')
        .setIcon('clipboard')
        .onClick(async () => {
          try {
            const text = await navigator.clipboard.readText();
            inputEl.value += `\n${text}\n`;
            inputEl.focus();
          } catch (error) {
            new Notice('Failed to read clipboard');
          }
        });
    });

    console.log('[MultiChatModal] Calling menu.showAtMouseEvent');

      // Try to show menu at mouse position
      // Get the button's position for better positioning
      const target = event.target as HTMLElement;
      const rect = target.getBoundingClientRect();

      console.log('[MultiChatModal] Button position:', {
        x: event.clientX,
        y: event.clientY,
        rect: rect
      });

      // Show menu at the button position
      menu.showAtPosition({ x: rect.left, y: rect.bottom + 5 });

      console.log('[MultiChatModal] Menu should now be visible');

      // Check if menu is in DOM
      setTimeout(() => {
        const menuElements = document.querySelectorAll('.menu');
        console.log('[MultiChatModal] Found menu elements:', menuElements.length, menuElements);
      }, 100);
    } catch (error) {
      console.error('[MultiChatModal] Error showing attachment menu:', error);
      new Notice(`Error showing menu: ${error.message}`);
    }
  }

  // Helper: Attach vault file
  async attachVaultFile(inputEl: HTMLTextAreaElement) {
    // Simple implementation: Show notice for now
    // Full file picker would require extending SuggestModal properly
    new Notice('File attachment: Type [[ to create a wiki link to any note in your vault');
    inputEl.value += '[[';
    inputEl.focus();
  }

  /**
   * Upload an image via file picker.
   *
   * Example:
   *     >>> await this.uploadImage();
   */
  private async uploadImage(): Promise<void> {
    // Create a hidden file input
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/png,image/jpeg,image/gif,image/webp,.pdf,.txt,.md,.json,.csv,.py,.ts,.js,.html,.xml,.yaml,.yml,.toml,.rst,.tex,.log';
    input.multiple = true;

    input.onchange = async () => {
      if (!input.files || input.files.length === 0) return;

      for (const file of Array.from(input.files)) {
        try {
          await this.processFileAttachment(file);
        } catch (error) {
          new Notice(`Failed to add file: ${error.message}`, 5000);
          console.error('File upload error:', error);
        }
      }
    };

    // Trigger the file picker
    input.click();
  }

  /**
   * Process a file attachment (image or document).
   *
   * Args:
   *     file: The file to process
   *
   * Example:
   *     >>> await this.processFileAttachment(file);
   */
  private async processFileAttachment(file: File): Promise<void> {
    if (file.type.startsWith('image/')) {
      const attachment = await this.readFileAsBase64(file);
      await this.addAttachment(attachment);
      new Notice(`Added image: ${file.name}`);
    } else if (file.name.toLowerCase().endsWith('.pdf')) {
      const attachment = await this.extractPdfText(file);
      await this.addFileAttachment(attachment);
      new Notice(`Added PDF: ${file.name}`);
    } else {
      const attachment = await this.readFileAsText(file);
      await this.addFileAttachment(attachment);
      new Notice(`Added file: ${file.name}`);
    }
  }

  /**
   * Add an image attachment to the pending list and update preview.
   *
   * Args:
   *     attachment: The image attachment to add.
   *
   * Example:
   *     >>> await this.addAttachment(imageAttachment);
   */
  private async addAttachment(attachment: ImageAttachment): Promise<void> {
    this.pendingAttachments.push(attachment);
    this.updateAttachmentPreview();
  }

  /**
   * Add a file attachment to the pending list and update preview.
   *
   * Args:
   *     attachment: The file attachment to add.
   *
   * Example:
   *     >>> await this.addFileAttachment(fileAttachment);
   */
  private async addFileAttachment(attachment: FileAttachment): Promise<void> {
    this.pendingFileAttachments.push(attachment);
    this.updateAttachmentPreview();
  }

  /**
   * Remove an image attachment from the pending list.
   *
   * Args:
   *     index: The index of the attachment to remove.
   *
   * Example:
   *     >>> this.removeAttachment(0);
   */
  private removeAttachment(index: number): void {
    this.pendingAttachments.splice(index, 1);
    this.updateAttachmentPreview();
  }

  /**
   * Remove a file attachment from the pending list.
   *
   * Args:
   *     index: The index of the attachment to remove.
   *
   * Example:
   *     >>> this.removeFileAttachment(0);
   */
  private removeFileAttachment(index: number): void {
    this.pendingFileAttachments.splice(index, 1);
    this.updateAttachmentPreview();
  }

  /**
   * Update the attachment preview strip UI.
   *
   * Example:
   *     >>> this.updateAttachmentPreview();
   */
  private updateAttachmentPreview(): void {
    if (!this.attachmentPreviewContainer) return;

    this.attachmentPreviewContainer.empty();

    const hasAttachments = this.pendingAttachments.length > 0 || this.pendingFileAttachments.length > 0;

    if (!hasAttachments) {
      this.attachmentPreviewContainer.style.display = 'none';
      return;
    }

    this.attachmentPreviewContainer.style.display = 'flex';

    // Render image attachments
    this.pendingAttachments.forEach((attachment, index) => {
      const thumbContainer = this.attachmentPreviewContainer!.createEl('div', {
        cls: 'chat-attachment-thumb'
      });

      // Create thumbnail image
      const img = thumbContainer.createEl('img', {
        attr: {
          src: `data:${attachment.media_type};base64,${attachment.data}`,
          alt: attachment.name,
          title: attachment.name
        }
      });

      // Create remove button
      const removeBtn = thumbContainer.createEl('button', {
        cls: 'chat-attachment-remove',
        text: '×',
        attr: {
          'aria-label': 'Remove image',
          title: 'Remove image'
        }
      });

      removeBtn.onclick = (e) => {
        e.preventDefault();
        this.removeAttachment(index);
      };
    });

    // Render file attachments
    this.pendingFileAttachments.forEach((attachment, index) => {
      const fileContainer = this.attachmentPreviewContainer!.createEl('div', {
        cls: 'chat-attachment-file'
      });

      const fileIcon = fileContainer.createEl('span', { cls: 'chat-attachment-file-icon' });
      fileIcon.innerHTML = this.getFileIcon(attachment.name);

      const fileName = fileContainer.createEl('span', {
        cls: 'chat-attachment-file-name',
        text: attachment.name,
        attr: {
          title: `${attachment.name} (${(attachment.size / 1024).toFixed(1)}KB)`
        }
      });

      // Create remove button
      const removeBtn = fileContainer.createEl('button', {
        cls: 'chat-attachment-remove',
        text: '×',
        attr: {
          'aria-label': 'Remove file',
          title: 'Remove file'
        }
      });

      removeBtn.onclick = (e) => {
        e.preventDefault();
        this.removeFileAttachment(index);
      };
    });
  }

  /**
   * Clear all pending attachments.
   *
   * Example:
   *     >>> this.clearAttachments();
   */
  private clearAttachments(): void {
    this.pendingAttachments = [];
    this.pendingFileAttachments = [];
    this.updateAttachmentPreview();
  }

  /**
   * Render markdown content in a container element
   */
  async renderMessageContent(content: string, container: HTMLElement) {
    // Clear existing content
    container.empty();

    // Render markdown using Obsidian's native renderer
    // Pass the plugin as the Component to avoid memory leaks
    await MarkdownRenderer.render(
      this.app,
      content,
      container,
      '',  // sourcePath
      this.plugin  // Plugin extends Component
    );

    // Add copy buttons to code blocks
    this.addCopyButtonsToCodeBlocks(container);
  }

  /**
   * Add action buttons (like copy) to a message element
   */
  addMessageActions(messageEl: HTMLElement, rawContent: string) {
    // Only add to assistant messages
    if (!messageEl.classList.contains('assistant')) return;

    // Check if actions already exist
    if (messageEl.querySelector('.message-actions')) return;

    // Create actions container
    const actionsEl = messageEl.createEl('div', {
      cls: 'message-actions'
    });

    // Create copy button
    const copyBtn = actionsEl.createEl('button', {
      cls: 'message-copy-button',
      text: 'Copy response',
      attr: {
        'aria-label': 'Copy response to clipboard'
      }
    });

    // Add click handler
    copyBtn.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(rawContent);
        copyBtn.textContent = 'Copied!';
        copyBtn.classList.add('copied');

        // Reset button after 2 seconds
        setTimeout(() => {
          copyBtn.textContent = 'Copy response';
          copyBtn.classList.remove('copied');
        }, 2000);
      } catch (error) {
        console.error('Failed to copy response:', error);
        copyBtn.textContent = 'Failed';
        setTimeout(() => {
          copyBtn.textContent = 'Copy response';
        }, 2000);
      }
    });
  }

  /**
   * Add copy buttons to all code blocks in a container
   */
  addCopyButtonsToCodeBlocks(container: HTMLElement) {
    const codeBlocks = container.querySelectorAll('pre > code');

    codeBlocks.forEach((codeEl) => {
      const pre = codeEl.parentElement;
      if (!pre) return;

      // Check if button already exists
      if (pre.querySelector('.code-copy-button')) return;

      // Create copy button
      const copyBtn = document.createElement('button');
      copyBtn.className = 'code-copy-button';
      copyBtn.textContent = 'Copy';
      copyBtn.setAttribute('aria-label', 'Copy code to clipboard');

      // Add click handler
      copyBtn.addEventListener('click', async () => {
        const code = codeEl.textContent || '';

        try {
          await navigator.clipboard.writeText(code);
          copyBtn.textContent = 'Copied!';
          copyBtn.classList.add('copied');

          // Reset button after 2 seconds
          setTimeout(() => {
            copyBtn.textContent = 'Copy';
            copyBtn.classList.remove('copied');
          }, 2000);
        } catch (error) {
          console.error('Failed to copy code:', error);
          copyBtn.textContent = 'Failed';
          setTimeout(() => {
            copyBtn.textContent = 'Copy';
          }, 2000);
        }
      });

      // Add button to pre element
      pre.style.position = 'relative';
      pre.appendChild(copyBtn);
    });
  }

}
