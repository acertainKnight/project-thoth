import { App } from 'obsidian';
import { ThothSettings } from '../types';

/**
 * Tab configuration interface
 */
export interface TabConfig {
  id: string;
  title: string;
  icon?: string;
  content?: HTMLElement;
  onActivate?: () => void;
  onDeactivate?: () => void;
  isActive?: boolean;
}

/**
 * Tabbed interface state
 */
export interface TabbedInterfaceState {
  activeTabId: string;
  tabs: Map<string, TabConfig>;
  container?: HTMLElement;
  tabNavigation?: HTMLElement;
  contentContainer?: HTMLElement;
}

/**
 * Event callbacks for tab interactions
 */
export interface TabbedInterfaceCallbacks {
  onTabSwitch?: (fromTabId: string, toTabId: string) => void;
  onTabAdded?: (tabId: string) => void;
  onTabRemoved?: (tabId: string) => void;
  onStateChange?: (state: TabbedInterfaceState) => void;
}

/**
 * Tabbed interface implementation for VSCode-like settings experience
 */
export interface ITabbedInterface {
  addTab(config: TabConfig): void;
  removeTab(tabId: string): void;
  switchTab(tabId: string): void;
  getCurrentTab(): string;
  updateTabContent(tabId: string, content: HTMLElement): void;
  updateTabTitle(tabId: string, title: string): void;
  setTabActive(tabId: string, isActive: boolean): void;
  getTabConfig(tabId: string): TabConfig | undefined;
  getAllTabs(): TabConfig[];
  onTabSwitch(callback: (fromTabId: string, toTabId: string) => void): void;
  render(container: HTMLElement): void;
  restoreActiveTab(): string | null;
  cleanup(): void;
}

/**
 * TabbedInterface implementation with VSCode-like behavior
 */
export class TabbedInterface implements ITabbedInterface {
  private state: TabbedInterfaceState;
  private callbacks: TabbedInterfaceCallbacks = {};
  private app: App;

  constructor(app: App, initialTabId?: string) {
    this.app = app;
    this.state = {
      activeTabId: initialTabId || '',
      tabs: new Map(),
      container: undefined,
      tabNavigation: undefined,
      contentContainer: undefined
    };

    this.initializeStyles();
  }

  /**
   * Add a new tab to the interface
   */
  addTab(config: TabConfig): void {
    this.state.tabs.set(config.id, { ...config });

    // Set as active if it's the first tab or explicitly marked active
    if (this.state.tabs.size === 1 || config.isActive) {
      this.state.activeTabId = config.id;
    }

    // Re-render if already mounted
    if (this.state.container) {
      this.renderTabNavigation();
      this.renderActiveContent();
    }

    // Trigger callback
    if (this.callbacks.onTabAdded) {
      this.callbacks.onTabAdded(config.id);
    }
  }

  /**
   * Remove a tab from the interface
   */
  removeTab(tabId: string): void {
    if (!this.state.tabs.has(tabId)) return;

    this.state.tabs.delete(tabId);

    // If removing active tab, switch to first available tab
    if (this.state.activeTabId === tabId && this.state.tabs.size > 0) {
      const firstTabId = Array.from(this.state.tabs.keys())[0];
      this.switchTab(firstTabId);
    }

    // Re-render if already mounted
    if (this.state.container) {
      this.renderTabNavigation();
      this.renderActiveContent();
    }

    // Trigger callback
    if (this.callbacks.onTabRemoved) {
      this.callbacks.onTabRemoved(tabId);
    }
  }

  /**
   * Switch to a specific tab
   */
  switchTab(tabId: string): void {
    if (!this.state.tabs.has(tabId) || this.state.activeTabId === tabId) {
      return;
    }

    const previousTabId = this.state.activeTabId;
    const previousTab = this.state.tabs.get(previousTabId);
    const newTab = this.state.tabs.get(tabId);

    // Deactivate previous tab
    if (previousTab && previousTab.onDeactivate) {
      previousTab.onDeactivate();
    }

    // Update active tab
    this.state.activeTabId = tabId;

    // Activate new tab
    if (newTab && newTab.onActivate) {
      newTab.onActivate();
    }

    // Update UI
    this.updateTabButtonStates();
    this.renderActiveContent();

    // Trigger callbacks
    if (this.callbacks.onTabSwitch) {
      this.callbacks.onTabSwitch(previousTabId, tabId);
    }
    if (this.callbacks.onStateChange) {
      this.callbacks.onStateChange(this.state);
    }

    // Persist active tab preference
    this.persistActiveTab(tabId);
  }

  /**
   * Get currently active tab ID
   */
  getCurrentTab(): string {
    return this.state.activeTabId;
  }

