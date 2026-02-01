import { App, Modal, Notice, Menu, SuggestModal } from 'obsidian';
import { ChatSession, ChatMessage } from '../types';
import type ThothPlugin from '../../main';
import { ResearchTabComponent } from '../components/research-tab';
import { SettingsTabComponent } from '../components/settings-tab';

export class MultiChatModal extends Modal {
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

  constructor(app: App, plugin: ThothPlugin) {
    super(app);
    this.plugin = plugin;
  }

  /**
   * Fetch with timeout to prevent UI from hanging
   */
  private async fetchWithTimeout(url: string, options: RequestInit = {}, timeoutMs: number = 10000): Promise<Response> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal
      });
      clearTimeout(timeoutId);
      return response;
    } catch (error) {
      clearTimeout(timeoutId);
      if (error.name === 'AbortError') {
        throw new Error('Request timed out - server may be down or slow');
      }
      throw error;
    }
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

    // Add global keyboard shortcuts
    this.setupKeyboardShortcuts();
  }

  setupModalPosition() {
    const modalEl = this.modalEl;
    modalEl.addClass('thoth-chat-popup');

    // Check if we're on mobile
    if ((this.app as any).isMobile) {
      // Mobile: Full-screen modal
      modalEl.addClass('thoth-mobile-modal');
      modalEl.style.position = 'fixed';
      modalEl.style.top = '0';
      modalEl.style.left = '0';
      modalEl.style.right = '0';
      modalEl.style.bottom = '0';
      modalEl.style.width = '100vw';
      modalEl.style.height = '100vh';
      modalEl.style.maxWidth = '100vw';
      modalEl.style.maxHeight = '100vh';
      modalEl.style.borderRadius = '0';
      modalEl.style.resize = 'none';
      modalEl.style.transform = 'none';
      modalEl.style.zIndex = '1000';
      modalEl.style.overflow = 'hidden';
    } else {
      // Desktop: Remove backdrop to allow background interaction
      const backdrop = modalEl.parentElement;
      if (backdrop && backdrop.classList.contains('modal-container')) {
        backdrop.style.backgroundColor = 'transparent';
        backdrop.style.pointerEvents = 'none';
        backdrop.addClass('thoth-transparent-backdrop');
        // Allow pointer events only on the modal itself
        modalEl.style.pointerEvents = 'auto';
      }

      // Also try to find and handle the backdrop element directly
      setTimeout(() => {
        const modalBackdrop = document.querySelector('.modal-container:has(.thoth-chat-popup), .modal-container .thoth-chat-popup')?.parentElement;
        if (modalBackdrop) {
          (modalBackdrop as HTMLElement).style.backgroundColor = 'transparent';
          (modalBackdrop as HTMLElement).style.pointerEvents = 'none';
          modalEl.style.pointerEvents = 'auto';
        }
      }, 100);

      // Desktop: Position in bottom right
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
  }

  makeDraggable() {
    const modalEl = this.modalEl;
    const titleEl = this.titleEl;

    // Skip dragging on mobile
    if ((this.app as any).isMobile) {
      // Mobile: Style title bar but no dragging
      titleEl.style.cursor = 'default';
      titleEl.style.userSelect = 'none';
      titleEl.style.padding = '15px 20px'; // Larger padding for touch
      titleEl.style.background = 'var(--background-secondary)';
      titleEl.style.borderBottom = '1px solid var(--background-modifier-border)';
      titleEl.style.borderRadius = '0';
      titleEl.style.fontSize = '16px'; // Larger text for mobile
      return;
    }

    let isDragging = false;
    let currentX = 0;
    let currentY = 0;
    let initialX = 0;
    let initialY = 0;
    let xOffset = 0;
    let yOffset = 0;

    // Desktop: Make title bar the drag handle
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
    this.modalEl.addEventListener('remove', () => {
      document.removeEventListener('keydown', handleKeydown);
    });
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
      { id: 'chat', label: '💬 Chat', icon: 'message-circle' },
      { id: 'conversations', label: '📝 Conversations', icon: 'message-square' },
      { id: 'research', label: '🔬 Research', icon: 'beaker' },
      { id: 'settings', label: '⚙️ Settings', icon: 'settings' }
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
      if (index === ['chat', 'conversations', 'research', 'settings'].indexOf(tabId)) {
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
        this.renderResearchTab();
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

    // Settings button
    const settingsBtn = controlsSection.createEl('button', {
      text: '⚙️',
      cls: 'settings-btn',
      title: 'Settings',
      attr: { 'aria-label': 'Settings' }
    });
    settingsBtn.onclick = () => {
      this.switchTab('settings');
    };

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
    const endpoint = this.plugin.getEndpointUrl();
    const isConnected = this.plugin.isAgentRunning || this.plugin.settings.remoteMode;
    const mode = this.plugin.settings.remoteMode ? 'Remote' : 'Local';
    
    const details = `
Connection Status: ${isConnected ? 'Connected' : 'Disconnected'}
Mode: ${mode}
Endpoint: ${endpoint}

${isConnected ? '✓ Ready to chat' : '⚠ Start the Thoth server to begin'}
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

    // Search box
    const searchInput = conversationsArea.createEl('input', {
      type: 'text',
      placeholder: 'Search conversations...',
      cls: 'thoth-conversation-search'
    });

    searchInput.oninput = () => {
      this.filterConversations(searchInput.value);
    };

    // Conversations list
    const conversationsListContainer = conversationsArea.createEl('div', { cls: 'conversations-list-container' });
    await this.loadAndDisplayConversations(conversationsListContainer);
  }

  async loadAndDisplayAgents(container: HTMLElement) {
    try {
      // Clear existing content
      container.empty();

      const loadingEl = container.createEl('div', { text: 'Loading agents...', cls: 'loading' });

      // Fetch available agents
      const endpoint = this.plugin.getEndpointUrl();
      const response = await fetch(`${endpoint}/agents/list`);

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
    // For now, show a simple alert. In the future, this could be a more sophisticated modal.
    const description = prompt(
      'Describe the agent you want to create:\n\nExample: "Create a citation analysis agent that can extract and analyze references from research papers"'
    );

    if (description && description.trim()) {
      // Switch to chat tab and send the creation message
      this.switchTab('chat');
      setTimeout(() => {
        const inputField = document.querySelector('.chat-input') as HTMLTextAreaElement;
        if (inputField) {
          inputField.value = `Create an agent that ${description.trim()}`;
          // Trigger the send message function
          const sendBtn = document.querySelector('.chat-send-btn') as HTMLButtonElement;
          if (sendBtn && !sendBtn.disabled) {
            sendBtn.click();
          }
        }
      }, 100);
    }
  }

  async confirmDeleteAgent(agentName: string) {
    // Note: This is actually deleting a conversation, not an agent
    // (Legacy method name from when we called conversations "agents")
    const sessionId = agentName; // The "name" is actually the session ID
    
    if (confirm(`Delete this conversation? This action cannot be undone.`)) {
      try {
        const endpoint = this.plugin.getEndpointUrl();
        const response = await fetch(`${endpoint}/v1/conversations/${sessionId}`, {
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

  addStyles() {
    const style = document.createElement('style');
    style.textContent = `
      .thoth-chat-popup {
        border-radius: 12px !important;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3) !important;
      }

      /* Allow background interaction by making backdrop transparent and non-interactive */
      .modal-container:has(.thoth-chat-popup),
      .thoth-transparent-backdrop {
        background-color: transparent !important;
        pointer-events: none !important;
      }

      .modal-container:has(.thoth-chat-popup) .thoth-chat-popup,
      .thoth-transparent-backdrop .thoth-chat-popup {
        pointer-events: auto !important;
      }

      /* Fallback for browsers that don't support :has() */
      .modal-container .thoth-chat-popup {
        pointer-events: auto !important;
      }

      /* Mobile-specific styles */
      .thoth-mobile-modal {
        border-radius: 0 !important;
      }

      .thoth-mobile-modal .thoth-tab-button {
        padding: 12px 20px !important;
        font-size: 14px !important;
        min-height: 44px !important;
      }

      .thoth-mobile-modal .new-chat-btn.compact,
      .thoth-mobile-modal .toggle-sidebar-btn {
        min-height: 44px !important;
        min-width: 44px !important;
        padding: 12px !important;
        font-size: 14px !important;
      }

      .thoth-mobile-modal .session-selector {
        min-height: 44px !important;
        font-size: 14px !important;
        padding: 8px 12px !important;
      }

      .thoth-mobile-modal .thoth-command-button {
        min-height: 44px !important;
        padding: 16px 20px !important;
        font-size: 14px !important;
      }

      .thoth-mobile-modal .chat-input {
        min-height: 44px !important;
        font-size: 16px !important;
        padding: 12px 16px !important;
      }

      .thoth-mobile-modal .chat-send-btn {
        min-height: 44px !important;
        padding: 12px 20px !important;
        font-size: 14px !important;
      }

      .thoth-mobile-modal .session-action-btn {
        min-width: 32px !important;
        min-height: 32px !important;
        padding: 8px !important;
      }

      .multi-chat-container.compact {
        display: flex;
        flex-direction: column;
        height: 100%;
        gap: 0;
        padding: 0;
        overflow: hidden;
        user-select: text;
      }

      .thoth-tab-navigation {
        display: flex;
        background: var(--background-secondary);
        border-bottom: 1px solid var(--background-modifier-border);
        padding: 8px 12px 0 12px;
        gap: 4px;
        flex-shrink: 0;
        user-select: none;
      }

      .thoth-tab-button {
        padding: 8px 16px;
        background: transparent;
        border: none;
        border-radius: 6px 6px 0 0;
        cursor: pointer;
        color: var(--text-muted);
        font-size: 13px;
        font-weight: 500;
        transition: all 0.2s ease;
        border-bottom: 2px solid transparent;
      }

      .thoth-tab-button:hover {
        background: var(--background-modifier-hover);
        color: var(--text-normal);
      }

      .thoth-tab-button.active {
        background: var(--background-primary);
        color: var(--text-accent);
        border-bottom-color: var(--interactive-accent);
      }

      .tab-content-container {
        flex: 1;
        display: flex;
        flex-direction: column;
        min-height: 0;
        overflow: hidden;
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
        flex-shrink: 0;
        user-select: none;
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
        overflow: hidden;
      }

      .chat-content {
        flex: 1;
        display: flex;
        flex-direction: column;
        padding: 8px;
        gap: 8px;
        min-height: 0;
        overflow: hidden;
      }

      .chat-messages {
        flex: 1;
        overflow-y: auto;
        overflow-x: hidden;
        padding: 8px;
        border: 1px solid var(--background-modifier-border);
        border-radius: 6px;
        background: var(--background-primary);
        min-height: 200px;
        max-height: none;
        scroll-behavior: smooth;
        scrollbar-width: thin;
        scrollbar-color: var(--scrollbar-thumb-bg) var(--scrollbar-bg);
        user-select: text;
        pointer-events: auto;
      }

      .chat-messages::-webkit-scrollbar {
        width: 6px;
      }

      .chat-messages::-webkit-scrollbar-track {
        background: var(--background-secondary);
        border-radius: 3px;
      }

      .chat-messages::-webkit-scrollbar-thumb {
        background: var(--text-muted);
        border-radius: 3px;
      }

      .chat-messages::-webkit-scrollbar-thumb:hover {
        background: var(--text-normal);
      }

      .chat-message {
        margin-bottom: 12px;
        padding: 8px 12px;
        border-radius: 8px;
        max-width: 85%;
        word-wrap: break-word;
        animation: fadeIn 0.3s ease-in-out;
        position: relative;
        user-select: text;
        pointer-events: auto;
        cursor: text;
      }

      @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
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
        user-select: text;
        pointer-events: auto;
        cursor: text;
      }

      .chat-input-area {
        display: flex;
        gap: 6px;
        align-items: flex-end;
        flex-shrink: 0;
        pointer-events: auto !important;
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
        pointer-events: auto !important;
        cursor: text;
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

      /* Commands tab styles */
      .commands-area {
        flex: 1;
        overflow-y: auto;
        padding: 16px;
        height: 100%;
      }

      .thoth-command-section {
        margin-bottom: 24px;
        padding: 16px;
        border: 1px solid var(--background-modifier-border);
        border-radius: 8px;
        background: var(--background-secondary);
      }

      .thoth-command-section h3 {
        margin: 0 0 12px 0;
        color: var(--text-accent);
        font-size: 16px;
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .thoth-command-section p {
        margin: 0 0 16px 0;
        color: var(--text-muted);
        font-size: 14px;
      }

      .thoth-command-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 12px;
      }

      .thoth-command-button {
        padding: 12px 16px;
        border: 1px solid var(--background-modifier-border);
        background: var(--background-primary);
        color: var(--text-normal);
        border-radius: 6px;
        cursor: pointer;
        transition: all 0.2s ease;
        text-align: left;
        font-size: 14px;
        line-height: 1.4;
      }

      .thoth-command-button:hover {
        background: var(--background-modifier-hover);
        border-color: var(--interactive-accent);
        transform: translateY(-1px);
      }

      .thoth-command-button:active {
        transform: translateY(0);
      }

      .command-title {
        font-weight: 600;
        margin-bottom: 4px;
      }

      .command-desc {
        font-size: 12px;
        color: var(--text-muted);
      }

      /* Tools tab styles */
      .tools-area {
        flex: 1;
        overflow-y: auto;
        padding: 16px;
        height: 100%;
      }

      /* Status tab styles */
      .status-area {
        flex: 1;
        overflow-y: auto;
        padding: 16px;
        height: 100%;
      }

      .status-section {
        margin-bottom: 24px;
        padding: 16px;
        border: 1px solid var(--background-modifier-border);
        border-radius: 8px;
        background: var(--background-secondary);
      }

      .status-section h3 {
        margin: 0 0 12px 0;
        color: var(--text-accent);
        font-size: 16px;
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .status-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 0;
        border-bottom: 1px solid var(--background-modifier-border);
      }

      .status-item:last-child {
        border-bottom: none;
      }

      .status-label {
        font-weight: 500;
        color: var(--text-normal);
      }

      .status-value {
        color: var(--text-muted);
        font-size: 14px;
      }

      .status-indicator {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 8px;
      }

      .status-online {
        background-color: var(--color-green);
      }

      .status-offline {
        background-color: var(--color-red);
      }

      .status-warning {
        background-color: var(--color-orange);
      }
    `;
    document.head.appendChild(style);
  }

  async loadChatSessions() {
    try {
      const endpoint = this.plugin.getEndpointUrl();
      // Get conversations for the default agent
      const agentId = await this.getOrCreateDefaultAgent();
      const response = await this.fetchWithTimeout(`${endpoint}/v1/conversations?agent_id=${agentId}&limit=50`);

      if (response.ok) {
        const conversations = await response.json();
        // Map Letta conversations to session format with all required ChatSession properties
        this.chatSessions = conversations.map((conv: any): ChatSession => ({
          id: conv.id,
          title: conv.summary || `Chat ${conv.id.slice(0, 8)}`,
          created_at: conv.created_at,
          updated_at: conv.updated_at || conv.created_at,
          is_active: conv.id === this.activeSessionId,
          message_count: conv.message_count || 0,
          last_message_preview: conv.last_message || '',
          metadata: { agent_id: conv.agent_id }
        }));
      } else {
        console.warn('Could not load chat sessions from server');
        this.chatSessions = [];
      }
    } catch (error) {
      console.warn('Failed to load chat sessions:', error);
      this.chatSessions = [];
    }
  }

  private cachedAgentId: string | null = null;

  async getOrCreateDefaultAgent(): Promise<string> {
    // Return cached agent ID if available
    if (this.cachedAgentId) {
      return this.cachedAgentId;
    }

    try {
      const endpoint = this.plugin.getEndpointUrl();
      // Get the main Thoth orchestrator agent (auto-created by backend on startup)
      const listResponse = await this.fetchWithTimeout(`${endpoint}/v1/agents?limit=100`);
      if (listResponse.ok) {
        const agents = await listResponse.json();
        // The main orchestrator is always named "thoth_research_agent"
        const thothAgent = agents.find((a: any) => a.name === 'thoth_research_agent');
        
        if (thothAgent) {
          this.cachedAgentId = thothAgent.id;
          return thothAgent.id;
        }
      }

      // Agent not found - backend may not have started properly
      throw new Error('Thoth orchestrator agent not found. Please ensure the Thoth backend is running and has initialized agents.');
    } catch (error) {
      console.error('Failed to get Thoth agent:', error);
      throw error;
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

        sessionEl.onclick = () => {
          this.switchToSession(session.id);
          // Note: switchToSession already calls closeSidebar()
        };

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
      const agentId = await this.getOrCreateDefaultAgent();

      const response = await fetch(`${endpoint}/v1/conversations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_id: agentId,
          summary: sessionTitle
        })
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

    // Auto-close sidebar after switching session
    this.closeSidebar();
  }


  async loadChatMessages(sessionId: string) {
    this.chatContentContainer.empty();

    try {
      const endpoint = this.plugin.getEndpointUrl();
      const response = await fetch(`${endpoint}/v1/conversations/${sessionId}/messages?limit=100`);

      if (response.ok) {
        const messages = await response.json();
        this.renderChatInterface(sessionId, messages || []);
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

    // Load existing messages or show empty state
    if (messages.length === 0) {
      this.createEmptyState(
        messagesContainer,
        '💬',
        'Start a conversation',
        'Ask me anything about your research, papers, or knowledge base. I can help you discover papers, analyze citations, and more.',
        'Try: "Find recent papers on transformers"'
      );
    } else {
      messages.forEach(msg => {
        this.addMessageToChat(messagesContainer, msg.role, msg.content);
      });
    }

    // Input area
    const inputArea = this.chatContentContainer.createEl('div', {
      cls: 'chat-input-area'
    });

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

    // Attachment button
    const attachBtn = inputArea.createEl('button', {
      text: '📎',
      cls: 'chat-attach-btn',
      attr: { 'aria-label': 'Attach file', 'title': 'Attach file for context' }
    });
    
    attachBtn.onclick = (e: MouseEvent) => {
      e.preventDefault();
      this.showAttachmentMenu(inputEl, e);
    };

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

      // Auto-resize input back to minimum height
      inputEl.style.height = '36px';

      // Disable send button
      sendBtn.disabled = true;
      sendBtn.textContent = 'Sending...';

      // Add thinking indicator
      const thinkingMsg = this.addThinkingIndicator(messagesContainer);

      try {
        // Send to Letta conversation
        const endpoint = this.plugin.getEndpointUrl();
        const response = await fetch(`${endpoint}/v1/conversations/${sessionId}/messages`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            role: 'user',
            text: message
          })
        });

        if (response.ok) {
          // Remove thinking indicator
          thinkingMsg.remove();
          
          const result = await response.json();
          // Letta returns an array of messages (assistant response)
          const messages = Array.isArray(result) ? result : [result];
          messages.forEach((msg: any) => {
            if (msg.role === 'assistant') {
              this.addMessageToChat(messagesContainer, 'assistant', msg.text);
            }
          });

          // Update session list to reflect new message
          await this.loadChatSessions();
          this.renderSessionList();
          
          // Show success toast
          this.showToast('Message sent successfully', 'success');
        } else {
          throw new Error('Failed to send message');
        }
      } catch (error) {
        console.error('Chat error:', error);
        // Remove thinking indicator
        thinkingMsg.remove();
        this.addMessageToChat(messagesContainer, 'assistant', `Error: ${error.message}`);
        this.showToast(`Error: ${error.message}`, 'error');
      } finally {
        sendBtn.disabled = false;
        sendBtn.textContent = 'Send';
        inputEl.focus();
      }
    };

    sendBtn.onclick = sendMessage;

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
  }

  addMessageToChat(container: HTMLElement, role: string, content: string) {
    const messageEl = container.createEl('div', {
      cls: `chat-message ${role}`
    });

    messageEl.createEl('div', {
      text: role === 'user' ? 'You' : 'Assistant',
      cls: 'message-role'
    });

    const contentEl = messageEl.createEl('div', {
      text: content,
      cls: 'message-content'
    });

    // Auto-scroll to new message with smooth behavior
    setTimeout(() => {
      this.scrollToBottom(container);
    }, 100);
  }

  private scrollToBottom(container: HTMLElement, smooth: boolean = true) {
    if (smooth) {
      container.scrollTo({
        top: container.scrollHeight,
        behavior: 'smooth'
      });
    } else {
      container.scrollTop = container.scrollHeight;
    }
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
      const response = await fetch(`${endpoint}/v1/conversations/${sessionId}`, {
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

    if (!confirm(`Delete "${session.title}"? This cannot be undone.`)) return;

    try {
      const endpoint = this.plugin.getEndpointUrl();
      const response = await fetch(`${endpoint}/v1/conversations/${sessionId}`, {
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

  // Commands tab functionality (integrated from CommandsModal)
  createAgentCommands(contentEl: HTMLElement) {
    const section = contentEl.createEl('div', { cls: 'thoth-command-section' });
    section.createEl('h3').innerHTML = '🤖 Agent Management';
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
    section.createEl('h3').innerHTML = '🔍 Discovery System';
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
      },
      {
        title: 'Add Discovery Source',
        desc: 'Add new content source',
        action: () => this.plugin.openDiscoverySourceModal()
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
    section.createEl('h3').innerHTML = '📊 Data Management';
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
    section.createEl('h3').innerHTML = '⚙️ System Operations';
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
      const response = await fetch(`${endpoint}/health`);

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
      const response = await fetch(`${endpoint}/execute/command`, {
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
      const response = await fetch(`${endpoint}/execute/command`, {
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
      const response = await fetch(`${endpoint}/execute/command`, {
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

  // Tools tab functionality
  createCitationTools(contentEl: HTMLElement) {
    const section = contentEl.createEl('div', { cls: 'thoth-command-section' });
    section.createEl('h3').innerHTML = '📝 Citation Tools';
    section.createEl('p', { text: 'Tools for managing citations and references' });

    const commandGrid = section.createEl('div', { cls: 'thoth-command-grid' });

    const tools = [
      {
        title: 'Citation Inserter',
        desc: 'Insert formatted citations into your notes',
        action: () => this.openCitationInserter()
      },
      {
        title: 'Reference Manager',
        desc: 'Manage your reference library',
        action: () => this.openReferenceManager()
      },
      {
        title: 'Auto-Cite Selection',
        desc: 'Automatically cite selected text',
        action: () => this.autoCiteSelection()
      },
      {
        title: 'Export Bibliography',
        desc: 'Export bibliography in various formats',
        action: () => this.exportBibliography()
      }
    ];

    tools.forEach(tool => {
      const button = commandGrid.createEl('div', { cls: 'thoth-command-button' });
      button.createEl('div', { text: tool.title, cls: 'command-title' });
      button.createEl('div', { text: tool.desc, cls: 'command-desc' });
      button.onclick = () => {
        tool.action();
        new Notice(`Executed: ${tool.title}`);
      };
    });
  }

  createResearchTools(contentEl: HTMLElement) {
    const section = contentEl.createEl('div', { cls: 'thoth-command-section' });
    section.createEl('h3').innerHTML = '🔬 Research Tools';
    section.createEl('p', { text: 'Advanced research and analysis tools' });

    const commandGrid = section.createEl('div', { cls: 'thoth-command-grid' });

    const tools = [
      {
        title: 'Research Assistant',
        desc: 'Open the research assistant interface',
        action: () => this.openResearchAssistant()
      },
      {
        title: 'Topic Explorer',
        desc: 'Explore topics and connections',
        action: () => this.openTopicExplorer()
      },
      {
        title: 'Source Discovery',
        desc: 'Discover new relevant sources',
        action: () => this.openSourceDiscovery()
      },
      {
        title: 'Concept Map',
        desc: 'Generate concept maps from your notes',
        action: () => this.generateConceptMap()
      }
    ];

    tools.forEach(tool => {
      const button = commandGrid.createEl('div', { cls: 'thoth-command-button' });
      button.createEl('div', { text: tool.title, cls: 'command-title' });
      button.createEl('div', { text: tool.desc, cls: 'command-desc' });
      button.onclick = () => {
        tool.action();
        new Notice(`Executed: ${tool.title}`);
      };
    });
  }

  createUtilityTools(contentEl: HTMLElement) {
    const section = contentEl.createEl('div', { cls: 'thoth-command-section' });
    section.createEl('h3').innerHTML = '🛠️ Utility Tools';
    section.createEl('p', { text: 'General utility and helper functions' });

    const commandGrid = section.createEl('div', { cls: 'thoth-command-grid' });

    const tools = [
      {
        title: 'Note Templates',
        desc: 'Create notes from templates',
        action: () => this.openNoteTemplates()
      },
      {
        title: 'Quick Actions',
        desc: 'Access quick action menu',
        action: () => this.openQuickActions()
      },
      {
        title: 'File Organization',
        desc: 'Organize and manage files',
        action: () => this.openFileOrganizer()
      },
      {
        title: 'Bulk Operations',
        desc: 'Perform bulk operations on notes',
        action: () => this.openBulkOperations()
      }
    ];

    tools.forEach(tool => {
      const button = commandGrid.createEl('div', { cls: 'thoth-command-button' });
      button.createEl('div', { text: tool.title, cls: 'command-title' });
      button.createEl('div', { text: tool.desc, cls: 'command-desc' });
      button.onclick = () => {
        tool.action();
        new Notice(`Executed: ${tool.title}`);
      };
    });
  }

  // Tool action methods
  async openCitationInserter() {
    // Check if there's an active editor
    const activeLeaf = this.app.workspace.activeLeaf;
    if (activeLeaf?.view?.getViewType() === 'markdown') {
      const editor = (activeLeaf.view as any).editor;
      if (editor) {
        await this.plugin.openCitationInserter(editor);
      } else {
        new Notice('No active editor found');
      }
    } else {
      new Notice('Please open a markdown file first');
    }
  }

  openReferenceManager() {
    new Notice('Reference manager coming soon!');
  }

  autoCiteSelection() {
    const activeLeaf = this.app.workspace.activeLeaf;
    if (activeLeaf?.view?.getViewType() === 'markdown') {
      const editor = (activeLeaf.view as any).editor;
      if (editor) {
        const selection = editor.getSelection();
        if (selection) {
          new Notice(`Auto-citing: "${selection.substring(0, 50)}..."`);
          // Auto-cite logic would go here
        } else {
          new Notice('Please select text to cite');
        }
      }
    } else {
      new Notice('Please open a markdown file first');
    }
  }

  exportBibliography() {
    new Notice('Bibliography export coming soon!');
  }

  openResearchAssistant() {
    // Switch to chat tab as that's our research interface
    this.switchTab('chat');
    new Notice('Research assistant is available in the Chat tab');
  }

  openTopicExplorer() {
    new Notice('Topic explorer coming soon!');
  }

  openSourceDiscovery() {
    this.plugin.openDiscoverySourceCreator();
  }

  generateConceptMap() {
    new Notice('Concept map generation coming soon!');
  }

  openNoteTemplates() {
    new Notice('Note templates coming soon!');
  }

  openQuickActions() {
    // Switch to commands tab
    this.switchTab('commands');
    new Notice('Quick actions are available in the Commands tab');
  }

  openFileOrganizer() {
    new Notice('File organizer coming soon!');
  }

  openBulkOperations() {
    new Notice('Bulk operations coming soon!');
  }

  // Status tab functionality
  createConnectionStatus(contentEl: HTMLElement) {
    const section = contentEl.createEl('div', { cls: 'status-section' });
    section.createEl('h3').innerHTML = '🔗 Connection Status';

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
      text: '🔄 Refresh Status',
      cls: 'thoth-command-button'
    });
    refreshBtn.style.marginTop = '12px';
    refreshBtn.onclick = () => {
      this.refreshConnectionStatus();
    };
  }

  createSystemInfo(contentEl: HTMLElement) {
    const section = contentEl.createEl('div', { cls: 'status-section' });
    section.createEl('h3').innerHTML = '💻 System Information';

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
    section.createEl('h3').innerHTML = '📋 Recent Activity';

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
      text: '🗑️ Clear Log',
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
        this.renderTabContent();
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
          '📝',
          'No conversations yet',
          'Start your first conversation to chat with Thoth and explore your research.',
          '+ New Conversation',
          () => this.createNewSession().then(() => this.switchTab('chat'))
        );
        return;
      }

      // Sort by most recent first
      const sortedSessions = [...this.chatSessions].sort((a, b) => {
        const dateA = new Date(b.created_at || 0).getTime();
        const dateB = new Date(a.created_at || 0).getTime();
        return dateA - dateB;
      });

      // Display conversation cards
      sortedSessions.forEach(session => {
        this.createConversationCard(container, session);
      });

    } catch (error) {
      container.empty();
      container.createEl('div', {
        text: `Error loading conversations: ${error.message}`,
        cls: 'error-message'
      });
    }
  }

  createConversationCard(container: HTMLElement, session: ChatSession) {
    const card = container.createEl('div', { cls: 'thoth-conversation-card' });

    // Prevent text selection on the card
    card.style.userSelect = 'none';
    card.style.cursor = 'pointer';

    if (session.id === this.activeSessionId) {
      card.addClass('active');
    }

    // Title
    const titleEl = card.createEl('div', {
      text: session.title || 'Untitled Conversation',
      cls: 'thoth-card-title'
    });

    // Metadata (time and message count)
    const metaEl = card.createEl('div', { cls: 'thoth-card-meta' });

    const timeAgo = this.getTimeAgo(session.created_at);
    const messageCount = session.message_count || 0;

    metaEl.setText(`${timeAgo} • ${messageCount} message${messageCount !== 1 ? 's' : ''}`);

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
      text: '✏️',
      cls: 'thoth-card-action',
      attr: { 'aria-label': 'Rename' }
    });

    renameBtn.onclick = async (e) => {
      e.stopPropagation();
      await this.renameConversation(session);
    };

    const deleteBtn = actionsEl.createEl('button', {
      text: '🗑️',
      cls: 'thoth-card-action delete',
      attr: { 'aria-label': 'Delete' }
    });

    deleteBtn.onclick = async (e) => {
      e.stopPropagation();
      await this.deleteConversation(session);
    };
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
    if (newTitle && newTitle !== session.title) {
      session.title = newTitle;
      await this.plugin.saveSettings();
      this.renderTabContent(); // Refresh
    }
  }

  async deleteConversation(session: ChatSession) {
    const confirmed = confirm(`Delete conversation "${session.title || 'Untitled'}"?`);
    if (confirmed) {
      this.chatSessions = this.chatSessions.filter(s => s.id !== session.id);
      if (this.activeSessionId === session.id) {
        this.activeSessionId = null;
        if (this.chatSessions.length > 0) {
          await this.switchToSession(this.chatSessions[0].id);
        } else {
          await this.createNewSession();
        }
      }
      await this.plugin.saveSettings();
      this.renderTabContent(); // Refresh
    }
  }

  filterConversations(query: string) {
    const cards = this.contentContainer.querySelectorAll('.thoth-conversation-card');
    const lowerQuery = query.toLowerCase();

    cards.forEach(card => {
      const titleEl = card.querySelector('.thoth-card-title');
      const title = titleEl?.textContent?.toLowerCase() || '';

      if (title.includes(lowerQuery)) {
        (card as HTMLElement).style.display = '';
      } else {
        (card as HTMLElement).style.display = 'none';
      }
    });
  }

  async promptForInput(title: string, defaultValue: string = ''): Promise<string | null> {
    return new Promise((resolve) => {
      const modal = new Modal(this.app);
      modal.titleEl.setText(title);
      
      const input = modal.contentEl.createEl('input', { 
        type: 'text',
        value: defaultValue
      });
      input.style.width = '100%';
      input.style.marginBottom = '10px';
      
      const buttonsEl = modal.contentEl.createEl('div');
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
  renderResearchTab() {
    const researchArea = this.contentContainer.createEl('div', { cls: 'research-area' });

    // Render Research Tab component
    const researchTab = new ResearchTabComponent(researchArea, this.plugin);
    researchTab.render();
  }

  // Settings tab
  renderSettingsTab() {
    const settingsArea = this.contentContainer.createEl('div', { cls: 'settings-area' });

    // Render Settings Tab component
    const settingsTab = new SettingsTabComponent(settingsArea, this.plugin);
    settingsTab.render();
  }

  // Helper: Add thinking indicator
  addThinkingIndicator(container: HTMLElement): HTMLElement {
    const msg = container.createEl('div', { cls: 'message assistant thinking' });
    const content = msg.createEl('div', { cls: 'message-content' });
    const indicator = content.createEl('div', { cls: 'thinking-indicator' });
    indicator.createEl('span', { cls: 'dot' });
    indicator.createEl('span', { cls: 'dot' });
    indicator.createEl('span', { cls: 'dot' });
    content.createEl('span', { text: 'Thinking...' });
    
    // Scroll to bottom
    container.scrollTop = container.scrollHeight;
    
    return msg;
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
    
    emptyState.createEl('div', { 
      cls: 'empty-state-icon',
      text: icon 
    });
    
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
    const menu = new Menu();
    
    menu.addItem((item) => {
      item
        .setTitle('📄 Attach note from vault')
        .setIcon('document')
        .onClick(() => {
          this.attachVaultFile(inputEl);
        });
    });
    
    menu.addItem((item) => {
      item
        .setTitle('🔗 Attach current note')
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
        .setTitle('📋 Paste clipboard')
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
    
    menu.showAtMouseEvent(event);
  }

  // Helper: Attach vault file
  async attachVaultFile(inputEl: HTMLTextAreaElement) {
    // Simple implementation: Show notice for now
    // Full file picker would require extending SuggestModal properly
    new Notice('File attachment: Type [[ to create a wiki link to any note in your vault');
    inputEl.value += '[[';
    inputEl.focus();
  }
}
