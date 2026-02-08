import { App, Modal, Notice, Menu, SuggestModal, MarkdownRenderer, MarkdownView } from 'obsidian';
import { ChatSession, ChatMessage } from '../types';
import type ThothPlugin from '../../main';
import { ResearchTabComponent } from '../components/research-tab';
import { SettingsTabComponent } from '../components/settings-tab';
import * as smd from 'streaming-markdown';
import { getRandomThinkingPhrase, getToolStatusMessage } from '../utils/thinking-messages';

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

  // Pagination tracking
  private messageCache: Map<string, any[]> = new Map();
  private hasMoreMessages: Map<string, boolean> = new Map();
  private oldestMessageId: Map<string, string> = new Map();

  constructor(app: App, plugin: ThothPlugin) {
    super(app);
    this.plugin = plugin;
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

      const response = await fetch(url, {
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

    // Ensure default conversation exists and get its ID
    const defaultConvId = await this.getOrCreateDefaultConversation();

    // Load active session or fall back to default
    if (this.plugin.settings.activeChatSessionId) {
      // Try to load the previously active session
      const sessionExists = this.chatSessions.find(s => s.id === this.plugin.settings.activeChatSessionId);
      if (sessionExists) {
        await this.switchToSession(this.plugin.settings.activeChatSessionId);
      } else {
        // Previous session doesn't exist, use default conversation
        await this.switchToSession(defaultConvId);
      }
    } else {
      // No active session stored, use default conversation
      await this.switchToSession(defaultConvId);
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
      // Mobile: Full-screen modal with safe area insets for iOS
      modalEl.addClass('thoth-mobile-modal');

      // CRITICAL: Also get the modal container (Obsidian's wrapper)
      const modalContainer = modalEl.parentElement;
      if (modalContainer && modalContainer.classList.contains('modal-container')) {
        // Style the container too
        modalContainer.style.position = 'fixed';
        modalContainer.style.top = '0';
        modalContainer.style.left = '0';
        modalContainer.style.right = '0';
        modalContainer.style.bottom = '0';
        modalContainer.style.width = '100vw';
        modalContainer.style.height = '100vh';
        modalContainer.style.maxHeight = '100vh';
        modalContainer.style.overflow = 'hidden';
      }

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
      // Safe area insets handled in CSS for close button and content
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
      // No extra top padding needed - parent modal handles safe area
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

    // Clean up keyboard listeners
    if (this.keyboardCleanup) {
      this.keyboardCleanup();
    }
  }

  // Store cleanup function for keyboard listeners
  private keyboardCleanup: (() => void) | null = null;

  /**
   * Setup mobile keyboard handling using Focus/Blur events
   * Tries to use native Capacitor keyboard events if available, falls back to measurement
   */
  setupMobileKeyboardHandling(
    inputEl: HTMLTextAreaElement,
    messagesContainer: HTMLElement,
    inputArea: HTMLElement
  ) {
    console.log('[MultiChatModal] 🚀 Setting up mobile keyboard handling...');

    const modalContent = this.modalEl;

    // Get Obsidian's modal container
    const modalContainer = modalContent.parentElement;
    const hasContainer = modalContainer && modalContainer.classList.contains('modal-container');

    let isKeyboardVisible = false;
    let nativeKeyboardHeight: number | null = null;

    // Check for Capacitor Keyboard plugin
    const capacitorKeyboard = (window as any).Capacitor?.Plugins?.Keyboard;
    if (capacitorKeyboard) {
      console.log('[MultiChatModal] ✅ Capacitor Keyboard plugin detected!');

      // Listen to native keyboard events
      capacitorKeyboard.addListener('keyboardWillShow', (info: any) => {
        nativeKeyboardHeight = info.keyboardHeight;
        console.log('[MultiChatModal] 🎹 Native keyboard height:', nativeKeyboardHeight);
      });

      capacitorKeyboard.addListener('keyboardWillHide', () => {
        nativeKeyboardHeight = null;
        console.log('[MultiChatModal] 🎹 Native keyboard hidden');
      });
    } else {
      console.log('[MultiChatModal] ⚠️ No Capacitor Keyboard plugin - using fallback');
    }

    // Check for CSS variable approach
    const checkCSSVariable = () => {
      const keyboardOffset = getComputedStyle(document.documentElement)
        .getPropertyValue('--keyboard-offset');
      if (keyboardOffset && keyboardOffset !== '0px') {
        console.log('[MultiChatModal] 📐 CSS --keyboard-offset detected:', keyboardOffset);
        return parseInt(keyboardOffset);
      }
      return null;
    };

    const handleInputFocus = () => {
      if (isKeyboardVisible) return; // Already handled

      // Delay to let keyboard animation start
      setTimeout(() => {
        isKeyboardVisible = true;

        // Try multiple detection methods in order of reliability:
        const windowHeight = window.innerHeight;
        let modalHeight: number;
        let detectionMethod = 'unknown';

        // Method 1: Native Capacitor keyboard height (most accurate)
        if (nativeKeyboardHeight !== null) {
          modalHeight = Math.round(windowHeight - nativeKeyboardHeight);
          detectionMethod = 'capacitor-native';
          console.log('[MultiChatModal] ⌨️ Using native keyboard height:', {
            windowHeight,
            nativeKeyboardHeight,
            modalHeight
          });
        }
        // Method 2: CSS variable from Obsidian/theme
        else {
          const cssKeyboardOffset = checkCSSVariable();
          if (cssKeyboardOffset !== null) {
            modalHeight = Math.round(windowHeight - cssKeyboardOffset);
            detectionMethod = 'css-variable';
            console.log('[MultiChatModal] ⌨️ Using CSS keyboard offset:', {
              windowHeight,
              cssKeyboardOffset,
              modalHeight
            });
          }
          // Method 3: Visual Viewport API
          else {
            const visualViewport = window.visualViewport;
            const vpHeight = visualViewport ? visualViewport.height : windowHeight;
            const inputRect = inputEl.getBoundingClientRect();
            const inputBottom = inputRect.bottom;

            if (inputBottom > vpHeight - 50) {
              // Input is obscured - use viewport height
              modalHeight = Math.max(300, vpHeight);
              detectionMethod = 'viewport-measurement';
              console.log('[MultiChatModal] ⌨️ Using viewport measurement:', {
                windowHeight,
                vpHeight,
                inputBottom,
                modalHeight
              });
            }
            // Method 4: Fallback estimate (25%)
            else {
              const estimatedKeyboardHeight = windowHeight * 0.25;
              modalHeight = Math.round(windowHeight - estimatedKeyboardHeight);
              detectionMethod = 'fallback-estimate';
              console.log('[MultiChatModal] ⌨️ Using 25% estimate:', {
                windowHeight,
                estimatedKeyboardHeight,
                modalHeight
              });
            }
          }
        }

        // Add class for CSS styling
        modalContent.addClass('keyboard-visible');

        // Adjust Obsidian's container
        if (hasContainer && modalContainer) {
          modalContainer.style.height = `${modalHeight}px`;
          modalContainer.style.maxHeight = `${modalHeight}px`;
        }

        // Adjust modal
        modalContent.style.height = `${modalHeight}px`;
        modalContent.style.maxHeight = `${modalHeight}px`;

        // Adjust messages container to fit within available space
        const inputAreaHeight = inputArea.offsetHeight || 80;
        const messagesMaxHeight = modalHeight - inputAreaHeight - 120;
        messagesContainer.style.maxHeight = `${messagesMaxHeight}px`;
        messagesContainer.style.flexShrink = '1';
        messagesContainer.style.overflowY = 'auto';

        // Force browser to recalculate layout
        if (hasContainer && modalContainer) {
          modalContainer.offsetHeight;
        }
        modalContent.offsetHeight;
        messagesContainer.offsetHeight;

        // Scroll to bottom and ensure input is visible
        this.scrollToBottom(messagesContainer, true);
        setTimeout(() => {
          inputEl.scrollIntoView({ behavior: 'smooth', block: 'end' });
        }, 50);
      }, 150); // Wait for keyboard animation to start
    };

    const handleInputBlur = () => {
      if (!isKeyboardVisible) return; // Already handled

      // Small delay to handle case where user taps between inputs
      setTimeout(() => {
        // Check if another input got focus
        if (document.activeElement === inputEl) return;

        isKeyboardVisible = false;
        console.log('[MultiChatModal] ✅ Keyboard hidden - restoring modal size');

        // Remove class
        modalContent.removeClass('keyboard-visible');

        // Restore full height
        if (hasContainer && modalContainer) {
          modalContainer.style.height = '100vh';
          modalContainer.style.maxHeight = '100vh';
        }

        modalContent.style.height = '100vh';
        modalContent.style.maxHeight = '100vh';

        // Reset messages container
        messagesContainer.style.maxHeight = '';
        messagesContainer.style.flexShrink = '';
        messagesContainer.style.overflowY = '';
      }, 100);
    };

    // Add event listeners
    inputEl.addEventListener('focus', handleInputFocus);
    inputEl.addEventListener('blur', handleInputBlur);

    // Store cleanup function
    this.keyboardCleanup = () => {
      console.log('[MultiChatModal] 🧹 Cleaning up keyboard handlers');

      inputEl.removeEventListener('focus', handleInputFocus);
      inputEl.removeEventListener('blur', handleInputBlur);

      // Restore container and modal height
      if (hasContainer && modalContainer) {
        modalContainer.style.height = '';
        modalContainer.style.maxHeight = '';
      }

      modalContent.style.height = '';
      modalContent.style.maxHeight = '';

      messagesContainer.style.maxHeight = '';
      messagesContainer.style.flexShrink = '';
      messagesContainer.style.overflowY = '';
      modalContent.removeClass('keyboard-visible');
    };
  }

  /**
   * Fallback keyboard handling for devices without Visual Viewport API
   * Uses focus/blur events and fixed height adjustments
   */
  setupFallbackKeyboardHandling(
    inputEl: HTMLTextAreaElement,
    messagesContainer: HTMLElement,
    inputArea: HTMLElement,
    debugPanel: HTMLElement,
    addDebugLine: (text: string) => void
  ) {
    console.log('[MultiChatModal] 📱 Using fallback keyboard handling');
    addDebugLine('📱 Using FALLBACK method');
    const modalContent = this.modalEl;
    const modalContainer = modalContent.parentElement;

    const handleFocus = () => {
      console.log('[MultiChatModal] ⌨️ Fallback: Keyboard detected (focus)');
      addDebugLine('⌨️ FALLBACK: Keyboard shown (focus)');
      modalContent.addClass('keyboard-visible');

      // Use a fixed percentage for mobile
      const screenHeight = window.innerHeight;
      const keyboardHeight = screenHeight * 0.4; // Assume keyboard takes 40% of screen
      const availableHeight = screenHeight - keyboardHeight;

      // CRITICAL FIX: Adjust BOTH modal container and modal height
      if (modalContainer) {
        modalContainer.style.height = `${availableHeight}px`;
        modalContainer.style.maxHeight = `${availableHeight}px`;
        addDebugLine(`Container: ${availableHeight}px`);
      }

      modalContent.style.height = `${availableHeight}px`;
      modalContent.style.maxHeight = `${availableHeight}px`;

      addDebugLine(`Modal height: ${availableHeight}px`);

      const messagesHeight = availableHeight * 0.7; // Use 70% of available height for messages
      messagesContainer.style.maxHeight = `${messagesHeight}px`;
      messagesContainer.style.flexShrink = '1';
      messagesContainer.style.overflowY = 'auto';

      addDebugLine(`Messages: ${messagesHeight}px`);

      // Force layout recalculation
      modalContent.offsetHeight;

      // Scroll to bottom
      setTimeout(() => {
        this.scrollToBottom(messagesContainer, true);
        inputEl.scrollIntoView({ behavior: 'smooth', block: 'end' });
      }, 100);
    };

    const handleBlur = () => {
      console.log('[MultiChatModal] 👋 Fallback: Keyboard hidden (blur)');
      addDebugLine('👋 FALLBACK: Keyboard hidden (blur)');
      setTimeout(() => {
        modalContent.removeClass('keyboard-visible');

        // Restore modal AND container height
        if (modalContainer) {
          modalContainer.style.height = '100vh';
          modalContainer.style.maxHeight = '100vh';
        }
        modalContent.style.height = '100vh';
        modalContent.style.maxHeight = '100vh';

        messagesContainer.style.maxHeight = '';
        messagesContainer.style.flexShrink = '';
        messagesContainer.style.overflowY = '';
      }, 100);
    };

    inputEl.addEventListener('focus', handleFocus);
    inputEl.addEventListener('blur', handleBlur);

    addDebugLine('✅ Fallback listeners attached');

    this.keyboardCleanup = () => {
      console.log('[MultiChatModal] 🧹 Cleaning up fallback handlers');
      inputEl.removeEventListener('focus', handleFocus);
      inputEl.removeEventListener('blur', handleBlur);

      // Restore modal height
      modalContent.style.height = '';
      modalContent.style.maxHeight = '';

      messagesContainer.style.maxHeight = '';
      messagesContainer.style.flexShrink = '';
      messagesContainer.style.overflowY = '';
      modalContent.removeClass('keyboard-visible');

      // Remove debug panel
      if (debugPanel.parentNode) {
        debugPanel.parentNode.removeChild(debugPanel);
      }
    };
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

  async switchTab(tabId: string) {
    // Update tab buttons
    this.tabContainer.querySelectorAll('.thoth-tab-button').forEach((btn, index) => {
      if (index === ['chat', 'conversations', 'research', 'settings'].indexOf(tabId)) {
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
    const lettaEndpoint = this.plugin.getLettaEndpointUrl(); // Chat uses Letta
    const isConnected = this.plugin.isAgentRunning || this.plugin.settings.remoteMode;
    const mode = this.plugin.settings.remoteMode ? 'Remote' : 'Local';

    const details = `
Connection Status: ${isConnected ? 'Connected' : 'Disconnected'}
Mode: ${mode}
Chat Endpoint: ${lettaEndpoint}

${isConnected ? '✓ Ready to chat with Letta' : '⚠ Start the Letta server to begin'}
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

      // Fetch available agents from Letta
      // Note: Letta API requires trailing slash on collection endpoints
      // Use view=basic to avoid fetching full memory blocks (reduces response from 30MB to ~100KB)
      const endpoint = this.plugin.getLettaEndpointUrl();
      const response = await fetch(`${endpoint}/v1/agents/?view=basic`);

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
        const endpoint = this.plugin.getLettaEndpointUrl(); // Use Letta endpoint for chat
        // Note: NO trailing slash for DELETE - Letta API returns 405 with trailing slash
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

      .session-title-container {
        display: flex;
        align-items: center;
        gap: 4px;
      }

      .default-badge {
        display: inline-block;
        font-size: 10px;
        opacity: 0.8;
        flex-shrink: 0;
      }

      .session-item.default {
        border-left: 3px solid var(--interactive-accent);
        padding-left: 5px;
      }

      .thoth-conversation-card.default {
        border-left: 3px solid var(--interactive-accent);
      }

      .thoth-card-title .default-badge {
        color: var(--interactive-accent);
        font-size: 14px;
        margin-left: 4px;
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

      /* Mobile keyboard handling - ensure proper layout adjustment */
      @media (max-width: 768px) {
        .thoth-mobile-modal .multi-chat-container.compact {
          /* Ensure full height utilization */
          height: 100vh;
          max-height: 100vh;
        }

        .thoth-mobile-modal .chat-content {
          /* Allow content to flex and adjust */
          flex: 1;
          min-height: 0;
          display: flex;
          flex-direction: column;
        }

        .thoth-mobile-modal .chat-messages {
          /* Messages container flexes to available space */
          flex: 1;
          min-height: 0;
          overflow-y: auto;
          -webkit-overflow-scrolling: touch;
        }

        .thoth-mobile-modal .chat-input-area {
          /* Input area stays at bottom and doesn't shrink */
          flex-shrink: 0;
          position: relative;
          padding: 12px 16px;
          background: var(--background-primary);
          border-top: 1px solid var(--background-modifier-border);
        }

        /* When keyboard is visible, adjust layout */
        .thoth-mobile-modal.keyboard-visible .chat-content {
          /* Smooth transition when keyboard appears */
          transition: all 0.3s ease-in-out;
        }

        .thoth-mobile-modal.keyboard-visible .chat-messages {
          /* Allow messages to shrink when keyboard appears */
          transition: max-height 0.3s ease-in-out;
        }

        .thoth-mobile-modal.keyboard-visible .chat-input-area {
          /* Keep input visible and at bottom */
          position: sticky;
          bottom: 0;
          z-index: 100;
          box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.15);
        }
      }
    `;
    document.head.appendChild(style);
  }

  async loadChatSessions() {
    try {
      const endpoint = this.plugin.getLettaEndpointUrl(); // Use Letta endpoint for chat
      // Get conversations for the default agent
      // Note: Use trailing slash to avoid nginx redirect that duplicates query params
      const agentId = await this.getOrCreateDefaultAgent();
      const response = await this.fetchWithTimeout(`${endpoint}/v1/conversations/?agent_id=${agentId}&limit=50`);

      if (response.ok) {
        const conversations = await response.json();

        // Get default conversation ID to mark it in metadata
        const defaultConvId = await this.getOrCreateDefaultConversation();

        // Map Letta conversations to session format with all required ChatSession properties
        this.chatSessions = conversations.map((conv: any): ChatSession => ({
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

        // Sort to ensure default conversation is first in the list
        this.chatSessions.sort((a, b) => {
          if (a.metadata?.is_default) return -1;
          if (b.metadata?.is_default) return 1;
          // Sort others by updated_at (most recent first)
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
    // Return cached agent ID from settings (persists across sessions)
    if (this.plugin.settings.lettaAgentId) {
      console.log('[MultiChatModal] Using cached agent ID:', this.plugin.settings.lettaAgentId);
      return this.plugin.settings.lettaAgentId;
    }

    console.log('[MultiChatModal] No cached agent ID, fetching from server...');

    try {
      const endpoint = this.plugin.getLettaEndpointUrl();
      // Get the main Thoth orchestrator agent (auto-created by backend on startup)
      // Note: Letta API requires trailing slash on collection endpoints
      // Use view=basic to avoid fetching full memory blocks (30MB+ with all agents!)
      const listResponse = await this.fetchWithTimeout(`${endpoint}/v1/agents/?view=basic`);
      if (listResponse.ok) {
        const agents = await listResponse.json();
        console.log('[MultiChatModal] Found agents:', agents.map((a: any) => a.name));

        // The main orchestrator is named "thoth_main_orchestrator"
        const thothAgent = agents.find((a: any) => a.name === 'thoth_main_orchestrator');

        if (thothAgent) {
          // Cache in settings for future use
          this.plugin.settings.lettaAgentId = thothAgent.id;
          await this.plugin.saveSettings();
          console.log('[MultiChatModal] Cached agent ID for future use:', thothAgent.id);
          return thothAgent.id;
        }

        // If not found, log all available agent names to help debug
        console.error('[MultiChatModal] thoth_main_orchestrator not found. Available agents:', agents.map((a: any) => a.name));
      }

      // Agent not found - backend may not have started properly
      throw new Error('Thoth orchestrator agent not found. Please ensure the Thoth backend is running and has initialized agents.');
    } catch (error) {
      console.error('Failed to get Thoth agent:', error);
      throw error;
    }
  }

  async getOrCreateDefaultConversation(): Promise<string> {
    const endpoint = this.plugin.getLettaEndpointUrl();
    const agentId = await this.getOrCreateDefaultAgent();

    console.log('[MultiChatModal] Getting or creating default conversation...');

    // Find or create a default conversation via list endpoint
    try {
      const listResponse = await this.fetchWithTimeout(
        `${endpoint}/v1/conversations/?agent_id=${agentId}&limit=50`
      );

      if (!listResponse.ok) {
        throw new Error('Failed to fetch conversations');
      }

      const conversations = await listResponse.json();
      console.log('[MultiChatModal] Found conversations:', conversations.length);

      // Look for existing default (by title or oldest)
      let defaultConv = conversations.find((c: any) =>
        c.summary?.toLowerCase().includes('default') ||
        c.summary === 'Main Conversation'
      );

      if (defaultConv) {
        console.log('[MultiChatModal] Found existing default conversation by title:', defaultConv.id);
        return defaultConv.id;
      }

      if (conversations.length > 0) {
        // Use oldest conversation as default
        const sorted = [...conversations].sort((a: any, b: any) =>
          new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
        );
        defaultConv = sorted[0];
        console.log('[MultiChatModal] Using oldest conversation as default:', defaultConv.id);
        return defaultConv.id;
      }

      // No conversations exist, create new default conversation
      console.log('[MultiChatModal] No conversations exist, creating default...');
      const createResponse = await this.fetchWithTimeout(
        `${endpoint}/v1/conversations/?agent_id=${agentId}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ summary: 'Default Conversation' })
        }
      );

      if (!createResponse.ok) {
        throw new Error('Failed to create default conversation');
      }

      defaultConv = await createResponse.json();
      console.log('[MultiChatModal] Created new default conversation:', defaultConv.id);
      return defaultConv.id;

    } catch (error) {
      console.error('[MultiChatModal] Error in getOrCreateDefaultConversation:', error);
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
          text: '✏️',
          cls: 'session-action-btn',
          title: 'Rename session'
        });
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
          titleContainer.createEl('span', {
            text: '⭐',
            cls: 'default-badge',
            attr: { 'title': 'Default conversation' }
          });
        }

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
      // Generate better default title with timestamp
      let sessionTitle = title;
      if (!sessionTitle) {
        const now = new Date();
        const timeStr = now.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
        sessionTitle = `New Chat - ${timeStr}`;
      }

      const endpoint = this.plugin.getLettaEndpointUrl(); // Use Letta endpoint for chat
      const agentId = await this.getOrCreateDefaultAgent();

      // Note: Letta API expects agent_id as query param, with trailing slash to avoid nginx redirect
      const response = await fetch(`${endpoint}/v1/conversations/?agent_id=${agentId}`, {
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
      const endpoint = this.plugin.getLettaEndpointUrl();

      // Build URL with pagination support
      // Use desc order to get NEWEST messages first (most recent 50)
      let url = `${endpoint}/v1/conversations/${sessionId}/messages?limit=50&order=desc`;

      // If loading earlier messages, use cursor-based pagination
      if (loadEarlier && this.oldestMessageId.has(sessionId)) {
        const oldestId = this.oldestMessageId.get(sessionId);
        url += `&before=${oldestId}`;
      }

      const response = await fetch(url);

      if (response.ok) {
        const newMessages = await response.json();

        console.log(`[MultiChatModal] Loaded ${newMessages.length} messages for session ${sessionId}`, {
          loadEarlier,
          messageTypes: newMessages.map((m: any) => m.message_type || m.type).filter((t: any, i: number, arr: any[]) => arr.indexOf(t) === i)
        });

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
        this.hasMoreMessages.set(sessionId, newMessages.length >= 50);

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

    /**
     * Helper function to extract content from message.
     * Handles both string content and array of content parts (per Letta API).
     *
     * @param msg - The message object
     * @returns The extracted text content
     */
    const extractContent = (msg: any): string => {
      const content = msg.text || msg.content;
      if (Array.isArray(content)) {
        // Handle array of content parts (e.g., [{type: 'text', text: '...'}])
        return content
          .filter(part => part.type === 'text' || part.text)
          .map(part => part.text)
          .join('');
      }
      return content || '';
    };

    // Filter messages to show only user and assistant messages
    // Exclude system, reasoning, tool_call, and tool_return messages
    const chatMessages = messages.filter(msg => {
      // Check message_type field (Letta's primary message type)
      const messageType = msg.message_type || msg.type;
      if (messageType === 'user_message' ||
          messageType === 'assistant_message') {
        return true;
      }

      // Fallback to role field for backward compatibility
      const role = msg.role;
      if (role === 'user' || role === 'assistant') {
        return true;
      }

      return false;
    })
    // Sort by date to ensure chronological order (oldest first)
    // This provides a fallback in case the API order changes
    .sort((a, b) => {
      const dateA = new Date(a.date || a.created_at || 0).getTime();
      const dateB = new Date(b.date || b.created_at || 0).getTime();
      return dateA - dateB;
    });

    console.log(`[MultiChatModal] Rendering ${chatMessages.length} chat messages from ${messages.length} total messages`);

    // Load existing messages or show empty state
    if (chatMessages.length === 0) {
      this.createEmptyState(
        messagesContainer,
        '💬',
        'Start a conversation',
        'Ask me anything about your research, papers, or knowledge base. I can help you discover papers, analyze citations, and more.',
        'Try: "Find recent papers on transformers"'
      );
    } else {
      // Render all messages with markdown support (only user and assistant)
      await Promise.all(
        chatMessages.map(async (msg) => {
          const messageType = msg.message_type || msg.type;

          // Only render user and assistant messages
          const role = messageType === 'user_message' ? 'user'
                     : messageType === 'assistant_message' ? 'assistant'
                     : msg.role;
          const content = extractContent(msg);
          await this.addMessageToChat(messagesContainer, role, content);
        })
      );
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
      await this.addMessageToChat(messagesContainer, 'user', message);
      inputEl.value = '';

      // Auto-resize input back to minimum height
      inputEl.style.height = '36px';

      // Disable send button
      sendBtn.disabled = true;
      sendBtn.textContent = 'Sending...';

      // Add thinking indicator
      const thinkingMsg = this.addThinkingIndicator(messagesContainer);

      try {
        // Send to Letta conversation with streaming enabled
        const endpoint = this.plugin.getLettaEndpointUrl();
        const response = await fetch(`${endpoint}/v1/conversations/${sessionId}/messages`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            input: message,
            streaming: true,  // Enable SSE streaming for real-time token display
            stream_tokens: true  // Stream individual tokens
          })
        });

        if (response.ok && response.body) {
          // Don't remove thinking indicator yet - wait for first content token

          let assistantMessageEl: HTMLElement | null = null;
          let contentEl: HTMLElement | null = null;
          let streamingRenderer: StreamingMarkdownRenderer | null = null;
          let thinkingRemoved = false; // Track if we've removed the thinking indicator
          let accumulatedContent = ''; // Accumulate raw markdown for copy button

          // Read SSE stream
          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let buffer = '';

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            // Decode chunk and add to buffer
            buffer += decoder.decode(value, { stream: true });

            // Process complete SSE messages (ending with \n\n)
            const lines = buffer.split('\n\n');
            buffer = lines.pop() || ''; // Keep incomplete message in buffer

            for (const block of lines) {
              // Extract the data line from SSE blocks (may have event: prefix)
              const dataLine = block.split('\n').find(l => l.trim().startsWith('data:'));
              if (!dataLine) continue;

              const jsonStr = dataLine.replace(/^data:\s*/, '').trim();
              if (!jsonStr || jsonStr === '[DONE]') continue;

              try {
                const msg = JSON.parse(jsonStr);
                const messageType = msg.message_type;
                const messageId = msg.id;

                // Handle error_message from Letta (e.g. LLM errors)
                if (messageType === 'error_message') {
                  const errorDetail = msg.detail || msg.message || 'Unknown agent error';
                  console.error('[MultiChatModal] Agent error:', errorDetail);
                  throw new Error(errorDetail);
                }

                // Handle stop_reason (may indicate errors)
                if (messageType === 'stop_reason' && msg.stop_reason === 'llm_api_error') {
                  console.error('[MultiChatModal] LLM API error reported');
                  // Don't throw yet - wait for the error_message with details
                }

                // Handle reasoning_message
                if (messageType === 'reasoning_message') {
                  // Update status indicator - don't create reasoning block during streaming
                  if (!thinkingRemoved) {
                    const phrase = getRandomThinkingPhrase('thinking');
                    this.updateStatusIndicator(thinkingMsg, `${phrase}...`, '💭');
                  }
                }

                // Handle tool_call_message
                else if (messageType === 'tool_call_message') {
                  // Update status indicator - don't create tool call card during streaming
                  if (!thinkingRemoved) {
                    const toolName = msg.tool_call?.name || 'tool';
                    const statusMsg = getToolStatusMessage(toolName);
                    this.updateStatusIndicator(thinkingMsg, `${statusMsg}...`, '🔧');
                  }
                }

                // Handle tool_return_message
                else if (messageType === 'tool_return_message') {
                  // Update status indicator - don't create tool return card during streaming
                  if (!thinkingRemoved) {
                    const phrase = getRandomThinkingPhrase('processing');
                    this.updateStatusIndicator(thinkingMsg, `${phrase} results...`, '⚙️');
                  }
                }

                // Handle assistant_message (with streaming)
                else if (messageType === 'assistant_message') {
                  const delta = msg.content || msg.text || '';

                  if (delta && messageId) {
                    // Remove thinking indicator on first content token
                    if (!thinkingRemoved) {
                      thinkingMsg.remove();
                      thinkingRemoved = true;
                    }

                    // Create assistant message element on first chunk
                    if (!assistantMessageEl) {
                      assistantMessageEl = messagesContainer.createEl('div', {
                        cls: 'chat-message assistant'
                      });
                      assistantMessageEl.createEl('div', {
                        text: 'Assistant',
                        cls: 'message-role'
                      });
                      contentEl = assistantMessageEl.createEl('div', {
                        cls: 'message-content'
                      });

                      // Initialize streaming markdown renderer
                      streamingRenderer = new StreamingMarkdownRenderer(contentEl);
                    }

                    // Accumulate raw content for copy button
                    accumulatedContent += delta;

                    // Write delta directly to streaming renderer
                    if (streamingRenderer) {
                      streamingRenderer.write(delta);
                      this.scrollToBottom(messagesContainer, true);
                    }
                  }
                }
              } catch (e) {
                // Re-throw agent errors so they display to the user
                if (e.message && !e.message.includes('Failed to parse')) {
                  throw e;
                }
                console.warn('[MultiChatModal] Failed to parse SSE message:', jsonStr.substring(0, 100));
              }
            }
          }

          // Ensure thinking indicator is removed if stream completed without content
          if (!thinkingRemoved) {
            thinkingMsg.remove();
            thinkingRemoved = true;
          }

          // End streaming and re-render with Obsidian's native markdown
          if (streamingRenderer) {
            streamingRenderer.end();

            // Re-render accumulated content with Obsidian's native MarkdownRenderer
            // which properly handles tables, callouts, and other complex markdown
            // that streaming-markdown doesn't fully support
            if (contentEl && accumulatedContent) {
              await this.renderMessageContent(accumulatedContent, contentEl);
            }

            // Add message actions (copy button) with accumulated content
            if (assistantMessageEl && accumulatedContent) {
              this.addMessageActions(assistantMessageEl, accumulatedContent);
            }

            this.scrollToBottom(messagesContainer, true);
          }

          // Update session list to reflect new message
          await this.loadChatSessions();
          this.renderSessionList();
        } else {
          // Add better error logging with response body
          const errorBody = await response.text();
          console.error(`[MultiChatModal] Message send failed: ${response.status}`, errorBody);
          throw new Error(`Failed to send message: ${response.status}`);
        }
      } catch (error) {
        console.error('Chat error:', error);
        // Remove thinking indicator
        thinkingMsg.remove();
        await this.addMessageToChat(messagesContainer, 'assistant', `Error: ${error.message}`);
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

    // Mobile keyboard handling
    if ((this.app as any).isMobile) {
      this.setupMobileKeyboardHandling(inputEl, messagesContainer, inputArea);
    }
  }

  async addMessageToChat(container: HTMLElement, role: string, content: string) {
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

    // Render markdown content
    await this.renderMessageContent(content, contentEl);

    // Add message actions (copy button) for assistant messages
    this.addMessageActions(messageEl, content);

    // Auto-scroll to new message with smooth behavior
    setTimeout(() => {
      this.scrollToBottom(container);
    }, 100);
  }

  async addReasoningMessage(container: HTMLElement, msg: any) {
    const reasoningEl = container.createEl('div', {
      cls: 'chat-message reasoning-block'
    });

    const header = reasoningEl.createEl('div', {
      cls: 'reasoning-header'
    });

    const icon = header.createEl('span', {
      cls: 'reasoning-icon',
      text: '💭'
    });

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

    header.createEl('span', {
      cls: 'tool-call-icon',
      text: '🔧'
    });

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

    header.createEl('span', {
      cls: 'tool-return-icon',
      text: '✅'
    });

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

    // Use InputModal instead of prompt() (Electron-compatible)
    const newTitle = await new Promise<string | null>((resolve) => {
      const modal = new (require('../modals/input-modal').InputModal)(
        (this.plugin as any).app,
        'Enter new session name:',
        resolve,
        session.title  // Default value
      );
      modal.open();
    });
    if (!newTitle || newTitle === session.title) return;

    try {
      const endpoint = this.plugin.getLettaEndpointUrl(); // Use Letta endpoint for chat
      // Note: NO trailing slash for PATCH - Letta API may have issues with trailing slashes
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

    // Use InputModal for confirmation instead of confirm() (Electron-compatible)
    const confirmed = await new Promise<boolean>((resolve) => {
      const modal = new (require('../modals/input-modal').InputModal)(
        (this.plugin as any).app,
        `Delete "${session.title}"? Type "DELETE" to confirm:`,
        (result: string | null) => resolve(result === 'DELETE')
      );
      modal.open();
    });
    if (!confirmed) return;

    try {
      const endpoint = this.plugin.getLettaEndpointUrl(); // Use Letta endpoint for chat
      // Note: NO trailing slash for DELETE - Letta API returns 405 with trailing slash
      const response = await fetch(`${endpoint}/v1/conversations/${sessionId}`, {
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
      titleEl.createEl('span', {
        text: ' ⭐',
        cls: 'default-badge',
        attr: { 'title': 'Default conversation' }
      });
    }

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

    // Delete button removed - Letta API 0.16.3 doesn't support deleting conversations
    // const deleteBtn = actionsEl.createEl('button', {
    //   text: '🗑️',
    //   cls: 'thoth-card-action delete',
    //   attr: { 'aria-label': 'Delete' }
    // });
    //
    // deleteBtn.onclick = async (e) => {
    //   e.stopPropagation();
    //   await this.deleteConversation(session);
    // };
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
      const endpoint = this.plugin.getLettaEndpointUrl();
      // Sync to Letta API - NO trailing slash for PATCH
      const response = await fetch(`${endpoint}/v1/conversations/${session.id}`, {
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

    const confirmed = confirm(`Delete conversation "${session.title || 'Untitled'}"?`);
    if (confirmed) {
      try {
      // Delete from server
      const endpoint = this.plugin.getLettaEndpointUrl();
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

  // Helper: Add dynamic status indicator
  addThinkingIndicator(container: HTMLElement): HTMLElement {
    const msg = container.createEl('div', { cls: 'message assistant thinking status-indicator-dynamic' });
    const content = msg.createEl('div', { cls: 'message-content' });
    const indicator = content.createEl('div', { cls: 'thinking-indicator' });
    indicator.createEl('span', { cls: 'dot' });
    indicator.createEl('span', { cls: 'dot' });
    indicator.createEl('span', { cls: 'dot' });
    const statusText = content.createEl('span', {
      text: 'Starting...',
      cls: 'status-text'
    });

    // Store reference to status text for updates
    (msg as any).__statusText = statusText;

    // Scroll to bottom
    container.scrollTop = container.scrollHeight;

    return msg;
  }

  // Helper: Update status indicator
  updateStatusIndicator(indicator: HTMLElement, status: string, icon?: string) {
    const statusText = (indicator as any).__statusText;
    if (statusText) {
      let displayText = status;
      if (icon) {
        displayText = `${icon} ${status}`;
      }
      statusText.textContent = displayText;
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