  /**
   * Update content for a specific tab
   */
  updateTabContent(tabId: string, content: HTMLElement): void {
    const tab = this.state.tabs.get(tabId);
    if (!tab) return;

    tab.content = content;

    // Re-render if this is the active tab
    if (this.state.activeTabId === tabId && this.state.contentContainer) {
      this.renderActiveContent();
    }
  }

  /**
   * Update title for a specific tab
   */
  updateTabTitle(tabId: string, title: string): void {
    const tab = this.state.tabs.get(tabId);
    if (!tab) return;

    tab.title = title;

    // Update tab button if rendered
    if (this.state.tabNavigation) {
      const tabButton = this.state.tabNavigation.querySelector(`[data-tab-id="${tabId}"]`) as HTMLButtonElement;
      if (tabButton) {
        const titleEl = tabButton.querySelector('.thoth-tab-title') as HTMLElement;
        if (titleEl) {
          titleEl.textContent = title;
        }
      }
    }
  }

  /**
   * Set tab active state (for external control)
   */
  setTabActive(tabId: string, isActive: boolean): void {
    if (isActive) {
      this.switchTab(tabId);
    }
  }

  /**
   * Get tab configuration
   */
  getTabConfig(tabId: string): TabConfig | undefined {
    return this.state.tabs.get(tabId);
  }

  /**
   * Get all tabs
   */
  getAllTabs(): TabConfig[] {
    return Array.from(this.state.tabs.values());
  }

  /**
   * Set tab switch callback
   */
  onTabSwitch(callback: (fromTabId: string, toTabId: string) => void): void {
    this.callbacks.onTabSwitch = callback;
  }

  /**
   * Render the complete tabbed interface
   */
  render(container: HTMLElement): void {
    this.state.container = container;
    container.className = 'thoth-tabbed-interface';

    // Clear existing content
    container.empty();

    // Create tab navigation
    this.state.tabNavigation = container.createEl('div', { cls: 'thoth-tab-navigation' });
    this.renderTabNavigation();

    // Create content container
    this.state.contentContainer = container.createEl('div', { cls: 'thoth-tab-content-container' });
    this.renderActiveContent();

    // Set up keyboard navigation
    this.setupKeyboardNavigation();
  }

  /**
   * Render tab navigation buttons
   */
  private renderTabNavigation(): void {
    if (!this.state.tabNavigation) return;

    this.state.tabNavigation.empty();

    // Create tab buttons
    for (const [tabId, tab] of this.state.tabs) {
      const tabButton = this.state.tabNavigation.createEl('button', {
        cls: 'thoth-tab-button'
      });
      tabButton.dataset.tabId = tabId;

      // Tab icon (if provided)
      if (tab.icon) {
        tabButton.createEl('span', { text: tab.icon, cls: 'thoth-tab-icon' });
      }

      // Tab title
      tabButton.createEl('span', { text: tab.title, cls: 'thoth-tab-title' });

      // Set active state
      if (tabId === this.state.activeTabId) {
        tabButton.addClass('active');
      }

      // Click handler
      tabButton.addEventListener('click', () => {
        this.switchTab(tabId);
      });

      // Accessibility
      tabButton.setAttribute('role', 'tab');
      tabButton.setAttribute('aria-selected', (tabId === this.state.activeTabId).toString());
      tabButton.setAttribute('aria-controls', `thoth-tab-panel-${tabId}`);
      tabButton.setAttribute('id', `thoth-tab-${tabId}`);
    }

    // Accessibility for tab list
    this.state.tabNavigation.setAttribute('role', 'tablist');
    this.state.tabNavigation.setAttribute('aria-label', 'Settings view tabs');
  }

  /**
   * Render active tab content
   */
  private renderActiveContent(): void {
    if (!this.state.contentContainer || !this.state.activeTabId) return;

    this.state.contentContainer.empty();

    const activeTab = this.state.tabs.get(this.state.activeTabId);
    if (!activeTab || !activeTab.content) return;

    // Create tab panel
    const tabPanel = this.state.contentContainer.createEl('div', {
      cls: 'thoth-tab-panel'
    });
    tabPanel.setAttribute('role', 'tabpanel');
    tabPanel.setAttribute('aria-labelledby', `thoth-tab-${this.state.activeTabId}`);
    tabPanel.setAttribute('id', `thoth-tab-panel-${this.state.activeTabId}`);

    // Add content
    tabPanel.appendChild(activeTab.content);
  }

