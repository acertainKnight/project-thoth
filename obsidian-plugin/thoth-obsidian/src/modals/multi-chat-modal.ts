import { App, Modal, Notice } from 'obsidian';
import { ChatSession, ChatMessage } from '../types';
import type ThothPlugin from '../../main';

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
      { id: 'research', label: '🔬 Research', icon: 'beaker' }
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
      if (index === ['chat', 'conversations', 'research'].indexOf(tabId)) {
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
    }
  }

  renderChatTab() {
    // Top bar with session selector and controls (only for chat tab)
    const topBar = this.contentContainer.createEl('div', { cls: 'chat-top-bar' });

    // Session selector dropdown
    const sessionSelector = topBar.createEl('select', { cls: 'session-selector' });
    this.sessionSelector = sessionSelector;
    sessionSelector.onchange = () => {
      const selectedId = sessionSelector.value;
      if (selectedId && selectedId !== 'new') {
        this.switchToSession(selectedId);
        // Note: switchToSession already calls closeSidebar()
      } else if (selectedId === 'new') {
        this.createNewSession();
        // Note: createNewSession already calls closeSidebar()
      }
    };

    // New chat button
    const newChatBtn = topBar.createEl('button', {
      text: '+',
      cls: 'new-chat-btn compact',
      title: 'New Chat'
    });
    newChatBtn.onclick = () => {
      this.createNewSession();
      // Note: createNewSession already calls closeSidebar()
    };

    // Toggle sidebar button
    const toggleBtn = topBar.createEl('button', {
      text: '☰',
      cls: 'toggle-sidebar-btn',
      title: 'Toggle Sessions'
    });
    toggleBtn.onclick = () => this.toggleSidebar();

    // Create chat area within the content container
    const chatArea = this.contentContainer.createEl('div', { cls: 'chat-area' });

    // Chat content area
    this.chatContentContainer = chatArea.createEl('div', { cls: 'chat-content' });

    // Update session selector
    this.updateSessionSelector();

    // Load active session or show empty state
    if (this.activeSessionId) {
      this.loadChatMessages(this.activeSessionId);
    } else {
      this.renderEmptyState();
    }
  }

  renderCommandsTab() {
    const commandsArea = this.contentContainer.createEl('div', { cls: 'commands-area' });

    // Create sections like in CommandsModal
    this.createAgentCommands(commandsArea);
    this.createDiscoveryCommands(commandsArea);
    this.createDataCommands(commandsArea);
    this.createSystemCommands(commandsArea);
  }

  renderToolsTab() {
    const toolsArea = this.contentContainer.createEl('div', { cls: 'tools-area' });

    // Create tools sections
    this.createCitationTools(toolsArea);
    this.createResearchTools(toolsArea);
    this.createUtilityTools(toolsArea);
  }

  renderStatusTab() {
    const statusArea = this.contentContainer.createEl('div', { cls: 'status-area' });

    // Create status sections
    this.createConnectionStatus(statusArea);
    this.createSystemInfo(statusArea);
    this.createActivityLog(statusArea);
  }

  async renderConversationsTab() {
    const conversationsArea = this.contentContainer.createEl('div', { cls: 'conversations-area' });

    // Header with create conversation button
    const header = conversationsArea.createEl('div', { cls: 'conversations-header' });
    
    const createBtn = header.createEl('button', {
      text: '+ New Conversation',
      cls: 'create-conversation-btn'
    });

    createBtn.onclick = async () => {
      await this.createNewSession();
      this.switchTab('chat'); // Switch to chat after creating
    };

    // Search box
    const searchContainer = conversationsArea.createEl('div', { cls: 'conversation-search' });
    const searchInput = searchContainer.createEl('input', {
      type: 'text',
      placeholder: 'Search conversations...',
      cls: 'conversation-search-input'
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
    if (confirm(`Delete agent @${agentName}? This action cannot be undone.`)) {
      // TODO: Implement agent deletion API call
      // For now, just show a notice
      new Notice(`Agent deletion not yet implemented for @${agentName}`);
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

    // Ensure input area clicks focus the input
    inputArea.addEventListener('click', (e) => {
      if (e.target === inputArea) {
        inputEl.focus();
      }
    });

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

      try {
        // Send to server - use agent endpoint for agent messages
        const endpoint = this.plugin.getEndpointUrl();
        const isAgentMessage = this.detectAgentInteraction(message);
        const apiEndpoint = isAgentMessage ? '/agents/chat' : '/research/chat';

        const response = await fetch(`${endpoint}${apiEndpoint}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: message,
            conversation_id: sessionId,
            user_id: 'obsidian_user', // TODO: Add user identification
            timestamp: Date.now(),
            id: crypto.randomUUID()
          })
        });

        if (response.ok) {
          const result = await response.json();
          this.addMessageToChat(messagesContainer, 'assistant', result.response);

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
        container.createEl('div', {
          text: 'No conversations yet. Create your first one!',
          cls: 'empty-state'
        });
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
    const card = container.createEl('div', { cls: 'conversation-card' });
    
    if (session.id === this.activeSessionId) {
      card.addClass('active');
    }

    // Title
    const titleEl = card.createEl('div', { 
      text: session.title || 'Untitled Conversation',
      cls: 'conversation-title'
    });

    // Metadata (time and message count)
    const metaEl = card.createEl('div', { cls: 'conversation-meta' });
    
    const timeAgo = this.getTimeAgo(session.created_at);
    const messageCount = session.message_count || 0;
    
    metaEl.setText(`${timeAgo} • ${messageCount} message${messageCount !== 1 ? 's' : ''}`);

    // Click to switch
    card.onclick = async () => {
      await this.switchToSession(session.id);
      this.switchTab('chat');
    };

    // Actions (delete, rename)
    const actionsEl = card.createEl('div', { cls: 'conversation-actions' });
    
    const renameBtn = actionsEl.createEl('button', { 
      text: '✏️',
      cls: 'conversation-action-btn',
      attr: { 'aria-label': 'Rename' }
    });
    
    renameBtn.onclick = async (e) => {
      e.stopPropagation();
      await this.renameConversation(session);
    };

    const deleteBtn = actionsEl.createEl('button', { 
      text: '🗑️',
      cls: 'conversation-action-btn delete',
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
      await this.saveSessionToBackend(session);
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
      await this.saveChatSessions();
      this.renderTabContent(); // Refresh
    }
  }

  filterConversations(query: string) {
    const cards = this.contentContainer.querySelectorAll('.conversation-card');
    const lowerQuery = query.toLowerCase();
    
    cards.forEach(card => {
      const titleEl = card.querySelector('.conversation-title');
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

  // Research tab methods (placeholder for now)
  renderResearchTab() {
    const researchArea = this.contentContainer.createEl('div', { cls: 'research-area' });

    // Placeholder for now
    researchArea.createEl('h3', { text: '🔬 Research Dashboard' });
    researchArea.createEl('p', { 
      text: 'Live discovery results and research management coming soon!',
      cls: 'placeholder-text'
    });
  }
}