  /**
   * Update tab button states
   */
  private updateTabButtonStates(): void {
    if (!this.state.tabNavigation) return;

    const tabButtons = this.state.tabNavigation.querySelectorAll('.thoth-tab-button');
    tabButtons.forEach(button => {
      const tabId = (button as HTMLElement).dataset.tabId;
      const isActive = tabId === this.state.activeTabId;

      button.classList.toggle('active', isActive);
      button.setAttribute('aria-selected', isActive.toString());
    });
  }

  /**
   * Set up keyboard navigation for accessibility
   */
  private setupKeyboardNavigation(): void {
    if (!this.state.tabNavigation) return;

    this.state.tabNavigation.addEventListener('keydown', (event) => {
      const tabButtons = Array.from(this.state.tabNavigation!.querySelectorAll('.thoth-tab-button')) as HTMLButtonElement[];
      const currentIndex = tabButtons.findIndex(btn => btn.dataset.tabId === this.state.activeTabId);

      switch (event.key) {
        case 'ArrowLeft':
        case 'ArrowUp':
          event.preventDefault();
          const prevIndex = currentIndex > 0 ? currentIndex - 1 : tabButtons.length - 1;
          const prevTabId = tabButtons[prevIndex].dataset.tabId;
          if (prevTabId) {
            this.switchTab(prevTabId);
            tabButtons[prevIndex].focus();
          }
          break;

        case 'ArrowRight':
        case 'ArrowDown':
          event.preventDefault();
          const nextIndex = currentIndex < tabButtons.length - 1 ? currentIndex + 1 : 0;
          const nextTabId = tabButtons[nextIndex].dataset.tabId;
          if (nextTabId) {
            this.switchTab(nextTabId);
            tabButtons[nextIndex].focus();
          }
          break;

        case 'Home':
          event.preventDefault();
          const firstTabId = tabButtons[0].dataset.tabId;
          if (firstTabId) {
            this.switchTab(firstTabId);
            tabButtons[0].focus();
          }
          break;

        case 'End':
          event.preventDefault();
          const lastTabId = tabButtons[tabButtons.length - 1].dataset.tabId;
          if (lastTabId) {
            this.switchTab(lastTabId);
            tabButtons[tabButtons.length - 1].focus();
          }
          break;
      }
    });
  }

  /**
   * Persist active tab preference
   */
  private persistActiveTab(tabId: string): void {
    try {
      localStorage.setItem('thoth-active-settings-tab', tabId);
    } catch (error) {
      console.warn('Failed to persist active tab:', error);
    }
  }

  /**
   * Restore active tab preference
   */
  public restoreActiveTab(): string | null {
    try {
      return localStorage.getItem('thoth-active-settings-tab');
    } catch (error) {
      console.warn('Failed to restore active tab:', error);
      return null;
    }
  }

  /**
   * Clean up resources
   */
  cleanup(): void {
    // Clear event listeners and references
    this.callbacks = {};

    // Deactivate all tabs
    for (const [, tab] of this.state.tabs) {
      if (tab.onDeactivate) {
        tab.onDeactivate();
      }
    }

    // Clear state
    this.state.tabs.clear();
  }

  /**
   * Initialize tabbed interface styles
   */
  private initializeStyles(): void {
    if (document.getElementById('thoth-tabbed-interface-styles')) {
      return; // Styles already loaded
    }

    const style = document.createElement('style');
    style.id = 'thoth-tabbed-interface-styles';
    style.textContent = `
      /* Tabbed interface layout */
      .thoth-tabbed-interface {
        display: flex;
        flex-direction: column;
        height: 100%;
        max-height: 70vh;
        overflow: hidden;
      }

      /* Tab navigation */
      .thoth-tab-navigation {
        display: flex;
        background: var(--background-secondary);
        border-bottom: 1px solid var(--background-modifier-border);
        padding: 8px 12px 0 12px;
        gap: 4px;
        flex-shrink: 0;
        user-select: none;
        overflow-x: auto;
        scrollbar-width: none;
        -ms-overflow-style: none;
      }

      .thoth-tab-navigation::-webkit-scrollbar {
        display: none;
      }

      /* Tab buttons */
      .thoth-tab-button {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 10px 16px 8px 16px;
        background: transparent;
        border: none;
        border-radius: 6px 6px 0 0;
        cursor: pointer;
        color: var(--text-muted);
        font-size: 13px;
        font-weight: 500;
        transition: all 0.2s ease;
        border-bottom: 2px solid transparent;
        white-space: nowrap;
        min-width: fit-content;
        position: relative;
      }

      .thoth-tab-button:hover {
        background: var(--background-modifier-hover);
        color: var(--text-normal);
      }

      .thoth-tab-button:focus {
        outline: 2px solid var(--interactive-accent);
        outline-offset: -2px;
      }

      .thoth-tab-button.active {
        background: var(--background-primary);
        color: var(--text-accent);
        border-bottom-color: var(--interactive-accent);
        font-weight: 600;
      }

      .thoth-tab-button.active::after {
        content: '';
        position: absolute;
        bottom: -1px;
        left: 0;
        right: 0;
        height: 1px;
        background: var(--background-primary);
      }

      /* Tab icons and titles */
      .thoth-tab-icon {
        font-size: 14px;
        flex-shrink: 0;
      }

      .thoth-tab-title {
        flex: 1;
        text-align: left;
      }

      /* Content container */
      .thoth-tab-content-container {
        flex: 1;
        overflow: hidden;
        background: var(--background-primary);
        position: relative;
      }

      /* Tab panels */
      .thoth-tab-panel {
        height: 100%;
        overflow-y: auto;
        padding: 0;
        display: flex;
        flex-direction: column;
      }

      /* Responsive behavior */
      @media (max-width: 600px) {
        .thoth-tab-button {
          padding: 8px 12px 6px 12px;
          font-size: 12px;
        }

        .thoth-tab-icon {
          font-size: 12px;
        }

        .thoth-tabbed-interface {
          max-height: 80vh;
        }
      }

      /* Loading state for tab content */
      .thoth-tab-loading {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 200px;
        color: var(--text-muted);
        font-style: italic;
      }

      .thoth-tab-loading::before {
        content: '⏳';
        margin-right: 8px;
        font-size: 1.2em;
      }

      /* Error state for tab content */
      .thoth-tab-error {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 200px;
        color: var(--color-red);
        text-align: center;
        padding: 20px;
      }

      .thoth-tab-error-icon {
        font-size: 2em;
        margin-bottom: 12px;
      }

      .thoth-tab-error-message {
        font-weight: 500;
        margin-bottom: 8px;
      }

      .thoth-tab-error-details {
        font-size: 0.9em;
        color: var(--text-muted);
        font-style: italic;
      }

      /* Animation for tab switching */
      .thoth-tab-panel {
        animation: fadeInTab 0.2s ease;
      }

      @keyframes fadeInTab {
        from {
          opacity: 0;
          transform: translateY(10px);
        }
        to {
          opacity: 1;
          transform: translateY(0);
        }
      }

      /* Active tab indicator */
      .thoth-tab-button.active .thoth-tab-title {
        position: relative;
      }

      /* Focus ring for accessibility */
      .thoth-tab-button:focus-visible {
        outline: 2px solid var(--interactive-accent);
        outline-offset: 2px;
        border-radius: 4px;
      }

      /* High contrast mode support */
      @media (prefers-contrast: high) {
        .thoth-tab-button {
          border: 1px solid var(--background-modifier-border);
        }

        .thoth-tab-button.active {
          border-color: var(--interactive-accent);
          border-width: 2px;
        }
      }

      /* Reduced motion support */
      @media (prefers-reduced-motion: reduce) {
        .thoth-tab-button {
          transition: none;
        }

        .thoth-tab-panel {
          animation: none;
        }
      }
    `;

    document.head.appendChild(style);
  }
}

/**
 * Tab state management utilities
 */
export class TabStateManager {
  private static readonly STORAGE_KEY = 'thoth-tab-states';

  /**
   * Save tab state to localStorage
   */
  static saveTabState(interfaceId: string, state: { activeTabId: string; preferences: Record<string, any> }): void {
    try {
      const allStates = this.getAllTabStates();
      allStates[interfaceId] = state;
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(allStates));
    } catch (error) {
      console.warn('Failed to save tab state:', error);
    }
  }

  /**
   * Load tab state from localStorage
   */
  static loadTabState(interfaceId: string): { activeTabId: string; preferences: Record<string, any> } | null {
    try {
      const allStates = this.getAllTabStates();
      return allStates[interfaceId] || null;
    } catch (error) {
      console.warn('Failed to load tab state:', error);
      return null;
    }
  }

  /**
   * Get all saved tab states
   */
  private static getAllTabStates(): Record<string, any> {
    try {
      const stored = localStorage.getItem(this.STORAGE_KEY);
      return stored ? JSON.parse(stored) : {};
    } catch (error) {
      return {};
    }
  }

  /**
   * Clear tab state for specific interface
   */
  static clearTabState(interfaceId: string): void {
    try {
      const allStates = this.getAllTabStates();
      delete allStates[interfaceId];
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(allStates));
    } catch (error) {
      console.warn('Failed to clear tab state:', error);
    }
  }
}

/**
 * Tab factory for creating standard tab configurations
 */
export class TabFactory {
  /**
   * Create UI View tab configuration
   */
  static createUIViewTab(content: HTMLElement): TabConfig {
    return {
      id: 'ui-view',
      title: 'UI View',
      icon: '🎨',
      content: content,
      onActivate: () => {
        console.log('UI View tab activated');
      },
      onDeactivate: () => {
        console.log('UI View tab deactivated');
      }
    };
  }

  /**
   * Create Structured JSON tab configuration
   */
  static createStructuredJSONTab(content: HTMLElement): TabConfig {
    return {
      id: 'structured-json',
      title: 'Structured JSON',
      icon: '📋',
      content: content,
      onActivate: () => {
        console.log('Structured JSON tab activated');
      },
      onDeactivate: () => {
        console.log('Structured JSON tab deactivated');
      }
    };
  }

  /**
   * Create Raw JSON tab configuration
   */
  static createRawJSONTab(content: HTMLElement): TabConfig {
    return {
      id: 'raw-json',
      title: 'Raw JSON',
      icon: '📝',
      content: content,
      onActivate: () => {
        console.log('Raw JSON tab activated');
      },
      onDeactivate: () => {
        console.log('Raw JSON tab deactivated');
      }
    };
  }

  /**
   * Create all standard settings tabs
   */
  static createSettingsTabs(
    uiContent: HTMLElement,
    structuredContent: HTMLElement,
    rawContent: HTMLElement
  ): TabConfig[] {
    return [
      this.createUIViewTab(uiContent),
      this.createStructuredJSONTab(structuredContent),
      this.createRawJSONTab(rawContent)
    ];
  }
}

/**
 * Tabbed interface factory
 */
export class TabbedInterfaceFactory {
  /**
   * Create a new tabbed interface instance
   */
  static create(app: App, initialTabId?: string): ITabbedInterface {
    return new TabbedInterface(app, initialTabId);
  }

  /**
   * Create tabbed interface with standard settings tabs
   */
  static createSettingsInterface(
    app: App,
    uiContent: HTMLElement,
    structuredContent: HTMLElement,
    rawContent: HTMLElement
  ): ITabbedInterface {
    const tabbedInterface = new TabbedInterface(app, 'ui-view');

    // Add standard tabs
    const tabs = TabFactory.createSettingsTabs(uiContent, structuredContent, rawContent);
    tabs.forEach(tab => tabbedInterface.addTab(tab));

    return tabbedInterface;
  }
}

/**
 * Tab content lifecycle manager
 */
export class TabContentManager {
  private contentCache: Map<string, HTMLElement> = new Map();
  private lazyLoaders: Map<string, () => Promise<HTMLElement>> = new Map();

  /**
   * Register lazy content loader for a tab
   */
  registerLazyLoader(tabId: string, loader: () => Promise<HTMLElement>): void {
    this.lazyLoaders.set(tabId, loader);
  }

  /**
   * Get content for tab (with lazy loading support)
   */
  async getTabContent(tabId: string): Promise<HTMLElement> {
    // Check cache first
    if (this.contentCache.has(tabId)) {
      return this.contentCache.get(tabId)!;
    }

    // Check for lazy loader
    const loader = this.lazyLoaders.get(tabId);
    if (loader) {
      try {
        const content = await loader();
        this.contentCache.set(tabId, content);
        return content;
      } catch (error) {
        console.error(`Failed to load content for tab ${tabId}:`, error);
        return this.createErrorContent(`Failed to load ${tabId} content: ${error.message}`);
      }
    }

    // Create placeholder content
    return this.createPlaceholderContent(tabId);
  }

  /**
   * Create placeholder content for missing tabs
   */
  private createPlaceholderContent(tabId: string): HTMLElement {
    const container = document.createElement('div');
    container.className = 'thoth-tab-loading';
    container.textContent = `Loading ${tabId}...`;
    return container;
  }

  /**
   * Create error content for failed tabs
   */
  private createErrorContent(errorMessage: string): HTMLElement {
    const container = document.createElement('div');
    container.className = 'thoth-tab-error';

    container.createEl('div', { text: '❌', cls: 'thoth-tab-error-icon' });
    container.createEl('div', { text: 'Failed to Load Content', cls: 'thoth-tab-error-message' });
    container.createEl('div', { text: errorMessage, cls: 'thoth-tab-error-details' });

    return container;
  }

  /**
   * Clear content cache
   */
  clearCache(): void {
    this.contentCache.clear();
  }

  /**
   * Remove specific content from cache
   */
  removeCachedContent(tabId: string): void {
    this.contentCache.delete(tabId);
  }
}
